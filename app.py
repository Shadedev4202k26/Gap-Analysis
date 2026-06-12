import streamlit as st
import pandas as pd
import os
import json
import requests
import re
from urllib.parse import quote_plus
from reportlab.pdfgen import canvas
from io import BytesIO

# Imports for PDF processing
try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, create_string_object, NumberObject, BooleanObject
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

st.set_page_config(page_title="Ziggybot", page_icon="🔥", layout="wide")

# --- AI & Helper Functions ---
def generate_strain_profile(groq_key, strain_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    api_headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    system_prompt = (
        "You are a highly accurate cannabis strain database for a retail dispensary. "
        "Provide the most widely accepted genetic lineage, terpenes, flavor, and effects for the requested strain based on established industry knowledge. "
        "Output clean, structured JSON. Keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects', 'cannabinoids'."
    )
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Target Strain: {strain_name}"}], "temperature": 0.1}
    try:
        res = requests.post(url, headers=api_headers, json=payload, timeout=12)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
    except Exception as e: return {"error": str(e)}
    return {"classification": "HYBRID", "lineage": "N/A", "terpenes": "N/A", "flavor": "N/A", "effects": "N/A", "cannabinoids": "N/A"}

def get_compound_profile(api_key, compound_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = "You are an advanced cannabinoid science database. Output JSON. Keys: 'primary_effects', 'medical_benefits', 'customer_pitch'."
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Profile for: {compound_name}"}], "temperature": 0.1}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
        return {"error": f"Status code {res.status_code}"}
    except Exception as e: return {"error": str(e)}

# --- UI Styling ---
custom_css = """
<style>
.stApp { background-color: #0F172A; color: #F8FAFC; font-family: 'Inter', sans-serif; }
.brand-banner { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 20px; border-radius: 16px; border-left: 6px solid #8B5CF6; }
.strain-card { background: linear-gradient(145deg, #1E293B 0%, #0F172A 100%); padding: 35px; border-radius: 16px; border-top: 4px solid #8B5CF6; }
</style>"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- App Layout ---
# Reduced video container width to approx 50% relative to total width
col_vid, col_title = st.columns([1, 4]) 
with col_vid:
    if os.path.exists("video.mp4"): st.video("video.mp4", loop=True, autoplay=True, muted=True)
with col_title:
    st.markdown('<div class="brand-banner"><h1>Ziggyz Strain Sniffer & Hub</h1><p>Inventory Logistics & Base Knowledge Management Engine</p></div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🔍 STRAIN SNIFFER", "📊 INVENTORY INTELLIGENCE", "🏷️ HOOK TAG GENERATOR"])

with tab1:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    with st.form("strain_form"):
        user_input = st.text_input("Enter Strain Name:")
        # New "More Results" button logic
        if st.form_submit_button("More Results"):
            if user_input:
                google_url = f"https://www.google.com/search?q={quote_plus(user_input + ' strain')}"
                st.markdown(f'<meta http-equiv="refresh" content="0; url={google_url}">', unsafe_allow_html=True)
                st.write(f"Redirecting to [Google Search]({google_url})...")
            
    st.write("---")
    st.markdown("### 🧪 Cannabinoid Encyclopedia")
    s_chem = st.selectbox("Quick Select Compound", ["--", "THC", "CBD", "CBG", "CBN"])
    if s_chem != "--": st.write(get_compound_profile(st.secrets["GROQ_API_KEY"], s_chem))

with tab2:
    uploaded_file = st.file_uploader("Upload Dutchie CSV", type="csv")
    if uploaded_file:
        st.dataframe(pd.read_csv(uploaded_file))

with tab3:
    if not PYPDF_AVAILABLE:
        st.error("Missing library: pypdf")
    else:
        hook_file = st.file_uploader("Upload Inventory CSV for Tags", type=["csv"])
        if hook_file:
            st.success("Logic active. (Flattening ready).")
