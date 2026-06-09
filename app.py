import streamlit as st
import random
import requests

# --- SVG GRAPHICS ENGINE ---
# These SVG strings render the exact style of gallows and man shown in your design.
def get_hangman_svg(stage):
    stages = [
        # Stage 0: Empty Gallows
        f'<svg width="200" height="250"><line x1="20" y1="230" x2="150" y2="230" stroke="#8B4513" stroke-width="6"/><line x1="80" y1="230" x2="80" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="80" y1="20" x2="160" y2="20" stroke="#8B4513" stroke-width="6"/><line x1="160" y1="20" x2="160" y2="50" stroke="#8B4513" stroke-width="4"/></svg>',
        # Stage 1: Head
        f'<svg width="200" height="250">...</svg><circle cx="160" cy="80" r="30" fill="none" stroke="#F9FAFB" stroke-width="4"/>',
        # ... (Additional stages 2-6 build the body, arms, and legs)
    ]
    return stages[stage]

def choose_word():
    # Fetch from AI or use local bank
    words = ["PINENE", "MYRCENE", "LIMONENE", "LINALOOL", "CARYOPHYLLENE"]
    word = random.choice(words)
    st.session_state.game = {
        "word": word,
        "hint": "Major terpene found in pine trees, known for distinct aroma.",
        "revealed": [word[0]] + ["_" for _ in word[1:]],
        "guesses": [word[0]],
        "stage": 0,
        "remaining": 6
    }

# --- GAME TAB LOGIC ---
with st.tabs(["📊 INVENTORY", "🔍 AI", "🧠 GAMIFIED KNOWLEDGE"])[2]:
    st.markdown("### 🎮 Ziggy's Learning Hub")
    if "game" not in st.session_state: choose_word()
    
    col_gfx, col_ctrl = st.columns([1, 1])
    
    with col_gfx:
        st.markdown(get_hangman_svg(st.session_state.game["stage"]), unsafe_allow_html=True)
        st.markdown(f"### {' '.join(st.session_state.game['revealed'])}")
    
    with col_ctrl:
        st.info(f"💡 Hint: {st.session_state.game['hint']}")
        
        # Using a form to ensure the input clears automatically
        with st.form("guess_form", clear_on_submit=True):
            guess = st.text_input("Input Letter:", max_chars=1).upper()
            submit = st.form_submit_button("Submit Guess")
            
            if submit and guess and guess not in st.session_state.game["guesses"]:
                st.session_state.game["guesses"].append(guess)
                if guess in st.session_state.game["word"]:
                    for i, char in enumerate(st.session_state.game["word"]):
                        if char == guess: st.session_state.game["revealed"][i] = guess
                else:
                    st.session_state.game["stage"] += 1
                    st.session_state.game["remaining"] -= 1
                st.rerun()

    if st.button("Next Game"):
        choose_word()
        st.rerun()
