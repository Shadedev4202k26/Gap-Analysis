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
        "id": "strain-sniffer",
        "until": dt.date(2026, 12, 7),
        "highlight": True,
        "title": "New: Strain Sniffer finds what a customer will like",
        "body": ("Strain lookup is now **Strain Sniffer**, the big card on Home. Tell it what a "
                 "customer likes and it lists what's on **{store}**'s shelves with the closest "
                 "**terpene mix**, from real lab tests."),
        "points": [
            "**🔍 Look up a strain**: any strain, even one we don't carry. The search box stays at the top",
            "**🛍️ Like something we sell**: pick a product they like, see others like it",
            "**✨ By feel & flavor**: relaxed, energetic, citrus, piney and more",
            "Each match shows **why** it matches, price, THC, out front or vault, and this week's **deal**",
        ],
        "note": ("Matches marked *Estimated* have no lab test yet; lab-tested ones come first. "
                 "Feel and flavor words are what customers commonly report, not medical advice."),
        "page": "strain",
        "page_label": "Strain Sniffer",
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
        "id": "strain-lookup-store",
        "until": dt.date(2026, 11, 23),
        "title": "Strain Sniffer shows your store's own numbers",
        "body": ("Search a strain and **{store}'s Dutchie listings** for it show first, with "
                 "the type and THC on the package. Go by those numbers."),
        "points": [
            "**Add the brand** (like FAVRD) for that brand's version of the strain",
            "The profile below is from a live Google search and can take up to a minute",
        ],
        "page": "strain",
        "page_label": "Strain Sniffer",
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
    {
        "id": "live-stock",
        "until": dt.date(2026, 12, 7),
        "title": "No more inventory exports",
        "body": ("**Shelf tags**, **Inventory balance** and **Aging stock** now load "
                 "{store}'s stock straight from Dutchie. It updates every 15 minutes."),
        "points": [
            "**Shelf tags:** pick **Live stock** on the first step (it's picked for you)",
            "**Curbside, Sales Floor and both vaults** are included; the Waiting Room isn't",
            "Need an export anyway? It still works: pick **Import inventory CSV**",
        ],
        "note": "Each page shows when the stock was last updated. Refresh takes the newest.",
        "page": "studio",
        "page_label": "Shelf tags",
    },
    {
        "id": "deals-from-reports",
        "until": dt.date(2026, 12, 7),
        "title": "The weekly deals sheet arrives by itself",
        "body": ("No need to upload the deals sheet here any more. It comes over from "
                 "Smilez Reports within a couple of minutes of being uploaded there."),
        "points": [
            "**Next week's sheet** shows up in the **Week** menu as soon as it's in, "
            "usually Tuesday or Wednesday; this week's stays in use until Monday",
            "**Only what changed** now always compares with last week's sheet",
        ],
        "note": "The upload in the Week menu still works if a sheet is ever missing.",
    },
    {
        "id": "custom-deals",
        "until": dt.date(2026, 11, 30),
        "title": "Custom tags: sale prices and your own bubbles",
        "body": "The typing table in **Custom tags** has two new columns.",
        "points": [
            "**Sale:** crosses out the Price and prints the sale price beside it",
            "**Bubble:** prints a red bubble with your text, like BOGO or 2/$30",
            "A row with its own Sale or Bubble keeps it over this week's deals",
        ],
        "page": "custom",
        "page_label": "Custom tags",
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
