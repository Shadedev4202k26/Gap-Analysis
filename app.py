import streamlit as st
import pandas as pd
import base64
import os
from weasyprint import HTML

# Set up Page Config
st.set_page_config(page_title="Smilez Operational Hub", page_icon="⚡", layout="wide")

# 1. PREMIUM CSS INJECTION
st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Urbanist:wght@600;700&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
    
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
        padding: 10px 25px !important;
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
    }
    .metric-label { color: #FDD835; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-family: 'Urbanist', sans-serif; font-size: 48px; font-weight: 700; color: #F9FAFB; margin-top: 10px; }

    /* Strain Reference Card */
    .strain-card {
        background-color: #1F2937;
        padding: 35px;
        border-radius: 15px;
        border-top: 4px solid #FDD835;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        margin-top: 15px;
    }
    .strain-title { font-family: 'Urbanist', sans-serif; font-size: 32px; color: #FDD835; margin-bottom: 10px; text-transform: uppercase; }
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
    uploaded_file = st.file_uploader("Drop Dutchie CSV Export Here", type="csv", key="dutchie_uploader")

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

            if not final_df.empty:
                # Metrics Row
                m1, m2, m3 = st.columns(3)
                with m1: st.markdown(f'<div class="metric-tile"><div class="metric-label">High-Impact Gaps</div><div class="metric-value">{len(final_df)}</div></div>', unsafe_allow_html=True)
                with m2: st.markdown(f'<div class="metric-tile"><div class="metric-label">Units to Move</div><div class="metric-value">{final_df["Available Qty"].sum()}</div></div>', unsafe_allow_html=True)
                with m3: st.markdown(f'<div class="metric-tile"><div class="metric-label">Min Threshold</div><div class="metric-value">15+</div></div>', unsafe_allow_html=True)

                st.write("---")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                # PDF Export
                html_pdf = f"<html><body style='font-family:sans-serif;'><h2>Smilez Gap Report</h2>{final_df.to_html()}</body></html>"
                pdf_out = HTML(string=html_pdf).write_pdf()
                st.download_button("📥 DOWNLOAD MERCHANDISING PDF", pdf_out, "Smilez_Report.pdf", "application/pdf")
            else:
                st.info("No gaps found matching the 15+ unit threshold.")
            
        except Exception as e:
            st.error(f"Analysis Error: {e}")

# --- TAB 2: STRAIN CHECKER ---
with tab2:
    st.markdown("### 🔍 Strain Reference Search")
    
    # Offline Master Dictionary
    db = [
        {"name": "Amnesia Haze", "type": "Sativa", "terps": "Terpinolene, Myrcene, Caryophyllene", "flav": "Sharp Citrus, Sweet Lemon, Fresh Earth", "eff": "Energetic, Uplifting, Creative, Mental Clarity"},
        {"name": "Block Berry", "type": "Hybrid", "terps": "Limonene, Myrcene, Caryophyllene", "flav": "Sweet Berry, Crushed Orange, Tart Zest", "eff": "Laser Focused, Intense Euphoria, Relaxed Body"},
        {"name": "Runtz", "type": "Hybrid", "terps": "Caryophyllene, Limonene, Linalool", "flav": "Sugary Sweet, Sugared Candy, Tropical Fruit", "eff": "Talkative, Long-Lasting Happiness, Smooth Body Buzz"},
        {"name": "Wedding Cake", "type": "Indica", "terps": "Limonene, Caryophyllene, Myrcene", "flav": "Rich Vanilla, Sweet Cake Batter, Earthy Pepper", "eff": "Deeply Sedative, Relaxed Muscles, Calming, Appetite Stimulant"},
        {"name": "Gelato", "type": "Hybrid", "terps": "Caryophyllene, Limonene, Humulene", "flav": "Creamy Dessert, Sweet Citrus, Soft Woody Notes", "eff": "Physically Relaxing, Mentally Stimulating, Creative Boost"},
        {"name": "GG4", "type": "Hybrid", "terps": "Caryophyllene, Myrcene, Limonene", "flav": "Heavy Pungent, Piney Wood, Sour Chem", "eff": "Heavy Couchlock, Relaxed Mind, Deep Physical Comfort"},
        {"name": "Blue Dream", "type": "Hybrid", "terps": "Myrcene, Pinene, Caryophyllene", "flav": "Sweet Blueberry, Fresh Berry, Herbal Earth", "eff": "Gentle Uplift, Full-Body Relaxation, Creative Day-Use"},
        {"name": "Sour Diesel", "type": "Sativa", "terps": "Caryophyllene, Limonene, Myrcene", "flav": "Skunky Diesel, Fuel, Sour Citrus", "eff": "Fast Acting, Energizing Dreaminess, Social Uplift"},
        {"name": "Granddaddy Purple", "type": "Indica", "terps": "Myrcene, Caryophyllene, Pinene", "flav": "Sweet Grape, Deep Berry, Floral Musky", "eff": "Deep Body Stone, Sleep Inducing, Stress Melt"}
    ]
    
    # Text input with distinct styling placeholder
    query = st.text_input("Search Engine Input", placeholder="Type strain name here (e.g. Block Berry, Runtz)...", label_visibility="collapsed").lower().strip()
    
    if query:
        # Correctly cycle through dictionaries and match characters against the 'name' key
        matches = [s for s in db if query in s['name'].lower()]
        
        if matches:
            for s in matches:
                st.markdown(f"""
                    <div class="strain-card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                            <div class="strain-title">✨ {s['name']}</div>
                            <span style="background:#FDD835; color:#0F172A; padding:6px 16px; border-radius:20px; font-weight:700; font-size:13px;">{s['type'].upper()}</span>
                        </div>
                        <hr style="border: 0; border-top: 1px solid rgba(148, 163, 184, 0.2); margin-bottom: 15px;">
                        <div class="section-head">🧪 Dominant Terpenes</div>
                        <div class="section-data">{s['terps']}</div>
                        <div class="section-head">🍋 Flavor Profile</div>
                        <div class="section-data">{s['flav']}</div>
                        <div class="section-head">🧠 Reported Effects</div>
                        <div class="section-data">{s['eff']}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No matching profile found in the quick-cache database.")
