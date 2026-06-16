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
