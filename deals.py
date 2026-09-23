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


# ── sheet structure ─────────────────────────────────────────────────────────
# Row 0 is a header of store names, one column each, and every later row holds
# that store's wording for one deal. Section headers group the rows; the only
# one that changes how a line is read is Brands of the Week, whose percentage
# lives in the header and whose brands are listed bare underneath it.
SECTION = re.compile(
    r"^(bulk\s+flower|prepacked?\s+flower|edibles?|non[\s-]?infused\s+pre[\s-]?rolls?"
    r"|infused\s+pre[\s-]?rolls?|concentrates?|disposable\b.*carts?|510\s+carts?"
    r"|daily\s+deals?|new\s+customer|other\s+deals?|misc)\s*$", re.I)
BOTW = re.compile(r"brands?\s+of\s+the\s+week.*?(\d{1,2})\s*%\s*off", re.I)


def _is_bare_brand(text):
    """A brand name alone on a line — no price, percentage, size or quantity."""
    return 2 <= len(text) <= 40 and not re.search(r"[$%\d]", text)


def parse_column(lines):
    """Parse one store's column in order, so sectioned deals keep their context.

    Order matters for Brands of the Week: the header carries the percentage and
    the brands are listed bare beneath it, so they only mean anything read
    together. parse_line() alone sees a header it skips and a run of names with
    no price, and returns nothing for either.
    """
    deals, seen = [], set()
    botw_pct = None
    for raw in lines:
        cell = re.sub(r"\s{2,}", " ", str(raw or "")).strip()
        if not cell or cell.lower() == "nan":
            continue
        m = BOTW.search(cell)
        if m:
            botw_pct = int(m.group(1))
            continue
        if SECTION.match(cell):
            botw_pct = None
            continue
        if botw_pct and _is_bare_brand(cell):
            if cell.lower() not in seen:
                seen.add(cell.lower())
                deals.append(Deal(f"{cell} {botw_pct}% OFF", "botw", f"{botw_pct}% OFF",
                                  [cell], None, pct=botw_pct))
            continue
        botw_pct = None                      # any priced line ends the brand list
        if cell in seen:
            continue
        seen.add(cell)
        d = parse_line(cell)
        if d and d.brands:
            deals.append(d)
    return deals


def week_from_name(name):
    """Week-start date out of an export filename like '9-21-26 Weekly Deals'."""
    import datetime
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", str(name or ""))
    if not m:
        return None
    mo, day, yr = (int(x) for x in m.groups())
    yr += 2000 if yr < 100 else 0
    try:
        return datetime.date(yr, mo, day)
    except ValueError:
        return None


class Sheet:
    """One weekly deals export: the store columns, and the week it covers."""

    def __init__(self, stores, columns, week=None, name=""):
        self.stores = list(stores)
        self.columns = [list(c) for c in columns]
        self.week = week
        self.name = name

    def deals(self, store=None):
        """Deals for one store, or every store's merged when none is given."""
        if store and store in self.stores:
            return parse_column(self.columns[self.stores.index(store)])
        out, seen = [], set()
        for col in self.columns:
            for d in parse_column(col):
                if d.text not in seen:
                    seen.add(d.text)
                    out.append(d)
        return out

    def to_dict(self):
        return {"name": self.name, "stores": self.stores,
                "week": self.week.isoformat() if self.week else None,
                "columns": self.columns}

    @classmethod
    def from_dict(cls, d):
        import datetime
        wk = d.get("week")
        return cls(d.get("stores") or [], d.get("columns") or [],
                   datetime.date.fromisoformat(wk) if wk else None,
                   d.get("name") or "")


def _rows(data):
    """Raw cell rows from a CSV or XLSX export."""
    if data[:2] == b"PK":
        import pandas as pd
        out = []
        for sheet in pd.read_excel(io.BytesIO(data), sheet_name=None, header=None).values():
            out.extend(sheet.astype(str).values.tolist())
        return out
    text = data.decode("utf-8", errors="replace")
    csv.field_size_limit(10 ** 9)
    return list(csv.reader(io.StringIO(text)))


def load_sheet(file_or_bytes, name=""):
    """Read an export into a Sheet, keeping the store columns apart."""
    data = file_or_bytes.read() if hasattr(file_or_bytes, "read") else file_or_bytes
    rows = _rows(data)
    if not rows:
        return Sheet([], [], week_from_name(name), name)
    stores = []
    for cell in rows[0]:
        cell = str(cell).strip()
        if not cell or cell.lower() == "nan":
            break                       # the sheet pads thousands of empty columns
        stores.append(cell)
    if not stores:                      # no header row — treat it as one column
        stores = ["All stores"]
    columns = [[(str(r[j]).strip() if j < len(r) else "") for r in rows[1:]]
               for j in range(len(stores))]
    return Sheet(stores, columns, week_from_name(name), name)


def changed(rows, previous, current):
    """Rows whose deal differs between two weeks — new, changed or ended.

    An ended deal counts: that shelf tag is still showing a discount the store
    no longer honours, so it needs reprinting just as much as a new one does.
    """
    out = []
    for r in rows:
        was = for_row(r, previous or [])
        now = for_row(r, current or [])
        if (was.as_badge(r.get("price")) if was else None) != \
           (now.as_badge(r.get("price")) if now else None):
            out.append(r)
    return out


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
    A brand of two or more words never drops to a single one: "High Neighbor"
    worn down to "high" claimed both "High Supply" and "Stay High", and "Fire
    Styxx" worn down to "fire" claimed "Michigander Fire".
    """
    words = _norm(brand).split()
    floor = 2 if len(words) > 1 else 1
    while len(words) >= floor:
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
    text = _norm(f"{row.get('product','')} {row.get('brand','')}")
    # Brands are matched against the brand field only, never the whole product
    # name. Several real brands double as ordinary product words, and _brand_hit
    # drops trailing words until something sticks, so matching the full name put
    # other brands' deals on the wrong tags: "Packs" hit every "28 x 1G Preroll
    # Pack", and "Fire Styxx" degraded to "fire". Custom tags carry no brand, so
    # those still fall back to the whole line.
    brand_text = _norm(row.get("brand", "")) or text
    if not any(_brand_hit(b, brand_text) for b in deal.brands):
        return False
    if deal.size:
        # Sizes are written into the product name, so this still reads it all.
        size = _norm(deal.size).replace(" ", "")
        sizes = {s.replace(" ", "") for s in re.findall(r"\d*\.?\d+\s*(?:g|mg|oz|pk)", text)}
        if sizes and size not in sizes:
            return False
    return True


def for_row(row, deals):
    """Best deal for a row.

    Brand of the Week outranks everything. Those brands are the week's headline
    and the 25% comes off a single unit, so it beats a multi-buy that happens to
    name the same brand: a Society C 3.5G matches both "Brands of the Week 25%
    OFF" and "3/$60 Giving Tree OR Society C 3.5G Bags", and the shopper should
    see the 25%.

    Below that it is the most specific match — brand + size beats brand alone.
    """
    hits = [d for d in deals if matches(d, row)]
    if not hits:
        return None
    hits.sort(key=lambda d: (d.kind == "botw", d.size is not None,
                             len(" ".join(d.brands))), reverse=True)
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


# ── standing bulk deals ─────────────────────────────────────────────────────
# Category-wide offers that run every week, unlike the weekly sheet. They fill
# the badge space on tags that have no sale of their own, and render pale green
# rather than red so this week's real discounts still stand out.
#
# Matched on the POS category by keyword, because the exports spell them several
# ways ("Prepacked Flower Brands", "Multi Pack PreRolls"). First match wins, so
# the more specific patterns come first.
BULK_DEALS = [
    (re.compile(r"edible|gumm|chocolate", re.I),            ("BUY 10", "15% OFF")),
    (re.compile(r"concentrate|rosin|resin|badder|shatter|wax", re.I),
                                                            ("BUY 10G", "15% OFF")),
    (re.compile(r"cart|disposable|vape|510", re.I),         ("BUY 10G", "15% OFF")),
    (re.compile(r"pre.?roll", re.I),                        ("BUY 5", "15% OFF")),
    (re.compile(r"prepack|flower", re.I),                   ("BUY 5", "15% OFF")),
]


def bulk_for(row):
    """Standing bulk deal for a row, as a badge dict, or None.

    Reads the row's category, falling back to the product text — the tag rows
    carry a category only when they came from a CSV import.
    """
    hay = f"{row.get('category', '')} {row.get('product', '')} {row.get('brand', '')}"
    for pattern, lines in BULK_DEALS:
        if pattern.search(hay):
            return {"tiers": list(lines), "bulk": True}
    return None


def attach_bulk(rows):
    """Give every row without a sale deal its category's bulk deal. Returns n."""
    n = 0
    for r in rows:
        if r.get("deal"):
            continue
        b = bulk_for(r)
        if b:
            r["deal"] = b
            r["deals_on"] = True
            n += 1
    return n
