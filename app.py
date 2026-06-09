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
@import url('https://fonts.googleapis.com/css2?family=Urbanist:wght=700;900&family=DM+Sans:wght=400;700&display=swap');
.stApp { background-color: #0B0F19; color: #F9FAFB; font-family: 'DM Sans', sans-serif; }
.brand-banner { background-color: #111827; border-radius: 12px; border-left: 6px solid #FDD835; margin-bottom: 25px; display: flex; align-items: center; box-shadow: 0 4px 20px rgba(0,0,0,0.4); padding: 30px; }
.brand-text h1 { font-family: 'Urbanist', sans-serif; font-weight: 900; color: #FDD835 !important; font-size: 40px; margin: 0; letter-spacing: -1px; text-transform: uppercase; }
.brand-text p { color: #94A3B8; margin: 3px 0 0 0; font-size: 15px; letter-spacing: 0.5px; }
.stTabs [data-baseweb='tab-list'] { gap: 8px; }
.stTabs [data-baseweb='tab'] { height: 55px; background-color: #1F2937 !important; border-radius: 8px 8px 0 0 !important; padding: 10px 20px !important; color: #94A3B8 !important; font-family: 'Urbanist', sans-serif; font-weight: 700; border: none !important; }
.stTabs [aria-selected='true'] { background-color: #FDD835 !important; color: #0B0F19 !important; }
.hangman-box { display: flex; justify-content: center; align-items: center; background: #0B0F19; border-radius: 12px; padding: 20px; border: 1px solid #374151; }
.letter-display { font-size: 50px; font-weight: 900; letter-spacing: 15px; color: #FDD835; text-align: center; margin: 30px 0; }
.hint-box { background: #1F2937; padding: 15px; border-radius: 8px; border-left: 4px solid #10B981; margin-top: 10px; }
.strain-card { background: #111827; padding: 20px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 15px; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- SVG ENGINE ---
def get_hangman_svg(stage):
    stages = [
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="140" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="140" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="130" y2="120" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="140" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="130" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="190" y2="120" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="140" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="130" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="190" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="140" x2="130" y2="180" stroke="#F9FAFB" stroke-width="4"/></svg>',
        '<svg width="200" height="200"><line x1="20" y1="190" x2="180" y2="190" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="190" x2="100" y2="20" stroke="#8B4513" stroke-width="8"/><line x1="100" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/><circle cx="160" cy="70" r="20" fill="none" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="90" x2="160" y2="140" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="130" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="100" x2="190" y2="120" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="140" x2="130" y2="180" stroke="#F9FAFB" stroke-width="4"/><line x1="160" y1="140" x2="190" y2="180" stroke="#F9FAFB" stroke-width="4"/></svg>'
    ]
    return stages[min(stage, len(stages)-1)]

# --- GAME LOGIC ---
def reset_game():
    bank = {"PINENE": "Known for pine-like aroma.", "LINALOOL": "Floral, lavender-like scent.", "MYRCENE": "Earthy, musky, herbal terpene."}
    word = random.choice(list(bank.keys()))
    st.session_state.game = {"word": word, "revealed": [word[0]] + ["_"]*(len(word)-1), "guesses": [word[0]], "stage": 0, "hint": bank[word], "over": False}

# --- HEADER / BRANDING ---
logo_html = ""
if os.path.exists('image.png'):
    with open('image.png', 'rb') as f:
        logo_html = f'<img src="data:image/png;base64,{base64.b64encode(f.read()).decode("utf-8")}" style="height: 196px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f'<div class="brand-banner">{logo_html}<div class="brand-text"><h1>ZIGGYZ STRAIN SNIFFER & OPERATIONAL HUB</h1><p>INVENTORY LOGISTICS & KNOWLEDGE MANAGEMENT ENGINE</p></div></div>', unsafe_allow_html=True)

# --- TAB STRUCTURE ---
tab1, tab2, tab3 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE", "🧠 GAMIFIED KNOWLEDGE"])

with tab1:
    st.markdown("### 📥 Live Restock Gap Analyzer")
    uploaded_file = st.file_uploader("Upload Dutchie Export", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df, use_container_width=True)

with tab2:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    c1, c2 = st.columns([1, 1])
    with c1:
        search = st.text_input("Search Strain Library")
    with c2:
        cannabinoid = st.selectbox("Cannabinoid Lookup", ["THC", "CBD", "CBG", "CBN", "CBC", "THCV"])
        
    if st.button("Search Database"):
        st.info(f"Searching for {search} filtered by {cannabinoid}...")
        st.markdown(f'<div class="strain-card"><h4>Results for {search} ({cannabinoid})</h4><p>Data will appear here.</p></div>', unsafe_allow_html=True)

with tab3:
    st.markdown("### 🎮 Ziggy's Learning Hub")
    if "game" not in st.session_state or "over" not in st.session_state.game: reset_game()
    
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown(f'<div class="hangman-box">{get_hangman_svg(st.session_state.game["stage"])}</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="letter-display">{" ".join(st.session_state.game["revealed"])}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hint-box">**💡 HINT:** {st.session_state.game["hint"]}</div>', unsafe_allow_html=True)
        
        if not st.session_state.game["over"]:
            with st.form("guess_form", clear_on_submit=True):
                guess = st.text_input("Guess a letter:", max_chars=1).upper()
                if st.form_submit_button("Submit Guess"):
                    if guess and guess.isalpha() and guess not in st.session_state.game["guesses"]:
                        st.session_state.game["guesses"].append(guess)
                        if guess in st.session_state.game["word"]:
                            for i, char in enumerate(st.session_state.game["word"]):
                                if char == guess: st.session_state.game["revealed"][i] = guess
                            if "_" not in st.session_state.game["revealed"]:
                                st.success("VICTORY! YOU GUESSED THE WORD.")
                                st.session_state.game["over"] = True
                        else:
                            st.session_state.game["stage"] += 1
                            if st.session_state.game["stage"] >= 6:
                                st.error(f"GAME OVER! THE WORD WAS: {st.session_state.game['word']}")
                                st.session_state.game["over"] = True
                    st.rerun()
        else:
            if st.button("🔄 Start New Puzzle"):
                reset_game()
                st.rerun()
