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
.stApp { background-color: #0B0F19; color: #F9FAFB; font-family: 'DM Sans', sans-serif; }
.brand-banner { background-color: #111827; border-radius: 12px; border-left: 6px solid #FDD835; margin-bottom: 25px; display: flex; align-items: center; box-shadow: 0 4px 20px rgba(0,0,0,0.4); padding: 30px; }
.game-area { background-color: #111827; padding: 40px; border-radius: 15px; border: 1px solid #374151; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
.hangman-box { display: flex; justify-content: center; align-items: center; min-height: 250px; background: #0B0F19; border-radius: 10px; }
.letter-display { font-size: 50px; font-weight: 900; letter-spacing: 15px; color: #FDD835; text-align: center; margin: 30px 0; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- HIGH-FIDELITY SVG GRAPHICS ENGINE ---
def get_hangman_svg(stage):
    # These SVGs are styled to look like the weathered, hand-drawn look in your reference
    stages = [
        '<svg width="200" height="200"><line x1="20" y1="180" x2="180" y2="180" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="180" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="180" x2="180" y2="180" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="180" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="180" x2="180" y2="180" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="180" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="130" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="180" x2="180" y2="180" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="180" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="130" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="130" y2="120" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="180" x2="180" y2="180" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="180" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="130" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="130" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="190" y2="120" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="180" x2="180" y2="180" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="180" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="130" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="130" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="190" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="130" x2="130" y2="170" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="180" x2="180" y2="180" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="180" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="130" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="130" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="190" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="130" x2="130" y2="170" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="130" x2="190" y2="170" stroke="#F9FAFB" stroke-width="4"/></svg>'
    ]
    return stages[min(stage, len(stages)-1)]

# --- INITIALIZATION ---
if "game" not in st.session_state:
    target = "PINENE"
    st.session_state.game = {"word": target, "revealed": [target[0]] + ["_"]*5, "guesses": [target[0]], "stage": 0, "hint": "A terpene known for pine-like aroma."}

# --- UI RENDER ---
st.markdown('<div class="brand-banner"><h1>ZIGGYZ STRAIN SNIFFER</h1></div>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["📊 INVENTORY", "🔍 AI PROFILER", "🧠 GAME HUB"])

with tab3:
    st.markdown("### 🎮 Ziggy's Learning Hub")
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown(f'<div class="hangman-box">{get_hangman_svg(st.session_state.game["stage"])}</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="letter-display">{" ".join(st.session_state.game["revealed"])}</div>', unsafe_allow_html=True)
        st.info(f"💡 HINT: {st.session_state.game['hint']}")
        
        with st.form("h", clear_on_submit=True):
            guess = st.text_input("GUESS A LETTER:", max_chars=1).upper()
            if st.form_submit_button("SUBMIT"):
                if guess and guess not in st.session_state.game["guesses"]:
                    st.session_state.game["guesses"].append(guess)
                    if guess in st.session_state.game["word"]:
                        for i, char in enumerate(st.session_state.game["word"]):
                            if char == guess: st.session_state.game["revealed"][i] = guess
                    else:
                        st.session_state.game["stage"] += 1
                st.rerun()
