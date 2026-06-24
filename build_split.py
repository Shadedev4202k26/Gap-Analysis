#!/usr/bin/env python3
"""Build a side-by-side SPLIT template from a Smilez single-strain template.
Keeps the original page (gradient border + Smilez logo background + the
Paralucent-Heavy font in /DR) and replaces the 10 single-strain field sets
with 20 two-column field sets (left/right strain per cell)."""
import sys, re, io, os, tempfile, subprocess
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (DictionaryObject, ArrayObject, NameObject,
    NumberObject, FloatObject, TextStringObject, BooleanObject)
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import Color

def sample_border_color(src):
    """Sample the dominant saturated colour (the gradient border) so the
    divider matches the tag's strain colour exactly. Returns (r,g,b) 0..1."""
    try:
        import numpy as np
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'p')
            subprocess.run(['pdftoppm', '-png', '-r', '80', '-singlefile', src, p],
                           check=True, capture_output=True)
            arr = np.asarray(Image.open(p + '.png').convert('RGB')).astype(float)
        mx = arr.max(2); mn = arr.min(2)
        sat = (mx - mn) / np.maximum(mx, 1)
        mask = (sat > 0.35) & (mx > 60)
        if mask.sum() < 50:
            return (0.45, 0.45, 0.45)
        return tuple((arr[mask].mean(0) / 255.0).tolist())
    except Exception:
        return (0.45, 0.45, 0.45)

def _median(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n//2] if n % 2 else (xs[n//2-1] + xs[n//2]) / 2.0

def _field_grid(reader):
    """From the original fields: per-column x-bands, per-row centres (top->bottom)
    and the typical cell height."""
    fields = reader.get_fields() or {}
    ph = {fn: (fld.get('/V','') or '').strip() for fn,fld in fields.items()
          if isinstance(fld.get('/V',''), str)}
    page = reader.pages[0]
    rects = {}
    for a in page.get('/Annots', []):
        o = a.get_object(); nm = o.get('/T')
        if nm is None and o.get('/Parent'): nm = o['/Parent'].get_object().get('/T')
        if nm and o.get('/Rect'): rects[str(nm)] = [float(x) for x in o['/Rect']]
    slots = {}
    for fn, v in ph.items():
        m = re.match(r'(BRAND|STRAIN|THC|PRICE)_+\s*(\d+)', v)
        if m and fn in rects:
            slots.setdefault(int(m.group(2)), []).append(rects[fn])
    raw = [(min(r[0] for r in rs), min(r[1] for r in rs),
            max(r[2] for r in rs), max(r[3] for r in rs)) for rs in slots.values()]
    mid = float(page.mediabox[2]) / 2
    left  = [c for c in raw if (c[0]+c[2])/2 <  mid]
    right = [c for c in raw if (c[0]+c[2])/2 >= mid]
    col_x = {0: (_median([c[0] for c in left]),  _median([c[2] for c in left])),
             1: (_median([c[0] for c in right]), _median([c[2] for c in right]))}
    order = sorted(raw, key=lambda c: -(c[1]+c[3])/2)
    rows, cur = [], [order[0]]
    for c in order[1:]:
        if ((cur[-1][1]+cur[-1][3])/2) - ((c[1]+c[3])/2) > 60:
            rows.append(cur); cur = [c]
        else:
            cur.append(c)
    rows.append(cur)
    centres = [_median([(m[1]+m[3])/2 for m in r]) for r in rows]
    h = _median([m[3]-m[1] for m in raw])
    return col_x, centres, h

def detect_interior_centres(src, dpi=150):
    """Find each tag's white interior centre straight from the printed art, so
    the text grid can match the BORDER pitch (which differs slightly from the
    original field pitch and is the real cause of the down-page drift)."""
    try:
        import numpy as np
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'p')
            subprocess.run(['pdftoppm', '-png', '-r', str(dpi), '-singlefile', src, p],
                           check=True, capture_output=True)
            im = np.asarray(Image.open(p + '.png').convert('RGB')).astype(float)
        H = im.shape[0]; ptpx = 72.0 / dpi
        x0 = int(58/72*dpi); x1 = int(140/72*dpi)   # left-edge strip: skips logo+centre text
        strip = im[:, x0:x1, :]
        mx = strip.max(2); mn = strip.min(2); sat = (mx - mn) / np.maximum(mx, 1)
        colored = ((sat > 0.16) & (mx > 40)).mean(1)
        interior = colored < 0.25
        runs, s = [], None
        for y in range(H):
            if interior[y] and s is None: s = y
            elif not interior[y] and s is not None: runs.append((s, y-1)); s = None
        if s is not None: runs.append((s, H-1))
        cen = [((H-1-a)*ptpx + (H-1-b)*ptpx)/2 for a, b in runs if (b-a)*ptpx > 80]
        cen.sort(reverse=True)
        return cen if len(cen) == 5 else None
    except Exception:
        return None

def original_cells(reader, src=None):
    """2-col x 5-row grid (reading order). Rows are placed on the BORDER pitch
    measured from the art (per template), shifted to best-fit the original field
    positions — so text sits consistently in every tag, top to bottom."""
    col_x, fcentres, h = _field_grid(reader)
    icentres = detect_interior_centres(src) if src else None
    if icentres and len(icentres) == len(fcentres) == 5:
        off = _median([f - i for f, i in zip(fcentres, icentres)])
        centres = [i + off for i in icentres]          # art pitch, original phase
    else:
        centres = fcentres                              # fallback: field grid
    cells = []
    for c in centres:                                   # top -> bottom
        cells.append((col_x[0][0], c - h/2, col_x[0][1], c + h/2))
        cells.append((col_x[1][0], c - h/2, col_x[1][1], c + h/2))
    return cells

def mk_field(writer, page_ref, name, placeholder, rect, q):
    d = DictionaryObject({
        NameObject('/FT'): NameObject('/Tx'),
        NameObject('/Subtype'): NameObject('/Widget'),
        NameObject('/T'): TextStringObject(name),
        NameObject('/V'): TextStringObject(placeholder),
        NameObject('/DA'): TextStringObject('/Paralucent-Heavy 0 Tf 0 g'),
        NameObject('/Q'): NumberObject(q),
        NameObject('/F'): NumberObject(4),
        NameObject('/Rect'): ArrayObject([FloatObject(round(v,1)) for v in rect]),
        NameObject('/P'): page_ref,
    })
    return writer._add_object(d)

def build(src, out, color=None):
    reader = PdfReader(src)
    cells = original_cells(reader, src)
    writer = PdfWriter(); writer.append(reader)
    page = writer.pages[0]; page_ref = page.indirect_reference
    acro = writer._root_object['/AcroForm'].get_object()

    new_annots = ArrayObject()
    slot = 0
    LOGO_HALF = 38      # half-width of centred Smilez logo to avoid (pt)
    for (x0, y0, x1, y1) in cells:
        xm = (x0 + x1) / 2.0
        cols = [(x0, xm), (xm, x1)]          # left, right
        for ci, (cx0, cx1) in enumerate(cols):
            slot += 1
            cw = cx1 - cx0
            pad = 4
            # vertical bands within the cell
            brand_r  = (cx0+pad, y1-17,  cx1-pad, y1-1)
            strain_r = (cx0+1,   y0+44,  cx1-1,   y1-20)
            # THC/PRICE pinned to the OUTER side, clear of the centred logo
            if ci == 0:   # left strain -> text hugs left edge
                tx0, tx1, q = cx0+pad, xm-LOGO_HALF, 0
            else:         # right strain -> text hugs right edge
                tx0, tx1, q = xm+LOGO_HALF, cx1-pad, 2
            thc_r   = (tx0, y0+22, tx1, y0+40)
            price_r = (tx0, y0+1,  tx1, y0+21)
            for key, rect, qq in [('BRAND', brand_r, 1), ('STRAIN', strain_r, 1),
                                  ('THC', thc_r, q), ('PRICE', price_r, q)]:
                ref = mk_field(writer, page_ref, f'f{slot}_{key.lower()}',
                               f'{key}_{slot}', rect, qq)
                new_annots.append(ref)

    page[NameObject('/Annots')] = new_annots
    acro[NameObject('/Fields')] = new_annots
    acro[NameObject('/NeedAppearances')] = BooleanObject(True)

    # --- strain-coloured divider down each tag's centre, stopping above logo ---
    if color is None:
        color = sample_border_color(src)
    pw = float(page.mediabox[2]); ph = float(page.mediabox[3])
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(pw, ph))
    c.setStrokeColor(Color(*color)); c.setLineWidth(2.0); c.setLineCap(1)
    for (x0, y0, x1, y1) in cells:
        xm = (x0 + x1) / 2.0
        c.line(xm, y0 + 44, xm, y1 - 3)      # top -> just above the Smilez logo
    c.save(); buf.seek(0)
    page.merge_page(PdfReader(buf).pages[0])

    with open(out, 'wb') as f:
        writer.write(f)
    print(f'built {out}: {slot} slots ({slot//2} split tags) · divider rgb='
          f'{tuple(round(x,2) for x in color)}')

def _slot_fields(reader):
    """{slot: {KEY: rect}} from the original placeholders."""
    fields = reader.get_fields() or {}
    ph = {fn: (fl.get('/V','') or '').strip() for fn,fl in fields.items()
          if isinstance(fl.get('/V',''), str)}
    page = reader.pages[0]; rects = {}
    for a in page.get('/Annots', []):
        o = a.get_object(); nm = o.get('/T')
        if nm is None and o.get('/Parent'): nm = o['/Parent'].get_object().get('/T')
        if nm and o.get('/Rect'): rects[str(nm)] = [float(x) for x in o['/Rect']]
    slots = {}
    for fn, v in ph.items():
        m = re.match(r'(BRAND|STRAIN|THC|PRICE)_+\s*(\d+)', v)
        if m and fn in rects:
            slots.setdefault(int(m.group(2)), {})[m.group(1)] = rects[fn]
    return slots

def build_single(src, out):
    """Rebuild a single-strain Smilez template: same art (border + Smilez logo +
    font), but every tag's BRAND/STRAIN/THC/PRICE re-placed on the border-pitch
    grid (drift fix) using the template's own layout, with all 10 tags complete
    (repairs missing/duplicated/misnamed source fields)."""
    reader = PdfReader(src)
    pw = float(reader.pages[0].mediabox[2])
    slotf = _slot_fields(reader)
    # canonical within-cell offsets, from clean tags only (all 4 fields, normal width)
    offs = {k: [] for k in ('BRAND', 'STRAIN', 'THC', 'PRICE')}
    dims = {k: [] for k in offs}
    for d in slotf.values():
        if not all(k in d for k in offs):
            continue
        cx0 = min(d[k][0] for k in d); cy0 = min(d[k][1] for k in d)
        cx1 = max(d[k][2] for k in d)
        if cx1 - cx0 > 0.6 * pw:            # skip a merged/duplicate cell
            continue
        for k in offs:
            r = d[k]
            offs[k].append((r[0]-cx0, r[1]-cy0)); dims[k].append((r[2]-r[0], r[3]-r[1]))
    canon = {}
    for k in offs:
        canon[k] = (_median([o[0] for o in offs[k]]), _median([o[1] for o in offs[k]]),
                    _median([d[0] for d in dims[k]]), _median([d[1] for d in dims[k]]))

    cells = original_cells(reader, src)      # 10 cells on the corrected border grid
    writer = PdfWriter(); writer.append(reader)
    page = writer.pages[0]; page_ref = page.indirect_reference
    acro = writer._root_object['/AcroForm'].get_object()
    Q = {'BRAND': 1, 'STRAIN': 1, 'THC': 0, 'PRICE': 2}
    new_annots = ArrayObject()
    for i, (x0, y0, x1, y1) in enumerate(cells, 1):     # reading order, 1..10
        for key in ('BRAND', 'STRAIN', 'THC', 'PRICE'):
            dx0, dy0, w, h = canon[key]
            rect = (x0+dx0, y0+dy0, x0+dx0+w, y0+dy0+h)
            ref = mk_field(writer, page_ref, f'f{i}_{key.lower()}', f'{key}_{i}', rect, Q[key])
            new_annots.append(ref)
    page[NameObject('/Annots')] = new_annots
    acro[NameObject('/Fields')] = new_annots
    acro[NameObject('/NeedAppearances')] = BooleanObject(True)
    with open(out, 'wb') as f:
        writer.write(f)
    print(f'built {out}: single-strain, 10 tags, drift-corrected')

if __name__ == '__main__':
    if len(sys.argv) > 3 and sys.argv[3] == '--single':
        build_single(sys.argv[1], sys.argv[2])
    else:
        build(sys.argv[1], sys.argv[2])
