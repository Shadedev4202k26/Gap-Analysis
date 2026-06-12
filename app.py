import streamlit as st
import pandas as pd
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
    PYPDF_AVAILABLE = Trueimport streamlit as st
import pandas as pd
import os  # FIXED: Added this import
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
        "You are a highly accurate cannabis strain database. Output clean, structured JSON. "
        "Keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects', 'cannabinoids'."
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
.stApp { background-color: #0F172A; color: #F8FAFC; }
.brand-banner { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 20px; border-radius: 16px; border-left: 6px solid #8B5CF6; }
.strain-card { background: linear-gradient(145deg, #1E293B 0%, #0F172A 100%); padding: 35px; border-radius: 16px; border-top: 4px solid #8B5CF6; }
</style>"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- App Layout ---
col_banner1, col_banner2 = st.columns([1, 3])
with col_banner1:
    if os.path.exists("video.mp4"): st.video("video.mp4", loop=True, autoplay=True, muted=True)
with col_banner2:
    st.markdown('<div class="brand-banner"><h1>Ziggyz Strain Sniffer & Hub</h1><p>Inventory Logistics & Base Knowledge Management Engine</p></div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🔍 STRAIN SNIFFER", "📊 INVENTORY INTELLIGENCE", "🏷️ HOOK TAG GENERATOR"])

with tab1:
    with st.form("strain_form"):
        user_input = st.text_input("Enter Strain Name:")
        submitted = st.form_submit_button("SEARCH")
    if submitted and user_input:
        data = generate_strain_profile(st.secrets["GROQ_API_KEY"], user_input)
        st.write(data)
    
    st.write("---")
    s_chem = st.selectbox("Quick Select Compound", ["--", "THC", "CBD", "CBG", "CBN"])
    if s_chem != "--": st.write(get_compound_profile(st.secrets["GROQ_API_KEY"], s_chem))

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
                st.success("Logic active. (Use the previously finalized flattening code here).")
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
        "If the strain name is completely unrecognizable, output 'Unknown strain, please check Google' for the lineage. "
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
    system_prompt = "You are an advanced cannabinoid science database. Output JSON. Keys: 'status', 'primary_effects', 'medical_benefits', 'customer_pitch'."
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
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800;900&family=Inter:wght@400;500;700&display=swap');
.stApp { background-color: #0F172A; color: #F8FAFC; }
.brand-banner { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 20px; border-radius: 16px; border-left: 6px solid #8B5CF6; }
.strain-card { background: linear-gradient(145deg, #1E293B 0%, #0F172A 100%); padding: 35px; border-radius: 16px; border-top: 4px solid #8B5CF6; }
.badge-sativa { background: #10B981; color: white; padding: 4px 12px; border-radius: 8px; font-weight: 800; }
.badge-hybrid { background: #8B5CF6; color: white; padding: 4px 12px; border-radius: 8px; font-weight: 800; }
.badge-indica { background: #3B82F6; color: white; padding: 4px 12px; border-radius: 8px; font-weight: 800; }
</style>"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- App Layout ---
col_banner1, col_banner2 = st.columns([1, 3])
with col_banner1:
    if os.path.exists("video.mp4"): st.video("video.mp4", loop=True, autoplay=True, muted=True)
with col_banner2:
    st.markdown('<div class="brand-banner"><h1>Ziggyz Strain Sniffer & Hub</h1><p>Inventory Logistics & Base Knowledge Management Engine</p></div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🔍 STRAIN SNIFFER", "📊 INVENTORY INTELLIGENCE", "🏷️ HOOK TAG GENERATOR"])

with tab1:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    with st.form("strain_form"):
        user_input = st.text_input("Enter Strain Name:")
        submitted = st.form_submit_button("SEARCH")
    
    if submitted and user_input:
        data = generate_strain_profile(st.secrets["GROQ_API_KEY"], user_input)
        if "error" not in data:
            clf = str(data.get('classification', 'HYBRID')).upper()
            badge = "badge-sativa" if "SATIVA" in clf else ("badge-indica" if "INDICA" in clf else "badge-hybrid")
            st.markdown(f'<div class="strain-card"><h2>{user_input.upper()}</h2><span class="{badge}">{clf}</span><br><br><b>Lineage:</b> {data.get("lineage")}<br><b>Terpenes:</b> {data.get("terpenes")}<br><b>Effects:</b> {data.get("effects")}</div>', unsafe_allow_html=True)

    st.write("---")
    st.markdown("### 🧪 Cannabinoid Encyclopedia")
    c1, c2 = st.columns(2)
    s_chem = c1.selectbox("Quick Select", ["--", "THC", "CBD", "CBG", "CBN"])
    c_chem = c2.text_input("Or type specific compound")
    target = c_chem if c_chem else (None if s_chem == "--" else s_chem)
    if target:
        c_data = get_compound_profile(st.secrets["GROQ_API_KEY"], target)
        st.write(c_data)

with tab2:
    st.write("Inventory logic here...")

with tab3:
    st.write("Tag Generator logic remains as previously finalized.")
