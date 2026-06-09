import streamlit as st
import pandas as pd
import base64
import os
import json
import requests
import random
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from io import BytesIO

# --- PAGE CONFIG ---
st.set_page_config(page_title="Ziggybot Hub", page_icon="🔥", layout="wide")

# --- CUSTOM CSS ---
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Urbanist:wght=700;900&family=DM+Sans:wght=400;700&display=swap');
.stApp { background-color: #0B0F19; color: #F9FAFB; font-family: 'DM Sans', sans-serif; }
.brand-banner { background-color: #111827; border-radius: 12px; border-left: 6px solid #FDD835; margin-bottom: 25px; display: flex; align-items: center; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
.brand-text h1 { font-family: 'Urbanist', sans-serif; font-weight: 900; color: #FDD835 !important; font-size: 40px; margin: 0; letter-spacing: -1px; text-transform: uppercase; }
.brand-text p { color: #94A3B8; margin: 3px 0 0 0; font-size: 15px; letter-spacing: 0.5px; }
.stTabs [data-baseweb='tab-list'] { gap: 8px; }
.stTabs [data-baseweb='tab'] { height: 55px; background-color: #1F2937 !important; border-radius: 8px 8px 0 0 !important; padding: 10px 20px !important; color: #94A3B8 !important; font-family: 'Urbanist', sans-serif; font-weight: 700; border: none !important; }
.stTabs [aria-selected='true'] { background-color: #FDD835 !important; color: #0B0F19 !important; }
.metric-tile { background-color: #111827; padding: 25px; border-radius: 12px; border: 1px solid rgba(253, 216, 53, 0.15); text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
.metric-label { color: #FDD835; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; }
.metric-value { font-family: 'Urbanist', sans-serif; font-size: 44px; font-weight: 900; color: #F9FAFB; margin-top: 5px; }
.strain-card { background-color: #111827; padding: 35px; border-radius: 12px; border-top: 4px solid #FDD835; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- GAME GRAPHICS ENGINE ---
def get_hangman_svg(stage):
    stages = [
        '<svg width="150" height="200"><line x1="20" y1="190" x2="130" y2="190" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="190" x2="75" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="20" x2="130" y2="20" stroke="#8B4513" stroke-width="4"/><line x1="130" y1="20" x2="130" y2="50" stroke="#8B4513" stroke-width="4"/></svg>',
        '<svg width="150" height="200"><line x1="20" y1="190" x2="130" y2="190" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="190" x2="75" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="20" x2="130" y2="20" stroke="#8B4513" stroke-width="4"/><line x1="130" y1="20" x2="130" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="130" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="3"/></svg>',
        '<svg width="150" height="200"><line x1="20" y1="190" x2="130" y2="190" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="190" x2="75" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="20" x2="130" y2="20" stroke="#8B4513" stroke-width="4"/><line x1="130" y1="20" x2="130" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="130" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="90" x2="130" y2="140" stroke="#F9FAFB" stroke-width="3"/></svg>',
        '<svg width="150" height="200"><line x1="20" y1="190" x2="130" y2="190" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="190" x2="75" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="20" x2="130" y2="20" stroke="#8B4513" stroke-width="4"/><line x1="130" y1="20" x2="130" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="130" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="90" x2="130" y2="140" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="100" x2="100" y2="120" stroke="#F9FAFB" stroke-width="3"/></svg>',
        '<svg width="150" height="200"><line x1="20" y1="190" x2="130" y2="190" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="190" x2="75" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="20" x2="130" y2="20" stroke="#8B4513" stroke-width="4"/><line x1="130" y1="20" x2="130" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="130" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="90" x2="130" y2="140" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="100" x2="100" y2="120" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="100" x2="160" y2="120" stroke="#F9FAFB" stroke-width="3"/></svg>',
        '<svg width="150" height="200"><line x1="20" y1="190" x2="130" y2="190" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="190" x2="75" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="20" x2="130" y2="20" stroke="#8B4513" stroke-width="4"/><line x1="130" y1="20" x2="130" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="130" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="90" x2="130" y2="140" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="100" x2="100" y2="120" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="100" x2="160" y2="120" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="140" x2="100" y2="180" stroke="#F9FAFB" stroke-width="3"/></svg>',
        '<svg width="150" height="200"><line x1="20" y1="190" x2="130" y2="190" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="190" x2="75" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="75" y1="20" x2="130" y2="20" stroke="#8B4513" stroke-width="4"/><line x1="130" y1="20" x2="130" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="130" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="90" x2="130" y2="140" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="100" x2="100" y2="120" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="100" x2="160" y2="120" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="140" x2="100" y2="180" stroke="#F9FAFB" stroke-width="3"/><line x1="130" cy="140" x2="160" y2="180" stroke="#F9FAFB" stroke-width="3"/></svg>'
    ]
    return stages[min(stage, len(stages)-1)]

# --- INITIALIZATION ---
logo_html = ""
if os.path.exists('image.png'):
    with open('image.png', 'rb') as f:
        logo_html = f'<img src="data:image/png;base64,{base64.b64encode(f.read()).decode("utf-8")}" style="height: 196px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f'<div class="brand-banner" style="padding: 50px 35px;">{logo_html}<div class="brand-text"><h1>ZIGGYZ STRAIN SNIFFER & OPERATIONAL HUB</h1><p>INVENTORY LOGISTICS & KNOWLEDGE MANAGEMENT ENGINE</p></div></div>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE", "🧠 GAMIFIED KNOWLEDGE"])

with tab1:
    st.markdown("### 📥 Live Restock Gap Analyzer")
    uploaded_file = st.file_uploader("Upload Dutchie Export", type="csv")
    if uploaded_file:
        st.success("Analysis Engine Active")

with tab2:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    st.text_input("Enter Strain Name")

with tab3:
    st.markdown("### 🎮 Ziggy's Learning Hub")
    if "game" not in st.session_state:
        word = "PINENE"
        st.session_state.game = {"word": word, "revealed": [word[0]] + ["_"]*5, "guesses": [word[0]], "stage": 0}
    
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown(get_hangman_svg(st.session_state.game["stage"]), unsafe_allow_html=True)
    with c2:
        st.markdown(f"## {' '.join(st.session_state.game['revealed'])}")
        with st.form("h", clear_on_submit=True):
            guess = st.text_input("Guess a letter:", max_chars=1).upper()
            if st.form_submit_button("Submit"):
                if guess and guess not in st.session_state.game["guesses"]:
                    st.session_state.game["guesses"].append(guess)
                    if guess in st.session_state.game["word"]:
                        for i, char in enumerate(st.session_state.game["word"]):
                            if char == guess: st.session_state.game["revealed"][i] = guess
                    else:
                        st.session_state.game["stage"] += 1
                st.rerun()
