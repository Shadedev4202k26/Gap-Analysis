"""Which stores use which tools: a small log, and the Settings → Usage view.

Two kinds of line go into Supabase, each with the store, the tool (the page's
title) and the time, and nothing about the person or device:

  opened  the first time a visit opens a page — not every click on it
  used    a job finished: any download (tag PDFs, Aging stock PDF, tracker
          files) or a strain search

`visit` is a random id made when someone opens ZiggyBot, so one person
clicking around counts as one visit, not twenty.

`store_chosen` is false when the device never picked its store: the app then
falls back to the first store in the list, and counting that as Allegan would
make Allegan look busier than it is. A store is chosen when it is picked in
the sidebar, or comes from a bookmarked link (?store=Wayne).

Like the support requests, the app's key can add lines and read them, never
change or delete one, and the database stamps the time. Table: README →
"Usage".
"""
import datetime as dt
import uuid

import streamlit as st

TABLE = "ziggy_usage"
NOT_CHOSEN = "Store not picked"
SKIP = {"Settings"}                 # Chad's own page, not a store tool

_deps = {}


def configure(**kw):
    """init_db, context (-> {'store', 'store_chosen'}), page_title (-> str)."""
    _deps.update(kw)


def _visit():
    ss = st.session_state
    if "zb_visit" not in ss:
        ss["zb_visit"] = uuid.uuid4().hex[:12]
    return ss["zb_visit"]


def log(action, tool=None, detail=""):
    """Add one line. Never lets a logging problem reach the page."""
    tool = tool or (_deps["page_title"]() if _deps.get("page_title") else "")
    if not tool or tool in SKIP:
        return
    try:
        db = _deps["init_db"]()
        if db is None:
            return
        ctx = _deps["context"]() or {}
        db.table(TABLE).insert({
            "visit": _visit(), "store": (ctx.get("store") or "")[:60],
            "store_chosen": bool(ctx.get("store_chosen")), "tool": tool[:60],
            "action": action, "detail": (detail or "")[:120]}).execute()
    except Exception:                                        # noqa: BLE001
        pass


def opened(tool):
    """Once per visit per page — and once more after the store is picked, so
    the page someone was on when they picked it (usually Home) counts for that
    store and not only for "Store not picked"."""
    ctx = (_deps["context"]() if _deps.get("context") else None) or {}
    mark = (tool, ctx.get("store") if ctx.get("store_chosen") else None)
    seen = st.session_state.setdefault("zb_usage_seen", set())
    if mark in seen:
        return
    seen.add(mark)
    log("opened", tool)


def track_downloads():
    """Count every download button as a finished job, without touching each of
    the dozen call sites: st.download_button gets an on_click that logs the
    file, unless the call already has its own."""
    if getattr(st.download_button, "_zb_tracked", False):
        return
    original = st.download_button

    def download_button(*args, **kw):
        if "on_click" not in kw:
            name = kw.get("file_name") or (args[2] if len(args) > 2 else "")
            # The page is read now: the click's callback runs before the next
            # run has worked out which page it is on.
            tool = _deps["page_title"]() if _deps.get("page_title") else ""
            kw["on_click"] = log
            kw["args"] = ("used", tool, f"Downloaded {name}" if name else "Downloaded")
        return original(*args, **kw)

    download_button._zb_tracked = True
    st.download_button = download_button


# ── Settings → Usage ────────────────────────────────────────────────────────
PERIODS = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}
MEASURES = {"Jobs done": "used", "Visits": "opened"}


def _rows(db, since):
    out, start = [], 0
    while True:          # Supabase hands back 1,000 rows at a time
        page = (db.table(TABLE).select("at,visit,store,store_chosen,tool,action")
                .gte("at", since.isoformat()).order("at")
                .range(start, start + 999).execute().data or [])
        out += page
        if len(page) < 1000:
            return out
        start += 1000


def settings_view(tz_name, stores, tools):
    """Heat map of stores × tools, a bar chart per store, and last used."""
    from zoneinfo import ZoneInfo
    import altair as alt
    import pandas as pd

    st.markdown('<div class="cat-hdr">📊 Usage by store</div>', unsafe_allow_html=True)
    db = _deps["init_db"]()
    if db is None:
        st.warning("No Supabase connection — the usage log lives there.")
        return
    c1, c2 = st.columns(2)
    period = c1.segmented_control("Period", list(PERIODS), default="Last 30 days",
                                  key="zb_usage_period") or "Last 30 days"
    measure = c2.segmented_control("Count", list(MEASURES), default="Jobs done",
                                   key="zb_usage_measure") or "Jobs done"
    st.caption("**Jobs done** = tags or reports downloaded, and strain searches. "
               "**Visits** = times someone opened the tool (once per visit).")

    tz = ZoneInfo(tz_name)
    since = dt.datetime.now(tz) - dt.timedelta(days=PERIODS[period])
    try:
        rows = _rows(db, since)
    except Exception as e:                                   # noqa: BLE001
        st.error("The usage table isn't set up in Supabase yet — run the SQL in "
                 f"README → **Usage**. (`{e}`)")
        return
    if not rows:
        st.info(f"Nothing logged in the {period.lower()} yet. Lines appear as soon as "
                "stores open ZiggyBot.")
        return

    df = pd.DataFrame(rows)
    df["at"] = pd.to_datetime(df["at"], utc=True, format="ISO8601").dt.tz_convert(tz)
    # A visit's lines from before its store was picked count for the store it
    # picked; only visits that never picked one stay "Store not picked".
    picked = df[df["store_chosen"]].groupby("visit")["store"].last()
    df["store"] = (df["store"].where(df["store_chosen"], df["visit"].map(picked))
                   .fillna(NOT_CHOSEN))
    act = df[df["action"] == MEASURES[measure]]

    store_order = list(stores) + ([NOT_CHOSEN] if (df["store"] == NOT_CHOSEN).any() else [])
    store_order += sorted(set(df["store"]) - set(store_order))
    tool_order = [t for t in tools if t not in SKIP]
    tool_order += sorted(set(df["tool"]) - set(tool_order))

    by = act.groupby(["store", "tool"])        # a visit counts once per tool
    counts = (by["visit"].nunique() if measure == "Visits" else by.size()).rename("n").reset_index()
    grid = pd.MultiIndex.from_product([store_order, tool_order], names=["store", "tool"])
    counts = counts.set_index(["store", "tool"]).reindex(grid, fill_value=0).reset_index()

    if not counts["n"].any():           # an empty grid draws a legend of 0.000000
        st.info(f"No {measure.lower()} in the {period.lower()} yet."
                + (" Switch to **Visits** to see who has opened the tools." if measure == "Jobs done" else ""))
        _unpicked_note(df)
        return

    # ── heat map ──
    st.markdown(f"**{measure} by store and tool** — darker means used more; "
                "blank squares are tools that store hasn't used.")
    base = alt.Chart(counts).encode(
        x=alt.X("tool:N", sort=tool_order, title=None,
                axis=alt.Axis(orient="top", labelAngle=-30, labelLimit=160,
                              labelOverlap=False, labelFontSize=12)),
        y=alt.Y("store:N", sort=store_order, title=None))
    heat = base.mark_rect(stroke="#0b1020", strokeWidth=2).encode(
        color=alt.condition("datum.n > 0",
                            alt.Color("n:Q", title=measure, legend=alt.Legend(format="d"),
                                      scale=alt.Scale(scheme="purples")),
                            alt.value("rgba(255,255,255,0.04)")),
        tooltip=[alt.Tooltip("store:N", title="Store"), alt.Tooltip("tool:N", title="Tool"),
                 alt.Tooltip("n:Q", title=measure)])
    top = max(int(counts["n"].max()), 1)
    labels = base.mark_text(fontSize=13, fontWeight="bold").encode(
        text=alt.condition("datum.n > 0", "n:Q", alt.value("")),
        color=alt.condition(f"datum.n > {top / 2}", alt.value("white"), alt.value("#1e1b4b")))
    st.altair_chart((heat + labels).properties(height=34 * len(store_order) + 40),
                    use_container_width=True)

    # ── bar chart: one bar per store, its total written at the end ──
    st.markdown(f"**{measure} per store** — the longest bars are the busiest stores.")
    totals = counts.groupby("store", as_index=False)["n"].sum()
    if not totals["n"].any():
        st.caption(f"No {measure.lower()} in the {period.lower()}.")
    else:
        bar = alt.Chart(totals).encode(
            y=alt.Y("store:N", sort="-x", title=None, axis=alt.Axis(labelFontSize=12)),
            x=alt.X("n:Q", title=None, axis=None,           # room for the biggest number
                    scale=alt.Scale(domain=[0, int(totals["n"].max() * 1.12) + 1])),
            tooltip=[alt.Tooltip("store:N", title="Store"), alt.Tooltip("n:Q", title=measure)])
        chart = (bar.mark_bar(color="#8b5cf6", cornerRadiusEnd=4, height=20)
                 + bar.mark_text(align="left", dx=6, fontSize=13, fontWeight="bold",
                                 color="#e5e7eb").encode(text="n:Q"))
        st.altair_chart(chart.properties(height=30 * len(totals) + 20),
                        use_container_width=True)

    # ── last used: who to follow up with ──
    st.markdown("**Last used** — each store's most recent job in each tool.")
    jobs = df[df["action"] == "used"]
    last = (jobs.groupby(["store", "tool"])["at"].max().dt.strftime("%b %d")
            .unstack("tool").reindex(index=store_order, columns=tool_order))
    last = last.dropna(axis=1, how="all").fillna("—").rename_axis(index="Store", columns=None)
    if last.empty:
        st.caption("No jobs done in this period.")
    else:
        st.dataframe(last, use_container_width=True)

    _unpicked_note(df)


def _unpicked_note(df):
    n_unpicked = df.loc[df["store"] == NOT_CHOSEN, "visit"].nunique()
    if n_unpicked:
        st.caption(f"⚠️ {n_unpicked} visit(s) came from a device that never picked its "
                   "store. Send that store its own link (Settings → Store links) so its "
                   "tablet opens on the right store.")


def store_links(stores, base_url):
    """Each store's own link, to bookmark on its tablets."""
    st.markdown('<div class="cat-hdr">🔗 Store links</div>', unsafe_allow_html=True)
    st.markdown("Bookmark each store's link on its tablets and computers. ZiggyBot then "
                "opens on the right store, and usage counts for that store.")
    for s in stores:
        st.code(f"{base_url}/?store={s.replace(' ', '+')}", language=None)
