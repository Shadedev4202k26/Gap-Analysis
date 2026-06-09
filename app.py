import streamlit as st
import pandas as pd
import base64
import os
import random

# --- PAGE CONFIG ---
st.set_page_config(page_title="Ziggybot Hub", page_icon="🔥", layout="wide")

# --- FULL UI STYLING ---
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Urbanist:wght=700;900&family=DM+Sans:wght=400;700&display=swap');
.stApp { background-color: #0B0F19; color: #F9FAFB; font-family: 'DM Sans', sans-serif; }
.brand-banner { background-color: #111827; border-radius: 12px; border-left: 6px solid #FDD835; margin-bottom: 25px; display: flex; align-items: center; box-shadow: 0 4px 20px rgba(0,0,0,0.4); padding: 30px; }
.brand-text h1 { font-family: 'Urbanist', sans-serif; font-weight: 900; color: #FDD835 !important; font-size: 40px; margin: 0; letter-spacing: -1px; text-transform: uppercase; }
.brand-text p { color: #94A3B8; margin: 3px 0 0 0; font-size: 15px; letter-spacing: 0.5px; }
.stTabs [data-baseweb='tab-list'] { gap: 8px; }
.stTabs [data-baseweb='tab'] { height: 55px; background-color: #1F2937 !important; border-radius: 8px 8px 0 0 !important; padding: 10px 20px !important; color: #94A3B8 !important; font-family: 'Urbanist', sans-serif; font-weight: 700; border: none !important; }
.stTabs [aria-selected='true'] { background-color: #FDD835 !important; color: #0B0F19 !important; }
.hangman-box { display: flex; justify-content: center; align-items: center; background: #111827; border-radius: 12px; padding: 20px; border: 1px solid #374151; }
.letter-display { font-size: 45px; font-weight: 900; letter-spacing: 12px; color: #FDD835; text-align: center; margin: 20px 0; }
.hint-box { background: #1F2937; padding: 15px; border-radius: 8px; border-left: 4px solid #10B981; margin-top: 10px; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- SVG HANGMAN ENGINE ---
def get_hangman_svg(stage):
    # These SVG paths are calibrated to maintain the 'weathered gallows' look
    stages = [
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="140" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="140" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="130" y2="120" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="10
