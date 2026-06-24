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


def _load_font_widths(template_path):
    """Extract the real Paralucent-Heavy glyph widths (1/1000 em) from the
    template's AcroForm resources so text can be measured exactly."""
    try:
        reader = PdfReader(template_path)
        acro = reader.trailer["/Root"].get("/AcroForm", {})
        fonts = acro.get("/DR", {}).get("/Font", {}) if acro else {}
        para = None
        for k, v in (fonts.items() if hasattr(fonts, "items") else []):
            fo = v.get_object()
            if "Paralucent" in str(fo.get("/BaseFont", "")) and "/Widths" in fo:
                para = fo
                break
        if para is None:
            return None
        widths = [int(x) for x in para.get("/Widths")]
        first = int(para.get("/FirstChar", 0))
        return {"widths": widths, "first": first}
    except Exception:
        return None


def _text_width_units(text, fontinfo):
    """Total advance width of text in 1/1000 em units."""
    if not fontinfo:
        return len(text or "") * 500
    widths, first = fontinfo["widths"], fontinfo["first"]
    total = 0
    for ch in (text or ""):
        idx = ord(ch) - first
        total += widths[idx] if 0 <= idx < len(widths) else 500
    return max(1, total)


def _optimal_size(text, field_w, field_h, fontinfo, height_factor=0.62):
    """Largest font size that fits the text within the field, measured with the
    real font metrics so it never clips. Bounded by width AND height."""
    units = _text_width_units(text, fontinfo)
    usable_w = max(1.0, field_w - 8)            # padding each side
    size_w = usable_w * 1000.0 / units          # exact width-fit
    size_h = field_h * height_factor             # height cap
    return max(6.0, min(size_w, size_h))


def _field_rect(writer, fieldname):
    """Return (width, height) of the named field's widget rectangle."""
    for page in writer.pages:
        for a in page.get("/Annots", []):
            o = a.get_object()
            nm = o.get("/T")
            parent = o.get("/Parent")
            if nm is None and parent:
                nm = parent.get_object().get("/T")
            if str(nm) == fieldname and o.get("/Rect"):
                r = o["/Rect"]
                return (abs(float(r[2]) - float(r[0])), abs(float(r[3]) - float(r[1])))
    return None


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

    # Load the real font metrics once so text is measured exactly (no clipping).
    fontinfo = _load_font_widths(template_path)

    # THC and PRICE share a visual row. Size every THC/PRICE box on the sheet to
    # ONE shared font size — the largest that still fits all of them — so prices
    # (and THCs) are uniform tag-to-tag and their baselines line up.
    name_to_size = {}
    tp_fields, tp_sizes = [], []
    for slot in range(1, max_slots + 1):
        sf = sm.get(slot, {})
        for key in ("thc", "price"):
            fn = sf.get(key)
            if not fn:
                continue
            rect = _field_rect(writer, fn)
            if not rect:
                continue
            fw, fh = rect
            tp_fields.append(fn)
            txt = name_to_text.get(fn, "")
            if txt.strip():                       # ignore blank slots when finding the min
                tp_sizes.append(_optimal_size(txt, fw, fh, fontinfo, height_factor=0.80))
    if tp_fields:
        shared = min(tp_sizes) if tp_sizes else 12.0
        for fn in tp_fields:
            name_to_size[fn] = shared

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
            text = name_to_text[fieldname]
            # use the matched THC/price size when available, else per-field optimal
            size = name_to_size.get(fieldname) or _optimal_size(text, fw, fh, fontinfo)
            da   = f"/Paralucent-Heavy {size:.2f} Tf 0 g"
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
        ["pdftk", sized_tmpl, "fill_form", fdf_path, "output", out_path, "flatten"],
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
