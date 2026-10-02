"""Headless build check: every tag builder, both sizes, mix on/off, deals on/off.

    python tools/smoke_tags.py

Builds each combination and reports page count and byte size, so a change to
the deal rules or the templates cannot silently stop a sheet building. Then
checks a few tags that have printed the wrong deal before. Needs pdftk and
poppler (see README) and the 9/28 weekly deals CSV in ~/Downloads.
"""
import os
import sys, sys, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

import deals as deals_mod, preroll_tags as pt, combine_tags as ct, build_dual
from pypdf import PdfReader
import io

# Pass a deals sheet as the first argument, or set ZIGGY_DEALS_SHEET. The
# fallback is only a convenience for whoever exported one to Downloads today.
SHEET = (sys.argv[1] if len(sys.argv) > 1
         else os.environ.get("ZIGGY_DEALS_SHEET")
         or os.path.expanduser("~/Downloads/9-28-26 Weekly Deals-Smilez(Sheet1)-3.csv"))
# Loaded the way the app loads it. deals.load() flattens the sheet and loses the
# section each deal sits under, so it cannot see a preroll deal land on flower.
DEALS = deals_mod.load_sheet(open(SHEET, "rb").read(), os.path.basename(SHEET)).deals("Allegan")

ROWS = [
    {"brand": "Goldkine",        "strain": "OG Kush",      "thc": "28.4%", "price": "$14", "type": "sativa"},
    {"brand": "Giving Tree",     "strain": "Blue Dream",   "thc": "24.1%", "price": "$12", "type": "hybrid"},
    {"brand": "Common Citizens", "strain": "Granddaddy P", "thc": "31.0%", "price": "$10", "type": "indica"},
    {"brand": "Stay High",       "strain": "Sour Diesel",  "thc": "22.7%", "price": "$15", "type": "sativa"},
    {"brand": "Hi Cannabis",     "strain": "Wedding Cake", "thc": "26.3%", "price": "$13", "type": "indica"},
    {"brand": "Mitten",          "strain": "Gelato 41",    "thc": "29.8%", "price": "$11", "type": "hybrid"},
]
for r in ROWS:
    r["size"] = "3.5G"

TEMPLATES = {"sativa": "Sativa_Prerolls.pdf", "hybrid": "Hybrid_Prerolls.pdf", "indica": "Indica_Prerolls.pdf"}
WIDE      = {"sativa": "Sativa_Prerolls_4in.pdf", "hybrid": "Hybrid_Prerolls_4in.pdf", "indica": "Indica_Prerolls_4in.pdf"}
HOOK      = {"sativa": "Sativa_Hook.pdf", "hybrid": "Hybrid_Hook.pdf", "indica": "Indica_Hook.pdf"}

def rows(with_deals):
    out = [dict(r) for r in ROWS]
    if with_deals:
        deals_mod.attach(out, DEALS)
    return out

def pages(b):
    return len(PdfReader(io.BytesIO(b)).pages) if b else 0

def group(rs):
    g = {}
    for r in rs:
        g.setdefault(r.get("type", "hybrid"), []).append(r)
    return g

results, failures = [], []
for with_deals in (False, True):
    tag = "deals" if with_deals else "no-deals"
    rs = rows(with_deals)
    n_deals = sum(1 for r in rs if r.get("deal"))
    for label, tpls in (("hook", HOOK), ("3.5in", TEMPLATES), ("4in", WIDE)):
        for mix in (False, True):
            name = f"{label:6s} mix={str(mix):5s} {tag:8s}"
            try:
                with tempfile.TemporaryDirectory() as td:
                    if mix:
                        b = ct.build_combined(tpls, rs, td, 1)
                    else:
                        b = pt.build_separate(tpls, group(rs), td)
                results.append(f"  OK   {name}  pages={pages(b):2d}  bytes={len(b):7d}  deals_on_rows={n_deals}")
            except Exception as e:
                failures.append(f"  FAIL {name}  {type(e).__name__}: {e}")
    for size in ("3.5", "4"):
        name = f"dual {size:4s}            {tag:8s}"
        try:
            with tempfile.TemporaryDirectory() as td:
                b = build_dual.build_sheet(rs, td, size=size)
            results.append(f"  OK   {name}  pages={pages(b):2d}  bytes={len(b):7d}  deals_on_rows={n_deals}")
        except Exception as e:
            failures.append(f"  FAIL {name}  {type(e).__name__}: {e}")

# Tags that printed the wrong deal on 2026-09-25 (HookTags_Ready-11.pdf): the
# edibles deal from a strain called "Orange Gummi", and preroll deals on flower
# from brands that also make prerolls. (product, category, expected badge text)
KNOWN = [
    ("Grown Rogue | Orange Gummi | 3.5G Bag", "Prepacked Flower Brands", "BUY 5 15% OFF"),
    ("Goldkine | Biscotti Pancakes | 28G",    "Prepacked Flower Brands", None),
    ("Glacier | Heavy Z | 3.5G Bag",          "Prepacked Flower Brands", "BUY 5 15% OFF"),
    ("Common Citizen | Lemon Bar Smalls | 3.5G", "-RED TIER",            "RED"),
    # 2026-10-02: the sheet's Non Infused / Infused and 510 / Disposable sections
    # were one family each, so a deal crossed into the other half of the brand.
    ("Dragonfly | Zoap | 1G Preroll",              "PreRoll",
     "10/$7.50 OR 70/$49 Dragonfly"),
    ("Dragonfly | Zoap | 1.25G Infused Preroll",   "Infused PreRoll",   "BUY 5 15% OFF"),
    ("Superfire | Super Maui | 1G Disposable Vape", "Vape Carts Disposable Distillate",
     "BUY 10G 15% OFF"),
    # Vape Carts (MISC) mixes forms: its carts take either cart section's deals,
    # its disposables only the disposable section's.
    ("Platinum Vape | GMO | 1G FS Live Resin Cart", "Vape Carts (MISC)",
     "3/$16 Amnesia OR Platinum Vape 1G"),
    ("Church | Skywalker OG | 1G Liquid Diamond Cart", "Vape Carts (MISC)",
     "50% OFF ALL Church"),
    ("No Bad Days | Gas Berry | 1G Live Resin Disposable Vape", "Vape Carts (MISC)",
     "$10 Packs OR No Bad Days 1g Live Resin Disposables"),
]
for product, category, want in KNOWN:
    brand, strain = [p.strip() for p in product.split("|")][:2]
    r = {"brand": brand.upper(), "strain": strain.upper(), "product": product,
         "category": category, "price": "$20"}
    deals_mod.attach([r], DEALS)
    deals_mod.attach_bulk([r])
    deals_mod.attach_shelf([r])
    d = r.get("deal") or {}
    got = r.get("deal_text") or " ".join(d.get("tiers", [])) or d.get("badge")
    name = f"deal {strain[:24]:24s}"
    if got == want:
        results.append(f"  OK   {name}  {got or 'no badge'}")
    else:
        failures.append(f"  FAIL {name}  got {got or 'no badge'!r}, want {want or 'no badge'!r}")

# 2026-10-02 field report. Custom tags carry no category: on the Preroll page a
# typed "MAGIC" tag is a preroll; on a page that takes anything, a tag saying
# nothing about what it is takes no weekly deal rather than a guessed one (it
# printed Magic's 5/$22 cart deal). And "(Excludes Ratio)" must hold.
PRE = sorted(deals_mod.PREROLLS)
CUSTOM = [
    # Allegan has no Magic preroll line, so: never the cart deal.
    ("custom MAGIC, Preroll page", {"brand": "MAGIC", "strain": "X", "family_hint": PRE}, None),
    ("custom MAGIC, Hook page",    {"brand": "MAGIC", "strain": "X"}, None),
    ("The 8th CBN ratio gummy",    {"brand": "THE 8TH | 200MG", "strain": "X", "category": "Gummies 200MG",
                                    "product": "The 8th | Twilight Kiwi | 200mg: 100mg CBN Live Resin Gummies"},
     None),
]
for name, r, want in CUSTOM:
    r = dict(r, price="$10")
    d = deals_mod.for_row(r, DEALS)
    got = d.text if d else None
    line = f"deal {name[:24]:24s}"
    (results if got == want else failures).append(
        f"  {'OK  ' if got == want else 'FAIL'} {line}  {got or 'no deal'}"
        + ("" if got == want else f", want {want or 'no deal'!r}"))

# The 10/5 sheet's Brands of the Week: no percentage in the header, one per
# line, dated. They cover every section, and "Oct 1-31" is not part of a brand.
BOTW_LINES = ["Outdoor Bulk Flower-$17.50 OZ", "Brands of the Week  (Excludes Deli Flower)",
              "50% OFF Jungle Juice Oct 1-31", "30% OFF Zooted Oct 5-11", "Prepacked Flower",
              "3/$36 Goldkine 3.5G Bags"]
botw = deals_mod.parse_column(BOTW_LINES)
for product, category, want in [
        ("Jungle Juice | Strawnana | 2G Disposable", "Vape Carts Disposable Distillate",
         "50% OFF Jungle Juice Oct 1-31"),
        ("Zooted | Gushers | 2G Preroll", "PreRoll", "30% OFF Zooted Oct 5-11"),
        ("Goldkine | Biscotti | 3.5G Bag", "Prepacked Flower Brands", "3/$36 Goldkine 3.5G Bags")]:
    r = {"brand": product.split("|")[0].strip().upper(), "product": product,
         "category": category, "price": "$20"}
    d = deals_mod.for_row(r, botw)
    got = d.text if d else None
    line = f"botw {product.split('|')[0].strip()[:24]:24s}"
    (results if got == want else failures).append(
        f"  {'OK  ' if got == want else 'FAIL'} {line}  {got or 'no deal'}"
        + ("" if got == want else f", want {want!r}"))

print("\n".join(results))
if failures:
    print("\n--- FAILURES ---")
    print("\n".join(failures))
print(f"\n{len(results)} passed, {len(failures)} failed")
