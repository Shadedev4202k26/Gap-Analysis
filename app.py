import streamlit as st, pandas as pd, base64, os, json, requests
from urllib.parse import quote_plus
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from io import BytesIO

st.set_page_config(page_title="Ziggybot", page_icon="🔥", layout="wide")

def parse_pasted_context(groq_key, strain_name, raw_pasted_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    api_headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    
    system_prompt = (
        "You are an expert cannabis strain database compiler. Your sole objective is outputting clean, structured JSON.\n"
        "You will synthesize the raw text snippets provided by the user (copied from web search results, leafly, wikileaf, seedbanks, or grower forums) "
        "to parse out true genetic facts for the target strain.\n"
        "Even for rare, proprietary, or boutique marketplace strains, use the text clues to deduce the lineage or brand profile.\n\n"
        "CRITICAL EXTRACTION INSTRUCTIONS:\n"
        "1. LINEAGE: Identify the direct parental cross (e.g., 'Mendo Breath X Purple Punch'). If the text mentions a specific breeder brand or origin, capture that context accurately.\n"
        "2. TERPENES: Isolate the dominant terpene profile based on the text. Do not leave blank if any flavor/aroma properties are described.\n"
        "3. CLASSIFICATION: Strictly output 'INDICA', 'SATIVA', or 'HYBRID'.\n"
        "4. FLAVOR & EFFECTS: Provide a summary of consumer properties found in the text.\n\n"
        "Return ONLY a clean, valid JSON object containing exactly these keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects'."
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": f"Target Strain: {strain_name}\n\nRaw Search Text Provided:\n{raw_pasted_text}"}
        ], 
        "temperature": 0.0
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
    return {"classification": "HYBRID", "lineage": "Proprietary / Unverified Genetics", "terpenes": "N/A", "flavor": "N/A", "effects": "N/A"}

def get_compound_profile(api_key, compound_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = (
        "You are an advanced cannabinoid science database. Analyze the requested cannabis compound or THC variant "
        "and return ONLY a valid JSON object. Do not use double quotes inside any text values. "
        "The JSON must contain exactly these keys: 'status', 'primary_effects', 'medical_benefits', 'customer_pitch'."
    )
    user_prompt = f"Provide a consumer-facing operational profile for the specific compound: {compound_name}"
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.1}
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
    story.append(Spacer(1, 10))
    
    metric_data = [
        [Paragraph(f"<b>High-Impact Gaps:</b> {len(dataframe)}", cell_style),
         Paragraph(f"<b>Units to Move:</b> {dataframe['Available Qty'].sum()}", cell_style),
         Paragraph(f"<b>Min Threshold:</b> {threshold_value}+", cell_style)]
    ]
    metric_table = Table(metric_data, colWidths=[180, 180, 172])
    metric_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
        ('PADDING', (0,0), (-1,-1), 12),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(metric_table)
    story.append(Spacer(1, 25))
    
    table_content = [[Paragraph("Product Name", header_style), Paragraph("Location", header_style), Paragraph("Available Qty", header_style)]]
    for _, row in dataframe.iterrows():
        table_content.append([
            Paragraph(str(row['Product Name']), cell_style),
            Paragraph(str(row['Location']), cell_style),
            Paragraph(str(row['Available Qty']), cell_style)
        ])
        
    data_table = Table(table_content, colWidths=[312, 110, 110])
    data_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F3F4F6')),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('TOPPADDING', (0,0), (-1,0), 10),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    
    story.append(data_table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# UI Styling Configuration (Ziggy Urban Theme)
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght=400;600;800;900&family=Inter:wght=400;500;700&display=swap');

.stApp { background-color: #0F172A; color: #F8FAFC; font-family: 'Inter', sans-serif; }

/* The Hero Banner */
.brand-banner {
  background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-left: 6px solid #8B5CF6;
  border-radius: 16px;
  margin-bottom: 30px;
  display: flex;
  align-items: center;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
}
.brand-text h1 { font-family: 'Poppins', sans-serif; font-weight: 900; color: #8B5CF6 !important; font-size: 42px; margin: 0; letter-spacing: -1.5px; text-transform: uppercase; text-shadow: 2px 2px 4px rgba(0,0,0,0.4); }
.brand-text p { color: #E5E7EB; margin: 5px 0 0 0; font-size: 16px; font-weight: 500; letter-spacing: 0.5px; }

/* Tabs */
.stTabs [data-baseweb='tab-list'] { gap: 10px; background-color: transparent; }
.stTabs [data-baseweb='tab'] { height: 60px; background-color: #1E293B !important; border-radius: 10px 10px 0 0 !important; padding: 10px 25px !important; color: #94A3B8 !important; font-family: 'Poppins', sans-serif; font-weight: 800; border: 1px solid transparent !important; border-bottom: none !important; transition: all 0.3s ease; }
.stTabs [aria-selected='true'] { background-color: #8B5CF6 !important; color: #F8FAFC !important; box-shadow: 0 -4px 15px rgba(139, 92, 246, 0.4); }

/* Metric Tiles (Ziggy Cards) */
.metric-tile { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 25px; border-radius: 16px; border: 1px solid rgba(139, 92, 246, 0.2); text-align: center; box-shadow: 0 8px 20px rgba(0,0,0,0.3); transition: transform 0.2s ease, border-color 0.2s ease; }
.metric-tile:hover { transform: translateY(-3px); border-color: #8B5CF6; box-shadow: 0 12px 25px rgba(139, 92, 246, 0.25); }
.metric-label { color: #A78BFA; font-size: 13px; font-weight: 800; font-family: 'Poppins', sans-serif; text-transform: uppercase; letter-spacing: 1.5px; }
.metric-value { font-family: 'Poppins', sans-serif; font-size: 48px; font-weight: 900; color: #F8FAFC; margin-top: 5px; text-shadow: 0 2px 10px rgba(139, 92, 246, 0.3); }

/* Strain & Chem Cards */
.strain-card { background: linear-gradient(145deg, #1E293B 0%, #0F172A 100%); padding: 35px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.4); margin-top: 20px; margin-bottom: 30px; border: 1px solid rgba(139,92,246,0.15); border-top: 4px solid #8B5CF6; transition: all 0.3s ease; }
.strain-card:hover { border-color: rgba(139,92,246,0.4); box-shadow: 0 15px 35px rgba(0,0,0,0.6); }
.card-header-flow { display: flex; align-items: center; gap: 15px; flex-wrap: wrap; margin-bottom: 15px; }
.strain-title { font-family: 'Poppins', sans-serif; font-weight: 900; font-size: 34px; color: #F8FAFC; text-transform: uppercase; letter-spacing: -1px; text-shadow: 0 2px 8px rgba(0,0,0,0.5); }

/* Gradient Badges */
.badge-sativa { background: linear-gradient(90deg, #10B981, #059669); color: #FFF; padding: 6px 16px; border-radius: 8px; font-weight: 800; font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; font-family: 'Poppins', sans-serif; box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3); }
.badge-hybrid { background: linear-gradient(90deg, #8B5CF6, #6D28D9); color: #FFF; padding: 6px 16px; border-radius: 8px; font-weight: 800; font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; font-family: 'Poppins', sans-serif; box-shadow: 0 4px 10px rgba(139, 92, 246, 0.3); }
.badge-indica { background: linear-gradient(90deg, #3B82F6, #2563EB); color: #FFF; padding: 6px 16px; border-radius: 8px; font-weight: 800; font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; font-family: 'Poppins', sans-serif; box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3); }

/* Text & Typography Formatting */
.section-head { color: #A78BFA; font-weight: 800; text-transform: uppercase; font-size: 13px; margin-top: 24px; letter-spacing: 1.5px; font-family: 'Poppins', sans-serif; }
.section-data { font-size: 16px; color: #E5E7EB; margin-top: 6px; line-height: 1.6; font-weight: 400; }

/* Interactive Elements */
.stDownloadButton button { background: linear-gradient(90deg, #8B5CF6 0%, #6D28D9 100%) !important; color: #F8FAFC !important; font-family: 'Poppins', sans-serif; font-weight: 900; border: none !important; border-radius: 10px !important; padding: 16px !important; width: 100%; letter-spacing: 1.5px; text-transform: uppercase; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4); }
.stDownloadButton button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(139, 92, 246, 0.6); }

[data-testid='stDataFrame'] { border: 1px solid rgba(139, 92, 246, 0.2); border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
div[data-testid="stSlider"] label { color: #A78BFA !important; font-family: 'Poppins', sans-serif; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; }

/* Dark Mode Input Overrides */
div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div, div[data-baseweb="select"] > div { background-color: #1E293B !important; border: 1px solid rgba(139, 92, 246, 0.3) !important; border-radius: 8px !important; }
div[data-baseweb="input"] > div:focus-within, div[data-baseweb="textarea"] > div:focus-within { border-color: #8B5CF6 !important; box-shadow: 0 0 0 1px #8B5CF6 !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

logo_path, logo_html = 'image.png', ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_html = f'<img src="data:image/png;base64,{base64.b64encode(img_file.read()).decode("utf-8")}" style="height: 196px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f'<div class="brand-banner" style="padding: 50px 35px;">{logo_html}<div class="brand-text"><h1>Ziggyz Strain Sniffer & Hub</h1><p>Inventory Logistics & Base Knowledge Management Engine</p></div></div>', unsafe_allow_html=True)
tab1, tab2 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE"])

with tab1:
    st.markdown("### 📥 Live Restock Gap Analyzer")
    
    col_file, col_slider = st.columns([3, 2])
    with col_file:
        uploaded_file = st.file_uploader("Select Salesfloor & Curbside + any Category🔥Export Product, Room, & Quantity ONLY🔥Drop Dutchie CSV Export Here", type="csv", key="dutchie_uploader")
    with col_slider:
        min_threshold = st.slider("Adjust Minimum Backstock Target Threshold:", min_value=1, max_value=50, value=15, step=1, help="Adjust this lower (e.g., 5) for high-end concentrates/vapes or higher for top-tier pre-rolls/flower.")
        
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [str(col).strip('="').strip() for col in df.columns]
            qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col][0]
            df['Product'] = df['Product'].apply(lambda x: str(x).strip('="').strip())
            df['Room'] = df['Room'].apply(lambda x: str(x).strip('="').strip())
            df['Qty'] = pd.to_numeric(df[qty_col].apply(lambda x: str(x).strip('="').strip()), errors='coerce').fillna(0)
            
            pivot = df.groupby(['Product', 'Room'])['Qty'].sum().unstack(fill_value=0)
            results = []
            for product, row in pivot.iterrows():
                present, absent = row[row > 0].index.tolist(), row[row == 0].index.tolist()
                if absent and present:
                    for r in present:
                        if row[r] >= min_threshold: 
                            results.append({"Product Name": product, "Location": r, "Available Qty": int(row[r])})
            
            final_df = pd.DataFrame(results)
            if not final_df.empty:
                final_df = final_df.sort_values("Product Name")
                m1, m2, m3 = st.columns(3)
                with m1: st.markdown(f'<div class="metric-tile"><div class="metric-label">High-Impact Gaps</div><div class="metric-value">{len(final_df)}</div></div>', unsafe_allow_html=True)
                with m2: st.markdown(f'<div class="metric-tile"><div class="metric-label">Units to Move</div><div class="metric-value">{final_df["Available Qty"].sum()}</div></div>', unsafe_allow_html=True)
                with m3: st.markdown(f'<div class="metric-tile"><div class="metric-label">Min Threshold</div><div class="metric-value">{min_threshold}+</div></div>', unsafe_allow_html=True)
                st.write("---")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                pdf_data = build_pdf(final_df, min_threshold)
                st.download_button("📥 DOWNLOAD MERCHANDISING PDF", pdf_data, "Ziggy_Report.pdf", "application/pdf")
            else:
                st.info(f"No gaps found matching the {min_threshold}+ unit threshold.")
        except Exception as e: st.error(f"Analysis Error: {e}")

with tab2:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    if "GROQ_API_KEY" not in st.secrets:
        st.error("🔒 Security Alert: GROQ_API_KEY missing from Streamlit secrets vault.")
    else:
        col_input, col_link = st.columns([3, 2])
        
        with col_input:
            target_strain = st.text_input("Enter Strain Name:", placeholder="e.g., permanent marker, jealousy, local drop...").strip()
            
        with col_link:
            if target_strain:
                google_query = f'"{target_strain}" strain genetics lineage terpenes effects site:leafly.com OR site:seedfinder.eu OR site:allbud.com OR site:hytiva.com'
                google_url = f"https://www.google.com/search?q={quote_plus(google_query)}"
                st.markdown(f'<div style="margin-top:28px;"><a href="{google_url}" target="_blank" style="background: linear-gradient(90deg, #8B5CF6, #6D28D9); color: #F8FAFC; padding:10px 16px; border-radius:8px; font-weight:800; font-family: \'Poppins\', sans-serif; text-transform: uppercase; text-decoration:none; display:inline-block; box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4); transition: transform 0.2s;">⚡ OPEN GOOGLE FOR {target_strain.upper()}</a></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="margin-top:35px; color:#64748B; font-style:italic;">Enter a strain name to generate an instant Google link.</div>', unsafe_allow_html=True)

        if target_strain:
            st.write("---")
            st.markdown(f"### 📥 Step 2: Paste Google Snippets for **{target_strain.upper()}**")
            pasted_info = st.text_area("Right-click copy the top search summaries, description paragraphs, or profile pages, then paste them here:", height=130, placeholder="Paste whatever text you find on Google here... Llama will instantly strip out the clutter and clean it up.")
            
            if pasted_info.strip():
                with st.spinner("Extracting molecular details and compiling genetic layout..."):
                    data = parse_pasted_context(st.secrets["GROQ_API_KEY"], target_strain, pasted_info)
                    if "error" not in data:
                        clf = str(data.get('classification', 'HYBRID')).upper()
                        badge_class = "badge-hybrid"
                        if "SATIVA" in clf: badge_class = "badge-sativa"
                        elif "INDICA" in clf: badge_class = "badge-indica"
                        
                        card_html = f"""<div class="strain-card">
<div class="card-header-flow">
<div class="strain-title">✨ {target_strain.upper()}</div>
<span class="{badge_class}">{clf}</span>
</div>
<hr style="border: 0; border-top: 1px solid rgba(139, 92, 246, 0.2); margin-bottom: 15px;">
<div class="section-head">🌿 Genetic Lineage</div><div class="section-data">{data.get('lineage', 'N/A')}</div>
<div class="section-head">🧪 Dominant Terpenes</div><div class="section-data">{data.get('terpenes', 'N/A')}</div>
<div class="section-head">🍋 Flavor Profile</div><div class="section-data">{data.get('flavor', 'N/A')}</div>
<div class="section-head">🧠 Reported Consumer Effects</div><div class="section-data">{data.get('effects', 'N/A')}</div>
</div>"""
                        st.markdown(card_html, unsafe_allow_html=True)
                    else: 
                        st.error(f"Engine connection blip. Details: {data['error']}")
        
        st.write("---")
        st.markdown("### 🧪 Cannabinoid & THC Compound Encyclopedia")
        st.caption("Instant verification engine for compound behaviors, intoxication status, and consumer sales talking points.")
        
        col_select, col_custom = st.columns([2, 2])
        with col_select:
            selected_chem = st.selectbox(
                "Quick Select Target Compound",
                ["-- Choose a Compound --", "THC (Delta-9 Tetrahydrocannabinol)", "THCV (Tetrahydrocannabivarin)", "THCP (Tetrahydrocannabiphorol)", "CBD (Cannabidiol)", "CBG (Cannabigerol)", "CBN (Cannabinol)", "Delta-8 THC"],
                index=0
            )
        with col_custom:
            custom_chem = st.text_input("Or Type a Specific Compound Variant", placeholder="e.g., THCO, CBDA, CBC...").strip()
            
        target_chem = custom_chem if custom_chem else (None if selected_chem == "-- Choose a Compound --" else selected_chem)
        
        if target_chem:
            with st.spinner(f"Querying molecular database for '{target_chem}'..."):
                chem_data = get_compound_profile(st.secrets["GROQ_API_KEY"], target_chem)
                if "error" not in chem_data:
                    status_val = str(chem_data.get('status', 'N/A')).upper()
                    
                    chem_card_html = f"""<div class="strain-card" style="border-top: 4px solid #3B82F6;">
<div class="card-header-flow">
<div class="strain-title">🔬 {target_chem.upper()}</div>
<span class="badge-indica">{status_val}</span>
</div>
<hr style="border: 0; border-top: 1px solid rgba(139, 92, 246, 0.2); margin-bottom: 15px;">
<div class="section-head">🧠 Primary Psychoactive & Physical Effects</div><div class="section-data">{chem_data.get('primary_effects', 'N/A')}</div>
<div class="section-head">🩺 Reported Medicinal & Therapeutic Benefits</div><div class="section-data">{chem_data.get('medical_benefits', 'N/A')}</div>
<div class="section-head">🎯 The Budtender Pitch (How to sell it to customers)</div><div class="section-data" style="color: #A78BFA; font-style: italic;">"{chem_data.get('customer_pitch', 'N/A')}"</div>
</div>"""
                    st.markdown(chem_card_html, unsafe_allow_html=True)
                else: st.error(f"Engine connection blip. Details: {chem_data['error']}")
