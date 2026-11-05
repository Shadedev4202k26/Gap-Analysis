"""Keep the last couple of weekly deals sheets in Supabase.

Uploading the sheet is a weekly chore for whoever opens the app first, so the
parsed sheet is saved once and every later visit reads it back. Three weeks are
kept: the current one to print from, the one before it to diff against so
"only what changed" can be worked out, and next week's, which arrives on
Tuesday or Wednesday (with two, it pushed last week out mid-week).

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
import base64
import datetime
import gzip

import deals as deals_mod

# The sheets Smilez Reports hands over (its app/ziggy_push.py): one row per
# sheet it holds (this week's, next week's), by file name, as a small gzipped
# CSV of the first tab with the struck-through text already left out.
FROM_REPORTS = "ziggy_deal_file"

TABLE = "deal_sheets"
KEEP = 3                     # last week, this week, and next week's once it's in


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


def reports_sheets(db):
    """((name, uploaded_at), ...) for the sheets Smilez Reports handed over,
    oldest first; empty when there are none. Small: a file is only read when
    it's needed."""
    try:
        data = (db.table(FROM_REPORTS).select("name,uploaded_at")
                .order("uploaded_at").execute().data)
    except Exception:                                        # noqa: BLE001
        return ()
    return tuple((r["name"], r["uploaded_at"]) for r in data or ())


def take_from_reports(db, info):
    """Store the sheet Reports handed over as its week, unless that week already
    holds one saved since (here, or an earlier hand-off), or the week is older
    than every week kept. Returns the week stored, or None."""
    name, at = info
    week = deals_mod.week_from_name(name)
    if not week:
        return None
    have = {w["week"]: w["uploaded_at"] for w in weeks(db)}
    if week in have and _when(have[week]) >= _when(at):
        return None
    if week not in have and len(have) >= KEEP and week < min(have):
        return None                    # an old sheet; storing it would push a newer one out
    try:
        data = (db.table(FROM_REPORTS).select("file").eq("name", name).limit(1)
                .execute().data)
        raw = gzip.decompress(base64.b64decode(data[0]["file"]))
    except Exception as e:                                   # noqa: BLE001
        raise StoreError(f"couldn't read the sheet Reports sent: {e}") from e
    save(db, deals_mod.load_sheet(raw, name))
    return week


def _when(stamp):
    """A Supabase timestamp as a datetime, so two can be compared."""
    try:
        return datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def week_label(week):
    """'Sep 21 - Sep 27' for a week starting on `week`."""
    end = week + datetime.timedelta(days=6)
    # .day, not %-d: the no-padding flag is glibc/BSD only and Windows rejects it.
    return f"{week:%b} {week.day} – {end:%b} {end.day}"


def is_current(week, today=None):
    """Does `week` cover today? Weeks run from the date in the filename."""
    today = today or datetime.date.today()
    return week <= today <= week + datetime.timedelta(days=6)
