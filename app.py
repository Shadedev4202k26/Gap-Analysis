import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os, json, requests, re, subprocess, tempfile, shutil, random
from urllib.parse import quote_plus
from datetime import date, datetime, timezone
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from io import BytesIO
from collections import defaultdict

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

try:
    from crossword_data import get_flat_word_list
    from crossword_gen import generate_crossword
    CROSSWORD_AVAILABLE = True
except ImportError:
    CROSSWORD_AVAILABLE = False

try:
    from hangman_data import get_hangman_entries
    HANGMAN_AVAILABLE = True
except ImportError:
    HANGMAN_AVAILABLE = False

try:
    import preroll_tags
    PREROLL_AVAILABLE = True
except ImportError:
    PREROLL_AVAILABLE = False

st.set_page_config(page_title="ZiggyBot", page_icon="⚡", layout="wide")

# ── Supabase client ───────────────────────────────────────────────────────────
@st.cache_resource
def init_supabase():
    if not SUPABASE_AVAILABLE:
        return None
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, FileNotFoundError):
        return None
    # Normalise the URL: the client appends /rest/v1/... itself, so the secret
    # must be the bare project origin. Strip whitespace, trailing slashes, and any
    # accidentally-included path (e.g. a pasted /rest/v1) that would corrupt the
    # request path and trigger PostgREST PGRST125 "Invalid path" errors.
    url = (url or "").strip()
    for suffix in ("/rest/v1", "/rest"):
        if url.rstrip("/").endswith(suffix):
            url = url.rstrip("/")[: -len(suffix)]
    url = url.rstrip("/")
    key = (key or "").strip()
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None

# ── AI helpers ────────────────────────────────────────────────────────────────
def generate_strain_profile(groq_key, strain_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    system = ("You are a highly accurate cannabis strain database for a retail dispensary. "
              "Provide the most widely accepted genetic lineage, terpenes, flavor, and effects. "
              "If unrecognizable, output 'Unknown strain, please check Google' for lineage. "
              "Output clean JSON. Keys: classification, lineage, terpenes, flavor, effects, cannabinoids.")
    payload = {"model": "llama-3.3-70b-versatile",
               "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": f"Target Strain: {strain_name}"}],
               "temperature": 0.1}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=12)
        if r.status_code == 200:
            c = r.json()['choices'][0]['message']['content'].strip()
            if "{" in c and "}" in c:
                c = c[c.find("{"):c.rfind("}") + 1]
            return json.loads(c)
    except Exception as e:
        return {"error": str(e)}
    return {"classification": "HYBRID", "lineage": "N/A", "terpenes": "N/A",
            "flavor": "N/A", "effects": "N/A", "cannabinoids": "N/A"}

def get_compound_profile(api_key, compound_name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system = "You are an advanced cannabinoid science database. Output JSON. Keys: status, primary_effects, medical_benefits, customer_pitch."
    payload = {"model": "llama-3.1-8b-instant",
               "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": f"Profile for: {compound_name}"}],
               "temperature": 0.1}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            c = r.json()['choices'][0]['message']['content'].strip()
            if "{" in c and "}" in c:
                c = c[c.find("{"):c.rfind("}") + 1]
            return json.loads(c)
        return {"error": f"Status {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def build_pdf(dataframe, threshold_value, rooms, min_stock=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=36, leftMargin=36, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=styles['Heading1'], fontSize=22,
                        textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    ss = ParagraphStyle('S', parent=styles['Normal'], fontSize=11,
                        textColor=colors.HexColor('#4B5563'), fontName='Helvetica-Bold', spaceAfter=18)
    cs = ParagraphStyle('C', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#374151'), leading=11)
    hs = ParagraphStyle('H', parent=styles['Normal'], fontSize=9,
                        fontName='Helvetica-Bold', textColor=colors.HexColor('#FFFFFF'))

    n_rebal = int(dataframe["Status"].str.contains("Rebalance").sum())
    n_bal   = len(dataframe) - n_rebal

    story = [Paragraph("Ziggyz Room Balance Report", ts),
             Paragraph("STOCK MIX &amp; ROOM BALANCE MANIFEST", ss)]
    rule_txt = f"<b>Imbalance:</b> &gt;{threshold_value}%"
    if min_stock is not None:
        rule_txt += f" &nbsp;·&nbsp; <b>Min stock:</b> &le;{min_stock}"
    md = [[Paragraph(f"<b>Products:</b> {len(dataframe)}", cs),
           Paragraph(f"<b>Rebalance:</b> {n_rebal}", cs),
           Paragraph(f"<b>Balanced:</b> {n_bal}", cs),
           Paragraph(rule_txt, cs)]]
    mt = Table(md, colWidths=[110, 110, 110, 186])
    mt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F8FAFC')),
                             ('BOX',(0,0),(-1,-1),1,colors.HexColor('#E5E7EB')),
                             ('INNERGRID',(0,0),(-1,-1),0.5,colors.HexColor('#E5E7EB')),
                             ('PADDING',(0,0),(-1,-1),10),('ALIGN',(0,0),(-1,-1),'CENTER')]))
    story.append(mt)
    story.append(Paragraph("Rooms: " + ", ".join(rooms), ss))

    # Header: Product | [each room qty] | Total | Mix % | Status
    header = [Paragraph("Product", hs)]
    for r in rooms:
        header.append(Paragraph(r, hs))
    header += [Paragraph("Total", hs), Paragraph("Mix %", hs), Paragraph("Status", hs)]
    tdata = [header]

    for _, row in dataframe.iterrows():
        cells = [Paragraph(str(row['Product Name']), cs)]
        for r in rooms:
            cells.append(Paragraph(str(row[r]), cs))
        cells.append(Paragraph(str(row['Total']), cs))
        cells.append(Paragraph(str(row['Mix %']), cs))
        status_txt = str(row['Status']).replace("🔄", "").replace("✅", "").strip()
        cells.append(Paragraph(status_txt, cs))
        tdata.append(cells)

    n_rooms = len(rooms)
    room_w = min(70, 150 / max(1, n_rooms))
    prod_w = 150
    total_w, mix_w, status_w = 40, 110, 78
    col_widths = [prod_w] + [room_w]*n_rooms + [total_w, mix_w, status_w]

    dt = Table(tdata, colWidths=col_widths, repeatRows=1)
    style = [('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1E293B')),
             ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#E5E7EB')),
             ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
             ('PADDING',(0,0),(-1,-1),5),
             ('ALIGN',(1,0),(-1,-1),'CENTER'),
             ('ALIGN',(0,0),(0,-1),'LEFT')]
    # Amber bar on rows needing a rebalance; faint green bar on balanced ones
    for i, (_, row) in enumerate(dataframe.iterrows(), start=1):
        if "Rebalance" in str(row['Status']):
            style.append(('LINEBEFORE',(0,i),(0,i),3,colors.HexColor('#D97706')))
        else:
            style.append(('LINEBEFORE',(0,i),(0,i),3,colors.HexColor('#34D399')))
    dt.setStyle(TableStyle(style))
    story.append(dt)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def build_aging_pdf(watch_items, summary, today_date, watch_days=45, exp_soon_days=60):
    """Build a print-ready PDF of the aging-stock watch list, grouped by
    category and color-coded by severity. `watch_items` is the list of
    aggregated product dicts; `summary` is a dict of headline counts."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=36, leftMargin=36, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=styles['Heading1'], fontSize=22,
                        textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    ss = ParagraphStyle('S', parent=styles['Normal'], fontSize=11,
                        textColor=colors.HexColor('#4B5563'), fontName='Helvetica-Bold', spaceAfter=14)
    note = ParagraphStyle('N', parent=styles['Normal'], fontSize=8,
                          textColor=colors.HexColor('#6B7280'), spaceAfter=18, leading=11)
    cs = ParagraphStyle('C', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#374151'), leading=11)
    cs_b = ParagraphStyle('CB', parent=cs, fontName='Helvetica-Bold')
    hs = ParagraphStyle('H', parent=styles['Normal'], fontSize=9,
                        fontName='Helvetica-Bold', textColor=colors.HexColor('#FFFFFF'))
    cat_style = ParagraphStyle('Cat', parent=styles['Normal'], fontSize=11,
                               fontName='Helvetica-Bold', textColor=colors.HexColor('#5B21B6'),
                               spaceBefore=14, spaceAfter=6)

    def sev_color(age):
        if age >= 90: return colors.HexColor('#DC2626')   # red
        if age >= 60: return colors.HexColor('#D97706')   # amber
        return colors.HexColor('#2563EB')                 # blue

    story = [Paragraph("Ziggyz Aging Stock Watch List", ts),
             Paragraph(f"PRODUCTS AGED {watch_days}+ DAYS &nbsp;·&nbsp; GENERATED {today_date.strftime('%B %-d, %Y')}", ss)]

    # Summary band
    md = [[Paragraph(f"<b>Aging SKUs:</b> {summary['watch_count']}", cs),
           Paragraph(f"<b>Units Stuck:</b> {summary['watch_units']}", cs),
           Paragraph(f"<b>Expiring &lt;{exp_soon_days}d:</b> {summary['expiring']}", cs),
           Paragraph(f"<b>Total SKUs:</b> {summary['total_skus']}", cs)]]
    mt = Table(md, colWidths=[124, 124, 134, 124])
    mt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F8FAFC')),
                             ('BOX',(0,0),(-1,-1),1,colors.HexColor('#E5E7EB')),
                             ('INNERGRID',(0,0),(-1,-1),0.5,colors.HexColor('#E5E7EB')),
                             ('PADDING',(0,0),(-1,-1),10),('ALIGN',(0,0),(-1,-1),'CENTER')]))
    story.append(mt)
    story.append(Paragraph(
        "Watch list to investigate — age is a proxy for stagnation, not proof of non-sales. "
        "Review each item before discounting or pulling.", note))

    # Group by category, ordered by oldest item
    by_cat = defaultdict(list)
    for v in watch_items:
        by_cat[v["cat"]].append(v)
    cat_order = sorted(by_cat.keys(), key=lambda c: -max(v["age"] for v in by_cat[c]))

    for cat in cat_order:
        items = sorted(by_cat[cat], key=lambda v: -v["age"])
        oldest = items[0]["age"]
        story.append(Paragraph(f"{cat or 'Uncategorized'} &nbsp;—&nbsp; {len(items)} item(s), oldest {oldest}d", cat_style))

        header = [Paragraph("Age", hs), Paragraph("Product", hs),
                  Paragraph("Brand", hs), Paragraph("Qty", hs),
                  Paragraph("Rooms", hs), Paragraph("Flags", hs)]
        tdata = [header]
        row_colors = []
        for v in items:
            flags = []
            if v["days_to_exp"] is not None and v["days_to_exp"] < exp_soon_days:
                flags.append("EXPIRED" if v["days_to_exp"] < 0 else f"EXP {v['days_to_exp']}d")
            if v["on_sale"]:
                flags.append("ON SALE")
            rooms = ", ".join(sorted(v["rooms"])) if v["rooms"] else "—"
            tdata.append([
                Paragraph(f'<b>{v["age"]}d</b>', cs_b),
                Paragraph(v["product"], cs),
                Paragraph(v["brand"] or "—", cs),
                Paragraph(str(v["qty"]), cs),
                Paragraph(rooms, cs),
                Paragraph(", ".join(flags) if flags else "—", cs),
            ])
            row_colors.append(sev_color(v["age"]))

        tbl = Table(tdata, colWidths=[34, 168, 96, 30, 120, 92], repeatRows=1)
        style = [('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1E293B')),
                 ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#E5E7EB')),
                 ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                 ('PADDING',(0,0),(-1,-1),5),
                 ('ALIGN',(0,0),(0,-1),'CENTER'),
                 ('ALIGN',(3,0),(3,-1),'CENTER')]
        # Severity color bar on the Age cell of each data row
        for i, c in enumerate(row_colors, start=1):
            style.append(('TEXTCOLOR',(0,i),(0,i),c))
            style.append(('LINEBEFORE',(0,i),(0,i),3,c))
        tbl.setStyle(TableStyle(style))
        story.append(tbl)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def fmt_ts(ts_str):
    """Format Supabase ISO timestamp → friendly local-ish time string."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%-I:%M %p · %b %-d")
    except Exception:
        return ts_str or ""

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');
:root {
    --bg:#080C18; --s1:#0D1117; --s2:#161B2A; --s3:#1E2535;
    --purple:#8B5CF6; --purple-l:#A78BFA; --purple-d:rgba(139,92,246,.12);
    --cyan:#22D3EE; --cyan-d:rgba(34,211,238,.08);
    --green:#34D399; --green-d:rgba(52,211,153,.08);
    --amber:#F59E0B; --blue:#60A5FA;
    --text:#E2E8F0; --muted:#64748B; --dim:#94A3B8;
    --border:rgba(255,255,255,.05);
    --b-purple:rgba(139,92,246,.22); --b-cyan:rgba(34,211,238,.18);
    --shadow:0 8px 32px rgba(0,0,0,.5);
    --gp:0 0 28px rgba(139,92,246,.28); --gc:0 0 28px rgba(34,211,238,.2); --gg:0 0 20px rgba(52,211,153,.28);
    --r:14px; --rs:9px; --t:.22s cubic-bezier(.4,0,.2,1);
}
@keyframes pulse-dot {0%,100%{opacity:1;transform:scale(1)}50%{opacity:.7;transform:scale(.85)}}
@keyframes gb {0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
@keyframes fade-up {from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes shimmer {from{transform:translateX(-120%) skewX(-20deg)}to{transform:translateX(400%) skewX(-20deg)}}

.stApp{background:var(--bg)!important;color:var(--text)!important;font-family:'Inter',sans-serif!important}
.stApp::before{content:'';position:fixed;inset:0;
  background:radial-gradient(ellipse 65% 55% at 8% 4%,rgba(139,92,246,.09) 0%,transparent 65%),
             radial-gradient(ellipse 45% 35% at 92% 92%,rgba(34,211,238,.06) 0%,transparent 60%);
  pointer-events:none;z-index:0}
h1,h2,h3,h4{font-family:'Syne',sans-serif!important;color:var(--text)!important}
h3{font-size:17px!important;font-weight:800!important}
p{color:var(--dim)!important}
hr{border:none!important;height:1px!important;background:var(--border)!important;margin:22px 0!important}

/* TABS */
.stTabs [data-baseweb='tab-list']{background:rgba(13,17,23,.92)!important;backdrop-filter:blur(24px)!important;border:1px solid var(--b-purple)!important;border-radius:50px!important;padding:5px!important;gap:2px!important;box-shadow:var(--shadow),inset 0 1px 0 rgba(255,255,255,.03)!important;margin-bottom:24px!important}
.stTabs [data-baseweb='tab']{background:transparent!important;border-radius:50px!important;color:var(--muted)!important;font-family:'Inter',sans-serif!important;font-weight:700!important;font-size:11px!important;letter-spacing:1.2px!important;text-transform:uppercase!important;padding:10px 20px!important;border:none!important;transition:all var(--t)!important}
.stTabs [data-baseweb='tab']:hover{color:var(--purple-l)!important;background:rgba(139,92,246,.08)!important}
.stTabs [aria-selected='true']{background:linear-gradient(135deg,#8B5CF6,#5B21B6)!important;color:#fff!important;box-shadow:var(--gp),0 4px 12px rgba(0,0,0,.3)!important}
.stTabs [data-baseweb='tab-highlight'],.stTabs [data-baseweb='tab-border']{display:none!important}

/* BUTTONS */
.stButton>button{background:linear-gradient(135deg,#8B5CF6,#5B21B6)!important;color:#fff!important;border:none!important;border-radius:var(--rs)!important;font-family:'Inter',sans-serif!important;font-weight:700!important;font-size:11px!important;letter-spacing:1.5px!important;text-transform:uppercase!important;padding:13px 30px!important;box-shadow:var(--gp)!important;transition:all var(--t)!important;position:relative!important;overflow:hidden!important;width:100%!important}
.stButton>button::after{content:'';position:absolute;top:0;left:-100%;width:55%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.14),transparent);animation:shimmer 2.8s ease infinite}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 0 40px rgba(139,92,246,.55),0 8px 28px rgba(0,0,0,.4)!important;background:linear-gradient(135deg,#A78BFA,#7C3AED)!important}
.stButton>button:active{transform:translateY(0)!important}
.stDownloadButton>button{background:linear-gradient(135deg,#10B981,#065F46)!important;color:#fff!important;border:none!important;border-radius:var(--rs)!important;font-family:'Inter',sans-serif!important;font-weight:700!important;font-size:11px!important;letter-spacing:1.5px!important;text-transform:uppercase!important;padding:13px 30px!important;box-shadow:var(--gg)!important;transition:all var(--t)!important;width:100%!important}
.stDownloadButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 0 40px rgba(52,211,153,.5),0 8px 28px rgba(0,0,0,.4)!important}

/* INPUTS */
.stTextInput input,.stTextArea textarea{background:var(--s2)!important;border:1px solid var(--b-purple)!important;border-radius:var(--rs)!important;color:var(--text)!important;font-family:'Inter',sans-serif!important;font-size:14px!important;transition:all var(--t)!important}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--purple)!important;box-shadow:0 0 0 3px rgba(139,92,246,.18),var(--gp)!important;outline:none!important}
.stTextInput input::placeholder{color:var(--muted)!important}
.stTextInput label,.stSelectbox label,.stFileUploader label,.stSlider label{color:var(--dim)!important;font-size:11px!important;font-weight:700!important;letter-spacing:1.2px!important;text-transform:uppercase!important;font-family:'Inter',sans-serif!important}
.stSelectbox>div>div{background:var(--s2)!important;border:1px solid var(--b-purple)!important;border-radius:var(--rs)!important;color:var(--text)!important}
.stTextArea textarea{resize:vertical!important}

/* FILE UPLOADER */
[data-testid="stFileUploaderDropzone"]{background:rgba(22,27,42,.55)!important;border:2px dashed var(--b-purple)!important;border-radius:var(--r)!important;transition:all var(--t)!important}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--purple)!important;background:rgba(139,92,246,.05)!important;box-shadow:var(--gp)!important}

/* ALERTS */
[data-testid="stAlert"]{border-radius:var(--rs)!important;animation:fade-up .3s ease!important;font-family:'Inter',sans-serif!important;font-size:13px!important}
.stSuccess{background:rgba(52,211,153,.07)!important;border:1px solid rgba(52,211,153,.22)!important;border-left:3px solid var(--green)!important;color:#6EE7B7!important;border-radius:var(--rs)!important}
.stError{background:rgba(239,68,68,.07)!important;border:1px solid rgba(239,68,68,.22)!important;border-left:3px solid #EF4444!important;color:#FCA5A5!important;border-radius:var(--rs)!important}
.stInfo{background:rgba(34,211,238,.06)!important;border:1px solid rgba(34,211,238,.18)!important;border-left:3px solid var(--cyan)!important;color:#A5F3FC!important;border-radius:var(--rs)!important}
.stWarning{background:rgba(245,158,11,.06)!important;border:1px solid rgba(245,158,11,.18)!important;border-left:3px solid var(--amber)!important;border-radius:var(--rs)!important}

/* DATAFRAME */
[data-testid="stDataFrame"]{border:1px solid var(--b-purple)!important;border-radius:var(--r)!important;overflow:hidden!important;box-shadow:var(--shadow)!important}

/* SCROLLBAR */
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:var(--s1)}
::-webkit-scrollbar-thumb{background:var(--purple);border-radius:4px}

/* HEADER */
.hub-wrap{position:relative;border-radius:var(--r);padding:2px;background:linear-gradient(135deg,#8B5CF6,#22D3EE,#34D399,#8B5CF6);background-size:300% 300%;animation:gb 5s ease infinite;box-shadow:var(--gp)}
.hub-inner{background:linear-gradient(145deg,#0F172A,#141D30);border-radius:calc(var(--r) - 2px);padding:26px 30px}
.hub-status-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.hub-live{display:flex;align-items:center;gap:8px;background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.25);border-radius:50px;padding:5px 14px 5px 10px;font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;color:var(--green);letter-spacing:1.5px;text-transform:uppercase}
.status-dot{width:7px;height:7px;background:var(--green);border-radius:50%;animation:pulse-dot 2.2s ease infinite;box-shadow:0 0 8px var(--green)}
.hub-build{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--muted);letter-spacing:.5px}
.hub-title{font-family:'Syne',sans-serif!important;font-weight:800!important;font-size:36px!important;color:#fff!important;letter-spacing:-1px!important;line-height:1!important;margin:0 0 4px 0!important}
.hub-title em{color:var(--purple-l);font-style:normal}
.hub-sub{font-family:'Inter',sans-serif;font-size:11px;font-weight:600;color:var(--muted);letter-spacing:2.5px;text-transform:uppercase;margin-bottom:18px}
.hub-pills{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.hpill{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:5px 13px;border-radius:50px;letter-spacing:.5px}
.hp-p{background:rgba(139,92,246,.13);border:1px solid rgba(139,92,246,.32);color:var(--purple-l)}
.hp-c{background:rgba(34,211,238,.09);border:1px solid rgba(34,211,238,.28);color:var(--cyan)}
.hp-g{background:rgba(52,211,153,.09);border:1px solid rgba(52,211,153,.28);color:var(--green)}
.hp-a{background:rgba(245,158,11,.09);border:1px solid rgba(245,158,11,.28);color:var(--amber)}
.hp-b{background:rgba(96,165,250,.09);border:1px solid rgba(96,165,250,.28);color:var(--blue)}
.hp-r{background:rgba(239,68,68,.09);border:1px solid rgba(239,68,68,.28);color:#FCA5A5}

.hub-quote{background:rgba(13,17,23,.65);border-radius:var(--r);padding:16px 20px;margin-top:12px;border-left:3px solid var(--purple)}
.hub-quote p{font-family:'Inter',sans-serif!important;font-size:13px!important;font-style:italic!important;color:var(--dim)!important;margin:0!important;line-height:1.7!important}
.hub-quote em{color:var(--purple-l);font-style:normal;font-weight:700}

/* SECTION HEADING */
.sec-head{display:flex;align-items:center;gap:12px;margin:26px 0 18px 0;animation:fade-up .4s ease}
.sec-head-line{flex:1;height:1px;background:linear-gradient(90deg,var(--b-purple),transparent)}
.sec-head-text{font-family:'Syne',sans-serif;font-size:14px;font-weight:800;color:var(--text);letter-spacing:.3px;white-space:nowrap}

/* STRAIN CARD */
.sc{background:linear-gradient(150deg,#111827,#0F172A);border:1px solid var(--b-purple);border-top:2px solid var(--purple);border-radius:var(--r);padding:26px 28px;margin-top:14px;box-shadow:var(--shadow),inset 0 1px 0 rgba(255,255,255,.03);animation:fade-up .4s ease;position:relative;overflow:hidden}
.sc::before{content:'';position:absolute;top:0;right:0;width:180px;height:180px;background:radial-gradient(circle,rgba(139,92,246,.06) 0%,transparent 70%);pointer-events:none}
.sc-name{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;color:#fff;letter-spacing:-.5px;line-height:1}
.sc-header-row{display:flex;align-items:center;gap:10px;margin-bottom:18px;flex-wrap:wrap}
.sc-badge{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:5px 13px;border-radius:50px;letter-spacing:2px;text-transform:uppercase}
.sb-sativa{background:rgba(16,185,129,.13);border:1px solid rgba(16,185,129,.35);color:#34D399}
.sb-indica{background:rgba(59,130,246,.13);border:1px solid rgba(59,130,246,.35);color:#93C5FD}
.sb-hybrid{background:rgba(139,92,246,.13);border:1px solid rgba(139,92,246,.35);color:var(--purple-l)}
.sc-div{height:1px;background:linear-gradient(90deg,var(--b-purple),transparent);margin-bottom:20px}
.sc-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.sc-attr{display:flex;flex-direction:column;gap:5px}
.sc-attr-full{grid-column:1 / -1}
.attr-label{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:var(--purple-l);letter-spacing:2px;text-transform:uppercase}
.attr-val{font-family:'Inter',sans-serif;font-size:13px;color:var(--dim);line-height:1.55}
.attr-val-hi{color:var(--cyan)!important}

/* COMPOUND CARD */
.cc{background:linear-gradient(150deg,#0E1628,#0F172A);border:1px solid var(--b-cyan);border-top:2px solid var(--cyan);border-radius:var(--r);padding:26px 28px;margin-top:14px;box-shadow:var(--shadow);animation:fade-up .4s ease}
.cc-name{font-family:'Syne',sans-serif;font-size:26px;font-weight:800;color:var(--cyan);letter-spacing:-.5px;margin-bottom:16px}
.cc-div{height:1px;background:linear-gradient(90deg,var(--b-cyan),transparent);margin-bottom:18px}

/* METRIC TILES */
.metric-row{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}
.m-tile{background:var(--s2);border:1px solid var(--border);border-radius:var(--rs);padding:16px 18px;text-align:center;position:relative;overflow:hidden}
.m-tile::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--purple),var(--cyan))}
.m-num{font-family:'JetBrains Mono',monospace;font-size:30px;font-weight:700;color:#fff;line-height:1}
.m-lbl{font-family:'Inter',sans-serif;font-size:10px;font-weight:700;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;margin-top:5px}

/* STEP CARDS */
.step-card{background:var(--s2);border:1px solid var(--b-purple);border-radius:var(--r);padding:20px 24px;margin-bottom:12px;animation:fade-up .4s ease}
.step-header{display:flex;align-items:center;gap:14px}
.step-num{width:30px;height:30px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,#8B5CF6,#5B21B6);display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:#fff;box-shadow:var(--gp)}
.step-ttl{font-family:'Syne',sans-serif;font-size:14px;font-weight:800;color:var(--text)}
.step-dsc{font-family:'Inter',sans-serif;font-size:12px;color:var(--muted);margin-top:2px}

/* INSTRUCTION CARD */
.instr-card{background:rgba(22,27,42,.7);border:1px solid var(--b-purple);border-left:3px solid var(--purple);border-radius:var(--r);padding:16px 20px;margin-bottom:14px;animation:fade-up .4s ease}
.instr-title{font-family:'Syne',sans-serif;font-size:13px;font-weight:800;color:var(--purple-l);letter-spacing:.3px;margin-bottom:12px;text-transform:uppercase}
.instr-steps{display:flex;flex-direction:column;gap:9px}
.instr-step{display:flex;align-items:flex-start;gap:12px;font-family:'Inter',sans-serif;font-size:13px;color:var(--dim);line-height:1.5}
.instr-step strong{color:var(--text)}
.instr-icon{flex-shrink:0;width:22px;height:22px;background:var(--purple-d);border:1px solid var(--b-purple);border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;color:var(--purple-l);margin-top:1px}
.instr-icon.fire{background:rgba(245,158,11,.1);border-color:rgba(245,158,11,.3);color:var(--amber);font-size:12px}

/* GOOGLE BTN */
.g-btn{display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,#8B5CF6,#5B21B6);color:#fff!important;text-decoration:none!important;padding:9px 18px;border-radius:var(--rs);font-family:'Inter',sans-serif;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;box-shadow:var(--gp);transition:all var(--t);margin-bottom:14px}
.g-btn:hover{transform:translateY(-2px);box-shadow:0 0 36px rgba(139,92,246,.5)}

/* ═══════════════════════════════════════════════════
   CHECKLIST STYLES
═══════════════════════════════════════════════════ */
.shift-hdr{border-radius:var(--rs);padding:14px 18px;margin:22px 0 4px 0;display:flex;align-items:center;justify-content:space-between}
.shift-hdr-morning{background:rgba(52,211,153,.07);border-left:4px solid var(--green)}
.shift-hdr-handover{background:rgba(245,158,11,.07);border-left:4px solid var(--amber)}
.shift-hdr-afternoon{background:rgba(96,165,250,.07);border-left:4px solid var(--blue)}
.shift-ttl{font-family:'Syne',sans-serif;font-size:14px;font-weight:800;color:var(--text)}
.shift-meta{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--muted);margin-top:3px;letter-spacing:.5px}
.shift-badge{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;padding:6px 16px;border-radius:50px;background:var(--s3);color:var(--text)}
.cat-hdr{font-family:'Inter',sans-serif;font-size:10px;font-weight:700;color:var(--muted);letter-spacing:1.8px;text-transform:uppercase;padding:12px 0 5px 0;border-bottom:1px solid var(--border);margin-bottom:4px}
.task-lbl{font-family:'Inter',sans-serif;font-size:13px;font-weight:600;color:var(--text);line-height:1.4}
.task-lbl-done{font-family:'Inter',sans-serif;font-size:13px;font-weight:600;color:var(--muted);text-decoration:line-through;line-height:1.4}
.task-sign{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--green);margin-top:3px;letter-spacing:.3px}
.task-desc{font-family:'Inter',sans-serif;font-size:11px;color:var(--muted);margin-top:3px;line-height:1.5}
.checklist-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px}
.cs-tile{background:var(--s2);border:1px solid var(--border);border-radius:var(--rs);padding:14px 16px;text-align:center;position:relative;overflow:hidden}
.cs-tile-morning::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--green)}
.cs-tile-handover::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--amber)}
.cs-tile-afternoon::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--blue)}
.cs-tile-total::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--purple),var(--cyan))}
.cs-num{font-family:'JetBrains Mono',monospace;font-size:26px;font-weight:700;color:#fff;line-height:1}
.cs-lbl{font-family:'Inter',sans-serif;font-size:10px;font-weight:700;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;margin-top:4px}

/* ═══════════════════════════════════════════════════
   COMMS BOARD STYLES
═══════════════════════════════════════════════════ */
.msg-card{background:var(--s2);border:1px solid var(--border);border-radius:var(--r);padding:18px 22px;margin-bottom:10px;animation:fade-up .3s ease;position:relative}
.msg-pinned{border-left:3px solid var(--purple-l);background:rgba(139,92,246,.05)}
.msg-urgent{border-left:3px solid #EF4444;background:rgba(239,68,68,.05)}
.msg-flags{display:flex;gap:6px;margin-bottom:8px}
.msg-flag{font-size:10px;font-weight:700;padding:3px 10px;border-radius:50px;font-family:'JetBrains Mono',monospace;letter-spacing:1px}
.mf-pin{background:rgba(139,92,246,.15);color:var(--purple-l);border:1px solid var(--b-purple)}
.mf-urg{background:rgba(239,68,68,.15);color:#FCA5A5;border:1px solid rgba(239,68,68,.3)}
.msg-body{font-family:'Inter',sans-serif;font-size:14px;color:var(--text);line-height:1.6;margin-bottom:12px;white-space:pre-wrap}
.msg-meta{display:flex;align-items:center;gap:12px;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--muted)}
.msg-author{color:var(--purple-l)}
.post-card{background:var(--s2);border:1px solid var(--b-purple);border-radius:var(--r);padding:22px 26px;margin-bottom:22px}
.post-title{font-family:'Syne',sans-serif;font-size:14px;font-weight:800;color:var(--text);margin-bottom:16px}
.stCheckbox label{color:var(--dim)!important;font-size:13px!important;font-family:'Inter',sans-serif!important}

/* ═══════════════════════════════════════════════════
   DEAD STOCK STYLES
═══════════════════════════════════════════════════ */
.ds-row{display:grid;grid-template-columns:auto 1fr auto;gap:14px;align-items:center;background:var(--s2);border:1px solid var(--border);border-radius:var(--rs);padding:14px 18px;margin-bottom:8px;animation:fade-up .3s ease}
.ds-row-critical{border-left:3px solid #EF4444}
.ds-row-high{border-left:3px solid var(--amber)}
.ds-row-watch{border-left:3px solid var(--blue)}
.ds-age{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:22px;line-height:1;text-align:center;min-width:52px}
.ds-age-num-critical{color:#FCA5A5}
.ds-age-num-high{color:var(--amber)}
.ds-age-num-watch{color:var(--blue)}
.ds-age-unit{font-family:'Inter',sans-serif;font-size:9px;font-weight:700;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-top:3px}
.ds-name{font-family:'Inter',sans-serif;font-size:14px;font-weight:600;color:var(--text);line-height:1.3}
.ds-meta{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--muted);margin-top:4px;letter-spacing:.3px}
.ds-flags{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}
.ds-flag{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:2px 8px;border-radius:50px;letter-spacing:.5px}
.dsf-exp{background:rgba(239,68,68,.13);color:#FCA5A5;border:1px solid rgba(239,68,68,.3)}
.dsf-sale{background:rgba(245,158,11,.13);color:var(--amber);border:1px solid rgba(245,158,11,.3)}
.ds-qty{text-align:right}
.ds-qty-num{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:var(--text);line-height:1}
.ds-qty-lbl{font-family:'Inter',sans-serif;font-size:9px;font-weight:700;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-top:2px}
.ds-group-hdr{font-family:'Syne',sans-serif;font-size:13px;font-weight:800;color:var(--purple-l);letter-spacing:.3px;margin:22px 0 10px 0;padding-bottom:6px;border-bottom:1px solid var(--b-purple);display:flex;justify-content:space-between;align-items:center}
.ds-group-count{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);font-weight:400}
</style>
""", unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
col_vid, col_hdr = st.columns([1, 1])
with col_vid:
    with open('video.mp4', 'rb') as vf:
        st.video(vf.read(), loop=True, autoplay=True, muted=True)
with col_hdr:
    st.markdown("""
    <div class="hub-wrap"><div class="hub-inner">
      <div class="hub-status-row">
        <div class="hub-live"><span class="status-dot"></span>System Online</div>
        <span class="hub-build">ZIGGYBOT · v2.0</span>
      </div>
      <div class="hub-title">ZIGGY<em>BOT</em></div>
      <div class="hub-sub">Dispensary Intelligence Platform</div>
      <div class="hub-pills">
        <span class="hpill hp-p">⚡ Strain AI</span>
        <span class="hpill hp-c">📊 Inventory</span>
        <span class="hpill hp-g">🏷️ Hook Tags</span>
        <span class="hpill hp-g">🌿 Preroll Tags</span>
        <span class="hpill hp-a">✅ Checklist</span>
        <span class="hpill hp-b">📢 Comms</span>
        <span class="hpill hp-r">⏳ Aging Stock</span>
        <span class="hpill hp-g">🧩 Crossword</span>
        <span class="hpill hp-a">🔥 Burn Down</span>
      </div>
    </div></div>
    <div class="hub-quote">
      <p>"Your attitude, not your aptitude, will determine your altitude." — <em>Zig Ziglar</em></p>
    </div>""", unsafe_allow_html=True)

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab9, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "⚡  STRAIN SNIFFER",
    "📊  INVENTORY BALANCING",
    "🏷️  SMALL HOOK TAGS",
    "🌿  PREROLL TAGS",
    "⏳  AGING STOCK",
    "✅  DAILY CHECKLIST",
    "📢  COMMS BOARD",
    "🧩  CROSSWORD",
    "🔥  BURN DOWN",
])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — STRAIN SNIFFER
# ════════════════════════════════════════════════════════════════════════════════
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
        google_url = f"https://www.google.com/search?q={quote_plus(strain + ' strain')}&udm=50"
        st.markdown(f'<a href="{google_url}" target="_blank" class="g-btn">✨ Ask Google AI about {strain}</a>', unsafe_allow_html=True)
        data = generate_strain_profile(st.secrets["GROQ_API_KEY"], strain)
        if "error" not in data:
            clf  = str(data.get('classification', 'HYBRID')).upper()
            bcls = "sb-sativa" if "SATIVA" in clf else ("sb-indica" if "INDICA" in clf else "sb-hybrid")
            st.markdown(f"""
            <div class="sc"><div class="sc-header-row">
              <div class="sc-name">{strain.upper()}</div>
              <span class="sc-badge {bcls}">{clf}</span>
            </div><div class="sc-div"></div>
            <div class="sc-grid">
              <div class="sc-attr sc-attr-full"><div class="attr-label">🌿 Lineage</div><div class="attr-val">{data.get('lineage','—')}</div></div>
              <div class="sc-attr"><div class="attr-label">🧪 Terpenes</div><div class="attr-val">{data.get('terpenes','—')}</div></div>
              <div class="sc-attr"><div class="attr-label">🍋 Flavor</div><div class="attr-val">{data.get('flavor','—')}</div></div>
              <div class="sc-attr"><div class="attr-label">⚡ Cannabinoids</div><div class="attr-val attr-val-hi">{data.get('cannabinoids','—')}</div></div>
              <div class="sc-attr"><div class="attr-label">🧠 Effects</div><div class="attr-val">{data.get('effects','—')}</div></div>
            </div></div>""", unsafe_allow_html=True)
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
            <div class="cc"><div class="cc-name">🔬 {target_chem.upper()}</div><div class="cc-div"></div>
            <div class="sc-grid">
              <div class="sc-attr"><div class="attr-label">🧠 Primary Effects</div><div class="attr-val">{chem_data.get('primary_effects','—')}</div></div>
              <div class="sc-attr"><div class="attr-label">🩺 Medical Benefits</div><div class="attr-val">{chem_data.get('medical_benefits','—')}</div></div>
              <div class="sc-attr sc-attr-full"><div class="attr-label">🎯 Budtender Pitch</div><div class="attr-val attr-val-hi" style="font-style:italic;">"{chem_data.get('customer_pitch','—')}"</div></div>
            </div></div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — INVENTORY INTEL
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="sec-head"><div class="sec-head-text">📊 Live Room Balance Analyzer</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="instr-card"><div class="instr-title">📋 How to Export from Dutchie</div>
    <div class="instr-steps">
      <div class="instr-step"><span class="instr-icon">1</span><span>In Dutchie Backoffice, select your rooms &amp; <strong>one category</strong></span></div>
      <div class="instr-step"><span class="instr-icon fire">🔥</span><span>Export only <strong>Product</strong>, <strong>Room</strong>, &amp; <strong>Quantity</strong></span></div>
      <div class="instr-step"><span class="instr-icon">🔄</span><span><strong>Rebalance</strong> = stock is lopsided <em>or</em> a room is running low while the other has plenty — move some over</span></div>
    </div></div>""", unsafe_allow_html=True)
    uploaded_file = st.file_uploader(" ", type="csv", key="restock_csv", label_visibility="collapsed")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        df.columns = [str(col).strip('="').strip() for col in df.columns]
        qty_col = [col for col in df.columns if 'Quantity' in col or 'Qty' in col][0]
        df['Product'] = df['Product'].apply(lambda x: str(x).strip('="').strip())
        df['Room']    = df['Room'].apply(lambda x: str(x).strip('="').strip())
        df['Qty']     = pd.to_numeric(df[qty_col].apply(lambda x: str(x).strip('="').strip()), errors='coerce').fillna(0)

        all_rooms = sorted(df['Room'].dropna().unique().tolist())

        # ── Controls: room filter + minimum stock + imbalance threshold ──────
        rooms = st.multiselect("Rooms to include", all_rooms, default=all_rooms,
                               key="balance_rooms")
        ctrl_l, ctrl_r = st.columns([1, 1])
        with ctrl_l:
            min_stock = st.slider(
                "Minimum stock per room", 0, 25, 5,
                help="A room at or below this many units (while another room has "
                     "more) is flagged 🔄 Rebalance so you can move stock over.")
        with ctrl_r:
            imbalance_pct = st.slider(
                "Flag when a room holds more than this % of stock", 50, 95, 70,
                help="A product is flagged 🔄 Rebalance when one room holds more "
                     "than this share of its total. Lower = stricter.")

        if len(rooms) < 1:
            st.info("Select at least one room to analyze.")
        else:
            sub = df[df['Room'].isin(rooms)]
            pivot = sub.groupby(['Product', 'Room'])['Qty'].sum().unstack(fill_value=0)
            # ensure all selected rooms are columns even if absent in data
            for r in rooms:
                if r not in pivot.columns:
                    pivot[r] = 0
            pivot = pivot[rooms]

            rows = []
            for product, prow in pivot.iterrows():
                qtys = {r: int(prow[r]) for r in rooms}
                total = sum(qtys.values())
                if total <= 0:
                    continue  # nothing in the selected rooms — skip
                shares = {r: qtys[r] / total for r in rooms}
                top_share = max(shares.values())
                # Trigger 1: lopsided split beyond the imbalance threshold
                imbalanced = len(rooms) > 1 and (top_share * 100) > imbalance_pct
                # Trigger 2: a room is at/below minimum while another has stock to move
                low_room    = any(qtys[r] <= min_stock for r in rooms)
                source_room = any(qtys[r] > min_stock for r in rooms)
                low_flag = len(rooms) > 1 and low_room and source_room
                status = "🔄 Rebalance" if (imbalanced or low_flag) else "✅ Balanced"
                mix = " / ".join(f"{r.split()[0]} {round(shares[r]*100)}%" for r in rooms)
                entry = {"Product Name": product}
                for r in rooms:
                    entry[r] = qtys[r]
                entry["Total"] = total
                entry["Mix %"] = mix
                entry["Status"] = status
                entry["_skew"] = top_share  # for sorting
                rows.append(entry)

            final_df = pd.DataFrame(rows)
            # Default to showing only the ones needing action, with a toggle
            show_all = st.checkbox("Show balanced products too", value=False)
            if not final_df.empty and not show_all:
                view_df = final_df[final_df["Status"].str.contains("Rebalance")].copy()
            else:
                view_df = final_df.copy()

            if not final_df.empty:
                n_total   = len(final_df)
                n_rebal   = int((final_df["Status"].str.contains("Rebalance")).sum())
                n_bal     = n_total - n_rebal
                st.markdown(f"""
                <div class="metric-row">
                  <div class="m-tile"><div class="m-num">{n_total}</div><div class="m-lbl">Products</div></div>
                  <div class="m-tile"><div class="m-num">{n_rebal}</div><div class="m-lbl">🔄 Rebalance</div></div>
                  <div class="m-tile"><div class="m-num">{n_bal}</div><div class="m-lbl">✅ Balanced</div></div>
                </div>""", unsafe_allow_html=True)

                if view_df.empty:
                    st.success(f"✅ Nothing to rebalance across {', '.join(rooms)} "
                               f"at these settings. Rooms are balanced!")
                else:
                    # most lopsided first
                    view_df = view_df.sort_values(by=["Status", "_skew"],
                                                  ascending=[True, False]).reset_index(drop=True)
                    display_df = view_df.drop(columns=["_skew"])
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    st.download_button("📥  Download Balance Report PDF",
                                       build_pdf(display_df, imbalance_pct, rooms, min_stock),
                                       "Ziggy_Balance_Report.pdf", "application/pdf")
            else:
                st.success("✅ No stock found in the selected rooms.")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — HOOK TAG GENERATOR
# ════════════════════════════════════════════════════════════════════════════════
def render_hook_tags():
    st.markdown('<div class="sec-head"><div class="sec-head-text">🏷️ Automated Hook Tag Formatter</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)
    TEMPLATE_PATH = "master_template.pdf"
    if not PYPDF_AVAILABLE:
        st.error("pypdf not installed — add `pypdf` to requirements.txt and redeploy.")
        return
    try:
        subprocess.run(["pdftk", "--version"], capture_output=True, check=True)
        pdftk_ok = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pdftk_ok = False
    if not pdftk_ok:
        st.error("pdftk not found — add `pdftk` to packages.txt and redeploy.")
        return
    if not os.path.exists(TEMPLATE_PATH):
        st.error("`master_template.pdf` not found — commit it to the root of your repo.")
        return

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
        return
    slots_per_page = max(slot_map.keys())

    st.markdown(f"""
    <div class="step-card"><div class="step-header">
      <div class="step-num">1</div>
      <div><div class="step-ttl">Export &amp; Upload Inventory CSV</div>
      <div class="step-dsc">{slots_per_page} tags per sheet · duplicates auto-removed</div></div>
    </div></div>""", unsafe_allow_html=True)
    st.markdown("""
    <div class="instr-card"><div class="instr-title">📋 How to Export from Dutchie</div>
    <div class="instr-steps">
      <div class="instr-step"><span class="instr-icon">1</span><span>In Dutchie Backend, select any combination of <strong>product, room, category</strong>, etc.</span></div>
      <div class="instr-step"><span class="instr-icon fire">🔥</span><span>Export only <strong>Product</strong>, <strong>THC</strong>, &amp; <strong>Current Price</strong></span></div>
      <div class="instr-step"><span class="instr-icon fire">🔥</span><span>One tag per unique product — same strain with <strong>different THC %</strong> gets its own tag</span></div>
      <div class="instr-step"><span class="instr-icon fire">🔥</span><span>Save additional tags for <strong>future use</strong> — re-upload anytime</span></div>
    </div></div>""", unsafe_allow_html=True)

    hook_file = st.file_uploader(" ", type=["csv"], key="hook_csv", label_visibility="collapsed")
    if hook_file is None:
        st.markdown("""<div class="step-card" style="opacity:.4;"><div class="step-header">
          <div class="step-num">2</div>
          <div><div class="step-ttl">Review &amp; Generate</div>
          <div class="step-dsc">Upload a CSV above to continue</div></div>
        </div></div>""", unsafe_allow_html=True)
        return

    df_hook = pd.read_csv(hook_file)
    df_hook.columns = [str(c).strip('="').strip() for c in df_hook.columns]
    price_col = "Current price" if "Current price" in df_hook.columns else "Price"
    raw_rows = []
    for _, row in df_hook.iterrows():
        product = str(row.get("Product", "")).strip('="').strip()
        if not product or product.lower() == "nan": continue
        parts  = [p.strip() for p in product.split("|")]
        brand  = parts[0].upper() if len(parts) >= 1 else ""
        strain = parts[1].upper() if len(parts) >= 2 else product.upper()
        # Pull a gram weight from the product name (e.g. 7G, 28G, 3.5G, .5G) and
        # append it to the brand line. The 'm' in "mg" prevents matching edible doses.
        wt_match = re.search(r'(\d*\.?\d+)\s*g\b', product, re.IGNORECASE)
        if wt_match:
            wt_val = wt_match.group(1)
            if wt_val.endswith(".0"):
                wt_val = wt_val[:-2]
            brand = f"{brand} {wt_val}G".strip()
        # If the product name contains a mg dose (edibles/drinks), show that in
        # the THC field instead of the back-office THC %. e.g. "200MG Tarts" → 200MG
        mg_match = re.search(r'(\d+(?:\.\d+)?)\s*mg\b', product, re.IGNORECASE)
        if mg_match:
            mg_val = mg_match.group(1)
            if mg_val.endswith(".0"):
                mg_val = mg_val[:-2]
            thc = f"{mg_val}MG"
        else:
            # Preserve the exact THC value from back office — never round.
            thc = str(row.get("THC", "")).strip('="').strip()
        rp     = str(row.get(price_col, "0")).replace("$", "").strip('="').strip()
        pd_    = "".join(c for c in rp if c.isdigit() or c == ".")
        try:
            pv    = float(pd_) if pd_ else 0.0
            price = f"${int(pv)}" if pv == int(pv) else f"${pv:.2f}"
        except ValueError:
            price = "$0"
        raw_rows.append({"brand": brand, "strain": strain, "thc": thc,
                         "price": price, "product": product})

    if not raw_rows:
        st.error("No valid product rows found in the CSV.")
        return

    # Dedup on the FULL product description (not just strain name) so the same
    # strain in different packaged weights each gets its own tag.
    seen, rows = set(), []
    for r in raw_rows:
        key = (r["product"].strip().lower(), r["thc"].strip().lower())
        if key not in seen:
            seen.add(key); rows.append(r)

    n_pages = -(-len(rows) // slots_per_page)
    st.markdown(f"""
    <div class="step-card"><div class="step-header">
      <div class="step-num">2</div>
      <div><div class="step-ttl">Review Tag Summary</div>
      <div class="step-dsc">{len(rows)} unique tags · {n_pages} sheet(s) · {len(raw_rows)-len(rows)} duplicates removed</div></div>
    </div></div>""", unsafe_allow_html=True)

    preview = pd.DataFrame(rows)[["brand","strain","thc","price"]]
    preview.columns = ["Brand","Strain","THC","Price"]
    st.dataframe(preview, use_container_width=True, hide_index=True)

    st.markdown("""<div class="step-card"><div class="step-header">
      <div class="step-num">3</div>
      <div><div class="step-ttl">Generate &amp; Download</div>
      <div class="step-dsc">Fills template using embedded Paralucent-Heavy font with true autosize</div></div>
    </div></div>""", unsafe_allow_html=True)

    def _esc(s): return s.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
    def make_fdf(page_rows):
        entries = []
        for slot in range(1, slots_per_page + 1):
            d  = page_rows[slot-1] if slot-1 < len(page_rows) else {}
            sf = slot_map.get(slot, {})
            for key, val in [("brand",d.get("brand","")),("strain",d.get("strain","")),
                              ("thc",d.get("thc","")),("price",d.get("price",""))]:
                fn = sf.get(key)
                if fn: entries.append(f"<</T ({_esc(fn)})/V ({_esc(val)})>>")
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
                        with open(fp, "w", encoding="latin-1") as f: f.write(make_fdf(pg))
                        r = subprocess.run(["pdftk", TEMPLATE_PATH, "fill_form", fp, "output", op],
                                           capture_output=True, text=True)
                        if r.returncode != 0:
                            err = f"pdftk error on sheet {i+1}: {r.stderr.strip()}"; break
                        page_paths.append(op)
                    if err: st.error(err); return
                    if len(page_paths) == 1:
                        final = page_paths[0]
                    else:
                        final = os.path.join(tmp, "merged.pdf")
                        r = subprocess.run(["pdftk"]+page_paths+["cat","output",final],
                                           capture_output=True, text=True)
                        if r.returncode != 0:
                            st.error(f"Merge error: {r.stderr.strip()}"); return
                    with open(final, "rb") as f: pdf_bytes = f.read()
            except FileNotFoundError:
                st.error("pdftk not found — add `pdftk` to packages.txt."); return
            except Exception as e:
                st.error(f"Unexpected error: {e}"); return
        st.success(f"✅ {len(rows)} tags across {len(pages)} sheet(s) — ready to print!")
        st.download_button("📥  DOWNLOAD HOOK TAGS PDF", pdf_bytes, "HookTags_Ready.pdf", "application/pdf")



with tab3:
    render_hook_tags()

# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — DAILY CHECKLIST
# ════════════════════════════════════════════════════════════════════════════════
def render_checklist():
    st.markdown('<div class="sec-head"><div class="sec-head-text">✅ Daily Operations Checklist</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    if not SUPABASE_AVAILABLE:
        st.error("The `supabase` library isn't installed yet. Add `supabase` to requirements.txt and redeploy.")
        return

    db = init_supabase()
    if db is None:
        st.error("⚠️ Could not connect to Supabase. Check that SUPABASE_URL and SUPABASE_KEY are set correctly in your Streamlit Secrets.")
        st.markdown("""<div class="instr-card"><div class="instr-title">🔧 Fix in Streamlit Secrets</div>
        <div class="instr-steps">
          <div class="instr-step"><span class="instr-icon">1</span><span>App dashboard → <strong>Settings → Secrets</strong></span></div>
          <div class="instr-step"><span class="instr-icon">2</span><span>Add <strong>SUPABASE_URL</strong> and <strong>SUPABASE_KEY</strong> (anon public key)</span></div>
          <div class="instr-step"><span class="instr-icon">3</span><span>Save — the app reboots automatically</span></div>
        </div></div>""", unsafe_allow_html=True)
        return

    # ── Staff name ────────────────────────────────────────────────────────────
    if "staff_name" not in st.session_state:
        st.session_state.staff_name = ""

    name_col, _ = st.columns([1, 2])
    with name_col:
        name_input = st.text_input("👤 Your Name",
                                   value=st.session_state.staff_name,
                                   placeholder="Enter name to sign off tasks…",
                                   key="staff_name_field")
        st.session_state.staff_name = name_input

    if not name_input.strip():
        st.markdown("""<div class="instr-card">
          <div class="instr-title">👆 Enter your name above to begin signing off tasks</div>
          <div class="instr-steps"><div class="instr-step">
            <span class="instr-icon">i</span>
            <span>Your name will be recorded alongside each completed item. The board resets automatically at midnight.</span>
          </div></div></div>""", unsafe_allow_html=True)
        return

    # ── Load data ─────────────────────────────────────────────────────────────
    try:
        tasks       = db.table('checklist_tasks').select('*').eq('is_active', True).order('sort_order').execute().data
        today_str   = date.today().isoformat()
        completions = db.table('checklist_completions').select('*').eq('shift_date', today_str).execute().data
    except Exception as e:
        st.error(f"Database error while loading checklist: {e}")
        return

    if not tasks:
        st.warning("No tasks found in the database. Did the seed SQL run successfully?")
        return

    completed_ids = {c['task_id'] for c in completions}
    comp_by_task  = {c['task_id']: c for c in completions}

    # ── Summary tiles ─────────────────────────────────────────────────────────
    def shift_count(shift_key):
        t = [x for x in tasks if x['shift'] == shift_key]
        d = sum(1 for x in t if x['id'] in completed_ids)
        return d, len(t)

    m_d, m_t = shift_count('morning')
    h_d, h_t = shift_count('handover')
    a_d, a_t = shift_count('afternoon')
    all_d, all_t = m_d + h_d + a_d, m_t + h_t + a_t

    st.markdown(f"""
    <div class="checklist-summary">
      <div class="cs-tile cs-tile-total"><div class="cs-num">{all_d}/{all_t}</div><div class="cs-lbl">Total Today</div></div>
      <div class="cs-tile cs-tile-morning"><div class="cs-num">{m_d}/{m_t}</div><div class="cs-lbl">🟢 Morning</div></div>
      <div class="cs-tile cs-tile-handover"><div class="cs-num">{h_d}/{h_t}</div><div class="cs-lbl">🟡 Handover</div></div>
      <div class="cs-tile cs-tile-afternoon"><div class="cs-num">{a_d}/{a_t}</div><div class="cs-lbl">🔵 Afternoon</div></div>
    </div>""", unsafe_allow_html=True)

    # ── Group tasks ───────────────────────────────────────────────────────────
    by_shift = defaultdict(lambda: defaultdict(list))
    for task in tasks:
        by_shift[task['shift']][task['category']].append(task)

    SHIFT_CONFIG = [
        ('morning',   '🟢 Morning Shift',         '7:45 AM – 2:30 PM', 'morning'),
        ('handover',  '🟡 Shift Change Handover', '2:30 PM',           'handover'),
        ('afternoon', '🔵 Afternoon Shift',        '2:30 PM – Close',   'afternoon'),
    ]

    for shift_key, shift_label, shift_time, css_key in SHIFT_CONFIG:
        shift_tasks = [t for t in tasks if t['shift'] == shift_key]
        if not shift_tasks:
            continue

        s_done  = sum(1 for t in shift_tasks if t['id'] in completed_ids)
        s_total = len(shift_tasks)
        prog    = s_done / s_total if s_total else 0

        st.markdown(f"""
        <div class="shift-hdr shift-hdr-{css_key}">
          <div><div class="shift-ttl">{shift_label}</div>
               <div class="shift-meta">{shift_time}</div></div>
          <div class="shift-badge">{s_done} / {s_total}</div>
        </div>""", unsafe_allow_html=True)
        st.progress(prog)

        for category, cat_tasks in by_shift[shift_key].items():
            st.markdown(f'<div class="cat-hdr">{category}</div>', unsafe_allow_html=True)

            for task in cat_tasks:
                is_done = task['id'] in completed_ids
                col_chk, col_txt = st.columns([0.04, 0.96])

                with col_chk:
                    new_val = st.checkbox(" ", value=is_done, key=f"task_{task['id']}",
                                          label_visibility="collapsed")

                with col_txt:
                    if is_done:
                        info = comp_by_task[task['id']]
                        ts   = fmt_ts(info.get('completed_at', ''))
                        st.markdown(
                            f'<div class="task-lbl-done">{task["task_name"]}</div>'
                            f'<div class="task-sign">✓ {info["completed_by"]} · {ts}</div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="task-lbl">{task["task_name"]}</div>',
                                    unsafe_allow_html=True)
                        if task.get('description'):
                            st.markdown(f'<div class="task-desc">{task["description"]}</div>',
                                        unsafe_allow_html=True)

                if new_val and not is_done:
                    try:
                        db.table('checklist_completions').insert({
                            'task_id':      task['id'],
                            'completed_by': name_input.strip(),
                            'shift_date':   today_str,
                        }).execute()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Sign-off error: {e}")
                elif not new_val and is_done:
                    try:
                        db.table('checklist_completions').delete()\
                            .eq('task_id', task['id'])\
                            .eq('shift_date', today_str).execute()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Remove error: {e}")


with tab5:
    render_checklist()

# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 — COMMS BOARD
# ════════════════════════════════════════════════════════════════════════════════
def render_comms():
    st.markdown('<div class="sec-head"><div class="sec-head-text">📢 Team Communications Board</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    if not SUPABASE_AVAILABLE:
        st.error("The `supabase` library isn't installed yet. Add `supabase` to requirements.txt and redeploy.")
        return

    db = init_supabase()
    if db is None:
        st.error("⚠️ Could not connect to Supabase. Check that SUPABASE_URL and SUPABASE_KEY are set correctly in your Streamlit Secrets.")
        return

    # ── Post new message ──────────────────────────────────────────────────────
    st.markdown('<div class="post-card"><div class="post-title">✏️ Post a Message</div>', unsafe_allow_html=True)
    with st.form("new_msg_form", clear_on_submit=True):
        p_author  = st.text_input("Your Name", placeholder="Enter your name…")
        p_content = st.text_area("Message", placeholder="Type your message here…", height=100)
        fc1, fc2, _ = st.columns([1, 1, 2])
        with fc1:
            p_urgent = st.checkbox("🔥 Mark Urgent")
        with fc2:
            p_pin = st.checkbox("📌 Pin to Top")
        post_btn = st.form_submit_button("📤  POST MESSAGE")

        if post_btn:
            if not p_author.strip():
                st.warning("Please enter your name.")
            elif not p_content.strip():
                st.warning("Message cannot be empty.")
            else:
                try:
                    db.table('messages').insert({
                        'author':    p_author.strip(),
                        'content':   p_content.strip(),
                        'is_urgent': p_urgent,
                        'is_pinned': p_pin,
                    }).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Post error: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Load messages ─────────────────────────────────────────────────────────
    try:
        msgs = db.table('messages').select('*')\
                 .eq('is_archived', False)\
                 .order('created_at', desc=True).execute().data
    except Exception as e:
        st.error(f"Database error while loading messages: {e}")
        return

    pinned  = [m for m in msgs if m.get('is_pinned')]
    regular = [m for m in msgs if not m.get('is_pinned')]

    def render_message(msg):
        card_cls = "msg-card"
        if msg.get('is_urgent'): card_cls += " msg-urgent"
        if msg.get('is_pinned'): card_cls += " msg-pinned"

        flags = ""
        if msg.get('is_pinned'): flags += '<span class="msg-flag mf-pin">📌 PINNED</span>'
        if msg.get('is_urgent'): flags += '<span class="msg-flag mf-urg">🔥 URGENT</span>'
        flags_html = f'<div class="msg-flags">{flags}</div>' if flags else ''

        content = msg.get('content', '').replace('<', '&lt;').replace('>', '&gt;')
        author  = msg.get('author', 'Unknown')
        ts      = fmt_ts(msg.get('created_at', ''))
        msg_id  = msg.get('id')

        st.markdown(f"""
        <div class="{card_cls}">
          {flags_html}
          <div class="msg-body">{content}</div>
          <div class="msg-meta">
            <span class="msg-author">{author}</span><span>·</span><span>{ts}</span>
          </div>
        </div>""", unsafe_allow_html=True)

        _, arc_col = st.columns([6, 1])
        with arc_col:
            if st.button("Archive", key=f"arc_{msg_id}", help="Remove from board"):
                try:
                    db.table('messages').update({'is_archived': True}).eq('id', msg_id).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Archive error: {e}")

    if pinned:
        st.markdown('<div class="sec-head"><div class="sec-head-text">📌 Pinned</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)
        for m in pinned:
            render_message(m)

    if regular:
        st.markdown('<div class="sec-head"><div class="sec-head-text">💬 All Messages</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)
        for m in regular:
            render_message(m)

    if not msgs:
        st.markdown("""<div class="instr-card" style="text-align:center;padding:30px;">
          <div class="instr-title">No messages yet</div>
          <div class="instr-step" style="justify-content:center;">Post the first message above to kick things off.</div>
        </div>""", unsafe_allow_html=True)


with tab6:
    render_comms()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 6 — DEAD STOCK / AGING WATCH LIST
# ════════════════════════════════════════════════════════════════════════════════
def render_dead_stock():
    st.markdown('<div class="sec-head"><div class="sec-head-text">⏳ Aging Stock Watch List</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="instr-card"><div class="instr-title">📋 How to Export from Dutchie</div>
    <div class="instr-steps">
      <div class="instr-step"><span class="instr-icon">1</span><span>In Dutchie Backend, export your <strong>full inventory</strong> (any rooms/categories)</span></div>
      <div class="instr-step"><span class="instr-icon fire">🔥</span><span>Include at minimum: <strong>Product, Available, Inventory date, Expiration date</strong></span></div>
      <div class="instr-step"><span class="instr-icon">i</span><span>This is a <strong>watch list to investigate</strong>, not a sales report — it flags old stock by age, not proven non-sales</span></div>
    </div></div>""", unsafe_allow_html=True)

    WATCH_DAYS = 45          # age threshold
    EXP_SOON_DAYS = 60       # expiring-soon threshold

    ds_file = st.file_uploader(" ", type=["csv"], key="deadstock_csv", label_visibility="collapsed")
    if ds_file is None:
        return

    try:
        df = pd.read_csv(ds_file, dtype=str)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return

    df.columns = [str(c).strip('="').strip() for c in df.columns]

    def col(*names):
        """Return the first matching column name present in the df."""
        for n in names:
            if n in df.columns:
                return n
        return None

    c_product = col("Product", "Online title")
    c_avail   = col("Available", "Quantity (including allocated)")
    c_invdate = col("Inventory date", "Packaging date")
    c_pkgdate = col("Packaging date")
    c_expdate = col("Expiration date")
    c_room    = col("Room")
    c_cat     = col("Category", "Master category")
    c_sale    = col("Is on sale")
    c_brand   = col("Brand")
    c_price   = col("Current price", "Price (Catalog)")

    if not c_product or not c_invdate:
        st.error("This CSV is missing required columns (Product and Inventory/Packaging date). Re-export with those fields included.")
        return

    def cln(v):
        return str(v).strip('="').strip() if v is not None and str(v) != 'nan' else ""

    def pdate(s):
        s = cln(s)
        if not s:
            return None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    def to_int(v):
        v = cln(v)
        digits = "".join(ch for ch in v if ch.isdigit())
        return int(digits) if digits else 0

    today = date.today()

    # ── Aggregate by product (sum quantity across rooms, keep oldest date) ─────
    agg = {}
    for _, row in df.iterrows():
        product = cln(row.get(c_product))
        if not product or product.lower() == "nan":
            continue

        ref = pdate(row.get(c_pkgdate)) if c_pkgdate else None
        ref = ref or pdate(row.get(c_invdate))
        if ref is None:
            continue
        age = (today - ref).days

        exp = pdate(row.get(c_expdate)) if c_expdate else None
        days_to_exp = (exp - today).days if exp else None

        qty   = to_int(row.get(c_avail)) if c_avail else 0
        room  = cln(row.get(c_room)) if c_room else ""
        cat   = cln(row.get(c_cat)) if c_cat else "Uncategorized"
        brand = cln(row.get(c_brand)) if c_brand else ""
        price = cln(row.get(c_price)) if c_price else ""
        on_sale = cln(row.get(c_sale)).lower() in ("yes", "true", "1") if c_sale else False

        if product not in agg:
            agg[product] = {
                "product": product, "age": age, "qty": qty,
                "days_to_exp": days_to_exp, "cat": cat, "brand": brand,
                "price": price, "on_sale": on_sale, "rooms": set()
            }
        else:
            a = agg[product]
            a["age"] = max(a["age"], age)               # oldest wins
            a["qty"] += qty                             # sum across rooms
            if days_to_exp is not None:
                a["days_to_exp"] = days_to_exp if a["days_to_exp"] is None else min(a["days_to_exp"], days_to_exp)
            a["on_sale"] = a["on_sale"] or on_sale
        if room:
            agg[product]["rooms"].add(room)

    # ── Filter to watch candidates (45+ days) ─────────────────────────────────
    watch = [v for v in agg.values() if v["age"] >= WATCH_DAYS]

    total_skus = len(agg)
    watch_count = len(watch)
    expiring = [v for v in watch if v["days_to_exp"] is not None and v["days_to_exp"] < EXP_SOON_DAYS]
    watch_units = sum(v["qty"] for v in watch)

    # ── Summary tiles ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="checklist-summary">
      <div class="cs-tile cs-tile-total"><div class="cs-num">{total_skus}</div><div class="cs-lbl">Total SKUs</div></div>
      <div class="cs-tile cs-tile-afternoon"><div class="cs-num">{watch_count}</div><div class="cs-lbl">⏳ Aging 45+d</div></div>
      <div class="cs-tile cs-tile-handover"><div class="cs-num">{watch_units}</div><div class="cs-lbl">Units Stuck</div></div>
      <div class="cs-tile cs-tile-morning" style="border:none"><div class="cs-num" style="color:#FCA5A5">{len(expiring)}</div><div class="cs-lbl">🔴 Exp &lt;60d</div></div>
    </div>""", unsafe_allow_html=True)

    if not watch:
        st.success(f"✅ No products aged {WATCH_DAYS}+ days. Inventory is fresh!")
        return

    # ── Severity tiering by age ───────────────────────────────────────────────
    def severity(age):
        if age >= 90:  return "critical"
        if age >= 60:  return "high"
        return "watch"

    def render_row(v):
        sev = severity(v["age"])
        flags = ""
        if v["days_to_exp"] is not None and v["days_to_exp"] < EXP_SOON_DAYS:
            if v["days_to_exp"] < 0:
                flags += '<span class="ds-flag dsf-exp">⚠️ EXPIRED</span>'
            else:
                flags += f'<span class="ds-flag dsf-exp">⏰ EXP {v["days_to_exp"]}d</span>'
        if v["on_sale"]:
            flags += '<span class="ds-flag dsf-sale">🏷️ ON SALE</span>'
        flags_html = f'<div class="ds-flags">{flags}</div>' if flags else ''

        rooms = ", ".join(sorted(v["rooms"])) if v["rooms"] else "—"
        brand = f'{v["brand"]} · ' if v["brand"] else ''
        price = f' · ${v["price"]}' if v["price"] else ''
        name = v["product"].replace('<', '&lt;').replace('>', '&gt;')

        st.markdown(f"""
        <div class="ds-row ds-row-{sev}">
          <div class="ds-age">
            <div class="ds-age-num-{sev}">{v["age"]}</div>
            <div class="ds-age-unit">Days</div>
          </div>
          <div>
            <div class="ds-name">{name}</div>
            <div class="ds-meta">{brand}{rooms}{price}</div>
            {flags_html}
          </div>
          <div class="ds-qty">
            <div class="ds-qty-num">{v["qty"]}</div>
            <div class="ds-qty-lbl">In Stock</div>
          </div>
        </div>""", unsafe_allow_html=True)

    # ── Group by Category, sort each group age-first (oldest first) ────────────
    by_cat = defaultdict(list)
    for v in watch:
        by_cat[v["cat"]].append(v)

    # Order categories by their oldest item
    cat_order = sorted(by_cat.keys(), key=lambda c: -max(v["age"] for v in by_cat[c]))

    for cat in cat_order:
        items = sorted(by_cat[cat], key=lambda v: -v["age"])  # age-first
        oldest = items[0]["age"]
        st.markdown(f"""
        <div class="ds-group-hdr">
          <span>{cat or 'Uncategorized'}</span>
          <span class="ds-group-count">{len(items)} item(s) · oldest {oldest}d</span>
        </div>""", unsafe_allow_html=True)
        for v in items:
            render_row(v)

    # ── Export the watch list as a print-ready PDF ────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    summary = {
        "watch_count": watch_count,
        "watch_units": watch_units,
        "expiring": len(expiring),
        "total_skus": total_skus,
    }
    pdf_bytes = build_aging_pdf(watch, summary, today,
                                watch_days=WATCH_DAYS, exp_soon_days=EXP_SOON_DAYS)
    st.download_button(
        "📥  DOWNLOAD AGING STOCK PDF",
        pdf_bytes,
        f"AgingStock_Watchlist_{today.isoformat()}.pdf",
        "application/pdf",
    )


with tab4:
    render_dead_stock()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 7 — CROSSWORD
# ════════════════════════════════════════════════════════════════════════════════
def _crossword_html(puzzle):
    """Build the interactive crossword as a self-contained HTML/JS component."""
    data_json = json.dumps(puzzle)
    # Approx component height: grid + clue panel. Grid drawn with CSS, scrollable.
    return """
<div id="xw-root">
  <style>
    #xw-root { font-family: 'Inter', -apple-system, sans-serif; color: #E2E8F0; }
    .xw-wrap { display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-start; }
    .xw-grid-panel { flex: 1 1 420px; min-width: 300px; }
    .xw-clue-panel { flex: 1 1 320px; min-width: 260px; max-height: 620px; overflow-y: auto; }
    .xw-grid-scroll { overflow: auto; max-width: 100%; border-radius: 10px;
                      background: #0D1117; padding: 10px; border: 1px solid rgba(139,92,246,.25); }
    table.xw { border-collapse: collapse; margin: 0 auto; }
    table.xw td { width: 26px; height: 26px; padding: 0; position: relative;
                  border: 1px solid #2A3344; text-align: center; vertical-align: middle; }
    td.blk { background: #0D1117; border-color: #0D1117; }
    td.cell { background: #F8FAFC; cursor: pointer; }
    td.cell input { width: 100%; height: 100%; border: none; background: transparent;
                    text-align: center; font-size: 15px; font-weight: 700; color: #0F172A;
                    text-transform: uppercase; padding: 0; margin: 0; outline: none;
                    caret-color: transparent; cursor: pointer; }
    td.cell.hl input { background: rgba(167,139,250,.35); }
    td.cell.active input { background: rgba(245,200,66,.75); }
    td.cell.correct input { color: #059669; }
    td.cell.wrong input { color: #DC2626; }
    .xw-num { position: absolute; top: 0px; left: 1px; font-size: 7px;
              font-weight: 700; color: #475569; line-height: 1; pointer-events: none; }
    .xw-bar { display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 12px 0; }
    .xw-btn { background: linear-gradient(135deg,#8B5CF6,#5B21B6); color: #fff; border: none;
              border-radius: 8px; font-weight: 700; font-size: 10px; letter-spacing: .8px;
              text-transform: uppercase; padding: 9px 13px; cursor: pointer;
              font-family: inherit; transition: transform .15s; }
    .xw-btn:hover { transform: translateY(-1px); }
    .xw-btn.alt { background: #1E293B; border: 1px solid rgba(139,92,246,.3); }
    .xw-active-clue { background: #161B2A; border-left: 3px solid #A78BFA; border-radius: 8px;
                      padding: 12px 14px; margin-bottom: 12px; font-size: 14px; min-height: 20px;
                      color: #E2E8F0; }
    .xw-active-clue b { color: #A78BFA; }
    .xw-clue-head { font-family: 'Syne', sans-serif; font-size: 13px; font-weight: 800;
                    color: #A78BFA; letter-spacing: .5px; text-transform: uppercase;
                    margin: 14px 0 8px 0; border-bottom: 1px solid rgba(139,92,246,.2);
                    padding-bottom: 5px; }
    .xw-clue { font-size: 12.5px; color: #94A3B8; padding: 5px 8px; border-radius: 6px;
               cursor: pointer; line-height: 1.4; display: flex; gap: 7px; }
    .xw-clue:hover { background: rgba(139,92,246,.1); color: #E2E8F0; }
    .xw-clue.sel { background: rgba(167,139,250,.18); color: #fff; }
    .xw-clue .cn { font-weight: 700; color: #64748B; min-width: 20px; }
    .xw-clue.done .cn { color: #34D399; }
    .xw-win { background: rgba(52,211,153,.12); border: 1px solid rgba(52,211,153,.4);
              color: #6EE7B7; border-radius: 10px; padding: 14px; margin-bottom: 12px;
              font-weight: 700; text-align: center; display: none; }
  </style>

  <div class="xw-win" id="xw-win">🎉 Solved it! Nice work.</div>
  <div class="xw-bar">
    <button class="xw-btn" onclick="xwCheck()">✓ Check</button>
    <button class="xw-btn alt" onclick="xwRevealLetter()">Reveal Letter</button>
    <button class="xw-btn alt" onclick="xwRevealWord()">Reveal Word</button>
    <button class="xw-btn alt" onclick="xwClear()">Clear</button>
  </div>

  <div class="xw-wrap">
    <div class="xw-grid-panel">
      <div class="xw-active-clue" id="xw-active-clue">Click a square to begin.</div>
      <div class="xw-grid-scroll"><table class="xw" id="xw-table"></table></div>
    </div>
    <div class="xw-clue-panel">
      <div class="xw-clue-head">Across</div>
      <div id="xw-across"></div>
      <div class="xw-clue-head">Down</div>
      <div id="xw-down"></div>
    </div>
  </div>
</div>

<script>
const PUZ = __DATA__;
const H = PUZ.height, W = PUZ.width, SOL = PUZ.solution, NUMS = PUZ.numbers;
const ACROSS = PUZ.across, DOWN = PUZ.down;

let dir = "across";      // current direction
let cur = null;          // {r,c}
const inputs = {};       // "r,c" -> input element

function key(r,c){ return r+","+c; }
function isCell(r,c){ return r>=0 && r<H && c>=0 && c<W && SOL[r][c] !== null; }

// Build grid
const tbl = document.getElementById("xw-table");
for (let r=0; r<H; r++){
  const tr = document.createElement("tr");
  for (let c=0; c<W; c++){
    const td = document.createElement("td");
    if (SOL[r][c] === null){ td.className = "blk"; }
    else {
      td.className = "cell";
      const n = NUMS[key(r,c)];
      if (n){ const s=document.createElement("span"); s.className="xw-num"; s.textContent=n; td.appendChild(s); }
      const inp = document.createElement("input");
      inp.maxLength = 1;
      inp.dataset.r = r; inp.dataset.c = c;
      inp.addEventListener("focus", ()=>onFocus(r,c));
      inp.addEventListener("mousedown", (e)=>{ if (cur && cur.r===r && cur.c===c){ toggleDir(); }});
      inp.addEventListener("keydown", (e)=>onKey(e,r,c));
      inp.addEventListener("input", (e)=>onInput(e,r,c));
      td.appendChild(inp);
      inputs[key(r,c)] = inp;
    }
    tr.appendChild(td);
  }
  tbl.appendChild(tr);
}

function clearHL(){ document.querySelectorAll("td.cell").forEach(td=>td.classList.remove("hl","active")); }

function wordCells(r,c,d){
  const cells = [];
  let sr=r, sc=c;
  const dr = d==="down"?1:0, dc = d==="across"?1:0;
  while (isCell(sr-dr, sc-dc)){ sr-=dr; sc-=dc; }
  while (isCell(sr,sc)){ cells.push({r:sr,c:sc}); sr+=dr; sc+=dc; }
  return cells;
}

function findEntry(r,c,d){
  const cells = wordCells(r,c,d);
  if (cells.length<2) return null;
  const start = cells[0];
  const list = d==="across"?ACROSS:DOWN;
  return list.find(e=>e.row===start.r && e.col===start.c) || null;
}

function onFocus(r,c){
  cur = {r,c};
  // if current dir not valid here, switch
  if (wordCells(r,c,dir).length<2) dir = (dir==="across")?"down":"across";
  highlight();
}
function toggleDir(){
  const other = dir==="across"?"down":"across";
  if (cur && wordCells(cur.r,cur.c,other).length>=2){ dir=other; highlight(); }
}

function highlight(){
  clearHL();
  if (!cur) return;
  const cells = wordCells(cur.r,cur.c,dir);
  cells.forEach(({r,c})=>{ const td=inputs[key(r,c)].parentElement; td.classList.add("hl"); });
  const td = inputs[key(cur.r,cur.c)].parentElement; td.classList.add("active");
  const e = findEntry(cur.r,cur.c,dir);
  const box = document.getElementById("xw-active-clue");
  if (e){ box.innerHTML = "<b>"+e.num+" "+dir.toUpperCase()+"</b> &nbsp; "+e.clue+" &nbsp;("+e.len+")"; }
  // select in clue list
  document.querySelectorAll(".xw-clue").forEach(el=>el.classList.remove("sel"));
  if (e){ const el=document.getElementById("clue-"+dir+"-"+e.num); if(el) el.classList.add("sel"); }
}

function step(r,c,fwd=true){
  const dr = dir==="down"?1:0, dc = dir==="across"?1:0;
  let nr=r+(fwd?dr:-dr), nc=c+(fwd?dc:-dc);
  if (isCell(nr,nc)){ inputs[key(nr,nc)].focus(); }
}

function onInput(e,r,c){
  const v = e.target.value.toUpperCase().replace(/[^A-Z]/g,"");
  e.target.value = v;
  e.target.parentElement.classList.remove("correct","wrong");
  if (v){ step(r,c,true); }
  checkWin();
}
function onKey(e,r,c){
  const k = e.key;
  if (k==="Backspace"){
    if (!e.target.value){ e.preventDefault(); step(r,c,false);
      const dr=dir==="down"?1:0,dc=dir==="across"?1:0;
      const pr=r-dr,pc=c-dc; if(isCell(pr,pc)){inputs[key(pr,pc)].value="";}
    } else { e.target.parentElement.classList.remove("correct","wrong"); }
  } else if (k==="ArrowRight"){ e.preventDefault(); dir="across"; if(isCell(r,c+1))inputs[key(r,c+1)].focus(); else highlight(); }
  else if (k==="ArrowLeft"){ e.preventDefault(); dir="across"; if(isCell(r,c-1))inputs[key(r,c-1)].focus(); else highlight(); }
  else if (k==="ArrowDown"){ e.preventDefault(); dir="down"; if(isCell(r+1,c))inputs[key(r+1,c)].focus(); else highlight(); }
  else if (k==="ArrowUp"){ e.preventDefault(); dir="down"; if(isCell(r-1,c))inputs[key(r-1,c)].focus(); else highlight(); }
  else if (k===" "){ e.preventDefault(); toggleDir(); }
}

// Clue lists
function buildClues(list, dirName, container){
  list.forEach(e=>{
    const div = document.createElement("div");
    div.className = "xw-clue";
    div.id = "clue-"+dirName+"-"+e.num;
    div.innerHTML = "<span class='cn'>"+e.num+"</span><span>"+e.clue+"</span>";
    div.addEventListener("click", ()=>{ dir=dirName; inputs[key(e.row,e.col)].focus(); });
    container.appendChild(div);
  });
}
buildClues(ACROSS,"across",document.getElementById("xw-across"));
buildClues(DOWN,"down",document.getElementById("xw-down"));

function xwCheck(){
  for (let r=0;r<H;r++) for(let c=0;c<W;c++){
    if (SOL[r][c]===null) continue;
    const inp=inputs[key(r,c)]; const td=inp.parentElement;
    td.classList.remove("correct","wrong");
    if (inp.value){ td.classList.add(inp.value===SOL[r][c]?"correct":"wrong"); }
  }
}
function xwRevealLetter(){
  if(!cur) return;
  const inp=inputs[key(cur.r,cur.c)];
  inp.value=SOL[cur.r][cur.c];
  inp.parentElement.classList.add("correct");
  checkWin();
}
function xwRevealWord(){
  if(!cur) return;
  wordCells(cur.r,cur.c,dir).forEach(({r,c})=>{
    const inp=inputs[key(r,c)]; inp.value=SOL[r][c]; inp.parentElement.classList.add("correct");
  });
  checkWin();
}
function xwClear(){
  for(let r=0;r<H;r++)for(let c=0;c<W;c++){
    if(SOL[r][c]===null)continue;
    const inp=inputs[key(r,c)]; inp.value=""; inp.parentElement.classList.remove("correct","wrong");
  }
  document.getElementById("xw-win").style.display="none";
  markDoneClues();
}
function isEntryDone(e){
  const dr=e.dir==="down"?1:0,dc=e.dir==="across"?1:0;
  for(let i=0;i<e.len;i++){ const inp=inputs[key(e.row+dr*i,e.col+dc*i)]; if(!inp||inp.value!==SOL[e.row+dr*i][e.col+dc*i])return false; }
  return true;
}
function markDoneClues(){
  [["across",ACROSS],["down",DOWN]].forEach(([dn,list])=>{
    list.forEach(e=>{ const el=document.getElementById("clue-"+dn+"-"+e.num);
      if(el){ el.classList.toggle("done", isEntryDone(e)); } });
  });
}
function checkWin(){
  markDoneClues();
  for(let r=0;r<H;r++)for(let c=0;c<W;c++){
    if(SOL[r][c]===null)continue;
    if(inputs[key(r,c)].value!==SOL[r][c])return;
  }
  document.getElementById("xw-win").style.display="block";
}
</script>
""".replace("__DATA__", data_json)


def render_crossword():
    st.markdown('<div class="sec-head"><div class="sec-head-text">🧩 Daily Crossword</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    if not CROSSWORD_AVAILABLE:
        st.error("Crossword engine files missing — make sure `crossword_data.py` and `crossword_gen.py` are committed to your repo root.")
        return

    st.markdown("""
    <div class="instr-card"><div class="instr-title">🧩 How to Play</div>
    <div class="instr-steps">
      <div class="instr-step"><span class="instr-icon">1</span><span>Click a square and type. <strong>Click again</strong> (or press Space) to switch Across/Down</span></div>
      <div class="instr-step"><span class="instr-icon">2</span><span>Click any clue to jump to it. Arrow keys move around the grid</span></div>
      <div class="instr-step"><span class="instr-icon fire">🔥</span><span>50 words, fresh topics every puzzle — hit <strong>New Puzzle</strong> for a new board</span></div>
    </div></div>""", unsafe_allow_html=True)

    # Generate + cache the puzzle in session state
    if "xw_puzzle" not in st.session_state:
        with st.spinner("Building a fresh 50-word puzzle…"):
            st.session_state.xw_puzzle = generate_crossword(get_flat_word_list(), target=50)

    col_new, col_info = st.columns([1, 3])
    with col_new:
        if st.button("🔀  NEW PUZZLE", type="primary"):
            with st.spinner("Building a fresh puzzle…"):
                st.session_state.xw_puzzle = generate_crossword(
                    get_flat_word_list(), target=50, seed=random.randint(1, 10_000_000))
            st.rerun()

    puzzle = st.session_state.xw_puzzle
    with col_info:
        st.markdown(
            f'<div style="padding-top:10px;font-family:JetBrains Mono,monospace;font-size:12px;color:#94A3B8;">'
            f'{puzzle["word_count"]} words · {len(puzzle["across"])} across · {len(puzzle["down"])} down · '
            f'{puzzle["height"]}×{puzzle["width"]} grid</div>',
            unsafe_allow_html=True)

    # Estimate height: grid pixels + clue panel; allow generous space.
    grid_px = puzzle["height"] * 27 + 220
    components.html(_crossword_html(puzzle), height=max(640, grid_px), scrolling=True)


with tab7:
    render_crossword()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 8 — BURN DOWN (cannabis hangman)
# ════════════════════════════════════════════════════════════════════════════════
def _hangman_html(entries):
    """Self-contained HTML/JS hangman with a burning-joint graphic."""
    data_json = json.dumps(entries)
    return r"""
<div id="hm-root">
  <style>
    #hm-root { font-family: 'Inter', -apple-system, sans-serif; color: #E2E8F0;
               max-width: 720px; margin: 0 auto; }
    .hm-stage { background: #0D1117; border: 1px solid rgba(245,158,11,.25);
                border-radius: 14px; padding: 10px; margin-bottom: 14px; text-align: center; }
    .hm-score { display: flex; justify-content: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
    .hm-pill { font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 700;
               padding: 6px 14px; border-radius: 50px; letter-spacing: .5px; }
    .hm-pill.cat { background: rgba(139,92,246,.13); border: 1px solid rgba(139,92,246,.3); color: #A78BFA; }
    .hm-pill.win { background: rgba(52,211,153,.13); border: 1px solid rgba(52,211,153,.3); color: #34D399; }
    .hm-pill.loss { background: rgba(239,68,68,.13); border: 1px solid rgba(239,68,68,.3); color: #FCA5A5; }
    .hm-pill.left { background: rgba(245,158,11,.13); border: 1px solid rgba(245,158,11,.3); color: #F59E0B; }
    .hm-word { text-align: center; font-family: 'JetBrains Mono', monospace; font-weight: 700;
               font-size: 26px; letter-spacing: 6px; color: #fff; margin: 6px 0 4px 0;
               line-height: 1.5; word-break: break-word; }
    .hm-word .sp { display: inline-block; width: 18px; }
    .hm-msg { text-align: center; min-height: 22px; font-size: 14px; font-weight: 600; margin-bottom: 12px; }
    .hm-msg.good { color: #34D399; } .hm-msg.bad { color: #FCA5A5; }
    .hm-keys { display: grid; grid-template-columns: repeat(9, 1fr); gap: 6px; max-width: 560px; margin: 0 auto 14px; }
    .hm-key { aspect-ratio: 1/1; border: none; border-radius: 8px; background: #1E293B;
              color: #E2E8F0; font-family: inherit; font-weight: 700; font-size: 15px;
              cursor: pointer; transition: transform .12s, background .12s; }
    .hm-key:hover:not(:disabled) { transform: translateY(-2px); background: #2A3344; }
    .hm-key.hit { background: linear-gradient(135deg,#10B981,#065F46); color: #fff; }
    .hm-key.miss { background: linear-gradient(135deg,#7F1D1D,#450a0a); color: #FCA5A5; }
    .hm-key:disabled { cursor: default; }
    .hm-bar { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
    .hm-btn { background: linear-gradient(135deg,#8B5CF6,#5B21B6); color: #fff; border: none;
              border-radius: 8px; font-weight: 700; font-size: 11px; letter-spacing: .8px;
              text-transform: uppercase; padding: 11px 22px; cursor: pointer; font-family: inherit;
              transition: transform .15s; }
    .hm-btn:hover { transform: translateY(-1px); }
    .hm-btn.alt { background: #1E293B; border: 1px solid rgba(139,92,246,.3); }
    @media (max-width: 480px){ .hm-keys{ grid-template-columns: repeat(7,1fr);} .hm-word{font-size:21px;letter-spacing:4px;} }
  </style>

  <div class="hm-score">
    <span class="hm-pill cat" id="hm-cat">—</span>
    <span class="hm-pill left" id="hm-left">6 puffs left</span>
    <span class="hm-pill win" id="hm-wins">Wins 0</span>
    <span class="hm-pill loss" id="hm-losses">Cashed 0</span>
  </div>

  <div class="hm-stage"><div id="hm-svg"></div></div>

  <div class="hm-word" id="hm-word"></div>
  <div class="hm-msg" id="hm-msg"></div>
  <div class="hm-keys" id="hm-keys"></div>

  <div class="hm-bar">
    <button class="hm-btn alt" id="hm-hint" onclick="hmHint()">💡 Hint</button>
    <button class="hm-btn" onclick="hmNew()">🔀 New Word</button>
  </div>
</div>

<script>
const BANK = __DATA__;
const MAXW = 6;
let answer = "", category = "", hint = "";
let guessed = new Set(), wrong = 0, over = false, wins = 0, losses = 0, hintUsed = false;

function pick(){
  const e = BANK[Math.floor(Math.random()*BANK.length)];
  answer = e[0]; category = e[1]; hint = e[2];
}

// ── Burning joint SVG ───────────────────────────────────────────────────────
function jointSVG(w){
  const frac = w / MAXW;
  const fullLeft = 70, filterX = 290, bodyLen = filterX - fullLeft;
  const burnX = fullLeft + bodyLen * frac;
  const cy = 110, th = 22, top = cy - th/2, bot = cy + th/2;
  let s = '<svg viewBox="0 0 360 200" width="100%" style="max-width:420px">';
  // filter
  s += `<rect x="${filterX}" y="${top}" width="26" height="${th}" rx="5" fill="#C49A6C"/>`;
  if (w < MAXW){
    // paper body
    s += `<rect x="${burnX}" y="${top}" width="${filterX-burnX+2}" height="${th}" rx="6" fill="#F5F3EB"/>`;
    s += `<line x1="${burnX+6}" y1="${cy}" x2="${filterX}" y2="${cy}" stroke="#DCD8CD" stroke-width="1"/>`;
    if (w > 0){
      // ember (layered glow)
      s += `<circle cx="${burnX}" cy="${cy}" r="15" fill="#4a1c00"/>`;
      s += `<circle cx="${burnX}" cy="${cy}" r="11" fill="#b43c0a"/>`;
      s += `<circle cx="${burnX}" cy="${cy}" r="7" fill="#ff8c1e"/>`;
      s += `<circle cx="${burnX}" cy="${cy}" r="3.5" fill="#ffdc78"/>`;
      // ash bits
      for (let i=0;i<w;i++){
        const ax = burnX - 14 - i*9, ay = cy + 6 + (i%2)*6;
        s += `<ellipse cx="${ax}" cy="${ay}" rx="3" ry="2" fill="#6e6e6e"/>`;
      }
      // smoke
      for (let i=0;i<3;i++){
        let path = `M ${burnX+i*3} ${cy-14}`;
        for (let t=1;t<6;t++){ path += ` Q ${burnX+i*3+(t%2?9:-9)} ${cy-14-t*9+4} ${burnX+i*3} ${cy-14-t*9}`; }
        s += `<path d="${path}" fill="none" stroke="#8a8a8a" stroke-width="2" stroke-linecap="round" opacity="${0.5 - i*0.12}"/>`;
      }
    }
  } else {
    // cashed: ash pile + filter only
    for (let i=0;i<8;i++){
      const ax = filterX - 12 - i*12, ay = cy + 8, r = 4 + (i%3);
      s += `<ellipse cx="${ax}" cy="${ay}" rx="${r}" ry="${r/2+1}" fill="#${(90+i*4).toString(16)}${(90+i*4).toString(16)}60"/>`;
    }
  }
  s += '</svg>';
  return s;
}

function renderWord(){
  const html = answer.split("").map(ch=>{
    if (ch === " ") return '<span class="sp"></span>';
    const show = guessed.has(ch) || over;
    return show ? ch : "_";
  }).join("");
  document.getElementById("hm-word").innerHTML = html;
}

function renderKeys(){
  const box = document.getElementById("hm-keys");
  box.innerHTML = "";
  for (let i=65;i<=90;i++){
    const ch = String.fromCharCode(i);
    const b = document.createElement("button");
    b.className = "hm-key"; b.textContent = ch;
    if (guessed.has(ch)){
      b.disabled = true;
      b.classList.add(answer.includes(ch) ? "hit" : "miss");
    }
    if (over) b.disabled = true;
    b.onclick = ()=>guess(ch);
    box.appendChild(b);
  }
}

function refresh(){
  document.getElementById("hm-svg").innerHTML = jointSVG(wrong);
  document.getElementById("hm-cat").textContent = category;
  document.getElementById("hm-left").textContent = (MAXW-wrong)+" puff"+((MAXW-wrong)===1?"":"s")+" left";
  document.getElementById("hm-wins").textContent = "Wins "+wins;
  document.getElementById("hm-losses").textContent = "Cashed "+losses;
  renderWord(); renderKeys();
}

function guess(ch){
  if (over || guessed.has(ch)) return;
  guessed.add(ch);
  const msg = document.getElementById("hm-msg");
  if (answer.includes(ch)){
    msg.className = "hm-msg good"; msg.textContent = "Nice — keep going!";
    // win?
    const done = answer.split("").every(c=>c===" "||guessed.has(c));
    if (done){ over=true; wins++; msg.textContent = "🎉 Solved it! Well played."; }
  } else {
    wrong++;
    if (wrong >= MAXW){ over=true; losses++;
      msg.className="hm-msg bad"; msg.innerHTML = "🔥 Cashed! It was <b>"+answer+"</b>"; }
    else { msg.className="hm-msg bad"; msg.textContent = "Puff burned — "+(MAXW-wrong)+" left."; }
  }
  refresh();
}

function hmHint(){
  if (over || hintUsed) return;
  hintUsed = true;
  const msg = document.getElementById("hm-msg");
  msg.className = "hm-msg"; msg.style.color = "#A78BFA";
  msg.textContent = "💡 " + hint;
  document.getElementById("hm-hint").disabled = true;
}

function hmNew(){
  pick(); guessed = new Set(); wrong = 0; over = false; hintUsed = false;
  const msg = document.getElementById("hm-msg"); msg.className="hm-msg"; msg.textContent="";
  document.getElementById("hm-hint").disabled = false;
  refresh();
}

document.addEventListener("keydown", (e)=>{
  const k = e.key.toUpperCase();
  if (k.length===1 && k>="A" && k<="Z") guess(k);
});

hmNew();
</script>
""".replace("__DATA__", data_json)


def render_hangman():
    st.markdown('<div class="sec-head"><div class="sec-head-text">🔥 Burn Down</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    if not HANGMAN_AVAILABLE:
        st.error("Game word bank missing — make sure `hangman_data.py` is committed to your repo root.")
        return

    st.markdown("""
    <div class="instr-card"><div class="instr-title">🔥 How to Play</div>
    <div class="instr-steps">
      <div class="instr-step"><span class="instr-icon">1</span><span>Guess the hidden word or phrase one letter at a time — tap a key or use your keyboard</span></div>
      <div class="instr-step"><span class="instr-icon fire">🔥</span><span>Every wrong letter <strong>burns the joint down</strong>. Six misses and it's <strong>Cashed</strong></span></div>
      <div class="instr-step"><span class="instr-icon">💡</span><span>Stuck? The category is always shown, and you get one <strong>Hint</strong> per word</span></div>
    </div></div>""", unsafe_allow_html=True)

    entries = get_hangman_entries()
    components.html(_hangman_html(entries), height=560, scrolling=True)


with tab8:
    render_hangman()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 9 — PREROLL TAGS (color-coded by strain type)
# ════════════════════════════════════════════════════════════════════════════════
def render_preroll_tags():
    st.markdown('<div class="sec-head"><div class="sec-head-text">🌿 Preroll Hook Tags</div><div class="sec-head-line"></div></div>', unsafe_allow_html=True)

    if not PREROLL_AVAILABLE:
        st.error("Preroll engine missing — commit `preroll_tags.py` to your repo root.")
        return

    TEMPLATES = {
        "sativa": "Sativa_Prerolls_Updated.pdf",
        "hybrid": "Hybrid_Prerolls_Updated_-_Copy.pdf",
        "indica": "Indica_Prerolls_Updated.pdf",
    }
    missing = [f for f in TEMPLATES.values() if not os.path.exists(f)]
    if missing:
        st.error("Missing template file(s) in repo root: " + ", ".join(missing))
        return

    st.markdown("""
    <div class="instr-card"><div class="instr-title">📋 How it Works</div>
    <div class="instr-steps">
      <div class="instr-step"><span class="instr-icon">1</span><span>Export prerolls with <strong>Product, Strain, THC, Current price</strong></span></div>
      <div class="instr-step"><span class="instr-icon">🔴</span><span><strong>Sativa</strong> → red/orange border &nbsp;·&nbsp; <span style="color:#A78BFA"><strong>Indica</strong></span> → purple &nbsp;·&nbsp; <span style="color:#34D399"><strong>Hybrid / No&nbsp;Strain</strong></span> → blue/green</span></div>
      <div class="instr-step"><span class="instr-icon fire">🔥</span><span>Tags are grouped into <strong>color-coded pages by strain type</strong> in one PDF</span></div>
    </div></div>""", unsafe_allow_html=True)

    pr_file = st.file_uploader(" ", type=["csv"], key="preroll_csv", label_visibility="collapsed")
    if pr_file is None:
        return

    df = pd.read_csv(pr_file)
    df.columns = [str(c).strip('="').strip() for c in df.columns]
    if "Product" not in df.columns or "Strain" not in df.columns:
        st.error("CSV must include at least `Product` and `Strain` columns.")
        return
    price_col = "Current price" if "Current price" in df.columns else "Price"

    raw_rows = []
    for _, row in df.iterrows():
        product = str(row.get("Product", "")).strip('="').strip()
        if not product or product.lower() == "nan":
            continue
        parts  = [p.strip() for p in product.split("|")]
        brand  = parts[0].upper() if len(parts) >= 1 else ""
        strain = parts[1].upper() if len(parts) >= 2 else product.upper()
        # Build the brand line as Brand | Weight | Pack, omitting any missing piece.
        brand_bits = [brand] if brand else []
        # weight (handles 1G, 3.5G, and leading-decimal like .5G/.7G)
        wt = re.search(r'(\d*\.?\d+)\s*g\b', product, re.IGNORECASE)
        if wt:
            v = wt.group(1)
            if v.endswith(".0"): v = v[:-2]
            brand_bits.append(f"{v}G")
        # multi-pack count, normalized to PK (e.g. 5PK, 14PK, 28PK)
        pack = None
        mx = re.search(r'\b(\d+)\s*[xX]\s*[\d.]', product)  # "5 x 1G", "28 x 1G"
        if mx:
            pack = f"{int(mx.group(1))}PK"
        else:
            mc = re.search(r'(\d+)\s*(?:ct|pk|pks|pcs?|count|counts|pack|packs|pieces?|cnt)\b',
                           product, re.IGNORECASE)
            if mc:
                pack = f"{int(mc.group(1))}PK"
        if pack:
            brand_bits.append(pack)
        brand = " | ".join(brand_bits)
        # THC: drop decimals without rounding (e.g. "40.70 %" -> "40 %") so the
        # THC/price line can render larger and stay readable from the counter.
        thc_raw = str(row.get("THC", "")).strip('="').strip()
        tm = re.search(r'(\d+)(?:\.\d+)?', thc_raw)
        if tm:
            thc = f"{tm.group(1)} %" if "%" in thc_raw else tm.group(1)
        else:
            thc = thc_raw
        rp  = str(row.get(price_col, "0")).replace("$", "").strip('="').strip()
        pdg = "".join(c for c in rp if c.isdigit() or c == ".")
        try:
            pv = float(pdg) if pdg else 0.0
            price = f"${int(pv)}" if pv == int(pv) else f"${pv:.2f}"
        except ValueError:
            price = "$0"
        stype = preroll_tags.classify_type(str(row.get("Strain", "")))
        raw_rows.append({"brand": brand, "strain": strain, "thc": thc,
                         "price": price, "type": stype, "product": product})

    if not raw_rows:
        st.error("No valid product rows found in the CSV.")
        return

    # Dedup on full product + THC (keeps weight/potency variants separate)
    seen, rows = set(), []
    for r in raw_rows:
        key = (r["product"].strip().lower(), r["thc"].strip().lower())
        if key not in seen:
            seen.add(key); rows.append(r)

    from collections import Counter
    counts = Counter(r["type"] for r in rows)
    st.markdown(f"""
    <div class="metric-row">
      <div class="m-tile"><div class="m-num">{counts.get('sativa',0)}</div><div class="m-lbl">🔴 Sativa</div></div>
      <div class="m-tile"><div class="m-num">{counts.get('hybrid',0)}</div><div class="m-lbl">🟢 Hybrid</div></div>
      <div class="m-tile"><div class="m-num">{counts.get('indica',0)}</div><div class="m-lbl">🟣 Indica</div></div>
    </div>""", unsafe_allow_html=True)

    preview = pd.DataFrame(rows)[["brand", "strain", "thc", "price", "type"]]
    preview.columns = ["Brand", "Strain", "THC", "Price", "Type"]
    st.dataframe(preview, use_container_width=True, hide_index=True)

    if st.button("🖨️  GENERATE PREROLL TAGS", type="primary"):
        grouped = {}
        for r in rows:
            grouped.setdefault(r["type"], []).append(r)
        with st.spinner(f"Building tags for {len(rows)} prerolls…"):
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    pdf_bytes = preroll_tags.build_separate(TEMPLATES, grouped, tmp)
            except FileNotFoundError:
                st.error("pdftk not found — add `pdftk` to packages.txt.")
                return
            except Exception as e:
                st.error(f"Error building tags: {e}")
                return
        st.success(f"✅ {len(rows)} preroll tags ready "
                   f"({counts.get('sativa',0)} sativa · {counts.get('hybrid',0)} hybrid · {counts.get('indica',0)} indica)")
        st.download_button("📥  DOWNLOAD PREROLL TAGS PDF", pdf_bytes,
                           "Preroll_Tags.pdf", "application/pdf")


with tab9:
    render_preroll_tags()
