"""Check that the deals storage is actually wired up. Run from the repo root.

    python tools/check_supabase.py

Reads the same values the app does — .streamlit/secrets.toml, or the
SUPABASE_URL / SUPABASE_KEY environment variables — and walks the whole path the
app takes: connect, read the table, write a row, read it back, delete it. Each
step says what failed and what to do about it, because "storage is off" on its
own never tells you which of the three setup steps was missed.

The key is never printed.
"""
import datetime
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK, BAD, INFO = "  ✅", "  ❌", "  ·"
PROBE_WEEK = datetime.date(1999, 1, 4)      # a week nothing else will ever use


def secrets():
    """(url, key, where they came from)."""
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    if url and key:
        return url, key, "environment"
    path = pathlib.Path(".streamlit/secrets.toml")
    if not path.exists():
        return None, None, str(path)
    try:
        import tomllib
    except ModuleNotFoundError:                      # py<3.11
        import tomli as tomllib                      # noqa: F401
    data = tomllib.loads(path.read_text())
    return data.get("SUPABASE_URL"), data.get("SUPABASE_KEY"), str(path)


def main():
    print("\nZiggyBot — deals storage check\n" + "=" * 34)

    url, key, where = secrets()
    if not url or not key:
        print(f"{BAD} No SUPABASE_URL / SUPABASE_KEY found ({where}).")
        print(f"{INFO} Create .streamlit/secrets.toml with those two values, or")
        print(f"{INFO} export them into the environment. It is gitignored.")
        return 1
    host = url.split("//")[-1].split(".")[0]
    print(f"{OK} Credentials loaded from {where}")
    print(f"{INFO} project ref: {host}   (key: {len(key)} chars, not shown)")

    try:
        from supabase import create_client
    except ImportError:
        print(f"{BAD} The `supabase` library is not installed in this environment.")
        return 1

    try:
        db = create_client(url.strip().rstrip("/"), key.strip())
    except Exception as e:                                   # noqa: BLE001
        print(f"{BAD} Could not build a client: {e}")
        return 1
    print(f"{OK} Client created")

    import deal_store

    # 1. read
    try:
        rows = db.table(deal_store.TABLE).select("*").limit(1).execute().data
    except Exception as e:                                   # noqa: BLE001
        msg = str(e)
        print(f"{BAD} Cannot read `{deal_store.TABLE}`: {msg}")
        if "does not exist" in msg or "PGRST205" in msg:
            print(f"{INFO} The table was never created, or it was created in a "
                  f"different project than {host}.")
            print(f"{INFO} Run the deal_sheets SQL from the README in THIS project.")
        elif "permission" in msg.lower() or "row-level" in msg.lower():
            print(f"{INFO} The table exists but the key's role cannot read it — "
                  "the policies did not apply.")
        return 1
    print(f"{OK} Table `{deal_store.TABLE}` is readable ({len(rows)} row(s) sampled)")

    # 2. write / read back / delete
    try:
        db.table(deal_store.TABLE).upsert({
            "week_start": PROBE_WEEK.isoformat(),
            "name": "check_supabase.py probe",
            "payload": {"probe": True},
        }).execute()
    except Exception as e:                                   # noqa: BLE001
        print(f"{BAD} Cannot write: {e}")
        print(f"{INFO} Reads work but writes do not — the insert/update policies "
              "are missing. Re-run the SQL block; it is safe to run again.")
        return 1
    print(f"{OK} Write accepted")

    back = deal_store.get(db, PROBE_WEEK)
    print(f"{OK} Read back" if back is not None else f"{BAD} Wrote, but could not read back")

    try:
        db.table(deal_store.TABLE).delete().eq(
            "week_start", PROBE_WEEK.isoformat()).execute()
        print(f"{OK} Delete accepted (probe row cleaned up)")
    except Exception as e:                                   # noqa: BLE001
        print(f"{BAD} Cannot delete: {e}")
        print(f"{INFO} Pruning old weeks will fail, so more than two will pile up.")

    # 3. what the app would show
    weeks = deal_store.weeks(db)
    print(f"\n{OK} Storage is working. Weeks currently stored: {len(weeks)}")
    for w in weeks:
        current = "  ← covers today" if deal_store.is_current(w["week"]) else ""
        print(f"{INFO} {deal_store.week_label(w['week'])}  from {w['name'] or '?'}{current}")
    if not weeks:
        print(f"{INFO} None yet — upload a sheet in the app and press Save.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
