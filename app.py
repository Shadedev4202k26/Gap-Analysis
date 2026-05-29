import streamlit as st
import pandas as pd
import base64
import os
from weasyprint import HTML

# Set up Page Config
st.set_page_config(page_title="Smilez Operational Hub", page_icon="⚡", layout="wide")

# 1. PREMIUM CSS INJECTION (MATCHING THE HUB DESIGN SLIDE)
st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Urbanist:wght@600;700&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
    
    <style>
    /* Global Styles */
    .stApp { background-color: #0F172A; color: #F9FAFB; }
    font-family: 'DM Sans', sans-serif;

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
    .brand-text p {
        color: #94A3B8;
        margin: 5px 0 0 0;
        font-size: 16px;
    }

    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        background-color: #1F2937 !important;
        border-radius: 8px 8px 0px 0px !important;
        gap: 0px;
        padding-top: 10px !important;
        padding-bottom: 10px !important;
        color: #94A3B8 !important;
        font-family: 'Urbanist', sans-serif;
        font-weight: 600;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FDD835 !important;
        color: #0F172A !important;
    }

    /* Metric Tiles */
    .metric-tile {
        background-color: #1F2937;
        padding: 30px;
        border-radius: 12px;
        border: 1px solid rgba(253, 216, 53, 0.1);
        text-align: center;
        transition: transform 0.3s ease;
    }
    .metric-tile:hover { transform: translateY(-5px); border-color: #FDD835; }
    .metric-label { color: #FDD835; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-family: 'Urbanist', sans-serif; font-size: 48px; font-weight: 700; color: #F9FAFB; margin-top: 10px; }

    /* Strain Reference Card */
    .strain-card {
        background-color: #1F2937;
        padding: 35px;
        border-radius: 15px;
        border-top: 4px solid #FDD835;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    .strain-title { font-family: 'Urbanist', sans-serif; font-size: 32px; color: #FDD835; margin-bottom: 10px; }
    .section-head { color: #94A3B8; font-weight: 700; text-transform: uppercase; font-size: 13px; margin-top: 20px; }
    .section-data { font-size: 18px; color: #F9FAFB; margin-top: 5px; }

    /* Buttons */
    .stDownloadButton button {
        background-color: #FDD835 !important;
        color: #0F172A !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 15px 30px !important;
        width: 100%;
    }

    /* Dataframe Overrides */
    [data-testid="stDataFrame"] {
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# 2. LOGO & HEADER LOGIC
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

# 3. THE TWO-TAB NAVIGATION
tab1, tab2 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 KNOWLEDGE BASE"])

# --- TAB 1: INVENTORY GAP ANALYSIS ---
with tab1:
    st.markdown("### 📥 Live Data Ingestion")
    uploaded_file = st.file_uploader("Drop Dutchie CSV Export Here", type="csv", label_visibility="collapsed")

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [str(col).strip('="').strip() for col in df.columns]
            qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col][0]
            
            # Data Cleaning
            df['Product'] = df['Product'].apply(lambda x: str(x).strip('="').strip())
            df['Room'] = df['Room'].apply(lambda x: str(x).strip('="').strip())
            df['Qty'] = pd.to_numeric(df[qty_col].apply(lambda x: str(x).strip('="').strip()), errors='coerce').fillna(0)
            
            # Processing
            pivot = df.groupby(['Product', 'Room'])['Qty'].sum().unstack(fill_value=0)
            results = []
            for product, row in pivot.iterrows():
                present = row[row > 0].index.tolist()
                absent = row[row == 0].index.tolist()
                if absent and present:
                    for r in present:
                        if row[r] >= 15:
                            results.append({"Product Name": product, "Location": r, "Available Qty": int(row[r])})
            
            final_df = pd.DataFrame(results).sort_values("Product Name")

            # Metrics Row
            m1, m2, m3 = st.columns(3)
            with m1: st.markdown(f'<div class="metric-tile"><div class="metric-label">High-Impact Gaps</div><div class="metric-value">{len(final_df)}</div></div>', unsafe_allow_html=True)
            with m2: st.markdown(f'<div class="metric-tile"><div class="metric-label">Units to Move</div><div class="metric-value">{final_df["Available Qty"].sum()}</div></div>', unsafe_allow_html=True)
            with m3: st.markdown(f'<div class="metric-tile"><div class="metric-label">Min Threshold</div><div class="metric-value">15+</div></div>', unsafe_allow_html=True)

            st.write("---")
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            
            # PDF Export (Minimalistic WeasyPrint)
            html_pdf = f"<html><body style='font-family:sans-serif;'><h2>Smilez Gap Report</h2>{final_df.to_html()}</body></html>"
            pdf_out = HTML(string=html_pdf).write_pdf()
            st.download_button("📥 DOWNLOAD MERCHANDISING PDF", pdf_out, "Smilez_Report.pdf", "application/pdf")
            
        except Exception as e:
            st.error(f"Analysis Error: {e}")

# --- TAB 2: STRAIN CHECKER ---
with tab2:
    st.markdown("### 🔍 Strain Reference Search")
    query = st.text_input("Type Cultivar Name (e.g. Block Berry, Runtz)", placeholder="Search Knowledge Base...", label_visibility="collapsed").lower().strip()
    
    # Offline Master Dictionary
    db = [
        {"name": "Amnesia Haze", "type": "Sativa", "terps": "Terpinolene, Myrcene", "flav": "Lemon, Citrus, Earthy", "eff": "Energetic, Cerebral"},
        {"name": "Block Berry", "type": "Hybrid", "terps": "Limonene, Myrcene", "flav": "Sweet Berry, Orange", "eff": "Focused, Euphoric"},
        {"name": "Runtz", "type": "Hybrid", "terps": "Caryophyllene, Limonene", "flav": "Candy, Fruit, Sweet", "eff": "Happy, Talkative"},
        {"name": "Wedding Cake", "type": "Indica", "terps": "Limonene, Caryophyllene", "flav": "Vanilla, Cake, Pepper", "eff": "Relaxed, Calm"}
    ]
    
    if query:
        matches = [s for s in db if query in s['name'].lower()]
        if matches:
            for s in matches:
                st.markdown(f"""
                    <div class="strain-card">
                        <div class="strain-title">✨ {s['name']}</div>
                        <span style="background:#FDD835; color:#0F172A; padding:4px 12px; border-radius:20px; font-weight:700;">{s['type']}</span>
                        <div class="section-head">🧪 Dominant Terpenes</div>
                        <div class="section-data">{s['terps']}</div>
                        <div class="section-head">🍋 Flavor Profile</div>
                        <div class="section-data">{s['flav']}</div>
                        <div class="section-head">🧠 Reported Effects</div>
                        <div class="section-data">{s['eff']}</div>
                    </div><br>
                """, unsafe_allow_html=True)
        else:
            st.info("No exact profile match found in knowledge base.")
