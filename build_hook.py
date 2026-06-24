#!/usr/bin/env python3
"""Make 3 colour-coded Small Hook Tag templates from master_template.pdf by
recolouring the gradient stripe (baked into the page background image) to each
strain type's exact preroll colour. Cut guides + Smilez logo are left untouched.
The 24 form fields are unchanged, so the existing engine fills them as-is."""
import io, sys
import numpy as np
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import Color
import build_split as bs            # reuse sample_border_color

MASTER = "master_template.pdf"
OUT = {"sativa": "Sativa_Hook.pdf", "hybrid": "Hybrid_Hook.pdf", "indica": "Indica_Hook.pdf"}
SRC_COLOR = {"sativa": "Sativa_Prerolls.pdf", "hybrid": "Hybrid_Prerolls.pdf",
             "indica": "Indica_Prerolls.pdf"}

def stripe_rects(src):
    """Detect stripe rectangles (PDF points) as the 8 row-bands x 3 column-bands
    of saturated pixels in the background image — robust full coverage."""
    reader = PdfReader(src)
    im0 = reader.pages[0]["/Resources"]["/XObject"]["/Im0"].get_object()
    img = Image.open(io.BytesIO(im0.get_data())).convert("RGB")
    a = np.asarray(img).astype(float)
    H, W = a.shape[:2]
    pw = float(reader.pages[0].mediabox[2]); ph = float(reader.pages[0].mediabox[3])
    sx, sy = pw / W, ph / H
    mx = a.max(2); mn = a.min(2); sat = (mx - mn) / np.maximum(mx, 1)
    mask = (sat > 0.30) & (mx > 60)

    def segments(hits, min_len):
        out, s = [], None
        for i, v in enumerate(hits):
            if v and s is None: s = i
            elif not v and s is not None:
                if i - s >= min_len: out.append((s, i - 1))
                s = None
        if s is not None and len(hits) - s >= min_len: out.append((s, len(hits) - 1))
        return out

    def strongest(segs, axis_sum, n):                # keep the n segments with most stripe pixels
        scored = sorted(segs, key=lambda ab: -axis_sum[ab[0]:ab[1] + 1].sum())
        return sorted(scored[:n])

    rowsum = mask.sum(1); colsum = mask.sum(0)
    bands = strongest(segments(rowsum > 0.04 * W, 1), rowsum, 8)   # 8 stripe rows
    cols  = strongest(segments(colsum > 12, 80), colsum, 3)        # 3 stripe columns
    rects = []
    for ya, yb in bands:
        for xa, xb in cols:
            rects.append((xa * sx, ph - (yb + 1) * sy, xb * sx, ph - ya * sy))
    return rects, pw, ph

def build(strain_type, rects, pw, ph):
    color = bs.sample_border_color(SRC_COLOR[strain_type])
    reader = PdfReader(MASTER)
    writer = PdfWriter(); writer.append(reader)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(pw, ph))
    c.setFillColor(Color(*color)); c.setStrokeColor(Color(*color))
    for x0, y0, x1, y1 in rects:                  # cover gradient with solid colour (+pad)
        c.rect(x0 - 1, y0 - 1.5, (x1 - x0) + 2, (y1 - y0) + 3, fill=1, stroke=0)
    c.save(); buf.seek(0)
    writer.pages[0].merge_page(PdfReader(buf).pages[0])
    with open(OUT[strain_type], "wb") as f:
        writer.write(f)
    print(f"built {OUT[strain_type]}  ({len(rects)} stripes) rgb="
          f"{tuple(round(v,2) for v in color)}")

if __name__ == "__main__":
    rects, pw, ph = stripe_rects(MASTER)
    print(f"detected {len(rects)} stripe rects")
    for t in OUT:
        build(t, rects, pw, ph)
