"""Take the Smilez wordmark out of the tag templates, permanently.

Build-time tool: run from the repo root, once, after re-exporting any template.

    python tools/strip_logo.py            # rewrite all nine templates in place
    python tools/strip_logo.py --check    # report only, change nothing

Why the art and not a mask at fill time: on the hook templates the wordmark sits
in the same band as the strain (logo y 671.0-695.5, strain box bottom 690.8, and
large strain text inks down to about 698.6), so a rectangle big enough to hide it
always ate the bottom of the strain, and one small enough to spare the strain
always left a sliver of logo showing. No rectangle does both. Removing it from
the template removes the choice.

The two template families carry it differently:

  hook      24 /Btn image-button fields named Image2_af_image, one per slot.
            Widgets paint over the page content, which is why covering them from
            the content stream does nothing. They are deleted outright.

  prerolls  drawn straight into the page content as coloured text, clear of
            every field, so a white patch over the box measured in
            sale_badges.LOGO_OFFSETS is enough.
"""

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, NameObject

import sale_badges as sb

TEMPLATES = [f"{t}_{k}.pdf" for k in ("Hook", "Prerolls", "Prerolls_4in")
             for t in ("Sativa", "Hybrid", "Indica")]

LOGO_FIELD = "Image2_af_image"     # the hook templates' image-button wordmark
# Slop around a measured preroll box. The hybrid wordmark sits a few pt off
# where LOGO_OFFSETS puts it and the tail of the 'z' escaped a tight patch, so
# this is wider than the measurement error — the patch only ever covers blank
# art between the THC and price boxes, well inside the coloured frame.
MARGIN = 8.0
DPI = 300
MARKER = b"% smilez-wordmark painted out by tools/strip_logo.py"


def _is_logo_button(annot):
    o = annot.get_object()
    if str(o.get("/Subtype")) != "/Widget":
        return False
    parent = o.get("/Parent")
    ft = o.get("/FT") or (parent.get_object().get("/FT") if parent else None)
    name = o.get("/T") or (parent.get_object().get("/T") if parent else None)
    return str(ft) == "/Btn" and str(name) == LOGO_FIELD


def logo_boxes(tpl):
    """White patches to add to the page content."""
    off = sb.LOGO_OFFSETS.get(os.path.basename(tpl))
    if off:                                    # prerolls: the measured box
        return [(g["THC"][0] + off[0] - MARGIN, g["THC"][1] + off[1] - MARGIN,
                 g["THC"][0] + off[2] + MARGIN, g["THC"][1] + off[3] + MARGIN)
                for g in sb.slot_geometry(tpl).values()]
    # Hook: the whole strip from the THC floor to just past where the strain
    # sits, full tag width. Deleting the wordmark button uncovers a "The science
    # of happiness." tagline printed into the background art beneath it, which
    # runs wider than the pocket, so the patch spans the tag. Everything in this
    # strip — strain, THC, price — is a field painted over the art when the form
    # is flattened, so the only thing a patch this size erases is the branding.
    return [(g["BRAND"][0], g["THC"][1], g["BRAND"][2], g["STRAIN"][1] + 8)
            for g in sb.slot_geometry(tpl).values()]


def count(tpl):
    """(logo buttons, wordmark-coloured pixels in the pocket strip)."""
    reader = PdfReader(tpl)
    page = reader.pages[0]
    buttons = sum(1 for a in (page.get("/Annots") or []) if _is_logo_button(a))
    with tempfile.TemporaryDirectory() as td:
        stem = os.path.join(td, "r")
        subprocess.run(["pdftoppm", "-png", "-r", str(DPI), tpl, stem],
                       check=True, capture_output=True)
        png = next(f for f in sorted(os.listdir(td)) if f.endswith(".png"))
        a = np.array(Image.open(os.path.join(td, png)).convert("RGB")).astype(int)
    s = DPI / 72.0
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    ink = (g > 140) & (g < 215) & (r < g - 40) & (b < 250)
    px = 0
    for gm in sb.slot_geometry(tpl).values():
        thc, price, strain = gm["THC"], gm["PRICE"], gm["STRAIN"]
        r0, r1 = int((792 - (strain[1] + 4)) * s), int((792 - thc[1]) * s)
        px += int(ink[r0:r1, int(thc[2] * s):int(price[0] * s)].sum())
    return buttons, px


def strip(tpl):
    reader = PdfReader(tpl)
    writer = PdfWriter(clone_from=reader)
    page = writer.pages[0]

    annots = page.get("/Annots")
    dropped = 0
    if annots:
        keep = [a for a in annots if not _is_logo_button(a)]
        dropped = len(annots) - len(keep)
        if dropped:
            page[NameObject("/Annots")] = ArrayObject(keep)
            # Keep the AcroForm in step, or readers re-add the field.
            form = writer._root_object.get("/AcroForm")
            form = form.get_object() if form is not None else None
            if form and "/Fields" in form:
                fields = [f for f in form["/Fields"] if not _is_logo_button(f)]
                form[NameObject("/Fields")] = ArrayObject(fields)

    boxes = logo_boxes(tpl)
    contents = page[NameObject("/Contents")]
    parts = ([o.get_object().get_data() for o in contents]
             if isinstance(contents, ArrayObject) else [contents.get_data()])
    painted = 0
    if boxes and not any(MARKER in p for p in parts):
        ops = [MARKER, b"q", b"1 1 1 rg"]
        for x0, y0, x1, y1 in boxes:
            ops.append(f"{x0:.2f} {y0:.2f} {x1-x0:.2f} {y1-y0:.2f} re f".encode())
        ops.append(b"Q")
        stream = DecodedStreamObject()
        stream.set_data(b"\n".join(parts) + b"\n" + b"\n".join(ops) + b"\n")
        page[NameObject("/Contents")] = writer._add_object(stream)
        painted = len(boxes)

    if dropped or painted:
        with open(tpl, "wb") as f:
            writer.write(f)
    return dropped, painted


if __name__ == "__main__":
    check = "--check" in sys.argv
    bad = 0
    for tpl in TEMPLATES:
        if not os.path.exists(tpl):
            print(f"{tpl:26s} MISSING")
            bad += 1
            continue
        if check:
            btn, px = count(tpl)
            print(f"{tpl:26s} {btn:3d} logo buttons   {px:6d} wordmark px")
            continue
        before = count(tpl)
        dropped, painted = strip(tpl)
        after = count(tpl)
        print(f"{tpl:26s} removed {dropped:3d} buttons, painted {painted:3d} boxes   "
              f"buttons {before[0]}->{after[0]}   px {before[1]}->{after[1]}")
    sys.exit(1 if bad else 0)
