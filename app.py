import streamlit as st
import pandas as pd
import base64
import os
import json
import requests
import re
import subprocess
import tempfile
import shutil
from urllib.parse import quote_plus
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from io import BytesIO

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, create_string_object, NumberObject
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

st.set_page_config(page_title="Ziggybot", page_icon="⚡", layout="wide")

# ── AI helpers (unchanged) ────────────────────────────────────────────────────
def generate_strain_profile(groq_key, strain_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    api_headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    system_prompt = (
        "You are a highly accurate cannabis strain database for a retail dispensary. "
        "Provide the most widely accepted genetic lineage, terpenes, flavor, and effects for the requested strain based on established industry knowledge. "
        "If the strain name is completely unrecognizable or clearly fictional, output 'Unknown strain, please check Google' for the lineage. "
        "Output clean, structured JSON. Keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects', 'cannabinoids'."
    )
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Target Strain: {strain_name}"}],
        "temperature": 0.1
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
    return {"classification": "HYBRID", "lineage": "N/A", "terpenes": "N/A", "flavor": "N/A", "effects": "N/A", "cannabinoids": "N/A"}

def get_compound_profile(api_key, compound_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system_prompt = "You are an advanced cannabinoid science database. Output JSON. Keys: 'status', 'primary_effects', 'medical_benefits', 'customer_pitch'."
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Profile for: {compound_name}"}], "temperature": 0.1}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content:
                content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
        return {"error": f"Status code {res.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def build_pdf(dataframe, threshold_value):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    subtitle_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#4B5563'), fontName='Helvetica-Bold', spaceAfter=20)
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#374151'))
    header_style = ParagraphStyle('HeaderText', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#0F172A'))
    story.append(Paragraph("Ziggyz Merchandise Gap Report", title_style))
    story.append(Paragraph("HIGH-IMPACT FLOOR RESTOCK & DISCREPANCY MANIFEST", subtitle_style))
    metric_data = [[Paragraph(f"<b>High-Impact Gaps:</b> {len(dataframe)}", cell_style), Paragraph(f"<b>Units to Move:</b> {dataframe['Available Qty'].sum()}", cell_style), Paragraph(f"<b>Min Threshold:</b> {threshold_value}+", cell_style)]]
    metric_table = Table(metric_data, colWidths=[180, 180, 172])
    metric_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')), ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')), ('PADDING', (0,0), (-1,-1), 12), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    story.append(metric_table)
    table_content = [[Paragraph("Product Name", header_style), Paragraph("Location", header_style), Paragraph("Available Qty", header_style)]]
    for _, row in dataframe.iterrows():
        table_content.append([Paragraph(str(row['Product Name']), cell_style), Paragraph(str(row['Location']), cell_style), Paragraph(str(row['Available Qty']), cell_style)])
    data_table = Table(table_content, colWidths=[312, 110, 110])
    data_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F3F4F6')), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')), ('PADDING', (0,0), (-1,-1), 8)]))
    story.append(data_table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

/* === VARIABLES === */
:root {
    --bg: #080C18;
    --s1: #0D1117;
    --s2: #161B2A;
    --s3: #1E2535;
    --purple: #8B5CF6;
    --purple-l: #A78BFA;
    --purple-d: rgba(139,92,246,0.12);
    --cyan: #22D3EE;
    --cyan-d: rgba(34,211,238,0.08);
    --green: #34D399;
    --green-d: rgba(52,211,153,0.08);
    --amber: #F59E0B;
    --text: #E2E8F0;
    --muted: #64748B;
    --dim: #94A3B8;
    --border: rgba(255,255,255,0.05);
    --b-purple: rgba(139,92,246,0.22);
    --b-cyan: rgba(34,211,238,0.18);
    --shadow: 0 8px 32px rgba(0,0,0,0.5);
    --gp: 0 0 28px rgba(139,92,246,0.28);
    --gc: 0 0 28px rgba(34,211,238,0.2);
    --gg: 0 0 20px rgba(52,211,153,0.28);
    --r: 14px;
    --rs: 9px;
    --ease: cubic-bezier(.4,0,.2,1);
    --t: .22s cubic-bezier(.4,0,.2,1);
}

/* === ANIMATIONS === */
@keyframes pulse-dot {
    0%,100% { opacity:1; transform:scale(1); box-shadow:0 0 0 0 rgba(52,211,153,.5); }
    50% { opacity:.7; transform:scale(.85); box-shadow:0 0 0 5px rgba(52,211,153,0); }
}
@keyframes gb { 0%,100%{background-position:0% 50%} 50%{background-position:100% 50%} }
@keyframes fade-up {
    from { opacity:0; transform:translateY(10px); }
    to { opacity:1; transform:translateY(0); }
}
@keyframes shimmer {
    from { transform:translateX(-120%) skewX(-20deg); }
    to { transform:translateX(400%) skewX(-20deg); }
}

/* === BASE === */
.stApp {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
}
.stApp::before {
    content:'';
    position:fixed;
    inset:0;
    background:
        radial-gradient(ellipse 65% 55% at 8% 4%, rgba(139,92,246,.09) 0%, transparent 65%),
        radial-gradient(ellipse 45% 35% at 92% 92%, rgba(34,211,238,.06) 0%, transparent 60%),
        radial-gradient(ellipse 30% 45% at 55% 45%, rgba(52,211,153,.03) 0%, transparent 65%);
    pointer-events:none;
    z-index:0;
}

/* === TYPOGRAPHY === */
h1,h2,h3,h4 { font-family:'Syne',sans-serif !important; color:var(--text) !important; }
h3 { font-size:17px !important; font-weight:800 !important; letter-spacing:-.2px !important; }
p  { color:var(--dim) !important; }
hr { border:none !important; height:1px !important; background:var(--border) !important; margin:22px 0 !important; }

/* === TABS === */
.stTabs [data-baseweb='tab-list'] {
    background: rgba(13,17,23,.92) !important;
    backdrop-filter: blur(24px) !important;
    border: 1px solid var(--b-purple) !important;
    border-radius: 50px !important;
    padding: 5px !important;
    gap: 2px !important;
    box-shadow: var(--shadow), inset 0 1px 0 rgba(255,255,255,.03) !important;
    margin-bottom: 24px !important;
}
.stTabs [data-baseweb='tab'] {
    background: transparent !important;
    border-radius: 50px !important;
    color: var(--muted) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 11px !important;
    letter-spacing: 1.2px !important;
    text-transform: uppercase !important;
    padding: 10px 22px !important;
    border: none !important;
    transition: all var(--t) !important;
}
.stTabs [data-baseweb='tab']:hover {
    color: var(--purple-l) !important;
    background: rgba(139,92,246,.08) !important;
}
.stTabs [aria-selected='true'] {
    background: linear-gradient(135deg,#8B5CF6,#5B21B6) !important;
    color: #fff !important;
    box-shadow: var(--gp), 0 4px 12px rgba(0,0,0,.3) !important;
}
.stTabs [data-baseweb='tab-highlight'],
.stTabs [data-baseweb='tab-border'] { display:none !important; }

/* === BUTTONS === */
.stButton > button {
    background: linear-gradient(135deg,#8B5CF6,#5B21B6) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--rs) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 11px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    padding: 13px 30px !important;
    box-shadow: var(--gp) !important;
    transition: all var(--t) !important;
    position: relative !important;
    overflow: hidden !important;
    width: 100% !important;
}
.stButton > button::after {
    content:'';
    position:absolute;
    top:0; left:-100%;
    width:55%; height:100%;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,.14),transparent);
    animation: shimmer 2.8s ease infinite;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 0 40px rgba(139,92,246,.55), 0 8px 28px rgba(0,0,0,.4) !important;
    background: linear-gradient(135deg,#A78BFA,#7C3AED) !important;
}
.stButton > button:active { transform:translateY(0) !important; }

.stDownloadButton > button {
    background: linear-gradient(135deg,#10B981,#065F46) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--rs) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 11px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    padding: 13px 30px !important;
    box-shadow: var(--gg) !important;
    transition: all var(--t) !important;
    width: 100% !important;
}
.stDownloadButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 0 40px rgba(52,211,153,.5), 0 8px 28px rgba(0,0,0,.4) !important;
}

/* === INPUTS === */
.stTextInput input, .stTextArea textarea {
    background: var(--s2) !important;
    border: 1px solid var(--b-purple) !important;
    border-radius: var(--rs) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    transition: all var(--t) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--purple) !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,.18), var(--gp) !important;
    outline: none !important;
}
.stTextInput input::placeholder { color:var(--muted) !important; }
.stTextInput label, .stSelectbox label,
.stFileUploader label, .stSlider label {
    color: var(--dim) !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 1.2px !important;
    text-transform: uppercase !important;
    font-family: 'Inter', sans-serif !important;
}
.stSelectbox > div > div {
    background: var(--s2) !important;
    border: 1px solid var(--b-purple) !important;
    border-radius: var(--rs) !important;
    color: var(--text) !important;
}

/* === FILE UPLOADER === */
[data-testid="stFileUploaderDropzone"] {
    background: rgba(22,27,42,.55) !important;
    border: 2px dashed var(--b-purple) !important;
    border-radius: var(--r) !important;
    transition: all var(--t) !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--purple) !important;
    background: rgba(139,92,246,.05) !important;
    box-shadow: var(--gp) !important;
}

/* === INSTRUCTION CARD === */
.instr-card {
    background: rgba(22,27,42,.7);
    border: 1px solid var(--b-purple);
    border-left: 3px solid var(--purple);
    border-radius: var(--r);
    padding: 16px 20px;
    margin-bottom: 14px;
    animation: fade-up .4s ease;
}
.instr-title {
    font-family: 'Syne', sans-serif;
    font-size: 13px;
    font-weight: 800;
    color: var(--purple-l);
    letter-spacing: .3px;
    margin-bottom: 12px;
    text-transform: uppercase;
}
.instr-steps { display: flex; flex-direction: column; gap: 9px; }
.instr-step {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: var(--dim);
    line-height: 1.5;
}
.instr-step strong { color: var(--text); }
.instr-icon {
    flex-shrink: 0;
    width: 22px; height: 22px;
    background: var(--purple-d);
    border: 1px solid var(--b-purple);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; font-weight: 700;
    color: var(--purple-l);
    margin-top: 1px;
}
.instr-icon.fire {
    background: rgba(245,158,11,.1);
    border-color: rgba(245,158,11,.3);
    color: var(--amber);
    font-size: 12px;
    width: 22px; height: 22px;
}

/* === ALERTS === */
[data-testid="stAlert"] {
    border-radius: var(--rs) !important;
    animation: fade-up .3s ease !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
}
[data-testid="stNotification"] { border-radius: var(--rs) !important; }
div[data-testid="stAlert"] > div {
    background: transparent !important;
}
.stSuccess  { background:rgba(52,211,153,.07)!important; border:1px solid rgba(52,211,153,.22)!important; border-left:3px solid var(--green)!important; color:#6EE7B7!important; border-radius:var(--rs)!important; }
.stError    { background:rgba(239,68,68,.07)!important;  border:1px solid rgba(239,68,68,.22)!important;  border-left:3px solid #EF4444!important; color:#FCA5A5!important; border-radius:var(--rs)!important; }
.stInfo     { background:rgba(34,211,238,.06)!important; border:1px solid rgba(34,211,238,.18)!important; border-left:3px solid var(--cyan)!important; color:#A5F3FC!important; border-radius:var(--rs)!important; }
.stWarning  { background:rgba(245,158,11,.06)!important; border:1px solid rgba(245,158,11,.18)!important; border-left:3px solid var(--amber)!important; border-radius:var(--rs)!important; }

/* === DATAFRAME === */
[data-testid="stDataFrame"] {
    border: 1px solid var(--b-purple) !important;
    border-radius: var(--r) !important;
    overflow: hidden !important;
    box-shadow: var(--shadow) !important;
}

/* === SCROLLBAR === */
::-webkit-scrollbar { width:4px; height:4px; }
::-webkit-scrollbar-track { background:var(--s1); }
::-webkit-scrollbar-thumb { background:var(--purple); border-radius:4px; }
::-webkit-scrollbar-thumb:hover { background:var(--purple-l); }

/* === HEADER === */
.hub-wrap {
    position: relative;
    border-radius: var(--r);
    padding: 2px;
    background: linear-gradient(135deg,#8B5CF6,#22D3EE,#34D399,#8B5CF6);
    background-size: 300% 300%;
    animation: gb 5s ease infinite;
    box-shadow: var(--gp);
}
.hub-inner {
    background: linear-gradient(145deg,#0F172A,#141D30);
    border-radius: calc(var(--r) - 2px);
    padding: 26px 30px;
}
.hub-status-row {
    display:flex; align-items:center; justify-content:space-between; margin-bottom:16px;
}
.hub-live {
    display:flex; align-items:center; gap:8px;
    background:rgba(52,211,153,.1); border:1px solid rgba(52,211,153,.25);
    border-radius:50px; padding:5px 14px 5px 10px;
    font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:700;
    color:var(--green); letter-spacing:1.5px; text-transform:uppercase;
}
.status-dot {
    width:7px; height:7px; background:var(--green);
    border-radius:50%; animation:pulse-dot 2.2s ease infinite;
    box-shadow:0 0 8px var(--green);
}
.hub-build {
    font-family:'JetBrains Mono',monospace; font-size:10px;
    color:var(--muted); letter-spacing:.5px;
}
.hub-title {
    font-family:'Syne',sans-serif !important;
    font-weight:800 !important; font-size:36px !important;
    color:#fff !important; letter-spacing:-1px !important;
    line-height:1 !important; margin:0 0 4px 0 !important;
}
.hub-title em { color:var(--purple-l); font-style:normal; }
.hub-sub {
    font-family:'Inter',sans-serif; font-size:11px; font-weight:600;
    color:var(--muted); letter-spacing:2.5px; text-transform:uppercase;
    margin-bottom:18px;
}
.hub-pills { display:flex; gap:8px; flex-wrap:wrap; margin-top:16px; }
.hpill {
    font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:700;
    padding:5px 13px; border-radius:50px; letter-spacing:.5px;
}
.hp-p { background:rgba(139,92,246,.13); border:1px solid rgba(139,92,246,.32); color:var(--purple-l); }
.hp-c { background:rgba(34,211,238,.09); border:1px solid rgba(34,211,238,.28); color:var(--cyan); }
.hp-g { background:rgba(52,211,153,.09); border:1px solid rgba(52,211,153,.28); color:var(--green); }

/* Quote */
.hub-quote {
    background: rgba(13,17,23,.65);
    border-radius: var(--r);
    padding: 16px 20px;
    margin-top: 12px;
    border-left: 3px solid var(--purple);
}
.hub-quote p {
    font-family:'Inter',sans-serif !important; font-size:13px !important;
    font-style:italic !important; color:var(--dim) !important;
    margin:0 !important; line-height:1.7 !important;
}
.hub-quote em { color:var(--purple-l); font-style:normal; font-weight:700; }

/* Section heading */
.sec-head {
    display:flex; align-items:center; gap:12px;
    margin:26px 0 18px 0; animation:fade-up .4s ease;
}
.sec-head-line { flex:1; height:1px; background:linear-gradient(90deg,var(--b-purple),transparent); }
.sec-head-text {
    font-family:'Syne',sans-serif; font-size:14px; font-weight:800;
    color:var(--text); letter-spacing:.3px; white-space:nowrap;
}

/* === STRAIN CARD === */
.sc {
    background: linear-gradient(150deg,#111827,#0F172A);
    border: 1px solid var(--b-purple);
    border-top: 2px solid var(--purple);
    border-radius: var(--r);
    padding: 26px 28px;
    margin-top: 14px;
    box-shadow: var(--shadow), inset 0 1px 0 rgba(255,255,255,.03);
    animation: fade-up .4s ease;
    position: relative; overflow: hidden;
}
.sc::before {
    content:''; position:absolute; top:0; right:0;
    width:180px; height:180px;
    background:radial-gradient(circle,rgba(139,92,246,.06) 0%,transparent 70%);
    pointer-events:none;
}
.sc-name {
    font-family:'Syne',sans-serif; font-size:28px; font-weight:800;
    color:#fff; letter-spacing:-.5px; line-height:1;
}
.sc-header-row {
    display:flex; align-items:center; gap:10px;
    margin-bottom:18px; flex-wrap:wrap;
}
.sc-badge {
    font-family:'JetBrains Mono',monospace; font-size:9px; font-weight:700;
    padding:5px 13px; border-radius:50px; letter-spacing:2px; text-transform:uppercase;
}
.sb-sativa { background:rgba(16,185,129,.13); border:1px solid rgba(16,185,129,.35); color:#34D399; }
.sb-indica { background:rgba(59,130,246,.13); border:1px solid rgba(59,130,246,.35); color:#93C5FD; }
.sb-hybrid { background:rgba(139,92,246,.13); border:1px solid rgba(139,92,246,.35); color:var(--purple-l); }
.sc-div { height:1px; background:linear-gradient(90deg,var(--b-purple),transparent); margin-bottom:20px; }
.sc-grid {
    display:grid; grid-template-columns:1fr 1fr; gap:16px;
}
.sc-attr { display:flex; flex-direction:column; gap:5px; }
.sc-attr-full { grid-column:1 / -1; }
.attr-label {
    font-family:'JetBrains Mono',monospace; font-size:9px; font-weight:700;
    color:var(--purple-l); letter-spacing:2px; text-transform:uppercase;
}
.attr-val {
    font-family:'Inter',sans-serif; font-size:13px;
    color:var(--dim); line-height:1.55;
}
.attr-val-hi { color:var(--cyan) !important; }

/* === COMPOUND CARD === */
.cc {
    background: linear-gradient(150deg,#0E1628,#0F172A);
    border: 1px solid var(--b-cyan);
    border-top: 2px solid var(--cyan);
    border-radius: var(--r);
    padding: 26px 28px;
    margin-top: 14px;
    box-shadow: var(--shadow), inset 0 1px 0 rgba(34,211,238,.04);
    animation: fade-up .4s ease;
}
.cc-name {
    font-family:'Syne',sans-serif; font-size:26px; font-weight:800;
    color:var(--cyan); letter-spacing:-.5px; margin-bottom:16px;
}
.cc-div { height:1px; background:linear-gradient(90deg,var(--b-cyan),transparent); margin-bottom:18px; }

/* === METRIC TILES === */
.metric-row { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px; }
.m-tile {
    background:var(--s2); border:1px solid var(--border);
    border-radius:var(--rs); padding:16px 18px;
    text-align:center; position:relative; overflow:hidden;
}
.m-tile::before {
    content:''; position:absolute; top:0; left:0; right:0; height:2px;
    background:linear-gradient(90deg,var(--purple),var(--cyan));
}
.m-num {
    font-family:'JetBrains Mono',monospace; font-size:30px;
    font-weight:700; color:#fff; line-height:1;
}
.m-lbl {
    font-family:'Inter',sans-serif; font-size:10px; font-weight:700;
    color:var(--muted); letter-spacing:1.5px; text-transform:uppercase; margin-top:5px;
}

/* === STEP CARDS (Tab 3) === */
.step-card {
    background: var(--s2);
    border: 1px solid var(--b-purple);
    border-radius: var(--r);
    padding: 20px 24px;
    margin-bottom: 12px;
    animation: fade-up .4s ease;
}
.step-header { display:flex; align-items:center; gap:14px; }
.step-num {
    width:30px; height:30px; border-radius:50%; flex-shrink:0;
    background:linear-gradient(135deg,#8B5CF6,#5B21B6);
    display:flex; align-items:center; justify-content:center;
    font-family:'JetBrains Mono',monospace; font-size:12px;
    font-weight:700; color:#fff; box-shadow:var(--gp);
}
.step-ttl {
    font-family:'Syne',sans-serif; font-size:14px; font-weight:800; color:var(--text);
}
.step-dsc {
    font-family:'Inter',sans-serif; font-size:12px; color:var(--muted); margin-top:2px;
}

/* Google button */
.g-btn {
    display:inline-flex; align-items:center; gap:6px;
    background:linear-gradient(135deg,#8B5CF6,#5B21B6);
    color:#fff !important; text-decoration:none !important;
    padding:9px 18px; border-radius:var(--rs);
    font-family:'Inter',sans-serif; font-size:11px; font-weight:700;
    letter-spacing:1px; text-transform:uppercase;
    box-shadow:var(--gp); transition:all var(--t);
    margin-bottom:14px; display:inline-flex;
}
.g-btn:hover { transform:translateY(-2px); box-shadow:0 0 36px rgba(139,92,246,.5); }

/* misc */
.stSpinner > div { border-top-color:var(--purple) !important; }
</style>
""", unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
col_vid, col_hdr = st.columns([1, 1])

with col_vid:
    with open('video.mp4', 'rb') as vf:
        st.video(vf.read(), loop=True, autoplay=True, muted=True)

with col_hdr:
    st.markdown("""
    <div class="hub-wrap">
      <div class="hub-inner">
        <div class="hub-status-row">
          <div class="hub-live"><span class="status-dot"></span>System Online</div>
          <span class="hub-build">ZIGGYBOT · v2.0</span>
        </div>
        <div class="hub-title">ZIGGY'S<em>BOT</em></div>
        <div class="hub-sub">Dispensary Intelligence Platform</div>
        <div class="hub-pills">
          <span class="hpill hp-p">⚡ Strain AI</span>
          <span class="hpill hp-c">📊 Inventory</span>
          <span class="hpill hp-g">🏷️ Hook Tags</span>
        </div>
      </div>
    </div>
    <div class="hub-quote">
      <p>"Your attitude, not your aptitude, will determine your altitude." — <em>Zig Ziglar</em></p>
    </div>
    """, unsafe_allow_html=True)

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["⚡  STRAIN SNIFFER", "📊  INVENTORY INTEL", "🏷️  HOOK TAG GENERATOR"])

# ── TAB 1 ─────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="sec-head"><div class="sec-head-text">⚡ Verified AI Strain Profiler</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    with st.form("strain_form", clear_on_submit=True):
        user_input = st.text_input("Strain Name", placeholder="e.g., Permanent Marker, Bacio Gelato…")
        submitted = st.form_submit_button("🔍  SEARCH STRAIN")

    if submitted and user_input:
        st.session_state.last_strain = user_input
        st.rerun()

    if "last_strain" in st.session_state and st.session_state.last_strain:
        strain = st.session_state.last_strain
        google_url = f"https://www.google.com/search?q={quote_plus(strain + ' strain')}"
        st.markdown(f'<a href="{google_url}" target="_blank" class="g-btn">🔎 More results for {strain}</a>', unsafe_allow_html=True)

        data = generate_strain_profile(st.secrets["GROQ_API_KEY"], strain)
        if "error" not in data:
            clf  = str(data.get('classification', 'HYBRID')).upper()
            bcls = "sb-sativa" if "SATIVA" in clf else ("sb-indica" if "INDICA" in clf else "sb-hybrid")
            st.markdown(f"""
            <div class="sc">
              <div class="sc-header-row">
                <div class="sc-name">{strain.upper()}</div>
                <span class="sc-badge {bcls}">{clf}</span>
              </div>
              <div class="sc-div"></div>
              <div class="sc-grid">
                <div class="sc-attr sc-attr-full">
                  <div class="attr-label">🌿 Lineage</div>
                  <div class="attr-val">{data.get('lineage','—')}</div>
                </div>
                <div class="sc-attr">
                  <div class="attr-label">🧪 Terpenes</div>
                  <div class="attr-val">{data.get('terpenes','—')}</div>
                </div>
                <div class="sc-attr">
                  <div class="attr-label">🍋 Flavor</div>
                  <div class="attr-val">{data.get('flavor','—')}</div>
                </div>
                <div class="sc-attr">
                  <div class="attr-label">⚡ Cannabinoids</div>
                  <div class="attr-val attr-val-hi">{data.get('cannabinoids','—')}</div>
                </div>
                <div class="sc-attr">
                  <div class="attr-label">🧠 Effects</div>
                  <div class="attr-val">{data.get('effects','—')}</div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)
        st.session_state.last_strain = None

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="sec-head"><div class="sec-head-text">🧪 Cannabinoid Encyclopedia</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    col_sel, col_cust = st.columns([2, 2])
    with col_sel:
        selected_chem = st.selectbox("Quick-select compound", ["— Choose —", "THC", "THCV", "THCP", "CBD", "CBG", "CBN", "Delta-8 THC"])
    with col_cust:
        custom_chem = st.text_input("Or enter a variant", placeholder="e.g., THCO, CBDA…").strip()

    target_chem = custom_chem if custom_chem else (None if selected_chem == "— Choose —" else selected_chem)
    if target_chem:
        chem_data = get_compound_profile(st.secrets["GROQ_API_KEY"], target_chem)
        if "error" not in chem_data:
            st.markdown(f"""
            <div class="cc">
              <div class="cc-name">🔬 {target_chem.upper()}</div>
              <div class="cc-div"></div>
              <div class="sc-grid">
                <div class="sc-attr">
                  <div class="attr-label">🧠 Primary Effects</div>
                  <div class="attr-val">{chem_data.get('primary_effects','—')}</div>
                </div>
                <div class="sc-attr">
                  <div class="attr-label">🩺 Medical Benefits</div>
                  <div class="attr-val">{chem_data.get('medical_benefits','—')}</div>
                </div>
                <div class="sc-attr sc-attr-full">
                  <div class="attr-label">🎯 Budtender Pitch</div>
                  <div class="attr-val attr-val-hi" style="font-style:italic;">"{chem_data.get('customer_pitch','—')}"</div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

# ── TAB 2 ─────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="sec-head"><div class="sec-head-text">📊 Live Restock Gap Analyzer</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="instr-card">
      <div class="instr-title">📋 How to Export from Dutchie</div>
      <div class="instr-steps">
        <div class="instr-step">
          <span class="instr-icon">1</span>
          <span>In Dutchie Backoffice, select <strong>any 2 rooms</strong> &amp; <strong>one category</strong></span>
        </div>
        <div class="instr-step">
          <span class="instr-icon fire">🔥</span>
          <span>Export only <strong>Product</strong>, <strong>Room</strong>, &amp; <strong>Quantity</strong></span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(" ", type="csv", key="restock_csv", label_visibility="collapsed")
    min_threshold = st.slider("Minimum stock threshold", 1, 50, 15)

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        df.columns = [str(col).strip('="').strip() for col in df.columns]
        qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col][0]
        df['Product'] = df['Product'].apply(lambda x: str(x).strip('="').strip())
        df['Room']    = df['Room'].apply(lambda x: str(x).strip('="').strip())
        df['Qty']     = pd.to_numeric(df[qty_col].apply(lambda x: str(x).strip('="').strip()), errors='coerce').fillna(0)
        pivot   = df.groupby(['Product', 'Room'])['Qty'].sum().unstack(fill_value=0)
        results = [{"Product Name": p, "Location": r, "Available Qty": int(row[r])}
                   for p, row in pivot.iterrows() if (row == 0).any()
                   for r in row[row >= min_threshold].index]
        final_df = pd.DataFrame(results)

        if not final_df.empty:
            # Metric tiles
            total_gaps  = len(final_df)
            total_units = int(final_df['Available Qty'].sum())
            locations   = final_df['Location'].nunique()
            st.markdown(f"""
            <div class="metric-row">
              <div class="m-tile"><div class="m-num">{total_gaps}</div><div class="m-lbl">Gap Lines</div></div>
              <div class="m-tile"><div class="m-num">{total_units}</div><div class="m-lbl">Units to Move</div></div>
              <div class="m-tile"><div class="m-num">{locations}</div><div class="m-lbl">Locations</div></div>
            </div>""", unsafe_allow_html=True)

            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.download_button("📥  Download Restock PDF", build_pdf(final_df, min_threshold), "Ziggy_Report.pdf", "application/pdf")

# ── TAB 3 ─────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="sec-head"><div class="sec-head-text">🏷️ Automated Hook Tag Formatter</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    TEMPLATE_PATH = "master_template.pdf"

    # Dependency checks
    if not PYPDF_AVAILABLE:
        st.error("pypdf not installed — add `pypdf` to requirements.txt and redeploy.")
        st.stop()
    try:
        subprocess.run(["pdftk", "--version"], capture_output=True, check=True)
        pdftk_ok = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pdftk_ok = False
    if not pdftk_ok:
        st.error("pdftk not found — add `pdftk` to packages.txt and redeploy.")
        st.stop()
    if not os.path.exists(TEMPLATE_PATH):
        st.error("`master_template.pdf` not found — commit it to the root of your repo.")
        st.stop()

    # Auto-detect slot map (cached)
    @st.cache_resource
    def load_slot_map(path):
        reader, slot_map = PdfReader(path), {}
        for fname, field in (reader.get_fields() or {}).items():
            v = field.get("/V", "")
            if not isinstance(v, str): continue
            vs = v.strip()
            for prefix, key in [("BRAND_","brand"),("STRAIN_","strain"),("THC_","thc"),("PRICE_","price")]:
                if vs.startswith(prefix):
                    try:
                        slot_map.setdefault(int(vs[len(prefix):].strip()), {})[key] = fname
                    except ValueError:
                        pass
        return slot_map

    slot_map = load_slot_map(TEMPLATE_PATH)
    if not slot_map:
        st.error("Template doesn't contain BRAND_N/STRAIN_N/THC_N/PRICE_N placeholders.")
        st.stop()

    slots_per_page = max(slot_map.keys())

    # Step UI
    st.markdown(f"""
    <div class="step-card">
      <div class="step-header">
        <div class="step-num">1</div>
        <div>
          <div class="step-ttl">Export &amp; Upload Inventory CSV</div>
          <div class="step-dsc">{slots_per_page} tags per sheet · duplicates auto-removed</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class="instr-card">
      <div class="instr-title">📋 How to Export from Dutchie</div>
      <div class="instr-steps">
        <div class="instr-step">
          <span class="instr-icon">1</span>
          <span>In Dutchie Backend, select any combination of <strong>product, room, category</strong>, etc.</span>
        </div>
        <div class="instr-step">
          <span class="instr-icon fire">🔥</span>
          <span>Export only <strong>Product</strong>, <strong>THC</strong>, &amp; <strong>Current Price</strong></span>
        </div>
        <div class="instr-step">
          <span class="instr-icon fire">🔥</span>
          <span>One tag per unique product — same strain with <strong>different THC %</strong> each gets its own tag</span>
        </div>
        <div class="instr-step">
          <span class="instr-icon fire">🔥</span>
          <span>Save additional tags for <strong>future use</strong> — re-upload anytime</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    hook_file = st.file_uploader(" ", type=["csv"], key="hook_csv", label_visibility="collapsed")

    if hook_file is None:
        st.markdown("""
        <div class="step-card" style="opacity:.45;">
          <div class="step-header">
            <div class="step-num">2</div>
            <div><div class="step-ttl">Review &amp; Generate</div>
            <div class="step-dsc">Upload a CSV above to continue</div></div>
          </div>
        </div>""", unsafe_allow_html=True)
        st.stop()

    # Parse CSV
    df_hook = pd.read_csv(hook_file)
    df_hook.columns = [str(c).strip('="').strip() for c in df_hook.columns]
    price_col = "Current price" if "Current price" in df_hook.columns else "Price"

    raw_rows = []
    for _, row in df_hook.iterrows():
        product = str(row.get("Product", "")).strip('="').strip()
        if not product or product.lower() == "nan":
            continue
        parts  = [p.strip() for p in product.split("|")]
        brand  = parts[0].upper()  if len(parts) >= 1 else ""
        strain = parts[1].upper()  if len(parts) >= 2 else product.upper()
        thc    = str(row.get("THC", "")).strip()
        rp     = str(row.get(price_col, "0")).replace("$", "").strip('="').strip()
        pd_    = "".join(c for c in rp if c.isdigit() or c == ".")
        try:
            pv    = float(pd_) if pd_ else 0.0
            price = f"${int(pv)}" if pv == int(pv) else f"${pv:.2f}"
        except ValueError:
            price = "$0"
        raw_rows.append({"brand": brand, "strain": strain, "thc": thc, "price": price})

    if not raw_rows:
        st.error("No valid product rows found in the CSV.")
        st.stop()

    # Deduplicate on (brand, strain, thc)
    seen, rows = set(), []
    for r in raw_rows:
        key = (r["brand"].strip().lower(), r["strain"].strip().lower(), r["thc"].strip().lower())
        if key not in seen:
            seen.add(key)
            rows.append(r)

    n_pages = -(-len(rows) // slots_per_page)

    st.markdown(f"""
    <div class="step-card">
      <div class="step-header">
        <div class="step-num">2</div>
        <div>
          <div class="step-ttl">Review Tag Summary</div>
          <div class="step-dsc">{len(rows)} unique tags detected across {n_pages} sheet(s) · {len(raw_rows) - len(rows)} duplicates removed</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # Preview table
    preview = pd.DataFrame(rows)[["brand", "strain", "thc", "price"]]
    preview.columns = ["Brand", "Strain / Product", "THC", "Price"]
    st.dataframe(preview, use_container_width=True, hide_index=True)

    st.markdown("""
    <div class="step-card">
      <div class="step-header">
        <div class="step-num">3</div>
        <div>
          <div class="step-ttl">Generate &amp; Download</div>
          <div class="step-dsc">Fills the template using the original Paralucent-Heavy font with true autosize</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    def _esc(s):
        return s.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")

    def make_fdf(page_rows):
        entries = []
        for slot in range(1, slots_per_page + 1):
            d  = page_rows[slot - 1] if slot - 1 < len(page_rows) else {}
            sf = slot_map.get(slot, {})
            for key, val in [("brand",d.get("brand","")),("strain",d.get("strain","")),("thc",d.get("thc","")),("price",d.get("price",""))]:
                fn = sf.get(key)
                if fn:
                    entries.append(f"<</T ({_esc(fn)})/V ({_esc(val)})>>")
        return "%FDF-1.2\n1 0 obj\n<< /FDF << /Fields [\n" + "\n".join(entries) + "\n] >> >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"

    if st.button("🖨️  GENERATE PRINT-READY TAGS", type="primary"):
        pages = [rows[i:i+slots_per_page] for i in range(0, len(rows), slots_per_page)]
        with st.spinner(f"Filling {len(rows)} tags across {len(pages)} sheet(s)…"):
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    page_paths, err = [], None
                    for i, pg in enumerate(pages):
                        fp = os.path.join(tmp, f"p{i}.fdf")
                        op = os.path.join(tmp, f"p{i}.pdf")
                        with open(fp, "w", encoding="latin-1") as f:
                            f.write(make_fdf(pg))
                        r = subprocess.run(["pdftk", TEMPLATE_PATH, "fill_form", fp, "output", op], capture_output=True, text=True)
                        if r.returncode != 0:
                            err = f"pdftk error on sheet {i+1}: {r.stderr.strip()}"
                            break
                        page_paths.append(op)

                    if err:
                        st.error(err)
                        st.stop()

                    if len(page_paths) == 1:
                        final = page_paths[0]
                    else:
                        final = os.path.join(tmp, "merged.pdf")
                        r = subprocess.run(["pdftk"] + page_paths + ["cat", "output", final], capture_output=True, text=True)
                        if r.returncode != 0:
                            st.error(f"Merge error: {r.stderr.strip()}")
                            st.stop()

                    with open(final, "rb") as f:
                        pdf_bytes = f.read()

            except FileNotFoundError:
                st.error("pdftk not found — add `pdftk` to packages.txt.")
                st.stop()
            except Exception as e:
                st.error(f"Unexpected error: {e}")
                st.stop()

        st.success(f"✅ {len(rows)} tags across {len(pages)} sheet(s) — ready to print!")
        st.download_button("📥  DOWNLOAD HOOK TAGS PDF", pdf_bytes, "HookTags_Ready.pdf", "application/pdf")
