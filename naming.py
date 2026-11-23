"""Dutchie product names for the items on a Metrc manifest.

Jacob's check-in sheet turns a manifest's own wording ("Infused Jeeter 1g Sugar
Plum") into the name Dutchie uses ("Jeeter | Sugar Plum | 1G Rosin Diamond
Infused Preroll"). There is no written rule for it: the names already in
Dutchie are the rulebook, so this reads them.

Every item comes back with a status, and only the first is trusted:

  exact      this exact manifest wording was approved before, or it matches a
             product already in Dutchie on brand, strain, size and kind.
  suggested  a name built from how that brand's other products are written.
             Someone has to look at it.
  none       the brand isn't recognised, so there is nothing to build from.
             Someone has to type it.

A name only becomes `exact` by being approved by a person (it is then
remembered) or by being an existing Dutchie product. Nothing the tool builds
itself is ever marked exact.
"""
import datetime
import difflib
import re
from collections import Counter, defaultdict

# Words that describe the product type or the sheet, not the strain.
_GENERIC = {
    "pre", "roll", "rolls", "preroll", "prerolls", "infused", "infusion", "sativa", "indica",
    "hybrid", "cart", "carts", "cartridge", "disposable", "stylus", "pk", "pack", "ct", "count",
    "gummies", "gummy", "cones", "live", "resin", "rosin", "hash", "each", "ea", "concentrate",
    "vape", "medicated", "mylar", "case", "eighth", "baby", "tarantula", "tarantulas",
    "the", "and", "n", "of", "x", "mg", "g", "oz", "ml", "dose", "thc", "unit", "units",
}
_STRAIN_TYPES = {"sativa", "indica", "hybrid"}
_TYPE_WORDS = {"cones", "gummies", "gummy", "stylus", "cart", "disposable", "syrup", "blunt", "rosin",
               "resin", "live", "hash", "infused", "preroll", "prerolls", "diamond", "sugar", "tarantula",
               "tarantulas", "badder", "sauce", "bag", "jar", "roll", "pre"}
_SIZE = re.compile(r"(\d*\.?\d+)\s*(mg|g|oz|ml)\b", re.I)
_PACK = re.compile(r"(\d+)\s*(?:pk|pack|ct|count)\b", re.I)
_PACK_X = re.compile(r"\b(\d+)\s*x\s*\d*\.?\d+\s*(?:g|mg)\b", re.I)    # "0.5g x 5"
_PACK_X2 = re.compile(r"\b\d*\.?\d+\s*(?:g|mg)\s*x\s*(\d+)\b", re.I)
_SKIP_BRANDS = {"bulk", "med", "rec", "misc"}


def _num(x):
    n = f"{float(x):g}"
    return n[1:] if n.startswith("0.") else n          # Dutchie writes .5G, not 0.5G


def _key(s):
    return " ".join(re.findall(r"[a-z0-9.#']+", str(s).lower().replace("&", " and ")))


def _tokens(s):
    return re.findall(r"[a-z0-9.#']+", str(s).lower().replace("&", " and "))


def size_of(text, divide=True):
    """The size Dutchie would put first: '1G', '.7G', '200MG', or ''.

    On a manifest, a pack's grams are split per unit ("5pk 3.5g" -> .7G, "0.5g x 5"
    -> .5G); milligram packs (gummies, cones) keep the package total, as Dutchie
    writes them. `divide=False` reads a Dutchie name, whose size is already per unit."""
    t = str(text)
    sizes = [(float(n), u.lower()) for n, u in _SIZE.findall(t)]
    if not sizes:
        return ""
    if not divide:
        n, u = sizes[0]
        return f"{_num(n)}{u.upper()}"
    each = re.search(r"(\d*\.?\d+)\s*g\s*x\s*(\d+)\b", t, re.I)       # "0.5g x 5"
    if each:
        return f"{_num(float(each.group(1)))}G"
    packs = [int(p) for p in _PACK.findall(t)]
    grams = [n for n, u in sizes if u == "g"]
    if grams and packs and packs[0] > 1:
        return f"{_num(round(max(grams) / packs[0], 3))}G"
    n, u = max(sizes) if all(x[1] == sizes[0][1] for x in sizes) else sizes[0]
    return f"{_num(n)}{u.upper()}"


def pack_of(text):
    for rx in (_PACK, _PACK_X, _PACK_X2):
        m = rx.search(str(text))
        if m and int(m.group(1)) > 1:
            return int(m.group(1))
    return 0


def flags(text):
    """(infused, kind) read from the item or a Dutchie name's description."""
    w = set(_tokens(text)) | {t.replace("-", "") for t in _tokens(str(text).replace("-", " "))}
    t = " ".join(_tokens(str(text).replace("-", " ")))
    infused = "infused" in w
    if re.search(r"\b(cart|cartridge|disposable|stylus|vape|aio|510)\b", t):
        kind = "vape"
    elif re.search(r"\b(pre ?roll|prerolls?|blunt|tarantulas?|eclair|cone)\b", t) and "cones" not in w:
        kind = "preroll"
    elif re.search(r"\b(gummies|gummy|cones|syrup|chocolate|edible|roll on)\b", t):
        kind = "edible"
    elif re.search(r"\b(rosin|resin|badder|sugar|sauce|wax|shatter|concentrate|diamonds?)\b", t):
        kind = "concentrate"
    elif re.search(r"\b(flower|bud|buds|bag|eighth|smalls)\b", t):
        kind = "flower"
    else:
        kind = ""
    return infused, kind


def strain_tokens(text, brand="", joiners=False):
    """The words left once brand, sizes and product-type words are removed.

    `joiners` keeps "and" / "&" between words, for building a name."""
    t = str(text).replace("&", " & ")
    t = _SIZE.sub(" ", t)
    t = _PACK.sub(" ", t)
    t = re.sub(r"\b\d+\s*x\b", " ", t, flags=re.I)
    t = re.sub(r"\(\s*\)", " ", t)
    b = set(_tokens(brand))
    words = re.findall(r"[A-Za-z0-9.#'&]+", t)
    out = []
    for w in words:
        lw = w.lower()
        if joiners and lw in ("and", "&", "n"):
            out.append("&")
            continue
        if lw in b or lw in _GENERIC or lw in _STRAIN_TYPES or re.fullmatch(r"[\d.]+", lw) or lw == "&":
            continue
        out.append(w)
    return out


def _title(words):
    return " ".join(w if (w.isupper() and len(w) <= 4) or any(c.isupper() for c in w[1:]) else w[:1].upper() + w[1:].lower()
                    for w in words)


def _fuzzy_set_eq(a, b):
    a, b = [x.lower() for x in a], [x.lower() for x in b]
    if len(a) != len(b):
        return False
    rest = list(b)
    for x in a:
        hit = next((y for y in rest if y == x or difflib.SequenceMatcher(None, x, y).ratio() >= 0.88), None)
        if hit is None:
            return False
        rest.remove(hit)
    return True


class Catalog:
    """The Dutchie names a store can see, indexed by brand."""

    def __init__(self, names):
        self.by_brand = defaultdict(list)       # key(brand) -> [parsed names]
        self.brand_label = {}
        seen = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            parts = [p.strip() for p in str(name).split(" | ")]
            if len(parts) != 3 or parts[0].lower() in _SKIP_BRANDS:
                continue
            brand, strain, tail = parts
            k = _key(brand)
            self.brand_label.setdefault(k, brand)
            self.by_brand[k].append({
                "name": name, "brand": brand, "strain": strain, "tail": tail,
                "size": size_of(tail, divide=False), "pack": pack_of(tail), "flags": flags(tail)})
        # Longest brand first, so "Jungle Juice" is found before "Juice".
        self._brands = sorted((k for k in self.by_brand if len(k) > 2), key=len, reverse=True)
        self.strains = Counter(p["strain"] for ps in self.by_brand.values() for p in ps)

    def brand_in(self, item):
        """The brand named in the item: the one that appears first, then the longest."""
        t = " " + _key(item.replace("-", " ")) + " "
        hits = [(t.index(f" {k} "), -len(k), k) for k in self._brands if f" {k} " in t]
        return self.brand_label[min(hits)[2]] if hits else ""

    def _spell(self, words, brand):
        """Strain words as Dutchie already spells them, when a close one exists."""
        if not words:
            return ""
        raw = _title(words)
        pool = [p["strain"] for p in self.by_brand.get(_key(brand), [])] or []
        pool = pool + [s for s in self.strains if abs(len(s) - len(raw)) <= 3]
        best = max(pool, key=lambda s: difflib.SequenceMatcher(None, s.lower(), raw.lower()).ratio(),
                   default=None)
        if best and difflib.SequenceMatcher(None, best.lower(), raw.lower()).ratio() >= 0.92:
            return best
        return raw

    def find(self, item):
        """(brand, [existing products that fit]) for an item."""
        brand = self.brand_in(item)
        if not brand:
            return "", []
        size, pack, fl = size_of(item), pack_of(item), flags(item)
        st = strain_tokens(item, brand)
        fits = []
        words = set(_tokens(str(item).replace("-", " ")))
        for p in self.by_brand[_key(brand)]:
            # A milligram pack ("200mg 10 pk") is the same product whether or not
            # Dutchie's name counts the pieces; a gram pack is not (1G vs 14PK).
            pack_ok = p["pack"] == pack or (p["pack"] == 0 and size.endswith("MG"))
            if p["size"] != size or not pack_ok:
                continue
            # Edibles: a manifest says "Cones", Dutchie says "Infused Sugar Cones".
            # Treat infused as agreeing only when both name the same edible type.
            shares = bool(words & set(_tokens(p["tail"])) & {"cones", "gummies", "gummy", "syrup"})
            if fl[0] != p["flags"][0] and not (fl[1] == "edible" and p["flags"][1] == "edible" and shares):
                continue
            if fl[1] and p["flags"][1] and fl[1] != p["flags"][1]:
                continue
            if _fuzzy_set_eq(st, strain_tokens(p["strain"], brand)):
                fits.append(p)
        return brand, fits

    def descriptor(self, brand, size, pack, fl, item=""):
        """How this brand writes what comes after the size, or ''."""
        pool = self.by_brand.get(_key(brand), [])
        item_words = set(_tokens(str(item).replace("-", " ")))
        ranked = []
        for p in pool:
            shared = len(item_words & set(_tokens(p["tail"])) & _TYPE_WORDS)
            score = (p["size"] == size) * 4 + (p["flags"] == fl) * 3 + (p["flags"][0] == fl[0]) \
                + (p["pack"] == pack) * 2 + (p["flags"][1] == fl[1]) * 2 + shared * 2
            if score >= 5:
                rest = re.sub(r"^\s*\.?\d[\d.]*\s*(?:mg|g|oz|ml)\b\s*", "", p["tail"], flags=re.I)
                ranked.append((score, rest))
        if not ranked:
            return ""
        top = max(s for s, _ in ranked)
        return Counter(r for s, r in ranked if s == top).most_common(1)[0][0]

    def draft(self, item):
        """A built name for an item with no existing product, and the closest names."""
        brand = self.brand_in(item)
        if not brand:
            return "", []
        size, pack, fl = size_of(item), pack_of(item), flags(item)
        words = strain_tokens(item, brand, joiners=True)
        while words and words[0] == "&":
            words = words[1:]
        while words and words[-1] == "&":
            words = words[:-1]
        strain = self._spell(words, brand)
        desc = self.descriptor(brand, size, pack, fl, item)
        if not desc:
            base = {"preroll": "Preroll", "vape": "Cart", "edible": "", "concentrate": "", "flower": "Bag"}.get(fl[1], "")
            if fl[0] and fl[1] == "preroll":
                base = "Infused Preroll"
            desc = base + (f" {pack}PK" if pack and fl[1] == "preroll" and pack > 5 else "")
        name = f"{brand} | {strain} | {(size + ' ' + desc).strip()}".replace("  ", " ")
        # Same brand, same strain: the products people will recognise.
        near = [p["name"] for p in self.by_brand[_key(brand)]
                if strain and _fuzzy_set_eq(strain_tokens(strain, brand), strain_tokens(p["strain"], brand))][:3]
        return name, near


def suggest(item, catalog, memory=None):
    """{'name', 'status', 'note', 'near'} for one manifest item.

    `memory` maps key(item) -> the Dutchie name somebody approved for that exact
    wording."""
    mem = (memory or {}).get(_key(item))
    if mem:
        return {"name": mem, "status": "exact", "note": "Approved before", "near": []}
    brand, fits = catalog.find(item)
    if len(fits) == 1:
        return {"name": fits[0]["name"], "status": "exact", "note": "Already in Dutchie", "near": []}
    if len(fits) > 1:
        return {"name": fits[0]["name"], "status": "suggested", "near": [p["name"] for p in fits[:3]],
                "note": "More than one Dutchie product fits. Pick the right one."}
    name, near = catalog.draft(item)
    if name:
        return {"name": name, "status": "suggested", "near": near,
                "note": "Built from how this brand's other products are named. Check it."}
    return {"name": "", "status": "none", "near": [],
            "note": "Brand not recognised. Type the Dutchie name."}


# ── what people approved, kept so the same wording is exact next time ─────────
TABLE = "transfer_names"


def memory_load(db):
    """({key(item): Dutchie name}, error or None). The error is shown, never fatal."""
    if db is None:
        return {}, "no Supabase connection"
    try:
        data = db.table(TABLE).select("item_key,name").limit(5000).execute().data or []
    except Exception as e:                                   # noqa: BLE001
        return {}, str(e)
    return {r["item_key"]: r["name"] for r in data}, None


def memory_save(db, entries):
    """Remember approved names. entries: [(manifest item, Dutchie name, sender)]."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = [{"item_key": _key(i), "item": i[:300], "name": n[:200], "sender": (s or "")[:120],
             "updated_at": now} for i, n, s in entries if _key(i) and n]
    if rows:
        db.table(TABLE).upsert(rows, on_conflict="item_key").execute()
