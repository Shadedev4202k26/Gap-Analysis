import streamlit as st, pandas as pd, base64, os, json, requests, random
from urllib.parse import quote_plus
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from io import BytesIO

st.set_page_config(page_title="Ziggybot", page_icon="🔥", layout="wide")

# --- CORE FUNCTIONS ---
def parse_pasted_context(groq_key, strain_name, raw_pasted_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a cannabis strain database parser. Return ONLY JSON with keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects'."},
            {"role": "user", "content": f"Target: {strain_name}\nData: {raw_pasted_text}"}
        ],
        "temperature": 0.0
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        return json.loads(res.json()['choices'][0]['message']['content'].strip())
    except: return {"error": "Parsing failed"}

def generate_word_bank(groq_key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "Provide 20 unique, single-word cannabis industry terms (strains, terpenes, compounds, anatomy). Return only a comma-separated list."}],
        "temperature": 0.7
    }
    res = requests.post(url, headers=headers, json=payload)
    return [w.strip().upper() for w in res.json()['choices'][0]['message']['content'].split(',')]

# --- UI & NAVIGATION ---
tab1, tab2, tab3 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE", "🧠 GAMIFIED KNOWLEDGE"])

with tab1:
    st.markdown("### 📥 Live Restock Gap Analyzer")
    col_file, col_slider = st.columns([3, 2])
    with col_file: uploaded_file = st.file_uploader("Drop Dutchie CSV Export Here", type="csv")
    with col_slider: min_threshold = st.slider("Min Threshold:", 1, 50, 15)
    
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        # (Standard processing logic here...)
        st.success("Analysis Ready")

with tab2:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    target_strain = st.text_input("Enter Strain Name:")
    if target_strain:
        pasted_info = st.text_area("Paste Google search snippet:")
        if pasted_info and st.button("Generate Profile"):
            data = parse_pasted_context(st.secrets["GROQ_API_KEY"], target_strain, pasted_info)
            st.json(data)

with tab3:
    st.markdown("### 🎮 Ziggyz Learning Hub")
    if "game_words" not in st.session_state: st.session_state.game_words = ["CANNABIS", "TERPENE", "INDICA", "SATIVA"]
    
    if st.button("🔄 Refresh Knowledge Bank"):
        st.session_state.game_words = generate_word_bank(st.secrets["GROQ_API_KEY"])
        st.rerun()

    mode = st.radio("Select Game:", ["Hangman", "WordScramble"])
    if mode == "Hangman":
        target = random.choice(st.session_state.game_words)
        st.write(f"Word: {'_ ' * len(target)}")
        guess = st.text_input("Guess Letter:", max_chars=1)
    else:
        word = random.choice(st.session_state.game_words)
        scrambled = "".join(random.sample(word, len(word)))
        st.write(f"Scrambled: {scrambled}")
        st.text_input("Unscramble this:")
