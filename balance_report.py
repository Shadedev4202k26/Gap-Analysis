"""Inventory balance: the products missing from a selling room while another
room has them, and the printable check list. The page and the store mailer
both build it from here, so an emailed list is the same one staff see.

Managers found the old balancing analysis (room mix %, low-stock flags) far
too long to work in a shift, so on 2026-11-06 it was dropped: the page only
reports zeros. A zero in a storage room (Vault, Upstairs Vault) is normal and
never listed; a zero on the Sales Floor (or Wayne's Curbside Room) is.
"""
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

import aging

# Dutchie categories left out to start (lower case, without Dutchie's leading
# "-"). Not cannabis, or tiered flower: the Red/White/Blue tiers, Secret Stash
# and Outdoor are weighed out like bulk and never balanced between rooms (they
# made Wayne's Curbside list ~1,000 lines long). Staff can add any back.
SKIP = {"accessories", "apparel", "vaporizer batteries", "promotional", "retired skus",
        "red tier", "white tier", "blue tier", "secret stash",
        "secret stash infused flower", "outdoor flower", "infused flower"}
# Bulk deli flower ("BULK | brand | strain") isn't a Dutchie category, so it is
# offered as one: it's weighed out, not moved by the unit.
BULK_OPTION = "Bulk flower (BULK | …)"

# The rooms each store compares. Wayne also sells from its Curbside Room and
# keeps back stock upstairs; every other store is just Sales Floor and Vault.
ROOMS = {"Wayne": ["Sales Floor", "Curbside Room", "Vault", "Upstairs Vault"]}
ROOMS_DEFAULT = ["Sales Floor", "Vault"]

# Products with fewer than this many in stock (all rooms together) aren't
# worth moving: Wayne doesn't balance anything under about 20.
MIN_STOCK = {"Wayne": 20}


def min_stock(store):
    """Where the page's "fewest in stock" slider starts for `store`."""
    return MIN_STOCK.get(store, 0)

# How to work the list: on the page and at the top of the PDF.
STEPS = [
    "Take the list to the sales floor and check each item against what is really on the wall.",
    "<b>It's on the wall:</b> Dutchie has it in the wrong room or count. Make the adjustment "
    "in Backoffice, then tick it off.",
    "<b>It's not on the wall:</b> bring it out from the vault, move it to the selling room in "
    "Backoffice, then tick it off.",
    "Ask a manager about anything you can't find in either place.",
]


def default_skip(options):
    """The leave-out choices picked to start, from the ones on offer."""
    return [c for c in options if c == BULK_OPTION or c.strip().lstrip("-").strip().lower() in SKIP]


def leave_out(df, skip):
    """df without the products in `skip` (categories, and BULK_OPTION for bulk)."""
    if BULK_OPTION in skip:
        df = df[~df["Product"].map(aging.is_bulk)]
    if "Category" in df.columns and skip:
        df = df[~df["Category"].astype(str).isin(skip)]
    return df


def storage_rooms(rooms):
    """Back-stock rooms, where a zero is normal: Vault, Storage, Back..."""
    return [r for r in rooms if "vault" in r.lower()
            or "storage" in r.lower() or "back" in r.lower()]


def rooms_for(store, available):
    """The rooms `store` compares, out of the ones its stock has. Falls back to
    every room when none of the usual names are there (an odd CSV export)."""
    want = ROOMS.get(store, ROOMS_DEFAULT)
    have = {r.lower(): r for r in available}
    got = [have[w.lower()] for w in want if w.lower() in have]
    return got if len(got) > 1 else list(available)


def _qty(v):
    return int(v) if float(v).is_integer() else round(float(v), 2)


def zero_rows(df, rooms, store_rooms, min_total=0):
    """(rows, checked): one row per product with zero in a selling room while
    another room has some, sorted by category then name, and how many products
    were compared. Row columns: Category, Product, each room's qty, Missing in.
    `df` needs Product, Room and Qty (Category if it has one). Products with
    fewer than `min_total` across the rooms are skipped and not counted."""
    sub = df[df["Room"].isin(rooms)]
    cols = ["Category", "Product"] + list(rooms) + ["Missing in"]
    if sub.empty:
        return pd.DataFrame(columns=cols), 0
    pivot = (sub.groupby(["Product", "Room"])["Qty"].sum()
             .unstack(fill_value=0).reindex(columns=rooms, fill_value=0))
    cat = sub.groupby("Product")["Category"].first() if "Category" in sub.columns else {}
    selling = [r for r in rooms if r not in store_rooms]
    rows, checked = [], 0
    for product, q in pivot.iterrows():
        total = q.clip(lower=0).sum()
        if total <= 0 or total < min_total:
            continue                      # none anywhere, or too few to move
        checked += 1
        missing = [r for r in selling if q[r] <= 0]
        if not missing:
            continue
        row = {"Category": str(cat.get(product, "") or ""), "Product": product}
        row.update({r: _qty(max(q[r], 0)) for r in rooms})
        row["Missing in"] = ", ".join(missing)
        rows.append(row)
    out = pd.DataFrame(rows, columns=cols)
    if not out.empty:
        out = (out.assign(_c=out["Category"].str.lower(), _p=out["Product"].str.lower())
               .sort_values(["_c", "_p"]).drop(columns=["_c", "_p"]).reset_index(drop=True))
    return out, checked


def _fmt(v):
    """A count as printed: 64, not 64.0; grams keep their decimals."""
    return f"{v:g}"


def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(rows, rooms, store_rooms, store="", stamp="", title="Missing stock check"):
    """The printable check list: how to work it, then the products grouped by
    category with each room's count and an empty Done box to tick. The store
    mailer calls the same list "Replenishment needed"."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30,
                            topMargin=30, bottomMargin=30,
                            title=f"{title} {store}".strip())
    base = getSampleStyleSheet()["Normal"]
    ts = ParagraphStyle("T", parent=base, fontSize=17, leading=20, fontName="Helvetica-Bold",
                        textColor=colors.HexColor("#0F172A"))
    ss = ParagraphStyle("S", parent=base, fontSize=9, leading=12,
                        textColor=colors.HexColor("#4B5563"), spaceAfter=6)
    step = ParagraphStyle("St", parent=base, fontSize=8.5, leading=11,
                          textColor=colors.HexColor("#1F2937"))
    cs = ParagraphStyle("C", parent=base, fontSize=8, leading=9.5,
                        textColor=colors.HexColor("#111827"))
    hs = ParagraphStyle("H", parent=cs, fontName="Helvetica-Bold", textColor=colors.white)
    hn = ParagraphStyle("HN", parent=hs, alignment=1)
    cat_s = ParagraphStyle("Cat", parent=cs, fontName="Helvetica-Bold", fontSize=8.5,
                           textColor=colors.HexColor("#5B21B6"))

    selling = [r for r in rooms if r not in store_rooms]
    show_missing = len(selling) > 1        # one selling room: its zero says it all
    head = f"{_esc(title)} · {_esc(store)}" if store else _esc(title)
    story = [Paragraph(head, ts),
             Paragraph(f"{len(rows)} items with nothing in "
                       f"{' or '.join(_esc(r) for r in selling)} while another room has some"
                       + (f" &nbsp;·&nbsp; {_esc(stamp)}" if stamp else ""), ss)]
    steps = Table([[Paragraph(f"<b>{i}.</b> {s}", step)] for i, s in enumerate(STEPS, 1)],
                  colWidths=[doc.width])
    steps.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F3FF")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#C4B5FD")),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, -1), (-1, -1), 6)]))
    story += [steps, Paragraph("&nbsp;", ss)]

    if rows.empty:
        story.append(Paragraph("Nothing missing: every product is in "
                               + " and ".join(_esc(r) for r in selling) + ".", ss))
        doc.build(story)
        return buffer.getvalue()

    room_w, miss_w, done_w = 46, 92 if show_missing else 0, 34
    prod_w = doc.width - room_w * len(rooms) - miss_w - done_w
    widths = [prod_w] + [room_w] * len(rooms) + ([miss_w] if show_missing else []) + [done_w]
    ncol = len(widths)
    data = [[Paragraph("Product", hs)] + [Paragraph(_esc(r), hn) for r in rooms]
            + ([Paragraph("Missing in", hs)] if show_missing else []) + [Paragraph("Done", hn)]]
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("FONTSIZE", (0, 1), (-1, -1), 8), ("LEADING", (0, 1), (-1, -1), 9.5),
             ("ALIGN", (1, 1), (-1, -1), "CENTER"),
             ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    last_cat = None
    for _, r in rows.iterrows():
        c = r["Category"] or "Uncategorized"
        if c != last_cat:
            data.append([Paragraph(_esc(c), cat_s)] + [""] * (ncol - 1))
            i = len(data) - 1
            style += [("SPAN", (0, i), (-1, i)),
                      ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#EDE9FE"))]
            last_cat = c
        cells = [Paragraph(_esc(r["Product"]), cs)]
        for room in rooms:
            v = r[room]
            cells.append(_fmt(v))
            if v == 0 and room in selling:
                style += [("TEXTCOLOR", (len(cells) - 1, len(data)), (len(cells) - 1, len(data)),
                           colors.HexColor("#B91C1C")),
                          ("FONTNAME", (len(cells) - 1, len(data)), (len(cells) - 1, len(data)),
                           "Helvetica-Bold")]
        if show_missing:
            cells.append(Paragraph(_esc(r["Missing in"]), cs))
        cells.append("")
        data.append(cells)
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle(style))
    story.append(t)
    doc.build(story)
    return buffer.getvalue()
