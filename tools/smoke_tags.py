"""Headless build check: every tag builder, both sizes, mix on/off, deals on/off.

    python tools/smoke_tags.py

Builds each combination and reports page count and byte size, so a change to
the deal rules or the templates cannot silently stop a sheet building. Needs
pdftk and poppler (see README) and a weekly deals CSV in ~/Downloads.
"""
import os, sys, tempfile
sys.path.insert(0, "/Users/chadhunter/Gap-Analysis")
os.chdir("/Users/chadhunter/Gap-Analysis")

import deals as deals_mod, preroll_tags as pt, combine_tags as ct, build_dual
from pypdf import PdfReader
import io

SHEET = "/Users/chadhunter/Downloads/9-21-26 Weekly Deals-Smilez(Sheet1).csv"
DEALS = deals_mod.load(open(SHEET, "rb").read())

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

print("\n".join(results))
if failures:
    print("\n--- FAILURES ---")
    print("\n".join(failures))
print(f"\n{len(results)} passed, {len(failures)} failed")
