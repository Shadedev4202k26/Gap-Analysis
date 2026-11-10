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


# Products whose terpenes are the plant's own. Distillate carts, disposables
# and infused prerolls usually have terpenes added (one Runtz cart tests 90%
# limonene), so they never speak for a strain: Runtz built from them came out
# limonene-heavy and matched Orange Tree, a citrus sativa.
NOT_NATURAL = re.compile(r"infused|distillate|cart|vape|disposable|pod|gumm|edible|beverage|chocolate", re.I)


def natural(category, name):
    return group_of(category) in ("Flower", "Pre-rolls", "Concentrates") \
        and not NOT_NATURAL.search(f"{category} {name}")


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
    """Strain -> its usual type (indica / sativa / hybrid) across our products."""
    return _library(stores)[1]


@st.cache_data(ttl=300, show_spinner=False, max_entries=4)
def _library(stores):
    db = _deps.get("db") and _deps["db"]()
    per, types = {}, {}
    for store in stores:
        got = live_stock.latest(db, store)
        if not got or "Terpenes" not in got[0].columns:
            continue
        df = got[0]
        rows = _deps["build_rows"](df)
        strain_of = {r["product"]: (_norm_strain(r["strain"]), r["type"]) for r in rows}
        for prod, lab, cat in zip(df["Product"], df["Terpenes"], df["Category"]):
            name = str(prod).strip('="').strip()
            s, typ = strain_of.get(name, (None, None))
            if not s:
                continue
            types.setdefault(s, {})[typ] = types.get(s, {}).get(typ, 0) + 1
            m = mix(parse_lab(lab))
            if m and natural(cat, name):
                per.setdefault(s, {})[name] = m          # one vote per product, not per package
    return ({s: average(list(p.values())) for s, p in per.items()},
            {s: max(t, key=t.get) for s, t in types.items()})


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


def rank(target, prods, library, exclude=None, pct=None, ttype=None):
    """Closest first. Within a closeness band: a real lab test before an
    estimate, then the store's better sellers, then the closer mix."""
    pct = pct or {}
    out = []
    for p in prods:
        if exclude and exclude(p):
            continue
        m, src = profile(p, library)
        if not m:
            continue
        s = similarity(target, m) - type_gap(ttype, p["type"])
        band = 3 if s >= 0.95 else 2 if s >= 0.88 else 1 if s >= 0.75 else 0
        out.append(((band, {"lab": 2, "strain lab": 1}.get(src, 0), round(pct.get(p["name"], 0), 1), s),
                    s, p, m, src))
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


def _sold(p, units, days):
    n = units.get(p["name"], 0)
    unit = "g" if p["name"].upper().startswith("BULK") else ""
    return f"⭐ Popular here · {n:,.0f}{unit} sold in {days // 7} weeks"


def _card(s, p, m, src, target, like, photo="", hot="", note=""):
    out_front = any(r in OUT_FRONT for r in p["rooms"])
    where = "Out front" if out_front else "Vault only"
    tag, col = SOURCE[src]
    deal = (f'<div style="margin-top:6px;font-size:12.5px;color:#FCA5A5;font-weight:600">🔥 {_esc(p["deal"])}</div>'
            if p["deal"] else "")
    if hot:
        deal = (f'<div style="margin-top:6px;font-size:12.5px;color:#FDE68A;font-weight:600">{_esc(hot)}</div>'
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
        <div style="white-space:nowrap;color:#22D3EE;font-weight:700">{_esc(closeness(s))}</div></div>
      <div style="font-size:12.5px;color:#D1D5DB;margin-top:3px">{_esc(why(target, m, like))}</div>
      {f'<div style="font-size:12.5px;color:#C4B5FD;margin-top:2px">🤖 {_esc(note)}</div>' if note else ""}
      {_bars(m)}
      <div style="font-size:12px;color:#9CA3AF;margin-top:4px">
        <span style="color:{col}">{tag}</span> · {_esc(p["type"].title())} · THC {_esc(p["thc"] or "—")} ·
        {_esc(p["price"] or "—")} · {where} ({qty} on hand)</div>{deal}</div></div>"""
    # One line, no indents: Markdown reads an indented line after a <style> tag as code.
    return " ".join(line.strip() for line in html.splitlines())


def _day(iso):
    try:
        d = dt.date.fromisoformat(str(iso)[:10])
        return f"{d:%b} {d.day}"
    except ValueError:
        return str(iso or "")


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


def results(target, key, like="", exclude=None, stores=(), store="", ttype=None, ref=""):
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

    c1, c2, c3 = st.columns([2, 2, 2], vertical_alignment="bottom")
    grp = c1.selectbox("Category", [ALL] + [g for g, _ in GROUPS], key=f"{key}_grp")
    cap = c2.select_slider("Price up to", ["Any", "$10", "$20", "$30", "$40", "$50", "$75", "$100"],
                           value="Any", key=f"{key}_cap")
    strength = c3.pills("Potency", POTENCY, selection_mode="multi", key=f"{key}_pot",
                        help="Compared with the rest of its category at this store: a strong "
                             "flower and a strong concentrate are different THC levels.")
    c4, c5, c6 = st.columns(3, vertical_alignment="center")
    front = c4.toggle("Out front only", value=True, key=f"{key}_front")
    deal_only = c5.toggle("On deal", key=f"{key}_deal")
    use_ai = c6.toggle("🤖 AI double-check", value=True, key=f"{key}_ai",
                       help="Groq re-sorts the closest 20 by each strain's lineage and reported "
                            "effects. Off: lab terpenes only.")
    cuts = potency_cuts(prods)
    pool = [p for p in prods
            if (grp == ALL or p["group"] == grp)
            and (not strength or potency_of(p, cuts) in strength)
            and (cap == "Any" or (_price(p) is not None and _price(p) <= float(cap[1:])))
            and (not front or any(r in OUT_FRONT for r in p["rooms"]))
            and (not deal_only or p["deal"])]
    units, through, days = live_stock.popular(db, store)
    pct, hot = sellers(prods, units)
    ranked = rank(target, pool, library, exclude, pct, ttype)
    if not ranked:
        st.caption("Nothing on the shelves matches with these filters. Try All categories or a higher price.")
        return
    if ref:
        _log_ask(ref)
    notes, used = {}, False
    if use_ai:
        with st.spinner("Ziggy is double-checking the picks…"):
            ranked, notes, used = ai_rerank(ref or like, ranked)
    labs = sum(1 for _, _, _, src in ranked[:SHOW] if src != "estimated")
    pics = live_stock.photos(db, store)
    st.caption(f"Closest {min(SHOW, len(ranked))} of {len(ranked)} products · {labs} from lab tests"
               + (f" · {waiting} untested strains still being estimated in the background; "
                  f"they join the list over the next few minutes" if waiting else "")
               + (f" · ⭐ Popular here: {store}'s top sellers in that category, {days // 7} weeks to "
                  f"{_day(through)}" if units else "")
               + (" · 🤖 order double-checked by AI on lineage and reported effects" if used else
                  " · 🤖 AI double-check unavailable right now, lab order shown" if use_ai and ref + like else ""))
    # .sc is the strain card's frame; its "STRAIN.PROFILE" corner label doesn't belong on a match.
    st.markdown("<style>.sc.tm::before{display:none}</style>"
                + "".join(_card(s, p, m, src, target, like, pics.get(p["name"], ""),
                                _sold(p, units, days) if p["name"] in hot else "", notes.get(p["name"], ""))
                          for s, p, m, src in ranked[:SHOW]),
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
    return f'{p["name"]} | {p["type"] or "?"} | ' + ", ".join(f"{t} {m[t]:.0%}" for t in top(m))


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
    got = _ai_order(ref, tuple(_ai_line(p, m) for _, p, m, _ in head), key, model)
    if not got:
        return ranked, {}, False
    order = [head[i] for i, _ in got]
    notes = {head[i][1]["name"]: n for i, n in got if n}
    order += [x for x in head if x not in order]
    return order + ranked[AI_POOL:], notes, True


def strain_target(strain, profile_terps, stores, classification=""):
    """(mix, source, type) to match a searched strain: our own lab tests of its
    flower, pre-rolls and live concentrates when any store has them, else the
    terpenes from its online profile. Type: what we sell it as, else the
    profile's classification."""
    lib = lab_library(tuple(stores))
    k = _norm_strain(strain)
    typ = strain_types(tuple(stores)).get(k) or next(
        (t for t in ("indica", "sativa", "hybrid") if t in str(classification).lower()), None)
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
        results(m, "tm_like", like=p["strain"].title() or pick, exclude=lambda x: x["name"] == pick,
                stores=stores, store=store, ttype=p["type"],
                ref=f'{pick} ({p["type"] or "type unknown"}; top terpenes '
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
    results(picker_target(picked), "tm_pick", stores=stores, store=store,
            ref=f"a feel and flavor: {words}")
