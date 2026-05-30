import streamlit as st, pandas as pd, base64, os, json, requests
from weasyprint import HTML

st.set_page_config(page_title="Ziggybot", page_icon="🔥", layout="wide")

def get_strain_profile(api_key, strain_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = "You are an expert cannabis database. Analyze the strain and return ONLY a valid JSON object. CRITICAL: Do not use double quotes inside text values. The JSON must contain exactly these keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects'."
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Provide data for: {strain_name}"}], "temperature": 0.1}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
        return {"error": f"Status code {res.status_code}"}
    except Exception as e: return {"error": str(e)}

# Condensed into a single-line string literal to eliminate text truncation syntax errors
custom_css = "<style>@import url('https://fonts.googleapis.com/css2?family=Urbanist:wght=700;900&family=DM+Sans:wght=400;700&display=swap'); .stApp { background-color: #0B0F19; color: #F9FAFB; font-family: 'DM Sans', sans-serif; } .brand-banner { background-color: #111827; border-radius: 12px; border-left: 6px solid #FDD835; margin-bottom: 25px; display: flex; align-items: center; box-shadow: 0 4px 20px rgba(0,0,0,0.4); } .brand-text h1 { font-family: 'Urbanist', sans-serif; font-weight: 900; color: #FDD835 !important; font-size: 40px; margin: 0; letter-spacing: -1px; text-transform: uppercase; } .brand-text p { color: #94A3B8; margin: 3px 0 0 0; font-size: 15px; letter-spacing: 0.5px; } .stTabs [data-baseweb='tab-list'] { gap: 8px; } .stTabs [data-baseweb='tab'] { height: 55px; background-color: #1F2937 !important; border-radius: 8px 8px 0 0 !important; padding: 10px 20px !important; color: #94A3B8 !important; font-family: 'Urbanist', sans-serif; font-weight: 700; border: none !important; } .stTabs [aria-selected='true'] { background-color: #FDD835 !important; color: #0B0F19 !important; } .metric-tile { background-color: #111827; padding: 25px; border-radius: 12px; border: 1px solid rgba(253, 216, 53, 0.15); text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.2); } .metric-label { color: #FDD835; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; } .metric-value { font-family: 'Urbanist', sans-serif; font-size: 44px; font-weight: 900; color: #F9FAFB; margin-top: 5px; } .strain-card { background-color: #111827; padding: 35px; border-radius: 12px; border-top: 4px solid #FDD835; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-top: 15px; } .card-header-flow { display: flex; align-items: center; gap: 15px; flex-wrap: wrap; margin-bottom: 15px; } .strain-title { font-family: 'Urbanist', sans-serif; font-weight: 900; font-size: 32px; color: #FDD835; text-transform: uppercase; letter-spacing: -0.5px; } .badge-sativa { background: #10B981; color: #FFF; padding: 5px 14px; border-radius: 6px; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; } .badge-hybrid { background: #FDD835; color: #0B0F19; padding: 5px 14px; border-radius: 6px; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; } .badge-indica { background: #6366F1; color: #FFF; padding: 5px 14px; border-radius: 6px; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; } .section-head { color: #64748B; font-weight: 700; text-transform: uppercase; font-size: 12px; margin-top: 20px; letter-spacing: 1px; } .section-data { font-size: 17px; color: #E2E8F0; margin-top: 4px; line-height: 1.5; } .stDownloadButton button { background-color: #FDD835 !important; color: #0B0F19 !important; font-family: 'Urbanist', sans-serif; font-weight: 900; border: none !important; border-radius: 8px !important; padding: 14px !important; width: 100%; letter-spacing: 1px; } [data-testid='stDataFrame'] { border: 1px solid rgba(253, 216, 53, 0.1); border-radius: 8px; }</style>"
st.markdown(custom_css, unsafe_allow_html=True)

logo_path, logo_html = 'image.png', ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_html = f'<img src="data:image/png;base64,{base64.b64encode(img_file.read()).decode("utf-8")}" style="height: 196px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f'<div class="brand-banner" style="padding: 50px 35px;">{logo_html}<div class="brand-text"><h1>Ziggyz Operational Hub</h1><p>Inventory Logistics & Base Knowledge Management Engine</p></div></div>', unsafe_allow_html=True)
tab1, tab2 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE"])

with tab1:
    st.markdown("### 📥 Live Data Ingestion")
    uploaded_file = st.file_uploader("Select Salesfloor & Curbside + any Category🔥Export Product, Room, & Quantity ONLY🔥Drop Dutchie CSV Export Here", type="csv", key="dutchie_uploader")
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
                        if row[r] >= 15: results.append({"Product Name": product, "Location": r, "Available Qty": int(row[r])})
            
            final_df = pd.DataFrame(results)
            if not final_df.empty:
                final_df = final_df.sort_values("Product Name")
                m1, m2, m3 = st.columns(3)
                with m1: st.markdown(f'<div class="metric-tile"><div class="metric-label">High-Impact Gaps</div><div class="metric-value">{len(final_df)}</div></div>', unsafe_allow_html=True)
                with m2: st.markdown(f'<div class="metric-tile"><div class="metric-label">Units to Move</div><div class="metric-value">{final_df["Available Qty"].sum()}</div></div>', unsafe_allow_html=True)
                with m3: st.markdown(f'<div class="metric-tile"><div class="metric-label">Min Threshold</div><div class="metric-value">15+</div></div>', unsafe_allow_html=True)
                st.write("---")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                # Premium HTML & CSS configuration for the PDF Print Engine
                pdf_html = f"""
                <html>
                <head>
                <style>
                    @page {{ size: A4; margin: 20mm; background-color: #0B0F19; }}
                    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #F9FAFB; background-color: #0B0F19; margin: 0; padding: 0; }}
                    .header {{ border-left: 6px solid #FDD835; padding-left: 15px; margin-bottom: 30px; }}
                    h1 {{ font-size: 28px; color: #FDD835; text-transform: uppercase; margin: 0; font-weight: bold; letter-spacing: -0.5px; }}
                    p {{ color: #94A3B8; font-size: 12px; margin: 5px 0 0 0; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background-color: #111827; border-radius: 8px; overflow: hidden; }}
                    th {{ background-color: #1F2937; color: #FDD835; text-transform: uppercase; font-size: 11px; font-weight: bold; letter-spacing: 1px; padding: 12px; text-align: left; border-bottom: 2px solid rgba(253, 216, 53, 0.15); }}
                    td {{ padding: 12px; color: #E2E8F0; font-size: 13px; border-bottom: 1px solid rgba(148, 163, 184, 0.1); }}
                    tr:nth-child(even) {{ background-color: #161F30; }}
                </style>
                </head>
                <body>
                    <div class="header">
                        <h1>Smilez Merchandise Gap Report</h1>
                        <p>High-Impact Floor Restock & Discrepancy Manifest</p>
                    </div>
                    {final_df.to_html(index=False)}
                </body>
                </html>
                """
                
                pdf_out = HTML(string=pdf_html).write_pdf()
                st.download_button("📥 DOWNLOAD MERCHANDISING PDF", pdf_out, "Smilez_Report.pdf", "application/pdf")
            else:
                st.info("No gaps found matching the 15+ unit threshold.")
        except Exception as e: st.error(f"Analysis Error: {e}")

with tab2:
    st.markdown("### 🔍 Real-Time AI Strain Profiler")
    if "GROQ_API_KEY" not in st.secrets:
        st.error("🔒 Security Alert: GROQ_API_KEY missing from Streamlit secrets vault.")
    else:
        query = st.text_input("AI Search Engine Input", placeholder="Type any strain name...", key="ai_search_box", label_visibility="collapsed").strip()
        if query:
            with st.spinner(f"Analyzing genetic matrices for '{query}'..."):
                data = get_strain_profile(st.secrets["GROQ_API_KEY"], query)
                if "error" not in data:
                    clf = str(data.get('classification', 'HYBRID')).upper()
                    badge_class = "badge-hybrid"
                    if "SATIVA" in clf: badge_class = "badge-sativa"
                    elif "INDICA" in clf: badge_class = "badge-indica"
                    
                    card_html = f"""<div class="strain-card">
<div class="card-header-flow">
<div class="strain-title">✨ {query.upper()}</div>
<span class="{badge_class}">{clf}</span>
</div>
<hr style="border: 0; border-top: 1px solid rgba(253, 216, 53, 0.15); margin-bottom: 15px;">
<div class="section-head">🌿 Genetic Lineage</div><div class="section-data">{data.get('lineage', 'N/A')}</div>
<div class="section-head">🧪 Dominant Terpenes</div><div class="section-data">{data.get('terpenes', 'N/A')}</div>
<div class="section-head">🍋 Flavor Profile</div><div class="section-data">{data.get('flavor', 'N/A')}</div>
<div class="section-head">🧠 Reported Consumer Effects</div><div class="section-data">{data.get('effects', 'N/A')}</div>
</div>"""
                    st.markdown(card_html, unsafe_allow_html=True)
                else: st.error(f"Engine connection blip. Details: {data['error']}")
