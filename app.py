import streamlit as st
import pandas as pd
import base64
import os
from weasyprint import HTML

# Set up premium look with wide configuration
st.set_page_config(page_title="Smilez Inventory Hub", page_icon="⚡", layout="wide")

# High-end Custom CSS for a flashy, professional dark-accented retail look
st.markdown("""
    <style>
    /* Main Background adjustments */
    .stApp { background-color: #fafbfc; }
    
    /* Premium Header Card */
    .brand-banner {
        background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
        color: #ffffff;
        padding: 30px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        display: flex;
        align-items: center;
        margin-bottom: 30px;
    }
    .brand-text h1 {
        color: #fdd835 !important;
        margin: 0;
        font-size: 32px;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .brand-text p {
        margin: 5px 0 0 0;
        opacity: 0.8;
        font-size: 14px;
    }
    
    /* Glassmorphism Metric Cards */
    .metric-card {
        background: white;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02), 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #edf2f7;
        border-top: 5px solid #fdd835;
        text-align: center;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 15px rgba(0,0,0,0.05);
    }
    .metric-val {
        font-size: 36px;
        font-weight: 800;
        color: #1a1a1a;
        margin-top: 5px;
    }
    .metric-label {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #718096;
        font-weight: 700;
    }
    
    /* Clean button layout overrides */
    .stDownloadButton button {
        background: linear-gradient(135deg, #fdd835 0%, #fbc02d 100%) !important;
        color: #1a1a1a !important;
        font-weight: 700 !important;
        border: none !important;
        padding: 12px 28px !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 12px rgba(253, 216, 53, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    .stDownloadButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(253, 216, 53, 0.5) !important;
    }
    </style>
""", unsafe_allow_html=True)

# Define path for logo file
logo_path = 'image.png'
logo_base64 = ""
logo_html = ""

if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="height: 70px; margin-right: 25px; border-radius: 6px;">'

# Dynamic Top Branded Banner View
st.markdown(f"""
    <div class="brand-banner">
        {logo_html}
        <div class="brand-text">
            <h1>SMILEZ INVENTORY HUB</h1>
            <p>In Dutchie backend select both Curbside and Salesfloor rooms and any category • Export only Product, Room, and Quantity</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# Dropzone layout element
st.markdown("###  Load Live Inventory Export")
uploaded_file = st.file_uploader("", type="csv")

def clean_val(val):
    if isinstance(val, str):
        return val.strip('="').strip()
    return val

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Strip header quote formatting elements common in POS formats
        df.columns = [str(col).strip('="').strip() for col in df.columns]
        qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col]
        
        if 'Product' not in df.columns or 'Room' not in df.columns or not qty_col:
            st.error(f"Columns structural mismatch. Found: {list(df.columns)}")
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
                        results.append({
                            'Product Name': product,
                            'Available In': p_room,
                            'Current Qty': int(qty)
                        })
                        
        final_df = pd.DataFrame(results).sort_values(by='Product Name', ascending=True)
        
        if not final_df.empty:
            st.markdown("###  Store Floor Performance Metrics")
            
            # Stylized Metric Row layout 
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                st.markdown(f'<div class="metric-card"><div class="metric-label">High-Impact Gaps</div><div class="metric-val">{len(final_df)}</div></div>', unsafe_allow_html=True)
            with m_col2:
                st.markdown(f'<div class="metric-card"><div class="metric-label">Total Units Missing From Floor</div><div class="metric-val">{final_df["Current Qty"].sum():,}</div></div>', unsafe_allow_html=True)
            with m_col3:
                st.markdown(f'<div class="metric-card"><div class="metric-label">Floor Restock Target</div><div class="metric-val">≥ 15 Units</div></div>', unsafe_allow_html=True)
            
            st.write(" ")
            st.markdown("###  Merchandising Priority Action List")
            
            # Interactive structured presentation table
            st.dataframe(
                final_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Current Qty": st.column_config.NumberColumn("Current Available Stock Volume", format="%d 🔥"),
                    "Available In": st.column_config.TextColumn("Room Location holding Stock")
                }
            )
            
            # Formulating Premium Branded PDF layout structure
            pdf_logo_src = f'data:image/png;base64,{logo_base64}' if logo_base64 else ""
            pdf_logo_tag = f'<img src="{pdf_logo_src}" style="height: 60px; margin-right: 25px; border-radius: 4px;">' if pdf_logo_src else ""
            
            html_content = f"""
            <html>
            <head>
                <style>
                    @page {{ size: A4; margin: 18mm 15mm; }}
                    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #2c3e50; }}
                    .header-bar {{ background-color: #fdd835; color: #1a1a1a; padding: 25px; border-radius: 6px; display: flex; align-items: center; }}
                    h1 {{ margin: 0; font-size: 24pt; font-weight: bold; letter-spacing: -1px; }}
                    .meta-info {{ opacity: 0.85; font-size: 10.5pt; margin-top: 4px; font-weight: 500; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 25px; }}
                    th {{ background-color: #f8fafc; text-align: left; padding: 12px 10px; font-size: 9.5pt; text-transform: uppercase; letter-spacing: 0.5px; color: #4a5568; border-bottom: 3px solid #e2e8f0; }}
                    td {{ padding: 12px 10px; font-size: 10pt; border-bottom: 1px solid #edf2f7; }}
                    .badge {{ background-color: #fff9c4; color: #fbc02d; padding: 3px 10px; border-radius: 12px; font-weight: bold; font-size: 8.5pt; }}
                </style>
            </head>
            <body>
                <div class="header-bar">
                    {pdf_logo_tag}
                    <div>
                        <h1>SMILEZ INVENTORY STOCK GAP REPORT</h1>
                        <div class="meta-info">High-Volume Merchandising Matrix  |  Target Threshold: Qty &ge; 15</div>
                    </div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 55%;">Product Name</th>
                            <th style="width: 25%;">Available In Location</th>
                            <th style="width: 20%; text-align:right;">Current Available Qty</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for _, row in final_df.iterrows():
                html_content += f"""
                        <tr>
                            <td style="font-weight: 500; color: #1a1a1a;">{row['Product Name']}</td>
                            <td><span class="badge">{row['Available In']}</span></td>
                            <td style="text-align:right; font-weight:bold; color: #1a1a1a; font-size: 10.5pt;">{row['Current Qty']:,}</td>
                        </tr>
                """
            html_content += "</tbody></table></body></html>"
            
            pdf_bytes = HTML(string=html_content).write_pdf()
            
            st.markdown("<div style='text-align: right; margin-top: 15px;'>", unsafe_allow_html=True)
            st.download_button(
                label="📥 Export High-Impact Floor Report (PDF)",
                data=pdf_bytes,
                file_name="Smilez_High_Impact_Gap_Report.pdf",
                mime="application/pdf"
            )
            st.markdown("</div>", unsafe_allow_html=True)
            
        else:
            st.info("Excellent! No major stock room gaps identified matching the 15+ unit threshold.")
            
    except Exception as e:
        st.error(f"System parsing delay: {e}")
