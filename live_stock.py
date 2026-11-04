"""Each store's stock, live from Dutchie, so tags, Inventory balance and Aging
stock work without exporting a CSV.

Smilez Reports reads every store's inventory from the Dutchie API every 15
minutes during store hours and writes one row per store into the `ziggy_stock`
table here (Reports' app/ziggy_push.py). ZiggyBot only reads it: a Reports
update or restart never stops ZiggyBot, which keeps using the last copy and
says how old it is.

The copy is the same table as Dutchie's Inventory export (Package ID, Product,
Available, Strain, THC, Current price, Room, Category, Inventory date,
Expiration date) for the sellable rooms only: Sales Floor, Curbside Room, Vault
and Upstairs Vault. So every page reads it exactly as it reads an uploaded CSV.

A page takes one copy and keeps it for the visit (`pin`), so a tag picked from
it doesn't vanish when the next push lands; "Refresh" takes the newest.
"""
import base64
import datetime as dt
import gzip
import json
import os
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

TABLE = "ziggy_stock"
STORE_TZ = ZoneInfo("America/Detroit")
OLD_AFTER = dt.timedelta(hours=2)     # older than this during the day: say so


@st.cache_data(ttl=300, show_spinner=False, max_entries=16)
def _fetch(_db, store):
    """(updated_at, payload) for a store, shared by everyone for 5 minutes."""
    # Local testing only: ZIGGY_STOCK_DIR holds Reports' dry-run payloads
    # (ziggy_stock_<store>.txt from ziggy_push.push(send=False)). Never set online.
    folder = os.environ.get("ZIGGY_STOCK_DIR")
    if folder:
        f = os.path.join(folder, f"ziggy_stock_{store.lower().replace(' ', '-')}.txt")
        if not os.path.exists(f):
            return None
        at = dt.datetime.fromtimestamp(os.path.getmtime(f), dt.timezone.utc).isoformat()
        return at, open(f, encoding="utf-8").read()
    try:
        data = (_db.table(TABLE).select("updated_at,payload").eq("store", store)
                .limit(1).execute().data)
    except Exception:                                        # noqa: BLE001
        return None
    return (data[0]["updated_at"], data[0]["payload"]) if data else None


@st.cache_data(show_spinner=False, max_entries=16)
def _decode(payload):
    body = json.loads(gzip.decompress(base64.b64decode(payload)))
    return pd.DataFrame(body["rows"], columns=body["cols"]).astype(str)


def latest(db, store):
    """(DataFrame, updated_at as Michigan time) for the store, or None when
    there is no copy (not set up yet, or the store isn't sent)."""
    if db is None or not store:
        return None
    hit = _fetch(db, store)
    if not hit:
        return None
    try:
        df = _decode(hit[1])
        at = dt.datetime.fromisoformat(hit[0].replace("Z", "+00:00")).astimezone(STORE_TZ)
    except Exception:                                        # noqa: BLE001
        return None
    return df, at


def pin(db, store, key, refresh=False):
    """The copy this page uses for the visit: taken once per store and kept, so
    the rows don't change under someone picking tags. refresh=True takes the
    newest. Returns (DataFrame, updated_at) or None."""
    ss = st.session_state
    held = ss.get(key)
    if held and held[0] == store and not refresh:
        return held[1]
    if refresh:
        _fetch.clear()
    got = latest(db, store)
    ss[key] = (store, got)
    return got


def when(at, now=None):
    """'10:42 AM', or 'Tue 4:05 PM' when it isn't from today."""
    now = now or dt.datetime.now(STORE_TZ)
    t = at.strftime("%I:%M %p").lstrip("0")
    return t if at.date() == now.date() else f"{at.strftime('%a')} {t}"


def is_old(at, now=None):
    now = now or dt.datetime.now(STORE_TZ)
    return now - at > OLD_AFTER
