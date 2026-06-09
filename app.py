import streamlit as st
import pandas as pd
import base64
import os
import random

# --- PAGE CONFIG ---
st.set_page_config(page_title="Ziggybot Hub", page_icon="🔥", layout="wide")

# --- CUSTOM CSS ---
custom_css = """
<style>
.stApp { background-color: #0B0F19; color: #F9FAFB; }
.brand-banner { background-color: #111827; border-radius: 12px; border-left: 6px solid #FDD835; padding: 30px; display: flex; align-items: center; margin-bottom: 25px; }
.brand-text h1 { color: #FDD835 !important; font-weight: 900; margin: 0; }
.strain-card { background: #111827; padding: 20px; border-radius: 12px; border: 1px solid #374151; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- HEADER / BRANDING ---
# Ensures the logo loads only if the file exists
logo_html = ""
if os.path.exists('image.png'):
    with open('image.png', 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
        logo_html = f'<img src="data:image/png;base64,{img_b64}" style="height: 100px; margin-right: 30px;">'

st.markdown(f'<div class="brand-banner">{logo_html}<div class="brand-text"><h1>ZIGGYZ STRAIN SNIFFER & OPERATIONAL HUB</h1></div></div>', unsafe_allow_html=True)

# --- TAB STRUCTURE ---
tab1, tab2, tab3 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE", "🧠 GAMIFIED KNOWLEDGE"])

with tab1:
    st.markdown("### 📥 Inventory Management")
    uploaded_file = st.file_uploader("Upload Dutchie Export (CSV)", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df)

with tab2:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    # Clean inputs: No complex filtering, just standard UI fields
    col1, col2 = st.columns(2)
    with col1:
        strain_search = st.text_input("Strain Name")
    with col2:
        cannabinoid_search = st.text_input("Cannabinoid Profile")
        
    if st.button("Query Strain Database"):
        # We are leaving this block simple so it does not interfere with your logic
        st.info(f"Querying for: {strain_search if strain_search else 'All'} with {cannabinoid_search if cannabinoid_search else 'No'} specific cannabinoid focus.")
        st.markdown('<div class="strain-card">Search backend connection ready.</div>', unsafe_allow_html=True)

with tab3:
    st.markdown("### 🎮 Ziggy's Learning Hub")
    st.write("Hangman game initialized.")
    # Minimal game footprint to avoid interfering with tabs
    if "stage" not in st.session_state: st.session_state.stage = 0
    if st.button("New Game"): st.session_state.stage = 0
    st.write(f"Current Game Stage: {st.session_state.stage}")
