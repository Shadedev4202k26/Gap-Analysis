import streamlit as st
import pandas as pd
import base64
import os
from weasyprint import HTML

# Set up page configurations
st.set_page_config(page_title="Inventory Gap Analysis", page_icon="📊", layout="wide")

# Custom CSS styling for a professional dashboard look
st.markdown("""
    <style>
    .main-header { font-size: 28px; font-weight: bold; color: #1a1a1a; margin-bottom: 20px; }
    .metric-box { background-color: #f8fafc; padding: 15px; border-radius: 8px; border-left: 5px solid #fdd835; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Inventory Stock Gap Analysis")
st.write("Upload your raw POS inventory CSV to generate an alphabetical merchandising report for high-impact gaps (Qty ≥ 15).")

# File Uploader
uploaded_file = st.file_uploader("Choose an Inventory CSV file", type="csv")

def clean_val(val):
    if isinstance(val, str):
        return val.strip('="').strip()
    return val

if uploaded_file is not None:
    try:
        # Read raw content to fix encoding or header spacing bugs
        df = pd.read_csv(uploaded_file)
        
        # Clean column names to strip any hidden quotes or formatting from the POS export
        df.columns = [str(col).strip('="').strip() for col in df.columns]
        
        # Map columns flexibly in case of slight naming variations
        qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col]
        
        if 'Product' not in df.columns or 'Room' not in df.columns or not qty_col:
            st.error(f"Columns found: {list(df.columns)}. Expected 'Product', 'Room', and a Quantity column.")
            st.stop()
            
        qty_column_name = qty_col[0]

        # Clean POS formatting artifacts from the cells
        df['Product'] = df['Product'].apply(clean_val)
        df['Room'] = df['Room'].apply(clean_val)
        df['Quantity_Cleaned'] = df[qty_column_name].apply(clean_val)
        df['Quantity_Cleaned'] = pd.to_numeric(df['Quantity_Cleaned'], errors='coerce').fillna(0)
        
        # Consolidate quantities per product per room
        consolidated = df.groupby(['Product', 'Room'])['Quantity_Cleaned'].sum().reset_index()
        pivot_df = consolidated.pivot(index='Product', columns='Room', values='Quantity_Cleaned').fillna(0)
        
        # Identify Gaps with Qty >= 15
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
            # Display Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"<div class='metric-box'><b>High-Impact Gaps Found</b><br><span style='font-size:24px; color:#d4a017;'>{len(final_df)} Products</span></div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div class='metric-box'><b>Total Missing Units</b><br><span style='font-size:24px; color:#d4a017;'>{final_df['Current Qty'].sum()} Units</span></div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div class='metric-box'><b>Minimum Threshold</b><br><span style='font-size:24px; color:#718096;'>15 Units</span></div>", unsafe_allow_html=True)
            
            st.write("---")
            
            # Interactive Data Table View
            st.subheader("📋 Actionable Merchandising List")
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            
            # PDF Generation Layout (HTML/CSS)
            html_content = f"""
            <html>
            <head>
                <style>
                    @page {{ size: A4; margin: 15mm 12mm; }}
                    body {{ font-family: 'Helvetica', Arial, sans-serif; color: #2c3e50; }}
                    .header-bar {{ background-color: #fdd835; color: #1a1a1a; padding: 20px; border-radius: 4px; }}
                    h1 {{ margin: 0; font-size: 20pt; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                    th {{ background-color: #f8fafc; text-align: left; padding: 10px; font-size: 10pt; border-bottom: 2px solid #e2e8f0; }}
                    td {{ padding: 10px; font-size: 9.5pt; border-bottom: 1px solid #edf2f7; }}
                    .badge {{ background-color: #fff9c4; color: #fbc02d; padding: 2px 8px; border-radius: 12px; font-weight: bold; font-size: 8.5pt; }}
                </style>
            </head>
            <body>
                <div class="header-bar">
                    <h1>Inventory Stock Gap Analysis</h1>
                    <p>Alphabetical Merchandising Report | Filtered: Qty &ge; 15</p>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Product Name</th>
                            <th>Available In</th>
                            <th style="text-align:right;">Current Qty</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for _, row in final_df.iterrows():
                html_content += f"""
                        <tr>
                            <td>{row['Product Name']}</td>
                            <td><span class="badge">{row['Available In']}</span></td>
                            <td style="text-align:right; font-weight:bold;">{row['Current Qty']}</td>
                        </tr>
                """
            html_content += "</tbody></table></body></html>"
            
            # Generate PDF to binary memory
            pdf_bytes = HTML(string=html_content).write_pdf()
            
            # Streamlit Download Button
            st.write("---")
            st.download_button(
                label="📥 Download Branded PDF Report",
                data=pdf_bytes,
                file_name="Inventory_Gap_Analysis_Report.pdf",
                mime="application/pdf"
            )
            
        else:
            st.info("No stock gaps identified matching a threshold of 15 or more units.")
            
    except Exception as e:
        st.error(f"Error processing inventory file: {e}")
