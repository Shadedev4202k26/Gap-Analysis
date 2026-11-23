"""Scans on the Transfers page, kept so a refresh or a sleeping tablet does not lose them.

A scan check lives in the open browser tab, so reloading the page used to throw
away every scan so far. Each check is now saved in Supabase under a key made of
the store and the manifest's package tags, so loading the same manifest again at
that store picks up where it left off.

The app's key is public, so the table only lets the app add and update a row,
never delete one; "Start over" saves an empty check in its place. Table and
policies: README -> "Transfer scans". If the table is missing, scanning works
exactly as before and the page says scans aren't being saved.
"""
import datetime
import hashlib

TABLE = "transfer_scans"
LOG_MAX = 3000          # scans kept in a saved log; a transfer is a few hundred at most


def key(store, tags):
    """One check per store and manifest: the same tags always give the same key."""
    h = hashlib.sha1("\n".join(sorted(tags)).encode()).hexdigest()[:20]
    return f"{store or 'no store'}:{h}"[:120]


def load(db, scan_key):
    """(state or None, error or None). state has scanned, extras, log, n and saved_at."""
    if db is None:
        return None, "no Supabase connection"
    try:
        data = (db.table(TABLE).select("state,updated_at").eq("scan_key", scan_key)
                .limit(1).execute().data)
    except Exception as e:                                   # noqa: BLE001
        return None, str(e)
    if not data:
        return None, None
    state = dict(data[0]["state"] or {})
    state["updated_at"] = data[0].get("updated_at")
    return state, None


def save(db, scan_key, store, name, packages, scanned, extras, log, n):
    """Write the check. Returns an error text, or None when it was saved."""
    if db is None:
        return "no Supabase connection"
    state = {"scanned": scanned, "extras": extras, "log": list(log)[-LOG_MAX:], "n": n}
    try:
        db.table(TABLE).upsert({
            "scan_key": scan_key, "store": (store or "")[:60], "manifest_name": (name or "")[:200],
            "packages": int(packages), "state": state,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }, on_conflict="scan_key").execute()
    except Exception as e:                                   # noqa: BLE001
        return str(e)
    return None
