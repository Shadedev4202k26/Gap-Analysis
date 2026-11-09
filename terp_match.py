"""Find a match: products on this store's shelves whose terpene mix is closest to
what a customer is after, so a budtender can say "if you like that, try this".

Terpenes come, best first, from:
  1. the package's own lab test (Dutchie lab results, sent by Smilez Reports
     with the live stock),
  2. lab tests of other packages of the same strain at any Smilez store, and
  3. only when no package of that strain has been tested, an AI estimate from
     the strain name, labelled "estimated". Estimates are kept for the life of
     the app process, so a strain is estimated once, not on every search.

The match itself is arithmetic on the terpene mix (each terpene's share of the
total), so a search costs no AI calls and never waits for one. Estimates for
untested strains are made by one background worker, 40 strains per Groq call,
one call every 30 seconds: inside Groq's free limits (1,000 calls a day, 8,000
tokens a minute) with room left for Strain Sniffer's strain profiles.

Three ways in: a strain the customer likes (lab numbers when we carry it, else
the strain profile Strain Sniffer found online), something we sell, or feel and
flavor picks. The feel and flavor words are what customers commonly say about
each terpene, never health claims.
"""
import json
import math
import re
import threading
import time

import requests
import streamlit as st

import deals as deals_mod
import live_stock

# Dutchie lab test name -> the terpene we show. Alpha/beta pinene are one
# "Pinene" to people at the counter, and so on. Phytol and the oxides are left
# out: they're minor and nobody asks for them.
DUTCHIE = {"BetaMyrcene": "Myrcene", "Limonene": "Limonene", "BetaCaryophyllene": "Caryophyllene",
           "Linalool": "Linalool", "AlphaPinene": "Pinene", "BetaPinene": "Pinene",
           "Humulene": "Humulene", "Terpinolene": "Terpinolene", "Ocimene": "Ocimene",
           "Bisabolol": "Bisabolol", "AlphaBisabolol": "Bisabolol", "Nerolidol": "Nerolidol"}
TERPS = ["Myrcene", "Limonene", "Caryophyllene", "Linalool", "Pinene", "Humulene",
         "Terpinolene", "Ocimene", "Bisabolol", "Nerolidol"]
AROMA = {"Myrcene": "earthy, musky", "Limonene": "citrus", "Caryophyllene": "pepper, spice",
         "Linalool": "floral, lavender", "Pinene": "pine", "Humulene": "hoppy, woody",
         "Terpinolene": "fresh, fruity-herbal", "Ocimene": "sweet, tropical",
         "Bisabolol": "chamomile, honey", "Nerolidol": "woody, floral"}
COLOR = {"Myrcene": "#A78BFA", "Limonene": "#FACC15", "Caryophyllene": "#F97316",
         "Linalool": "#C084FC", "Pinene": "#4ADE80", "Humulene": "#A3E635",
         "Terpinolene": "#22D3EE", "Ocimene": "#FB7185", "Bisabolol": "#FDE68A",
         "Nerolidol": "#94A3B8"}

# What customers commonly say each terpene feels or tastes like. Weights are
# the mix that best fits the word.
FEELS = {
    "😌 Relaxed": {"Myrcene": 3, "Linalool": 2, "Caryophyllene": 1},
    "🌙 Sleepy": {"Myrcene": 3, "Linalool": 2, "Bisabolol": 1, "Nerolidol": 1},
    "😄 Happy": {"Limonene": 3, "Linalool": 1, "Caryophyllene": 1},
    "⚡ Energetic": {"Limonene": 2, "Terpinolene": 2, "Pinene": 2, "Ocimene": 1},
    "🎯 Focused": {"Pinene": 3, "Terpinolene": 1, "Limonene": 1},
    "🎨 Creative": {"Terpinolene": 3, "Ocimene": 1, "Limonene": 1},
    "🧘 Calm, clear-headed": {"Caryophyllene": 3, "Linalool": 1, "Humulene": 1},
}
FLAVORS = {
    "🍋 Citrus": {"Limonene": 3},
    "🌲 Pine": {"Pinene": 3},
    "🌶️ Spicy, peppery": {"Caryophyllene": 3, "Humulene": 1},
    "🌸 Floral": {"Linalool": 3, "Nerolidol": 1},
    "🍓 Sweet, fruity": {"Ocimene": 2, "Terpinolene": 1, "Myrcene": 1},
    "🌿 Earthy, musky": {"Myrcene": 3, "Humulene": 1},
    "🍺 Hoppy, woody": {"Humulene": 3, "Caryophyllene": 1},
}

GROUPS = [("Flower", re.compile(r"flower|prepack|eighth|bulk|smalls|popcorn|tier|secret stash", re.I)),
          ("Pre-rolls", re.compile(r"pre.?roll|blunt", re.I)),
          ("Vapes", re.compile(r"cart|vape|510|disposable|pod", re.I)),
          ("Concentrates", re.compile(r"concentrate|rosin|resin|badder|shatter|wax|sauce|diamond|hash|syringe|rso", re.I))]
ALL = "All"
OUT_FRONT = ("Sales Floor", "Curbside Room")
EST_BATCH, EST_PAUSE = 40, 30         # strains per estimate call, seconds between calls
SHOW = 10

_deps = {}


def configure(build_rows, fix_prices, groq_key, groq_model, db):
    """app.py hands over its tag-row parser, the outdoor price fix, the Groq key
    and model, and the Supabase connection."""
    _deps.update(build_rows=build_rows, fix_prices=fix_prices, groq_key=groq_key,
                 groq_model=groq_model, db=db)


# ── terpene vectors ─────────────────────────────────────────────────────────
def parse_lab(text):
    """'Limonene:1.65;BetaMyrcene:0.76' -> {'Limonene': 1.65, 'Myrcene': 0.76}."""
    out = {}
    for part in str(text or "").split(";"):
        name, _, v = part.partition(":")
        t = DUTCHIE.get(name.strip())
        try:
            val = float(v)
        except ValueError:
            continue
        if t and val > 0:
            out[t] = out.get(t, 0) + val
    return out


def mix(d):
    """Each terpene's share of the total, so a 1% product and a 3% product with
    the same profile match."""
    tot = sum(d.values())
    return {k: v / tot for k, v in d.items()} if tot > 0 else {}


def average(mixes):
    out = {}
    for m in mixes:
        for k, v in m.items():
            out[k] = out.get(k, 0) + v / len(mixes)
    return out


def from_names(names):
    """A ranked list of terpene names (strongest first) -> an approximate mix."""
    found = []
    for n in names:
        t = canon(n)
        if t and t not in found:
            found.append(t)
    weights = [0.4, 0.27, 0.18, 0.1, 0.05]
    return mix({t: weights[i] for i, t in enumerate(found[:5])})


def canon(word):
    w = str(word).lower()
    for t in TERPS:
        if t.lower() in w:
            return t
    if "caryoph" in w or "bcp" in w:
        return "Caryophyllene"
    return None


def from_text(text):
    """The strain profile's terpene text ('Myrcene, β-Caryophyllene and Limonene')."""
    return from_names(re.split(r",|;|/|\band\b|\(|\)", str(text or "")))


def similarity(a, b):
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def top(m, n=3):
    return [k for k, v in sorted(m.items(), key=lambda kv: -kv[1])[:n] if v > 0.04]


def closeness(s):
    return "Very close" if s >= 0.95 else "Close" if s >= 0.88 else "Similar" if s >= 0.75 else "Some overlap"


# ── stock -> products ───────────────────────────────────────────────────────
def group_of(category):
    for name, pat in GROUPS:
        if pat.search(str(category or "")):
            return name
    return None


def _norm_strain(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


@st.cache_data(ttl=300, show_spinner=False, max_entries=4)
def lab_library(stores):
    """Strain -> average lab mix over every tested package at every store. This
    is what corrects an estimate: one tested package anywhere beats a guess."""
    db = _deps.get("db") and _deps["db"]()
    per = {}
    for store in stores:
        got = live_stock.latest(db, store)
        if not got or "Terpenes" not in got[0].columns:
            continue
        df = got[0]
        rows = _deps["build_rows"](df)
        strain_of = {r["product"]: _norm_strain(r["strain"]) for r in rows}
        for prod, lab in zip(df["Product"], df["Terpenes"]):
            m = mix(parse_lab(lab))
            s = strain_of.get(str(prod).strip('="').strip())
            if m and s:
                per.setdefault(s, {})[str(prod)] = m     # one vote per product, not per package
    return {s: average(list(p.values())) for s, p in per.items()}


def products(df, deals):
    """The store's stock as one entry per product: rooms, quantity, price, THC,
    this week's deal and its own lab mix (if any package of it was tested)."""
    rows = _deps["build_rows"](df)
    _deps["fix_prices"](rows)
    by_name = {}
    for r in rows:
        by_name.setdefault(r["product"], r)
    has_lab = "Terpenes" in df.columns
    out = {}
    for rec in df.to_dict("records"):
        name = str(rec.get("Product", "")).strip('="').strip()
        r = by_name.get(name)
        grp = group_of(rec.get("Category"))
        if not r or not grp:
            continue
        p = out.get(name)
        if p is None:
            d = deals_mod.for_row(r, deals) if deals else None
            p = out[name] = {"name": name, "strain": r["strain"], "skey": _norm_strain(r["strain"]),
                             "type": r["type"], "thc": r["thc"], "price": r["price"],
                             "group": grp, "rooms": set(), "qty": 0.0, "labs": [],
                             "deal": d.text if d else ""}
        p["rooms"].add(str(rec.get("Room", "")))
        try:
            p["qty"] += float(rec.get("Available") or 0)
        except ValueError:
            pass
        if has_lab:
            m = mix(parse_lab(rec.get("Terpenes")))
            if m:
                p["labs"].append(m)
    return list(out.values())


@st.cache_resource
def _estimates():
    """Strain -> estimated mix (or {} when the AI didn't know it), shared by
    every store for the life of the app process, plus the strains waiting."""
    return {"memo": {}, "todo": [], "lock": threading.Lock(), "worker": None}


def estimate(strains):
    """Queue strains with no estimate yet for the background worker. A search
    never waits for it: new estimates show on later searches. Returns how many
    of these strains are still waiting."""
    e = _estimates()
    key = _deps.get("groq_key")
    with e["lock"]:
        memo, todo = e["memo"], e["todo"]
        waiting = [s for s in dict.fromkeys(strains) if s and s not in memo]
        # This store's strains go to the front of the line.
        e["todo"] = waiting + [s for s in todo if s not in set(waiting)]
        if key and e["todo"] and not (e["worker"] and e["worker"].is_alive()):
            e["worker"] = threading.Thread(target=_work, args=(e, key, _deps.get("groq_model")),
                                           daemon=True)
            e["worker"].start()
    return len(waiting)


def _work(e, key, model):
    """Estimate EST_BATCH strains at a time, one call every EST_PAUSE seconds,
    which keeps well inside Groq's free limit (8,000 tokens a minute) and
    leaves room for Strain Sniffer's strain profiles. Stops when the queue is empty
    or after repeated failures (it starts again on the next search)."""
    fails = 0
    while fails < 3:
        with e["lock"]:
            chunk = e["todo"][:EST_BATCH]
        if not chunk:
            return
        got, wait = _ask_groq(key, model, chunk)
        if got is None:
            fails += 1
        else:
            fails = 0
            with e["lock"]:
                for s in chunk:
                    e["memo"][s] = from_names(got.get(s, []) or [])
                e["todo"] = [s for s in e["todo"] if s not in e["memo"]]
        time.sleep(max(EST_PAUSE, wait))


def _ask_groq(key, model, names):
    """({strain: [terpenes]}, seconds to wait before the next call), or (None, wait)."""
    system = ("You are a cannabis strain database. For each strain name, give its three most "
              "dominant terpenes, strongest first, as commonly reported by lab-tested listings "
              "(Leafly, breeders, dispensary menus). Use only these names: " + ", ".join(TERPS) +
              ". If you don't recognise a strain, give an empty list. Answer with one JSON object "
              "mapping each name exactly as given to its list.")
    payload = {"model": model, "temperature": 0.1, "reasoning_effort": "low",
               "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": json.dumps(names)}]}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=40, json=payload,
                          headers={"Authorization": f"Bearer {key}"})
        if r.status_code == 429:
            try:
                return None, float(r.headers.get("retry-after", 60))
            except ValueError:
                return None, 60
        if r.status_code != 200:
            return None, 60
        c = r.json()["choices"][0]["message"]["content"]
        data = json.loads(c[c.find("{"):c.rfind("}") + 1])
        return {_norm_strain(k): v for k, v in data.items() if isinstance(v, list)}, 0
    except Exception:                                        # noqa: BLE001
        return None, 60


def profile(p, library):
    """(mix, source) for a product: its own lab, same-strain lab, or estimate."""
    if p["labs"]:
        return average(p["labs"]), "lab"
    if p["skey"] in library:
        return library[p["skey"]], "strain lab"
    est = _estimates()["memo"].get(p["skey"])
    return (est, "estimated") if est else ({}, None)


def rank(target, prods, library, exclude=None):
    out = []
    for p in prods:
        if exclude and exclude(p):
            continue
        m, src = profile(p, library)
        if not m:
            continue
        s = similarity(target, m)
        # Closeness band first, then a real lab test before an estimate.
        band = 3 if s >= 0.95 else 2 if s >= 0.88 else 1 if s >= 0.75 else 0
        out.append(((band, {"lab": 2, "strain lab": 1}.get(src, 0), s), s, p, m, src))
    out.sort(key=lambda x: x[0], reverse=True)
    return [(s, p, m, src) for _, s, p, m, src in out]


def why(target, m, like=""):
    shared = [t for t in top(m) if t in top(target)]
    if shared:
        words = " and ".join(t.lower() for t in shared[:2])
        aroma = "; ".join(AROMA[t] for t in shared[:2])
        return f"Both lead with {words} ({aroma})"
    lead = top(m, 1)
    return f"Leads with {lead[0].lower()} ({AROMA[lead[0]]})" if lead else ""


# ── page ────────────────────────────────────────────────────────────────────
def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bars(m):
    segs = "".join(f'<span title="{t} {v:.0%}" style="display:inline-block;height:8px;width:{v * 100:.1f}%;'
                   f'background:{COLOR[t]}"></span>' for t, v in sorted(m.items(), key=lambda kv: -kv[1]))
    names = " · ".join(f'<span style="color:{COLOR[t]}">●</span> {t} {m[t]:.0%}' for t in top(m))
    return (f'<div style="display:flex;border-radius:4px;overflow:hidden;background:rgba(255,255,255,.06);'
            f'margin:6px 0 3px">{segs}</div><div style="font-size:11.5px;color:#9CA3AF">{names}</div>')


SOURCE = {"lab": ("🧪 Lab tested", "#22D3EE"), "strain lab": ("🧪 Lab, same strain", "#67E8F9"),
          "estimated": ("≈ Estimated", "#F59E0B")}


def _card(s, p, m, src, target, like):
    out_front = any(r in OUT_FRONT for r in p["rooms"])
    where = "Out front" if out_front else "Vault only"
    tag, col = SOURCE[src]
    deal = (f'<div style="margin-top:6px;font-size:12.5px;color:#FCA5A5;font-weight:600">🔥 {_esc(p["deal"])}</div>'
            if p["deal"] else "")
    qty = f'{p["qty"]:g}'
    html = f"""<div class="sc tm" style="padding:12px 16px;margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:baseline">
        <div style="font-weight:700">{_esc(p["name"])}</div>
        <div style="white-space:nowrap;color:#22D3EE;font-weight:700">{_esc(closeness(s))}</div></div>
      <div style="font-size:12.5px;color:#D1D5DB;margin-top:3px">{_esc(why(target, m, like))}</div>
      {_bars(m)}
      <div style="font-size:12px;color:#9CA3AF;margin-top:4px">
        <span style="color:{col}">{tag}</span> · {_esc(p["type"].title())} · THC {_esc(p["thc"] or "—")} ·
        {_esc(p["price"] or "—")} · {where} ({qty} on hand)</div>{deal}</div>"""
    # One line, no indents: Markdown reads an indented line after a <style> tag as code.
    return " ".join(line.strip() for line in html.splitlines())


def _price(p):
    try:
        return float(str(p["price"]).replace("$", ""))
    except ValueError:
        return None


def results(target, key, like="", exclude=None, stores=(), store=""):
    """Filters, then the closest products for a target mix."""
    db = _deps["db"]()
    got = live_stock.latest(db, store) if store else None   # newest copy: no tags are picked here, so nothing to hold still
    if not got:
        st.info(f"No live stock for {store} right now, so there's nothing to match against.")
        return
    df = got[0]
    if "Terpenes" not in df.columns:
        st.info("The live stock doesn't carry lab terpenes yet. They arrive with the next "
                "Smilez Reports update.")
    from studio import context
    prods = products(df, context().get("deals") or [])
    library = lab_library(tuple(stores))
    waiting = estimate([p["skey"] for p in prods if not p["labs"] and p["skey"] not in library])

    c1, c2, c3, c4 = st.columns([2, 2, 1.4, 1.4], vertical_alignment="bottom")
    grp = c1.selectbox("Category", [ALL] + [g for g, _ in GROUPS], key=f"{key}_grp")
    cap = c2.select_slider("Price up to", ["Any", "$10", "$20", "$30", "$40", "$50", "$75", "$100"],
                           value="Any", key=f"{key}_cap")
    front = c3.toggle("Out front only", value=True, key=f"{key}_front")
    deal_only = c4.toggle("On deal", key=f"{key}_deal")
    pool = [p for p in prods
            if (grp == ALL or p["group"] == grp)
            and (cap == "Any" or (_price(p) is not None and _price(p) <= float(cap[1:])))
            and (not front or any(r in OUT_FRONT for r in p["rooms"]))
            and (not deal_only or p["deal"])]
    ranked = rank(target, pool, library, exclude)
    if not ranked:
        st.caption("Nothing on the shelves matches with these filters. Try All categories or a higher price.")
        return
    labs = sum(1 for _, _, _, src in ranked[:SHOW] if src != "estimated")
    st.caption(f"Closest {min(SHOW, len(ranked))} of {len(ranked)} products · {labs} from lab tests"
               + (f" · {waiting} untested strains still being estimated in the background; "
                  f"they join the list over the next few minutes" if waiting else ""))
    # .sc is the strain card's frame; its "STRAIN.PROFILE" corner label doesn't belong on a match.
    st.markdown("<style>.sc.tm::before{display:none}</style>"
                + "".join(_card(s, p, m, src, target, like) for s, p, m, src in ranked[:SHOW]),
                unsafe_allow_html=True)


def strain_target(strain, profile_terps, stores):
    """The mix to match a searched strain: our own lab tests of it when any
    store has them, else the terpenes from its online profile."""
    lib = lab_library(tuple(stores))
    k = _norm_strain(strain)
    if k in lib:
        return lib[k], "lab"
    m = from_text(profile_terps)
    return (m, "profile") if m else ({}, None)


def picker_target(selected):
    t = {}
    for name in selected:
        for terp, w in {**FEELS, **FLAVORS}.get(name, {}).items():
            t[terp] = t.get(terp, 0) + w
    return mix(t)


MODES = ["🔍 Look up a strain", "🛍️ Like something we sell", "✨ By feel & flavor"]


def match_section(store, stores, mode):
    """Strain Sniffer's other two modes: like something we sell, or by feel and flavor."""
    if mode == MODES[1]:
        db = _deps["db"]()
        got = live_stock.latest(db, store) if store else None   # newest copy: no tags are picked here, so nothing to hold still
        if not got:
            st.info(f"No live stock for {store} right now.")
            return
        from studio import context
        prods = products(got[0], context().get("deals") or [])
        library = lab_library(tuple(stores))
        names = sorted(p["name"] for p in prods if profile(p, library)[0])
        pick = st.selectbox("A product we have that they like", names, index=None,
                            placeholder="Type to search our products…", key="tm_like")
        if not pick:
            st.caption("Pick a product to find others with the closest terpene mix. "
                       "The list is what's in stock here now.")
            return
        p = next(x for x in prods if x["name"] == pick)
        m, src = profile(p, library)
        st.markdown(_bars(m), unsafe_allow_html=True)
        results(m, "tm_like", like=p["strain"].title() or pick, exclude=lambda x: x["name"] == pick, stores=stores, store=store)
        return
    feel = st.pills("Feel they're after", list(FEELS), selection_mode="multi", key="tm_feel")
    flav = st.pills("Flavors they like", list(FLAVORS), selection_mode="multi", key="tm_flav")
    picked = list(feel or []) + list(flav or [])
    if not picked:
        st.caption("Pick a feel, a flavor, or both. These are what customers commonly report, "
                   "not medical advice.")
        return
    results(picker_target(picked), "tm_pick", stores=stores, store=store)
