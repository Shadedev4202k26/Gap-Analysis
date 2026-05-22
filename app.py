import streamlit as st
import pandas as pd
import base64
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
        return val.strip('="')
    return val

if uploaded_file is not None:
    try:
        # Load data
        df = pd.read_csv(uploaded_file)
        
        # Clean POS formatting artifacts
        df['Product'] = df['Product'].apply(clean_val)
        df['Room'] = df['Room'].apply(clean_val)
        df['Quantity'] = df['Quantity (including allocated)'].apply(clean_val)
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
        
        # Consolidate quantities per product per room
        consolidated = df.groupby(['Product', 'Room'])['Quantity'].sum().reset_index()
        pivot_df = consolidated.pivot(index='Product', columns='Room', values='Quantity').fillna(0)
        
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
            
            # PDF Generation Logic Setup
            # (WeasyPrint HTML compilation structure goes here to offer download button)
            st.success("Analysis complete! Ready to distribute to the floor team.")
            
        else:
            st.info("No stock gaps identified matching a threshold of 15 or more units.")
            
    except Exception as e:
        st.error(f"Error processing inventory file: {e}. Please verify the CSV format matches standard POS exports.")
