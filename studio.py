"""The Home dashboard, the week & store context, and the Shelf tags flow.

Built to the navigation mockup (the "ZiggyBot UI redesign" canvas): one place to
print every shelf tag, in three steps — format and source, pick tags beside a
live sheet preview, then review the real pages and print.

Two things make it feel less like a script re-running top to bottom:

- The week and store are chosen once, in the bar at the top of every page,
  rather than in an expander inside each tag tab. They live in session state
  and everything reads them through context().
- The picker runs inside an st.fragment, so ticking a tag re-runs the picker
  alone — not the sidebar, the context bar or the rest of the page — and the
  preview beside it is HTML drawn from the same rows, not a PDF build. A real
  sheet takes two to four seconds to build; the preview has to keep up with a
  click. The real pages are built once, in step 3.

app.py hands its own helpers over with configure(), because this module cannot
import app.py (it is the running script).
"""
import datetime as dt
import html
import json
import os
import subprocess
import tempfile

import pandas as pd
import streamlit as st

import combine_tags
import deal_store
import deals as deals_mod
import preroll_tags
import sale_badges

_deps = {}


def configure(**kw):
    """init_db, build_rows, fix_outdoor, pages={name: st.Page}."""
    _deps.update(kw)


def _page(name):
    return _deps.get("pages", {}).get(name)


esc = html.escape

# ── formats ─────────────────────────────────────────────────────────────────
FORMATS = {
    "hook": {"label": "Hook tag", "sub": "24 per sheet · 2.5″ × 1.25″", "cols": 3,
             "style": "hook",
             "templates": {"sativa": "Sativa_Hook.pdf", "hybrid": "Hybrid_Hook.pdf",
                           "indica": "Indica_Hook.pdf"}},
    "pr35": {"label": "Preroll 3.5″", "sub": "10 per sheet", "cols": 2, "style": "pr",
             "templates": {"sativa": "Sativa_Prerolls.pdf", "hybrid": "Hybrid_Prerolls.pdf",
                           "indica": "Indica_Prerolls.pdf"}},
    "pr4": {"label": "Preroll 4″", "sub": "10 per sheet", "cols": 2, "style": "pr4",
            "templates": {"sativa": "Sativa_Prerolls_4in.pdf", "hybrid": "Hybrid_Prerolls_4in.pdf",
                          "indica": "Indica_Prerolls_4in.pdf"}},
}
TYPES = ["sativa", "hybrid", "indica"]
TYPE_ORDER = TYPES


@st.cache_data(show_spinner=False)
def _per_page(path):
    return preroll_tags.slots_per_page(path)


def per_page(fmt):
    return _per_page(FORMATS[fmt]["templates"]["hybrid"])


# ── the week & store context ────────────────────────────────────────────────
def _db():
    try:
        return _deps["init_db"]()
    except Exception:                                       # noqa: BLE001
        return None


@st.cache_data(ttl=120, show_spinner=False)
def _stored_weeks(_db, bust):
    return deal_store.weeks(_db)


def _sheet_for(db, week):
    """A stored week's Sheet, read once per session."""
    cache = st.session_state.setdefault("zb_sheets", {})
    key = week.isoformat()
    if key not in cache:
        sheet = deal_store.get(db, week)
        cache[key] = sheet.to_dict() if sheet else None
    d = cache[key]
    return deals_mod.Sheet.from_dict(d) if d else None


def context():
    """What every page prints against. Computed once per run.

    {"db", "why", "weeks": [{"week", "name"}], "week", "sheet", "stores",
     "store", "deals", "prev", "prev_week"}
    """
    ss = st.session_state
    cached = ss.get("_zb_ctx_run")
    if cached and cached[0] == ss.get("_zb_run_id"):
        return cached[1]

    db, why, stored = _db(), None, []
    if db is None:
        why = "no Supabase connection, so a sheet uploaded here lasts this session only"
    else:
        try:
            stored = _stored_weeks(db, ss.get("zb_weeks_bust", 0))
        except deal_store.StoreError as e:
            why, db = f"Supabase refused the request — {e}", None

    # Sheets uploaded this session but not stored — the only kind when Supabase
    # is unreachable. Kept like the store keeps them: the newest KEEP weeks.
    local = ss.get("zb_local_sheets", {})
    weeks = [{"week": w["week"], "name": w["name"]} for w in stored]
    for iso, d in local.items():
        lw = dt.date.fromisoformat(iso)
        if all(w["week"] != lw for w in weeks):
            weeks.append({"week": lw, "name": d.get("name", "")})
    weeks.sort(key=lambda w: w["week"], reverse=True)

    week = ss.get("zb_week")
    if week not in [w["week"] for w in weeks]:
        # The week that covers today, not the newest: a sheet loaded early for
        # next week would otherwise take over every tag printed this week.
        week = next((w["week"] for w in weeks if deal_store.is_current(w["week"])),
                    weeks[0]["week"] if weeks else None)
        ss["zb_week"] = week

    sheet = None
    if week is not None:
        if week.isoformat() in local:
            sheet = deals_mod.Sheet.from_dict(local[week.isoformat()])
        elif db is not None:
            try:
                sheet = _sheet_for(db, week)
            except deal_store.StoreError as e:
                why = f"could not read {deal_store.week_label(week)} back — {e}"

    stores = list(sheet.stores) if sheet else []
    store = ss.get("zb_store")
    if stores and store not in stores:
        store = stores[0]
        ss["zb_store"] = store
    current = sheet.deals(store) if sheet else []

    prev, prev_week = None, None
    others = [w["week"] for w in weeks if w["week"] != week]
    if others and sheet:
        prev_week = others[0]
        try:
            if prev_week.isoformat() in local:
                other = deals_mod.Sheet.from_dict(local[prev_week.isoformat()])
            else:
                other = _sheet_for(db, prev_week) if db is not None else None
            prev = other.deals(store) if other else None
        except deal_store.StoreError:
            prev = None

    ctx = {"db": db, "why": why, "weeks": weeks, "week": week, "sheet": sheet,
           "stores": stores, "store": store, "deals": current, "prev": prev,
           "prev_week": prev_week}
    ss["_zb_ctx_run"] = (ss.get("_zb_run_id"), ctx)
    return ctx


def new_run():
    """Mark the start of a script run so context() recomputes once per run."""
    st.session_state["_zb_run_id"] = st.session_state.get("_zb_run_id", 0) + 1


def _week_status(week):
    if week is None:
        return '<span class="zb-ctxwarn">No deals loaded</span>'
    if deal_store.is_current(week):
        return '<span class="zb-ctxok">● Covers today</span>'
    return '<span class="zb-ctxwarn">▲ Not this week</span>'


def _pick_week(label_to_week):
    st.session_state["zb_week"] = label_to_week[st.session_state["zb_week_radio"]]


def _week_panel(ctx):
    st.markdown('<div class="zb-panel-h">Week</div>', unsafe_allow_html=True)
    if ctx["weeks"]:
        labels = {}
        for w in ctx["weeks"]:
            tag = "  · covers today" if deal_store.is_current(w["week"]) else ""
            labels[f"{deal_store.week_label(w['week'])}{tag}"] = w["week"]
        names = list(labels)
        # zb_week is the one record of the chosen week; the radio is only a view
        # of it, re-pointed every run. Left to keep its own value it drifts: a
        # keyed widget holds its old pick when its options change underneath it.
        st.session_state["zb_week_radio"] = next(
            (n for n in names if labels[n] == ctx["week"]), names[0])
        st.radio("Week", names, key="zb_week_radio", label_visibility="collapsed",
                 on_change=_pick_week, args=(labels,))
        slots = f"{min(len(ctx['weeks']), deal_store.KEEP)} of {deal_store.KEEP} week slots used"
        extra = ("" if len(ctx["weeks"]) >= 2 else
                 " — a second week unlocks “only what changed”.")
        st.caption(slots + extra)
    else:
        st.caption("No week loaded yet. Drop this week's deals sheet below.")

    st.markdown('<div class="zb-panel-h">Add a week</div>', unsafe_allow_html=True)
    up = st.file_uploader("Weekly deals sheet", type=["csv", "xlsx", "xls"],
                          key="zb_dealfile", label_visibility="collapsed")
    if up is not None:
        try:
            sheet = deals_mod.load_sheet(up.getvalue(), up.name)
        except Exception as e:                              # noqa: BLE001
            st.error(f"Could not read that sheet: {e}")
            return
        if not sheet.week:
            st.error(f"`{up.name}` has no date in its name. Rename it like "
                     "`9-28-26 Weekly Deals.csv`.")
            return
        label = deal_store.week_label(sheet.week)
        if ctx["db"] is None:
            if st.button(f"Use {label} for this session", type="primary", key="zb_dealuse"):
                local = st.session_state.setdefault("zb_local_sheets", {})
                local[sheet.week.isoformat()] = sheet.to_dict()
                for old in sorted(local, reverse=True)[deal_store.KEEP:]:
                    local.pop(old)
                st.session_state["zb_week"] = sheet.week
                st.rerun()
        elif st.button(f"Save {label} for everyone", type="primary", key="zb_dealsave"):
            try:
                deal_store.save(ctx["db"], sheet)
            except deal_store.StoreError as e:
                st.error(f"Could not save: {e}")
                return
            st.session_state["zb_weeks_bust"] = st.session_state.get("zb_weeks_bust", 0) + 1
            st.session_state.get("zb_sheets", {}).pop(sheet.week.isoformat(), None)
            st.session_state["zb_week"] = sheet.week
            st.rerun()
    if ctx["why"]:
        st.caption(f"⚠️ Weeks are not shared: {ctx['why']}.")
    if _page("settings"):
        st.page_link(_page("settings"), label="Manage stored weeks", icon=":material/tune:")


def _pick_store():
    v = st.session_state.get("zb_store_pills")
    if v:
        st.session_state["zb_store"] = v


@st.cache_data(show_spinner=False)
def _avatar():
    import base64
    try:
        with open("ziggy-avatar.png", "rb") as fh:
            b = base64.b64encode(fh.read()).decode()
    except OSError:
        return ""
    return f'<img class="zb-av" src="data:image/png;base64,{b}" alt="">'


def context_bar(mark_html):
    """The bar above every page: week, store, and the wordmark."""
    ctx = context()
    week_txt = deal_store.week_label(ctx["week"]) if ctx["week"] else "Load a week"
    with st.container(key="zbctx", horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown('<span class="zb-ctxlab">WEEK</span>', unsafe_allow_html=True)
        with st.popover(week_txt, icon=":material/calendar_month:"):
            _week_panel(ctx)
        st.markdown(_week_status(ctx["week"]), unsafe_allow_html=True)
        st.markdown('<span class="zb-ctxsep"></span>', unsafe_allow_html=True)
        st.markdown('<span class="zb-ctxlab">STORE</span>', unsafe_allow_html=True)
        with st.popover(ctx["store"] or "—", icon=":material/storefront:",
                        disabled=not ctx["stores"]):
            st.markdown('<div class="zb-panel-h">Store</div>', unsafe_allow_html=True)
            st.session_state["zb_store_pills"] = ctx["store"]
            st.pills("Store", ctx["stores"], key="zb_store_pills",
                     selection_mode="single", label_visibility="collapsed",
                     on_change=_pick_store)
            if ctx["deals"]:
                st.caption(f"{ctx['store']} runs {len(ctx['deals'])} deals this week.")
        st.markdown('<span class="zb-grow"></span>', unsafe_allow_html=True)
        st.markdown(f'<span class="zb-ctxmark">{mark_html}{_avatar()}</span>',
                    unsafe_allow_html=True)
    return ctx


# ── home ────────────────────────────────────────────────────────────────────
def _greeting():
    tz = None
    try:
        from zoneinfo import ZoneInfo
        if st.context.timezone:
            tz = ZoneInfo(st.context.timezone)
    except Exception:                                       # noqa: BLE001
        tz = None
    h = dt.datetime.now(tz).hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"


def _inventory_stats():
    """Numbers from the inventory export loaded in Shelf tags, if any."""
    df = st.session_state.get("zb_inv")
    if df is None:
        return None
    out = {"rows": len(df), "name": st.session_state.get("zb_inv_name", "")}
    # Counted the way the Aging stock page counts, so the two never disagree:
    # per product, the oldest of its packages, dated by packaging date where
    # there is one and inventory date otherwise.
    def dates(name):
        if name not in df.columns:
            return None
        return pd.to_datetime(df[name].astype(str).str.strip('="').str.strip(),
                              errors="coerce", format="mixed")
    pkg, inv = dates("Packaging date"), dates("Inventory date")
    ref = pkg.fillna(inv) if pkg is not None and inv is not None else (pkg if pkg is not None else inv)
    if ref is not None and "Product" in df.columns:
        age = (pd.Timestamp(dt.date.today()) - ref).dt.days
        per = age.groupby(df["Product"].astype(str).str.strip('="').str.strip()).max().dropna()
        out["products"] = int(len(per))
        out["over45"] = int((per >= 45).sum())
        out["over90"] = int((per >= 90).sum())
    cat = next((c for c in df.columns if c.strip().lower() == "category"), None)
    if cat:
        out["outdoor"] = int(df[cat].astype(str).str.contains("outdoor", case=False).sum())
        out["cats"] = int(df[cat].nunique())
    return out


def _card(key, page, html_body):
    """A dashboard card whose whole surface opens `page`."""
    with st.container(key=f"zbcard_{key}"):
        st.markdown(html_body, unsafe_allow_html=True)
        if page is not None:
            st.page_link(page, label="Open", icon=":material/arrow_forward:")


def render_home():
    ctx = context()
    inv = _inventory_stats()
    wk = deal_store.week_label(ctx["week"]) if ctx["week"] else None
    where = (f'for <b>{esc(ctx["store"])}</b>, week of <b>{esc(wk)}</b>'
             if ctx["store"] and wk else "once this week's deals sheet is loaded")
    st.markdown(f'<div class="zb-home-h"><h1>{_greeting()}</h1>'
                f'<p>Everything below is {where}.</p></div>', unsafe_allow_html=True)

    left, right = st.columns([7, 5], gap="medium")
    with left:
        with st.container(key="zbhero"):
            st.markdown(
                '<div class="zb-hero"><div class="zb-hero-k">PRINT</div>'
                '<h2>Shelf tags</h2><p>Hook, 3.5″ and 4″ preroll — one flow, three steps. '
                'Pick from today\'s inventory with the sheet drawing itself beside you.</p>'
                '<div class="zb-hero-steps"><span>1 · Source &amp; format</span>'
                '<span>2 · Pick tags</span><span>3 · Review &amp; print</span></div></div>',
                unsafe_allow_html=True)
            if st.button("Start", type="primary", icon=":material/arrow_forward:",
                         key="zb_home_start"):
                st.session_state["zb_step"] = 1
                st.switch_page(_page("studio"))
    with right:
        if ctx["sheet"]:
            botw = sum(1 for d in ctx["deals"] if getattr(d, "kind", "") == "botw")
            n_weeks = min(len(ctx["weeks"]), deal_store.KEEP)
            note = ("" if n_weeks >= 2 else
                    '<div class="zb-note">Only one week is stored, so “only what changed” '
                    'is unavailable. Load last week\'s sheet from the Week menu to compare.</div>')
            st.markdown(
                f'<div class="zb-stats"><div class="zb-stats-h">This week\'s deals'
                f'<span>{esc(ctx["sheet"].name or "")}</span></div>'
                f'<div class="zb-stat-grid">'
                f'<div><b>{len(ctx["deals"])}</b><i>deals for {esc(ctx["store"] or "")}</i></div>'
                f'<div><b>{botw}</b><i>brands of the week</i></div>'
                f'<div><b>{len(ctx["stores"])}</b><i>stores in this sheet</i></div>'
                f'<div><b>{n_weeks} / {deal_store.KEEP}</b><i>week slots used</i></div>'
                f'</div>{note}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="zb-stats"><div class="zb-stats-h">This week\'s deals</div>'
                '<div class="zb-empty">No deals sheet loaded. Open <b>Week</b> in the bar '
                'above and drop this week\'s export — tags print without sale bubbles '
                'until then.</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="zb-sec">Stock &amp; tools</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        if inv and "over45" in inv:
            body = (f'<b class="zb-big">{inv["over45"]:,}</b> products 45+ days old'
                    f'<br><span>{inv["over90"]:,} past 90 · of {inv["products"]:,} '
                    f'in {esc(inv["name"])}</span>')
        else:
            body = ('Load today\'s inventory in Shelf tags and the oldest stock '
                    'shows up here.')
        _card("aging", _page("aging"),
              f'<div class="zb-card"><div class="zb-card-h">Aging stock</div>'
              f'<div class="zb-card-b">{body}</div></div>')
    with c2:
        body = (f'<b class="zb-big">{inv["rows"]:,}</b> packages loaded'
                f'<br><span>{inv.get("cats", 0)} categories</span>'
                if inv else "Compare rooms and shelves against a minimum stock level.")
        _card("inv", _page("inventory"),
              f'<div class="zb-card"><div class="zb-card-h">Inventory balance</div>'
              f'<div class="zb-card-b">{body}</div></div>')
    with c3:
        _card("strain", _page("strain"),
              '<div class="zb-card"><div class="zb-card-h">Strain lookup</div>'
              '<div class="zb-card-b">Effects, terpenes and lineage for any strain, '
              'grounded in a web search.</div></div>')
    with c4:
        _card("tools", _page("tools"),
              '<div class="zb-card"><div class="zb-card-h">Store tools</div>'
              '<div class="zb-card-b">Curbside, breaks &amp; lunches, and the games.</div></div>')


# ── shelf tags: rows ────────────────────────────────────────────────────────
def _deal_kind(deal):
    if not deal:
        return None
    if deal.get("shelf"):
        return "shelf"
    if deal.get("bulk"):
        return "bulk"
    return "sale"


def _badge_lines(deal):
    if not deal:
        return []
    lines = deal.get("tiers") or ([deal["badge"]] if deal.get("badge") else [])
    return [sale_badges.normalize(t) for t in lines if t]


def _badge_text(deal):
    txt = " · ".join(_badge_lines(deal))
    if deal and deal.get("was") and deal.get("now"):
        txt = (txt + "  " if txt else "") + f"{deal['was']} → {deal['now']}"
    return txt


def _source_rows():
    """The undecorated rows for the chosen source."""
    ss = st.session_state
    src = ss.get("zb_src", "csv")
    if src == "csv":
        return ss.get("zb_rows") or []
    if src == "handoff":
        return ss.get("zb_handoff_rows") or []
    return []


def _decorated(fmt, ctx):
    """Source rows with this week's deals, standing bulk deals and shelves on.

    Worked out once per (source, format, week, store) and kept: matching every
    deal against a few thousand products is the slow part of the whole page.
    """
    ss = st.session_state
    bubbles = ss.get("zb_bubbles", True)
    base = _source_rows()
    sig = (ss.get("zb_src"), ss.get("zb_rows_sig"), len(base), fmt,
           str(ctx["week"]), ctx["store"], bubbles, len(ctx["deals"] or []),
           str(ctx["prev_week"]))
    hit = ss.get("zb_dec")
    if hit and hit[0] == sig:
        return hit[1]
    rows = [dict(r, rid=i) for i, r in enumerate(base)]
    for r in rows:                       # accessories have no THC: pandas says "nan"
        for f in ("brand", "strain", "thc", "price"):
            if str(r.get(f, "")).strip().lower() == "nan":
                r[f] = ""
    if fmt == "hook" and _deps.get("fix_outdoor"):
        _deps["fix_outdoor"](rows)
    if bubbles and ctx["deals"]:
        deals_mod.attach(rows, ctx["deals"])
    deals_mod.attach_bulk(rows)
    deals_mod.attach_shelf(rows)
    changed = set()
    if ctx["prev"] is not None and ctx["deals"]:
        changed = {r["rid"] for r in deals_mod.changed(rows, ctx["prev"], ctx["deals"])}
    for r in rows:
        r["_kind"] = _deal_kind(r.get("deal"))
        r["_changed"] = r["rid"] in changed
        r["_outdoor"] = "outdoor" in str(r.get("category", "")).lower()
    ss["zb_dec"] = (sig, rows)
    return rows


EDITABLE = {"Strain": "strain", "Brand line": "brand", "THC": "thc", "Price": "price",
            "Type": "type"}


def _chosen(rows):
    """Selected rows, edits applied, each repeated by its quantity, grid order."""
    ss = st.session_state
    sel, edits = ss.setdefault("zb_sel", {}), ss.setdefault("zb_edit", {})
    out = []
    for r in rows:
        q = sel.get(r["rid"], 0)
        if not q:
            continue
        rr = dict(r)
        rr.update(edits.get(r["rid"], {}))
        out.extend(dict(rr) for _ in range(q))
    return out


def _pages(chosen, fmt, mix):
    per = per_page(fmt)
    if mix:
        return [chosen[i:i + per] for i in range(0, len(chosen), per)]
    pages = []
    for t in TYPE_ORDER:
        g = [r for r in chosen if r.get("type", "hybrid") == t]
        pages += [g[i:i + per] for i in range(0, len(g), per)]
    return pages


# ── shelf tags: the preview ─────────────────────────────────────────────────
SHELF_CSS = {"stash": ("#6B33A3", "#fff", None), "blue": ("#2161C2", "#fff", None),
             "white": ("#fff", "#14161F", "#73737F"), "red": ("#D12924", "#fff", None),
             "outdoor": ("#17804A", "#fff", None)}


def _badge_html(deal):
    lines = _badge_lines(deal)
    if not lines:
        return ""
    kind = _deal_kind(deal)
    if kind == "shelf" and deal.get("shelf") in SHELF_CSS:
        fill, ink, ol = SHELF_CSS[deal["shelf"]]
    elif kind == "bulk":
        fill, ink, ol = "#4A2982", "#D9CCF5", None
    else:
        fill, ink, ol = "#D12924", "#fff", None
    cls = "zt-bd multi" if len(lines) > 1 else "zt-bd"
    border = f"box-shadow:inset 0 0 0 1px {ol};" if ol else ""
    return (f'<span class="{cls}" style="background:{fill};color:{ink};{border}">'
            + "".join(f"<span>{esc(x)}</span>" for x in lines) + "</span>")


def _tag_html(r, style):
    t = r.get("type", "hybrid")
    deal = r.get("deal") or {}
    if deal.get("was") and deal.get("now"):
        price = (f'<span class="zt-p md"><b>{esc(sale_badges.normalize(deal["now"]))}</b>'
                 f'<s>{esc(sale_badges.normalize(deal["was"]))}</s></span>')
    else:
        price = f'<span class="zt-p">{esc(str(r.get("price", "")))}</span>'
    return (f'<div class="zt {style} {t}"><div class="zt-in">'
            f'<div class="zt-b">{esc(str(r.get("brand", "")))}</div>'
            f'<div class="zt-ln"></div>'
            f'<div class="zt-s">{esc(str(r.get("strain", "")))}</div>'
            f'<div class="zt-f"><span class="zt-t">{esc(str(r.get("thc", "")))}</span>'
            f'{_badge_html(deal)}{price}</div></div></div>')


def sheet_html(page_rows, fmt):
    f = FORMATS[fmt]
    per = per_page(fmt)
    cells = [_tag_html(r, f["style"]) for r in page_rows]
    cells += ['<div class="zt empty"></div>'] * (per - len(page_rows))
    return (f'<div class="zb-sheet {f["style"]}" style="--cols:{f["cols"]};'
            f'--rows:{per // f["cols"]}">{"".join(cells)}</div>')


# ── shelf tags: building the real thing ─────────────────────────────────────
@st.cache_data(show_spinner=False, max_entries=6)
def _build_pdf(fmt, mix, rows_json):
    rows = json.loads(rows_json)
    templates = FORMATS[fmt]["templates"]
    with tempfile.TemporaryDirectory() as td:
        if mix:
            return combine_tags.build_combined(templates, rows, td)
        grouped = {}
        for r in rows:
            grouped.setdefault(r.get("type", "hybrid"), []).append(r)
        return preroll_tags.build_separate(templates, grouped, td)


@st.cache_data(show_spinner=False, max_entries=6)
def _thumbs(pdf, dpi=72):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "s.pdf")
        with open(p, "wb") as fh:
            fh.write(pdf)
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), p, os.path.join(td, "p")],
                       check=True, capture_output=True)
        return [open(os.path.join(td, n), "rb").read()
                for n in sorted(os.listdir(td)) if n.endswith(".png")]


def _clean(r):
    return {k: v for k, v in r.items() if not k.startswith("_") and k != "rid"}


# ── shelf tags: the page ────────────────────────────────────────────────────
STEPS = ["Source & format", "Pick tags", "Review & print"]


def _rail(step):
    parts = []
    for i, name in enumerate(STEPS, 1):
        state = "done" if i < step else "on" if i == step else ""
        mark = "✓" if i < step else str(i)
        parts.append(f'<div class="zb-step {state}"><span>{mark}</span>{esc(name)}</div>')
        if i < len(STEPS):
            parts.append(f'<div class="zb-step-bar {"done" if i < step else ""}"></div>')
    st.markdown(f'<div class="zb-rail">{"".join(parts)}</div>', unsafe_allow_html=True)


def _option(key, title, sub, selected, glyph, disabled=False):
    """A selectable card. The real button covers the card, so the whole card is
    the target and it is still a button to a keyboard or a screen reader."""
    cls = "zb-opt" + (" on" if selected else "") + (" off" if disabled else "")
    check = '<span class="zb-opt-ck">✓</span>' if selected else ""
    with st.container(key=f"zbopt_{key}"):
        st.markdown(f'<div class="{cls}">{check}<div class="zb-opt-g">{glyph}</div>'
                    f'<div class="zb-opt-t">{esc(title)}</div>'
                    f'<div class="zb-opt-s">{esc(sub)}</div></div>', unsafe_allow_html=True)
        return st.button(f"{title} — {sub}", key=f"zboptb_{key}", disabled=disabled,
                         use_container_width=True)


GLYPH = {
    "hook": '<i style="width:44px;height:26px"></i>',
    "pr35": '<i style="width:52px;height:26px"></i>',
    "pr4": '<i style="width:60px;height:26px"></i>',
    "split": '<i style="width:28px;height:26px;border-color:#F59E0B"></i>'
             '<i style="width:28px;height:26px;border-color:#A78BFA"></i>',
    "csv": '<svg viewBox="0 0 24 24"><path d="M14 2.8H6.8a1.8 1.8 0 0 0-1.8 1.8v14.8a1.8 1.8 0 0 0 1.8 1.8h10.4a1.8 1.8 0 0 0 1.8-1.8V7.6Z"/><path d="M14 2.8v4.8h5"/></svg>',
    "hand": '<svg viewBox="0 0 24 24"><path d="M11 4.8H5.6a1.8 1.8 0 0 0-1.8 1.8v11.8a1.8 1.8 0 0 0 1.8 1.8h11.8a1.8 1.8 0 0 0 1.8-1.8V13"/><path d="M17.6 3.4a1.9 1.9 0 0 1 2.7 2.7L12.6 13.8l-3.6 1 1-3.6Z"/></svg>',
    "handoff": '<svg viewBox="0 0 24 24"><path d="M4 12h13M12 6l6 6-6 6"/></svg>',
}


def _handoff_waiting():
    ss = st.session_state
    for target in ("hook", "preroll"):
        rows = ss.get(f"handoff_{target}")
        if rows:
            return rows, ss.get(f"handoff_{target}_from", "the other builder")
    return None, None


def _footer(back_label, on_back, summary, next_label, on_next, next_ok=True, key="s"):
    with st.container(key="zbfoot", horizontal=True, vertical_alignment="center"):
        if back_label and st.button(back_label, key=f"zbf_back_{key}",
                                    icon=":material/arrow_back:"):
            on_back()
        st.markdown(f'<span class="zb-grow"></span><span class="zb-foot-sum">{summary}</span>',
                    unsafe_allow_html=True)
        if next_label and st.button(next_label, key=f"zbf_next_{key}", type="primary",
                                    disabled=not next_ok, icon=":material/arrow_forward:",
                                    icon_position="right"):
            on_next()


def _go(step):
    st.session_state["zb_step"] = step
    st.rerun(scope="app")


def _load_csv(up):
    sig = f"{up.name}:{up.size}"
    ss = st.session_state
    if ss.get("zb_rows_sig") == sig:
        return
    df = pd.read_csv(up)
    df.columns = [str(c).strip('="').strip() for c in df.columns]
    if "Product" not in df.columns:
        st.error("That file has no `Product` column — is it the Dutchie inventory export?")
        return
    rows = _deps["build_rows"](df)
    ss.update(zb_rows=rows, zb_rows_sig=sig, zb_inv=df, zb_inv_name=up.name,
              zb_sel={}, zb_edit={}, zb_grid_v=ss.get("zb_grid_v", 0) + 1)


def _setting(where, key, default, label, help_, disabled=False):
    """A toggle whose value outlives the step it is drawn on.

    Streamlit drops a widget's state on the first run that does not draw it, so
    a toggle keyed straight to the setting would reset the moment step 2 opens.
    The widget gets its own key and copies into the setting on change.
    """
    ss = st.session_state
    ss.setdefault(key, default)

    def keep():
        ss[key] = ss[f"{key}_w"]
    where.toggle(label, value=ss[key], key=f"{key}_w", on_change=keep, help=help_,
                 disabled=disabled)


def _step1(ctx):
    ss = st.session_state
    fmt = ss.setdefault("zb_fmt", "hook")
    src = ss.setdefault("zb_src", "csv")

    st.markdown('<div class="zb-h2">What are you printing?</div>', unsafe_allow_html=True)
    cols = st.columns(4, gap="small")
    for c, key in zip(cols[:3], FORMATS):
        with c:
            if _option(key, FORMATS[key]["label"], FORMATS[key]["sub"], fmt == key, GLYPH[key]):
                ss["zb_fmt"] = key
                st.rerun()
    with cols[3]:
        _option("split", "Split tag", "2 strains · in Preroll tags for now", False,
                GLYPH["split"], disabled=True)

    st.markdown('<div class="zb-h2">Where do the products come from?</div>',
                unsafe_allow_html=True)
    waiting, frm = _handoff_waiting()
    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        if _option("csv", "Import inventory CSV", "Dutchie export", src == "csv", GLYPH["csv"]):
            ss["zb_src"] = "csv"
            st.rerun()
    with c2:
        if _option("hand", "Type them by hand", "One-off tags", src == "hand", GLYPH["hand"]):
            ss["zb_src"] = "hand"
            st.rerun()
    with c3:
        sub = f"{len(waiting)} tags from {frm}" if waiting else "Nothing waiting"
        if _option("handoff", "Handed over", sub, src == "handoff", GLYPH["handoff"],
                   disabled=not waiting):
            ss.update(zb_src="handoff", zb_handoff_rows=[dict(r) for r in waiting],
                      zb_sel={i: 1 for i in range(len(waiting))}, zb_edit={},
                      zb_grid_v=ss.get("zb_grid_v", 0) + 1)
            st.rerun()

    o1, o2, o3 = st.columns(3, gap="small")
    _setting(o1, "zb_mix", False, "Mix types on one page",
             "Put sativa, hybrid and indica on the same sheet instead of a page "
             "per type. Saves paper; every tag keeps its own colour.")
    _setting(o2, "zb_bubbles", True, "Sale bubbles from this week's deals",
             "Standing bulk deals and deli shelf badges print either way.",
             disabled=not ctx["deals"])
    if ctx["prev"] is not None:
        _setting(o3, "zb_changed_only", False,
                 f"Only what changed since {deal_store.week_label(ctx['prev_week'])}",
                 "Start the picker on the tags whose deal is new, different or "
                 "ended — the ones on the shelf that are now wrong.")

    ready = True
    if src == "csv":
        up = st.file_uploader("Inventory export", type=["csv"], key="zb_csv",
                              label_visibility="collapsed")
        if up is not None:
            _load_csv(up)
        rows = ss.get("zb_rows") or []
        if rows:
            n_out = sum(1 for r in rows if "outdoor" in str(r.get("category", "")).lower())
            st.markdown(
                f'<div class="zb-loaded">✓ <b>{len(rows):,}</b> products from '
                f'<code>{esc(ss.get("zb_inv_name", ""))}</code>'
                + (f' · {n_out} outdoor at the fixed price' if n_out and fmt == "hook" else "")
                + '</div>', unsafe_allow_html=True)
        ready = bool(rows)
    fmt_l = FORMATS[ss["zb_fmt"]]["label"]
    src_l = {"csv": "Import CSV", "hand": "Typed by hand", "handoff": "Handed over"}[src]

    def nxt():
        if ss.get("zb_changed_only") and ctx["prev"] is not None:
            ss["zb_filter"] = "Changed"
        _go(2)
    _footer("Home", lambda: st.switch_page(_page("home")), f"{fmt_l} · {src_l}",
            "Next — pick tags", nxt, next_ok=ready, key="1")


FILTERS = ["All", "On sale", "Changed", "Outdoor", "Selected"]


@st.fragment
def _step2(ctx):
    ss = st.session_state
    fmt, mix = ss["zb_fmt"], ss.get("zb_mix", False)
    if ss.get("zb_src") == "hand":
        return _step2_hand(ctx)
    rows = _decorated(fmt, ctx)
    sel, edits = ss.setdefault("zb_sel", {}), ss.setdefault("zb_edit", {})

    left, right = st.columns([13, 10], gap="large")
    with left:
        cats = pd.Series([r.get("category") or "—" for r in rows]).value_counts()
        s1, s2 = st.columns([1, 1], vertical_alignment="center")
        q = s1.text_input("Search", key="zb_q", placeholder="Search strain or brand…",
                          label_visibility="collapsed", icon=":material/search:")
        cat = s2.selectbox("Category", ["All categories"] + list(cats.index), key="zb_cat",
                           label_visibility="collapsed",
                           format_func=lambda c: c if c == "All categories"
                           else f"{c}  ({cats[c]:,})")
        ql = (q or "").strip().lower()
        # The rows the search and category leave. The filter counts are taken
        # from these, so a pill never promises tags the grid then cannot show.
        scope = [r for r in rows
                 if (cat == "All categories" or (r.get("category") or "—") == cat)
                 and (not ql or ql in f'{r.get("strain","")} {r.get("brand","")} '
                                      f'{r.get("product","")}'.lower())]
        test = {"All": lambda r: True,
                "On sale": lambda r: r["_kind"] == "sale",
                "Changed": lambda r: r["_changed"],
                "Outdoor": lambda r: r["_outdoor"],
                "Selected": lambda r: bool(sel.get(r["rid"]))}
        counts = {f: sum(1 for r in scope if t(r)) for f, t in test.items()}
        # Which pills exist is decided on every row, so they do not come and go
        # as the category changes; only their counts do.
        shown = [f for f in FILTERS if f in ("All", "On sale", "Selected")
                 or any(test[f](r) for r in rows)]
        if ss.get("zb_filter") not in shown:
            ss["zb_filter"] = "All"
        st.segmented_control("Filter", shown, key="zb_filter", label_visibility="collapsed",
                             format_func=lambda f: f"{f}  {counts[f]:,}")
        filt = ss.get("zb_filter") or "All"
        view_rows = [r for r in scope if test[filt](r)]
        _select_bar(view_rows, sel, filt, cat, ql, fmt)

        if not view_rows:
            _no_matches(filt, cat, (q or "").strip())
        else:
            def val(r, f):
                return edits.get(r["rid"], {}).get(f, r.get(f, ""))
            view = pd.DataFrame(
                {"Print": [bool(sel.get(r["rid"])) for r in view_rows],
                 "Qty": [sel.get(r["rid"], 1) or 1 for r in view_rows],
                 "Strain": [val(r, "strain") for r in view_rows],
                 "Brand line": [val(r, "brand") for r in view_rows],
                 "THC": [val(r, "thc") for r in view_rows],
                 "Price": [val(r, "price") for r in view_rows],
                 "Type": [val(r, "type") or "hybrid" for r in view_rows],
                 "Deal": [_badge_text(r.get("deal")) for r in view_rows]},
                index=[r["rid"] for r in view_rows])
            # Typed explicitly: pandas guesses float for an all-empty column, and
            # a checkbox column over floats is an error, not an empty grid.
            view = view.astype({"Print": bool, "Qty": int})
            gkey = f"zbgrid_{fmt}_{filt}_{hash((ql, cat))}_{ss.get('zb_grid_v', 0)}"
            out = st.data_editor(
                view, key=gkey, hide_index=True, use_container_width=True, height=470,
                disabled=["Deal"], num_rows="fixed",
                column_config={
                    "Print": st.column_config.CheckboxColumn("", width=36),
                    "Qty": st.column_config.NumberColumn("Qty", min_value=0, max_value=60,
                                                         step=1, width=52),
                    "Strain": st.column_config.TextColumn(width="medium"),
                    "Brand line": st.column_config.TextColumn(width="medium"),
                    "THC": st.column_config.TextColumn(width=64),
                    "Price": st.column_config.TextColumn(width=70),
                    "Type": st.column_config.SelectboxColumn(options=TYPES, width=86,
                                                             required=True),
                    "Deal": st.column_config.TextColumn(width="small"),
                })
            if len(out):
                diff = (out.astype(str) != view.astype(str)).any(axis=1)
                base = {r["rid"]: r for r in view_rows}
                membership = False
                for rid in out.index[diff]:
                    row, r = out.loc[rid], base[rid]
                    qty = int(row["Qty"] or 0)
                    if bool(row["Print"]) != bool(view.loc[rid, "Print"]):
                        want = bool(row["Print"])          # ticked or unticked
                    elif qty != int(view.loc[rid, "Qty"]):
                        want = qty > 0                     # a quantity picks it too
                    else:
                        want = rid in sel
                    if want:
                        membership |= rid not in sel
                        sel[rid] = max(1, qty)
                    elif rid in sel:
                        membership = True
                        sel.pop(rid)
                    e = {}
                    for col, f in EDITABLE.items():
                        if str(row[col]) != str(r.get(f, "")):
                            e[f] = row[col]
                    if e:
                        edits[rid] = e
                    else:
                        edits.pop(rid, None)
                if membership and filt == "Selected":
                    ss["zb_grid_v"] = ss.get("zb_grid_v", 0) + 1
                    st.rerun(scope="fragment")

        st.caption("Tick a tag to print it. Every cell but Deal can be edited — "
                   "changes print exactly as typed.")

    chosen = _chosen(rows)
    with right:
        _preview(chosen, fmt, mix)
    _step2_footer(chosen, fmt, mix, ctx)


def _preview(chosen, fmt, mix):
    ss = st.session_state
    pages = _pages(chosen, fmt, mix) or [[]]
    n = len(pages)
    pg = min(ss.get("zb_pg", 1), n)
    kinds = [r.get("_kind") for r in chosen]
    chips = "".join(
        f'<span class="zb-chip {k}"><i></i>{kinds.count(k)} {lab}</span>'
        for k, lab in (("sale", "on sale"), ("bulk", "bulk"), ("shelf", "shelf"))
        if kinds.count(k))
    st.markdown(f'<div class="zb-prev-h"><b>Sheet preview</b>'
                f'<span>page {pg} of {n}</span>{chips}</div>', unsafe_allow_html=True)
    st.markdown(sheet_html(pages[pg - 1], fmt), unsafe_allow_html=True)
    if n > 1:
        p = st.segmented_control("Page", list(range(1, n + 1)), default=pg,
                                 key=f"zb_pgsel_{n}", label_visibility="collapsed",
                                 format_func=lambda i: f"{i}")
        if p and p != pg:
            ss["zb_pg"] = p
            st.rerun(scope="fragment")


# A sheet takes about this long to build, per format (seconds, measured).
BUILD_S = {"hook": 2.5, "pr35": 0.6, "pr4": 0.9}


def _select_bar(view_rows, sel, filt, cat, ql, fmt):
    """Select all / clear, above the grid where they are always in reach."""
    ss = st.session_state
    n = len(view_rows)
    narrowed = filt != "All" or cat != "All categories" or ql
    todo = [r for r in view_rows if not sel.get(r["rid"])]
    with st.container(key="zbselbar", horizontal=True, vertical_alignment="center"):
        label = f"Select all {n:,}" + (" shown" if narrowed else "")
        if n and st.button(label if todo else f"All {n:,} selected", key="zb_selall",
                     icon=":material/done_all:", disabled=not todo):
            for r in todo:
                sel[r["rid"]] = 1
            ss["zb_grid_v"] = ss.get("zb_grid_v", 0) + 1
            st.rerun(scope="fragment")
        if st.button("Clear selection", key="zb_clear", icon=":material/close:",
                     disabled=not sel):
            sel.clear()
            ss["zb_grid_v"] = ss.get("zb_grid_v", 0) + 1
            st.rerun(scope="fragment")
    # Everything in one go is allowed — it is sometimes the job — but it should
    # not be a surprise: the whole 9/25 export is 166 hook sheets.
    total = sum(sel.values())
    sheets = -(-total // per_page(fmt)) if total else 0
    if sheets > 20:
        mins = max(1, round(sheets * BUILD_S.get(fmt, 2.5) / 60))
        st.caption(f"⚠️ {total:,} tags is about {sheets:,} sheets — building them in the "
                   f"last step takes roughly {mins} min.")


def _widen(**state):
    st.session_state.update(state)


def _no_matches(filt, cat, q):
    """Say why the grid is empty, and offer the way back out."""
    shelf = deals_mod.shelf_of({"category": cat}) if cat != "All categories" else None
    where = "" if cat == "All categories" else f" in <b>{esc(cat)}</b>"
    if shelf and filt in ("On sale", "Changed"):
        what = "is on sale" if filt == "On sale" else "has a changed deal"
        msg = (f"Nothing{where} {what}. Deli flower never takes a weekly deal — it "
               f"is priced by the shelf it sits on, so these tags carry the "
               f"<b>{esc(shelf[0])}</b> shelf badge instead.")
    else:
        bits = [f"<b>{esc(filt.lower())}</b>"] if filt != "All" else []
        if q:
            bits.append(f"matching <b>“{esc(q)}”</b>")
        msg = f"No products{where}" + (" " + " and ".join(bits) if bits else "") + "."
    st.markdown(f'<div class="zb-nomatch">{msg}</div>', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 2])
    if filt != "All":
        c1.button(f"Show all{' of ' + cat if cat != 'All categories' else ''}",
                  key="zb_nm_all", on_click=_widen, kwargs={"zb_filter": "All"})
    if cat != "All categories" or q:
        c2.button("Clear search & category", key="zb_nm_clear", on_click=_widen,
                  kwargs={"zb_cat": "All categories", "zb_q": ""})


def _step2_footer(chosen, fmt, mix, ctx):
    n = len(chosen)
    pages = len(_pages(chosen, fmt, mix))
    summary = (f"<b>{n}</b> tag{'s' if n != 1 else ''} selected · {pages} "
               f"sheet{'s' if pages != 1 else ''} · {esc(FORMATS[fmt]['label'].lower())}"
               + (f" · {esc(ctx['store'])}" if ctx["store"] else ""))
    _footer("Back", lambda: _go(1), summary, "Review & print", lambda: _go(3),
            next_ok=n > 0, key="2")


HAND_COLS = ["Qty", "Brand line", "Strain", "THC", "Price", "Type"]


def _step2_hand(ctx):
    ss = st.session_state
    fmt, mix = ss["zb_fmt"], ss.get("zb_mix", False)
    left, right = st.columns([13, 10], gap="large")
    with left:
        st.markdown('<div class="zb-h2">Type your tags</div>', unsafe_allow_html=True)
        seed = ss.setdefault("zb_hand_seed", pd.DataFrame(
            [{"Qty": 1, "Brand line": "", "Strain": "", "THC": "", "Price": "",
              "Type": "hybrid"} for _ in range(6)]))
        out = st.data_editor(
            seed, key="zb_hand", num_rows="dynamic", hide_index=True,
            use_container_width=True, height=470,
            column_config={
                "Qty": st.column_config.NumberColumn(min_value=0, max_value=60, step=1,
                                                     width=52),
                "Type": st.column_config.SelectboxColumn(options=TYPES, width=90),
            })
        st.caption("Text prints exactly as typed; blank lines stay blank. Brand names "
                   "still pick up this week's deals.")
    rows = []
    for _, r in out.iterrows():
        if not any(str(r[c] or "").strip() for c in ("Brand line", "Strain", "THC", "Price")):
            continue
        row = {"brand": str(r["Brand line"] or "").strip(),
               "strain": str(r["Strain"] or "").strip(),
               "thc": str(r["THC"] or "").strip(), "price": str(r["Price"] or "").strip(),
               "type": r["Type"] if r["Type"] in TYPES else "hybrid"}
        rows.extend(dict(row) for _ in range(int(r["Qty"] or 0)))
    if ss.get("zb_bubbles", True) and ctx["deals"]:
        deals_mod.attach(rows, ctx["deals"])
    for r in rows:
        r["_kind"] = _deal_kind(r.get("deal"))
    ss["zb_hand_rows"] = rows
    with right:
        _preview(rows, fmt, mix)
    _step2_footer(rows, fmt, mix, ctx)


def _step3(ctx):
    ss = st.session_state
    fmt, mix = ss["zb_fmt"], ss.get("zb_mix", False)
    if ss.get("zb_src") == "hand":
        chosen = ss.get("zb_hand_rows") or []
    else:
        chosen = _chosen(_decorated(fmt, ctx))
    if not chosen:
        st.info("Nothing selected yet.")
        _footer("Back", lambda: _go(2), "", None, None, key="3")
        return
    kinds = [r.get("_kind") for r in chosen]
    pages = _pages(chosen, fmt, mix)
    tiles = [(len(chosen), "tags"), (len(pages), "sheets"),
             (kinds.count("sale"), "on sale"), (kinds.count("bulk"), "bulk deal"),
             (kinds.count("shelf"), "shelf badge")]
    st.markdown('<div class="zb-tiles">' + "".join(
        f'<div><b>{n}</b><i>{esc(lab)}</i></div>' for n, lab in tiles) + '</div>',
        unsafe_allow_html=True)

    payload = json.dumps([_clean(r) for r in chosen], sort_keys=True, default=str)
    try:
        with st.spinner(f"Building {len(chosen)} {FORMATS[fmt]['label'].lower()}s…"):
            pdf = _build_pdf(fmt, mix, payload)
            thumbs = _thumbs(pdf)
    except FileNotFoundError as e:
        st.error(f"A tool the tag builder needs is missing: {e}. See packages.txt.")
        return
    except Exception as e:                                  # noqa: BLE001
        st.error(f"Could not build the sheet: {e}")
        return

    stamp = dt.date.today().isoformat()
    name = f"{FORMATS[fmt]['label'].replace('″', 'in').replace(' ', '')}_{stamp}.pdf"
    st.download_button("Download PDF to print", pdf, name, "application/pdf",
                       type="primary", icon=":material/print:", key="zb_dl")
    st.markdown('<div class="zb-sec">The real pages</div>', unsafe_allow_html=True)
    grid = st.columns(min(3, len(thumbs)) or 1, gap="medium")
    for i, png in enumerate(thumbs):
        with grid[i % len(grid)]:
            st.image(png, caption=f"Page {i + 1}", use_container_width=True)

    def restart():
        ss.update(zb_sel={}, zb_edit={}, zb_grid_v=ss.get("zb_grid_v", 0) + 1)
        _go(1)
    _footer("Back to picking", lambda: _go(2), f"{name}", "Start a new batch", restart, key="3")


def render_studio():
    ctx = context()
    step = st.session_state.setdefault("zb_step", 1)
    st.markdown('<div class="zb-titlebar"><h1>Shelf tags</h1></div>', unsafe_allow_html=True)
    _rail(step)
    if step == 1:
        _step1(ctx)
    elif step == 2:
        _step2(ctx)
    else:
        _step3(ctx)


# ── styling ─────────────────────────────────────────────────────────────────
# Selectors are data-testid values and st-key-<key> classes only, checked
# against Streamlit 1.63. Never the st-emotion-cache-* hashes.
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@700;800;900&display=swap');

/* context bar */
.st-key-zbctx{height:64px;background:var(--s2);border-bottom:1px solid var(--border);
  margin:0 -40px!important;width:calc(100% + 80px)!important;max-width:none!important;padding:0 28px!important;gap:10px!important;flex-wrap:nowrap!important}
.st-key-zbctx [data-testid="stElementContainer"]:has(.zb-grow){flex:1 1 auto!important}
.st-key-zbctx [data-testid="stMarkdownContainer"] p{margin:0!important}
.zb-ctxmark{display:flex;align-items:center;gap:14px}
.zb-ctxmark img.zb-mark{height:17px;display:block;opacity:.9}
.zb-ctxmark img.zb-av{width:36px;height:36px;border-radius:50%;object-fit:cover;border:1px solid var(--b-purple)}
/* Narrow screens: Streamlit collapses the sidebar and floats its reopen button
   top-left, over the start of this bar. */
@media (max-width: 768px){.block-container{padding:0 16px 140px!important}
  .st-key-zbctx{margin:0 -16px!important;width:calc(100% + 32px)!important;padding-left:64px!important;overflow-x:auto}
  .zb-ctxmark{display:none}}
.zb-panel-h{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1.6px;
  color:var(--dim);text-transform:uppercase;margin:4px 0 8px}
[data-testid="stPopoverBody"]{min-width:340px;background:var(--s1)!important;
  border:1px solid var(--b-purple)!important}

/* shared */
.zb-titlebar{padding:22px 0 0}
.zb-titlebar h1{font-family:'Syne',sans-serif!important;font-weight:800!important;
  font-size:26px!important;letter-spacing:-.5px;margin:0!important;padding:0!important;color:var(--text)}
.zb-h2{font-family:'Syne',sans-serif;font-weight:700;font-size:17px;color:var(--text);margin:18px 0 10px}
.zb-sec{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1.6px;
  color:var(--dim);text-transform:uppercase;margin:26px 0 10px}

/* step rail */
.zb-rail{display:flex;align-items:center;padding:16px 0 4px}
.zb-step{display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600;color:var(--dim)}
.zb-step span{width:27px;height:27px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:13px;font-weight:700;background:var(--s3);
  border:1px solid var(--b-purple);color:var(--dim)}
.zb-step.on{color:var(--text);font-weight:700}
.zb-step.on span{background:var(--purple);border-color:var(--purple);color:#fff;
  box-shadow:0 0 0 4px rgba(139,92,246,.18)}
.zb-step.done span{background:rgba(52,211,153,.14);border-color:rgba(52,211,153,.5);color:var(--green-l)}
.zb-step-bar{width:64px;height:2px;background:rgba(139,92,246,.2);margin:0 16px}
.zb-step-bar.done{background:rgba(52,211,153,.45)}

/* option cards: the button is stretched over the card and made invisible */
[class*="st-key-zbopt_"]{position:relative;gap:0!important}
[class*="st-key-zbopt_"] [data-testid="stElementContainer"]:has([data-testid="stButton"]){
  position:absolute!important;inset:0!important;margin:0!important;z-index:2;width:auto!important}
[class*="st-key-zbopt_"] [data-testid="stButton"],
[class*="st-key-zbopt_"] [data-testid="stButton"] > div,
[class*="st-key-zbopt_"] button{width:100%!important;height:100%!important}
[class*="st-key-zbopt_"] button{opacity:0!important;cursor:pointer}
[class*="st-key-zbopt_"] button:disabled{cursor:not-allowed}
.zb-opt{position:relative;box-sizing:border-box;min-height:118px;padding:16px 18px;border-radius:12px;
  background:var(--s2);border:1.5px solid rgba(139,92,246,.2);display:flex;flex-direction:column;
  gap:6px;transition:border-color .15s,background .15s,transform .15s}
[class*="st-key-zbopt_"]:hover .zb-opt:not(.off){border-color:rgba(139,92,246,.55);transform:translateY(-1px)}
[class*="st-key-zbopt_"]:has(button:focus-visible) .zb-opt{outline:2px solid var(--purple-l);outline-offset:2px}
.zb-opt.on{background:rgba(139,92,246,.14);border-color:var(--purple)}
.zb-opt.off{opacity:.45}
.zb-opt-g{display:flex;gap:3px;height:30px;align-items:center}
.zb-opt-g i{display:block;border-radius:4px;border:2px solid #5D6B9C;box-sizing:border-box}
.zb-opt.on .zb-opt-g i{border-color:var(--purple-l);background:rgba(167,139,250,.14)}
.zb-opt-g svg{width:22px;height:22px;fill:none;stroke:#8C9BC4;stroke-width:1.8;
  stroke-linecap:round;stroke-linejoin:round}
.zb-opt.on .zb-opt-g svg{stroke:var(--purple-l)}
.zb-opt-t{font-size:15px;font-weight:700;color:var(--text)}
.zb-opt-s{font-size:12px;color:var(--dim)}
.zb-opt.on .zb-opt-s{color:#C4B5FD}
.zb-opt-ck{position:absolute;top:14px;right:14px;width:20px;height:20px;border-radius:50%;
  background:var(--purple);color:#fff;font-size:12px;font-weight:800;display:flex;
  align-items:center;justify-content:center}

.zb-loaded{margin:6px 0 0;padding:12px 16px;border-radius:10px;background:rgba(52,211,153,.07);
  border:1px solid rgba(52,211,153,.24);font-size:13px;color:var(--text)}
.zb-loaded code{background:transparent;color:var(--green-l);font-size:12px}
[data-testid="stFileUploaderDropzone"]{border:1.5px dashed rgba(139,92,246,.42)!important;
  background:rgba(139,92,246,.05)!important;border-radius:13px!important;padding:26px!important}

/* pinned action bar */
.st-key-zbfoot{position:fixed!important;bottom:0;left:268px;right:0;height:76px;z-index:60;
  background:rgba(10,14,28,.96);backdrop-filter:blur(8px);border-top:1px solid rgba(139,92,246,.22);
  padding:0 40px!important;gap:14px!important;width:auto!important}
.st-key-zbfoot [data-testid="stElementContainer"]:has(.zb-grow){flex:1 1 auto!important}
.zb-foot-sum{font-size:13px;color:var(--dim);white-space:nowrap}
.zb-foot-sum b{color:var(--text)}
.st-key-zbfoot button{min-height:44px!important;padding:0 22px!important;white-space:nowrap}
.st-key-zbfoot [data-testid="stBaseButton-secondary"]{background:transparent!important;
  border:1px solid rgba(139,92,246,.35)!important;color:var(--dim)!important;box-shadow:none!important}
.st-key-zbfoot [data-testid="stBaseButton-secondary"]:hover{border-color:var(--purple-l)!important;color:var(--text)!important}
@media (max-width: 900px){.st-key-zbfoot{left:0;height:auto;padding:10px 16px!important;
  flex-wrap:wrap!important;row-gap:8px!important}
  .st-key-zbfoot [data-testid="stElementContainer"]:has(.zb-grow){order:-1;flex:1 1 100%!important}
  .zb-foot-sum{white-space:normal}}
.st-key-zbfoot button:disabled{opacity:.4!important;box-shadow:none!important;filter:saturate(.4)}

/* picker */
.st-key-zbselbar{gap:8px!important;margin:-2px 0 2px}
.st-key-zbselbar button{min-height:36px!important;padding:0 14px!important;font-size:12px!important;
  background:rgba(139,92,246,.10)!important;border:1px solid rgba(139,92,246,.4)!important;
  color:#C4B5FD!important;box-shadow:none!important}
.st-key-zbselbar button:hover:not(:disabled){background:rgba(139,92,246,.2)!important;color:var(--text)!important}
.st-key-zbselbar button:disabled{opacity:.38!important;background:transparent!important}
.zb-nomatch{box-sizing:border-box;min-height:120px;margin:4px 0 12px;padding:22px 24px;border-radius:12px;
  border:1.5px dashed rgba(139,92,246,.35);background:rgba(139,92,246,.05);font-size:14px;
  color:var(--dim);line-height:1.55}
.zb-nomatch b{color:var(--text)}
.zb-prev-h{display:flex;align-items:center;flex-wrap:wrap;gap:6px 14px;margin:2px 0 10px;font-size:13px;color:var(--dim)}
.zb-prev-h > *{white-space:nowrap}
.zb-prev-h b{font-family:'Syne',sans-serif;font-size:15px;color:var(--text)}
.zb-chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--dim);white-space:nowrap}
.zb-chip i{width:9px;height:9px;border-radius:3px;display:block}
.zb-chip.sale i{background:#D12924}.zb-chip.bulk i{background:#4A2982}.zb-chip.shelf i{background:#17804A}
[data-testid="stDataFrame"]{border-radius:10px;overflow:hidden;border:1px solid var(--border)}

/* the sheet — a scale drawing of the page, sized from the pane's width */
.zb-sheet{box-sizing:border-box;background:#fff;border-radius:6px;aspect-ratio:8.5/11;
  padding:4.2% 5.4%;display:grid;grid-template-columns:repeat(var(--cols),1fr);
  grid-template-rows:repeat(var(--rows),1fr);box-shadow:0 18px 50px rgba(0,0,0,.55),
  0 0 0 1px rgba(255,255,255,.06);max-height:640px;margin:0 auto}
.zt{container-type:size;box-sizing:border-box;border:.5px dashed #C9CCD6;position:relative;
  overflow:hidden;font-family:'Archivo',sans-serif;color:#101114}
.zt.empty{background:repeating-linear-gradient(135deg,#fff 0 6px,#F6F6F9 6px 12px)}
.zt-in{position:absolute;inset:6% 5%;display:flex;flex-direction:column;align-items:center;
  justify-content:space-between;text-align:center}
.zt-b{font-weight:800;font-size:8cqh;letter-spacing:.2px;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;max-width:100%;text-transform:uppercase}
.zt-ln{width:92%;height:3.4cqh;border-radius:2px;background:var(--st)}
.zt-s{font-weight:900;font-size:13cqh;line-height:1.05;text-transform:uppercase;max-width:100%;
  overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.zt-f{display:flex;align-items:center;justify-content:space-between;width:100%;gap:3%}
.zt-t,.zt-p{font-weight:900;font-size:11cqh;white-space:nowrap}
.zt-p.md{display:flex;flex-direction:column;align-items:flex-end;line-height:1}
.zt-p.md s{font-size:7cqh;color:#6B6B75;text-decoration-color:#D12924}
.zt-bd{font-family:Helvetica,Arial,sans-serif;font-weight:700;font-size:8.5cqh;padding:2.5cqh 5cqw;
  border-radius:3cqh;white-space:nowrap;line-height:1;display:flex;flex-direction:column;gap:1cqh}
.zt-bd.multi{font-size:7cqh}
.zt.sativa{--st:#E8913A}.zt.hybrid{--st:#4EC3B0}.zt.indica{--st:#6F63C4}
/* prerolls: a coloured frame, not a stripe */
.zt.pr .zt-in,.zt.pr4 .zt-in{inset:9% 6%;background:#fff;border-radius:3cqh;padding:4% 4%;box-sizing:border-box}
.zt.pr,.zt.pr4{background:var(--fr)}
.zt.pr .zt-ln,.zt.pr4 .zt-ln{display:none}
.zt.pr.sativa,.zt.pr4.sativa{--fr:linear-gradient(135deg,#F7C548,#E4572E)}
.zt.pr.hybrid,.zt.pr4.hybrid{--fr:linear-gradient(135deg,#63CF8E,#39AFC9)}
.zt.pr.indica,.zt.pr4.indica{--fr:linear-gradient(135deg,#9A6FE0,#5747B0)}
.zt.pr .zt-b,.zt.pr4 .zt-b{font-size:9cqh}
.zt.pr .zt-s,.zt.pr4 .zt-s{font-size:15cqh}

/* home */
.zb-home-h{padding:28px 0 6px}
.zb-home-h h1{font-family:'Syne',sans-serif!important;font-weight:800!important;font-size:34px!important;
  letter-spacing:-.8px;margin:0!important;padding:0!important;color:var(--text)}
.zb-home-h p{margin:6px 0 0;font-size:15px;color:var(--dim)}
.zb-home-h b{color:var(--text)}
.st-key-zbhero{position:relative;border-radius:16px;padding:26px 28px!important;
  background:radial-gradient(120% 140% at 0% 0%,rgba(139,92,246,.32),transparent 55%),
  radial-gradient(90% 120% at 100% 100%,rgba(34,211,238,.14),transparent 60%),var(--s2);
  border:1px solid rgba(139,92,246,.4);min-height:232px;gap:14px!important}
.zb-hero-k{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1.6px;color:#C4B5FD}
.zb-hero h2{font-family:'Syne',sans-serif!important;font-weight:800!important;font-size:30px!important;
  margin:6px 0 6px!important;padding:0!important;color:var(--text);letter-spacing:-.6px}
.zb-hero p{margin:0;max-width:520px;font-size:14px;color:var(--dim);line-height:1.5}
.zb-hero-steps{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
.zb-hero-steps span{font-size:12px;font-weight:600;color:#C4B5FD;padding:5px 10px;border-radius:999px;
  background:rgba(139,92,246,.14);border:1px solid rgba(139,92,246,.3)}
.st-key-zbhero button{min-height:44px;padding:0 26px!important}
.zb-stats{box-sizing:border-box;border-radius:16px;padding:22px 24px;background:var(--s2);
  border:1px solid var(--border);min-height:232px}
.zb-stats-h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;
  font-family:'Syne',sans-serif;font-weight:700;font-size:16px;color:var(--text)}
.zb-stats-h span{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--dim);
  font-weight:400;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:60%}
.zb-stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px 18px;margin-top:16px}
.zb-stat-grid b{display:block;font-family:'Syne',sans-serif;font-size:30px;font-weight:800;
  color:var(--text);line-height:1}
.zb-stat-grid i{font-style:normal;font-size:12px;color:var(--dim)}
.zb-note{margin-top:16px;font-size:12px;color:var(--dim);padding:10px 12px;border-radius:9px;
  background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.25)}
.zb-empty{margin-top:14px;font-size:13px;color:var(--dim);line-height:1.55}
[class*="st-key-zbcard_"]{position:relative;border-radius:14px;background:var(--s2);
  border:1px solid var(--border);padding:18px 20px!important;min-height:150px;gap:6px!important;
  transition:border-color .15s,transform .15s}
[class*="st-key-zbcard_"]:hover{border-color:rgba(139,92,246,.5);transform:translateY(-1px)}
[class*="st-key-zbcard_"] [data-testid="stPageLink"] a::after{content:"";position:absolute;inset:0}
/* Every element wrapper is position:relative, which would trap the stretched
   link inside its own wrapper; and Streamlit's markdown carries a -1rem bottom
   margin that slides the next element up over it. */
[class*="st-key-zbcard_"] [data-testid="stElementContainer"],
[class*="st-key-zbcard_"] [data-testid="stPageLink"],
[class*="st-key-zbcard_"] [data-testid="stPageLink"] > div{position:static!important}
[class*="st-key-zbcard_"] [data-testid="stMarkdownContainer"],
[class*="st-key-zbopt_"] [data-testid="stMarkdownContainer"],
.st-key-zbhero [data-testid="stMarkdownContainer"]{margin-bottom:0!important}
[class*="st-key-zbcard_"] [data-testid="stElementContainer"]:has([data-testid="stPageLink"]){margin-top:auto}
[class*="st-key-zbcard_"] [data-testid="stPageLink"] a{padding:0!important;min-height:0!important}
[class*="st-key-zbcard_"] [data-testid="stPageLink"] p{font-size:12px!important;color:var(--purple-l)!important}
[class*="st-key-zbcard_"] [data-testid="stPageLink"] [data-testid="stIconMaterial"]{font-size:15px!important;color:var(--purple-l)!important}
.zb-card-h{font-family:'Syne',sans-serif;font-weight:700;font-size:15px;color:var(--text);margin-bottom:6px}
.zb-card-b{font-size:13px;color:var(--dim);line-height:1.5}
.zb-card-b span{font-size:12px}
.zb-big{font-family:'Syne',sans-serif;font-size:26px;color:var(--text);margin-right:4px}

/* review */
.zb-tiles{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:14px 0 18px}
.zb-tiles div{padding:14px 16px;border-radius:12px;background:var(--s2);border:1px solid var(--border)}
.zb-tiles b{display:block;font-family:'Syne',sans-serif;font-size:26px;font-weight:800;color:var(--text);line-height:1.05}
.zb-tiles i{font-style:normal;font-size:12px;color:var(--dim)}
[data-testid="stImage"] img{border-radius:6px;box-shadow:0 12px 36px rgba(0,0,0,.5)}
</style>
"""


def page_home():
    with st.container(key="zbhome"):
        render_home()


def page_studio():
    with st.container(key="zbstudio"):
        render_studio()
