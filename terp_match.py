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
total): how far apart two mixes are, with the rarer terpenes counting more. The
"Very close / Close / Similar" labels are set against our own lab data (see
CLOSE_AT), and tools/sniffer_check.py re-checks them. A search costs no AI calls
and never waits for one. Estimates for
untested strains are made by one background worker, 40 strains per Groq call,
one call every 30 seconds: inside Groq's free limits (1,000 calls a day, 8,000
tokens a minute) with room left for Strain Sniffer's strain profiles.

Three ways in: a strain the customer likes (lab numbers when we carry it, else
the strain profile Strain Sniffer found online), something we sell, or feel and
flavor picks. The feel and flavor words are what customers commonly say about
each terpene, never health claims.
"""
import datetime as dt
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

# The average product's mix and how much each terpene's share varies from one
# product to the next, over the 1,378 lab-tested flower, pre-roll and live
# concentrate products at the 8 stores (Nov 2026). Three terpenes (limonene,
# caryophyllene, myrcene) lead 94% of products, so two products picked at random
# already share most of their mix. A terpene that varies little counts for more
# when it differs. tools/sniffer_check.py prints these again from live stock.
TYPICAL = {"Myrcene": 0.176, "Limonene": 0.242, "Caryophyllene": 0.235, "Linalool": 0.110,
           "Pinene": 0.087, "Humulene": 0.092, "Terpinolene": 0.002, "Ocimene": 0.0,
           "Bisabolol": 0.031, "Nerolidol": 0.026}
SPREAD = {"Myrcene": 0.152, "Limonene": 0.111, "Caryophyllene": 0.119, "Linalool": 0.073,
          "Pinene": 0.060, "Humulene": 0.062, "Terpinolene": 0.020, "Ocimene": 0.020,
          "Bisabolol": 0.038, "Nerolidol": 0.032}
WEIGHT = {t: 1 / math.sqrt(v) for t, v in SPREAD.items()}

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
    named = mix({t: weights[i] for i, t in enumerate(found[:5])})
    if not named:
        return {}
    # The names only give the leaders. The rest of the mix is filled in from the
    # average product, so a guess isn't scored as if it had nothing else in it.
    return mix({t: NAMED_SHARE * named.get(t, 0) + (1 - NAMED_SHARE) * TYPICAL[t] for t in TERPS})


NAMED_SHARE = 0.75


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


def distance(a, b):
    """How far apart two mixes are: 0 is the same mix. Each terpene's gap is
    weighted, so a difference in pinene or terpinolene counts for more than the
    same difference in myrcene."""
    return math.sqrt(sum(((a.get(t, 0) - b.get(t, 0)) * WEIGHT[t]) ** 2 for t in TERPS))


def similarity(a, b):
    """1 for the same mix, falling to 0 as the mixes move apart."""
    return max(0.0, 1 - distance(a, b) / 2) if a and b else 0.0


def lean(target, m):
    """How much of a product's mix sits in the terpenes of a feel or flavor
    pick (1 = all of it). A pick isn't a real mix, so it gets its own score."""
    keys = set(target) | set(m)
    dot = sum(target.get(k, 0) * m.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in target.values()))
    nb = math.sqrt(sum(v * v for v in m.values()))
    return dot / (na * nb) if na and nb else 0.0


def top(m, n=3):
    return [k for k, v in sorted(m.items(), key=lambda kv: -kv[1])[:n] if v > 0.04]


# Where each label starts, measured on our own lab tests (Nov 2026): of two
# products picked at random, 2% come out Very close, 9% Close or better, 26%
# Similar or better, and half fall under Some overlap. Two packages of the
# same product are Very close 87% of the time, and one brand's products of the
# same strain 69%. Before, 35% of random pairs were "Close" or better, so the
# word meant little.
CLOSE_AT = (0.825, 0.75, 0.65, 0.52)
LABELS = ("Different mix", "Some overlap", "Similar", "Close", "Very close")
# A feel or flavor pick: how strongly the product leans that way.
LEAN_AT = (0.88, 0.75, 0.55)
LEAN_LABELS = ("Slight lean", "Leans this way", "Good fit", "Strong fit")
# How sure the mix is. A product matched on a test of the same strain from a
# different brand can't be called more than Close (two brands' versions of one
# strain are Close or better only about a third of the time), and an AI
# estimate no more than Similar.
BEST_BAND = {"lab": 4, "brand lab": 4, "strain lab": 3, "estimated": 2}


def band_of(s, how="mix"):
    return sum(1 for c in (CLOSE_AT if how == "mix" else LEAN_AT) if s >= c)


# ── stock -> products ───────────────────────────────────────────────────────
def group_of(category):
    for name, pat in GROUPS:
        if pat.search(str(category or "")):
            return name
    return None


# Grade and grow words that trail a strain: "Pink Runtz Smalls" is Pink Runtz.
GRADE = re.compile(r"\b(?:smalls?|popcorn|shake|trim|outdoor|indoor|greenhouse|sun ?grown|bulk)\b")
_SIZE = re.compile(r"\b\d+\s*x\s*|\d*\.?\d+\s*(?:g|mg|ct|pk|pack)\b", re.I)
_FORM = re.compile(r"flower|pre.?roll|blunt|cart|vape|disposable|infused|rosin|resin|gumm|jar|bag", re.I)


def _norm_strain(s):
    k = re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()
    return " ".join(GRADE.sub(" ", k).split()) or k


def strain_name(product, parsed):
    """The strain to match on. The shelf-tag parser reads the last part of
    "BULK | Common Citizen | OGee Crasher Smalls" as a size-and-grade note
    (Smalls is a grade), which leaves the brand as the strain: every Common
    Citizen smalls then looked like one strain. Here the strain is taken from
    that part instead. "" when the product has no strain."""
    brand = _norm_strain(brand_of(product))
    if parsed and _norm_strain(parsed) != brand:
        return parsed
    parts = [x.strip() for x in str(product).split("|")]
    if parts and parts[0].upper() == "BULK":
        parts = parts[1:]
    for part in parts[1:]:
        if not GRADE.search(part.lower()):
            continue
        name = _norm_strain(_SIZE.sub(" ", part))
        if name and name != brand and not _FORM.search(name) and not name.replace(" ", "").isdigit():
            return name.upper()
    return ""


# Products whose terpenes are the plant's own. Distillate carts, disposables
# and infused prerolls usually have terpenes added (one Runtz cart tests 90%
# limonene), so they never speak for a strain: Runtz built from them came out
# limonene-heavy and matched Orange Tree, a citrus sativa.
NOT_NATURAL = re.compile(r"infused|distillate|cart|vape|disposable|pod|gumm|edible|beverage|chocolate", re.I)


def natural(category, name):
    return group_of(category) in ("Flower", "Pre-rolls", "Concentrates") \
        and not NOT_NATURAL.search(f"{category} {name}")


def kind_of(category, name):
    """ "natural", or the category for products whose terpenes are added."""
    return "natural" if natural(category, name) else group_of(category)


# A small step down when the strain type differs (half that against a hybrid).
# Tested on strains several brands sell: it keeps the same strain from another
# brand near the top while pushing a sativa below a matching hybrid or indica.
TYPE_STEP = 0.03


def type_gap(a, b):
    a, b = str(a or "").lower(), str(b or "").lower()
    if a not in ("indica", "sativa", "hybrid") or b not in ("indica", "sativa", "hybrid") or a == b:
        return 0.0
    return TYPE_STEP / 2 if "hybrid" in (a, b) else TYPE_STEP


def lab_library(stores):
    """Strain -> average lab mix over every tested natural product at every
    store. This is what corrects an estimate: one tested package anywhere beats
    a guess."""
    return _library(stores)[0]


def strain_types(stores):
    """Strain -> its usual type (indica / sativa / hybrid) across our products,
    from Dutchie's own type (products with none don't vote)."""
    return _library(stores)[1]


def brand_types(stores):
    """Strain -> {brand: {type: products}} from Dutchie, across every store."""
    return _library(stores)[2]


def brand_library(stores):
    """(strain, brand, kind) -> average lab mix of that brand's own tested
    products of the strain. kind is "natural" (flower, pre-rolls, live
    concentrates) or the category for the rest, so a brand's untested cart
    borrows from its tested cart, not from its flower."""
    return _library(stores)[3]


def brand_of(name):
    """The brand: "BULK | Brand | Strain" or "Brand | Strain | Size"."""
    parts = [x.strip() for x in str(name).split("|")]
    return parts[1] if parts[0].upper() == "BULK" and len(parts) > 2 else parts[0]


def dutchie_type(value):
    t = str(value or "").strip().lower()
    return t if t in ("indica", "sativa", "hybrid") else None


@st.cache_data(ttl=300, show_spinner=False, max_entries=4)
def _library(stores):
    db = _deps.get("db") and _deps["db"]()
    per, votes, by_brand, per_brand = {}, {}, {}, {}
    for store in stores:
        got = live_stock.latest(db, store)
        if not got or "Terpenes" not in got[0].columns:
            continue
        df = got[0]
        rows = _deps["build_rows"](df)
        strain_of = {r["product"]: _norm_strain(strain_name(r["product"], r["strain"])) for r in rows}
        for prod, lab, cat, raw in zip(df["Product"], df["Terpenes"], df["Category"], df["Strain"]):
            name = str(prod).strip('="').strip()
            s = strain_of.get(name)
            if not s:
                continue
            typ = dutchie_type(raw)
            if typ:
                votes.setdefault(s, {}).setdefault(name, typ)     # one vote per product
                b = by_brand.setdefault(s, {}).setdefault(brand_of(name), {})
                b.setdefault(typ, set()).add(name)
            m = mix(parse_lab(lab))
            if m and natural(cat, name):
                per.setdefault(s, {})[name] = m          # one vote per product, not per package
            kind = kind_of(cat, name)
            if m and kind:
                per_brand.setdefault((s, brand_of(name).lower(), kind), {})[name] = m
    majority = {}
    for s, v in votes.items():
        count = {}
        for t in v.values():
            count[t] = count.get(t, 0) + 1
        majority[s] = max(count, key=count.get)
    return ({s: average(list(p.values())) for s, p in per.items()}, majority,
            {s: {b: {t: len(n) for t, n in ts.items()} for b, ts in bs.items()} for s, bs in by_brand.items()},
            {k: average(list(p.values())) for k, p in per_brand.items()})


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
            strain = strain_name(name, r["strain"])
            p = out[name] = {"name": name, "strain": strain, "skey": _norm_strain(strain),
                             "brand": brand_of(name).lower(), "kind": kind_of(rec.get("Category"), name),
                             "totals": [],
                             "type": r["type"], "thc": r["thc"], "price": r["price"],
                             "group": grp, "rooms": set(), "qty": 0.0, "labs": [],
                             "deal": d.text if d else "",
                             "ppg": per_gram(name, r["price"]),
                             "dtype": dutchie_type(rec.get("Strain")),
                             "infused": bool(LOW_GRADE.search(f'{name} {rec.get("Category", "")}'))}
        p["rooms"].add(str(rec.get("Room", "")))
        try:
            p["qty"] += float(rec.get("Available") or 0)
        except ValueError:
            pass
        if has_lab:
            raw = parse_lab(rec.get("Terpenes"))
            if raw:
                p["labs"].append(mix(raw))
                p["totals"].append(sum(raw.values()))
    for p in out.values():
        p["total"] = terp_total(p["totals"])
    return list(out.values())


def terp_total(totals):
    """A product's total terpenes (% by weight) from its own lab tests, or
    None. Left out when it looks like another unit was entered."""
    t = sum(totals) / len(totals) if totals else 0
    return t if 0.2 <= t <= 15 else None


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


def profile(p, library, brands=None):
    """(mix, source) for a product: its own lab test, its brand's test of the
    same strain, another brand's test of that strain, or an estimate."""
    if p["labs"]:
        return average(p["labs"]), "lab"
    own = (brands or {}).get((p["skey"], p["brand"], p["kind"]))
    if own:
        return own, "brand lab"
    if p["skey"] in library:
        return library[p["skey"]], "strain lab"
    est = _estimates()["memo"].get(p["skey"])
    return (est, "estimated") if est else ({}, None)


POPULAR_TOP = 0.10        # the top 10% of sellers in a category at the store get "Popular here"
POPULAR_MIN = 3           # and must have sold at least this many


def pool_of(p):
    """Bulk flower is sold by the gram, so it's ranked apart from bags and jars."""
    return (p["group"], p["name"].upper().startswith("BULK"))


def sellers(prods, units):
    """{product name: (share of its category it outsells, 0..1)} for the store's
    products with sales, and the set of names that are Popular here."""
    pools = {}
    for p in prods:
        pools.setdefault(pool_of(p), []).append(units.get(p["name"], 0))
    pct, hot = {}, set()
    for p in prods:
        n = units.get(p["name"], 0)
        if not n:
            continue
        others = pools[pool_of(p)]
        beaten = sum(1 for x in others if x < n)
        pct[p["name"]] = beaten / max(len(others) - 1, 1)
        if n >= POPULAR_MIN and pct[p["name"]] >= 1 - POPULAR_TOP:
            hot.add(p["name"])
    return pct, hot


# For "like something we sell", in the same category: a small step down when
# the total terpenes differ (TOTAL_STEP for half or double) or the potency
# level does (per level: mild, medium, strong).
TOTAL_STEP, POTENCY_STEP = 0.03, 0.015


def like_gap(base, p, cuts):
    if not base or base["group"] != p["group"]:
        return 0.0
    gap = 0.0
    a, b = base.get("total"), p.get("total")
    if a and b:
        gap += min(TOTAL_STEP, TOTAL_STEP * abs(math.log2(a / b)))
    la, lb = potency_of(base, cuts), potency_of(p, cuts)
    if la and lb:
        gap += POTENCY_STEP * abs(POTENCY.index(la) - POTENCY.index(lb))
    return gap


SOURCE_RANK = {"lab": 3, "brand lab": 2, "strain lab": 1, "estimated": 0}


def rank(target, prods, library, exclude=None, pct=None, ttype=None, brands=None, how="mix",
         base=None, cuts=None, best=4):
    """Closest first, as (score, product, mix, source, label). Within a label:
    a real lab test before a borrowed one or an estimate, then the store's
    better sellers, then the closer mix. how="lean" scores a feel or flavor
    pick. base is the product being matched ("like something we sell"). best
    holds every label down when the target itself is only a guess (a strain
    profile found online)."""
    pct = pct or {}
    score = similarity if how == "mix" else lean
    out = []
    for p in prods:
        if exclude and exclude(p):
            continue
        m, src = profile(p, library, brands)
        if not m:
            continue
        s = score(target, m) - type_gap(ttype, p["dtype"]) - like_gap(base, p, cuts or {})
        band = band_of(s, how)
        if how == "mix":
            band = min(band, BEST_BAND[src], best)
        label = (LABELS if how == "mix" else LEAN_LABELS)[band]
        out.append(((band, SOURCE_RANK[src], round(pct.get(p["name"], 0), 1), s), s, p, m, src, label))
    out.sort(key=lambda x: x[0], reverse=True)
    return [(s, p, m, src, label) for _, s, p, m, src, label in out]


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


SOURCE = {"lab": ("🧪 Lab tested", "#22D3EE"),
          "brand lab": ("🧪 Lab, same brand and strain", "#22D3EE"),
          "strain lab": ("🧪 Lab, same strain from another brand", "#67E8F9"),
          "estimated": ("≈ Estimated", "#F59E0B")}


def _sold(p, units, days):
    n = units.get(p["name"], 0)
    unit = "g" if p["name"].upper().startswith("BULK") else ""
    return f"⭐ Popular here · {n:,.0f}{unit} sold in {days // 7} weeks"


def type_warning(p, usual):
    """A line for a card whose type would surprise: no type in Dutchie, or the
    opposite of how the strain is usually listed (indica vs sativa)."""
    if not p.get("dtype"):
        return "No type in Dutchie for this product: check the package before saying indica or sativa"
    if usual and {p["dtype"], usual} == {"indica", "sativa"}:
        return (f'{brand_of(p["name"])} lists this as {p["dtype"].title()}; most '
                f'{p["strain"].title()} we carry is {usual.title()}')
    return ""


def _card(label, p, m, src, target, like, photo="", hot="", note="", shelf="", warn=""):
    out_front = any(r in OUT_FRONT for r in p["rooms"])
    where = "Out front" if out_front else "Vault only"
    tag, col = SOURCE[src]
    deal = (f'<div style="margin-top:6px;font-size:12.5px;color:#FCA5A5;font-weight:600">🔥 {_esc(p["deal"])}</div>'
            if p["deal"] else "")
    if hot:
        deal = (f'<div style="margin-top:6px;font-size:12.5px;color:#FDE68A;font-weight:600">{_esc(hot)}</div>'
                + deal)
    if warn:
        deal = (f'<div style="margin-top:6px;font-size:12.5px;color:#FDBA74;font-weight:600">⚠ {_esc(warn)}</div>'
                + deal)
    qty = f'{p["qty"]:g}'
    pic = (f'<img src="{_esc(photo)}" alt="" loading="lazy" style="width:76px;height:76px;object-fit:cover;'
           f'border-radius:10px;background:#fff;flex:none">' if photo else
           '<div style="width:76px;height:76px;border-radius:10px;flex:none;display:flex;align-items:center;'
           'justify-content:center;font-size:26px;background:rgba(255,255,255,.05)">🌿</div>')
    html = f"""<div class="sc tm" style="padding:12px 16px;margin-bottom:10px;display:flex;gap:14px">{pic}
      <div style="flex:1;min-width:0">
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:baseline">
        <div style="font-weight:700">{_esc(p["name"])}</div>
        <div style="white-space:nowrap;color:#22D3EE;font-weight:700">{_esc(label)}</div></div>
      <div style="font-size:12.5px;color:#D1D5DB;margin-top:3px">{_esc(why(target, m, like))}</div>
      {f'<div style="font-size:12.5px;color:#C4B5FD;margin-top:2px">🤖 {_esc(note)}</div>' if note else ""}
      {_bars(m)}
      <div style="font-size:12px;color:#9CA3AF;margin-top:4px">
        <span style="color:{col}">{tag}</span> · {_esc((p["dtype"] or "no type").title())} · THC {_esc(p["thc"] or "—")} ·
        {f'Terpenes {p["total"]:.1f}% · ' if p.get("total") else ""}
        {_esc(p["price"] or "—")}{" · " + _esc(shelf) if shelf else ""} · {where} ({qty} on hand)</div>{deal}</div></div>"""
    # One line, no indents: Markdown reads an indented line after a <style> tag as code.
    return " ".join(line.strip() for line in html.splitlines())


def _day(iso):
    try:
        d = dt.date.fromisoformat(str(iso)[:10])
        return f"{d:%b} {d.day}"
    except ValueError:
        return str(iso or "")


# Shelf level: price per gram against the rest of the category at the store,
# so a search for a top-shelf brand starts with top-shelf matches.
SHELF = ["Value", "Mid", "Top shelf"]
# Infused, ground, shake and trim: cheaper, and their terpenes are mostly added,
# so they're left out of strain and product matches unless switched on.
LOW_GRADE = re.compile(r"infused|ground|shake|trim", re.I)


def per_gram(name, price):
    """Price per gram from the price and the size in the name, or None.
    BULK is priced by the gram; packs multiply ("28 x 1G", ".6G ... 5CT")."""
    try:
        p = float(str(price).replace("$", ""))
    except ValueError:
        return None
    if p <= 0:
        return None
    n = str(name).upper()
    if n.startswith("BULK"):
        return p
    m = re.search(r"(\d+)\s*X\s*(\d*\.?\d+)\s*G\b", n)
    if m:
        g = int(m.group(1)) * float(m.group(2))
    else:
        one = re.search(r"(\d*\.?\d+)\s*G\b", n)
        if not one:
            return None
        ct = re.search(r"(\d+)\s*(?:CT|PK|PACK)\b", n)
        g = float(one.group(1)) * (int(ct.group(1)) if ct else 1)
    return p / g if g else None


def shelf_cuts(prods):
    cuts = {}
    for g in {p["group"] for p in prods}:
        vals = sorted(p["ppg"] for p in prods if p["group"] == g and p.get("ppg"))
        if len(vals) >= 3:
            cuts[g] = (vals[len(vals) // 3], vals[2 * len(vals) // 3])
    return cuts


def shelf_of(p, cuts):
    v, c = p.get("ppg"), cuts.get(p["group"])
    if not v or not c:
        return None
    level = SHELF[0] if v < c[0] else SHELF[2] if v >= c[1] else SHELF[1]
    # Smalls and popcorn are a lower grade whatever they cost: never top shelf.
    if level == SHELF[2] and re.search(r"\bsmalls?\b|popcorn", p["name"], re.I):
        level = SHELF[1]
    return level


def start_shelf(prods, cuts, shelf_from):
    """The shelf level to start from: the picked product's own, else the
    middle level of what we stock from the searched brand (and strain)."""
    if not shelf_from:
        return None
    if shelf_from.get("product"):
        p = next((x for x in prods if x["name"] == shelf_from["product"]), None)
        return shelf_of(p, cuts) if p else None
    brand = str(shelf_from.get("brand") or "").lower().strip()
    strain = _norm_strain(shelf_from.get("strain"))
    if not brand:
        return None
    mine = [p for p in prods if brand in p["name"].lower() and not p["infused"]]
    both = [p for p in mine if strain and p["skey"] == strain]
    levels = sorted(SHELF.index(s) for s in (shelf_of(p, cuts) for p in (both or mine)) if s)
    return SHELF[levels[len(levels) // 2]] if levels else None


POTENCY = ["Mild", "Medium", "Strong"]


def _thc(p):
    m = re.search(r"\d+(?:\.\d+)?", str(p.get("thc") or ""))
    return float(m.group()) if m and "%" in str(p.get("thc")) else None


def potency_cuts(prods):
    """Per category, the THC levels that split its in-stock products into
    thirds: a 30% flower is strong, a 30% concentrate is not."""
    cuts = {}
    for g in {p["group"] for p in prods}:
        vals = sorted(v for v in (_thc(p) for p in prods if p["group"] == g) if v)
        if len(vals) >= 3:
            cuts[g] = (vals[len(vals) // 3], vals[2 * len(vals) // 3])
    return cuts


def potency_of(p, cuts):
    v, c = _thc(p), cuts.get(p["group"])
    if v is None or not c:
        return None
    return POTENCY[0] if v < c[0] else POTENCY[2] if v >= c[1] else POTENCY[1]


def _price(p):
    try:
        return float(str(p["price"]).replace("$", ""))
    except ValueError:
        return None


def results(target, key, like="", exclude=None, stores=(), store="", ttype=None, ref="",
            shelf_from=None, infused=False, how="mix", base=None, best=4):
    """Filters, then the closest products for a target mix. how, base and best
    are rank()'s."""
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
    library, brands = lab_library(tuple(stores)), brand_library(tuple(stores))
    waiting = estimate([p["skey"] for p in prods if not p["labs"] and p["skey"] not in library])

    scuts = shelf_cuts(prods)
    first = start_shelf(prods, scuts, shelf_from)
    c1, c2, c3, c0 = st.columns([1.6, 1.6, 1.7, 2.1], vertical_alignment="bottom")
    grp = c1.selectbox("Category", [ALL] + [g for g, _ in GROUPS], key=f"{key}_grp")
    cap = c2.select_slider("Price up to", ["Any", "$10", "$20", "$30", "$40", "$50", "$75", "$100"],
                           value="Any", key=f"{key}_cap")
    strength = c3.pills("Potency", POTENCY, selection_mode="multi", key=f"{key}_pot",
                        help="Compared with the rest of its category at this store: a strong "
                             "flower and a strong concentrate are different THC levels.")
    # Keyed by the starting level, so a new search starts from its own level.
    shelves = c0.pills("Shelf", SHELF, selection_mode="multi", key=f"{key}_shelf_{first}",
                       default=SHELF[SHELF.index(first):] if first else None,
                       help="Price per gram compared with the rest of its category at this "
                            "store. A brand or product search starts at its own level and up.")
    c4, c5, c6, c7 = st.columns(4, vertical_alignment="center")
    front = c4.toggle("Out front only", value=True, key=f"{key}_front")
    deal_only = c5.toggle("On deal", key=f"{key}_deal")
    with_low = c6.toggle("Include infused & shake", value=infused, key=f"{key}_low",
                         help="Infused, ground, shake and trim: usually cheaper, and their "
                              "terpenes are mostly added after.")
    use_ai = c7.toggle("🤖 AI double-check", value=True, key=f"{key}_ai",
                       help="Groq re-sorts the closest 20 by each strain's lineage and reported "
                            "effects. Off: lab terpenes only.")
    cuts = potency_cuts(prods)
    pool = [p for p in prods
            if (grp == ALL or p["group"] == grp)
            and (not strength or potency_of(p, cuts) in strength)
            and (not shelves or shelf_of(p, scuts) in shelves)
            and (with_low or not p["infused"])
            and (cap == "Any" or (_price(p) is not None and _price(p) <= float(cap[1:])))
            and (not front or any(r in OUT_FRONT for r in p["rooms"]))
            and (not deal_only or p["deal"])]
    units, through, days = live_stock.popular(db, store)
    pct, hot = sellers(prods, units)
    if base:                                   # the picked product, with this store's numbers
        base = next((x for x in prods if x["name"] == base), None)
    ranked = rank(target, pool, library, exclude, pct, ttype, brands, how, base, cuts, best)
    if not ranked:
        st.caption("Nothing on the shelves matches with these filters. Try All categories or a higher price.")
        return
    if ref:
        _log_ask(ref)
    notes, used = {}, False
    if use_ai:
        with st.spinner("Ziggy is double-checking the picks…"):
            ranked, notes, used = ai_rerank(ref or like, ranked)
    labs = sum(1 for _, _, _, src, _ in ranked[:SHOW] if src != "estimated")
    pics = live_stock.photos(db, store)
    usual = strain_types(tuple(stores))
    st.caption(f"Closest {min(SHOW, len(ranked))} of {len(ranked)} products · {labs} from lab tests"
               + (f" · {waiting} untested strains still being estimated in the background; "
                  f"they join the list over the next few minutes" if waiting else "")
               + (f" · ⭐ Popular here: {store}'s top sellers in that category, {days // 7} weeks to "
                  f"{_day(through)}" if units else "")
               + (f" · starting at **{first}**, like {shelf_from.get('brand') or shelf_from.get('product')}"
                  if first else "")
               + (" · 🤖 order double-checked by AI on lineage and reported effects" if used else
                  " · 🤖 AI double-check unavailable right now, lab order shown" if use_ai and ref + like else ""))
    # .sc is the strain card's frame; its "STRAIN.PROFILE" corner label doesn't belong on a match.
    st.markdown("<style>.sc.tm::before{display:none}</style>"
                + "".join(_card(label, p, m, src, target, like, pics.get(p["name"], ""),
                                _sold(p, units, days) if p["name"] in hot else "", notes.get(p["name"], ""),
                                shelf_of(p, scuts) or "", type_warning(p, usual.get(p["skey"])))
                          for s, p, m, src, label in ranked[:SHOW]),
                unsafe_allow_html=True)


def _log_ask(ref):
    """One usage line per distinct question per visit, for Settings' demand
    report: "Like: <product>" or "Feel: <words>". Strain searches are already
    logged as "Searched <strain>" when the search is made."""
    if ref.startswith("the strain "):
        return
    detail = ("Feel: " + ref.split(": ", 1)[1] if ref.startswith("a feel and flavor: ")
              else "Like: " + ref.split(" (", 1)[0])
    seen = st.session_state.setdefault("tm_logged", set())
    if detail in seen:
        return
    seen.add(detail)
    import usage
    usage.log("used", "Strain Sniffer", detail[:120])


AI_POOL = 20             # how many of the lab ranking's best the AI double-check may reorder


def _ai_line(p, m):
    return f'{p["name"]} | {p["dtype"] or "type not listed"} | ' + ", ".join(f"{t} {m[t]:.0%}" for t in top(m))


@st.cache_data(ttl=3600, show_spinner=False, max_entries=256)
def _ai_order(ref, lines, key, model):
    """Groq's order for the candidates, as [(index, note)], or None. Cached an
    hour per question and list, so moving filters back and forth is free."""
    system = (
        "You help budtenders at a Michigan cannabis dispensary. A customer described what they "
        "like. Below are products on our shelves, already shortlisted by lab-tested terpene mix "
        "(name | type | top terpenes). Reorder them from best to worst fit for this customer, "
        "using what you know about each strain's lineage, typically reported effects and "
        "flavor, as well as the terpenes and type shown. Put products whose strain is known to "
        "feel very different (for example an energetic sativa for someone who likes a relaxing "
        "hybrid) last. For each, add a note of at most 8 words saying why it fits, about "
        "lineage, flavor or feel only. Never make medical or health claims. Answer with JSON: "
        '{"order": [{"i": <number>, "note": "<why>"}, ...]} using every number once.')
    user = f"Customer likes: {ref}\n\n" + "\n".join(f"{i}. {line}" for i, line in enumerate(lines))
    payload = {"model": model, "temperature": 0.2, "reasoning_effort": "low",
               "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=12, json=payload,
                          headers={"Authorization": f"Bearer {key}"})
        if r.status_code != 200:
            return None
        c = r.json()["choices"][0]["message"]["content"]
        got = json.loads(c[c.find("{"):c.rfind("}") + 1]).get("order", [])
    except Exception:                                        # noqa: BLE001
        return None
    out, seen = [], set()
    for item in got:
        try:
            i = int(item.get("i"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= i < len(lines) and i not in seen:
            seen.add(i)
            out.append((i, str(item.get("note") or "")[:80]))
    return out or None


def ai_rerank(ref, ranked):
    """The lab ranking's top AI_POOL, reordered by Groq on lineage and reported
    effects; anything it leaves out keeps its lab order after. Returns
    (ranked, {name: note}, used). Any trouble: the lab order, untouched."""
    key, model = _deps.get("groq_key"), _deps.get("groq_model")
    head = ranked[:AI_POOL]
    if not (key and ref and len(head) > 1):
        return ranked, {}, False
    got = _ai_order(ref, tuple(_ai_line(p, m) for _, p, m, _, _ in head), key, model)
    if not got:
        return ranked, {}, False
    order = [head[i] for i, _ in got]
    notes = {head[i][1]["name"]: n for i, n in got if n}
    order += [x for x in head if x not in order]
    return order + ranked[AI_POOL:], notes, True


def strain_target(strain, profile_terps, stores, classification="", brand=""):
    """(mix, source, type) to match a searched strain. Best first: the searched
    brand's own lab tests of it ("brand lab"), our lab tests of it from every
    brand ("lab": flower, pre-rolls and live concentrates), else the terpenes
    from its online profile. Type: what we sell it as, else the profile's
    classification."""
    lib = lab_library(tuple(stores))
    k = _norm_strain(strain)
    typ = strain_types(tuple(stores)).get(k) or next(
        (t for t in ("indica", "sativa", "hybrid") if t in str(classification).lower()), None)
    want = str(brand or "").lower().strip()
    if want:
        mine = [m for (s, b, kind), m in brand_library(tuple(stores)).items()
                if s == k and kind == "natural" and want in b]
        if mine:
            return average(mine), "brand lab", typ
    if k in lib:
        return lib[k], "lab", typ
    m = from_text(profile_terps)
    return (m, "profile", typ) if m else ({}, None, typ)


def picker_target(selected):
    t = {}
    for name in selected:
        for terp, w in {**FEELS, **FLAVORS}.get(name, {}).items():
            t[terp] = t.get(terp, 0) + w
    return mix(t)


MODES = ["🔍 Look up a strain", "🛍️ Like something we sell", "✨ By feel & flavor"]


# Feels that pull opposite ways can't both be picked: the newer pick stays.
CLASH = [("🌙 Sleepy", "⚡ Energetic"), ("🌙 Sleepy", "🎯 Focused"), ("🌙 Sleepy", "🎨 Creative"),
         ("😌 Relaxed", "⚡ Energetic")]


def _no_clash():
    ss = st.session_state
    now, before = list(ss.get("tm_feel") or []), set(ss.get("tm_feel_prev") or [])
    new = [f for f in now if f not in before]
    for added in new:
        for a, b in CLASH:
            other = b if added == a else a if added == b else None
            if other in now:
                now.remove(other)
                ss["tm_clash_note"] = True
                ss["tm_clash_msg"] = (f"{_bare(added)} and {_bare(other)} pull opposite ways, "
                                      f"so Ziggy kept {_bare(added)}.")
    ss["tm_feel"] = now
    ss["tm_feel_prev"] = now


def _bare(label):
    return re.sub(r"^\W+\s*", "", label)


def demand_view(stores, tz_name):
    """Settings: what customers asked Strain Sniffer for, by store, from the
    usage log: strains looked up, feels and flavors picked, products they like."""
    import collections
    import datetime as _dt
    from zoneinfo import ZoneInfo
    import pandas as pd
    st.markdown('<div class="cat-hdr">👃 What customers ask for</div>', unsafe_allow_html=True)
    db = _deps["db"]()
    if db is None:
        st.warning("No Supabase connection — the usage log lives there.")
        return
    c1, c2 = st.columns(2)
    days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}
    period = c1.segmented_control("Period", list(days), default="Last 30 days", key="tm_dem_period") \
        or "Last 30 days"
    where = c2.selectbox("Store", ["All stores"] + list(stores), key="tm_dem_store")
    since = _dt.datetime.now(ZoneInfo(tz_name)) - _dt.timedelta(days=days[period])
    rows, start = [], 0
    try:
        while True:
            page = (db.table("ziggy_usage").select("store,tool,detail")
                    .in_("tool", ["Strain Sniffer", "Strain lookup"]).eq("action", "used")
                    .gte("at", since.isoformat()).range(start, start + 999).execute().data or [])
            rows += page
            if len(page) < 1000:
                break
            start += 1000
    except Exception as e:                                   # noqa: BLE001
        st.error(f"Couldn't read the usage log. (`{e}`)")
        return
    if where != "All stores":
        rows = [r for r in rows if r.get("store") == where]
    strains, feels, likes = collections.Counter(), collections.Counter(), collections.Counter()
    for r in rows:
        d = str(r.get("detail") or "")
        if d.startswith("Searched "):
            strains[d[9:].strip().title()] += 1
        elif d.startswith("Feel: "):
            for w in d[6:].split(","):
                if w.strip():
                    feels[w.strip()] += 1
        elif d.startswith("Like: "):
            likes[d[6:].strip()] += 1
    if not (strains or feels or likes):
        st.info(f"No Strain Sniffer searches in the {period.lower()} yet.")
        return
    st.caption(f"{len(rows):,} searches · {'all stores' if where == 'All stores' else where}. Use it for buying: "
               f"what people ask for that we don't carry, and the feels and flavors in demand.")
    a, b, c = st.columns(3)
    for col, title, counter, label in ((a, "Strains looked up", strains, "Strain"),
                                       (b, "Feels & flavors picked", feels, "Feel or flavor"),
                                       (c, "Products they like", likes, "Product")):
        col.markdown(f"**{title}**")
        if counter:
            col.dataframe(pd.DataFrame(counter.most_common(15), columns=[label, "Times"]),
                          hide_index=True, width="stretch")
        else:
            col.caption("None yet.")


def type_check_view(stores, brand_check):
    """Settings: products whose strain type needs fixing in Dutchie: none at
    all, or the opposite of every other brand's (indica vs sativa). A product
    can be checked against its brand's own site, one at a time."""
    import pandas as pd
    st.markdown('<div class="cat-hdr">🧬 Strain type check</div>', unsafe_allow_html=True)
    st.caption("Fix these in Dutchie Backoffice: the type sets the shelf tag colour, the online "
               "menu and Strain Sniffer's matching. Products without a strain (accessories, most "
               "edibles) are left out.")
    db = _deps["db"]()
    usual = strain_types(tuple(stores))
    missing, clash = {}, {}
    for store in stores:
        got = live_stock.latest(db, store)
        if not got:
            continue
        rows = _deps["build_rows"](got[0])
        strain_of = {r["product"]: (strain_name(r["product"], r["strain"]),
                                    _norm_strain(strain_name(r["product"], r["strain"]))) for r in rows}
        for rec in got[0].to_dict("records"):
            name = str(rec.get("Product", "")).strip('="').strip()
            strain, key = strain_of.get(name, ("", ""))
            if not key or not group_of(rec.get("Category")):
                continue
            t = dutchie_type(rec.get("Strain"))
            if not t:
                missing.setdefault(name, {"Product": name, "Category": rec.get("Category"), "Stores": set(),
                                          "_strain": strain.title()})
                missing[name]["Stores"].add(store)
            elif usual.get(key) and {t, usual[key]} == {"indica", "sativa"}:
                clash.setdefault(name, {"Product": name, "In Dutchie": t.title(),
                                        "Most of this strain": usual[key].title(), "Stores": set(),
                                        "_strain": strain.title()})
                clash[name]["Stores"].add(store)
    a, b = st.columns(2)
    a.metric("No type in Dutchie", f"{len(missing):,}")
    b.metric("Opposite of the usual type", f"{len(clash):,}")
    where = st.selectbox("Store", ["All stores"] + list(stores), key="tm_tc_store")

    def table(d):
        out = [dict(v, Stores=", ".join(sorted(v["Stores"]))) for v in d.values()
               if where == "All stores" or where in v["Stores"]]
        return pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in out])
    t1, t2 = st.tabs([f"No type ({len(missing):,})", f"Opposite type ({len(clash):,})"])
    with t1:
        df = table(missing)
        st.dataframe(df, hide_index=True, width="stretch") if len(df) else st.caption("None.")
    with t2:
        df = table(clash)
        st.dataframe(df, hide_index=True, width="stretch") if len(df) else st.caption("None.")
    st.markdown("**Check one against its brand's own site**")
    pool = sorted(set(missing) | set(clash))
    pick = st.selectbox("Product", pool, index=None, placeholder="Pick a product from the lists above…",
                        key="tm_tc_pick", label_visibility="collapsed")
    if pick and st.button("🔎 Check the brand's site", key="tm_tc_go"):
        strain = (clash.get(pick) or missing.get(pick))["_strain"]
        with st.spinner(f"Searching {brand_of(pick)}'s pages for {strain}… up to a minute"):
            bt, src, common = brand_check(strain, brand_of(pick))
        if bt:
            if src.startswith("http"):
                from urllib.parse import urlparse
                host = urlparse(src).netloc.replace("www.", "")
                src = f"[{'Google result' if 'vertexaisearch' in host or not host else host}]({src})"
            now = str(clash.get(pick, {}).get("In Dutchie", "")).lower()
            st.success(f"{brand_of(pick)} lists {strain} as **{bt.title()}**"
                       + (f" ({src})" if src else "")
                       + (". Dutchie already matches: this brand's version just differs from the usual."
                          if now == bt else ". Enter that in Dutchie."))
        else:
            st.warning(f"{brand_of(pick)}'s own type for {strain} wasn't found. Check the package or COA"
                       + (f"; strain databases say {common.title()}." if common else "."))


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
        library, brands = lab_library(tuple(stores)), brand_library(tuple(stores))
        names = sorted(p["name"] for p in prods if profile(p, library, brands)[0])
        pick = st.selectbox("A product we have that they like", names, index=None,
                            placeholder="Type to search our products…", key="tm_like")
        if not pick:
            st.caption("Pick a product to find others with the closest terpene mix. "
                       "The list is what's in stock here now.")
            return
        p = next(x for x in prods if x["name"] == pick)
        m, src = profile(p, library, brands)
        st.markdown(_bars(m), unsafe_allow_html=True)
        if src != "lab":
            st.caption({"brand lab": "This product has no terpene test of its own, so this is "
                                     f"{brand_of(pick)}'s test of the same strain.",
                        "strain lab": "This product has no terpene test of its own, so this is "
                                      "another brand's test of the same strain. Matches can only "
                                      "be rough.",
                        "estimated": "No lab test of this strain anywhere, so this mix is an "
                                     "estimate. Matches can only be rough."}[src])
        results(m, "tm_like", like=p["strain"].title() or pick, exclude=lambda x: x["name"] == pick,
                stores=stores, store=store, ttype=p["dtype"],
                shelf_from={"product": pick}, infused=p["infused"], base=pick,
                best=BEST_BAND[src],
                ref=f'{pick} ({p["dtype"] or "type not listed"}; top terpenes '
                    + ", ".join(top(m)) + ")")
        return
    feel = st.pills("Feel they're after", list(FEELS), selection_mode="multi", key="tm_feel",
                    on_change=_no_clash)
    if st.session_state.pop("tm_clash_note", None):
        st.toast(st.session_state.pop("tm_clash_msg", ""), icon=":material/swap_horiz:")
    flav = st.pills("Flavors they like", list(FLAVORS), selection_mode="multi", key="tm_flav")
    picked = list(feel or []) + list(flav or [])
    if not picked:
        st.caption("Pick a feel, a flavor, or both. These are what customers commonly report, "
                   "not medical advice.")
        return
    words = ", ".join(re.sub(r"^\W+\s*", "", w) for w in picked)
    results(picker_target(picked), "tm_pick", stores=stores, store=store, infused=True,
            how="lean", ref=f"a feel and flavor: {words}")
