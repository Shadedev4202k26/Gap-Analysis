"""Inventory balance's report: which products are lopsided or missing from a
room, and its PDF. The page and the store mailer both build it from here, so
the emailed report is the same one staff see on the page.

The "zero report" is balancing off: every product with zero in a selling room
(a storage room at zero is normal and not reported).
"""
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

import aging

# Dutchie categories left out to start (lower case): not cannabis, so they only
# pad the list. Staff can add them back on the page.
SKIP = {"accessories", "apparel", "vaporizer batteries", "promotional", "retired skus"}
# Bulk deli flower ("BULK | brand | strain") isn't a Dutchie category, so it is
# offered as one: it's weighed out, not moved by the unit.
BULK_OPTION = "Bulk flower (BULK | …)"


def default_skip(options):
    """The leave-out choices picked to start, from the ones on offer."""
    return [c for c in options if c == BULK_OPTION or c.strip().lower() in SKIP]


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


def room_rows(df, rooms, store_rooms, balancing, imbalance_pct=70, min_stock=5, min_total=0):
    """One row per product: its qty in each room, Total, Status, and Mix % or
    Missing In. `df` needs Product, Room and Qty."""
    sub = df[df['Room'].isin(rooms)]
    pivot = sub.groupby(['Product', 'Room'])['Qty'].sum().unstack(fill_value=0)
    # ensure all selected rooms are columns even if absent in data
    for r in rooms:
        if r not in pivot.columns:
            pivot[r] = 0
    pivot = pivot[rooms]

    rows = []
    for product, prow in pivot.iterrows():
        qtys = {r: int(prow[r]) for r in rooms}
        total = sum(qtys.values())
        if total <= 0 or total < min_total:
            continue  # nothing here, or below the total-qty filter
        shares = {r: qtys[r] / total for r in rooms}
        top_share = max(shares.values())
        empty_rooms = [r for r in rooms if qtys[r] == 0]
        # only zeros in SELLING rooms count as a gap
        gap_rooms = [r for r in empty_rooms if r not in store_rooms]
        mix = " / ".join(f"{r.split()[0]} {round(shares[r]*100)}%" for r in rooms)
        entry = {"Product Name": product}
        for r in rooms:
            entry[r] = qtys[r]
        entry["Total"] = total
        if balancing:
            # Trigger 1: lopsided beyond the imbalance threshold
            imbalanced = len(rooms) > 1 and (top_share * 100) > imbalance_pct
            # Trigger 2: a room at/below minimum while another has stock to move
            sell_rooms  = [r for r in rooms if r not in store_rooms] or rooms
            low_room    = any(qtys[r] <= min_stock for r in sell_rooms)
            source_room = any(qtys[r] > min_stock for r in rooms)
            low_flag    = len(rooms) > 1 and low_room and source_room
            status = "🔄 Rebalance" if (imbalanced or low_flag) else "✅ Balanced"
            entry["Mix %"] = mix
            entry["Status"] = status
        else:
            gap = len(rooms) > 1 and len(gap_rooms) > 0
            entry["Missing In"] = ", ".join(gap_rooms) if gap_rooms else "—"
            entry["Status"] = "⚠️ Gap" if gap else "✅ In all rooms"
        entry["_skew"] = top_share  # for sorting
        rows.append(entry)

    return pd.DataFrame(rows)


def build_pdf(dataframe, threshold_value, rooms, min_stock=None, mode="balance",
              qty_label="Available"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=36, leftMargin=36, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=styles['Heading1'], fontSize=22,
                        textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    ss = ParagraphStyle('S', parent=styles['Normal'], fontSize=11,
                        textColor=colors.HexColor('#4B5563'), fontName='Helvetica-Bold', spaceAfter=18)
    cs = ParagraphStyle('C', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#374151'), leading=11)
    hs = ParagraphStyle('H', parent=styles['Normal'], fontSize=9,
                        fontName='Helvetica-Bold', textColor=colors.HexColor('#FFFFFF'))

    gap_mode  = (mode == "gap")
    flag_word = "Gap" if gap_mode else "Rebalance"
    extra_col = "Missing In" if gap_mode else "Mix %"
    n_flag = int(dataframe["Status"].str.contains(flag_word).sum())
    n_ok   = len(dataframe) - n_flag

    title    = "Ziggyz Room Comparison" if gap_mode else "Ziggyz Room Balance Report"
    subtitle = ("ROOM COMPARISON &middot; MISSING STOCK" if gap_mode
                else "STOCK MIX &amp; ROOM BALANCE MANIFEST")
    story = [Paragraph(title, ts), Paragraph(subtitle, ss)]

    if gap_mode:
        rule_txt = f"<b>Gap</b> = zero {qty_label} in one or more rooms"
        md = [[Paragraph(f"<b>Products:</b> {len(dataframe)}", cs),
               Paragraph(f"<b>Gaps:</b> {n_flag}", cs),
               Paragraph(f"<b>In all rooms:</b> {n_ok}", cs),
               Paragraph(rule_txt, cs)]]
    else:
        rule_txt = f"<b>Counts:</b> {qty_label} &nbsp;·&nbsp; <b>Imbalance:</b> &gt;{threshold_value}%"
        if min_stock is not None:
            rule_txt += f" &nbsp;·&nbsp; <b>Min stock:</b> &le;{min_stock}"
        md = [[Paragraph(f"<b>Products:</b> {len(dataframe)}", cs),
               Paragraph(f"<b>Rebalance:</b> {n_flag}", cs),
               Paragraph(f"<b>Balanced:</b> {n_ok}", cs),
               Paragraph(rule_txt, cs)]]
    mt = Table(md, colWidths=[110, 110, 110, 186])
    mt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F8FAFC')),
                             ('BOX',(0,0),(-1,-1),1,colors.HexColor('#E5E7EB')),
                             ('INNERGRID',(0,0),(-1,-1),0.5,colors.HexColor('#E5E7EB')),
                             ('PADDING',(0,0),(-1,-1),10),('ALIGN',(0,0),(-1,-1),'CENTER')]))
    story.append(mt)
    story.append(Paragraph("Rooms: " + ", ".join(rooms), ss))

    # Header: Product | [each room qty] | Total | (Mix % | Missing In) | Status
    header = [Paragraph("Product", hs)]
    for r in rooms:
        header.append(Paragraph(r, hs))
    header += [Paragraph("Total", hs), Paragraph(extra_col, hs), Paragraph("Status", hs)]
    tdata = [header]

    for _, row in dataframe.iterrows():
        cells = [Paragraph(str(row['Product Name']), cs)]
        for r in rooms:
            cells.append(Paragraph(str(row[r]), cs))
        cells.append(Paragraph(str(row['Total']), cs))
        cells.append(Paragraph(str(row.get(extra_col, "")), cs))
        status_txt = (str(row['Status']).replace("🔄", "").replace("✅", "")
                      .replace("⚠️", "").strip())
        cells.append(Paragraph(status_txt, cs))
        tdata.append(cells)

    n_rooms = len(rooms)
    room_w = min(70, 150 / max(1, n_rooms))
    prod_w = 150
    total_w, extra_w, status_w = 40, 110, 78
    col_widths = [prod_w] + [room_w]*n_rooms + [total_w, extra_w, status_w]

    dt = Table(tdata, colWidths=col_widths, repeatRows=1)
    style = [('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1E293B')),
             ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#E5E7EB')),
             ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
             ('PADDING',(0,0),(-1,-1),5),
             ('ALIGN',(1,0),(-1,-1),'CENTER'),
             ('ALIGN',(0,0),(0,-1),'LEFT')]
    # Amber bar on rows needing attention; faint green bar on the rest
    for i, (_, row) in enumerate(dataframe.iterrows(), start=1):
        if flag_word in str(row['Status']):
            style.append(('LINEBEFORE',(0,i),(0,i),3,colors.HexColor('#D97706')))
        else:
            style.append(('LINEBEFORE',(0,i),(0,i),3,colors.HexColor('#34D399')))
    dt.setStyle(TableStyle(style))
    story.append(dt)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
