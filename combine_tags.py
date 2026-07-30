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

__version__ = "2.0-aligned"   # art-frame detection + uniform destination grid

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


def _raster(src, dpi=150):
    import os
    import subprocess
    import tempfile

    import numpy as np
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "p")
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-singlefile", src, p],
                       check=True, capture_output=True)
        return np.asarray(Image.open(p + ".png").convert("RGB")).astype(float) / 255.0


def _bands(hit, s, merge_pt=3.0):
    """Contiguous True runs in `hit`, merged when closer than merge_pt."""
    runs, st = [], None
    for i, v in enumerate(hit):
        if v and st is None:
            st = i
        elif not v and st is not None:
            runs.append((st, i - 1))
            st = None
    if st is not None:
        runs.append((st, len(hit) - 1))
    out = []
    for r in runs:
        if out and (r[0] - out[-1][1]) / s < merge_pt:
            out[-1] = (out[-1][0], r[1])
        else:
            out.append(list(r))
            out[-1] = tuple(out[-1])
            out[-1] = (r[0], r[1])
    return out


def _boundaries(bands, s, flip=None):
    """Border bands -> the n+1 cut lines separating n tags."""
    if len(bands) < 2:
        return []
    edges = [bands[0][0]]
    for b in bands[1:-1]:
        edges.append((b[0] + b[1]) / 2.0)
    edges.append(bands[-1][1])
    return [e / s for e in edges]


def art_cells(src, dpi=150):
    """True tag boxes taken from the printed border frame.

    Returns {slot: (x0, y0, x1, y1)} in reading order, or None when the template
    has no coloured frame (e.g. the hook tags, whose art is a background image).
    """
    a = _raster(src, dpi)
    s = dpi / 72.0
    H, W = a.shape[:2]
    sat = a.max(2) - a.min(2)
    col = (sat > 0.20) & (a.max(2) > 0.35)

    vstrip = col[:, int(80 * s):int(120 * s)]
    hbands = _bands(vstrip.mean(1) > 0.5, s)
    hstrip = col[int(60 * s):int(100 * s), :]
    vbands = _bands(hstrip.mean(0) > 0.5, s)
    if len(hbands) < 3 or len(vbands) < 3:
        return None

    ys = _boundaries(hbands, s)                    # image-space, top -> bottom
    xs = _boundaries(vbands, s)
    if len(ys) < 2 or len(xs) < 2:
        return None
    rows = [(H / s - ys[i + 1], H / s - ys[i]) for i in range(len(ys) - 1)]  # pdf y
    cols = [(xs[i], xs[i + 1]) for i in range(len(xs) - 1)]

    cells, slot = {}, 1
    for (ry0, ry1) in rows:
        for (cx0, cx1) in cols:
            cells[slot] = (cx0, ry0, cx1, ry1)
            slot += 1
    return cells


def uniform_grid(cells, page_w=612.0, page_h=792.0):
    """A clean, evenly spaced grid the same shape as `cells`, centred on the page.
    Used as the destination so every strain type lands on identical rows."""
    xs = _cluster([(c[0] + c[2]) / 2 for c in cells.values()])
    ys = sorted(_cluster([(c[1] + c[3]) / 2 for c in cells.values()]), reverse=True)
    ncol, nrow = len(xs), len(ys)
    w = _median([c[2] - c[0] for c in cells.values()])
    h = _median([c[3] - c[1] for c in cells.values()])
    x0 = (page_w - ncol * w) / 2.0
    ytop = page_h - (page_h - nrow * h) / 2.0
    out, slot = {}, 1
    for r in range(nrow):
        for c in range(ncol):
            out[slot] = (x0 + c * w, ytop - (r + 1) * h, x0 + (c + 1) * w, ytop - r * h)
            slot += 1
    return out


def tag_cells(src):
    """slot -> (x0, y0, x1, y1) tag cell. Prefers the true border-frame boxes and
    falls back to the field grid for templates without a coloured frame."""
    ac = art_cells(src)
    if ac:
        return ac
    fc = _field_centres(src)
    if not fc:
        return {}
    col_c = _cluster([c[0] for c in fc.values()])
    row_c = sorted(_cluster([c[1] for c in fc.values()]), reverse=True)
    w = _median([col_c[i + 1] - col_c[i] for i in range(len(col_c) - 1)]) \
        if len(col_c) > 1 else float(PdfReader(src).pages[0].mediabox[2])
    h = _median([row_c[i] - row_c[i + 1] for i in range(len(row_c) - 1)]) \
        if len(row_c) > 1 else float(PdfReader(src).pages[0].mediabox[3])
    return {s: (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            for s, (cx, cy) in fc.items()}


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
    pw = float(PdfReader(templates[ref]).pages[0].mediabox[2])
    ph = float(PdfReader(templates[ref]).pages[0].mediabox[3])
    dest = uniform_grid(cells[ref], pw, ph)

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
                sw = src_rect[2] - src_rect[0]
                sh = src_rect[3] - src_rect[1]
                dw = dst_rect[2] - dst_rect[0]
                dh = dst_rect[3] - dst_rect[1]
                if sw <= 0 or sh <= 0:
                    continue
                sx, sy = dw / sw, dh / sh          # normalise differing tag sizes
                layer = _clipped_page(filled[t], src_rect)
                tx = dst_rect[0] - sx * src_rect[0]
                ty = dst_rect[1] - sy * src_rect[1]
                out_page.merge_transformed_page(
                    layer, Transformation().scale(sx, sy).translate(tx, ty))
        writer.add_page(out_page)

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.getvalue()
