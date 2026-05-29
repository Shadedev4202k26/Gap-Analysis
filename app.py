import streamlit as st
import pandas as pd
import base64
import os
import json
import requests
from weasyprint import HTML

# Set up Page Config
st.set_page_config(page_title="Smilez Operational Hub", page_icon="⚡", layout="wide")

# ==========================================
# BACKEND AI ENGINE (Isolated Helper Function)
# ==========================================
def get_strain_profile(api_key, strain_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "You are an expert commercial cannabis laboratory database. "
        "Analyze the strain requested and return ONLY a valid JSON object. "
        "Do not include introductory text or conversational prose. "
        "The JSON must contain exactly these keys: "
        "'classification', 'lineage', 'cannabinoids', 'terpenes', 'flavor', 'effects'."
    )
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Provide data for: {strain_name}"}
        ],
        "temperature": 0.1
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content:
                content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
        else:
            return {"error": f"Status code {res.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# 1. PREMIUM INJECTED DESIGN UI
# ==========================================
custom_css = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Urbanist:wght=600;700&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">

<style>
/* Global Styles */
.stApp { background-color: #0F172A; color: #F9FAFB; }
body, p, span, div { font-family: 'DM Sans', sans-serif; }

/* Header Banner */
.brand-banner {
    background-color: #111827;
    padding: 40px;
    border-radius: 12px;
    border-left: 6px solid #FDD835;
    margin-bottom: 30px;
    display: flex;
    align-items: center;
}
.brand-text h1 {
    font-family: 'Urbanist', sans-serif;
    color: #FDD835 !important;
    font-size: 42px;
    margin: 0;
    letter-spacing: -1px;
}
.brand-text p { color: #94A3B8; margin: 5px 0 0 0; font-size: 16px; }

/* Tab Styling */
.stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; }
.stTabs [data-baseweb="tab"] {
    height: 60px;
    background-color: #1F2937 !important;
    border-radius: 8px 8px 0px 0px !important;
    padding: 10px 25px !important;
    color: #94A3B8 !important;
    font-family: 'Urbanist', sans-serif;
    font-weight: 600;
    border: none !important;
}
.stTabs [aria-selected="true"] { background-color: #FDD835 !important; color: #0F172A !important; }

/* Metric Tiles */
.metric-tile { background-color: #1F2937; padding: 30px; border-radius: 12px; border: 1px solid rgba(253, 216, 53, 0.1); text-align: center; }
.metric-label { color: #FDD835; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
.metric-value { font-family: 'Urbanist', sans-serif; font-size: 48px; font-weight: 700; color: #F9FAFB; margin-top: 10px; }

/* Strain Card */
.strain-card {
    background-color: #1F2937;
    padding: 35px;
    border-radius: 15px;
    border-top: 4px solid #FDD835;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    margin-top: 15px;
}
.strain-title { font-family: 'Urbanist', sans-serif; font-size: 32px; color: #FDD835; margin-bottom: 5px; text-transform: uppercase; }

.badge-class { background: #10B981; color: #FFF; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 12px; text-transform: uppercase; }
.section-head { color: #94A3B8; font-weight: 700; text-transform: uppercase; font-size: 13px; margin-top: 20px; }
.section-data { font-size: 18px; color: #F9FAFB; margin-top: 5px; }

.stDownloadButton button {
    background-color: #FDD835 !important;
    color: #0F172A !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 15px 30px !important;
    width: 100%;
}
[data-testid="stDataFrame"] { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# 2. BRAND LOGO HANDLER
# ==========================================
logo_path = 'image.png'
logo_html = ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="height: 80px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f"""
    <div class="brand-banner">
        {logo_html}
        <div class="brand-text">
            <h1>SMILEZ OPERATIONAL HUB</h1>
            <p>Intelligence Engine for Inventory Logistics & Knowledge Management</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# 3. INTERFACE TABS
# ==========================================
tab1, tab2 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE"])

# --- TAB 1: LOGISTICS MATCHING ENGINE ---
with tab1:
    st.markdown("### 📥 Live Data Ingestion")
    uploaded_file = st.file_uploader("Drop Dutchie CSV Export Here", type="csv", key="dutchie_uploader")

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            
            # Clean columns using short, safe statements
            raw_cols = df.columns
            cleaned_cols = [str(col).strip('="').strip() for col in raw_cols]
            df.columns = cleaned_cols
