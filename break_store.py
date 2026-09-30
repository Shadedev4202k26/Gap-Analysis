"""Managers and the edit history for the break & lunch tracker.

The tracker (break-lunch-tracker.html) used to gate its Admin tab behind one
PIN kept in each tablet's browser. Managers now sign in by picking their name
from a per-store list kept here — adding it themselves the first time, since
there is no central list of managers — and every Admin change the tracker makes is
written to an append-only history so a changed break or a removed associate
can be traced to a name and a time.

The history is append-only on purpose: the policies grant the app's key select
and insert, never update or delete, and the timestamp is set by the database
rather than the tablet, so neither a manager nor a wrong tablet clock can
rewrite when something happened. Removing a manager deactivates them for the
same reason — their name stays attached to what they did.

Tables and policies: README → "Break & lunch tracker".
"""
import datetime
import re

MANAGERS = "break_managers"
HISTORY = "break_audit"
NAME_MAX = 40


class StoreError(RuntimeError):
    """Supabase refused the call — usually a missing table or RLS policy."""


def clean_name(name):
    """Trim and collapse spaces, so 'Jess ' and 'Jess' are one manager."""
    return re.sub(r"\s+", " ", str(name or "")).strip()[:NAME_MAX]


def managers(db, store=None, include_inactive=False):
    """[{'id', 'store', 'name', 'active'}] sorted by store then name."""
    try:
        q = db.table(MANAGERS).select("id,store,name,active")
        if store:
            q = q.eq("store", store)
        if not include_inactive:
            q = q.eq("active", True)
        rows = q.execute().data or []
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e
    return sorted(rows, key=lambda r: (r["store"], r["name"].casefold()))


def add_manager(db, store, name):
    """Add `name` to `store`'s list, or bring them back if they were removed.

    Returns 'added' or 'restored'. Matching ignores case, so re-adding 'jess'
    restores 'Jess' rather than creating a second person in the history.
    """
    name = clean_name(name)
    if not name:
        raise StoreError("type a name first")
    existing = next((m for m in managers(db, store, include_inactive=True)
                     if m["name"].casefold() == name.casefold()), None)
    if existing and existing["active"]:
        raise StoreError(f"{existing['name']} is already on the {store} list")
    try:
        if existing:
            db.table(MANAGERS).update({"active": True}).eq("id", existing["id"]).execute()
            outcome, name = "restored", existing["name"]
        else:
            db.table(MANAGERS).insert({"store": store, "name": name}).execute()
            outcome = "added"
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e
    log(db, store, "Settings", f"Manager {outcome}", name)
    return outcome


def remove_manager(db, manager):
    """Take a manager off the sign-in list. Their history stays as it was."""
    try:
        db.table(MANAGERS).update({"active": False}).eq("id", manager["id"]).execute()
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e
    log(db, manager["store"], "Settings", "Manager removed", manager["name"])


def log(db, store, manager, action, detail=""):
    """Append one line to the history. The database stamps the time."""
    try:
        db.table(HISTORY).insert({"store": store, "manager": manager,
                                  "action": action, "detail": detail,
                                  "device": "ZiggyBot settings"}).execute()
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e


def history(db, store=None, since=None, until=None, limit=5000):
    """History rows newest first. `since`/`until` are aware datetimes."""
    try:
        q = db.table(HISTORY).select("at,device_at,store,manager,action,detail,device")
        if store:
            q = q.eq("store", store)
        if since:
            q = q.gte("at", since.isoformat())
        if until:
            q = q.lt("at", until.isoformat())
        return q.order("at", desc=True).limit(limit).execute().data or []
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(str(e)) from e


def parse_ts(value):
    """Supabase timestamptz text → aware datetime, or None."""
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
