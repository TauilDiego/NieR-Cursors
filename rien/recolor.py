#!/usr/bin/env python3
"""Recolor NieR Cursors frames into rien-OS's dark palette (in place), keeping the details.

The original cursors are light, slightly translucent bodies with a faint inner grid, thin dark
outlines, a shaded dark core ("ball"), thin transparent seams and hollow outlined diamonds.
On rien-OS's light paper they wash out, so each frame is remapped by role:
  - body (light pixels)            -> ink #4E4B42, keeping the inner texture, nearly opaque
  - outline (dark, on the border)  -> paper-light #D7D1B3 (edge on any background)
  - core/details (dark, inside)    -> paper-light, with the shading kept in the same direction
  - seams (thin transparent gaps)  -> medium gray #676458, as subtle as in the original
  - enclosed transparent areas     -> ink (fills the hollow diamonds and rings)
Alpha and antialiasing are kept. Frames without a real light body (e.g. the text I-beam, already
dark strokes with a light edge) are left as they are: they already read on both backgrounds.

Usage: recolor.py <png>...
"""
import sys

import numpy as np
from PIL import Image

INK = np.array([0x4E, 0x4B, 0x42], float)
MEDIUM = np.array([0x67, 0x64, 0x58], float)
LIGHT = np.array([0xD7, 0xD1, 0xB3], float)
LO, HI = 0.30, 0.70          # source luminance: <= LO is "dark", >= HI is "light"
BODY_ALPHA = 235             # minimum alpha for recolored bodies
TEXTURE = 0.35               # how much of the body's inner texture survives


def shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    out[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = \
        m[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]
    return out


def dilate(m, r):
    for _ in range(r):
        m = m | shift(m, 1, 0) | shift(m, -1, 0) | shift(m, 0, 1) | shift(m, 0, -1)
    return m


def erode(m, r):
    return ~dilate(~m, r)


def flood_outside(clear):
    """Clear pixels connected to the image border."""
    out = np.zeros_like(clear)
    out[0, :], out[-1, :], out[:, 0], out[:, -1] = clear[0, :], clear[-1, :], clear[:, 0], clear[:, -1]
    while True:
        grown = dilate(out, 1) & clear
        if (grown == out).all():
            return out
        out = grown


def largest_component(mask):
    """The biggest 4-connected region of `mask` (the cursor's main shape)."""
    label = np.zeros(mask.shape, int)
    best, best_size, n = 0, 0, 0
    h, w = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if label[y0, x0]:
            continue
        n += 1
        stack, size = [(y0, x0)], 0
        label[y0, x0] = n
        while stack:
            y, x = stack.pop()
            size += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not label[yy, xx]:
                    label[yy, xx] = n
                    stack.append((yy, xx))
        if size > best_size:
            best, best_size = n, size
    return label == best


def recolor(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im, float)
    rgb, alpha = a[..., :3], a[..., 3]
    h, w = alpha.shape
    r = int(w / 40)                               # seam width grows with size; 0 below 40 px

    lum = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255
    t = np.clip((lum - LO) / (HI - LO), 0, 1)     # 0 dark .. 1 light
    clear = alpha < 16
    solid = ~clear

    body_px = solid & (t >= 0.5)
    if body_px.sum() < 0.25 * solid.sum():
        return                                    # no light body: keep the original

    outside = flood_outside(clear)
    enclosed = clear & ~outside
    main = largest_component(solid)
    # thin gaps inside the main shape only (not the space between the shape and its diamonds)
    seams = (outside & erode(dilate(main, r), r) & ~main) if r else np.zeros_like(clear)
    near_edge = dilate(outside & ~seams, max(r, 1))  # outline = dark pixels on the outer border

    out = np.zeros_like(a)
    # body: ink plus a bit of the original texture around its mean
    body = solid & (t >= 0.5)
    mean = lum[body].mean() if body.any() else 0.8
    tex = (lum - mean)[..., None] * 255 * TEXTURE
    out[..., :3] = np.where(body[..., None], np.clip(INK + tex, 0, 255), 0)
    out[..., 3] = np.where(body, np.maximum(alpha, BODY_ALPHA), 0)

    # dark pixels: outline -> light; inner details -> light with the shading kept (not inverted)
    dark = solid & (t < 0.5)
    outline = dark & near_edge
    detail = dark & ~near_edge
    if detail.any():
        lo, hi = lum[detail].min(), lum[detail].max()
        shade = ((lum - lo) / (hi - lo if hi > lo else 1))[..., None]   # 0 darkest .. 1 lightest
        detail_rgb = np.clip(LIGHT * (0.72 + 0.28 * shade), 0, 255)
        out[..., :3] = np.where(detail[..., None], detail_rgb, out[..., :3])
    edge_rgb = LIGHT + (INK - LIGHT) * (t[..., None] * 2)                # antialiased toward ink
    out[..., :3] = np.where(outline[..., None], edge_rgb, out[..., :3])
    out[..., 3] = np.where(dark, alpha, out[..., 3])

    # seams and enclosed areas
    out[..., :3] = np.where(seams[..., None], MEDIUM, out[..., :3])
    out[..., 3] = np.where(seams, 255, out[..., 3])
    out[..., :3] = np.where(enclosed[..., None], INK, out[..., :3])
    out[..., 3] = np.where(enclosed, 255, out[..., 3])

    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA").save(path)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        recolor(p)
