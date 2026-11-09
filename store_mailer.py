"""Daily "Replenishment needed" emails: each store's list of products with
nothing on the selling floor while the vault has some, built exactly like the
Inventory balance page (balance_report), from the live stock in Supabase.

- Every store compares Sales Floor and Vault. Wayne also compares Curbside
  Room and Upstairs Vault, and skips products with under 20 left in all.
- Bulk and tiered flower, accessories, apparel, promo and batteries are left out.
- Each store's manager gets their own store; the summary list (Chad, Firas)
  gets the counts for every store with all the PDFs attached.

Run it:
    python store_mailer.py                 # dry run: writes PDFs + .eml files, sends nothing
    python store_mailer.py --send          # really sends
    python store_mailer.py --store Wayne   # one store only

Settings come from environment variables, never from this (public) repo:
    SUPABASE_URL, SUPABASE_KEY              live stock (or ZIGGY_STOCK_DIR for local test files)
    MAILER_RECIPIENTS   path to a JSON file: {"Allegan": ["manager@..."], ...,
                        "summary": ["chad@...", "firas@..."]}
    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, MAIL_FROM   only for --send
"""
import argparse
import datetime as dt
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import balance_report
import live_stock

STORES = ["Allegan", "Burton", "Corunna", "Quincy", "Reading", "Sturgis",
          "Three Rivers", "Wayne"]
TITLE = "Replenishment needed"
TZ = ZoneInfo("America/Detroit")


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
    """(rows, pdf bytes, rooms) for one store, with the page's default settings."""
    df = prepare(df)
    all_rooms = sorted(df["Room"].dropna().unique().tolist())
    cats = sorted(c for c in df["Category"].astype(str).unique() if c.strip()) \
        if "Category" in df.columns else []
    options = [balance_report.BULK_OPTION] + cats
    df = balance_report.leave_out(df, balance_report.default_skip(options))
    rooms = balance_report.rooms_for(store, all_rooms)
    store_rooms = balance_report.storage_rooms(rooms)
    rows, _ = balance_report.zero_rows(df, rooms, store_rooms,
                                       balance_report.min_stock(store))
    pdf = balance_report.build_pdf(rows, rooms, store_rooms, store, stamp, title=TITLE)
    return rows, pdf, rooms


def _db():
    if os.environ.get("ZIGGY_STOCK_DIR"):
        return object()                      # live_stock reads the local files
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _filename(store, day):
    return f"Replenishment_{store.replace(' ', '_')}_{day:%Y-%m-%d}.pdf"


def store_email(store, rows, pdf, rooms, at, day, to):
    selling = [r for r in rooms if r not in balance_report.storage_rooms(rooms)]
    n = len(rows)
    msg = EmailMessage()
    msg["Subject"] = (f"{TITLE}: {store} · {n} item{'s' * (n != 1)} · {day:%a %m/%d}" if n
                      else f"{TITLE}: {store} · nothing today · {day:%a %m/%d}")
    msg["To"] = ", ".join(to)
    where = " or ".join(selling)
    if n:
        body = (f"Good morning {store},\n\n"
                f"{n} product{'s have' if n != 1 else ' has'} nothing in {where} while another "
                f"room has some. The list is attached: bring each one out, move it in "
                f"Backoffice, and tick it off.\n\n"
                f"Stock as of {at:%a %m/%d %I:%M %p}.\n\n— ZiggyBot")
        msg.set_content(body)
        msg.add_attachment(pdf, maintype="application", subtype="pdf",
                           filename=_filename(store, day))
    else:
        msg.set_content(f"Good morning {store},\n\nEverything in stock is in {where}. "
                        f"Nothing to bring out today.\n\nStock as of "
                        f"{at:%a %m/%d %I:%M %p}.\n\n— ZiggyBot")
    return msg


def summary_email(results, day, to):
    """results: [(store, count or None, pdf or None, note)]."""
    msg = EmailMessage()
    total = sum(c or 0 for _, c, _, _ in results)
    msg["Subject"] = f"{TITLE}: all stores · {total} items · {day:%a %m/%d}"
    msg["To"] = ", ".join(to)
    lines = [f"{s:<13} {('' if c is None else c):>5}  {note}".rstrip()
             for s, c, _, note in results]
    msg.set_content("Replenishment needed today, by store:\n\n"
                    + "\n".join(lines) + "\n\nEach store's list is attached.\n\n— ZiggyBot")
    for store, c, pdf, _ in results:
        if pdf and c:
            msg.add_attachment(pdf, maintype="application", subtype="pdf",
                               filename=_filename(store, day))
    return msg


def run(stores, send=False, out="mailer_out"):
    recipients = {}
    if os.environ.get("MAILER_RECIPIENTS"):
        recipients = json.loads(Path(os.environ["MAILER_RECIPIENTS"]).read_text("utf-8"))
    db = _db()
    now = dt.datetime.now(TZ)
    day = now.date()
    messages, results = [], []
    for store in stores:
        got = live_stock.latest(db, store)
        if not got:
            results.append((store, None, None, "no live stock — not sent"))
            continue
        df, at = got
        note = " (stock is over 2 hours old)" if live_stock.is_old(at, now) else ""
        rows, pdf, rooms = store_report(df, store, f"stock as of {at:%a %m/%d %I:%M %p}")
        results.append((store, len(rows), pdf, f"stock {at:%a %I:%M %p}{note}"))
        to = recipients.get(store) or []
        if to:
            messages.append(store_email(store, rows, pdf, rooms, at, day, to))
        else:
            results[-1] = results[-1][:3] + (results[-1][3] + " · no manager email set",)
    summary_to = recipients.get("summary") or []
    if summary_to:
        messages.append(summary_email(results, day, summary_to))

    for store, c, _, note in results:
        print(f"{store:<13} {'' if c is None else c:>5}  {note}")
    if not send:
        folder = Path(out)
        folder.mkdir(exist_ok=True)
        for store, c, pdf, _ in results:
            if pdf:
                (folder / _filename(store, day)).write_bytes(pdf)
        for i, m in enumerate(messages, 1):
            (folder / f"email_{i}.eml").write_bytes(bytes(m))
        print(f"Dry run: nothing sent. {len(messages)} email(s) and the PDFs are in {folder}/")
        return results
    if not messages:
        print("No recipients set (MAILER_RECIPIENTS); nothing sent.")
        return results
    sender = os.environ["MAIL_FROM"]
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        for m in messages:
            m["From"] = sender
            s.send_message(m)
    print(f"Sent {len(messages)} email(s).")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Email each store its Replenishment needed list.")
    ap.add_argument("--send", action="store_true", help="really send (default: dry run)")
    ap.add_argument("--store", action="append", choices=STORES, help="only this store")
    ap.add_argument("--out", default="mailer_out", help="dry-run folder")
    a = ap.parse_args()
    run(a.store or STORES, send=a.send, out=a.out)
    sys.exit(0)
