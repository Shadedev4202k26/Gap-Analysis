"""The "What's new" pop-up on Home.

Each entry in UPDATES shows once per visit, until its `until` date (Michigan
time) has passed, so a notice retires itself without anyone removing it.
Streamlit forgets everything when the page is reopened, so "once per visit"
is the most it can remember without sign-ins: the seen flag is set before the
pop-up opens, which also covers someone closing it with the ✕.

To announce an update, add an entry at the top of UPDATES.
"""
import datetime as dt
from zoneinfo import ZoneInfo

import streamlit as st

STORE_TZ = ZoneInfo("America/Detroit")

UPDATES = [
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


def current(today=None):
    """The newest update still inside its date, or None."""
    today = today or dt.datetime.now(STORE_TZ).date()
    for u in UPDATES:
        if today <= u["until"]:
            return u
    return None


def show(page_for):
    """Open the pop-up for the current update, once per visit. `page_for` maps
    an update's "page" name to its st.Page (studio._page)."""
    u = current()
    if u is None or st.session_state.get(f"zb_seen_{u['id']}"):
        return
    st.session_state[f"zb_seen_{u['id']}"] = True

    @st.dialog("What's new in Ziggy")
    def _pop():
        st.markdown(f"#### {u['title']}")
        st.markdown(u["body"])
        st.markdown("\n".join(f"- {p}" for p in u["points"]))
        st.caption(u["note"])
        left, right = st.columns(2)
        if left.button("Got it", use_container_width=True, key="zb_new_ok"):
            st.rerun()
        target = page_for(u.get("page"))
        if target is not None and right.button(
                u["page_label"], type="primary", icon=":material/arrow_forward:",
                use_container_width=True, key="zb_new_go"):
            st.switch_page(target)

    _pop()
