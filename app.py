import streamlit as st
import pandas as pd
import base64
import os
from weasyprint import HTML

# Set up premium look with wide configuration
st.set_page_config(page_title="Smilez Knowledge Base", page_icon="⚡", layout="wide")

# Custom CSS for a clean, unified retail look
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
    
    /* Interactive Strain Profile Cards */
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
    
    .metric-card {
        background: white; padding: 24px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 5px solid #fdd835; text-align: center;
    }
    .metric-val { font-size: 36px; font-weight: 800; color: #1a1a1a; }
    .metric-label { font-size: 12px; text-transform: uppercase; color: #718096; font-weight: 700; }
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
st.markdown(f'<div class="brand-banner">{logo_html}<div class="brand-text"><h1>SMILEZ RETAIL HUB</h1><p>Store Performance Data & Budtender Knowledge Engine</p></div></div>', unsafe_allow_html=True)

# Navigation Tabs
tab1, tab2 = st.tabs(["📊 Inventory Gap Analysis", "🔍 Budtender Strain Checker"])

# --- TAB 1: INVENTORY GAP ANALYSIS ---
with tab1:
    st.markdown("### 📥 Load Live Inventory Export")
    uploaded_file = st.file_uploader("Drop your Dutchie CSV below:", type="csv", key="inv_uploader")

    def clean_val(val):
        if isinstance(val, str):
            return val.strip('="').strip()
        return val

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [str(col).strip('="').strip() for col in df.columns]
            qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col]
            
            if 'Product' not in df.columns or 'Room' not in df.columns or not qty_col:
                st.error(f"Columns structural mismatch. Found fields: {list(df.columns)}. Expected 'Product', 'Room', and a Quantity column.")
                st.stop()
                
            qty_column_name = qty_col[0]
            df['Product'] = df['Product'].apply(clean_val)
            df['Room'] = df['Room'].apply(clean_val)
            df['Quantity_Cleaned'] = df[qty_column_name].apply(clean_val)
            df['Quantity_Cleaned'] = pd.to_numeric(df['Quantity_Cleaned'], errors='coerce').fillna(0)
            
            consolidated = df.groupby(['Product', 'Room'])['Quantity_Cleaned'].sum().reset_index()
            pivot_df = consolidated.pivot(index='Product', columns='Room', values='Quantity_Cleaned').fillna(0)
            
            results = []
            for product, row in pivot_df.iterrows():
                present_rooms = row[row > 0].index.tolist()
                missing_rooms = row[row == 0].index.tolist()
                if len(missing_rooms) > 0 and len(present_rooms) > 0:
                    for p_room in present_rooms:
                        qty = row[p_room]
                        if qty >= 15:
                            results.append({'Product Name': product, 'Available In': p_room, 'Current Qty': int(qty)})
                            
            final_df = pd.DataFrame(results).sort_values(by='Product Name', ascending=True)
            
            if not final_df.empty:
                m_col1, m_col2, m_col3 = st.columns(3)
                with m_col1:
                    st.markdown(f'<div class="metric-card"><div class="metric-label">High-Impact Gaps</div><div class="metric-val">{len(final_df)}</div></div>', unsafe_allow_html=True)
                with m_col2:
                    st.markdown(f'<div class="metric-card"><div class="metric-label">Total Units Missing</div><div class="metric-val">{final_df["Current Qty"].sum():,}</div></div>', unsafe_allow_html=True)
                with m_col3:
                    st.markdown(f'<div class="metric-card"><div class="metric-label">Target Threshold</div><div class="metric-val">≥ 15 Units</div></div>', unsafe_allow_html=True)
                
                st.write(" ")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                # Setup PDF Generation Data
                html_content = f"""
                <html>
                <head>
                    <style>
                        @page {{ size: A4; margin: 18mm 15mm; }}
                        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #2c3e50; }}
                        .header-bar {{ background-color: #fdd835; color: #1a1a1a; padding: 25px; border-radius: 6px; }}
                        h1 {{ margin: 0; font-size: 22pt; font-weight: bold; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 25px; }}
                        th {{ background-color: #f8fafc; text-align: left; padding: 12px 10px; font-size: 9.5pt; border-bottom: 3px solid #e2e8f0; }}
                        td {{ padding: 12px 10px; font-size: 10pt; border-bottom: 1px solid #edf2f7; }}
                    </style>
                </head>
                <body>
                    <div class="header-bar">
                        <h1>SMILEZ INVENTORY STOCK GAP REPORT</h1>
                    </div>
                    <table>
                        <thead><tr><th>Product Name</th><th>Location</th><th style="text-align:right;">Qty</th></tr></thead>
                        <tbody>
                """
                for _, row in final_df.iterrows():
                    html_content += f"<tr><td>{row['Product Name']}</td><td>{row['Available In']}</td><td style='text-align:right;'>{row['Current Qty']}</td></tr>"
                html_content += "</tbody></table></body></html>"
                
                pdf_bytes = HTML(string=html_content).write_pdf()
                st.download_button(label="📥 Export Floor Report (PDF)", data=pdf_bytes, file_name="Smilez_Gap_Report.pdf", mime="application/pdf")
            else:
                st.info("No major stock room gaps identified matching the 15+ unit threshold.")
        except Exception as e:
            st.error(f"Error parsing file: {e}")

# --- TAB 2: STANDALONE STRAIN CHECKER ---
with tab2:
    st.markdown("### 🔍 Live Strain Profile Lookup")
    st.write("Type a cultivar name below to instantly view category breakdowns, primary terpenes, and target characteristics.")
    
    # Embedded High-Volume Reference Encyclopedia (100% Offline-Safe)
    strain_database = [
        {"name": "Amnesia Haze", "type": "Sativa", "terpenes": "Terpinolene, Myrcene, Caryophyllene", "flavors": "Sharp Citrus, Sweet Lemon, Fresh Earth", "effects": "Energetic, Uplifting, Creative, Mental Clarity"},
        {"name": "Block Berry", "type": "Hybrid", "terpenes": "Limonene, Myrcene, Caryophyllene", "flavors": "Sweet Berry, Crushed Orange, Tart Zest", "effects": "Laser Focused, Intense Euphoria, Relaxed Body"},
        {"name": "Runtz", "type": "Hybrid", "terpenes": "Caryophyllene, Limonene, Linalool", "flavors": "Sugary Sweet, Sugared Candy, Tropical Fruit", "effects": "Talkative, Long-Lasting Happiness, Smooth Body Buzz"},
        {"name": "Wedding Cake", "type": "Indica", "terpenes": "Limonene, Caryophyllene, Myrcene", "flavors": "Rich Vanilla, Sweet Cake Batter, Earthy Pepper", "effects": "Deeply Sedative, Relaxed Muscles, Calming, Appetite Stimulant"},
        {"name": "Gelato", "type": "Hybrid", "terpenes": "Caryophyllene, Limonene, Humulene", "flavors": "Creamy Dessert, Sweet Citrus, Soft Woody Notes", "effects": "Physically Relaxing, Mentally Stimulating, Creative Boost"},
        {"name": "GG4", "type": "Hybrid", "terpenes": "Caryophyllene, Myrcene, Limonene", "flavors": "Heavy Pungent, Piney Wood, Sour Chem", "effects": "Heavy Couchlock, Relaxed Mind, Deep Physical Comfort"},
        {"name": "Blue Dream", "type": "Hybrid", "terpenes": "Myrcene, Pinene, Caryophyllene", "flavors": "Sweet Blueberry, Fresh Berry, Herbal Earth", "effects": "Gentle Uplift, Full-Body Relaxation, Creative Day-Use"},
        {"name": "Sour Diesel", "type": "Sativa", "terpenes": "Caryophyllene, Limonene, Myrcene", "flavors": "Skunky Diesel, Fuel, Sour Citrus", "effects": "Fast Acting, Energizing Dreaminess, Social Uplift"},
        {"name": "Granddaddy Purple", "type": "Indica", "terpenes": "Myrcene, Caryophyllene, Pinene", "flavors": "Sweet Grape, Deep Berry, Floral Musky", "effects": "Deep Body Stone, Sleep Inducing, Stress Melt"}
    ]
    
    # Process into standard lookup list
    df_strains = pd.DataFrame(strain_database)
    df_strains['search_name'] = df_strains['name'].str.lower()
    
    search_query = st.text_input("Start typing a cultivar name (e.g. Block Berry, Runtz, Wedding Cake)...", "").lower().strip()
    
    if search_query:
        # Match using plain pandas syntax without internet requests
        matches = df_strains[df_strains['search_name'].str.contains(search_query, na=False)]
        
        if not matches.empty:
            if len(matches) > 1:
                selected_name = st.selectbox(f"💡 Found {len(matches)} potential profiles. Select your target batch:", matches['name'].values)
                target_data = matches[matches['name'] == selected_name].iloc[0]
            else:
                target_data = matches.iloc[0]
                
            s_name = target_data['name']
            s_type = target_data['type']
            s_terps = target_data['terpenes']
            s_flavors = target_data['flavors']
            s_effects = target_data['effects']
            
            badge_class = "badge-indica" if "indica" in s_type.lower() else ("badge-sativa" if "sativa" in s_type.lower() else "badge-hybrid")
            
            st.markdown(f"""
                <div class="strain-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="margin: 0; font-size: 26px; font-weight: 800; color: #111827;">✨ {s_name}</h2>
                        <span class="{badge_class}">{s_type} Class</span>
                    </div>
                    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-bottom: 20px;">
                    
                    <div class="section-title">🧪 Dominant Terpene Architecture</div>
                    <div class="section-body">{s_terps}</div>
                    
                    <div class="section-title">🍋 Aroma & Flavor Indicators</div>
                    <div class="section-body">{s_flavors}</div>
                    
                    <div class="section-title">🧠 Common Reported Effects</div>
                    <div class="section-body">{s_effects}</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Strain profile matching details not found in local quick-cache. Double check spellings or consult raw certificate of analysis (COA) testing documentation.")
