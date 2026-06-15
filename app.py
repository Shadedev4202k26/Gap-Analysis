import streamlit as st
import pandas as pd
import base64
import os
import json
import requests
import re
import subprocess
import tempfile
import shutil
from urllib.parse import quote_plus
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from io import BytesIO

# Safe import wrapper to prevent crashes if pypdf is missing
try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, create_string_object, NumberObject
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

st.set_page_config(page_title="Ziggybot", page_icon="🔥", layout="wide")

def generate_strain_profile(groq_key, strain_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    api_headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    
    system_prompt = (
        "You are a highly accurate cannabis strain database for a retail dispensary. "
        "Provide the most widely accepted genetic lineage, terpenes, flavor, and effects for the requested strain based on established industry knowledge. "
        "If the strain name is completely unrecognizable or clearly fictional, output 'Unknown strain, please check Google' for the lineage. "
        "Output clean, structured JSON. Keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects', 'cannabinoids'."
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": f"Target Strain: {strain_name}"}
        ], 
        "temperature": 0.1
    }
    
    try:
        res = requests.post(url, headers=api_headers, json=payload, timeout=12)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: 
                content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
    except Exception as e: 
        return {"error": str(e)}
        
    return {"classification": "HYBRID", "lineage": "N/A", "terpenes": "N/A", "flavor": "N/A", "effects": "N/A", "cannabinoids": "N/A"}

def get_compound_profile(api_key, compound_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = "You are an advanced cannabinoid science database. Output JSON. Keys: 'status', 'primary_effects', 'medical_benefits', 'customer_pitch'."
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Profile for: {compound_name}"}], "temperature": 0.1}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
        return {"error": f"Status code {res.status_code}"}
    except Exception as e: return {"error": str(e)}

def build_pdf(dataframe, threshold_value):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    subtitle_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#4B5563'), fontName='Helvetica-Bold', spaceAfter=20)
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#374151'))
    header_style = ParagraphStyle('HeaderText', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#0F172A'))
    story.append(Paragraph("Ziggyz Merchandise Gap Report", title_style))
    story.append(Paragraph("HIGH-IMPACT FLOOR RESTOCK & DISCREPANCY MANIFEST", subtitle_style))
    metric_data = [[Paragraph(f"<b>High-Impact Gaps:</b> {len(dataframe)}", cell_style), Paragraph(f"<b>Units to Move:</b> {dataframe['Available Qty'].sum()}", cell_style), Paragraph(f"<b>Min Threshold:</b> {threshold_value}+", cell_style)]]
    metric_table = Table(metric_data, colWidths=[180, 180, 172])
    metric_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')), ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')), ('PADDING', (0,0), (-1,-1), 12), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    story.append(metric_table)
    table_content = [[Paragraph("Product Name", header_style), Paragraph("Location", header_style), Paragraph("Available Qty", header_style)]]
    for _, row in dataframe.iterrows():
        table_content.append([Paragraph(str(row['Product Name']), cell_style), Paragraph(str(row['Location']), cell_style), Paragraph(str(row['Available Qty']), cell_style)])
    data_table = Table(table_content, colWidths=[312, 110, 110])
    data_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F3F4F6')), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')), ('PADDING', (0,0), (-1,-1), 8)]))
    story.append(data_table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800;900&family=Inter:wght@400;500;700&display=swap');
.stApp { background-color: #0F172A; color: #F8FAFC; font-family: 'Inter', sans-serif; }
.brand-banner { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid rgba(139, 92, 246, 0.3); border-left: 6px solid #8B5CF6; border-radius: 16px; margin-bottom: 15px; display: flex; align-items: center; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); }
.brand-text h1 { font-family: 'Poppins', sans-serif; font-weight: 900; color: #8B5CF6 !important; font-size: 42px; margin: 0; letter-spacing: -1.5px; text-transform: uppercase; }
.quote-banner { background: #1E293B; border-radius: 12px; padding: 15px 25px; margin-bottom: 30px; border: 1px solid rgba(139, 92, 246, 0.15); border-left: 4px solid #8B5CF6; text-align: center; }
.quote-text { font-family: 'Inter', sans-serif; font-size: 15px; font-style: italic; color: #E5E7EB; margin: 0; font-weight: 500; line-height: 1.4; }
.quote-author { color: #A78BFA; font-weight: 700; font-style: normal; }
.stTabs [data-baseweb='tab'] { height: 60px; background-color: #1E293B !important; border-radius: 10px 10px 0 0 !important; color: #94A3B8 !important; font-weight: 800; }
.stTabs [aria-selected='true'] { background-color: #8B5CF6 !important; color: #F8FAFC !important; }
.strain-card { background: linear-gradient(145deg, #1E293B 0%, #0F172A 100%); padding: 35px; border-radius: 16px; border-top: 4px solid #8B5CF6; margin-top: 20px; }
.strain-title { font-family: 'Poppins', sans-serif; font-weight: 900; font-size: 34px; color: #F8FAFC; text-transform: uppercase; }
.badge-sativa { background: linear-gradient(90deg, #10B981, #059669); color: #FFF; padding: 6px 16px; border-radius: 8px; font-weight: 800; font-size: 12px; text-transform: uppercase; }
.badge-hybrid { background: linear-gradient(90deg, #8B5CF6, #6D28D9); color: #FFF; padding: 6px 16px; border-radius: 8px; font-weight: 800; font-size: 12px; text-transform: uppercase; }
.badge-indica { background: linear-gradient(90deg, #3B82F6, #2563EB); color: #FFF; padding: 6px 16px; border-radius: 8px; font-weight: 800; font-size: 12px; text-transform: uppercase; }
.section-head { color: #A78BFA; font-weight: 800; text-transform: uppercase; font-size: 13px; margin-top: 24px; }
.section-data { font-size: 16px; color: #E5E7EB; margin-top: 6px; }
.google-btn { background: linear-gradient(90deg, #8B5CF6, #6D28D9); color: #F8FAFC !important; padding: 10px 16px; border-radius: 8px; font-weight: 800; text-transform: uppercase; text-decoration: none; display: inline-block; }
.metric-tile { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 25px; border-radius: 16px; border: 1px solid rgba(139, 92, 246, 0.2); text-align: center; }
.metric-label { color: #A78BFA; font-size: 13px; font-weight: 800; text-transform: uppercase; }
.metric-value { font-family: 'Poppins', sans-serif; font-size: 48px; font-weight: 900; color: #F8FAFC; }
</style>"""
st.markdown(custom_css, unsafe_allow_html=True)

# Main layout split
header_col1, header_col2 = st.columns([1, 1])

with header_col1:
    video_file = open('video.mp4', 'rb')
    video_bytes = video_file.read()
    st.video(video_bytes, loop=True, autoplay=True, muted=True) 

with header_col2:
    st.markdown(
        '<div class="brand-banner" style="padding: 25px; min-height: 140px;">'
        '<div class="brand-text">'
        '<h1>Ziggy\'s Strain Sniffer & Inventory Assistant</h1>'
        '<p style="color: #94A3B8; font-weight: 500; margin-top: 4px;">Dispensary Operational Base Engine</p>'
        '</div></div>', 
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="quote-banner">'
        '<p class="quote-text">"Your attitude, not your aptitude, will determine your altitude." &mdash; <span class="quote-author">Zig</span></p>'
        '</div>',
        unsafe_allow_html=True
    )

tab1, tab2, tab3 = st.tabs(["🔍 STRAIN SNIFFER", "📊 INVENTORY INTELLIGENCE", "🏷️ HOOK TAG GENERATOR"])

with tab1:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    with st.form("strain_form", clear_on_submit=True):
        user_input = st.text_input("Enter Strain Name:", placeholder="e.g., permanent marker...")
        submitted = st.form_submit_button("SEARCH STRAIN")

    if submitted and user_input:
        st.session_state.last_strain = user_input
        st.rerun()

    if "last_strain" in st.session_state and st.session_state.last_strain:
        strain = st.session_state.last_strain
        google_url = f"https://www.google.com/search?q={quote_plus(strain + ' strain')}"
        st.markdown(f'<a href="{google_url}" target="_blank" class="google-btn">💥 MORE RESULTS FOR {strain.upper()}</a>', unsafe_allow_html=True)
        data = generate_strain_profile(st.secrets["GROQ_API_KEY"], strain)
        if "error" not in data:
            clf = str(data.get('classification', 'HYBRID')).upper()
            badge = "badge-sativa" if "SATIVA" in clf else ("badge-indica" if "INDICA" in clf else "badge-hybrid")
            st.markdown(f'<div class="strain-card"><div class="card-header-flow"><div class="strain-title">✨ {strain.upper()}</div><span class="{badge}">{clf}</span></div><hr><div class="section-head">🌿 Lineage</div><div class="section-data">{data.get("lineage")}</div><div class="section-head">🧪 Terpenes</div><div class="section-data">{data.get("terpenes")}</div><div class="section-head">🍋 Flavor</div><div class="section-data">{data.get("flavor")}</div><div class="section-head">⚡ Cannabinoids</div><div class="section-data" style="color: #A78BFA;">{data.get("cannabinoids")}</div><div class="section-head">🧠 Effects</div><div class="section-data">{data.get("effects")}</div></div>', unsafe_allow_html=True)
        st.session_state.last_strain = None

    st.write("---")
    st.markdown("### 🧪 Cannabinoid & THC Compound Encyclopedia")
    col_select, col_custom = st.columns([2, 2])
    with col_select:
        selected_chem = st.selectbox("Quick Select Target Compound", ["-- Choose a Compound --", "THC", "THCV", "THCP", "CBD", "CBG", "CBN", "Delta-8 THC"])
    with col_custom:
        custom_chem = st.text_input("Or Type a Specific Compound Variant", placeholder="e.g., THCO, CBDA...").strip()
    
    target_chem = custom_chem if custom_chem else (None if selected_chem == "-- Choose a Compound --" else selected_chem)
    if target_chem:
        chem_data = get_compound_profile(st.secrets["GROQ_API_KEY"], target_chem)
        if "error" not in chem_data:
            st.markdown(f'<div class="strain-card" style="border-top: 4px solid #3B82F6;"><div class="strain-title">🔬 {target_chem.upper()}</div><div class="section-head">🧠 Primary Effects</div><div class="section-data">{chem_data.get("primary_effects")}</div><div class="section-head">🩺 Benefits</div><div class="section-data">{chem_data.get("medical_benefits")}</div><div class="section-head">🎯 The Budtender Pitch</div><div class="section-data" style="font-style: italic;">"{chem_data.get("customer_pitch")}"</div></div>', unsafe_allow_html=True)

with tab2:
    st.markdown("### 📥 Live Restock Gap Analyzer")
    uploaded_file = st.file_uploader("Drop Dutchie CSV Export Here", type="csv", key="restock_csv")
    min_threshold = st.slider("Min Threshold:", 1, 50, 15)
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        df.columns = [str(col).strip('="').strip() for col in df.columns]
        qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col][0]
        df['Product'] = df['Product'].apply(lambda x: str(x).strip('="').strip())
        df['Room'] = df['Room'].apply(lambda x: str(x).strip('="').strip())
        df['Qty'] = pd.to_numeric(df[qty_col].apply(lambda x: str(x).strip('="').strip()), errors='coerce').fillna(0)
        pivot = df.groupby(['Product', 'Room'])['Qty'].sum().unstack(fill_value=0)
        results = [{"Product Name": product, "Location": r, "Available Qty": int(row[r])} for product, row in pivot.iterrows() if (row == 0).any() for r in row[row >= min_threshold].index]
        final_df = pd.DataFrame(results)
        if not final_df.empty:
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.download_button("📥 DOWNLOAD MERCHANDISING PDF", build_pdf(final_df, min_threshold), "Ziggy_Report.pdf", "application/pdf")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — HOOK TAG GENERATOR
# Uses pdftk to fill the AcroForm fields in master_template.pdf directly.
# This preserves the embedded Paralucent-Heavy font and triggers true autosize
# so every tag fills its box perfectly regardless of text length.
#
# DEPLOYMENT CHECKLIST:
#   1. Add  pdftk  to packages.txt  (system dependency)
#   2. Add  pypdf  to requirements.txt  (already imported above)
#   3. Commit master_template.pdf to the root of your repo
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("### 🏷️ Automated Hook Tag Formatter")

    TEMPLATE_PATH = "master_template.pdf"

    # ── Dependency checks ────────────────────────────────────────────────────
    if not PYPDF_AVAILABLE:
        st.error("⚠️ pypdf is not installed. Add `pypdf` to requirements.txt and redeploy.")
        st.stop()

    try:
        subprocess.run(["pdftk", "--version"], capture_output=True, check=True)
        pdftk_ok = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pdftk_ok = False

    if not pdftk_ok:
        st.error("⚠️ pdftk is not installed. Add `pdftk` to packages.txt and redeploy.")
        st.stop()

    if not os.path.exists(TEMPLATE_PATH):
        st.error("⚠️ `master_template.pdf` not found. Commit it to the root of your GitHub repo.")
        st.stop()

    # ── Auto-detect slot→field mapping from the template (runs once) ─────────
    @st.cache_resource
    def load_slot_map(template_path):
        """Read the template's AcroForm placeholder values to build a
        slot-number → {brand, strain, thc, price} field-name mapping."""
        reader  = PdfReader(template_path)
        fields  = reader.get_fields() or {}
        slot_map = {}
        for field_name, field in fields.items():
            v = field.get("/V", "")
            if not isinstance(v, str):
                continue
            vs = v.strip()
            for prefix, key in [
                ("BRAND_",  "brand"),
                ("STRAIN_", "strain"),
                ("THC_",    "thc"),
                ("PRICE_",  "price"),
            ]:
                if vs.startswith(prefix):
                    try:
                        n = int(vs[len(prefix):].strip())
                        slot_map.setdefault(n, {})[key] = field_name
                    except ValueError:
                        pass
        return slot_map

    slot_map = load_slot_map(TEMPLATE_PATH)

    if not slot_map:
        st.error(
            "The template doesn't contain BRAND_N / STRAIN_N / THC_N / PRICE_N "
            "placeholder values. Check that master_template.pdf is the correct file."
        )
        st.stop()

    slots_per_page = max(slot_map.keys())   # e.g. 24

    # ── UI ───────────────────────────────────────────────────────────────────
    st.markdown(
        f"In Dutchie Backend Inventory select any combination of product, room, category, ect."
        f"Export Only Product, THC, & Current Price"
        f"Upload your inventory CSV. One tag per unique product — if the same strain "
        f"appears with different THC percentages, each variation gets its own tag. Save addtional tag for future use."
        f"Template fits **{slots_per_page} tags per sheet**."
    )
    hook_file = st.file_uploader(
        "Drop Hook Tag Inventory (CSV)", type=["csv"], key="hook_csv"
    )

    if hook_file is None:
        st.stop()

    # ── Parse CSV ────────────────────────────────────────────────────────────
    df_hook = pd.read_csv(hook_file)
    df_hook.columns = [str(c).strip('="').strip() for c in df_hook.columns]

    price_col = "Current price" if "Current price" in df_hook.columns else "Price"

    rows = []
    for _, row in df_hook.iterrows():
        product = str(row.get("Product", "")).strip('="').strip()
        if not product or product.lower() == "nan":
            continue

        # Split "Brand | Strain | Product Type" → brand / strain+type
        parts  = [p.strip() for p in product.split("|")]
        brand  = parts[0]               if len(parts) >= 1 else ""
        strain = " | ".join(parts[1:])  if len(parts) >= 2 else product

        # THC — keep the raw CSV value (e.g. "87.66 %")
        thc = str(row.get("THC", "")).strip()

        # Price — normalise to "$N" or "$N.NN"
        raw_price  = str(row.get(price_col, "0")).replace("$", "").strip('="').strip()
        price_digits = "".join(c for c in raw_price if c.isdigit() or c == ".")
        try:
            pv    = float(price_digits) if price_digits else 0.0
            price = f"${int(pv)}" if pv == int(pv) else f"${pv:.2f}"
        except ValueError:
            price = "$0"

        rows.append({"brand": brand, "strain": strain, "thc": thc, "price": price})

    if not rows:
        st.error("No valid product rows found in the CSV.")
        st.stop()

    # ── Deduplicate: one tag per unique (brand, strain, thc) combo ───────────
    # Same product + same THC → single tag. Different THC → separate tag each.
    seen    = set()
    deduped = []
    for r in rows:
        key = (r["brand"].strip().lower(), r["strain"].strip().lower(), r["thc"].strip().lower())
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    rows = deduped

    st.info(f"**{len(rows)}** unique tags — will generate **{-(-len(rows) // slots_per_page)}** sheet(s).")

    # ── FDF builder ──────────────────────────────────────────────────────────
    def _esc(s):
        """Escape a string for use inside a PDF literal string."""
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def make_fdf(page_rows):
        """Return an FDF byte string that fills one page of the template."""
        entries = []
        for slot in range(1, slots_per_page + 1):
            d  = page_rows[slot - 1] if slot - 1 < len(page_rows) else {}
            sf = slot_map.get(slot, {})
            for key, val in [
                ("brand",  d.get("brand",  "")),
                ("strain", d.get("strain", "")),
                ("thc",    d.get("thc",    "")),
                ("price",  d.get("price",  "")),
            ]:
                fn = sf.get(key)
                if fn:
                    entries.append(f"<</T ({_esc(fn)})/V ({_esc(val)})>>")
        return (
            "%FDF-1.2\n1 0 obj\n<< /FDF << /Fields [\n"
            + "\n".join(entries)
            + "\n] >> >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
        )

    # ── Generate PDF on button press ─────────────────────────────────────────
    if st.button("🖨️ GENERATE HOOK TAGS", type="primary"):
        pages = [rows[i : i + slots_per_page] for i in range(0, len(rows), slots_per_page)]

        with st.spinner(f"Filling {len(rows)} tags across {len(pages)} page(s)…"):
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    page_paths = []
                    error_msg  = None

                    for i, page_rows in enumerate(pages):
                        fdf_path = os.path.join(tmpdir, f"p{i}.fdf")
                        out_path  = os.path.join(tmpdir, f"p{i}.pdf")

                        with open(fdf_path, "w", encoding="latin-1") as f:
                            f.write(make_fdf(page_rows))

                        r = subprocess.run(
                            ["pdftk", TEMPLATE_PATH, "fill_form", fdf_path, "output", out_path],
                            capture_output=True, text=True,
                        )
                        if r.returncode != 0:
                            error_msg = f"pdftk error on page {i + 1}: {r.stderr.strip()}"
                            break
                        page_paths.append(out_path)

                    if error_msg:
                        st.error(error_msg)
                        st.stop()

                    # Merge pages (or single page pass-through)
                    if len(page_paths) == 1:
                        final_path = page_paths[0]
                    else:
                        final_path = os.path.join(tmpdir, "merged.pdf")
                        r = subprocess.run(
                            ["pdftk"] + page_paths + ["cat", "output", final_path],
                            capture_output=True, text=True,
                        )
                        if r.returncode != 0:
                            st.error(f"pdftk merge error: {r.stderr.strip()}")
                            st.stop()

                    with open(final_path, "rb") as f:
                        pdf_bytes = f.read()

            except Exception as e:
                st.error(f"Unexpected error: {e}")
                st.stop()

        st.success(f"✅ {len(rows)} tags across {len(pages)} sheet(s) — ready to print!")
        st.download_button(
            label="📥 DOWNLOAD PRINT-READY HOOK TAGS",
            data=pdf_bytes,
            file_name="HookTags_Ready.pdf",
            mime="application/pdf",
        )
