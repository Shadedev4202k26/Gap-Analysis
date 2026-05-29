import streamlit as st, pandas as pd, base64, os, json, requests
from weasyprint import HTML

st.set_page_config(page_title="Smilez Hub", layout="wide")

def get_strain_profile(api_key, strain_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = (
        "You are an expert cannabis laboratory database. Analyze the strain and return ONLY a valid JSON object. "
        "CRITICAL: Do not use double quotes inside any text values (use single quotes or plain text instead). "
        "The JSON must contain exactly these keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects'."
    )
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Provide data for: {strain_name}"}], "temperature": 0.1}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
        return {"error": f"Status code {res.status_code}"}
    except Exception as e: return {"error": str(e)}

st.title("⚡ SMILEZ OPERATIONAL HUB")
tab1, tab2 = st.tabs(["📊 INVENTORY INTELLIGENCE", "🔍 AI KNOWLEDGE BASE"])

with tab1:
    st.markdown("### 📥 Live Data Ingestion")
    uploaded_file = st.file_uploader("Drop Dutchie CSV Export Here", type="csv")
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
                st.metric("High-Impact Gaps Found", len(final_df))
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                pdf_out = HTML(string=f"<html><body><h2>Smilez Gap Report</h2>{final_df.to_html()}</body></html>").write_pdf()
                st.download_button("📥 DOWNLOAD MERCHANDISING PDF", pdf_out, "Smilez_Report.pdf", "application/pdf")
            else:
                st.info("No gaps found matching the 15+ unit threshold.")
        except Exception as e: st.error(f"Analysis Error: {e}")

with tab2:
    st.markdown("### 🔍 Real-Time AI Strain Profiler")
    if "GROQ_API_KEY" not in st.secrets:
        st.error("🔒 GROQ_API_KEY missing from Streamlit secrets vault.")
    else:
        query = st.text_input("AI Search Engine Input", placeholder="Type strain name...").strip()
        if query:
            with st.spinner(f"Analyzing '{query}'..."):
                data = get_strain_profile(st.secrets["GROQ_API_KEY"], query)
                if "error" not in data:
                    clf = str(data.get('classification', 'HYBRID')).upper()
                    st.subheader(f"✨ {query.upper()} ({clf})")
                    st.markdown(f"**🌿 Genetic Lineage:**\n{data.get('lineage', 'N/A')}")
                    st.markdown(f"**🧪 Dominant Terpenes:**\n{data.get('terpenes', 'N/A')}")
                    st.markdown(f"**🍋 Flavor Profile:**\n{data.get('flavor', 'N/A')}")
                    st.markdown(f"**🧠 Reported Consumer Effects:**\n{data.get('effects', 'N/A')}")
                else: st.error(f"Engine connection blip: {data['error']}")
