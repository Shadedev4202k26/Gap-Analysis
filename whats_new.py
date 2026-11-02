"""The "What's new" pop-up on Home.

Every entry in UPDATES still inside its `until` date (Michigan time) shows in
one pop-up, newest first, so a notice retires itself without anyone removing
it. An entry with "highlight" is drawn as a bold callout at the top. "{store}"
in a body becomes the store this device picked.

An entry's "page" gives the pop-up a button to that page, and its "state" is
set first (Split tags opens Shelf tags with Split tag picked). The newest
entry with a page gets the button.

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
        "id": "classic-retired",
        "until": dt.date(2026, 11, 30),
        "title": "Classic tag pages are gone",
        "body": ("**Hook tags · classic** and **Preroll tags · classic** are off the menu. "
                 "Everything they did is in **Shelf tags** now."),
        "points": [
            "**Deals tags:** Shelf tags, then pick Hook, 3.5″, 4″ or Split tag",
            "**Typed tags** (curbside, notes): **Custom tags** in the Print menu",
            "Old bookmarks still work. They open Shelf tags.",
        ],
    },
    {
        "id": "split-tags",
        "until": dt.date(2026, 11, 16),
        "title": "Split tags are now in Shelf tags",
        "body": ("Two strains on one preroll tag, to save space in the bins. Pick "
                 "**Split tag** on the first step of Shelf tags, then 3.5″ or 4″."),
        "points": [
            "**Each half keeps its own colour** and its own sale bubble",
            "**From the inventory:** halves pair up in the order you tick them",
            "**Typed by hand:** rows 1 and 2 share a tag, then 3 and 4",
        ],
        "page": "studio",
        "page_label": "Split tags",
        "state": {"zb_split": True, "zb_fmt": "pr4", "zb_step": 1},
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
            st.session_state.update(target[0].get("state") or {})
            st.switch_page(target[1])

    _pop()
