import streamlit as st
import pandas as pd
import base64
import os
import requests

# Set up premium look with wide configuration
st.set_page_config(page_title="Smilez Knowledge Base", page_icon="🌿", layout="wide")

# Custom CSS for a professional retail look
st.markdown("""
    <style>
    .stApp { background-color: #fafbfc; }
    .brand-banner {
        background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
        color: #ffffff;
        padding: 30px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        margin-bottom: 25px;
    }
    .brand-text h1 { color: #fdd835 !important; margin: 0; font-size: 30px; font-weight: 800; }
    .brand-text p { margin: 5px 0 0 0; opacity: 0.8; font-size: 14px; }
    
    /* Premium Interactive Strain Profile Cards */
    .strain-card {
        background: white;
        padding: 30px;
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.03);
        border: 1px solid #e5e7eb;
        margin-top: 20px;
    }
    .badge-indica { background-color: #f3e8ff; color: #6b21a8; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 13px; display: inline-block; }
    .badge-sativa { background-color: #d1fae5; color: #065f46; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 13px; display: inline-block; }
    .badge-hybrid { background-color: #fef3c7; color: #92400e; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 13px; display: inline-block; }
    
    .section-title { font-size: 14px; font-weight: 700; color: #4b5563; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
    .section-body { font-size: 16px; color: #111827; margin-bottom: 15px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# Load Logo
logo_path = 'image.png'
logo_html = ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="height: 70px; margin-right: 25px; border-radius: 6px;">'

# Top Banner Layout
st.markdown(f'<div class="brand-banner">{logo_html}<div class="brand-text"><h1>SMILEZ RETAIL HUB</h1><p>Budtender Knowledge Base & Terpene Encyclopedia</p></div></div>', unsafe_allow_html=True)

st.markdown("### 🔍 Live Strain Profile Lookup")
st.write("Type any strain or lineage name below to pull genetic classing, major terpene profiles, and consumer markers.")

# Cache the database load so the website stays lightning-fast for floor terminals
@st.cache_data
def load_strain_database():
    # Fetching a clean, crowdsourced comprehensive public index of major global strains
    url = "https://raw.githubusercontent.com/kushyapp/cannabis-dataset/master/data-csv/strains.csv"
    try:
        data = pd.read_csv(url)
        # Keep only the actionable education columns we need to protect memory speeds
        columns_to_keep = ['name', 'type', 'thc', 'cbd', 'terpenes', 'flavors', 'effects']
        data = data[[col for col in columns_to_keep if col in data.columns]]
        data['name_clean'] = data['name'].str.lower().str.strip()
        return data
    except Exception:
        # Robust localized offline fallback database if github network drops
        fallback_data = pd.DataFrame([
            {"name": "Amnesia Haze", "type": "Sativa", "terpenes": "Terpinolene, Myrcene", "flavors": "Citrus, Lemon, Earthy", "effects": "Energetic, Cerebral"},
            {"name": "Block Berry", "type": "Hybrid", "terpenes": "Limonene, Caryophyllene", "flavors": "Sweet Berry, Orange, Tart", "effects": "Focused, Euphoric"},
            {"name": "Runtz", "type": "Hybrid", "terpenes": "Caryophyllene, Limonene", "flavors": "Fruity, Sweet Candy", "effects": "Happy, Relaxed"},
            {"name": "Wedding Cake", "type": "Indica", "terpenes": "Limonene, Myrcene", "flavors": "Vanilla, Sweet Pepper", "effects": "Deeply Relaxed, Calming"},
            {"name": "Gelato", "type": "Hybrid", "terpenes": "Caryophyllene, Linalool", "flavors": "Creamy, Berry, Woody", "effects": "Creative, Relaxed"}
        ])
        fallback_data['name_clean'] = fallback_data['name'].str.lower().str.strip()
        return fallback_data

df_db = load_strain_database()

# User input text field
search_query = st.text_input("Start typing a cultivar name (e.g. Runtz, Kush, Berry)...", "").lower().strip()

if search_query:
    # Use string matching to find any strain names containing the search query
    matched_results = df_db[df_db['name_clean'].str.contains(search_query, na=False)]
    
    if not matched_results.empty:
        # If multiple variations exist, let the budtender click the exact one they are holding
        if len(matched_results) > 1:
            selected_strain = st.selectbox(f"💡 Found {len(matched_results)} variations. Choose exact match:", matched_results['name'].values)
            target_row = matched_results[matched_results['name'] == selected_strain].iloc[0]
        else:
            target_row = matched_results.iloc[0]
            
        # Extract metadata attributes cleanly, providing clear defaults for incomplete entries
        s_name = target_row['name']
        s_type = str(target_row.get('type', 'Hybrid')).capitalize()
        s_terps = str(target_row.get('terpenes', 'Limonene, Myrcene, Caryophyllene (Standard Profile)')).title()
        s_flavors = str(target_row.get('flavors', 'Earthy, Sweet, Citrus')).title()
        s_effects = str(target_row.get('effects', 'Balanced, Creative, Relaxing')).title()
        
        # Format style class dynamically
        badge_style = "badge-indica" if "indica" in s_type.lower() else ("badge-sativa" if "sativa" in s_type.lower() else "badge-hybrid")
        
        # Render the custom designed product info card
        st.markdown(f"""
            <div class="strain-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h2 style="margin: 0; font-size: 28px; font-weight: 800; color: #111827; text-transform: uppercase;">✨ {s_name}</h2>
                    <span class="{badge_style}">{s_type}</span>
                </div>
                <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 20px;">
                
                <div class="section-title">🧪 Dominant Terpene Architecture</div>
                <div class="section-body">{s_terps}</div>
                
                <div class="section-title">🍋 Aroma & Flavor Indicators</div>
                <div class="section-body">{s_flavors}</div>
                
                <div class="section-title">🧠 Reported Consumer Effects</div>
                <div class="section-body">{s_effects}</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No exact matching profile found in the public database index. Check the batch's lab testing sticker (COA) for specific terpene values.")
