import streamlit as st, pandas as pd, base64, os, json, requests, random
from weasyprint import HTML

st.set_page_config(page_title="Ziggybot", page_icon="🔥", layout="wide")

def get_strain_profile(api_key, strain_name):
    search_context = ""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            query_string = f'"{strain_name}" strain lineage genetics terpenes effects parents'
            results = [r for r in ddgs.text(query_string, max_results=3)]
            if results:
                search_context = "\n\n".join([f"Data Source Snippet:\n{r['body']}" for r in results])
    except Exception:
        pass

    url = "https://api.groq.com/openai/v1/chat/completions"
    api_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    system_prompt = (
        "You are an expert, deterministic cannabis strain database parser. Your sole objective is outputting clean, structured JSON.\n"
        "You will synthesize your extensive pre-trained knowledge of cannabis genetics along with the provided live search context fragments to compile a 100% accurate profile for the requested strain.\n\n"
        "CRITICAL EXTRACTION INSTRUCTIONS:\n"
        "1. LINEAGE: Identify the exact direct parental cross (e.g., 'GSC X Pink Panties' for Sunset Sherbert). Prioritize universally accepted lineage facts. If the lineage is completely unknown or a closely guarded breeder secret, output 'Proprietary / Unverified Genetics'.\n"
        "2. TERPENES: Isolate the dominant chemical terpene profile (e.g., 'Limone, Myrcene, Caryophyllene'). Never leave this blank or return N/A if the chemical properties are known in cannabis science.\n"
        "3. CLASSIFICATION: Must strictly be one of these three options: 'INDICA', 'SATIVA', or 'HYBRID'.\n"
        "4. FLAVOR & EFFECTS: Provide a concise list of consumer flavors and reported physical/cerebral effects.\n\n"
        "Return ONLY a clean, valid JSON object containing exactly these keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects'."
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": f"Target Strain: {strain_name}\n\nLive Supplemental Context:\n{search_context if search_context else 'No extra context available.'}"}
        ], 
        "temperature": 0.0
    }
    
    try:
        res = requests.post(url, headers=api_headers, json=payload, timeout=12)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: 
                content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
    except Exception as e:
        return {"error": str(e)}
        
    return {"classification": "HYBRID", "lineage": "Proprietary / Unverified Genetics", "terpenes": "N/A", "flavor": "N/A", "effects": "N/A"}

def get_compound_profile(api_key, compound_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = (
        "You are an advanced cannabinoid science database. Analyze the requested cannabis compound or THC variant "
        "and return ONLY a valid JSON object. Do not use double quotes inside any text values. "
        "The JSON must contain exactly these keys: 'status', 'primary_effects', 'medical_benefits', 'customer_pitch'."
    )
    user_prompt = f"Provide a consumer-facing operational profile for the specific compound: {compound_name}"
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.1}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
        return {"error": f"Status code {res.status_code}"}
    except Exception as e: return {"error": str(e)}

# UI Styling Configuration
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
.strain-card { background-color: #111827; padding: 35px; border-radius: 12px; border-top: 4px solid #FDD835; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-top: 15px; margin-bottom: 25px; }
.card-header-flow { display: flex; align-items: center; gap: 15px; flex-wrap: wrap; margin-bottom: 15px; }
.strain-title { font-family: 'Urbanist', sans-serif; font-weight: 900; font-size: 32px; color: #FDD835; text-transform: uppercase; letter-spacing: -0.5px; }
.badge-sativa { background: #10B981; color: #FFF; padding: 5px 14px; border-radius: 6px; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
.badge-hybrid { background: #FDD835; color: #0B0F19; padding: 5px 14px; border-radius: 6px; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
.badge-indica { background: #6366F1; color: #FFF; padding: 5px 14px; border-radius: 6px; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
.section-head { color: #64748B; font-weight: 700; text-transform: uppercase; font-size: 12px; margin-top: 20px; letter-spacing: 1px; }
.section-data { font-size: 17px; color: #E2E8F0; margin-top: 4px; line-height: 1.5; }
.stDownloadButton button { background-color: #FDD835 !important; color: #0B0F19 !important; font-family: 'Urbanist', sans-serif; font-weight: 900; border: none !important; border-radius: 8px !important; padding: 14px !important; width: 100%; letter-spacing: 1px; }
[data-testid='stDataFrame'] { border: 1px solid rgba(253, 216, 53, 0.1); border-radius: 8px; }

/* Retro Game Rendering Styles */
.game-container { background-color: #05070B; border: 3px solid #FDD835; padding: 20px; border-radius: 8px; font-family: monospace; font-size: 24px; line-height: 1.2; letter-spacing: 4px; text-align: center; margin-bottom: 15px; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

logo_path, logo_html = 'image.png', ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_html = f'<img src="data:image/png;base64,{base64.b64encode(img_file.read()).decode("utf-8")}" style="height: 196px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f'<div class="brand-banner" style="padding: 50px 35px;">{logo_html}<div class="brand-text"><h1>Ziggyz Strain Sniffer & Operational Hub</h1><p>Inventory Logistics & Base Knowledge Management Engine</p></div></div>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE", "🎮 BREAKROOM MINI-ARCADE"])

with tab1:
    # --- MERCHANDISING GAP TOOL MODULE ---
    st.markdown("### 📥 Live Restock Gap Analyzer")
    uploaded_file = st.file_uploader("Select Salesfloor & Curbside + any Category🔥Export Product, Room, & Quantity ONLY🔥Drop Dutchie CSV Export Here", type="csv", key="dutchie_uploader")
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [str(col).strip('="').strip() for col in df.columns]
            qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col][0]
            df['Product'] = df['Product'].apply(lambda x: str(x).strip('="').strip())
            df['Room'] = df['Room'].apply(lambda x: str(x).strip('="').strip())
            df['Qty'] = pd.to_numeric(df[qty_col].apply(lambda x: str(x).strip('="').strip()), errors='coerce').fillna(0)
            
            pivot = df.groupby(['Product', 'Room'])['Qty'].sum().unstack(fill_value=0)
            results = []
            for product, row in pivot.iterrows():
                present, absent = row[row > 0].index.tolist(), row[row == 0].index.tolist()
                if absent and present:
                    for r in present:
                        if row[r] >= 15: results.append({"Product Name": product, "Location": r, "Available Qty": int(row[r])})
            
            final_df = pd.DataFrame(results)
            if not final_df.empty:
                final_df = final_df.sort_values("Product Name")
                m1, m2, m3 = st.columns(3)
                with m1: st.markdown(f'<div class="metric-tile"><div class="metric-label">High-Impact Gaps</div><div class="metric-value">{len(final_df)}</div></div>', unsafe_allow_html=True)
                with m2: st.markdown(f'<div class="metric-tile"><div class="metric-label">Units to Move</div><div class="metric-value">{final_df["Available Qty"].sum()}</div></div>', unsafe_allow_html=True)
                with m3: st.markdown(f'<div class="metric-tile"><div class="metric-label">Min Threshold</div><div class="metric-value">15+</div></div>', unsafe_allow_html=True)
                st.write("---")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                pdf_html = f"""
                <html>
                <head>
                <style>
                    @page {{ size: A4; margin: 20mm; background-color: #FFFFFF; }}
                    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1F2937; background-color: #FFFFFF; margin: 0; padding: 0; }}
                    .header {{ border-left: 6px solid #EAB308; padding-left: 15px; margin-bottom: 25px; }}
                    h1 {{ font-size: 26px; color: #111827; text-transform: uppercase; margin: 0; font-weight: bold; letter-spacing: -0.5px; }}
                    .subhead {{ color: #4B5563; font-size: 12px; margin: 5px 0 0 0; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }}
                    .summary-container {{ display: table; width: 100%; margin-top: 25px; margin-bottom: 30px; border-collapse: separate; border-spacing: 12px 0; }}
                    .metric-box {{ display: table-cell; width: 33.33%; background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 12px; text-align: center; vertical-align: middle; }}
                    .label {{ color: #4B5563; font-size: 9px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }}
                    .value {{ font-size: 22px; font-weight: bold; color: #111827; margin: 0; }}
                    table {{ width: 100%; border-collapse: collapse; background-color: #FFFFFF; border-radius: 8px; overflow: hidden; margin-top: 10px; border: 1px solid #E5E7EB; }}
                    th {{ background-color: #F3F4F6; color: #111827; text-transform: uppercase; font-size: 11px; font-weight: bold; letter-spacing: 1px; padding: 12px; text-align: left; border-bottom: 2px solid #D1D5DB; }}
                    td {{ padding: 12px; color: #374151; font-size: 13px; border-bottom: 1px solid #E5E7EB; }}
                    tr:nth-child(even) {{ background-color: #F9FAFB; }}
                </style>
                </head>
                <body>
                    <div class="header">
                        <h1>Ziggyz Merchandise Gap Report</h1>
                        <div class="subhead">High-Impact Floor Restock & Discrepancy Manifest</div>
                    </div>
                    <div class="summary-container">
                        <div class="metric-box">
                            <div class="label">High-Impact Gaps</div>
                            <div class="value">{len(final_df)}</div>
                        </div>
                        <div class="metric-box">
                            <div class="label">Units to Move</div>
                            <div class="value">{final_df["Available Qty"].sum()}</div>
                        </div>
                        <div class="metric-box">
                            <div class="label">Min Threshold</div>
                            <div class="value">15+</div>
                        </div>
                    </div>
                    {final_df.to_html(index=False)}
                </body>
                </html>
                """
                pdf_out = HTML(string=pdf_html).write_pdf()
                st.download_button("📥 DOWNLOAD MERCHANDISING PDF", pdf_out, "Ziggy_Report.pdf", "application/pdf")
            else:
                st.info("No gaps found matching the 15+ unit threshold.")
        except Exception as e: st.error(f"Analysis Error: {e}")

with tab2:
    st.markdown("### 🔍 Real-Time AI Strain Profiler")
    if "GROQ_API_KEY" not in st.secrets:
        st.error("🔒 Security Alert: GROQ_API_KEY missing from Streamlit secrets vault.")
    else:
        if "active_query" not in st.session_state:
            st.session_state.active_query = ""

        def clear_input_box():
            st.session_state.active_query = st.session_state.strain_input_widget
            st.session_state.strain_input_widget = ""

        st.text_input(
            "AI Search Engine Input", 
            placeholder="Type any strain name and press enter...", 
            key="strain_input_widget", 
            on_change=clear_input_box,
            label_visibility="collapsed"
        )
        
        query = st.session_state.active_query.strip()
        if query:
            with st.spinner(f"Querying molecular intelligence metrics for '{query}'..."):
                data = get_strain_profile(st.secrets["GROQ_API_KEY"], query)
                if "error" not in data:
                    clf = str(data.get('classification', 'HYBRID')).upper()
                    badge_class = "badge-hybrid"
                    if "SATIVA" in clf: badge_class = "badge-sativa"
                    elif "INDICA" in clf: badge_class = "badge-indica"
                    
                    card_html = f"""<div class="strain-card">
<div class="card-header-flow">
<div class="strain-title">✨ {query.upper()}</div>
<span class="{badge_class}">{clf}</span>
</div>
<hr style="border: 0; border-top: 1px solid rgba(253, 216, 53, 0.15); margin-bottom: 15px;">
<div class="section-head">🌿 Genetic Lineage</div><div class="section-data">{data.get('lineage', 'N/A')}</div>
<div class="section-head">🧪 Dominant Terpenes</div><div class="section-data">{data.get('terpenes', 'N/A')}</div>
<div class="section-head">🍋 Flavor Profile</div><div class="section-data">{data.get('flavor', 'N/A')}</div>
<div class="section-head">🧠 Reported Consumer Effects</div><div class="section-data">{data.get('effects', 'N/A')}</div>
</div>"""
                    st.markdown(card_html, unsafe_allow_html=True)
                else: st.error(f"Engine connection blip. Details: {data['error']}")
        
        st.write("---")
        st.markdown("### 🧪 Cannabinoid & THC Compound Encyclopedia")
        st.caption("Instant verification engine for compound behaviors, intoxication status, and consumer sales talking points.")
        
        col_select, col_custom = st.columns([2, 2])
        with col_select:
            selected_chem = st.selectbox(
                "Quick Select Target Compound",
                ["-- Choose a Compound --", "THC (Delta-9 Tetrahydrocannabinol)", "THCV (Tetrahydrocannabivarin)", "THCP (Tetrahydrocannabiphorol)", "CBD (Cannabidiol)", "CBG (Cannabigerol)", "CBN (Cannabinol)", "Delta-8 THC"],
                index=0
            )
        with col_custom:
            custom_chem = st.text_input("Or Type a Specific Compound Variant", placeholder="e.g., THCO, CBDA, CBC...").strip()
            
        target_chem = custom_chem if custom_chem else (None if selected_chem == "-- Choose a Compound --" else selected_chem)
        
        if target_chem:
            with st.spinner(f"Querying molecular database for '{target_chem}'..."):
                chem_data = get_compound_profile(st.secrets["GROQ_API_KEY"], target_chem)
                if "error" not in chem_data:
                    status_val = str(chem_data.get('status', 'N/A')).upper()
                    
                    chem_card_html = f"""<div class="strain-card" style="border-top: 4px solid #10B981;">
<div class="card-header-flow">
<div class="strain-title">🔬 {target_chem.upper()}</div>
<span class="badge-sativa" style="background-color: #6366F1;">{status_val}</span>
</div>
<hr style="border: 0; border-top: 1px solid rgba(148, 163, 184, 0.15); margin-bottom: 15px;">
<div class="section-head">🧠 Primary Psychoactive & Physical Effects</div><div class="section-data">{chem_data.get('primary_effects', 'N/A')}</div>
<div class="section-head">🩺 Reported Medicinal & Therapeutic Benefits</div><div class="section-data">{chem_data.get('medical_benefits', 'N/A')}</div>
<div class="section-head">🎯 The Budtender Pitch (How to sell it to customers)</div><div class="section-data" style="color: #FDD835; font-style: italic;">"{chem_data.get('customer_pitch', 'N/A')}"</div>
</div>"""
                    st.markdown(chem_card_html, unsafe_allow_html=True)
                else: st.error(f"Engine connection blip. Details: {chem_data['error']}")

with tab3:
    st.markdown("### 🎮 Ziggy's Breakroom Arcade")
    game_mode = st.radio("Select Shift Duty", ["💼 Vault Escape (2D Strategy)", "🕶️ Vault Defender 3D (Retro Shooter)"], horizontal=True)
    st.write("---")

    # ------------------ GAME 1: VAULT ESCAPE ------------------
    if game_mode == "💼 Vault Escape (2D Strategy)":
        st.markdown("#### 📦 Vault Escape: The Inventory Crawler")
        st.caption("Navigate layouts, grab missing inventory cases, and dodge the compliance auditor!")
        
        MAZE = [
            ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
            ["#", "P", ".", ".", "#", ".", ".", ".", ".", ".", ".", "📦", ".", ".", "#"],
            ["#", ".", "#", ".", "#", ".", "#", "#", "#", "#", "#", ".", "#", ".", "#"],
            ["#", ".", "#", ".", ".", ".", ".", ".", ".", ".", "#", ".", "#", ".", "#"],
            ["#", ".", "#", "#", "#", "#", ".", "#", "#", ".", "#", ".", "#", ".", "#"],
            ["#", "📦", ".", ".", ".", "#", ".", "E", "#", ".", ".", ".", ".", "📦", "#"],
            ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"]
        ]
        
        if "v_x" not in st.session_state:
            st.session_state.v_x, st.session_state.v_y = 1, 1
            st.session_state.v_score, st.session_state.v_game_over = 0, False
            st.session_state.v_left = 3
            
        def move_vault(dx, dy):
            if st.session_state.v_game_over: return
            nx, ny = st.session_state.v_x + dx, st.session_state.v_y + dy
            if 0 <= ny < len(MAZE) and 0 <= nx < len(MAZE[0]) and MAZE[ny][nx] != "#":
                st.session_state.v_x, st.session_state.v_y = nx, ny
                if ny == 1 and nx == 11 and "vb1" not in st.session_state:
                    st.session_state.vb1 = True; st.session_state.v_score += 100; st.session_state.v_left -= 1
                elif ny == 5 and nx == 1 and "vb2" not in st.session_state:
                    st.session_state.vb2 = True; st.session_state.v_score += 100; st.session_state.v_left -= 1
                elif ny == 5 and nx == 13 and "vb3" not in st.session_state:
                    st.session_state.vb3 = True; st.session_state.v_score += 100; st.session_state.v_left -= 1
                if ny == 5 and nx == 7: st.session_state.v_game_over = True

        v_rows = []
        for y, row in enumerate(MAZE):
            chars = []
            for x, c in enumerate(row):
                if y == st.session_state.v_y and x == st.session_state.v_x: chars.append("🤠")
                elif y == 1 and x == 11 and "vb1" in st.session_state: chars.append(" floor ")
                elif y == 5 and x == 1 and "vb2" in st.session_state: chars.append(" floor ")
                elif y == 5 and x == 13 and "vb3" in st.session_state: chars.append(" floor ")
                elif c == "#": chars.append("🧱")
                elif c == "📦": chars.append("📦")
                elif c == "E": chars.append("🕵️")
                else: chars.append(" 🟩 ")
            v_rows.append("".join(chars))
            
        cv, cp, cc = st.columns([6, 3, 3])
        with cv:
            st.markdown(f'<div class="game-container">{"<br>".join(v_rows)}</div>', unsafe_allow_html=True)
            if st.session_state.v_left == 0:
                st.success("🏆 Manifest Cleared! Stock safely logged back into the Dutchie vault.")
                st.session_state.v_game_over = True
            elif st.session_state.v_game_over:
                st.error("🚨 Audit Violation! The compliance agent caught you running packages without an active Metrc tag.")
            if st.button("🔄 Reset Vault"):
                st.session_state.v_x, st.session_state.v_y = 1, 1
                st.session_state.v_score, st.session_state.v_game_over, st.session_state.v_left = 0, False, 3
                for k in ["vb1", "vb2", "vb3"]: st.session_state.pop(k, None)
                st.rerun()
        with cp:
            st.metric("Score", f"{st.session_state.v_score} pts")
            st.metric("Boxes Left", f"{st.session_state.v_left} / 3")
        with cc:
            st.button("🔼", key="v_up", on_click=move_vault, args=(0, -1))
            r_mid = st.columns(2)
            r_mid[0].button("◀️", key="v_lf", on_click=move_vault, args=(-1, 0))
            r_mid[1].button("▶️", key="v_rt", on_click=move_vault, args=(1, 0))
            st.button("🔽", key="v_dn", on_click=move_vault, args=(0, 1))

    # ------------------ GAME 2: 3D RETRO SHOOTER ------------------
    else:
        st.markdown("#### 🕶️ Vault Defender 3D")
        st.caption("Click into the window below to lock controls. Clear out incoming compliance bugs in real-time.")
        
        import streamlit.components.v1 as components
        
        three_d_game_html = """
        <div style="text-align:center; background:#0B0F19; padding:15px; border-radius:8px;">
            <canvas id="raycasterCanvas" width="640" height="400" style="border:3px solid #FDD835; background:#000; cursor:crosshair;"></canvas>
            <div style="color:#94A3B8; font-family:sans-serif; font-size:13px; margin-top:10px;">
                <strong>W / S</strong> — Forward/Backward | <strong>A / D</strong> — Strafe | <strong>Left / Right Arrow</strong> — Look | <strong>Spacebar</strong> — Shoot Bug Target
            </div>
            <div id="scoreBoard" style="color:#FDD835; font-family:sans-serif; font-weight:bold; font-size:18px; margin-top:8px;">Bugs Terminated: 0</div>
        </div>
        
        <script>
        const canvas = document.getElementById('raycasterCanvas');
        const ctx = canvas.getContext('2d');
        
        // Map Grid setup (1 = Wall, 0 = Empty floor space)
        const map = [
            [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
            [1,0,0,0,0,0,1,0,0,0,0,0,0,0,0,1],
            [1,0,1,1,0,0,1,0,1,1,1,1,0,1,0,1],
            [1,0,1,0,0,0,0,0,0,0,0,1,0,1,0,1],
            [1,0,1,0,1,1,1,1,1,0,0,1,0,1,0,1],
            [1,0,0,0,1,0,0,0,1,0,0,0,0,0,0,1],
            [1,0,1,0,1,0,0,0,1,0,1,1,1,1,0,1],
            [1,0,1,0,1,1,0,1,1,0,1,0,0,1,0,1],
            [1,0,1,0,0,0,0,0,0,0,1,0,0,1,0,1],
            [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
        ];
        const mapWidth = 16, mapHeight = 10;
        
        // Player Position details
        let player = { x: 2.5, y: 2.5, angle: 0, fov: Math.PI / 3 };
        let keys = {};
        let score = 0;
        
        // Game variables for the target bug entity
        let bug = { x: 7.5, y: 5.5, baseSize: 40, health: 1, timer: 0 };
        let flashFrame = 0;
        
        window.addEventListener('keydown', (e) => { keys[e.key] = true; if(e.key === ' ') shootWeapon(); });
        window.addEventListener('keyup', (e) => { keys[e.key] = false; });
        
        function shootWeapon() {
            flashFrame = 4; // Fire trigger muzzle flash duration
            // Basic hit confirmation if bug is center screen alignment
            if (bug.health > 0) {
                let dx = bug.x - player.x;
                let dy = bug.y - player.y;
                let angleToBug = Math.atan2(dy, dx) - player.angle;
                while (angleToBug < -Math.PI) angleToBug += Math.PI * 2;
                while (angleToBug > Math.PI) angleToBug -= Math.PI * 2;
                
                if (Math.abs(angleToBug) < 0.2) {
                    score++;
                    document.getElementById('scoreBoard').innerText = "Bugs Terminated: " + score;
                    respawnBug();
                }
            }
        }
        
        function respawnBug() {
            let valid = false;
            while(!valid) {
                let rx = Math.floor(Math.random() * mapWidth);
                let ry = Math.floor(Math.random() * mapHeight);
                if (map[ry][rx] === 0) {
                    bug.x = rx + 0.5;
                    bug.y = ry + 0.5;
                    valid = true;
                }
            }
        }
        
        function updatePlayerPosition() {
            let moveSpeed = 0.04;
            let rotSpeed = 0.03;
            
            if (keys['ArrowLeft'] || keys['Left']) player.angle -= rotSpeed;
            if (keys['ArrowRight'] || keys['Right']) player.angle += rotSpeed;
            
            let dx = Math.cos(player.angle) * moveSpeed;
            let dy = Math.sin(player.angle) * moveSpeed;
            
            if (keys['w'] || keys['W']) {
                if (map[Math.floor(player.y)][Math.floor(player.x + dx)] === 0) player.x += dx;
                if (map[Math.floor(player.y + dy)][Math.floor(player.x)] === 0) player.y += dy;
            }
            if (keys['s'] || keys['S']) {
                if (map[Math.floor(player.y)][Math.floor(player.x - dx)] === 0) player.x -= dx;
                if (map[Math.floor(player.y - dy)][Math.floor(player.x)] === 0) player.y -= dy;
            }
            // Strafe mechanics
            let sx = Math.cos(player.angle + Math.PI/2) * moveSpeed;
            let sy = Math.sin(player.angle + Math.PI/2) * moveSpeed;
            if (keys['a'] || keys['A']) {
                if (map[Math.floor(player.y)][Math.floor(player.x - sx)] === 0) player.x -= sx;
                if (map[Math.floor(player.y - sy)][Math.floor(player.x)] === 0) player.y -= sy;
            }
            if (keys['d'] || keys['D']) {
                if (map[Math.floor(player.y)][Math.floor(player.x + sx)] === 0) player.x += sx;
                if (map[Math.floor(player.y + sy)][Math.floor(player.x)] === 0) player.y += sy;
            }
        }
        
        function render3DView() {
            // Draw Ceiling and Floor fields
            ctx.fillStyle = '#111622'; ctx.fillRect(0, 0, 640, 200);
            ctx.fillStyle = '#181E29'; ctx.fillRect(0, 200, 640, 200);
            
            let numRays = 320;
            let rayWidth = 2;
            let depthBuffer = new Array(numRays);
            
            // Core Raycasting math loop
            for (let i = 0; i < numRays; i++) {
                let rayAngle = (player.angle - player.fov / 2) + (i / numRays) * player.fov;
                let distance = 0;
                let hitWall = false;
                
                let cx = Math.cos(rayAngle);
                let cy = Math.sin(rayAngle);
                
                while (!hitWall && distance < 16) {
                    distance += 0.05;
                    let checkX = Math.floor(player.x + cx * distance);
                    let checkY = Math.floor(player.y + cy * distance);
                    
                    if (checkX < 0 || checkX >= mapWidth || checkY < 0 || checkY >= mapHeight) {
                        hitWall = true; distance = 16;
                    } else if (map[checkY][checkX] > 0) {
                        hitWall = true;
                    }
                }
                
                // Correct fisheye distortion lens
                let correctedDistance = distance * Math.cos(rayAngle - player.angle);
                depthBuffer[i] = correctedDistance;
                let wallHeight = Math.min(400, Math.floor(300 / correctedDistance));
                
                // Set color density based on distance wall gradients
                let cValue = Math.floor(Math.max(20, 220 - (correctedDistance * 16)));
                ctx.fillStyle = `rgb(${Math.floor(cValue * 0.9)}, ${Math.floor(cValue * 0.8)}, ${Math.floor(cValue * 0.3)})`;
                ctx.fillRect(i * rayWidth, (400 - wallHeight) / 2, rayWidth, wallHeight);
            }
            
            // Render Sprite mechanics (Compliance Bug Target)
            let bdx = bug.x - player.x;
            let bdy = bug.y - player.y;
            let spriteDist = Math.sqrt(bdx*bdx + bdy*bdy);
            let spriteAngle = Math.atan2(bdy, bdx) - player.angle;
            
            while (spriteAngle < -Math.PI) spriteAngle += Math.PI * 2;
            while (spriteAngle > Math.PI) spriteAngle -= Math.PI * 2;
            
            if (Math.abs(spriteAngle) < player.fov / 1.5 && spriteDist > 0.2) {
                let spriteHeight = Math.min(400, Math.floor(300 / spriteDist));
                let spriteX = Math.floor((320) + (Math.tan(spriteAngle) * 320) - spriteHeight / 2);
                let spriteY = Math.floor((400 - spriteHeight) / 2);
                
                // Basic render check against wall depth buffers
                let rayIdx = Math.floor((spriteX + spriteHeight / 2) / 2);
                if (rayIdx >= 0 && rayIdx < numRays && depthBuffer[rayIdx] > spriteDist) {
                    bug.timer += 0.07;
                    let hover = Math.sin(bug.timer) * 10;
                    ctx.fillStyle = '#EF4444';
                    // Render stylized diamond layout bug target shape
                    ctx.beginPath();
                    ctx.moveTo(spriteX + spriteHeight/2, spriteY + hover);
                    ctx.lineTo(spriteX + spriteHeight, spriteY + spriteHeight/2 + hover);
                    ctx.lineTo(spriteX + spriteHeight/2, spriteY + spriteHeight + hover);
                    ctx.lineTo(spriteX, spriteY + spriteHeight/2 + hover);
                    ctx.closePath();
                    ctx.fill();
                    
                    // Core critical core graphic target overlay
                    ctx.fillStyle = '#FFFFFF';
                    ctx.fillRect(spriteX + spriteHeight/2 - 4, spriteY + spriteHeight/2 - 4 + hover, 8, 8);
                }
            }
            
            // Render UI Crosshair hud elements
            ctx.strokeStyle = 'rgba(253, 216, 53, 0.4)';
            ctx.lineWidth = 2;
            ctx.beginPath(); ctx.moveTo(320, 180); ctx.lineTo(320, 220); ctx.moveTo(300, 200); ctx.lineTo(340, 200); ctx.stroke();
            
            // Weapon Muzzle Blast Flash display layer
            if (flashFrame > 0) {
                ctx.fillStyle = `rgba(253, 216, 53, ${flashFrame * 0.2})`;
                ctx.fillRect(0, 0, 640, 400);
                flashFrame--;
            }
        }
        
        function frameIteration() {
            updatePlayerPosition();
            render3DView();
            requestAnimationFrame(frameIteration);
        }
        frameIteration();
        </script>
        """
        components.html(three_d_game_html, height=520, scrolling=False)
