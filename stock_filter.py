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


def bar(key, products, categories=None, extra=None, placeholder=None, multi_cats=False):
    """Draw the bar and return one True/False per item: does it pass?

    products: each item's full product name (its brand is read from it).
    categories: each item's category, or None for no Category picker.
    extra: more text per item the search also looks in (strain, brand line...).
    multi_cats: instead of one Category box, two lists on a second row: "Only
        these categories" (empty = all) and "Leave out these categories", so a
        report can run on everything except accessories and a few more.
    """
    ss = st.session_state
    qk = f"{key}_q"
    if qk not in ss:
        ss[qk] = ss.get(SHARED_Q, "")
    multi = multi_cats and categories is not None
    cols = st.columns([3, 2, 2] if categories is not None and not multi
                      else [3, 2], vertical_alignment="center")
    q = cols[0].text_input(
        "Search", key=qk, on_change=_keep_q, args=(qk,), label_visibility="collapsed",
        icon=":material/search:",
        placeholder=placeholder or "Search: any words, any order (e.g. wedding preroll)")
    brands = [brand_of(p) for p in products]
    cat_pick = ALL_CATS
    only, leave_out = set(), set()
    if categories is not None:
        counts = {}
        for c in categories:
            counts[c or "—"] = counts.get(c or "—", 0) + 1
        label = lambda c: f"{c}  ({counts[c]:,})"
        if multi:
            # A category that left the export would make a saved pick invalid.
            for k in (f"{key}_only", f"{key}_out"):
                if k in ss:
                    ss[k] = [c for c in ss[k] if c in counts]
            c1, c2 = st.columns(2)
            only = set(c1.multiselect(
                "Only these categories", sorted(counts), key=f"{key}_only",
                format_func=label, placeholder="All categories",
                help="Leave empty to include every category."))
            leave_out = set(c2.multiselect(
                "Leave out these categories", sorted(counts), key=f"{key}_out",
                format_func=label, placeholder="None left out",
                help="Pick categories to skip, like Accessories."))
        else:
            cat_pick = cols[1].selectbox(
                "Category", [ALL_CATS] + sorted(counts), key=f"{key}_cat",
                label_visibility="collapsed",
                format_func=lambda c: c if c == ALL_CATS else label(c))

    def cat_ok(i):
        c = (categories[i] or "—") if categories is not None else ""
        if multi:
            return (not only or c in only) and c not in leave_out
        return cat_pick == ALL_CATS or c == cat_pick

    # Brands listed are the ones left in the chosen categories, so the list stays short.
    bcounts = {}
    for i, b in enumerate(brands):
        if cat_ok(i):
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
        ok = cat_ok(i) \
            and (brand_pick == ALL_BRANDS or brands[i] == brand_pick) \
            and match(qw, f"{p} {extra[i] if extra else ''}")
        out.append(ok)
    return out
