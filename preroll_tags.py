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


def _optimal_size(text, field_w, field_h, ratio=0.52):
    """Compute a font size that fills the field well — bounded by width (so long
    text still fits) and height (so short text grows to fill vertical space).
    ratio calibrates avg glyph advance per font-size unit for this field type."""
    text = text or ""
    n = max(1, len(text))
    usable_w = max(1.0, field_w - 6)
    size_w = usable_w / (n * ratio)
    size_h = field_h * 0.72
    return max(6.0, min(size_w, size_h))

# Calibrated character-width ratios per field type for Paralucent-Heavy:
# brand  — pipes + digits + letters: ~0.46 (narrow avg due to | and numbers)
# strain — all-caps wide letters:    ~0.62 (widest avg)
# thc    — digits + % + spaces:      ~0.55
# price  — $ + digits + . :          ~0.60
_FIELD_RATIOS = {"brand": 0.46, "strain": 0.62, "thc": 0.55, "price": 0.60}


def _apply_optimal_sizes(template_path, page_rows, tmpdir, tag):
    """Write a copy of the template whose field DAs carry a computed (larger)
    fixed font size per field, so the filled text fills each box better than
    pdftk's conservative autosize. Returns the path to the modified template."""
    from pypdf.generic import TextStringObject, NameObject
    sm = build_slot_map(template_path)
    max_slots = max(sm.keys()) if sm else 0
    # Map field-name -> the text value it will hold on this page
    name_to_text = {}
    for slot in range(1, max_slots + 1):
        d = page_rows[slot - 1] if slot - 1 < len(page_rows) else None
        sf = sm.get(slot, {})
        for key in ("brand", "strain", "thc", "price"):
            fn = sf.get(key)
            if fn:
                name_to_text[fn] = (d.get(key, "") if d else "")

    reader = PdfReader(template_path)
    writer = PdfWriter()
    writer.append(reader)

    # Build reverse map: field-name → field-type (brand/strain/thc/price)
    name_to_type = {}
    for slot, keys in sm.items():
        for ftype, fname in keys.items():
            name_to_type[fname] = ftype

    for page in writer.pages:
        for a in page.get("/Annots", []):
            o = a.get_object()
            nm = o.get("/T")
            parent = o.get("/Parent")
            if nm is None and parent:
                nm = parent.get_object().get("/T")
            fieldname = str(nm) if nm else None
            if fieldname not in name_to_text:
                continue
            rect = o.get("/Rect")
            if not rect:
                continue
            fw = abs(float(rect[2]) - float(rect[0]))
            fh = abs(float(rect[3]) - float(rect[1]))
            text  = name_to_text[fieldname]
            ftype = name_to_type.get(fieldname, "brand")
            ratio = _FIELD_RATIOS.get(ftype, 0.52)
            size  = _optimal_size(text, fw, fh, ratio)
            da    = f"/Paralucent-Heavy {size:.2f} Tf 0 g"
            target = o if o.get("/T") else (parent.get_object() if parent else o)
            target[NameObject("/DA")] = TextStringObject(da)

    out_tmpl = os.path.join(tmpdir, f"tmpl_{tag}.pdf")
    with open(out_tmpl, "wb") as f:
        writer.write(f)
    return out_tmpl


def _fill_template(template_path, page_rows, tmpdir, tag):
    """Fill one page of a template with page_rows, return output pdf path.
    Sizes each field's font to fill its box better than default autosize."""
    sm = build_slot_map(template_path)
    max_slots = max(sm.keys()) if sm else 0
    # Build a template variant with per-field optimal font sizes baked in.
    sized_tmpl = _apply_optimal_sizes(template_path, page_rows, tmpdir, tag)
    fdf_path = os.path.join(tmpdir, f"{tag}.fdf")
    out_path = os.path.join(tmpdir, f"{tag}.pdf")
    with open(fdf_path, "w", encoding="latin-1") as f:
        f.write(_make_fdf(sm, page_rows, max_slots))
    r = subprocess.run(
        ["pdftk", sized_tmpl, "fill_form", fdf_path, "output", out_path],
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
