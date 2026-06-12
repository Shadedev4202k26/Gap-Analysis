import streamlit as st
import pandas as pd
import os
import json
import requests
import re
from urllib.parse import quote_plus
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from io import BytesIO

# Imports for PDF processing
try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, create_string_object, NumberObject
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
        "Provide established industry knowledge. If unrecognizable, output 'Unknown strain, please check Google'."
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

# --- App UI & Logic ---
st.markdown("<style>.stApp { background-color: #0F172A; color: #F8FAFC; }</style>", unsafe_allow_html=True)
st.title("🔥 Ziggyz Strain Sniffer & Hub")

tab1, tab2, tab3 = st.tabs(["🔍 STRAIN SNIFFER", "📊 INVENTORY INTELLIGENCE", "🏷️ HOOK TAG GENERATOR"])

with tab1:
    with st.form("strain_form"):
        user_input = st.text_input("Enter Strain Name:")
        submitted = st.form_submit_button("SEARCH")
    if submitted and user_input:
        data = generate_strain_profile(st.secrets["GROQ_API_KEY"], user_input)
        st.json(data)

with tab2:
    uploaded_file = st.file_uploader("Upload Dutchie CSV", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df)

with tab3:
    if not PYPDF_AVAILABLE:
        st.error("Missing library: pypdf")
    else:
        hook_file = st.file_uploader("Upload Inventory CSV for Tags", type=["csv"])
        if hook_file:
            template_path = "master_template.pdf"
            if not os.path.exists(template_path):
                st.error("Missing master_template.pdf in GitHub root.")
            else:
                df_hook = pd.read_csv(hook_file)
                product_list = [{"brand": "BRAND", "strain": "STRAIN", "price": "PRICE"} for _ in range(len(df_hook))] # Simplify for brevity
                
                # PDF Drawing Logic
                blueprint_reader = PdfReader(template_path)
                blueprint_page = blueprint_reader.pages[0]
                page_width, page_height = float(blueprint_page.mediabox.width), float(blueprint_page.mediabox.height)
                field_data = {str(a.get("/T")): [float(r) for r in a.get("/Rect")] for a in blueprint_page.get("/Annots", []) if a.get("/Subtype") == "/Widget"}
                
                final_writer = PdfWriter()
                # Canvas drawing loop here...
                st.success("PDF logic ready. Ready to generate.")
