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
        "id": "sell-more",
        "until": dt.date(2026, 12, 14),
        "highlight": True,
        "tag": "Sell more",
        "title": "Help every customer find their next favorite",
        "body": ("Two tools to turn \"what do you have like…?\" into a sale: **Strain Sniffer** "
                 "for the conversation, **hook tags** so every deal is on the wall."),
        "points": [
            "**Ask what they like**, then open **Strain Sniffer**, the big card on Home: a strain "
            "(even one we don't carry), a product they love, or a feel or flavor",
            "**Lead with ⭐ Popular here**: what's selling best at {store} right now",
            "**Mention the 🔥 deal** on a match: a 3-for or 2-for deal is an easy second item",
            "**Out front or vault only** is on every match, so you grab it fast",
            "**Hook tags print this week's deals by themselves**: the sheet arrives from Smilez "
            "Reports and stock comes live from Dutchie, no exports",
            "**Only what changed** reprints just the tags whose deal changed, so the wall stays right",
            "**Custom tags** take a sale price or your own bubble (BOGO, 2/$30) for anything off the sheet",
        ],
        "note": ("Feel and flavor words are what customers commonly report. Never promise "
                 "medical effects."),
        "page": "strain",
        "page_label": "Open Strain Sniffer",
    },
    {
        "id": "sniffer-come-back",
        "until": dt.date(2026, 12, 14),
        "title": "Strain Sniffer: picks based on what shoppers come back for",
        "body": ("**Like something we sell** now lists what shoppers of that product really go on to "
                 "buy, from our own sales at all 8 stores."),
        "points": [
            "**🛒 The reason is on the card**: its shoppers later bought this, same brand, same shelf level",
            "**🔁 Shoppers come back for this** marks products people buy again: our own version of a good review",
            "The terpene match is still there as the tie-breaker and the talking point",
            "Looking up a strain, and feel and flavor, work as before",
        ],
        "note": "Counts only. ZiggyBot never sees who bought what.",
        "page": "strain",
        "page_label": "Open Strain Sniffer",
    },
    {
        "id": "sniffer-honest-labels",
        "until": dt.date(2026, 12, 7),
        "title": "Strain Sniffer: \"Very close\" now means it",
        "body": ("Matches are scored more strictly, so you'll see **fewer \"Very close\" and "
                 "\"Close\"** picks. The ones you do see are worth leading with."),
        "points": [
            "**Very close** is rare: about 1 in 50 products would earn it by chance",
            "**The brand counts.** A product with no terpene test of its own now uses its "
            "**own brand's** test of that strain first",
            "A match based on **another brand's** test of the strain never shows above **Close**, "
            "and an estimate never above **Similar**: two brands' versions of one strain often differ",
            "Tested products show their **total terpenes %**: higher usually means more smell and flavor",
        ],
        "page": "strain",
        "page_label": "Open Strain Sniffer",
    },
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
        "id": "missing-stock-check",
        "until": dt.date(2026, 11, 30),
        "title": "Inventory balance is now a short Missing Stock Check",
        "body": ("It lists only what's **missing from the sales floor** while the vault has it. "
                 "No more room percentages or long balancing reports."),
        "points": [
            "**Print the list** and check each item against the wall",
            "**On the wall?** Make the adjustment in Backoffice and tick it off",
            "**Not on the wall?** Bring it out from the vault, move it in Backoffice, tick it off",
            "Bulk and tiered flower, accessories, apparel, promo and batteries are left out to start",
            "**A slider skips products with only a few left**, too few to be worth moving",
        ],
        "note": ("Wayne also checks the Curbside Room and Upstairs Vault, and skips "
                 "products with fewer than 20 in stock to start."),
        "page": "inventory",
        "page_label": "Inventory balance",
    },
    {
        "id": "aging-slider",
        "until": dt.date(2026, 11, 23),
        "title": "Aging stock: pick how old",
        "body": ("A slider at the top of **Aging stock** sets the youngest stock it lists. "
                 "It starts at **90 days**, so stock from the last couple of months stays off the list."),
        "points": [
            "**Slide right** to see only the oldest stock, **left** to look further back (down to 45 days)",
            "The counts and the **PDF** follow the slider",
        ],
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
            here = store or "your store"
            body = u["body"].replace("{store}", here)
            points = [p.replace("{store}", here) for p in u["points"]]
            if u.get("highlight"):
                note = (f'<p style="margin-top:8px;font-size:.85em;opacity:.8">{_md(u["note"])}</p>'
                        if u.get("note") else "")
                st.markdown(
                    f'<div class="zb-new-hl"><span class="zb-new-tag">{_md(u.get("tag", "Important"))}</span>'
                    f'<h4>{_md(u["title"])}</h4><p>{_md(body)}</p><ul>'
                    + "".join(f"<li>{_md(p)}</li>" for p in points)
                    + f"</ul>{note}</div>", unsafe_allow_html=True)
                continue
            st.markdown(f"#### {u['title']}")
            st.markdown(body)
            st.markdown("\n".join(f"- {p}" for p in points))
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
