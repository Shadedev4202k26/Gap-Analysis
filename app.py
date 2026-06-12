import streamlit as st
import pandas as pd
import base64
import os
import json
import requests
import re
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
.brand-banner { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid rgba(139, 92, 246, 0.3); border-left: 6px solid #8B5CF6; border-radius: 16px; margin-bottom: 30px; display: flex; align-items: center; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); }
.brand-text h1 { font-family: 'Poppins', sans-serif; font-weight: 900; color: #8B5CF6 !important; font-size: 42px; margin: 0; letter-spacing: -1.5px; text-transform: uppercase; }
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

logo_path = 'image.png'
logo_html = f'<img src="data:image/png;base64,{base64.b64encode(open(logo_path, "rb").read()).decode("utf-8")}" style="height: 196px; margin-right: 30px; border-radius: 8px;">' if os.path.exists(logo_path) else ""
st.markdown(f'<div class="brand-banner" style="padding: 50px 35px;">{logo_html}<div class="brand-text"><h1>Ziggyz Strain Sniffer & Hub</h1><p>Inventory Logistics & Base Knowledge Management Engine</p></div></div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🔍 STRAIN SNIFFER", "📊 INVENTORY INTELLIGENCE", "🏷️ HOOK TAG GENERATOR"])

with tab1:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    with st.form("strain_form", clear_on_submit=True):
        user_input = st.text_input("Enter Strain Name:", placeholder="e.g., permanent marker...")
        

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
        results = [{"Product Name": product, "Location": r, "Available Qty": int(row[r])} for product, row in pivot.iterrows() for r in row[row >= min_threshold].index if row[row > 0].index.size > 0]
        final_df = pd.DataFrame(results)
        if not final_df.empty:
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.download_button("📥 DOWNLOAD MERCHANDISING PDF", build_pdf(final_df, min_threshold), "Ziggy_Report.pdf", "application/pdf")

with tab3:
    st.markdown("### 🏷️ Automated Hook Tag Formatter")
    
    if not PYPDF_AVAILABLE:
        st.error("⚠️ The required library 'pypdf' is not installed yet. Please add 'pypdf' to your requirements.txt file in GitHub to activate this feature.")
    else:
        st.write("Upload your inventory CSV to instantly generate a multi-page print file using your GitHub template.")

        hook_file = st.file_uploader("Drop Hook Tag Inventory (CSV)", type=["csv"], key="hook_csv")

        if hook_file is not None:
            template_path = "master_template.pdf"
            
            if not os.path.exists(template_path):
                st.error("⚠️ 'master_template.pdf' is missing from your GitHub repository. Please upload it to your main folder to proceed.")
            else:
                df_hook = pd.read_csv(hook_file)
                
                df_hook.columns = [str(col).strip('="').strip() for col in df_hook.columns]
                
                if 'Product' in df_hook.columns:
                    df_hook['Product'] = df_hook['Product'].apply(lambda x: str(x).strip('="').strip())
                    df_hook = df_hook.drop_duplicates(subset=['Product']).dropna(subset=['Product'])
                
                product_list = []

                for index, row in df_hook.iterrows():
                    product_name = str(row.get('Product', ''))
                    if not product_name.strip() or product_name.lower() == 'nan':
                        continue
                        
                    parts = [p.strip() for p in product_name.split('|')]
                    if len(parts) >= 3:
                        brand = f"{parts[0]} | {parts[2]}"
                        strain = parts[1]
                    elif len(parts) == 2:
                        brand = parts[0]
                        strain = parts[1]
                    else:
                        brand = "MUHA MEDS"
                        strain = product_name
                        
                    raw_thc = str(row.get('THC', '0'))
                    try:
                        thc_str = ''.join(c for c in raw_thc if c.isdigit() or c == '.')
                        if thc_str:
                            thc = f"{round(float(thc_str))}%"
                        else:
                            thc = "88%"
                    except ValueError:
                        thc = "88%" 
                        
                    price_col = 'Current price' if 'Current price' in df_hook.columns else 'Price'
                    raw_price = str(row.get(price_col, '0')).replace('$', '')
                    try:
                        price_str = ''.join(c for c in raw_price if c.isdigit() or c == '.')
                        if price_str:
                            price_val = float(price_str)
                            price = f"${int(price_val)}" if price_val.is_integer() else f"${price_val:.2f}"
                        else:
                            price = "$0"
                    except ValueError:
                        price = "$0"
                    
                    product_list.append({
                        "brand": brand.upper(),
                        "strain": strain.upper(),
                        "price": f"{thc} Smilez  {price}"
                    })

                if product_list:
                    try:
                        blueprint_reader = PdfReader(template_path)
                        blueprint_page = blueprint_reader.pages[0]
                        page_width = float(blueprint_page.mediabox.width)
                        page_height = float(blueprint_page.mediabox.height)
                        
                        field_data = {}
                        if "/Annots" in blueprint_page:
                            for annot in blueprint_page.get("/Annots", []):
                                annot_obj = annot.get_object()
                                if annot_obj.get("/Subtype") == "/Widget" and annot_obj.get("/T"):
                                    name = str(annot_obj.get("/T")).strip("()")
                                    rect = annot_obj.get("/Rect")
                                    if rect:
                                        field_data[name] = [float(r) for r in rect]
                        
                        if field_data:
                            tag_numbers = []
                            for name in field_data.keys():
                                match = re.search(r'\d+', name)
                                if match:
                                    tag_numbers.append(int(match.group()))
                                    
                            tags_per_page = max(tag_numbers) if tag_numbers else 1
                            final_writer = PdfWriter()
                            
                            data_chunks = [product_list[i:i + tags_per_page] for i in range(0, len(product_list), tags_per_page)]
                            
                            for page_num, chunk in enumerate(data_chunks):
                                packet = BytesIO()
                                c = canvas.Canvas(packet, pagesize=(page_width, page_height))
                                
                                for field_name, rect in field_data.items():
                                    
                                    match = re.search(r'\d+', field_name)
                                    tag_idx = (int(match.group()) - 1) if match else 0
                                    
                                    if tag_idx < len(chunk):
                                        product = chunk[tag_idx]
                                        name_lower = field_name.lower()
                                        
                                        text = ""
                                        is_brand = False
                                        max_size = 14
                                        
                                        if 'brand' in name_lower:
                                            text = product['brand']
                                            max_size = 28
                                            is_brand = True
                                        elif 'strain' in name_lower:
                                            text = product['strain']
                                            max_size = 16
                                        elif 'price' in name_lower or 'thc' in name_lower:
                                            text = product['price']
                                            max_size = 14
                                            
                                        if text:
                                            ll_x, ll_y, ur_x, ur_y = rect
                                            box_width = ur_x - ll_x
                                            box_height = ur_y - ll_y
                                            center_x = ll_x + (box_width / 2)
                                            
                                            font_size = max_size
                                            c.setFont("Helvetica-Bold", font_size)
                                            
                                            while c.stringWidth(text, "Helvetica-Bold", font_size) > (box_width - 8) and font_size > 6:
                                                font_size -= 0.5
                                                c.setFont("Helvetica-Bold", font_size)
                                            
                                            center_y = ll_y + (box_height / 2) - (font_size * 0.35)
                                            
                                            if is_brand:
                                                c.setTextRenderMode(2) 
                                                c.setLineWidth(0.4)    
                                                c.setStrokeColorRGB(0, 0, 0)
                                            else:
                                                c.setTextRenderMode(0)
                                                
                                            c.setFillColorRGB(0, 0, 0)
                                            c.drawCentredString(center_x, center_y, text)

                                c.showPage()
                                c.save()
                                packet.seek(0)
                                overlay = PdfReader(packet)
                                
                                fresh_reader = PdfReader(template_path)
                                base_page = fresh_reader.pages[0]
                                base_page.merge_page(overlay.pages[0])
                                
                                if "/Annots" in base_page:
                                    del base_page[NameObject("/Annots")]
                                    
                                final_writer.add_page(base_page)
                            
                            if "/AcroForm" in final_writer.root_object:
                                del final_writer.root_object[NameObject("/AcroForm")]
                            
                            pdf_output = BytesIO()
                            final_writer.write(pdf_output)
                            pdf_output.seek(0)
                            
                            total_tags = len(product_list)
                            st.success(f"Successfully baked {total_tags} perfectly sized tags across {len(data_chunks)} pages!")
                            
                            st.download_button(
                                label="📥 DOWNLOAD FLATTENED PRINT FILE",
                                data=pdf_output,
                                file_name="Print_Ready_Hook_Tabs.pdf",
                                mime="application/pdf"
                            )
                        else:
                            st.error("No invisible layout boxes detected in the master_template.pdf.")
                        
                    except Exception as e:
                        st.error(f"Error processing the PDF: {e}")
