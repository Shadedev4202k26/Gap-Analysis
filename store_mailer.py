"""Daily "Replenishment needed" lists: each store's products with nothing on
the selling floor while another room has some, built exactly like the
Inventory balance page (balance_report), from the live stock in Supabase.

- Every store compares Sales Floor and Vault. Wayne also compares Curbside
  Room and Upstairs Vault, and skips products with under 20 left in all.
- Bulk and tiered flower, accessories, apparel, promo and batteries are left out.

How it reaches the managers (fully automatic, nothing to run or approve):
1. GitHub runs this every morning (.github/workflows/replenishment.yml). It
   empties the Dropbox folder /Replenishment, then puts in one PDF per store
   ("Allegan - 93 items - Tue 11-10.pdf") and, last, every store's lists in one
   PDF ("All stores - 448 items - Tue 11-10.pdf").
2. Chad's Power Automate flow "Daily replenishment email" starts on each new
   file there and emails it from chad@shopsmilez.com: a store's file to its
   manager, the All stores file to the summary list. The addresses live in
   the flow, never in this (public) repo.
If the stock is too old or anything fails, no file is written for that store,
so nothing stale is sent; GitHub emails the repo owner about a failed run.

Run it:
    python store_mailer.py                  # test: writes the PDFs to mailer_out/, nothing uploaded
    python store_mailer.py --dropbox        # really uploads (the flow then sends the emails)
    python store_mailer.py --store Wayne    # one store only

Settings (environment variables / GitHub secrets, never in the repo):
    SUPABASE_URL, SUPABASE_KEY                    live stock (or ZIGGY_STOCK_DIR for local test files)
    DROPBOX_APP_KEY, DROPBOX_REFRESH_TOKEN        only for --dropbox
"""
import argparse
import datetime as dt
import json
import os
import sys
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from pypdf import PdfReader, PdfWriter

import balance_report
import live_stock

STORES = ["Allegan", "Burton", "Corunna", "Quincy", "Reading", "Sturgis",
          "Three Rivers", "Wayne"]
TITLE = "Replenishment needed"
TZ = ZoneInfo("America/Detroit")
FOLDER = "/Replenishment"
# Reports pushes stock every 15 minutes while stores are open, so before
# opening the newest copy is from last night's close. Older than this: skip.
TOO_OLD = dt.timedelta(hours=20)


def _clean(v):
    return str(v).strip('="').strip()


def prepare(df):
    """The stock table with Product, Room and Qty (Available) cleaned, as the
    Inventory balance page reads it."""
    df = df.copy()
    df.columns = [_clean(c) for c in df.columns]
    qty = next((c for c in df.columns if c.lower() == "available"), None) \
        or next((c for c in df.columns if "available" in c.lower()), None) \
        or next((c for c in df.columns if "quantity" in c.lower() or c.lower() == "qty"), None)
    if qty is None or "Product" not in df.columns or "Room" not in df.columns:
        raise ValueError("stock is missing Product, Room or Available")
    df["Product"] = df["Product"].map(_clean)
    df["Room"] = df["Room"].map(_clean)
    df["Qty"] = pd.to_numeric(df[qty].map(_clean), errors="coerce").fillna(0)
    return df


def store_report(df, store, stamp=""):
    """(rows, pdf bytes) for one store, with the page's default settings."""
    df = prepare(df)
    all_rooms = sorted(df["Room"].dropna().unique().tolist())
    cats = sorted(c for c in df["Category"].astype(str).unique() if c.strip()) \
        if "Category" in df.columns else []
    df = balance_report.leave_out(df, balance_report.default_skip(
        [balance_report.BULK_OPTION] + cats))
    rooms = balance_report.rooms_for(store, all_rooms)
    store_rooms = balance_report.storage_rooms(rooms)
    rows, _ = balance_report.zero_rows(df, rooms, store_rooms,
                                       balance_report.min_stock(store))
    pdf = balance_report.build_pdf(rows, rooms, store_rooms, store, stamp, title=TITLE)
    return rows, pdf


def file_name(who, n, day):
    """'Allegan - 93 items - Tue 11-10.pdf': the flow reads the store from the
    part before the first ' - ' and uses the rest in the subject."""
    count = "nothing missing" if n == 0 else f"{n} item{'s' * (n != 1)}"
    return f"{who} - {count} - {day:%a %m-%d}.pdf"


def combine(pdfs):
    out = PdfWriter()
    for pdf in pdfs:
        for page in PdfReader(BytesIO(pdf)).pages:
            out.add_page(page)
    buf = BytesIO()
    out.write(buf)
    return buf.getvalue()


# ---------- Dropbox ----------
class Dropbox:
    def __init__(self, app_key, refresh_token):
        r = requests.post("https://api.dropboxapi.com/oauth2/token", timeout=30, data={
            "grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": app_key})
        if not r.ok:
            raise RuntimeError(f"Dropbox sign-in failed ({r.status_code}); connect Dropbox again.")
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def _rpc(self, path, body):
        r = requests.post(f"https://api.dropboxapi.com/2/{path}", json=body, headers=self.h, timeout=60)
        return r

    def files(self, folder):
        r = self._rpc("files/list_folder", {"path": folder})
        if r.status_code == 409 and "not_found" in r.text:
            self._rpc("files/create_folder_v2", {"path": folder})
            return []
        r.raise_for_status()
        return [e["path_lower"] for e in r.json()["entries"] if e[".tag"] == "file"]

    def delete(self, path):
        self._rpc("files/delete_v2", {"path": path}).raise_for_status()

    def upload(self, path, data):
        arg = json.dumps({"path": path, "mode": "overwrite", "mute": True})
        r = requests.post("https://content.dropboxapi.com/2/files/upload", data=data, timeout=120,
                          headers={**self.h, "Dropbox-API-Arg": arg,
                                   "Content-Type": "application/octet-stream"})
        r.raise_for_status()


def _db():
    if os.environ.get("ZIGGY_STOCK_DIR"):
        return object()                      # live_stock reads the local files
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def run(stores, upload=False, out="mailer_out"):
    db = _db()
    now = dt.datetime.now(TZ)
    day = now.date()
    files, lines, problems = [], [], []
    for store in stores:
        got = live_stock.latest(db, store)
        if not got:
            problems.append(f"{store}: no live stock")
            continue
        df, at = got
        if now - at > TOO_OLD:
            problems.append(f"{store}: stock is from {at:%a %m/%d %I:%M %p}, too old")
            continue
        rows, pdf = store_report(df, store, f"stock as of {at:%a %m/%d %I:%M %p}")
        files.append((file_name(store, len(rows), day), pdf, len(rows)))
        lines.append(f"{store:<13} {len(rows):>5}")
    for line in lines + problems:
        print(line)
    if not files:
        print("No store had fresh stock: nothing written.")
        return 1
    total = sum(n for _, _, n in files)
    files.append((file_name("All stores", total, day), combine([p for _, p, _ in files]), total))

    if not upload:
        folder = Path(out)
        folder.mkdir(exist_ok=True)
        for name, pdf, _ in files:
            (folder / name).write_bytes(pdf)
        print(f"Test run: nothing uploaded. {len(files)} PDFs in {folder}/")
        return 1 if problems else 0
    box = Dropbox(os.environ["DROPBOX_APP_KEY"], os.environ["DROPBOX_REFRESH_TOKEN"])
    for old in box.files(FOLDER):            # yesterday's lists out first
        box.delete(old)
    for name, pdf, _ in files:               # All stores last
        box.upload(f"{FOLDER}/{name}", pdf)
    print(f"Uploaded {len(files)} PDFs to Dropbox {FOLDER}.")
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Make each store's Replenishment needed list.")
    ap.add_argument("--dropbox", action="store_true", help="upload to Dropbox (the flow emails them)")
    ap.add_argument("--store", action="append", choices=STORES, help="only this store")
    ap.add_argument("--out", default="mailer_out", help="test-run folder")
    a = ap.parse_args()
    sys.exit(run(a.store or STORES, upload=a.dropbox, out=a.out))
