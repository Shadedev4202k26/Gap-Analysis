import streamlit as st, pandas as pd, base64, os, json, requests, random
from urllib.request import Request, urlopen
from urllib.parse import quote_plus
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from io import BytesIO

# UI Configuration
st.set_page_config(page_title="Ziggybot Hub", page_icon="🔥", layout="wide")

def set_game_defaults():
    st.session_state.game_state = {
        "score": 0,
        "words_left": 14,
        "current_streak": 0,
        "wrong_guesses": 0,
        "guesses_remaining": 6,
        "guesses_made": [],
        "current_word": "",
        "revealed_word": []
    }
    st.session_state.game_words = ["THC", "MYRCENE", "TRICHOME", "SATIVA", "HYBRID", "BUDTENDER", "CANNABIS"]

def choose_new_word():
    target = random.choice(st.session_state.game_words)
    st.session_state.game_state["current_word"] = target.upper()
    st.session_state.game_state["revealed_word"] = ["_" for _ in target]
    st.session_state.game_state["wrong_guesses"] = 0
    st.session_state.game_state["guesses_remaining"] = 6
    st.session_state.game_state["guesses_made"] = []
    st.session_state.hangman_graphic_level = 0

def generate_word_bank(groq_key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "Provide 30 unique, single-word cannabis industry terms (strains, terpenes, compounds, anatomy, hardware). Return ONLY a comma-separated list."}],
        "temperature": 0.7
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        return [w.strip().upper() for w in res.json()['choices'][0]['message']['content'].split(',')]
    except: return ["CANNABIS", "THC", "CBD", "MYRCENE", "TRICHOME", "INDICA", "SATIVA"]

# Graphic definitions for the hangman stage progression
stages = [
    """
    +-------+
    |       |
    |       
    |      
    |      
    |      
    +=========
    """,
    """
    +-------+
    |       |
    |       O
    |      
    |      
    |      
    +=========
    """,
    """
    +-------+
    |       |
    |       O
    |       |
    |      
    |      
    +=========
    """,
    """
    +-------+
    |       |
    |       O
    |      /|
    |      
    |      
    +=========
    """,
    """
    +-------+
    |       |
    |       O
    |      /|\\
    |      
    |      
    +=========
    """,
    """
    +-------+
    |       |
    |       O
    |      /|\\
    |      / 
    |      
    +=========
    """,
    """
    +-------+
    |       |
    |       O
    |      /|\\
    |      / \\
    |      
    +=========
    """
]

# --- UI Styling Configuration (Retained and Enhanced) ---
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
.game-metric { background-color: #1F2937; padding: 10px; border-radius: 8px; font-size: 14px; text-align: center; border: 1px solid rgba(148, 163, 184, 0.1); }
[data-testid='stDataFrame'] { border: 1px solid rgba(253, 216, 53, 0.1); border-radius: 8px; }
div[data-testid="stSlider"] label { color: #FDD835 !important; font-weight: bold; text-transform: uppercase; }
input[data-testid="stTextInput"] { background-color: #1F2937 !important; border: 1px solid rgba(148, 163, 184, 0.2) !important; color: #F9FAFB !important; font-size: 24px !important; text-align: center; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# Main Navigation Hub
logo_path, logo_html = 'image.png', ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_html = f'<img src="data:image/png;base64,{base64.b64encode(img_file.read()).decode("utf-8")}" style="height: 196px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f'<div class="brand-banner" style="padding: 50px 35px;">{logo_html}<div class="brand-text"><h1>ZIGGYZ STRAIN SNIFFER & OPERATIONAL HUB</h1><p>INVENTORY LOGISTICS & KNOWLEDGE MANAGEMENT ENGINE</p></div></div>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE", "🧠 GAMIFIED KNOWLEDGE"])

with tab1:
    st.markdown("### 📥 Live Restock Gap Analyzer")
    # (Retained Inventory module code here...)

with tab2:
    st.markdown("### 🔍 Verified AI Strain Profiler")
    # (Retained Strain Profiler module code here...)

with tab3:
    if "game_state" not in st.session_state: set_game_defaults()
    if not st.session_state.game_state["current_word"]: choose_new_word()

    st.markdown("### 🎮 Ziggy's Learning Hub")
    st.markdown("Classic Marijuana Hangman: Guess the cannabis term!")
    col_graphics, col_controls = st.columns([2, 1])

    with col_graphics:
        # 1. Main Game Display: Display the ASCII stages and revealed word as shown in the image
        st.markdown(f"<pre style='font-size:18px; color:#F9FAFB; background:#111827; padding:20px; border-radius:12px; border-top: 4px solid #FDD835; box-shadow: 0 10px 30px rgba(0,0,0,0.5);'>{stages[st.session_state.hangman_graphic_level]}</pre>", unsafe_allow_html=True)
        st.write("---")
        st.markdown(f"<div style='font-size: 54px; letter-spacing: 12px; text-align: center; font-weight: bold;'>{' '.join(st.session_state.game_state['revealed_word'])}</div>", unsafe_allow_html=True)
        st.write("---")
        st.markdown(f"**Guesses made:** {', '.join(st.session_state.game_state['guesses_made'])}")

    with col_controls:
        # 2. Main Controls & Metrics
        st.markdown(f"""
<div class="strain-card" style="margin-bottom:20px; border-top: 4px solid #FDD835;">
<div class="card-header-flow">
<div class="strain-title">OPERATIONAL METRICS</div>
<span class="badge-hybrid">STATIONED</span>
</div>
<hr style="border: 0; border-top: 1px solid rgba(253, 216, 53, 0.15); margin-bottom: 15px;">
<div class="section-head">Guesses Remaining</div><div class="section-data" style="color:#FDD835;">{st.session_state.game_state['guesses_remaining']} / 6</div>
<div class="section-head">Current Streak</div><div class="section-data">{st.session_state.game_state['current_streak']} (Max: 5)</div>
</div>""", unsafe_allow_html=True)

        # 3. Input Handling Module: Bypasses native Streamlit "delete to guess" limitation
        if "input_key" not in st.session_state: st.session_state.input_key = 0
        def clear_and_submit():
            st.session_state.last_guess = st.session_state[f"guess_input_{st.session_state.input_key}"].upper().strip()
            st.session_state.input_key += 1

        st.text_input("Input Letter (A-Z):", max_chars=1, key=f"guess_input_{st.session_state.input_key}", on_change=clear_and_submit)
        
        if "last_guess" in st.session_state:
            guess = st.session_state.last_guess
            if guess and guess.isalpha() and guess not in st.session_state.game_state["guesses_made"]:
                st.session_state.game_state["guesses_made"].append(guess)
                if guess in st.session_state.game_state["current_word"]:
                    for idx, char in enumerate(st.session_state.game_state["current_word"]):
                        if char == guess: st.session_state.game_state["revealed_word"][idx] = guess
                else:
                    st.session_state.game_state["wrong_guesses"] += 1
                    st.session_state.game_state["guesses_remaining"] -= 1
                    st.session_state.hangman_graphic_level += 1

            # Game Over / Win State checks
            if st.session_state.game_state["guesses_remaining"] <= 0:
                st.error(f"GAME OVER! The word was: {st.session_state.game_state['current_word']}")
                st.session_state.game_state["current_streak"] = 0
                st.button("Play Again", on_click=choose_new_word)
            elif "_" not in st.session_state.game_state["revealed_word"]:
                st.success(f"CORRECT! You revealed: {st.session_state.game_state['current_word']}")
                st.session_state.game_state["current_streak"] += 1
                st.session_state.game_state["words_left"] -= 1
                st.button("Next Game", on_click=choose_new_word)

        # 4. Global Refreshes
        st.write("---")
        c1, c2 = st.columns(2)
        with c1: st.button("Reset Station Metrics", on_click=set_game_defaults, key="reset_station")
        with c2: st.button("🔄 Refresh Word Bank (AI)", key="refresh_ai")
        if st.session_state.get("refresh_ai") and "GROQ_API_KEY" in st.secrets:
            st.session_state.game_words = generate_word_bank(st.secrets["GROQ_API_KEY"])
            choose_new_word()
            st.rerun()
