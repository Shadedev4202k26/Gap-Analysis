"""Aged stock, one Metrc package at a time.

The Aging stock page used to list one line per product name, summing every
package's units and showing the oldest package's age. On 2026-10-27 that made
"Seed Junky | Red Eye | 1G Preroll" read 397 days, 169 units — when one unit
was 397 days old, one was 183, fourteen were 82 and the other 153 had arrived
within the month. So this works per package: the Dutchie export's Package ID is
the Metrc tag, and its Inventory date is the day the store received it.

A package moved between rooms keeps its tag, so its rows are combined into one
line. Both the Aging stock page and the Home card read from here.
"""
import datetime
from collections import defaultdict

WATCH_DAYS = 45
EXP_SOON_DAYS = 60


def _clean(v):
    s = str(v if v is not None else "").strip('="').strip()
    return "" if s.lower() == "nan" else s


def _date(v):
    s = _clean(v)
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _units(v):
    digits = "".join(ch for ch in _clean(v) if ch.isdigit() or ch == ".")
    try:
        return float(digits) if digits else 0.0
    except ValueError:
        return 0.0


def _col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None


def is_bulk(product):
    """Loose deli flower ("BULK | brand | strain"): its Available is grams."""
    return str(product).strip().upper().startswith("BULK")


def qty_text(p):
    """Units as a count, or grams for bulk — never mixed in one number."""
    q = p["qty"]
    if p["unit"] == "g":
        return f"{q:,.2f} g".replace(".00 g", " g")
    return f"{q:,}"


def packages(df, today=None):
    """Every package in the export: [{tag, product, received, dated_by, age,
    qty, unit, rooms, cat, vendor, price, on_sale, days_to_exp, newer_units}].

    `unit` is "g" for bulk flower, whose Available is a weight, and "" for
    everything else. The old page stripped the decimal point, so 113.57 g of
    bulk read as 11,357 units.

    `dated_by` says which date the age counts from: "Received" (Inventory
    date) normally, "Packaged" only when an export has no Inventory date.
    `newer_units` is how many units of the same product sit in packages under
    WATCH_DAYS old — context for whether the product is still selling.
    Returns (packages, error) where error explains a missing column.
    """
    today = today or datetime.date.today()
    df = df.copy()
    df.columns = [str(c).strip('="').strip() for c in df.columns]
    c_tag = _col(df, "Package ID", "External package ID")
    c_product = _col(df, "Product", "Online title")
    c_received = _col(df, "Inventory date")
    c_packaged = _col(df, "Packaging date")
    if not c_product or not (c_received or c_packaged):
        return [], ("This export is missing Product or Inventory date. "
                    "Re-export with those columns included.")
    c_qty = _col(df, "Available", "Quantity (including allocated)")
    c_room, c_exp = _col(df, "Room"), _col(df, "Expiration date")
    c_cat = _col(df, "Category", "Master category")
    c_vendor = _col(df, "Brand", "Vendor")
    c_price = _col(df, "Current price", "Price (Catalog)")
    c_sale = _col(df, "Is on sale")

    by_tag = {}
    for i, row in enumerate(df.to_dict("records")):
        product = _clean(row.get(c_product))
        if not product:
            continue
        got, dated_by = (_date(row.get(c_received)) if c_received else None), "Received"
        if got is None and c_packaged:
            got, dated_by = _date(row.get(c_packaged)), "Packaged"
        if got is None:
            continue
        tag = _clean(row.get(c_tag)) if c_tag else ""
        key = tag or f"row{i}"
        exp = _date(row.get(c_exp)) if c_exp else None
        p = by_tag.get(key)
        if p is None:
            p = by_tag[key] = {
                "tag": tag, "product": product, "received": got, "dated_by": dated_by,
                "unit": "g" if is_bulk(product) else "",
                "age": (today - got).days, "qty": 0.0, "rooms": set(),
                "cat": _clean(row.get(c_cat)) if c_cat else "",
                "vendor": _clean(row.get(c_vendor)) if c_vendor else "",
                "price": _clean(row.get(c_price)) if c_price else "",
                "on_sale": False, "days_to_exp": None}
        p["qty"] += _units(row.get(c_qty)) if c_qty else 0
        room = _clean(row.get(c_room)) if c_room else ""
        if room:
            p["rooms"].add(room)
        if c_sale and _clean(row.get(c_sale)).lower() in ("yes", "true", "1"):
            p["on_sale"] = True
        if exp is not None:
            d = (exp - today).days
            p["days_to_exp"] = d if p["days_to_exp"] is None else min(p["days_to_exp"], d)

    out = list(by_tag.values())
    fresh = defaultdict(float)
    for p in out:
        if p["age"] < WATCH_DAYS:
            fresh[p["product"]] += p["qty"]
    for p in out:
        p["qty"] = int(p["qty"]) if float(p["qty"]).is_integer() else round(p["qty"], 2)
        p["newer_units"] = fresh.get(p["product"], 0)
    return out, None


def watch_list(pkgs):
    """Packages WATCH_DAYS or older, grouped by category: [(category, [pkg])],
    oldest category first and oldest package first within each."""
    by_cat = defaultdict(list)
    for p in pkgs:
        if p["age"] >= WATCH_DAYS:
            by_cat[p["cat"] or "Uncategorized"].append(p)
    groups = [(c, sorted(ps, key=lambda p: -p["age"])) for c, ps in by_cat.items()]
    return sorted(groups, key=lambda g: -g[1][0]["age"])


def short_tag(tag):
    """The end of a Metrc tag, which is what staff match on the label."""
    return f"…{tag[-8:]}" if len(tag) > 10 else tag


def totals(pkgs):
    """(units, grams) across packages: counted items and bulk weight apart."""
    units = sum(p["qty"] for p in pkgs if p["unit"] != "g")
    grams = round(sum(p["qty"] for p in pkgs if p["unit"] == "g"), 2)
    return (int(units) if float(units).is_integer() else round(units, 2)), grams
