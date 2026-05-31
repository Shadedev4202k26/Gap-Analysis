import streamlit as st, pandas as pd, base64, os, json, requests
from weasyprint import HTML
from bs4 import BeautifulSoup  # Direct DOM parser for live data scraping

st.set_page_config(page_title="Ziggybot", page_icon="🔥", layout="wide")

def get_strain_profile(api_key, strain_name):
    # Formulate exact AllBud URL pattern slug conventions
    formatted_slug = strain_name.strip().lower().replace(" ", "-")
    target_url = f"https://www.allbud.com/marijuana-strains/{formatted_slug}"
    
    scraped_html_context = ""
    
    # Attempt 1: Standard request with advanced browser headers
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        response = requests.get(target_url, headers=headers, timeout=8)
        
        # If Cloudflare blocks it (403), we handle it in the fallback block
        if response.status_code == 200 and "cloudflare" not in response.text.lower():
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # AllBud DOM Targets: Check both class variations and standard tags
            lineage_element = soup.find(class_="lineage") or soup.find(class_="genetics")
            description_element = soup.find(id="strain-description") or soup.find(class_="description")
            
            extracted_text = []
            if lineage_element:
                extracted_text.append(f"Direct Lineage Section: {lineage_element.get_text(strip=True)}")
            if description_element:
                extracted_text.append(f"Main Description Narrative: {description_element.get_text(strip=True)}")
                
            scraped_html_context = "\n".join(extracted_text)
    except Exception:
        pass

    # Layered Fallback Engine
    # Pulls from AllBud index snippets first to protect lineage data, then wide-web for missing terpene structures
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            context_fragments = [scraped_html_context] if scraped_html_context else []
            
            # If AllBud failed or was blocked, pull AllBud index snippets
            if not scraped_html_context or len(scraped_html_context) < 30:
                allbud_query = f'site:allbud.com/marijuana-strains/ "{strain_name}"'
                try:
                    allbud_results = [r for r in ddgs.text(allbud_query, max_results=2)]
                    for result in allbud_results:
                        context_fragments.append(f"AllBud Snippet: {result['body']}")
                except Exception:
                    pass
            
            # CRITICAL EXPANSION: Query the wider cannabis web explicitly looking for Terpene chemistry data
            terpene_query = f'"{strain_name}" strain "dominant terpenes" OR "terpene profile" caryophyllene limonene myrcene'
            try:
                terpene_results = [r for r in ddgs.text(terpene_query, max_results=3)]
                for result in terpene_results:
                    context_fragments.append(f"Chemical Profile Snippet: {result['body']}")
            except Exception:
                pass
                
            scraped_html_context = "\n".join(context_fragments)
    except Exception as e:
        if not scraped_html_context:
            scraped_html_context = f"All retrieval vectors exhausted. Error: {str(e)}"

    # Process via Llama-3.3-70b to interpret the combined context data
    url = "https://api.groq.com/openai/v1/chat/completions"
    api_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    system_prompt = (
        "You are a factual cannabis data extraction parser. Your sole objective is formatting the provided text data into structured JSON.\n"
        "Analyze the provided text fragments, snippets, or descriptions carefully to isolate the true genetic lineage and strain characteristics.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Identify the direct parent strains (e.g., 'Wedding Cake X Gelato #33') if mentioned anywhere in the narrative or snippets.\n"
        "2. Look for keywords like 'cross between', 'hybrid of', 'parents', or 'lineage'.\n"
        "3. Look for chemical context fragments to extract the dominant terpenes (e.g., 'Limonene, Myrcene, Caryophyllene'). Do not use generic fallback boilerplate for terpenes if chemical names show up in text.\n"
        "4. If the text does not explicitly reveal the parent genetics after deep inspection, return 'Proprietary / Unverified Genetics' for the lineage value.\n"
        "5. Filter out any noise, such as lists of unrelated similar strains or dispensary ads.\n\n"
        "Return ONLY a clean, valid JSON object containing exactly these keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects'."
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": f"Raw Retrieved Data:\n{scraped_html_context}\n\nTarget Strain to Extract: {strain_name}"}
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
    except Exception:
        pass
        
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

# Clean CSS layout configuration block
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
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

logo_path, logo_html = 'image.png', ""
if os.path.exists(logo_path):
    with open(logo_path, 'rb') as img_file:
        logo_html = f'<img src="data:image/png;base64,{base64.b64encode(img_file.read()).decode("utf-8")}" style="height: 196px; margin-right: 30px; border-radius: 8px;">'

st.markdown(f'<div class="brand-banner" style="padding: 50px 35px;">{logo_html}<div class="brand-text"><h1>Ziggyz Strain Sniffer & Operational Hub</h1><p>Inventory Logistics & Base Knowledge Management Engine</p></div></div>', unsafe_allow_html=True)
tab1, tab2 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE"])

with tab1:
    st.markdown("### 📥 Live Data Ingestion")
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
                    @page {{ size: A4; margin: 20mm; background-color: #0B0F19; }}
                    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #F9FAFB; background-color: #0B0F19; margin: 0; padding: 0; }}
                    .header {{ border-left: 6px solid #FDD835; padding-left: 15px; margin-bottom: 25px; }}
                    h1 {{ font-size: 26px; color: #FDD835; text-transform: uppercase; margin: 0; font-weight: bold; letter-spacing: -0.5px; }}
                    .subhead {{ color: #94A3B8; font-size: 12px; margin: 5px 0 0 0; }}
                    .summary-container {{ display: table; width: 100%; margin-top: 25px; margin-bottom: 30px; border-collapse: separate; border-spacing: 12px 0; }}
                    .metric-box {{ display: table-cell; width: 33.33%; background-color: #111827; border: 1px solid rgba(253, 216, 53, 0.15); border-radius: 6px; padding: 12px; text-align: center; vertical-align: middle; }}
                    .label {{ color: #FDD835; font-size: 9px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }}
                    .value {{ font-size: 22px; font-weight: bold; color: #F9FAFB; margin: 0; }}
                    table {{ width: 100%; border-collapse: collapse; background-color: #111827; border-radius: 8px; overflow: hidden; margin-top: 10px; }}
                    th {{ background-color: #1F2937; color: #FDD835; text-transform: uppercase; font-size: 11px; font-weight: bold; letter-spacing: 1px; padding: 12px; text-align: left; border-bottom: 2px solid rgba(253, 216, 53, 0.15); }}
                    td {{ padding: 12px; color: #E2E8F0; font-size: 13px; border-bottom: 1px solid rgba(148, 163, 184, 0.1); }}
                    tr:nth-child(even) {{ background-color: #161F30; }}
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
        query = st.text_input("AI Search Engine Input", placeholder="Type any strain name...", key="ai_search_box", label_visibility="collapsed").strip()
        
        if query:
            with st.spinner(f"Connecting to live data parameters for '{query}'..."):
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
        
        # Dedicated Cannabinoid & THC Variant Science Lookup Module
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
