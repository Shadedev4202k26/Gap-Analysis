#!/usr/bin/env python3
"""Deal badges for every tag template — hook, 3.5"/4" preroll, and dual split.

One module so every tag family gets the same look. The badge is the approved
"OG Kush" style: a red rounded badge with white text, centred in the pocket the
Smilez logo used to occupy. All sizes derive from the template's own field boxes,
so the hook tag renders exactly as approved and prerolls scale in proportion.

Deal kinds (a dict per tag):
    {"badge": "2/$30"}                     multi-unit, BOGO, "40% OFF" ...
    {"tiers": ["10/$7.50", "70/$49"]}      two or more price tiers, stacked
    {"was": "$12", "now": "$9"}            price markdown (new over struck old)
    any combination, e.g. {"badge": "SALE", "was": "$12", "now": "$9"}

Deal text is normalised on the way in: "3 for $55" / "3 FOR $55" -> "3/$55".
"""
import os
import re

from pypdf import PdfReader

RED = (0.82, 0.16, 0.14)
INK = (0.05, 0.05, 0.08)
GREY = (0.42, 0.42, 0.46)
FONT = "Helvetica-Bold"

# Bulk deals run every week on whole categories, so they sit in a dark violet
# badge with light violet text. Red is kept for the weekly sale alone — a shopper
# scanning the shelf should still spot the genuinely discounted tags first.
BULK_FILL = (0.29, 0.16, 0.51)
BULK_INK = (0.85, 0.80, 0.96)

# Deli flower is badged with the shelf it sits on, in that shelf's own colour:
# (fill, ink, outline). The white shelf needs the outline and dark text — a
# white pill on white card is invisible without it.
SHELF_STYLES = {
    "stash":   ((0.42, 0.20, 0.64), (1, 1, 1), None),
    "blue":    ((0.13, 0.38, 0.76), (1, 1, 1), None),
    "white":   ((1, 1, 1), (0.08, 0.09, 0.12), (0.45, 0.45, 0.50)),
    "red":     ((0.82, 0.16, 0.14), (1, 1, 1), None),
    "outdoor": ((0.09, 0.50, 0.27), (1, 1, 1), None),
}

# Cut guides. The templates carry their own, drawn as rows of Courier dashes in
# a dozen slightly different greys, so some lines print far too faint to cut
# against and some are missing outright. These are drawn fresh over the top at
# one weight and one tone, on every tag boundary.
GUIDE = (0.32, 0.32, 0.36)
GUIDE_WIDTH = 0.8
GUIDE_DASH = (5, 3)

# The approved "OG Kush" hook badge, at its real size. Every preroll tag has room
# for it, so all tags share one physical badge rather than scaling per template.
BADGE_H = 22.0           # single-line badge height (pt)
BADGE_W = 59.7           # minimum badge width (pt)
BADGE_TEXT = 14.0        # badge text size (pt)
TIER_H = 30.0            # stacked multi-tier badge height (pt)
TIER_TEXT = 11.0         # tier text size (pt)
NEW_PRICE, OLD_PRICE = 16.0, 10.0   # markdown sizes (pt)
MIN_INLINE_POCKET = 40   # narrower than this -> badge goes above the price line

# Smilez logo position per template, measured from the art and stored as an
# offset from that slot's THC box (x0, y0, x1, y1). Hybrid art is offset, so
# its logo pokes past the pocket. Nothing here masks the logo any more — the
# templates ship without it — but tools/strip_logo.py reads these to know what
# to paint out when a preroll template is re-exported.
LOGO_OFFSETS = {
    "Sativa_Prerolls.pdf": (83.8, 2.5, 148.2, 18.2),
    "Hybrid_Prerolls.pdf": (78.5, 6.9, 143.8, 22.8),
    "Indica_Prerolls.pdf": (84.1, 3.5, 148.5, 19.2),
    "Sativa_Prerolls_4in.pdf": (100.9, 2.4, 165.3, 18.0),
    "Hybrid_Prerolls_4in.pdf": (89.0, 6.8, 154.6, 22.1),
    "Indica_Prerolls_4in.pdf": (102.6, 3.5, 167.2, 19.2),
}

# ── text ─────────────────────────────────────────────────────────────────────
def normalize(text):
    """'3 for $55' -> '3/$55'; tidy spacing around slashes."""
    t = str(text or "").strip()
    t = re.sub(r"(\d+)\s*for\s*(\$?\s*\d)", r"\1/\2", t, flags=re.I)
    t = re.sub(r"\s*/\s*", "/", t)
    t = re.sub(r"\$\s+", "$", t)
    return re.sub(r"\s{2,}", " ", t)


def split_tiers(text):
    """'10/$7.50 OR 70/$49' -> ['10/$7.50', '70/$49'] (only price tiers kept)."""
    parts = re.split(r"\s+(?:or|&|\+)\s+|\s*,\s*", normalize(text), flags=re.I)
    return [p for p in parts if re.fullmatch(r"\d+/\$\d+(?:\.\d{1,2})?", p)]


# ── geometry ─────────────────────────────────────────────────────────────────
def slot_geometry(src):
    """{slot: {'THC': rect, 'PRICE': rect, 'STRAIN': rect, 'BRAND': rect}}."""
    out = {}
    for a in PdfReader(src).pages[0].get("/Annots", []) or []:
        o = a.get_object()
        v = o.get("/V")
        if v is None and o.get("/Parent"):
            v = o["/Parent"].get_object().get("/V")
        if o.get("/Rect") and isinstance(v, str):
            m = re.match(r"(BRAND|STRAIN|THC|PRICE)_+\s*(\d+)", v.strip())
            if m:
                out.setdefault(int(m.group(2)), {})[m.group(1)] = [
                    float(x) for x in o["/Rect"]]
    return out


def deal_box(g):
    """Where the badge goes for one slot.

    'inline': between THC and price, where the Smilez logo was (hook + singles).
    'above' : full width just above the price line (dual split halves, whose
              THC and price boxes nearly touch).
    """
    thc, price, strain = g["THC"], g["PRICE"], g["STRAIN"]
    if price[0] - thc[2] >= MIN_INLINE_POCKET:
        return "inline", (thc[2], thc[1], price[0], thc[3]), thc[3] - thc[1]
    return "above", (thc[0], thc[3], price[2], strain[1]), thc[3] - thc[1]


# ── drawing ──────────────────────────────────────────────────────────────────
def _fit(c, text, max_w, max_size, min_size=5):
    size = max_size
    while size > min_size and c.stringWidth(text, FONT, size) > max_w:
        size -= 0.25
    return size


def _white(c, rect, inset=1):
    x0, y0, x1, y1 = rect
    c.setFillColorRGB(1, 1, 1)
    c.rect(x0 + inset, y0 + inset, (x1 - x0) - 2 * inset, (y1 - y0) - 2 * inset,
           fill=1, stroke=0)


def _badge(c, box, field_h, lines, align="center", fill=RED, ink=(1, 1, 1), outline=None):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if len(lines) > 1:
        # Tiers stack by default, but where the box is too short for a full tier
        # badge (dual halves) put them on one line if that gives bigger text.
        box_h, box_w = (y1 - y0) - 2, (x1 - x0) - 5
        stack_size = TIER_TEXT * min(1.0, box_h / TIER_H)
        joined = "  ·  ".join(lines)
        line_size = _fit(c, joined, box_w - 12, BADGE_TEXT)
        if line_size > stack_size + 0.5:
            lines = [joined]
    stacked = len(lines) > 1
    h = min(TIER_H if stacked else BADGE_H, (y1 - y0) - 6)
    size = (TIER_TEXT if stacked else BADGE_TEXT) * h / (TIER_H if stacked else BADGE_H)
    need = max(c.stringWidth(t, FONT, size) for t in lines) + 12
    w = min((x1 - x0) - 5, max(BADGE_W, need))
    if align == "bottom":                          # keep clear of the strain above
        cy = y0 + 3 + h / 2
    c.setFillColorRGB(*fill)
    if outline:
        c.setStrokeColorRGB(*outline)
        c.setLineWidth(0.9)
    c.roundRect(cx - w / 2, cy - h / 2, w, h, 4, fill=1, stroke=1 if outline else 0)
    c.setFillColorRGB(*ink)
    size = min(_fit(c, t, w - 6, size) for t in lines)
    c.setFont(FONT, size)
    if not stacked:
        c.drawCentredString(cx, cy - size * 0.36, lines[0])
        return
    step = h / (len(lines) + 0.35)
    top = cy + step * (len(lines) - 1) / 2
    for i, t in enumerate(lines):
        c.drawCentredString(cx, top - i * step - size * 0.36, t)


def _markdown(c, price_rect, was, now):
    """New price above the old, old struck in red (approved Star World look)."""
    _white(c, price_rect)
    x0, y0, x1, y1 = price_rect
    h, w = y1 - y0, x1 - x0
    cx = (x0 + x1) / 2
    k = 1.0
    if w / h < 2.2:                                # tall box (hook): new over old
        ns, os_ = _fit(c, now, w - 4, NEW_PRICE), OLD_PRICE
        c.setFillColorRGB(*INK)
        c.setFont(FONT, ns)
        c.drawCentredString(cx, y0 + h * 0.48, now)
        c.setFillColorRGB(*GREY)
        c.setFont(FONT, os_)
        c.drawCentredString(cx, y0 + h * 0.16, was)
        sw = c.stringWidth(was, FONT, os_)
        ly = y0 + h * 0.16 + os_ * 0.31
        c.setStrokeColorRGB(*RED)
        c.setLineWidth(max(0.8, 1.4 * k))
        c.line(cx - sw / 2 - 2, ly, cx + sw / 2 + 2, ly)
        return
    # wide boxes (prerolls, dual halves): struck old left, new right, so the new
    # price can match the size of the regular prices around it
    os_, ns = h * 0.42, h * 0.78
    ow, nw = c.stringWidth(was, FONT, os_), c.stringWidth(now, FONT, ns)
    gap = 3
    scale = min(1.0, (w - 4) / (ow + gap + nw))
    os_, ns = os_ * scale, ns * scale
    ow, nw = ow * scale, nw * scale
    start = cx - (ow + gap + nw) / 2
    base = y0 + h * 0.2
    c.setFillColorRGB(*GREY)
    c.setFont(FONT, os_)
    c.drawString(start, base, was)
    c.setStrokeColorRGB(*RED)
    c.setLineWidth(1.0)
    c.line(start - 1, base + os_ * 0.31, start + ow + 1, base + os_ * 0.31)
    c.setFillColorRGB(*INK)
    c.setFont(FONT, ns)
    c.drawString(start + ow + gap, base, now)


def draw_deal(c, g, deal, template=None):
    """Draw one tag's deal. `g` is that slot's geometry, `deal` a deal dict.

    A deal marked {"bulk": True} is a standing category offer and gets the pale
    green badge; everything else is this week's sale and stays red.
    """
    if not deal:
        return
    mode, box, field_h = deal_box(g)
    bulk = bool(deal.get("bulk"))
    shelf = SHELF_STYLES.get(deal.get("shelf"))
    lines = []
    if deal.get("tiers"):
        lines = [normalize(t) for t in deal["tiers"] if t]
    elif deal.get("badge"):
        lines = [normalize(deal["badge"])]
    if lines:
        if shelf:
            fill, ink, outline = shelf
        else:
            fill, ink, outline = ((BULK_FILL, BULK_INK, None) if bulk
                                  else (RED, (1, 1, 1), None))
        _badge(c, box, field_h, lines, align="bottom" if mode == "above" else "center",
               fill=fill, ink=ink, outline=outline)
    if deal.get("was") and deal.get("now"):
        _markdown(c, g["PRICE"], normalize(deal["was"]), normalize(deal["now"]))


def draw_cut_guides(c, cells, page_w, page_h):
    """Dashed cut lines on every tag boundary, running the width of the sheet.

    `cells` is combine_tags.tag_cells(): {slot: (x0, y0, x1, y1)}. Tags tile edge
    to edge, so a line on a shared boundary falls between two tags rather than
    across either of them.
    """
    if not cells:
        return
    xs, ys = set(), set()
    for x0, y0, x1, y1 in cells.values():
        xs.update((round(x0, 2), round(x1, 2)))
        ys.update((round(y0, 2), round(y1, 2)))
    c.saveState()
    c.setStrokeColorRGB(*GUIDE)
    c.setLineWidth(GUIDE_WIDTH)
    c.setDash(*GUIDE_DASH)
    for x in sorted(xs):
        c.line(x, 0, x, page_h)
    for y in sorted(ys):
        c.line(0, y, page_w, y)
    c.restoreState()
