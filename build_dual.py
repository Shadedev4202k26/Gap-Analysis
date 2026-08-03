#!/usr/bin/env python3
"""PROTOTYPE — dual-strain split tag with a FULL colour border per half.

Each half of the tag gets its own complete rectangular border in its strain
type's colour, so one physical tag can carry a sativa and an indica and both
read correctly:

    +===============+  +===============+
    |  BRAND A      |  |  BRAND B      |
    |  STRAIN A     |  |  STRAIN B     |     left frame  = e.g. orange (sativa)
    | THC A  PRICE A|  | THC B  PRICE B|     right frame = e.g. purple (indica)
    +===============+  +===============+

The source template has a single gradient border baked into the page, so the
prototype masks that border ring with white and draws two fresh frames.

Usage:
    python build_dual.py                     # 4" base
    python build_dual.py --size 3.5          # 3.5" base
"""
import io
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, BooleanObject, NameObject
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas as rl_canvas

import build_split as bs
import combine_tags as ct

TYPE_COLOR = {
    "sativa": (0.89, 0.61, 0.30),
    "hybrid": (0.37, 0.76, 0.72),
    "indica": (0.42, 0.40, 0.66),
}
BORDER_W = 5.0        # thickness of each half's colour frame (pt)
GAP = 2.5             # white gap between the two halves (tight)
INSET = 1.5           # pull the frames just inside the tag cell
MASK = 12.0           # how far in to paint out the original border ring
STRAIN_MAX_H = 30.0   # strain box height = the size ceiling (matches "LEELA HERB")


def _tags_from_cells(cells):
    """Fold half-cells back into whole tags when the source is a split template."""
    order = sorted(cells)
    rows = {}
    for k in order:
        rows.setdefault(round(cells[k][1], 1), []).append(cells[k])
    xs = sorted({round(cells[k][0], 1) for k in order})
    if len(xs) < 4:                                   # already whole tags
        return [cells[k] for k in order]
    tags = []
    for y in sorted(rows, reverse=True):
        cs = sorted(rows[y], key=lambda c: c[0])
        for i in range(0, len(cs) - 1, 2):
            a, b = cs[i], cs[i + 1]
            tags.append((a[0], a[1], b[2], b[3]))
    return tags


def build(src, out, pairs=None, quiet=False):
    reader = PdfReader(src)
    cells = ct.art_cells(src) or {}
    if not cells:
        raise SystemExit(f"{src}: could not detect tag cells")
    tags = _tags_from_cells(cells)

    writer = PdfWriter()
    writer.append(reader)
    page = writer.pages[0]
    page_ref = page.indirect_reference
    acro = writer._root_object["/AcroForm"].get_object()

    # ── fields: two independent strains per tag ──────────────────────────────
    annots = ArrayObject()
    slot = 0
    for (x0, y0, x1, y1) in tags:
        xm = (x0 + x1) / 2.0
        for hx0, hx1 in [(x0, xm - GAP / 2), (xm + GAP / 2, x1)]:
            slot += 1
            ix0 = hx0 + BORDER_W + 4          # inside this half's own frame
            ix1 = hx1 - BORDER_W - 4
            iy0 = y0 + BORDER_W + 3
            iy1 = y1 - BORDER_W - 3
            hw = ix1 - ix0
            brand_r = (ix0, iy1 - 24, ix1, iy1)          # taller box = bigger brand text
            # Cap the strain box height so short names (SLAPZ) can't balloon —
            # the autosizer fits the box, so a shorter box IS the size limit.
            s_lo, s_hi = iy0 + 23, iy1 - 27
            s_mid = (s_lo + s_hi) / 2.0
            strain_r = (ix0, s_mid - STRAIN_MAX_H / 2, ix1, s_mid + STRAIN_MAX_H / 2)
            thc_r = (ix0, iy0 + 1, ix0 + hw * 0.45, iy0 + 20)
            price_r = (ix1 - hw * 0.45, iy0 + 1, ix1, iy0 + 20)
            for key, rect, q in [("BRAND", brand_r, 1), ("STRAIN", strain_r, 1),
                                 ("THC", thc_r, 0), ("PRICE", price_r, 2)]:
                annots.append(bs.mk_field(writer, page_ref, f"d{slot}_{key.lower()}",
                                          f"{key}_{slot}", rect, q))

    page[NameObject("/Annots")] = annots
    acro[NameObject("/Fields")] = annots
    acro[NameObject("/NeedAppearances")] = BooleanObject(True)

    if pairs is None:                                  # demo colour pairings
        combos = [("sativa", "indica"), ("hybrid", "sativa"), ("indica", "hybrid"),
                  ("sativa", "hybrid"), ("indica", "sativa")]
        pairs = [combos[i % len(combos)] for i in range(len(tags))]

    # ── art: mask the original border, draw one frame per half ───────────────
    pw = float(page.mediabox[2])
    ph = float(page.mediabox[3])
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(pw, ph))
    for (x0, y0, x1, y1), pair in zip(tags, pairs):
        w, h = x1 - x0, y1 - y0
        # paint out the baked-in gradient border ring (leave the interior alone)
        c.setFillColorRGB(1, 1, 1)
        c.rect(x0 - 1, y1 - MASK, w + 2, MASK + 1, fill=1, stroke=0)     # top
        c.rect(x0 - 1, y0 - 1, w + 2, MASK + 1, fill=1, stroke=0)        # bottom
        c.rect(x0 - 1, y0 - 1, MASK + 1, h + 2, fill=1, stroke=0)        # left
        c.rect(x1 - MASK, y0 - 1, MASK + 1, h + 2, fill=1, stroke=0)     # right
        # white channel between the halves so the two frames read separately
        xm = (x0 + x1) / 2.0
        c.rect(xm - GAP / 2, y0 - 1, GAP, h + 2, fill=1, stroke=0)
        # remove the centred Smilez logo — a dual tag has no single owner, and
        # the logo sits exactly where the two halves now meet
        c.rect(x0 + w * 0.34, y0 + 8, w * 0.32, 26, fill=1, stroke=0)
        if not pair:                       # unused tag on the last sheet
            continue
        lt, rt = pair
        # a clean full frame for each half, in its own strain colour
        c.setLineJoin(0)
        for hx0, hx1, t in [(x0 + INSET, xm - GAP / 2, lt),
                            (xm + GAP / 2, x1 - INSET, rt)]:
            c.setStrokeColor(Color(*TYPE_COLOR[t]))
            c.setLineWidth(BORDER_W)
            o = BORDER_W / 2.0
            c.rect(hx0 + o, y0 + INSET + o,
                   (hx1 - hx0) - BORDER_W, h - 2 * INSET - BORDER_W,
                   fill=0, stroke=1)
    c.save()
    buf.seek(0)
    page.merge_page(PdfReader(buf).pages[0])

    with open(out, "wb") as f:
        writer.write(f)
    if not quiet:
        print(f"built {out}: {len(tags)} dual-strain tags ({slot} slots), "
              f"full {BORDER_W}pt colour frame per half")
        for i, p in enumerate(pairs, 1):
            if p:
                print(f"   tag {i}: left={p[0]:7s} right={p[1]}")


if __name__ == "__main__":
    size = "4"
    if "--size" in sys.argv:
        size = sys.argv[sys.argv.index("--size") + 1]
    if size.startswith("3"):
        build("Sativa_Prerolls.pdf", "Dual_Split_35in_PROTOTYPE.pdf")
    else:
        build("Sativa_Prerolls_4in.pdf", "Dual_Split_4in_PROTOTYPE.pdf")


# ── Sheet builder used by the app ────────────────────────────────────────────
BASE_TEMPLATE = {"3.5": "Sativa_Prerolls.pdf", "4": "Sativa_Prerolls_4in.pdf"}


def build_sheet(rows, tmpdir, size="4"):
    """Build a finished dual-strain preroll PDF from a flat list of rows.

    Rows are consumed two at a time — left half, right half of one tag — and each
    half keeps its own strain type, so a sativa can share a tag with an indica.
    The colour frames depend on the actual pairing, so the template is generated
    per sheet rather than shipped as a static file.
    """
    import os

    import preroll_tags as pt

    rows = [r for r in rows if r]
    if not rows:
        return b""
    src = BASE_TEMPLATE.get(str(size), BASE_TEMPLATE["4"])
    slots = len(ct.art_cells(src) or {}) * 2          # two strains per tag
    per_page = max(2, slots)

    writer = PdfWriter()
    for pi in range(0, len(rows), per_page):
        chunk = rows[pi:pi + per_page]
        pairs = []
        for i in range(0, per_page, 2):
            if i >= len(chunk):
                pairs.append(None)                    # leave the tag blank
                continue
            lt = chunk[i].get("type", "hybrid")
            rt = chunk[i + 1].get("type", "hybrid") if i + 1 < len(chunk) else lt
            pairs.append((lt, rt))
        tpl = os.path.join(tmpdir, f"dual_tpl_{pi}.pdf")
        build(src, tpl, pairs=pairs, quiet=True)
        slotted = list(chunk) + [None] * (per_page - len(chunk))
        filled = pt._fill_template(tpl, slotted, tmpdir, f"dual{pi}")
        writer.append(PdfReader(filled))

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.getvalue()
