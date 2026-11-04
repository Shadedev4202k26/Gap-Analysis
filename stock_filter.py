"""One search-and-filter bar for every page that lists the store's stock:
Shelf tags, Inventory balance and Aging stock.

Dutchie's own Backoffice search only finds the exact phrase as written:
"wedding cake preroll" finds nothing next to "Zooted | Wedding Cake | 1G
Preroll". Here every word typed just has to appear somewhere, in any order,
ignoring case, accents and the " | " separators, so "wedding preroll",
"zooted wedding" and "wedding cake 1g" all find it.

Next to the search: Category and Brand pickers listing only what the store
has, with counts. The search text follows you from page to page; the pickers
belong to each page.
"""
import re
import unicodedata

import streamlit as st

ALL_CATS, ALL_BRANDS = "All categories", "All brands"
SHARED_Q = "zb_find_q"          # the search text, kept across pages


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9.%]+", " ", s.lower()).strip()


def words(q):
    return _norm(q).split()


def match(q_words, text):
    """Every typed word appears in the text, in any order."""
    if not q_words:
        return True
    t = _norm(text)
    return all(w in t for w in q_words)


def brand_of(product):
    """The brand: a full Dutchie name starts with it ("Zooted | Wedding Cake | ...")."""
    return str(product or "").split("|")[0].strip() or "—"


def _keep_q(key):
    st.session_state[SHARED_Q] = st.session_state.get(key, "")


def bar(key, products, categories=None, extra=None, placeholder=None):
    """Draw the bar and return one True/False per item: does it pass?

    products: each item's full product name (its brand is read from it).
    categories: each item's category, or None for no Category picker.
    extra: more text per item the search also looks in (strain, brand line...).
    """
    ss = st.session_state
    qk = f"{key}_q"
    if qk not in ss:
        ss[qk] = ss.get(SHARED_Q, "")
    cols = st.columns([3, 2, 2] if categories is not None else [3, 2],
                      vertical_alignment="center")
    q = cols[0].text_input(
        "Search", key=qk, on_change=_keep_q, args=(qk,), label_visibility="collapsed",
        icon=":material/search:",
        placeholder=placeholder or "Search: any words, any order (e.g. wedding preroll)")
    brands = [brand_of(p) for p in products]
    cat_pick = ALL_CATS
    if categories is not None:
        counts = {}
        for c in categories:
            counts[c or "—"] = counts.get(c or "—", 0) + 1
        cat_pick = cols[1].selectbox(
            "Category", [ALL_CATS] + sorted(counts), key=f"{key}_cat",
            label_visibility="collapsed",
            format_func=lambda c: c if c == ALL_CATS else f"{c}  ({counts[c]:,})")
    # Brands listed are the ones left in the chosen category, so the list stays short.
    bcounts = {}
    for i, b in enumerate(brands):
        if cat_pick == ALL_CATS or (categories[i] or "—") == cat_pick:
            bcounts[b] = bcounts.get(b, 0) + 1
    bk = f"{key}_brand"
    if ss.get(bk) not in (None, ALL_BRANDS) and ss[bk] not in bcounts:
        ss[bk] = ALL_BRANDS                  # that brand isn't in this category
    brand_pick = cols[-1].selectbox(
        "Brand", [ALL_BRANDS] + sorted(bcounts, key=str.lower), key=bk,
        label_visibility="collapsed",
        format_func=lambda b: b if b == ALL_BRANDS else f"{b}  ({bcounts[b]:,})")

    qw = words(q)
    out = []
    for i, p in enumerate(products):
        ok = (cat_pick == ALL_CATS or (categories[i] or "—") == cat_pick) \
            and (brand_pick == ALL_BRANDS or brands[i] == brand_pick) \
            and match(qw, f"{p} {extra[i] if extra else ''}")
        out.append(ok)
    return out
