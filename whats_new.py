"""The "What's new" pop-up on Home.

Every entry in UPDATES still inside its `until` date (Michigan time) shows in
one pop-up, newest first, so a notice retires itself without anyone removing
it. An entry with "highlight" is drawn as a bold callout at the top. "{store}"
in a body becomes the store this device picked.

It opens once per visit: Streamlit forgets everything when the page is
reopened, so that is the most it can remember without sign-ins. The seen flag
is set before the pop-up opens, which also covers someone closing it with ✕.

To announce an update, add an entry at the top of UPDATES.
"""
import datetime as dt
from zoneinfo import ZoneInfo

import streamlit as st

STORE_TZ = ZoneInfo("America/Detroit")

UPDATES = [
    {
        "id": "store-required",
        "until": dt.date(2026, 11, 16),
        "highlight": True,
        "title": "ZiggyBot now asks for your store first",
        "body": ("Nothing opens until your store is picked, so tags always print with "
                 "**your store's deals**. This device is set to **{store}**."),
        "points": [
            "**Bookmark this page now.** It opens on your store every time.",
            "Wrong store? Change it in the **Store** box at the top left.",
        ],
    },
    {
        "id": "aging-per-package",
        "until": dt.date(2026, 11, 4),
        "title": "Aging stock now shows each Metrc package",
        "body": ("Each package now gets its own line with its **received date**, age, and "
                 "**Metrc tag**. You'll no longer see one old unit making a whole product "
                 "look old."),
        "points": [
            ("**First in, first out:** pull the oldest package forward first"),
            ("**Counts:** match each line to a tag on the shelf or in the vault"),
            ("**Flags:** on sale, expiring within 60 days, expired"),
        ],
        "note": ("Export from Dutchie with Package ID, Product, Available, Inventory date "
                 "and Room."),
        "page": "aging",
        "page_label": "Aging stock",
    },
]

CSS = """<style>
.zb-new-hl{border:2px solid #f59e0b;background:rgba(245,158,11,.14);border-radius:12px;
  padding:14px 16px;margin:2px 0 14px}
.zb-new-hl .zb-new-tag{display:inline-block;background:#f59e0b;color:#1a1204;font-weight:800;
  font-size:11px;letter-spacing:.08em;text-transform:uppercase;border-radius:6px;
  padding:2px 8px;margin-bottom:6px}
.zb-new-hl h4{margin:0 0 6px;font-size:1.15rem}
.zb-new-hl p,.zb-new-hl li{margin:0 0 4px}
.zb-new-hl ul{margin:6px 0 0;padding-left:1.2em}
</style>"""


def current(today=None):
    """Every update still inside its date, newest first."""
    today = today or dt.datetime.now(STORE_TZ).date()
    return [u for u in UPDATES if today <= u["until"]]


def _md(text):
    """The few bits of markdown the entries use, for the callout's HTML."""
    import html
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(text))


def show(page_for, store=""):
    """Open the pop-up once per visit. `page_for` maps an update's "page" name
    to its st.Page (studio._page); `store` fills "{store}"."""
    ups = current()
    key = "zb_seen_" + "+".join(u["id"] for u in ups)
    if not ups or st.session_state.get(key):
        return
    st.session_state[key] = True

    @st.dialog("What's new in Ziggy")
    def _pop():
        st.markdown(CSS, unsafe_allow_html=True)
        for u in ups:
            body = u["body"].replace("{store}", store or "your store")
            if u.get("highlight"):
                st.markdown(
                    '<div class="zb-new-hl"><span class="zb-new-tag">Important</span>'
                    f'<h4>{_md(u["title"])}</h4><p>{_md(body)}</p><ul>'
                    + "".join(f"<li>{_md(p)}</li>" for p in u["points"])
                    + "</ul></div>", unsafe_allow_html=True)
                continue
            st.markdown(f"#### {u['title']}")
            st.markdown(body)
            st.markdown("\n".join(f"- {p}" for p in u["points"]))
            if u.get("note"):
                st.caption(u["note"])
        left, right = st.columns(2)
        if left.button("Got it", use_container_width=True, key="zb_new_ok"):
            st.rerun()
        target = next(((u, page_for(u["page"])) for u in ups if u.get("page")), None)
        if target and target[1] is not None and right.button(
                target[0]["page_label"], type="primary", icon=":material/arrow_forward:",
                use_container_width=True, key="zb_new_go"):
            st.switch_page(target[1])

    _pop()
