"""Keep the last couple of weekly deals sheets in Supabase.

Uploading the sheet is a weekly chore for whoever opens the app first, so the
parsed sheet is saved once and every later visit reads it back. Two weeks are
kept: the current one to print from, and the one before it to diff against so
"only what changed" can be worked out.

The stored payload is deals.Sheet.to_dict() — the store columns only, about
24KB, rather than the 2MB export, which is almost entirely empty padding
columns.

Table (see README for the walkthrough):

    create table public.deal_sheets (
        week_start  date primary key,
        name        text not null default '',
        payload     jsonb not null,
        uploaded_at timestamptz not null default now()
    );
"""
import datetime

import deals as deals_mod

TABLE = "deal_sheets"
KEEP = 2                     # current week + the one before it


class StoreError(RuntimeError):
    """Supabase refused the call — usually a missing table or RLS policy."""


def _rows(db):
    try:
        return db.table(TABLE).select("*").order("week_start", desc=True).execute().data or []
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e


def available(db):
    """True when the table exists and can be read with the app's key."""
    if db is None:
        return False
    try:
        _rows(db)
        return True
    except StoreError:
        return False


def weeks(db):
    """Stored weeks, newest first: [{'week': date, 'name': str, 'uploaded_at': str}]."""
    out = []
    for r in _rows(db):
        try:
            wk = datetime.date.fromisoformat(str(r["week_start"]))
        except (KeyError, ValueError):
            continue
        out.append({"week": wk, "name": r.get("name") or "",
                    "uploaded_at": r.get("uploaded_at") or ""})
    return out


def get(db, week):
    """The Sheet stored for `week`, or None."""
    try:
        data = db.table(TABLE).select("*").eq("week_start", week.isoformat()).execute().data
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e
    if not data:
        return None
    return deals_mod.Sheet.from_dict(data[0]["payload"])


def save(db, sheet):
    """Save (or replace) one week, then drop anything older than the last KEEP.

    Keyed on the week rather than the upload, so re-uploading a corrected export
    for the same week overwrites it instead of pushing the previous week out.
    """
    if not sheet.week:
        raise StoreError("that export has no date in its filename, so there is "
                         "no week to file it under")
    try:
        db.table(TABLE).upsert({
            "week_start": sheet.week.isoformat(),
            "name": sheet.name or "",
            "payload": sheet.to_dict(),
            "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }).execute()
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e
    return prune(db)


def delete(db, week):
    """Remove one stored week. Returns True when a row went."""
    try:
        res = db.table(TABLE).delete().eq("week_start", week.isoformat()).execute()
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e
    return bool(res.data)


def prune(db, keep=KEEP):
    """Delete all but the newest `keep` weeks. Returns how many went."""
    stored = weeks(db)
    gone = 0
    for row in stored[keep:]:
        try:
            db.table(TABLE).delete().eq("week_start", row["week"].isoformat()).execute()
            gone += 1
        except Exception:                                    # noqa: BLE001, S110
            pass
    return gone


def week_label(week):
    """'Sep 21 - Sep 27' for a week starting on `week`."""
    end = week + datetime.timedelta(days=6)
    return f"{week:%b %-d} – {end:%b %-d}"


def is_current(week, today=None):
    """Does `week` cover today? Weeks run from the date in the filename."""
    today = today or datetime.date.today()
    return week <= today <= week + datetime.timedelta(days=6)
