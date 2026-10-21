"""Build Ziggy's top-bar frame strips (static/ziggy-run.webp, ziggy-munch.webp)
from the Kling video of him running and munching on white.

    python tools/ziggy_frames.py path/to/kling.mp4

Needs imageio and imageio-ffmpeg (pip install imageio imageio-ffmpeg) — only
for building these files, not for running the app.

The video (Higgsfield, Kling 4.0, 940x940, 24 fps, 121 frames) was made from a
Nano Banana Pro side view of the shop's Ziggy artwork. Frames 8-15 are one
gallop stride and loop; frames 22-110 are him munching, his jaw snapping shut at
frames 30, 42, 58, 77 and 99 (ziggy.BITE_TIMES). Prints the snout position that
ziggy.SNOUT_X / SNOUT_Y need if the crop changes.
"""
import os
import sys

import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

RUN = list(range(8, 16))
MUNCH = list(range(22, 111, 2))
HEIGHT_2X = 100                     # strips are 2x; ziggy.py shows them 50px tall
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


def cutout(rgb):
    """Transparent background: near-white pixels connected to the frame's edge
    (so the white chest inside him stays), with the boundary faded by how white
    each pixel is, so no white fringe shows on the dark bar."""
    h, w = rgb.shape[:2]
    # .copy(): an image straight from fromarray() shares the array's memory, and
    # floodfill() on it silently changes nothing.
    mark = Image.fromarray((rgb.min(axis=2) > 222).astype(np.uint8) * 255).copy()
    for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
               (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]:
        if mark.getpixel(xy) == 255:
            ImageDraw.floodfill(mark, xy, 128)
    bg = np.array(mark) == 128
    # Background the legs close off mid-stride (a white pocket under the belly)
    # is not connected to the edge. Clear enclosed patches that are pure white,
    # sizeable and in the lower part of the body — not the white chest or the
    # jersey's sleeve stripes, which are higher up and shaded.
    ys, xs = np.where(~bg)
    lower = ys.min() + 0.55 * (ys.max() - ys.min())
    pure = rgb.min(axis=2) > 238
    for y, x in zip(*np.where(pure & ~bg & (np.arange(h)[:, None] > lower))):
        if bg[y, x] or mark.getpixel((int(x), int(y))) != 255:
            continue
        ImageDraw.floodfill(mark, (int(x), int(y)), 64)
        patch = np.array(mark) == 64
        if patch.sum() > 120 and rgb[patch].min(axis=1).mean() > 242:
            bg |= patch
            ImageDraw.floodfill(mark, (int(x), int(y)), 128)
        else:
            ImageDraw.floodfill(mark, (int(x), int(y)), 200)   # checked, keep
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    near = np.array(Image.fromarray(bg.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
    band = near & ~bg
    soft = np.clip((255 - rgb.min(axis=2).astype(float)) / 105, 0, 1) * 255
    alpha[band] = np.minimum(alpha[band], soft[band]).astype(np.uint8)
    return np.dstack([rgb, alpha])


def main(video):
    frames = iio.imread(video, index=None)
    rgba = {i: cutout(frames[i]) for i in RUN + MUNCH}
    # One crop over both sets, so run and munch frames share a scale and ground line.
    ys, xs = np.where(np.any(np.stack([rgba[i][..., 3] > 20 for i in RUN + MUNCH]), axis=0))
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    s = HEIGHT_2X / (y1 - y0)
    w2 = round((x1 - x0) * s)

    def frame(i):
        a = rgba[i][y0:y1, x0:x1].copy()
        if x0 == 0:                 # paws the video cut off at its left edge: fade them
            ramp = np.clip(np.arange(a.shape[1]) / 14.0, 0, 1)[None, :]
            a[..., 3] = (a[..., 3] * ramp).astype(np.uint8)
        return Image.fromarray(a).resize((w2, HEIGHT_2X), Image.LANCZOS)

    for ids, name in ((RUN, "ziggy-run.webp"), (MUNCH, "ziggy-munch.webp")):
        strip = Image.new("RGBA", (w2 * len(ids), HEIGHT_2X), (0, 0, 0, 0))
        for k, i in enumerate(ids):
            strip.paste(frame(i), (k * w2, 0))
        path = os.path.join(OUT, name)
        strip.save(path, "WEBP", quality=88, method=6)
        print(f"{name}: {len(ids)} frames of {w2 / 2}x{HEIGHT_2X / 2}px, {os.path.getsize(path) // 1024} KB")

    tips = []
    for i in MUNCH:
        a = rgba[i][..., 3] > 128
        top = int(y0 + 0.15 * (y1 - y0))
        band = a[top:int(y0 + 0.45 * (y1 - y0))]
        cols = np.where(band.any(axis=0))[0]
        tips.append((cols.max(), np.where(band[:, cols.max()])[0].mean() + top))
    tx, ty = np.median([t[0] for t in tips]), np.median([t[1] for t in tips])
    print(f"SNOUT_X = {(tx - x0) * s / 2:.1f}  SNOUT_Y = {(ty - y0) * s / 2:.1f}  SPRITE_W = {w2 / 2}")


if __name__ == "__main__":
    main(sys.argv[1])
