"""The app shell: sidebar navigation, the week/store context bar, styling.

Why the navigation is hand-built rather than st.navigation's own menu:
that menu renders each section as a COLLAPSIBLE group, it removes the links
from the DOM when collapsed, and the collapsed state survives a page reload.
A user who collapses a group cannot get those pages back, and hiding the
control to prevent it only makes the trap permanent. So the routing is
Streamlit's (`position="hidden"`) and the menu is ours, built from st.page_link.

The sidebar cannot be dismissed either — it is the only navigation. The expand
button stays styled and live all the same: Streamlit auto-collapses the sidebar
on a narrow screen, and without it a tablet would have no way back.

Every selector below is a `data-testid`, checked against Streamlit 1.63. The
`st-emotion-cache-*` classes are build hashes and must never be relied on.
"""
import streamlit as st

SIDEBAR_W = 268   # 248 clipped "Inventory balance" before Inter loaded

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

/* ── app chrome ─────────────────────────────────────────────────────────── */
/* Never display:none the header — it carries the button that reopens a
   collapsed sidebar. Zero it and hide only the Deploy menu inside it. */
header[data-testid="stHeader"]{{background:transparent!important;height:0!important;min-height:0!important}}
[data-testid="stDecoration"]{{display:none!important}}
[data-testid="stAppDeployButton"]{{display:none!important}}
[data-testid="stMainMenu"]{{display:none!important}}
[data-testid="stExpandSidebarButton"]{{position:fixed!important;top:12px!important;left:12px!important;
    z-index:200!important;background:var(--s3)!important;border:1px solid var(--b-purple)!important;
    border-radius:9px!important;width:40px!important;height:40px!important;
    display:flex!important;align-items:center!important;justify-content:center!important}}
[data-testid="stExpandSidebarButton"] span{{color:var(--text)!important}}
.block-container{{padding:0 40px 108px!important;max-width:none!important}}

/* ── sidebar ────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"]{{background:var(--s1);border-right:1px solid var(--border);
    width:{SIDEBAR_W}px!important}}
[data-testid="stSidebarContent"]{{display:flex;flex-direction:column;height:100%}}
[data-testid="stSidebarHeader"]{{height:0!important;min-height:0!important;padding:0!important}}
[data-testid="stSidebarUserContent"]{{padding:10px 14px 16px!important;height:100%}}
[data-testid="stSidebarCollapseButton"]{{display:none!important}}

[data-testid="stPageLink"] a{{border-radius:8px!important;min-height:44px!important;
    padding:10px 12px!important;display:flex!important;align-items:center!important;gap:11px!important;
    background:transparent!important;text-decoration:none!important}}
[data-testid="stPageLink"] a:hover{{background:rgba(139,92,246,.08)!important}}
[data-testid="stPageLink"] p{{font-family:'Inter',sans-serif!important;font-size:14px!important;
    font-weight:600!important;letter-spacing:0!important;text-transform:none!important;
    color:var(--dim)!important;margin:0!important;white-space:nowrap}}
[data-testid="stPageLink"] [data-testid="stIconMaterial"]{{font-size:19px!important;color:var(--dim)!important}}
/* Containers are keyed navactive_<path>, so match the class by prefix. */
[class*="st-key-navactive"] [data-testid="stPageLink"] a{{background:rgba(139,92,246,.14)!important;
    box-shadow:inset 3px 0 0 var(--purple)!important}}
[class*="st-key-navactive"] [data-testid="stPageLink"] p{{color:var(--text)!important}}
[class*="st-key-navactive"] [data-testid="stPageLink"] [data-testid="stIconMaterial"]{{
    color:var(--purple-l)!important}}

.zb-brand{{padding:4px 10px 2px}}
.zb-brand-name{{font-family:'Syne',sans-serif;font-weight:800;font-size:20px;letter-spacing:-.3px;
    color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.15}}
.zb-brand-sub{{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1.4px;
    color:var(--dim);margin-top:3px;white-space:nowrap}}
.zb-navsec{{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1.6px;
    color:var(--dim);text-transform:uppercase;margin:16px 0 4px;padding:0 12px}}

/* ── context bar ────────────────────────────────────────────────────────── */
.st-key-zbctx{{height:64px;background:var(--s2);border-bottom:1px solid var(--border);
    padding:0 28px!important;margin-bottom:0!important}}
.st-key-zbctx p{{margin:0!important}}
.zb-ctxlab{{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1.6px;
    color:var(--dim);white-space:nowrap}}
.zb-ctxok{{font-size:11px;font-weight:700;color:var(--green-l);white-space:nowrap}}
.zb-ctxwarn{{font-size:11px;font-weight:700;color:var(--amber);white-space:nowrap}}
.zb-ctxsep{{width:1px;height:24px;background:rgba(139,92,246,.2)}}
div[data-testid="stPopover"] button{{background:var(--s3)!important;border:1px solid var(--b-purple)!important;
    border-radius:9px!important;color:var(--text)!important;font-family:'Inter',sans-serif!important;
    font-weight:600!important;font-size:14px!important;text-transform:none!important;
    letter-spacing:0!important;padding:9px 13px!important;min-height:40px!important;
    box-shadow:none!important;width:auto!important}}

.zb-page{{padding:26px 40px 0}}

</style>
"""


def brand():
    st.markdown('<div class="zb-brand"><div class="zb-brand-name">ZiggyBot</div>'
                '<div class="zb-brand-sub">SMILEZ · V3</div></div>', unsafe_allow_html=True)


def nav_link(page, current):
    """One sidebar link. The container's key carries the active state to CSS."""
    state = "navactive" if page.url_path == current else "navidle"
    with st.container(key=f"{state}_{page.url_path or 'home'}"):
        st.page_link(page, label=page.title, icon=page.icon, use_container_width=True)


def sidebar(sections, trailing, current):
    """sections: {label: [Page]}. trailing: [Page] pinned at the bottom."""
    with st.sidebar:
        brand()
        for label, pages in sections.items():
            if label:
                st.markdown(f'<div class="zb-navsec">{label}</div>', unsafe_allow_html=True)
            for page in pages:
                nav_link(page, current)
        st.markdown('<div style="flex-grow:1;min-height:20px"></div>', unsafe_allow_html=True)
        for page in trailing:
            nav_link(page, current)


def page_header(title):
    st.markdown(f'<div class="zb-page"><h2 style="margin:0 0 14px">{title}</h2></div>',
                unsafe_allow_html=True)
