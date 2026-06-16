# preroll_tags.py
# Builds color-coded preroll hook tags from three template PDFs:
#   Sativa  = red/orange border
#   Hybrid  = blue/green border
#   Indica  = purple border
# Supports a "mixed" mode that places different-colored tags on the same sheet
# (image-composited), and a "separate" mode that simply stacks colored pages.

import os
import re
import subprocess
import tempfile
from pypdf import PdfReader, PdfWriter


# ── Strain-type routing ───────────────────────────────────────────────────────
def classify_type(strain_value):
    """Map a CSV 'Strain' value to one of: sativa, hybrid, indica.
    'No Strain' and anything unrecognized default to hybrid (blue/green)."""
    s = (strain_value or "").strip().lower()
    if "sativa" in s:
        return "sativa"
    if "indica" in s:
        return "indica"
    # hybrid, "no strain", blends, unknowns
    return "hybrid"


# ── FDF helpers ───────────────────────────────────────────────────────────────
def _esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_slot_map(template_path):
    """slot number -> {brand,strain,thc,price: field_name} from placeholder values."""
    reader = PdfReader(template_path)
    fields = reader.get_fields() or {}
    sm = {}
    for fname, fld in fields.items():
        v = fld.get("/V", "")
        if not isinstance(v, str):
            continue
        vs = v.strip()
        for prefix, key in [("BRAND_", "brand"), ("STRAIN_", "strain"),
                            ("THC_", "thc"), ("PRICE_", "price")]:
            if vs.startswith(prefix):
                try:
                    sm.setdefault(int(vs[len(prefix):].strip()), {})[key] = fname
                except ValueError:
                    pass
    return sm


def slots_per_page(template_path):
    sm = build_slot_map(template_path)
    return max(sm.keys()) if sm else 0


def _make_fdf(slot_map, page_rows, max_slots):
    entries = []
    for slot in range(1, max_slots + 1):
        d = page_rows[slot - 1] if slot - 1 < len(page_rows) else None
        sf = slot_map.get(slot, {})
        for key in ("brand", "strain", "thc", "price"):
            fn = sf.get(key)
            if fn:
                val = (d.get(key, "") if d else "")
                entries.append(f"<</T ({_esc(fn)})/V ({_esc(val)})>>")
    return ("%FDF-1.2\n1 0 obj\n<< /FDF << /Fields [\n"
            + "\n".join(entries)
            + "\n] >> >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n")


def _fill_template(template_path, page_rows, tmpdir, tag):
    """Fill one page of a template with page_rows, return output pdf path."""
    sm = build_slot_map(template_path)
    max_slots = max(sm.keys()) if sm else 0
    fdf_path = os.path.join(tmpdir, f"{tag}.fdf")
    out_path = os.path.join(tmpdir, f"{tag}.pdf")
    with open(fdf_path, "w", encoding="latin-1") as f:
        f.write(_make_fdf(sm, page_rows, max_slots))
    r = subprocess.run(
        ["pdftk", template_path, "fill_form", fdf_path, "output", out_path],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"pdftk fill failed: {r.stderr.strip()}")
    return out_path


# ── SEPARATE mode: stack colored pages in one PDF ─────────────────────────────
def build_separate(templates, grouped_rows, tmpdir):
    """templates: {type: path}. grouped_rows: {type: [rows...]}.
    Returns merged PDF bytes with each color's pages in sequence."""
    writer = PdfWriter()
    order = ["sativa", "hybrid", "indica"]
    for t in order:
        rows = grouped_rows.get(t, [])
        if not rows:
            continue
        spp = slots_per_page(templates[t])
        pages = [rows[i:i + spp] for i in range(0, len(rows), spp)]
        for pi, prows in enumerate(pages):
            out = _fill_template(templates[t], prows, tmpdir, f"{t}_{pi}")
            writer.append(out)
    import io
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.getvalue()


# ── MIXED mode: composite different-colored cells onto shared sheets ──────────
# Grid geometry for the preroll templates (612x792 pt, 2 cols x 5 rows).
# y values are PDF coordinates (from bottom); each cell ~144pt tall.
_DPI = 200
_SCALE = _DPI / 72.0
_PAGE_W_PT, _PAGE_H_PT = 612, 792
# Measured from the rendered templates: full bordered cells.
_ROW_TOPS_FROM_TOP = [24, 168, 313, 457, 601]   # top edge of each row (pt from top)
_ROW_H_PT = 146                                  # full cell height incl. borders
_COLS_X = [(45, 290), (320, 565)]                # (x0, x1) for col0, col1
_SLOTS_PER_SHEET = 10                            # 2 x 5


def _slot_to_grid(slot):
    """slot 1..10 -> (col, row)."""
    col = 0 if slot % 2 == 1 else 1
    row = (slot - 1) // 2
    return col, row


def _render_full_color(template_path, tmpdir, tag):
    """Fill a template with ALL slots populated by a single sample row so the
    border + Smilez logo render fully, then rasterize. Returns PIL image.
    (We only use this image's BORDER; text cells are overwritten per product.)"""
    # Actually we render a blank-filled version (no text) to get clean borders.
    sm = build_slot_map(template_path)
    max_slots = max(sm.keys()) if sm else 0
    blank_rows = [{} for _ in range(max_slots)]
    out = _fill_template(template_path, blank_rows, tmpdir, f"blank_{tag}")
    png = os.path.join(tmpdir, f"blank_{tag}.png")
    subprocess.run(["pdftoppm", "-png", "-r", str(_DPI), "-singlefile", out, png[:-4]],
                   check=True, capture_output=True)
    from PIL import Image
    return Image.open(png)


def _render_filled_color(template_path, page_rows, tmpdir, tag):
    """Fill a template with real product rows and rasterize to a PIL image."""
    out = _fill_template(template_path, page_rows, tmpdir, f"fill_{tag}")
    png = os.path.join(tmpdir, f"fill_{tag}.png")
    subprocess.run(["pdftoppm", "-png", "-r", str(_DPI), "-singlefile", out, png[:-4]],
                   check=True, capture_output=True)
    from PIL import Image
    return Image.open(png)


def _cell_box_px(col, row):
    """Pixel bounding box (left, top, right, bottom) for a grid cell,
    capturing the full colored border."""
    x0, x1 = _COLS_X[col]
    y_top = _ROW_TOPS_FROM_TOP[row]
    px0 = int(round(x0 * _SCALE))
    py0 = int(round(y_top * _SCALE))
    px1 = int(round(x1 * _SCALE))
    py1 = int(round((y_top + _ROW_H_PT) * _SCALE))
    return px0, py0, px1, py1


def build_mixed(templates, ordered_rows, tmpdir):
    """ordered_rows: list of dicts each with a 'type' key plus brand/strain/thc/price.
    Places up to 10 tags per physical sheet, each cell drawn from its own color
    template. Returns PDF bytes."""
    from PIL import Image

    # Pre-render each color filled with its OWN matching products would require
    # per-cell alignment; instead we render each color once PER SHEET with that
    # sheet's products placed only in the cells that match the color, then crop
    # the matching cells. Simpler + crisp: render each color sheet fully with the
    # sheet's data mapped to slot positions, then take each cell from its color.

    sheets = [ordered_rows[i:i + _SLOTS_PER_SHEET]
              for i in range(0, len(ordered_rows), _SLOTS_PER_SHEET)]
    page_images = []

    for sheet_rows in sheets:
        # For this sheet, for each color, build a page where every slot is filled
        # with the sheet's product at that position (so the cell we crop has the
        # right text). We then crop each slot's cell from its matching color.
        by_color_rows = {c: [None] * _SLOTS_PER_SHEET for c in templates}
        for idx, prod in enumerate(sheet_rows):
            by_color_rows[prod["type"]][idx] = prod
        # Fill in placeholders (empty) for slots not used by that color
        rendered = {}
        for c, path in templates.items():
            rows_for_c = [r if r else {} for r in by_color_rows[c]]
            # Only render if this color has at least one product on the sheet
            if any(by_color_rows[c]):
                rendered[c] = _render_filled_color(path, rows_for_c, tmpdir,
                                                   f"{c}_{len(page_images)}")

        # Build the composite sheet on a white canvas
        canvas = Image.new("RGB", (int(_PAGE_W_PT * _SCALE), int(_PAGE_H_PT * _SCALE)), "white")
        for idx, prod in enumerate(sheet_rows):
            slot = idx + 1
            col, row = _slot_to_grid(slot)
            color = prod["type"]
            src = rendered.get(color)
            if src is None:
                continue
            box = _cell_box_px(col, row)
            cell = src.crop(box)
            canvas.paste(cell, (box[0], box[1]))
        page_images.append(canvas)

    # Save all canvases into a single PDF
    import io
    buf = io.BytesIO()
    if page_images:
        page_images[0].save(buf, format="PDF", save_all=True,
                            append_images=page_images[1:], resolution=_DPI)
    buf.seek(0)
    return buf.getvalue()
