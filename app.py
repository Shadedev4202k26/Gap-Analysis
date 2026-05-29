import streamlit as st, pandas as pd, base64, os, json, requests
from weasyprint import HTML

st.set_page_config(page_title="Smilez Operational Hub", page_icon="⚡", layout="wide")

def get_strain_profile(api_key, strain_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = "You are an expert cannabis laboratory database. Analyze the strain and return ONLY a valid JSON object with keys: 'classification', 'lineage', 'cannabinoids', 'terpenes', 'flavor', 'effects'."
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Provide data for: {strain_name}"}], "temperature": 0.1}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
        return {"error": f"Status code {res.status_code}"}
    except Exception as e: return {"error": str(e)}

custom_css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Urbanist:wght@600;700&family=DM+Sans:wght@400;500&display=swap');
.stApp { background-color: #0F172A; color: #F9FAFB; font-family: 'DM Sans', sans-serif; }
.brand-banner { background-color: #111827; padding: 40px; border-radius: 12px; border-left: 6px solid #FDD835; margin-bottom: 30px; display: flex; align-items: center; }
.brand-text h1 { font-family: 'Urbanist', sans-serif; color: #FDD835 !important; font-size: 42px; margin: 0; letter-spacing: -1px; }
.brand-text p { color: #94A3B8; margin: 5px 0 0 0; font-size: 16px; }
.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] { height: 60px; background-color: #1F2937 !important; border-radius: 8px 8px 0 0 !important; padding: 10px 25px !important; color: #94A3B8 !important; font-family: 'Urbanist', sans-serif; font-weight: 600; border: none !important; }
.stTabs [aria-selected="true"] { background-color: #FDD835 !important; color: #0F172A !important; }
.metric-tile { background-color: #1F2937; padding: 30px; border-radius: 12px; border: 1px solid rgba(253, 216, 53, 0.1); text-align: center; }
.metric-label { color: #FDD835; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
.metric-value { font-family: 'Urbanist', sans-serif; font-size: 48px; font-weight: 700; color: #F9FAFB; margin-top: 10px; }
.strain-card { background-color: #1F2937; padding: 35px; border-radius: 15px; border-top: 4px solid #FDD835; box-shadow: 0 10px 30px rgba(0,0,0,0.3); margin-top: 15px; }
.strain-title { font-family: 'Urbanist', sans-serif; font-size: 32px; color: #FDD835; text-transform: uppercase; }
.badge-class { background: #10B981; color: #FFF; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 12px; text-transform: uppercase; }
.section-head { color: #94A3B8; font-weight: 700; text-transform: uppercase; font-size: 13px; margin-top: 20px; }
.section-data { font-size: 18px; color: #F9FAFB; margin-top: 5px; }
.stDownloadButton button { background-color: #FDD835 !important; color: #0F172A !important; font-weight: 700 !important; border: none !important; border-radius: 8px !important; padding: 15px 30px !important; width: 100%; }
[data-testid="stDataFrame"] { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; }
</style>"""
st.markdown(custom_css, unsafe_allow_html=True)

logo_path, logo_html = 'image.png', ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_html = f'<img src="data:image/png;base64,{base64.b64encode(img_file.read()).decode("utf-8")}" style="height: 80px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f'<div class="brand-banner">{logo_html}<div class="brand-text"><h1>SMILEZ OPERATIONAL HUB</h1><p>Intelligence Engine for Inventory Logistics & Knowledge Management</p></div></div>', unsafe_allow_html=True)
tab1, tab2 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE"])

with tab1:
    st.markdown("### 📥 Live Data Ingestion")
    uploaded_file = st.file_uploader("Drop Dutchie CSV Export Here", type="csv", key="dutchie_uploader")
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
                pdf_out = HTML(string=f"<html><body><h2>Smilez Gap Report</h2>{final_df.to_html()}</body></html>").write_pdf()
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
                    card_html = f"""<div class="strain-card">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
<div class="strain-title">✨ {query.upper()}</div>
<span class="badge-class">{data.get('classification', 'HYBRID')}</span>
</div>
<hr style="border: 0; border-top: 1px solid rgba(148, 163, 184, 0.2); margin-bottom: 15px;">
<div class="section-head">🌿 Genetic Lineage</div><div class="section-data">{data.get('lineage', 'N/A')}</div>
<div class="section-head">🧬 Cannabinoid Profile</div><div class="section-data">{data.get('cannabinoids', 'N/A')}</div>
<div class="section-head">🧪 Dominant Terpenes</div><div class="section-data">{data.get('terpenes', 'N/A')}</div>
<div class="section-head">🍋 Flavor Profile</div><div class="section-data">{data.get('flavor', 'N/A')}</div>
<div class="section-head">🧠 Reported Consumer Effects</div><div class="section-data">{data.get('effects', 'N/A')}</div>
</div>"""
                    st.markdown(card_html, unsafe_allow_html=True)
                else: st.error(f"Engine connection blip. Details: {data['error']}")
