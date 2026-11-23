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
import datetime
import json
import re
from io import BytesIO
from zoneinfo import ZoneInfo

import pandas as pd

import scan_store
import transfer_names

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
    man_col = _pick(heads, ("manifest number", "manifest #", "manifest id", "manifest"))

    out = []
    for r in rows[(head + 1) if head is not None else 0:]:
        cols = tag_cols or range(len(r))
        tags = [t for j in cols if j < len(r) for t in find_tags(r[j])]
        for t in tags[:1] if tag_cols else tags:
            item = r[item_col] if item_col is not None and item_col < len(r) else ""
            qty = r[qty_col] if qty_col is not None and qty_col < len(r) else ""
            unit = r[unit_col] if unit_col is not None and unit_col < len(r) else ""
            man = r[man_col] if man_col is not None and man_col < len(r) else ""
            out.append({"tag": t, "item": item, "qty": f"{qty} {unit}".strip(), "manifest": man})
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


def _pdf_rows(data):
    """Packages from a Metrc transport manifest PDF, in manifest order.

    Each package's tag sits just above its "Lab Test:" line, so the tag is read
    from there; the "Source Package(s)" tags further down the same block are
    other packages and are never taken. The PDF's text comes out in pieces (a
    tag can be split over several lines, and a page's header can land between
    the pieces), so the text just before "Lab Test:" is joined with its spaces
    removed and the tag is read off its end."""
    from pypdf import PdfReader
    text = "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(data)).pages)
    text = text.replace("\xa0", " ")
    head = re.search(r"Originating\s+Entity\s*\n(.+?)\n", text)
    sender = head.group(1).strip() if head else ""
    num = re.search(r"Manifest\s*No\.\s*(\d{6,})", text)
    manifest = num.group(1) if num else ""
    rows = []
    for m in re.finditer(r"Lab Test:", text):
        before = "".join(text[max(0, m.start() - 120):m.start()].split())
        t = re.search(r"([0-9][A-Z][0-9A-Z]{22})$", before)
        if not t:
            continue
        after = text[m.end():m.end() + 600]
        it = re.search(r"Contains Retail IDs:[^\n]*\n(.*?)\n\(([^\n]*)\)\nShp: ?\n?([\d.,]+)\n? ?(\w+)",
                       after, re.S)
        item = qty = ""
        if it:
            item = " ".join(it.group(1).split())
            # The PDF splits text where the font changes: ". 7 G" -> ".7G", "Pre- Roll" -> "Pre-Roll".
            item = re.sub(r"(?<![\w])\.\s+(\d)", r".\1", item)
            item = re.sub(r"(\d)\s+(g|mg|oz|ml)\b", r"\1\2", item, flags=re.I)
            item = re.sub(r"(\d) x (\d)", r"\1x\2", item)
            item = re.sub(r"(?<=\w)- (?=\w)", "-", item)
            qty = f"{it.group(3)} {it.group(4)}"
        rows.append({"tag": t.group(1), "item": item, "qty": qty,
                     "manifest": manifest, "sender": sender})
    return rows


def read_manifest(data, filename):
    """(rows, error). Rows are {"tag", "item", "qty"} in manifest order, one per tag.

    `data` is the uploaded file's bytes: the manifest PDF, or a Metrc .xlsx or
    .csv download."""
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            found_rows = _pdf_rows(data)
        elif name.endswith((".xlsx", ".xlsm")):
            sheets = pd.read_excel(BytesIO(data), sheet_name=None, header=None, dtype=str)
            found_rows = [r for df in sheets.values() for r in _from_sheet(df)]
        elif name.endswith((".csv", ".txt", ".tsv")):
            df = _read_csv(data, "\t" if name.endswith(".tsv") else ",")
            found_rows = _from_sheet(df)
        else:
            return [], "Upload the manifest as a PDF, an Excel (.xlsx) or a CSV file."
    except Exception as e:
        return [], f"Couldn't open that file: {e}"
    rows, seen = [], set()
    for r in found_rows:
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
    return [{"tag": t, "item": "", "qty": "", "manifest": ""} for t in tags], None


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


LOG_LABEL = {"ok": "On the manifest", "dupe": "Scanned again", "extra": "NOT on the manifest",
             "unclear": "Couldn't match"}


def results_xlsx(rows, scanned, extras, log=()):
    """The finished check as a spreadsheet: one line per manifest tag, then extras;
    and a second sheet with every scan in the order it happened."""
    out = []
    for r in rows:
        out.append({"Package ID": r["tag"], "Item": r["item"], "Quantity": r["qty"],
                    "Result": "Received" if r["tag"] in scanned else "NOT SCANNED",
                    "Scanned at": scanned.get(r["tag"], "")})
    for t, when in extras.items():
        out.append({"Package ID": t, "Item": "", "Quantity": "",
                    "Result": "NOT ON MANIFEST", "Scanned at": when})
    buf = BytesIO()
    with pd.ExcelWriter(buf) as xw:
        pd.DataFrame(out).to_excel(xw, index=False, sheet_name="Transfer check")
        if log:
            pd.DataFrame([{"#": e["n"], "Time": e["time"], "Scanned": e["tag"],
                           "Result": LOG_LABEL.get(e["status"], e["status"]),
                           "Item": e["item"], "Note": e["note"]} for e in log]
                         ).to_excel(xw, index=False, sheet_name="Scan log")
    return buf.getvalue()


# ── the page ────────────────────────────────────────────────────────────────
def manifest_counts(rows):
    """{manifest number: packages}, in file order; empty when the file names none."""
    out = {}
    for r in rows:
        if r.get("manifest"):
            out[r["manifest"]] = out.get(r["manifest"], 0) + 1
    return out


def _restart(ss):
    ss.update(ts_scanned={}, ts_extras={}, ts_last=None, ts_n=0, ts_log=[])


def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_deps = {}
STORE_TZ = ZoneInfo("America/Detroit")


def configure(**kw):
    """context (-> studio.context()): where the store and the database come from."""
    _deps.update(kw)


def _ctx():
    """(db, store) for saving scans; (None, '') when the app hasn't configured us."""
    try:
        c = _deps["context"]()
        return c["db"], c["store"]
    except Exception:                                        # noqa: BLE001
        return None, ""


def now_text():
    """The time of a scan as the store sees it, whatever clock the server keeps (Streamlit
    Cloud's is UTC)."""
    return datetime.datetime.now(STORE_TZ).strftime("%I:%M:%S %p").lstrip("0")


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
.ts-row.dupe{background:rgba(234,179,8,.16);border-color:#EAB308}
</style>
"""

# Runs in the page. A scanner types into whatever has focus, so after a click on
# the list, a button or empty space the next scan would go nowhere. While the scan
# box is on screen: a key pressed anywhere that isn't a text box first moves the
# cursor into the box (so that key still lands there), and every half second the
# cursor is put back if it has drifted onto a button or the page. A text box the
# person clicked into, such as the paste box, is left alone, and nothing happens
# while another tab is showing, because the scan box is hidden then.
GUARD_JS = """
(function(){
  if (window.__tsGuard) { try { window.__tsGuard(); } catch (e) {} }
  const SEL = 'input[aria-label="Scan blue tag"]';
  const box = () => { const i = document.querySelector(SEL); return i && i.offsetParent !== null ? i : null; };
  const editing = el => el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
  const grab = () => { const i = box(); if (i && !editing(document.activeElement)) i.focus(); };
  const onKey = e => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key.length !== 1 && e.key !== 'Enter') return;
    if (editing(e.target)) return;
    grab();
  };
  document.addEventListener('keydown', onKey, true);
  const timer = setInterval(grab, 400);
  grab();
  window.__tsGuard = () => { document.removeEventListener('keydown', onKey, true); clearInterval(timer); };
})();
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
      <div class="instr-step"><span class="instr-icon">1</span><span>Drop in the transfer's <strong>manifest</strong> below: the PDF that comes with the delivery, or the Excel / CSV download from Metrc. No editing needed</span></div>
      <div class="instr-step"><span class="instr-icon fire">2</span><span>Scan each <strong>blue tag</strong>. It turns <strong>green</strong> on the list when it matches</span></div>
      <div class="instr-step"><span class="instr-icon">3</span><span>Anything <strong>not scanned</strong> or <strong>not on the manifest</strong> shows at the top. Download the result when you're done</span></div>
    </div></div>""", unsafe_allow_html=True)

    up = st.file_uploader("Metrc manifest", type=["pdf", "xlsx", "csv"], key="ts_file",
                          label_visibility="collapsed")
    with st.expander("No spreadsheet? Paste the package tags instead"):
        pasted = st.text_area("Package tags", key="ts_paste", height=110,
                              placeholder="One tag per line, or copied straight from the manifest",
                              label_visibility="collapsed")

    # A new file starts a new check; the same one keeps its scans.
    if up is not None:
        data = up.getvalue()
        sig = ("file", up.name, len(data))
        if ss.get("ts_sig") != sig:
            rows, err = read_manifest(data, up.name)
            ss.update(ts_sig=sig, ts_all=rows, ts_err=err, ts_name=up.name, ts_pick=None)
            _restart(ss)
    elif pasted.strip():
        sig = ("paste", pasted)
        if ss.get("ts_sig") != sig:
            rows, err = read_pasted(pasted)
            ss.update(ts_sig=sig, ts_all=rows, ts_err=err, ts_name="pasted tags", ts_pick=None)
            _restart(ss)
    else:
        ss.pop("ts_sig", None)
        return
    if ss.get("ts_err"):
        st.error(ss["ts_err"])
        return

    # Metrc's "Packages" downloads can hold many transfers: pick the one on the truck.
    counts = manifest_counts(ss["ts_all"])
    pick = None
    if len(counts) > 1:
        pick = st.selectbox(
            f"This file has {len(counts)} transfers. Which one is on the truck?",
            list(counts), index=None, placeholder="Choose a manifest number",
            format_func=lambda m: f"{m}  ·  {counts[m]} packages", key="ts_manifest")
        if pick is None:
            return
    if ss.get("ts_pick") != pick:
        ss["ts_pick"] = pick
        _restart(ss)
    ss["ts_rows"] = [r for r in ss["ts_all"] if pick is None or r["manifest"] == pick]

    # The same manifest at the same store is the same check: bring back its scans.
    db, store = _ctx()
    skey = scan_store.key(store, [r["tag"] for r in ss["ts_rows"]])
    if ss.get("ts_key") != skey:
        ss["ts_key"] = skey
        saved, err = scan_store.load(db, skey)
        ss["ts_save_err"] = err
        log = (saved or {}).get("log") or []
        if saved and (saved.get("scanned") or saved.get("extras") or log):
            ss.update(ts_scanned=saved.get("scanned") or {}, ts_extras=saved.get("extras") or {},
                      ts_log=log, ts_n=saved.get("n") or len(log),
                      ts_last=(log[-1]["status"], log[-1]["tag"], log[-1]["note"]) if log else None)
            ss["ts_resumed"] = (ss["ts_n"], saved.get("updated_at"))
        else:
            _restart(ss)
            ss.pop("ts_resumed", None)
        ss["ts_saved_n"] = ss.get("ts_n", 0)

    tab_scan, tab_names = st.tabs(["📦  Scan tags", "🏷️  Dutchie names"])
    with tab_scan:
        _scan_tab(ss, ss["ts_rows"])
    with tab_names:
        transfer_names.render(ss["ts_rows"], ss["ts_sig"])


def _scan_tab(ss, rows):
    import time
    import streamlit as st
    import streamlit.components.v1 as components

    scanned, extras = ss["ts_scanned"], ss["ts_extras"]
    manifest = {r["tag"] for r in rows}
    db, store = _ctx()

    resumed = ss.get("ts_resumed")
    if resumed and ss.get("ts_n") == resumed[0]:
        when = ""
        try:
            when = datetime.datetime.fromisoformat(str(resumed[1]).replace("Z", "+00:00"))                 .astimezone(STORE_TZ).strftime(" (saved %a %I:%M %p)").replace(" 0", " ")
        except Exception:                                    # noqa: BLE001
            pass
        st.info(f"Picked up where this transfer left off{when}: {len(scanned)} of {len(rows)} scanned. "
                "Use Start over below to clear it.")

    def on_scan():
        # A quick second scan can land before the box has cleared, joining two
        # tags into one entry; whole tags are cut apart again.
        for raw in split_scans(ss.get("ts_input", "")):
            status, tag, note = check(raw, manifest, scanned)
            if status == "empty":
                continue
            now = now_text()
            if status == "ok":
                scanned[tag] = now
            elif status == "extra" and len(tag) == 24:
                extras.setdefault(tag, now)
            ss["ts_last"] = (status, tag, note)
            ss["ts_n"] = ss.get("ts_n", 0) + 1
            ss.setdefault("ts_log", []).append(
                {"n": ss["ts_n"], "time": now, "status": status, "tag": tag, "note": note,
                 "item": next((r["item"] for r in rows if r["tag"] == tag), "")})
        ss["ts_input"] = ""

    with st.form("ts_form", clear_on_submit=False, border=False):
        c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
        c1.text_input("Scan blue tag", key="ts_input", placeholder="Click here, then scan",
                      help="A scanner types the tag and presses Enter. You can also type the "
                           f"last {MIN_PARTIAL}+ characters of a tag that won't scan.")
        c2.form_submit_button("Check", on_click=on_scan, width="stretch")
    # Keep scans landing in the box. The guard is put into the page itself (not the
    # little frame this call makes) so it outlives the frame, which is replaced on
    # every rerun; each new copy takes the old one's place.
    components.html(
        "<script>try{const d=window.parent.document;const o=d.getElementById('ts-guard');"
        "if(o)o.remove();const s=d.createElement('script');s.id='ts-guard';"
        f"s.textContent={json.dumps(GUARD_JS).replace('</', '<' + chr(92) + '/')};d.head.appendChild(s);"
        "}catch(e){}</script>"
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

    log = ss.get("ts_log", [])
    if log:
        again = sum(1 for e in log if e["status"] == "dupe")
        bad = sum(1 for e in log if e["status"] in ("extra", "unclear"))
        st.markdown(f"**Scan log** · {len(log)} scans"
                    + (f" · {again} scanned again" if again else "")
                    + (f" · {bad} not matched" if bad else ""))
        icon = {"ok": "✅", "dupe": "⚠️", "extra": "❌", "unclear": "❓"}
        css = {"ok": " got", "dupe": " dupe", "extra": " extra", "unclear": " extra"}
        with st.container(height=260):
            st.markdown("".join(
                f'<div class="ts-row{css.get(e["status"], "")}">{e["time"]}'
                f'&nbsp;{icon.get(e["status"], "")}&nbsp;{_esc(e["tag"])}'
                f'<i>{_esc(" · ".join(x for x in (e["item"], LOG_LABEL.get(e["status"], ""), e["note"]) if x))}</i></div>'
                for e in reversed(log)), unsafe_allow_html=True)
    st.markdown("**Packages**")

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

    # Save after the page is drawn, so the next scan isn't kept waiting on the database.
    if ss.get("ts_n", 0) != ss.get("ts_saved_n"):
        err = scan_store.save(db, ss.get("ts_key", ""), store, ss.get("ts_name", ""), len(rows),
                              scanned, extras, ss.get("ts_log", []), ss.get("ts_n", 0))
        ss["ts_save_err"] = err
        if err is None:
            ss["ts_saved_n"] = ss.get("ts_n", 0)
    if ss.get("ts_save_err"):
        st.caption("⚠️ Scans aren't being saved right now, so a refresh would lose them. "
                   "Download the result every so often as a backup.")
    elif ss.get("ts_n"):
        st.caption("Saved as you go. If the page reloads, drop the same manifest in again to carry on.")
    st.download_button("⬇️  Download the result (Excel)", key="ts_dl",
                       data=results_xlsx(rows, scanned, extras, log),
                       file_name="transfer-check.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if st.button("Start over with a new manifest", key="ts_reset"):
        scan_store.save(db, ss.get("ts_key", ""), store, ss.get("ts_name", ""), len(rows), {}, {}, [], 0)
        for k in ("ts_key", "ts_resumed", "ts_save_err", "ts_saved_n", "ts_sig", "ts_all", "ts_pick", "ts_manifest", "ts_rows", "ts_err", "ts_scanned", "ts_extras", "ts_last", "ts_n", "ts_log",
                  "ts_name", "ts_input", "ts_file", "ts_paste"):
            ss.pop(k, None)
        st.rerun()
