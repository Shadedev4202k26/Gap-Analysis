#!/usr/bin/env python3
"""Read the weekly deals sheet and match its deals to imported products.

The sheet is a spreadsheet export: one deal per row, repeated across a column per
store, padded with empty columns. Lines come in a handful of shapes:

    3/$55 Jungle Juice OR Zooted 2G Disposables      multi-unit
    10/$7.50 OR 70/$49 Dragonfly                     two price tiers
    $16 Packs 2g Live Resin Disposables              fixed unit price
    40% OFF Zaaz                                     percent off
    Presidential BOGO                                buy one get one
    Mitten Extracts 15/$100                          multi-unit, price last

Section headers, shelf pricing, daily deals and customer discounts are ignored —
they are not per-product and do not belong on a tag.
"""
import csv
import io
import re

# Lines that are never a product deal, however they are worded.
SKIP = re.compile(
    r"shelf|\bOZ\b|1/8|buy\s+\d+\s*g?\s+get|daily deal|monday|tuesday|wednesday"
    r"|thursday|friday|saturday|sunday|referral|birthday|vet/|senior|new customer"
    r"|free edib|happy hour|stackable|brands of the week|excludes deli", re.I)
ENDED = re.compile(r"\bended\b", re.I)

# Words that trail the brand and are not part of its name.
NOISE = re.compile(
    r"\b(disposables?|dispos|gummies|gummy|prerolls?|pre-?rolls?|carts?|cartridges?"
    r"|bags?|buckets?|live\s+resin|hash\s+rosin|rosin|resin|infused|indoor|outdoor"
    r"|flower|shake|extracts?|classics?\s+only|burst|xl|switch|lqd|only)\b", re.I)
SIZE = re.compile(r"(?<![a-z0-9.])(\d*\.?\d+)\s*(g|mg|oz|pk)\b", re.I)
PAREN = re.compile(r"\([^)]*\)")
DATES = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")

MULTI = re.compile(r"(\d+)\s*/\s*\$\s*(\d+(?:\.\d{1,2})?)")
FIXED = re.compile(r"^\s*\$\s*(\d+(?:\.\d{1,2})?)\b")
PCT = re.compile(r"(\d{1,2})\s*%\s*off", re.I)
BOGO = re.compile(r"\bbogo\b|buy\s+one\s+get\s+one", re.I)


class Deal:
    def __init__(self, text, kind, badge, brands, size, tiers=None, pct=None, unit=None):
        self.text, self.kind, self.badge = text, kind, badge
        self.brands, self.size = brands, size
        self.tiers, self.pct, self.unit = tiers or [], pct, unit

    def as_badge(self, row_price=None):
        """The deal dict `sale_badges.draw_deal` expects."""
        d = {}
        if self.tiers:
            d["tiers"] = self.tiers
        elif self.badge:
            d["badge"] = self.badge
        was = _money(row_price)
        if self.pct and was is not None:
            d["was"], d["now"] = _fmt(was), _fmt(round(was * (100 - self.pct) / 100.0, 2))
        elif self.unit is not None and was is not None and self.unit < was:
            d["was"], d["now"] = _fmt(was), _fmt(self.unit)
        return d

    def __repr__(self):
        return f"<{self.kind} {self.badge!r} brands={self.brands} size={self.size}>"


def _money(text):
    m = re.search(r"(\d+(?:\.\d{1,2})?)", str(text or ""))
    return float(m.group(1)) if m else None


def _fmt(v):
    return f"${v:.2f}" if v % 1 else f"${int(v)}"


def _brands_and_size(rest):
    """Pull brand names and a pack size out of the text left after the price."""
    size = None
    m = SIZE.search(rest)
    if m:
        num = m.group(1).rstrip(".")
        size = f"{num}{m.group(2).upper()}"
    txt = PAREN.sub(" ", rest)
    txt = DATES.sub(" ", txt)
    txt = SIZE.sub(" ", txt)
    txt = NOISE.sub(" ", txt)
    txt = re.sub(r"\ball\b", " ", txt, flags=re.I)
    parts = re.split(r"\s+or\s+|\s*&\s*|\s*,\s*", txt, flags=re.I)
    stop = {"to", "x", "non", "only", "and", "the", "get", "buy", "all", "select"}
    brands = []
    for p in parts:
        p = re.sub(r"[^A-Za-z0-9'’\s-]", " ", p)
        words = [w for w in p.split() if w.lower() not in stop and not w.isdigit()]
        p = " ".join(words).strip(" -")
        if len(p) >= 2:
            brands.append(p)
    return brands, size


def parse_line(line):
    """One sheet line -> Deal, or None when it is not a per-product deal."""
    text = re.sub(r"\s{2,}", " ", str(line or "")).strip()
    if len(text) < 4 or SKIP.search(text) or ENDED.search(text):
        return None

    tiers = [f"{q}/${p}" for q, p in MULTI.findall(text)]
    if tiers:
        rest = MULTI.sub(" ", text)
        rest = re.sub(r"^\s*(?:or|and)\s+|\s+(?:or|and)\s+(?=\s*$)", " ", rest, flags=re.I)
        brands, size = _brands_and_size(rest)
        return Deal(text, "multi", tiers[0], brands, size,
                    tiers=tiers if len(tiers) > 1 else None)

    m = PCT.search(text)
    if m:
        pct = int(m.group(1))
        brands, size = _brands_and_size(PCT.sub(" ", text))
        return Deal(text, "pct", f"{pct}% OFF", brands, size, pct=pct)

    if BOGO.search(text):
        brands, size = _brands_and_size(BOGO.sub(" ", text))
        return Deal(text, "bogo", "BOGO", brands, size)

    m = FIXED.match(text)
    if m:
        unit = float(m.group(1))
        brands, size = _brands_and_size(text[m.end():])
        return Deal(text, "fixed", "SALE", brands, size, unit=unit)
    return None


def load(file_or_bytes):
    """Read a deals sheet (CSV or XLSX) -> list of Deal, de-duplicated."""
    data = file_or_bytes.read() if hasattr(file_or_bytes, "read") else file_or_bytes
    lines = []
    if data[:2] == b"PK":                                    # xlsx
        import pandas as pd
        for sheet in pd.read_excel(io.BytesIO(data), sheet_name=None, header=None).values():
            for row in sheet.astype(str).values.tolist():
                lines.extend(row)
    else:
        text = data.decode("utf-8", errors="replace")
        csv.field_size_limit(10 ** 9)
        for row in csv.reader(io.StringIO(text)):
            lines.extend(row)

    deals, seen = [], set()
    for raw in lines:
        cell = str(raw).strip()
        if not cell or cell.lower() == "nan" or cell in seen:
            continue
        seen.add(cell)
        d = parse_line(cell)
        if d and d.brands:
            deals.append(d)
    return deals


# ── matching ────────────────────────────────────────────────────────────────
def _norm(s):
    return re.sub(r"[^a-z0-9. ]", " ", str(s or "").lower())


def _brand_hit(brand, hay):
    """Longest leading part of the brand that appears in the product text.

    Sheet brands often carry trailing product words ("Packs Glass Cone"), so try
    the full phrase first and drop words from the end until something matches.
    """
    words = _norm(brand).split()
    while words:
        phrase = " ".join(words)
        if len(phrase) >= 3:
            # tolerate singular/plural on the last word ("Citizens" vs "Citizen")
            pat = re.escape(phrase)
            if phrase.endswith("s"):
                pat = re.escape(phrase[:-1]) + "s?"
            else:
                pat += "s?"
            if re.search(rf"\b{pat}\b", hay):
                return True
        words.pop()
    return False


def matches(deal, row):
    """Does this deal apply to this product row?"""
    hay = _norm(f"{row.get('product','')} {row.get('brand','')}")
    hit = any(_brand_hit(b, hay) for b in deal.brands)
    if not hit:
        return False
    if deal.size:
        size = _norm(deal.size).replace(" ", "")
        sizes = {s.replace(" ", "") for s in re.findall(r"\d*\.?\d+\s*(?:g|mg|oz|pk)", hay)}
        if sizes and size not in sizes:
            return False
    return True


def for_row(row, deals):
    """Best deal for a row: the most specific match (brand + size beats brand)."""
    hits = [d for d in deals if matches(d, row)]
    if not hits:
        return None
    hits.sort(key=lambda d: (d.size is not None, len(" ".join(d.brands))), reverse=True)
    return hits[0]


def attach(rows, deals):
    """Set row['deal'] for every row that a deal applies to. Returns match count."""
    n = 0
    for r in rows:
        d = for_row(r, deals)
        r["deal"] = d.as_badge(r.get("price")) if d else None
        r["deal_text"] = d.text if d else ""
        # Marks the whole run as deal-mode, so tags WITHOUT a deal still get the
        # Smilez logo cleared and the sheet reads consistently.
        r["deals_on"] = True
        if d:
            n += 1
    return n
