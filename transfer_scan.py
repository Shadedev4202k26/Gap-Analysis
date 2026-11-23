"""Transfer check: tick a Metrc manifest off as the blue tags are scanned.

Before this, a store downloaded the manifest into Excel, deleted everything but
the Package ID column, put a "highlight duplicates" rule over two columns and
typed each scanned tag into the second one. Too many steps for stores that
aren't comfortable in Excel, so here the manifest is uploaded as it comes out
of Metrc and the page finds the package tags itself.

A Metrc package tag is 24 letters and digits (Michigan's start 1A4...). The
manifest's layout isn't something we control, so the tags are found by their
shape rather than by a column position; when the sheet has a column headed
Package (or Package Label / Tag), only that column is read, so a "source
package" column further along can't add tags the truck never carried.

This file holds the matching; `render()` is the page.
"""
import re
from io import BytesIO

import pandas as pd

# Digit, letter, then 22 more letters/digits. Looked for inside a cell, so
# Dutchie-style ="1A40..." wrapping and stray spaces don't matter.
TAG_RE = re.compile(r"(?<![0-9A-Za-z])[0-9][A-Za-z][0-9A-Za-z]{22}(?![0-9A-Za-z])")
MIN_PARTIAL = 5          # fewest trailing characters accepted when a tag won't scan

_TAG_HEADER = re.compile(r"^(package|package (label|tag|id|number|#)|tag|label|metrc (tag|label))$")
_HEADER_WORDS = ("package", "item", "quantity", "qty", "product", "strain", "label", "tag")


def find_tags(text):
    """Every package tag in a piece of text, upper-cased, in order, no repeats."""
    seen, out = set(), []
    for m in TAG_RE.finditer(str(text or "")):
        t = m.group(0).upper()
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _cell(v):
    s = "" if v is None else str(v).strip()
    return "" if s.lower() in ("nan", "none") else s


def _header_row(rows, first_hit):
    """The nearest row above the first tag that looks like column headings."""
    for i in range(first_hit - 1, -1, -1):
        hits = sum(1 for c in rows[i] if any(w in _cell(c).lower() for w in _HEADER_WORDS))
        if hits >= 2:
            return i
    return None


def _pick(heads, exact, contains=(), avoid=()):
    for want in exact:
        for j, h in enumerate(heads):
            if h == want:
                return j
    for want in contains:
        for j, h in enumerate(heads):
            if want in h and not any(a in h for a in avoid):
                return j
    return None


def _from_sheet(df):
    rows = [[_cell(c) for c in r] for r in df.itertuples(index=False)]
    first = next((i for i, r in enumerate(rows) if any(find_tags(c) for c in r)), None)
    if first is None:
        return []
    head = _header_row(rows, first)
    heads = [c.lower() for c in rows[head]] if head is not None else []
    tag_cols = [j for j, h in enumerate(heads) if _TAG_HEADER.match(h)]
    item_col = _pick(heads, ("item", "item name", "product", "product name"),
                     ("item", "product"), avoid=("categor", "type", "unit", "strain"))
    qty_col = _pick(heads, ("quantity", "qty"), ("quantity", "qty"), avoid=("unit", "price", "cost"))
    unit_col = _pick(heads, ("unit of measure", "uom", "unit"), ("unit of measure",))

    out = []
    for r in rows[(head + 1) if head is not None else 0:]:
        cols = tag_cols or range(len(r))
        tags = [t for j in cols if j < len(r) for t in find_tags(r[j])]
        for t in tags[:1] if tag_cols else tags:
            item = r[item_col] if item_col is not None and item_col < len(r) else ""
            qty = r[qty_col] if qty_col is not None and qty_col < len(r) else ""
            unit = r[unit_col] if unit_col is not None and unit_col < len(r) else ""
            out.append({"tag": t, "item": item, "qty": f"{qty} {unit}".strip()})
    return out


def _read_csv(data, delim):
    """A CSV as a grid of text. Ragged rows are fine: Metrc's exports can open
    with a few title lines that have fewer columns than the table below."""
    import csv
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    grid = list(csv.reader(text.splitlines(), delimiter=delim))
    width = max((len(r) for r in grid), default=0)
    return pd.DataFrame([r + [""] * (width - len(r)) for r in grid], dtype=str)


def read_manifest(data, filename):
    """(rows, error). Rows are {"tag", "item", "qty"} in manifest order, one per tag.

    `data` is the uploaded file's bytes; .xlsx and .csv are read, and any text
    that has tags in it works too (paste)."""
    name = (filename or "").lower()
    try:
        if name.endswith((".xlsx", ".xlsm")):
            sheets = pd.read_excel(BytesIO(data), sheet_name=None, header=None, dtype=str)
            frames = list(sheets.values())
        elif name.endswith((".csv", ".txt", ".tsv")):
            frames = [_read_csv(data, "	" if name.endswith(".tsv") else ",")]
        else:
            return [], "Upload the manifest as an Excel (.xlsx) or CSV file."
    except Exception as e:
        return [], f"Couldn't open that file: {e}"
    rows, seen = [], set()
    for df in frames:
        for r in _from_sheet(df):
            if r["tag"] not in seen:
                seen.add(r["tag"])
                rows.append(r)
    if not rows:
        return [], ("No package tags found in that file. A Metrc tag is 24 letters and "
                    "numbers, like 1A4060300003B6D000000123.")
    return rows, None


def read_pasted(text):
    tags = find_tags(text)
    if not tags:
        return [], "No package tags found in what was pasted."
    return [{"tag": t, "item": "", "qty": ""} for t in tags], None


def clean_scan(raw):
    """What a scanner typed, with quotes and spaces removed, in capitals."""
    return re.sub(r"[^0-9A-Za-z]", "", str(raw or "")).upper()


def split_scans(raw):
    """One entry as a list of scans. Two or more whole tags run together
    (48, 72... characters) are cut into 24s; anything else stays as typed."""
    s = clean_scan(raw)
    if len(s) > 24 and len(s) % 24 == 0:
        return [s[i:i + 24] for i in range(0, len(s), 24)]
    return [raw]


def check(raw, manifest_tags, scanned):
    """Judge one scan. Returns (status, tag, note).

    status: "ok"      on the manifest, first time
            "dupe"    already scanned
            "extra"   not on the manifest
            "unclear" a few characters that fit more than one tag, or none, or too short
    A scan that is a tag's last few characters (a tag that wouldn't scan,
    typed by hand) counts when it fits exactly one manifest tag.
    """
    found = find_tags(raw)
    s = clean_scan(raw)
    if not s:
        return "empty", "", ""
    tag = found[0] if found else s
    if tag in manifest_tags:
        return ("dupe" if tag in scanned else "ok"), tag, ""
    if len(tag) == 24:
        return "extra", tag, "This tag is not on the manifest."
    if len(s) >= MIN_PARTIAL:
        hits = [t for t in manifest_tags if t.endswith(s)]
        if len(hits) == 1:
            return ("dupe" if hits[0] in scanned else "ok"), hits[0], ""
        if len(hits) > 1:
            return "unclear", s, f"{len(hits)} tags end in {s}. Type more of it."
        return "extra", s, "Nothing on the manifest ends that way."
    return "unclear", s, f"Type at least {MIN_PARTIAL} characters from the end, or scan the whole tag."


def results_xlsx(rows, scanned, extras):
    """The finished check as a spreadsheet: one line per manifest tag, then extras."""
    out = []
    for r in rows:
        out.append({"Package ID": r["tag"], "Item": r["item"], "Quantity": r["qty"],
                    "Result": "Received" if r["tag"] in scanned else "NOT SCANNED",
                    "Scanned at": scanned.get(r["tag"], "")})
    for t, when in extras.items():
        out.append({"Package ID": t, "Item": "", "Quantity": "",
                    "Result": "NOT ON MANIFEST", "Scanned at": when})
    buf = BytesIO()
    pd.DataFrame(out).to_excel(buf, index=False, sheet_name="Transfer check")
    return buf.getvalue()


# ── the page ────────────────────────────────────────────────────────────────
def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_CSS = """
<style>
.ts-banner{border-radius:14px;padding:18px 22px;margin:6px 0 14px;font-family:'Inter',sans-serif}
.ts-banner b{display:block;font-size:26px;font-weight:800;letter-spacing:-.3px}
.ts-banner span{font-size:14px;opacity:.9;word-break:break-all}
.ts-ok{background:rgba(34,197,94,.18);border:2px solid #22C55E;color:#BBF7D0}
.ts-dupe{background:rgba(234,179,8,.16);border:2px solid #EAB308;color:#FEF08A}
.ts-bad{background:rgba(239,68,68,.16);border:2px solid #EF4444;color:#FECACA}
.ts-idle{background:rgba(148,163,184,.10);border:2px dashed rgba(148,163,184,.4);color:#CBD5E1}
.ts-row{display:flex;gap:12px;align-items:center;padding:9px 14px;border-radius:9px;margin-bottom:5px;
    font-family:'JetBrains Mono',monospace;font-size:13px;border:1px solid rgba(148,163,184,.25)}
.ts-row i{font-style:normal;font-family:'Inter',sans-serif;font-size:13px;opacity:.85;margin-left:auto;text-align:right}
.ts-row.got{background:rgba(34,197,94,.20);border-color:#22C55E}
.ts-row.extra{background:rgba(239,68,68,.16);border-color:#EF4444}
</style>
"""

_BANNERS = {
    "ok": ("ts-ok", "✅ On the manifest"),
    "dupe": ("ts-dupe", "⚠️ Already scanned"),
    "extra": ("ts-bad", "❌ NOT on the manifest"),
    "unclear": ("ts-bad", "❓ Couldn't match that"),
}


def render():
    import time
    import streamlit as st
    import streamlit.components.v1 as components

    ss = st.session_state
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div class="sec-head"><div class="sec-head-text">📦 Transfer Check</div>'
                '<div class="sec-head-line"></div></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="instr-card"><div class="instr-title">📋 How it Works</div>
    <div class="instr-steps">
      <div class="instr-step"><span class="instr-icon">1</span><span>Download the transfer's <strong>manifest from Metrc</strong> (Excel or CSV) and drop it below — no editing needed</span></div>
      <div class="instr-step"><span class="instr-icon fire">2</span><span>Scan each <strong>blue tag</strong>. It turns <strong>green</strong> on the list when it matches</span></div>
      <div class="instr-step"><span class="instr-icon">3</span><span>Anything <strong>not scanned</strong> or <strong>not on the manifest</strong> shows at the top. Download the result when you're done</span></div>
    </div></div>""", unsafe_allow_html=True)

    up = st.file_uploader("Metrc manifest", type=["xlsx", "csv"], key="ts_file",
                          label_visibility="collapsed")
    with st.expander("No spreadsheet? Paste the package tags instead"):
        pasted = st.text_area("Package tags", key="ts_paste", height=110,
                              placeholder="One tag per line, or copied straight from the manifest",
                              label_visibility="collapsed")

    # A new manifest starts a new check; the same one keeps its scans.
    if up is not None:
        data = up.getvalue()
        sig = ("file", up.name, len(data))
        if ss.get("ts_sig") != sig:
            rows, err = read_manifest(data, up.name)
            ss.update(ts_sig=sig, ts_rows=rows, ts_err=err, ts_scanned={}, ts_extras={},
                      ts_last=None, ts_n=0, ts_name=up.name)
    elif pasted.strip():
        sig = ("paste", pasted)
        if ss.get("ts_sig") != sig:
            rows, err = read_pasted(pasted)
            ss.update(ts_sig=sig, ts_rows=rows, ts_err=err, ts_scanned={}, ts_extras={},
                      ts_last=None, ts_n=0, ts_name="pasted tags")
    else:
        ss.pop("ts_sig", None)
        return
    if ss.get("ts_err"):
        st.error(ss["ts_err"])
        return

    rows, scanned, extras = ss["ts_rows"], ss["ts_scanned"], ss["ts_extras"]
    manifest = {r["tag"] for r in rows}

    def on_scan():
        # A quick second scan can land before the box has cleared, joining two
        # tags into one entry; whole tags are cut apart again.
        for raw in split_scans(ss.get("ts_input", "")):
            status, tag, note = check(raw, manifest, scanned)
            if status == "empty":
                continue
            now = time.strftime("%I:%M:%S %p").lstrip("0")
            if status == "ok":
                scanned[tag] = now
            elif status == "extra" and len(tag) == 24:
                extras.setdefault(tag, now)
            ss["ts_last"] = (status, tag, note)
            ss["ts_n"] = ss.get("ts_n", 0) + 1
        ss["ts_input"] = ""

    with st.form("ts_form", clear_on_submit=False, border=False):
        c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
        c1.text_input("Scan blue tag", key="ts_input", placeholder="Click here, then scan",
                      help="A scanner types the tag and presses Enter. You can also type the "
                           f"last {MIN_PARTIAL}+ characters of a tag that won't scan.")
        c2.form_submit_button("Check", on_click=on_scan, width="stretch")
    # Put the cursor back in the box after every scan, so the next one lands there.
    # The box may not be on the page yet when this runs, so it keeps looking for ~2 s.
    components.html(
        "<script>let n=0;const t=setInterval(()=>{try{const i=window.parent.document"
        ".querySelector('input[aria-label=\"Scan blue tag\"]');"
        "if(i){i.focus();clearInterval(t);}}catch(e){clearInterval(t);}"
        "if(++n>20)clearInterval(t);},100);</script>"
        f"<!-- {ss.get('ts_n', 0)} -->", height=0)

    last = ss.get("ts_last")
    if last:
        status, tag, note = last
        cls, title = _BANNERS[status]
        item = next((r["item"] for r in rows if r["tag"] == tag and r["item"]), "")
        sub = " · ".join(x for x in (item, note) if x)
        st.markdown(f'<div class="ts-banner {cls}"><b>{title}</b><span>{_esc(tag)}'
                    f'{" — " + _esc(sub) if sub else ""}</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ts-banner ts-idle"><b>Ready — scan the first tag</b>'
                    f'<span>{len(rows)} packages on {_esc(ss.get("ts_name", "the manifest"))}</span></div>',
                    unsafe_allow_html=True)

    left = [r for r in rows if r["tag"] not in scanned]
    st.markdown(f"**{len(scanned)} of {len(rows)} scanned**"
                + (f" · {len(extras)} not on the manifest" if extras else ""))
    st.progress(len(scanned) / len(rows))
    if not left and not extras:
        st.success("✅ Every package on the manifest is accounted for.")
    elif not left:
        st.warning("Every package on the manifest is scanned, but some tags that were scanned are not on it.")

    body = []
    for t, when in extras.items():
        body.append(f'<div class="ts-row extra">{_esc(t)}<i>❌ Not on the manifest · {when}</i></div>')
    for r in left + [r for r in rows if r["tag"] in scanned]:
        got = r["tag"] in scanned
        label = " · ".join(x for x in (r["item"], r["qty"]) if x)
        right = f"✅ {scanned[r['tag']]}" if got else _esc(label)
        sub = f'<i>{right}</i>' if got or label else ""
        body.append(f'<div class="ts-row{" got" if got else ""}">{_esc(r["tag"])}{sub}</div>')
    st.markdown("".join(body), unsafe_allow_html=True)

    st.download_button("⬇️  Download the result (Excel)", key="ts_dl",
                       data=results_xlsx(rows, scanned, extras),
                       file_name="transfer-check.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if st.button("Start over with a new manifest", key="ts_reset"):
        for k in ("ts_sig", "ts_rows", "ts_err", "ts_scanned", "ts_extras", "ts_last", "ts_n",
                  "ts_name", "ts_input", "ts_file", "ts_paste"):
            ss.pop(k, None)
        st.rerun()
