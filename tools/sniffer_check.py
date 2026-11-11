"""Check Strain Sniffer's matching against today's lab data. Run from the repo root:

    python tools/sniffer_check.py

Reads every store's live stock the way the app does (Supabase, from
.streamlit/secrets.toml) and prints:

  1. How often each label ("Very close", "Close"...) is given to two products
     picked at random, to two packages of the same product, and to the same
     strain from the same brand or from another brand. A label is only worth
     showing if random pairs rarely earn it and the same product nearly always
     does.
  2. Whether the average mix and the spread the score is built on
     (terp_match.TYPICAL and SPREAD) still fit the shelves.
  3. The known pairs below: strains staff say are alike or nothing alike, and
     what the lab score says about them. A miss here doesn't fail the check; it
     shows where lab terpenes alone can't tell two strains apart, which is what
     the AI double-check and (later) repeat-purchase data are for.
  4. Strain names that look wrong (a brand read as a strain).

Run it after any change to terp_match's scoring. It exits 1 when the labels no
longer mean what terp_match.CLOSE_AT says they do.
"""
import ast
import collections
import itertools
import math
import os
import pathlib
import random
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

# (strain, strain, "alike" or "apart", who said so). Add to this list whenever
# a budtender or customer says a match was wrong, or spot on.
KNOWN = [
    ("Runtz", "Orange Tree", "apart", "Chad, Nov 9 2026: very different terpenes and effect"),
]

STORES = ["Allegan", "Burton", "Corunna", "Quincy", "Reading", "Sturgis", "Three Rivers", "Wayne"]


def app_function(name):
    """One function out of app.py, which can't be imported outside Streamlit."""
    import preroll_tags
    tree = ast.parse((REPO / "app.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    space = {"re": re, "preroll_tags": preroll_tags}
    exec(compile(ast.Module([node], []), "app.py", "exec"), space)
    return space[name]


def connect():
    import tomllib
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    if not (url and key):
        sec = tomllib.loads((REPO / ".streamlit/secrets.toml").read_text())
        url, key = sec["SUPABASE_URL"], sec["SUPABASE_KEY"]
    from supabase import create_client
    return create_client(url, key)


def share(values, test):
    return sum(1 for v in values if test(v)) / len(values) if values else 0.0


def main():
    import logging
    logging.disable(logging.WARNING)             # Streamlit's "no runtime" notes
    import live_stock
    import terp_match as tm
    db = connect()
    tm.configure(build_rows=app_function("build_tag_rows"), fix_prices=lambda rows: 0,
                 groq_key=None, groq_model=None, db=lambda: db)

    # Every tested product at every store, with each package's own mix.
    tested, everything = {}, {}
    for store in STORES:
        got = live_stock.latest(db, store)
        if not got:
            print(f"  ! no live stock for {store}")
            continue
        df = got[0]
        packages = {}
        for rec in df.to_dict("records"):
            name = str(rec.get("Product", "")).strip('="').strip()
            raw = tm.parse_lab(rec.get("Terpenes"))
            if raw:
                packages.setdefault(name, {})[rec.get("Package ID")] = tm.mix(raw)
        for p in tm.products(df, []):
            everything.setdefault(p["name"], p)
            if p["name"] in packages and p["skey"]:
                t = tested.setdefault(p["name"], dict(p, packs={}))
                t["packs"].update(packages[p["name"]])
    for t in tested.values():
        t["m"] = tm.average(list(t["packs"].values()))
    natural = [t for t in tested.values() if t["kind"] == "natural"]
    if len(natural) < 200:
        print(f"Only {len(natural)} lab-tested products found: not enough to check against.")
        return 1

    by_strain = collections.defaultdict(list)
    for t in natural:
        by_strain[t["skey"]].append(t)
    random.seed(11)
    rand = []
    while len(rand) < 20000:
        a, b = random.sample(natural, 2)
        if a["skey"] != b["skey"]:
            rand.append(tm.similarity(a["m"], b["m"]))
    packs = [tm.similarity(a, b) for t in natural if len(t["packs"]) > 1
             for a, b in itertools.combinations(list(t["packs"].values())[:5], 2)]
    same_brand = [tm.similarity(a["m"], b["m"]) for ps in by_strain.values()
                  for a, b in itertools.combinations(ps, 2) if a["brand"] == b["brand"]]
    other_brand = [tm.similarity(a["m"], b["m"]) for ps in by_strain.values()
                   for a, b in itertools.combinations(ps, 2) if a["brand"] != b["brand"]]

    print(f"\n1. What the labels mean today ({len(natural):,} lab-tested flower, pre-roll and "
          f"live concentrate products, {len(by_strain):,} strains)\n")
    print(f"   {'':38s}" + "".join(f"{x:>14s}" for x in reversed(tm.LABELS)))
    rows = (("Two products picked at random", rand), ("Two packages of the same product", packs),
            ("Same strain, same brand", same_brand), ("Same strain, another brand", other_brand))
    for title, vals in rows:
        bands = collections.Counter(tm.band_of(v) for v in vals)
        print(f"   {title:38s}" + "".join(f"{bands[i] / max(len(vals), 1):>14.0%}"
                                          for i in range(len(tm.LABELS) - 1, -1, -1))
              + f"   ({len(vals):,} pairs)")
    close = lambda v: tm.band_of(v) >= 3
    problems = []
    if share(rand, lambda v: tm.band_of(v) == 4) > 0.06:
        problems.append("more than 6% of random pairs come out Very close")
    if share(rand, close) > 0.15:
        problems.append("more than 15% of random pairs come out Close or better")
    if share(packs, close) < 0.85:
        problems.append("under 85% of same-product packages come out Close or better")

    print("\n2. The average mix the score is built on (terp_match.TYPICAL / SPREAD vs today)\n")
    for t in tm.TERPS:
        vals = [p["m"].get(t, 0) for p in natural]
        mean = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        off = abs(mean - tm.TYPICAL[t]) > 0.03 or abs(max(sd, 0.02) - tm.SPREAD[t]) > 0.03
        print(f"   {t:14s} average {mean:5.1%} (set {tm.TYPICAL[t]:5.1%})   spread {sd:5.1%} "
              f"(set {tm.SPREAD[t]:5.1%}){'   <- has moved, update terp_match' if off else ''}")
        if off:
            problems.append(f"{t}'s average or spread has moved")

    print("\n3. Known pairs (lab score only, before the AI double-check)\n")
    library = {k: tm.average([p["m"] for p in ps]) for k, ps in by_strain.items()}
    for a, b, want, who in KNOWN:
        ka, kb = tm._norm_strain(a), tm._norm_strain(b)
        if ka not in library or kb not in library:
            missing = a if ka not in library else b
            print(f"   -  {a} vs {b}: no lab-tested {missing} on the shelves today")
            continue
        band = tm.band_of(tm.similarity(library[ka], library[kb]))
        ok = band <= 1 if want == "apart" else band >= 3
        print(f"   {'ok' if ok else 'MISS'}  {a} vs {b}: {tm.LABELS[band]} (should be {want}; {who})")
        for k, name in ((ka, a), (kb, b)):
            lead = ", ".join(f"{t} {library[k][t]:.0%}" for t in tm.top(library[k], 4))
            print(f"         {name}: {lead}  ({len(by_strain[k])} tested products)")

    print("\n4. Strain names\n")
    bad = collections.Counter(p["skey"] for p in everything.values()
                              if p["skey"] and p["skey"] == tm._norm_strain(tm.brand_of(p["name"])))
    if bad:
        print("   Products whose strain came out as their own brand: "
              + ", ".join(f"{k} ({n})" for k, n in bad.most_common(10)))
    else:
        print("   No product's brand is being read as its strain.")
    src = collections.Counter()
    lib, per_brand = tm.lab_library(tuple(STORES)), tm.brand_library(tuple(STORES))
    for p in everything.values():
        if not p["skey"]:
            src["no strain in the name"] += 1
        elif p["labs"]:
            src["its own lab test"] += 1
        elif (p["skey"], p["brand"], p["kind"]) in per_brand:
            src["its brand's test of the strain"] += 1
        elif p["skey"] in lib:
            src["another brand's test of the strain"] += 1
        else:
            src["no test anywhere (AI estimate)"] += 1
    print(f"   Where each of the {len(everything):,} products gets its terpene mix:")
    for k, n in src.most_common():
        print(f"     {n:5,d}  {n / len(everything):4.0%}  {k}")

    print()
    if problems:
        print("NEEDS A LOOK: " + "; ".join(problems) + ".")
        return 1
    print("Labels check out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
