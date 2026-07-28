"""Combine different strain types onto the SAME sheet.

Each strain type has its own template with its own coloured border art, and the
three templates do not share an identical art grid (hybrid's row pitch is ~145.8pt
vs ~144.0pt for sativa/indica). So a mixed page is built by:

  1. filling each type's template with its rows placed at their target slots,
  2. clipping that filled page to the source cell of each of those slots,
  3. translating the clipped region onto a canonical destination grid.

The border art and the text move together, so every tag keeps its own colour.
"""
import io
import re

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf._page import PageObject
from pypdf.generic import DecodedStreamObject, NameObject

import preroll_tags as pt

TYPE_ORDER = ["sativa", "hybrid", "indica"]


def _field_centres(src):
    """slot -> (cx, cy) centre of the slot's field block."""
    r = PdfReader(src)
    slots = {}
    for a in r.pages[0].get("/Annots", []) or []:
        o = a.get_object()
        v = o.get("/V")
        if v is None and o.get("/Parent"):
            v = o["/Parent"].get_object().get("/V")
        if o.get("/Rect") and isinstance(v, str):
            m = re.match(r"(BRAND|STRAIN|THC|PRICE)_+\s*(\d+)", v.strip())
            if m:
                slots.setdefault(int(m.group(2)), []).append(
                    [float(x) for x in o["/Rect"]])
    out = {}
    for s, rects in slots.items():
        xs = [x[0] for x in rects] + [x[2] for x in rects]
        ys = [x[1] for x in rects] + [x[3] for x in rects]
        out[s] = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    return out


def _median(v):
    v = sorted(v)
    n = len(v)
    if not n:
        return 0.0
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def _cluster(vals, tol=6.0):
    """Cluster near-equal coordinates into ordered group centres."""
    out = []
    for v in sorted(vals):
        if out and abs(v - out[-1][-1]) <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(g) / len(g) for g in out]


def tag_cells(src):
    """slot -> (x0, y0, x1, y1) art-true tag cell, in PDF points.

    Cells are built from the template's own field grid (which was placed on the
    art grid), corrected by the constant art-vs-field vertical offset when that
    offset can be measured from the border art.
    """
    fc = _field_centres(src)
    if not fc:
        return {}
    col_c = _cluster([c[0] for c in fc.values()])
    row_c = _cluster([c[1] for c in fc.values()])
    row_c = sorted(row_c, reverse=True)                 # top row first

    w = _median([col_c[i + 1] - col_c[i] for i in range(len(col_c) - 1)]) \
        if len(col_c) > 1 else 0.0
    h = _median([row_c[i] - row_c[i + 1] for i in range(len(row_c) - 1)]) \
        if len(row_c) > 1 else 0.0
    if w <= 0:
        w = float(PdfReader(src).pages[0].mediabox[2]) / max(1, len(col_c))
    if h <= 0:
        h = float(PdfReader(src).pages[0].mediabox[3]) / max(1, len(row_c))

    dy = 0.0
    try:                                                # coloured-border templates
        import build_split as bs
        art = bs.detect_interior_centres(src)
        if len(art) == len(row_c):
            dy = _median([a - b for a, b in zip(sorted(art, reverse=True), row_c)])
    except Exception:
        dy = 0.0

    cells = {}
    for s, (cx, cy) in fc.items():
        cells[s] = (cx - w / 2, cy + dy - h / 2, cx + w / 2, cy + dy + h / 2)
    return cells


def _clipped_page(src_pdf, rect):
    """A fresh copy of src_pdf's page 1 whose content is clipped to rect."""
    page = PdfReader(src_pdf).pages[0]
    data = page.get_contents().get_data()
    x0, y0, x1, y1 = rect
    clip = f"q {x0:.3f} {y0:.3f} {x1 - x0:.3f} {y1 - y0:.3f} re W n\n".encode("latin-1")
    stream = DecodedStreamObject()
    stream.set_data(clip + data + b"\nQ")
    page[NameObject("/Contents")] = stream
    return page


def build_combined(templates, rows_in_order, tmpdir, pair=1):
    """Mix strain types on shared pages. rows_in_order is a flat list of row
    dicts (each with a 'type'); they fill slots in order. Returns PDF bytes.

    `pair` is how many slots make up one physical tag (2 for split templates).
    When pair > 1 the rows are grouped by type and each group padded to a whole
    number of tags, so the two halves of a tag never end up different colours.
    """
    rows_in_order = [r for r in rows_in_order if r]
    if not rows_in_order:
        return b""

    if pair > 1:
        order, groups = [], {}
        for r in rows_in_order:
            t = r.get("type", "hybrid")
            if t not in groups:
                groups[t] = []
                order.append(t)
            groups[t].append(r)
        packed = []
        for t in order:
            g = list(groups[t])
            while len(g) % pair:                      # pad to whole tags
                g.append({"brand": "", "strain": "", "thc": "", "price": "", "type": t})
            packed.extend(g)
        rows_in_order = packed

    ref = next((t for t in TYPE_ORDER if t in templates), None)
    spp = pt.slots_per_page(templates[ref])
    cells = {t: tag_cells(p) for t, p in templates.items()}
    dest = cells[ref]

    pw = float(PdfReader(templates[ref]).pages[0].mediabox[2])
    ph = float(PdfReader(templates[ref]).pages[0].mediabox[3])

    writer = PdfWriter()
    pages = [rows_in_order[i:i + spp] for i in range(0, len(rows_in_order), spp)]
    for pi, prows in enumerate(pages):
        # Which slots does each type occupy on this page?
        by_type = {}
        for idx, row in enumerate(prows):
            by_type.setdefault(row.get("type", "hybrid"), []).append((idx + 1, row))

        filled = {}
        for t, items in by_type.items():
            slotted = [None] * spp
            for slot, row in items:
                slotted[slot - 1] = row
            filled[t] = pt._fill_template(templates[t], slotted, tmpdir, f"mix{pi}_{t}")

        out_page = PageObject.create_blank_page(width=pw, height=ph)
        for t, items in by_type.items():
            for slot, _ in items:
                src_rect = cells[t].get(slot)
                dst_rect = dest.get(slot)
                if not src_rect or not dst_rect:
                    continue
                layer = _clipped_page(filled[t], src_rect)
                dx = dst_rect[0] - src_rect[0]
                dy = dst_rect[1] - src_rect[1]
                out_page.merge_transformed_page(
                    layer, Transformation().translate(dx, dy))
        writer.add_page(out_page)

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.getvalue()
