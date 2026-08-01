#!/usr/bin/env python3
"""Build a 4" x 2" preroll template from the 3.5" x 2" Smilez template.

The tag is widened with a horizontal 5-slice ("9-slice") stretch:

    | left border | stretch | LOGO | stretch | right border |
      native        1.3x      native  1.3x     native

so the left/right border ends keep their exact native thickness and the Smilez
logo is copied at native size (never distorted) and centred in the wider tag.
Only the two plain gaps either side of the logo are stretched, and because the
border gradient is continuous, the seams are invisible.

Usage:  python build_wide.py Sativa_Prerolls.pdf Sativa_Prerolls_4in.pdf
"""
import io
import re
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, BooleanObject, DecodedStreamObject,
                           FloatObject, NameObject, NumberObject)

from reportlab.pdfgen import canvas as rl_canvas

import build_split as bs
import combine_tags as ct

TAG_W, TAG_H = 288.0, 144.0          # 4" x 2"
COLS, ROWS = 2, 5
PAGE_W, PAGE_H = 612.0, 792.0
EDGE = 30.0                           # native border slice kept at each end


def _slot1_fields(src):
    r = PdfReader(src)
    out = {}
    for a in r.pages[0].get("/Annots", []) or []:
        o = a.get_object()
        v = o.get("/V")
        if v is None and o.get("/Parent"):
            v = o["/Parent"].get_object().get("/V")
        if o.get("/Rect") and isinstance(v, str):
            m = re.match(r"(BRAND|STRAIN|THC|PRICE)_+\s*(\d+)", v.strip())
            if m and int(m.group(2)) == 1:
                out[m.group(1)] = [float(x) for x in o["/Rect"]]
    return out


def _logo_extent(rel):
    """Relative x range of the centred Smilez logo: the gap the template itself
    leaves between the THC and PRICE fields. Deterministic for every colour
    (colour detection is unreliable when the border and logo share a hue)."""
    return rel["THC"][2], rel["PRICE"][0]



def _slot_fields(src):
    """{slot: {KEY: rect}} for every field on a built template."""
    r = PdfReader(src)
    out = {}
    for a in r.pages[0].get("/Annots", []) or []:
        o = a.get_object()
        v = o.get("/V")
        if v is None and o.get("/Parent"):
            v = o["/Parent"].get_object().get("/V")
        if o.get("/Rect") and isinstance(v, str):
            m = re.match(r"(BRAND|STRAIN|THC|PRICE)_+\s*(\d+)", v.strip())
            if m:
                out.setdefault(int(m.group(2)), {})[m.group(1)] = [
                    float(x) for x in o["/Rect"]]
    return out


def build_wide(src, out):
    reader = PdfReader(src)
    cells = ct.tag_cells(src)
    cell = cells[1]
    sx0, sy0, sx1, sy1 = cell
    src_w = sx1 - sx0
    src_h = sy1 - sy0

    f1 = _slot1_fields(src)
    rel = {k: [v[0] - sx0, v[1] - sy0, v[2] - sx0, v[3] - sy0] for k, v in f1.items()}
    lg0, lg1 = _logo_extent(rel)
    logo_w = lg1 - lg0

    # destination slice geometry (logo exactly centred in the wider tag)
    dl0 = EDGE
    dlogo0 = TAG_W / 2 - logo_w / 2
    dlogo1 = dlogo0 + logo_w
    dr0 = TAG_W - EDGE
    slices = [                       # (src_rel_x0, src_rel_x1, dst_rel_x0, dst_rel_x1)
        (0.0,       EDGE,     0.0,     dl0),
        (EDGE,      lg0,      dl0,     dlogo0),
        (lg0,       lg1,      dlogo0,  dlogo1),
        (lg1,       src_w - EDGE, dlogo1, dr0),
        (src_w - EDGE, src_w,  dr0,    TAG_W),
    ]

    writer = PdfWriter()
    writer.append(reader)
    page = writer.pages[0]
    page_ref = page.indirect_reference

    # original page art as a reusable Form XObject
    form = DecodedStreamObject()
    form.set_data(page.get_contents().get_data())
    form[NameObject("/Type")] = NameObject("/XObject")
    form[NameObject("/Subtype")] = NameObject("/Form")
    form[NameObject("/BBox")] = ArrayObject(
        [FloatObject(0), FloatObject(0), FloatObject(PAGE_W), FloatObject(PAGE_H)])
    form[NameObject("/Resources")] = page[NameObject("/Resources")]
    form_ref = writer._add_object(form)

    # new page content: paint each tag from the 5 slices
    ops = []
    dest_cells = []
    for r in range(ROWS):
        for c in range(COLS):
            dx = (PAGE_W - COLS * TAG_W) / 2 + c * TAG_W
            dy = PAGE_H - (PAGE_H - ROWS * TAG_H) / 2 - (r + 1) * TAG_H
            dest_cells.append((dx, dy))
            for s0, s1, d0, d1 in slices:
                sw = s1 - s0
                dw = d1 - d0
                if sw <= 0 or dw <= 0:
                    continue
                sc = dw / sw
                sv = TAG_H / src_h            # normalise differing source tag heights
                tx = (dx + d0) - sc * (sx0 + s0)
                ty = dy - sv * sy0
                ops.append(
                    f"q {dx + d0:.3f} {dy:.3f} {dw:.3f} {TAG_H:.3f} re W n "
                    f"{sc:.6f} 0 0 {sv:.6f} {tx:.3f} {ty:.3f} cm /ZFx Do Q")
    content = DecodedStreamObject()
    content.set_data("\n".join(ops).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(content)

    res = page[NameObject("/Resources")].get_object()
    xo = res.get(NameObject("/XObject"))
    if xo is None:
        from pypdf.generic import DictionaryObject
        xo = DictionaryObject()
        res[NameObject("/XObject")] = xo
    else:
        xo = xo.get_object()
    xo[NameObject("/ZFx")] = form_ref

    # ── fields: BRAND/STRAIN widen with the tag, THC/PRICE hug the outer edges
    layout = {}
    b = rel["BRAND"]
    layout["BRAND"] = (b[0], b[1], TAG_W - b[0], b[3])
    s_ = rel["STRAIN"]
    layout["STRAIN"] = (s_[0], s_[1], TAG_W - s_[0], s_[3])
    t = rel["THC"]
    layout["THC"] = (t[0], t[1], t[2], t[3])
    p = rel["PRICE"]
    right_margin = src_w - p[2]
    layout["PRICE"] = (TAG_W - right_margin - (p[2] - p[0]), p[1],
                       TAG_W - right_margin, p[3])

    Q = {"BRAND": 1, "STRAIN": 1, "THC": 0, "PRICE": 2}
    annots = ArrayObject()
    for i, (dx, dy) in enumerate(dest_cells, 1):
        for key in ("BRAND", "STRAIN", "THC", "PRICE"):
            rx0, ry0, rx1, ry1 = layout[key]
            rect = (dx + rx0, dy + ry0, dx + rx1, dy + ry1)
            annots.append(bs.mk_field(writer, page_ref, f"w{i}_{key.lower()}",
                                      f"{key}_{i}", rect, Q[key]))
    page[NameObject("/Annots")] = annots
    acro = writer._root_object["/AcroForm"].get_object()
    acro[NameObject("/Fields")] = annots
    acro[NameObject("/NeedAppearances")] = BooleanObject(True)

    with open(out, "wb") as f:
        writer.write(f)
    print(f"built {out}: {COLS*ROWS} tags of {TAG_W/72:.2f}in x {TAG_H/72:.2f}in "
          f"(logo native {logo_w:.1f}pt, stretch {(dlogo0-dl0)/(lg0-EDGE):.2f}x)")


if __name__ == "__main__":
    build_wide(sys.argv[1], sys.argv[2])


def flatten_art(src, out, dpi=300):
    """Rebuild `src` with its page art baked into ONE background image.

    The sliced construction above draws the source page five times per tag (50
    full-page draws a sheet), which makes rendering ~4x slower — and once such a
    sheet is composited for mixed-type printing the cost multiplies until viewers
    show the file but refuse to print it. The artwork is a raster image to begin
    with, so flattening costs no real quality.

    The original document is kept and only its page CONTENT is swapped, so the
    form fields, their /DA font sizing and the embedded Paralucent-Heavy font in
    /DR all survive untouched.
    """
    import os
    import subprocess
    import tempfile

    from reportlab.lib.utils import ImageReader

    writer = PdfWriter()
    writer.append(PdfReader(src))
    page = writer.pages[0]
    pw = float(page.mediabox[2])
    ph = float(page.mediabox[3])

    with tempfile.TemporaryDirectory() as td:
        # Rasterise an ANNOTATION-FREE copy. Rendering the template as-is bakes
        # the field placeholders (BRAND_1, STRAIN_1 …) into the artwork, and the
        # real values then print on top of them.
        bare = PdfWriter()
        bare.append(PdfReader(src))
        bare.pages[0][NameObject("/Annots")] = ArrayObject()
        if "/AcroForm" in bare._root_object:
            bare._root_object["/AcroForm"].get_object()[
                NameObject("/Fields")] = ArrayObject()
        bare_path = os.path.join(td, "bare.pdf")
        with open(bare_path, "wb") as bf:
            bare.write(bf)
        stem = os.path.join(td, "art")
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-singlefile",
                        bare_path, stem], check=True, capture_output=True)
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(pw, ph))
        c.drawImage(ImageReader(stem + ".png"), 0, 0, width=pw, height=ph)
        c.save()
    buf.seek(0)

    # Import the flat art page, then hand its content+resources to the real page.
    writer.append(PdfReader(buf))
    art = writer.pages[-1]
    page[NameObject("/Contents")] = art.get(NameObject("/Contents"))
    page[NameObject("/Resources")] = art.get(NameObject("/Resources"))
    writer.remove_page(len(writer.pages) - 1)

    with open(out, "wb") as f:
        writer.write(f)
    n = len(_slot_fields(out))
    print(f"flattened {out}: art baked at {dpi}dpi, {n} slots kept")
