#!/usr/bin/env python3
"""Retune the BRAND and STRAIN field boxes on the preroll templates.

The fill engine sizes text to fit its field box, bounded by width AND height, so
the box geometry IS the type scale:

  * BRAND was the smaller line on every tag. On the single templates it is
    width-limited (its box is narrower than the strain box), on the split
    templates it is height-limited (a 16pt-tall box). Both are widened/raised.
  * STRAIN had a very tall box, so short names ("GDP", "SLAPZ") ballooned while
    long ones stayed small. Capping the box height caps the maximum size, which
    evens the sheet out without shrinking the long names.

Artwork is untouched — only the field rectangles move.

Usage:  python tune_text.py            # retunes every known template in place
"""
import re
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, FloatObject, NameObject

SINGLE = ["Sativa_Prerolls.pdf", "Hybrid_Prerolls.pdf", "Indica_Prerolls.pdf",
          "Sativa_Prerolls_4in.pdf", "Hybrid_Prerolls_4in.pdf", "Indica_Prerolls_4in.pdf"]
SPLIT = ["sativa_split_template.pdf", "hybrid_split_template.pdf", "indica_split_template.pdf",
         "Sativa_Split_4in.pdf", "Hybrid_Split_4in.pdf", "Indica_Split_4in.pdf"]

BRAND_MIN_H = {"single": 42.0, "split": 28.0}   # taller box -> bigger brand text
STRAIN_MAX_H = {"single": 40.0, "split": 34.0}  # shorter box -> size ceiling
GAP = 3.0                                        # keep lines from touching


def _slots(page):
    """slot -> {KEY: annot} for the page's widgets."""
    out = {}
    for a in page.get("/Annots", []) or []:
        o = a.get_object()
        v = o.get("/V")
        if v is None and o.get("/Parent"):
            v = o["/Parent"].get_object().get("/V")
        if o.get("/Rect") and isinstance(v, str):
            m = re.match(r"(BRAND|STRAIN|THC|PRICE)_+\s*(\d+)", v.strip())
            if m:
                out.setdefault(int(m.group(2)), {})[m.group(1)] = o
    return out


def _rect(o):
    return [float(x) for x in o["/Rect"]]


def _set(o, r):
    o[NameObject("/Rect")] = ArrayObject([FloatObject(v) for v in r])


def tune(src, kind):
    reader = PdfReader(src)
    writer = PdfWriter()
    writer.append(reader)
    page = writer.pages[0]
    slots = _slots(page)
    changed = 0
    for n, d in slots.items():
        if "BRAND" not in d or "STRAIN" not in d:
            continue
        b = _rect(d["BRAND"])
        s = _rect(d["STRAIN"])
        top = max(b[3], s[3])                       # top of the text block
        base = s[1]                                 # bottom of the strain box
        if "THC" in d:
            base = max(base, _rect(d["THC"])[3] + GAP)

        # BRAND: match the strain box's width (it was narrower) and give it height
        bh = BRAND_MIN_H[kind]          # exact, so re-running is idempotent
        b_new = [s[0], top - bh, s[2], top]

        # STRAIN: cap the height, sitting just under the brand line
        avail_top = b_new[1] - GAP
        sh = min(STRAIN_MAX_H[kind], max(10.0, avail_top - base))
        mid = (avail_top + base) / 2.0
        s_new = [s[0], mid - sh / 2, s[2], mid + sh / 2]
        if s_new[3] > avail_top:
            s_new = [s[0], avail_top - sh, s[2], avail_top]

        _set(d["BRAND"], b_new)
        _set(d["STRAIN"], s_new)
        changed += 1

    with open(src, "wb") as f:
        writer.write(f)
    print(f"tuned {src}: {changed} slots  "
          f"(brand h={bh:.0f}, strain h={sh:.0f})")


if __name__ == "__main__":
    targets = sys.argv[1:] or (SINGLE + SPLIT)
    for t in targets:
        tune(t, "split" if t in SPLIT else "single")
