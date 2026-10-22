"""Ziggy runs across the top bar and takes bites out of the Smilez logo.

Plays once when the app opens: Ziggy runs in from the left of the bar, munches
the wordmark — five bites, each clipping a jagged piece off its left edge as his
jaw snaps shut, crumbs flying — then turns, runs off, and the logo grows back.

The frames are real animation, not a drawing in code. Higgsfield (Nano Banana
Pro) redrew the shop's Ziggy artwork as a side view, Kling 4.0 animated it
running and munching on white, and tools/ziggy_frames.py cut the white away
and packed the frames into two strips in static/, served by Streamlit's static
file server (config.toml: enableStaticServing) so they load once and cache:

  ziggy-run.webp    8 frames, one gallop stride (video frames 8-15), looped
  ziggy-munch.webp  45 frames, video frames 22-110 every second one, 12 fps

Everything else is CSS on one DURATION-second timeline, generated below so the
travel, the frame strips, the bites and the crumbs stay in step. Positions are
measured from the bar's right edge, where the wordmark sits (studio.CSS: its
left edge is LOGO_LEFT px from the right, LOGO_W px wide). Skipped for reduced
motion and at 768px and below, where studio.CSS hides the wordmark — the same
breakpoint, or a phone held sideways (768-900px) sees the logo eaten by no one.
"""

DELAY = 1.2            # after the page draws, so it is not lost in the load
LOGO_LEFT = 217.7      # px from the bar's right edge to the wordmark's left edge:
                       # 28 padding + 48 avatar + 12 + 13 "×" + 12 + 104.6 logo.
                       # Re-measure if any of those change (studio.CSS .zb-ctxmark).
LOGO_W = 105           # wordmark width, px
SPRITE_W = 53.5        # one frame as shown, px (the strips are 2x for sharp screens)
SPRITE_H = 50
SNOUT_X = 51.3         # snout tip within a munch frame, px from its left edge
SNOUT_Y = 20.2         # (measured by tools/ziggy_frames.py)
TOP = 11               # sprite top in the 64px bar: snout level with the logo's middle

RUN_FRAMES, RUN_CYCLE = 8, 1 / 3       # one stride = 8 frames at 24 fps
MUNCH_FRAMES, MUNCH_S = 45, 3.75       # 45 frames at 12 fps

RUN_IN_S = 3.0
TURN_S = 0.25                          # pause after the last frame before he turns
RUN_OUT_S = 2.2
REGROW_S = 0.7
TAIL_S = 0.6
DURATION = RUN_IN_S + MUNCH_S + TURN_S + RUN_OUT_S + REGROW_S + TAIL_S

# When his jaw snaps shut in the munch frames (video frames 30, 42, 58, 77, 99),
# as seconds into the munch, and how much of the logo is gone after each bite.
BITE_TIMES = [(f - 22) / 24 for f in (30, 42, 58, 77, 99)]
BITES = [9, 18, 28, 37, 46]

OFF_LEFT = "calc(100% + 8px)"          # `right` that puts the sprite past the bar's left end


def _pct(seconds):
    return 100.0 * seconds / DURATION


def _right_for_bite(b):
    """`right` (px) that puts Ziggy's snout on the logo's bitten edge."""
    edge = LOGO_LEFT - LOGO_W * b / 100.0
    return round(edge - (SPRITE_W - SNOUT_X) - 1, 1)


def _bite_polygon(b):
    """clip-path for the wordmark with b% eaten from the left, edge scalloped.
    Same number of points at every b, so the browser can step between them."""
    d = min(b, 8) / 8.0
    pts = [(b, 0), (100, 0), (100, 100), (b, 100),
           (b + 7 * d, 84), (b + 2 * d, 68), (b + 9 * d, 50), (b + 3 * d, 32), (b + 8 * d, 16)]
    return "polygon(" + ",".join(f"{x:.1f}% {y}%" for x, y in pts) + ")"


def _kf(name, stops):
    return f"@keyframes {name}{{" + "".join(f"{p:.2f}%{{{v}}}" for p, v in sorted(stops)) + "}"


def _keyframes():
    munch0 = RUN_IN_S
    munch1 = RUN_IN_S + MUNCH_S
    out0 = munch1 + TURN_S
    out1 = out0 + RUN_OUT_S
    bites_at = [munch0 + t for t in BITE_TIMES]
    css = []

    # ── where Ziggy is: run in, shuffle forward with each bite, turn, run out ──
    pos = [(0, f"right:{OFF_LEFT};transform:scaleX(1)"),
           (_pct(munch0), f"right:{_right_for_bite(0)}px;transform:scaleX(1)")]
    prev = 0
    for t, b in zip(bites_at, BITES):
        pos += [(_pct(t - 0.12), f"right:{_right_for_bite(prev)}px;transform:scaleX(1)"),
                (_pct(t + 0.08), f"right:{_right_for_bite(b)}px;transform:scaleX(1)")]
        prev = b
    last = _right_for_bite(BITES[-1])
    pos += [(_pct(out0) - 0.01, f"right:{last}px;transform:scaleX(1)"),
            (_pct(out0), f"right:{last}px;transform:scaleX(-1)"),
            (_pct(out1), f"right:{OFF_LEFT};transform:scaleX(-1)"),
            (100, f"right:{OFF_LEFT};transform:scaleX(-1)")]
    css.append(_kf("zgMove", pos))

    # ── which strip shows: running in and out, munching in between ──
    css.append(_kf("zgShowRun", [(0, "opacity:1"), (_pct(munch0), "opacity:0"),
                                 (_pct(out0), "opacity:1"), (_pct(out1), "opacity:0"),
                                 (100, "opacity:0")]))
    css.append(_kf("zgShowMunch", [(0, "opacity:0"), (_pct(munch0), "opacity:1"),
                                   (_pct(out0), "opacity:0"), (100, "opacity:0")]))
    css.append(f"@keyframes zgRunCycle{{from{{background-position-x:0}}"
               f"to{{background-position-x:-{RUN_FRAMES * SPRITE_W}px}}}}")
    css.append(f"@keyframes zgMunchStrip{{from{{background-position-x:0}}"
               f"to{{background-position-x:-{MUNCH_FRAMES * SPRITE_W}px}}}}")

    # ── the wordmark: a jagged piece goes with each bite, then it grows back ──
    clip = [(0, _bite_polygon(0))]
    prev = 0
    for t, b in zip(bites_at, BITES):
        clip += [(_pct(t) - 0.01, _bite_polygon(prev)), (_pct(t), _bite_polygon(b))]
        prev = b
    clip += [(_pct(out1), _bite_polygon(prev)), (_pct(out1 + REGROW_S), _bite_polygon(0)),
             (100, _bite_polygon(0))]
    css.append("@keyframes zgBite{" + "".join(
        f"{p:.2f}%{{clip-path:{v};-webkit-clip-path:{v}}}" for p, v in clip) + "}")
    r0, r1 = _pct(out1), _pct(out1 + REGROW_S)
    css.append(f"@keyframes zgRegrow{{0%,{r0:.2f}%{{transform:scale(1)}}"
               f"{(r0 + r1) / 2:.2f}%{{transform:scale(1.12)}}{r1:.2f}%,100%{{transform:scale(1)}}}}")

    # ── crumbs: a burst from the snout on every bite ──
    for n, (dx, dy) in enumerate([(-10, 16), (-3, 21), (7, 17), (13, 12)]):
        fr = [(0, "opacity:0;transform:translate(0,0)")]
        for t in bites_at:
            fr += [(_pct(t) - 0.01, "opacity:0;transform:translate(0,0)"),
                   (_pct(t), "opacity:1;transform:translate(0,0)"),
                   (_pct(t + 0.45), f"opacity:0;transform:translate({dx}px,{dy}px)")]
        fr.append((100, "opacity:0;transform:translate(0,0)"))
        css.append(_kf(f"zgCrumb{n}", fr))
    return "\n".join(css)


_ANIM = f"{DURATION:.2f}s {DELAY}s 1 both"
# Relative, not "/app/static": Streamlit Cloud runs the app in a frame under
# /~/+/, so a root path reaches the Cloud wrapper page instead of the files.
_STATIC = "app/static"
_CRUMBS = [("#fff", 4), ("#FFD400", 4), ("#fff", 3), ("#FFD400", 3)]

CSS = f"""<style>
{_keyframes()}
.st-key-zbctx [data-testid="stElementContainer"]:has(.zb-ziggy){{position:absolute!important;
  inset:0;width:auto!important;pointer-events:none;z-index:4;overflow:hidden}}   /* enters and leaves at the bar's edge */
.zb-ziggy{{position:absolute;top:{TOP}px;width:{SPRITE_W}px;height:{SPRITE_H}px;right:{OFF_LEFT};
  animation:zgMove {_ANIM} linear;will-change:right,transform}}
.zb-ziggy .zg-run,.zb-ziggy .zg-munch{{position:absolute;inset:0;background-repeat:no-repeat;
  filter:drop-shadow(0 2px 3px rgba(0,0,0,.5))}}
.zb-ziggy .zg-run{{background-image:url({_STATIC}/ziggy-run.webp);
  background-size:{RUN_FRAMES * SPRITE_W}px {SPRITE_H}px;
  animation:zgRunCycle {RUN_CYCLE:.3f}s steps({RUN_FRAMES}) {DELAY}s infinite,zgShowRun {_ANIM} step-end}}
.zb-ziggy .zg-munch{{background-image:url({_STATIC}/ziggy-munch.webp);
  background-size:{MUNCH_FRAMES * SPRITE_W}px {SPRITE_H}px;opacity:0;
  animation:zgMunchStrip {MUNCH_S}s steps({MUNCH_FRAMES}) {DELAY + RUN_IN_S:.2f}s 1 both,
            zgShowMunch {_ANIM} step-end}}
.zb-ziggy .zg-crumb{{position:absolute;left:{SNOUT_X - 2:.1f}px;top:{SNOUT_Y:.1f}px;
  border-radius:1px;opacity:0}}
""" + "".join(f".zb-ziggy .zg-c{n}{{background:{c};width:{s}px;height:{s}px;"
              f"animation:zgCrumb{n} {_ANIM} ease-out}}\n" for n, (c, s) in enumerate(_CRUMBS)) + f"""
.st-key-zbctx .zb-ctxmark img.zb-mark{{animation:zgBite {_ANIM} step-end,zgRegrow {_ANIM} ease-out}}
@media (prefers-reduced-motion: reduce){{
  .zb-ziggy{{display:none}}
  .st-key-zbctx .zb-ctxmark img.zb-mark{{animation:none}}}}
@media (max-width: 768px){{.zb-ziggy{{display:none}}}}   /* = studio.CSS's .zb-ctxmark breakpoint */
</style>"""

HTML = ('<div class="zb-ziggy" aria-hidden="true"><i class="zg-run"></i><i class="zg-munch"></i>'
        + "".join(f'<i class="zg-crumb zg-c{n}"></i>' for n in range(len(_CRUMBS))) + '</div>')
