"""Generate the depth wallpaper for the Windows 11 glass theme.

The wallpaper is the half of the "floating window" illusion that costs
nothing: a dark background with a receding perspective floor and a low
horizon glow makes any window sitting on top of it read as elevated,
even before DWM blur is involved.

Tuned for the target display (LG OLED 4K, HDR, 10-bit):
  - stays dark: an OLED panel showing a bright field runs at full power
    permanently, and this wallpaper is on screen all day
  - no pure white, no large bright static area
  - dithered gradients: banding is what betrays a flat gradient, and a
    10-bit panel makes it more visible, not less
"""

from __future__ import annotations

import numpy as np
from PIL import Image

WIDTH, HEIGHT = 3840, 2160
OUT = "wall_depth_4k.png"

# Deep background, top to bottom.
TOP = np.array([4, 6, 11], dtype=np.float64)
BOTTOM = np.array([10, 15, 26], dtype=np.float64)

# Horizon glow: cool steel, deliberately desaturated so it never competes
# with window content for attention.
GLOW = np.array([26, 52, 88], dtype=np.float64)
GLOW_X, GLOW_Y = 0.5, 0.86        # centre, low on the screen
GLOW_RX, GLOW_RY = 0.85, 0.34     # wide and flat

GRID_RGB = np.array([96, 148, 198], dtype=np.float64)
GRID_TOP = 0.56                   # horizon line, as a fraction of height
GRID_MAX_ALPHA = 0.190            # never more: this must stay felt, not seen
GRID_COLUMNS = 34
GRID_ROWS = 22


def vertical_gradient() -> np.ndarray:
    """Base gradient, top colour to bottom colour."""
    t = np.linspace(0.0, 1.0, HEIGHT)[:, None, None]
    return TOP[None, None, :] * (1.0 - t) + BOTTOM[None, None, :] * t


def horizon_glow(img: np.ndarray) -> np.ndarray:
    """Add a soft elliptical glow low on the screen."""
    x = np.linspace(0.0, 1.0, WIDTH)[None, :]
    y = np.linspace(0.0, 1.0, HEIGHT)[:, None]
    d = np.sqrt(((x - GLOW_X) / GLOW_RX) ** 2 + ((y - GLOW_Y) / GLOW_RY) ** 2)
    # smoothstep falloff, squared for a gentler shoulder
    f = np.clip(1.0 - d, 0.0, 1.0) ** 2
    return img + GLOW[None, None, :] * f[:, :, None]


def perspective_floor(img: np.ndarray) -> np.ndarray:
    """Draw a receding grid below the horizon.

    Rows are spaced by 1/n^2 so they bunch up towards the horizon, which is
    what actually reads as distance. Columns converge on the vanishing point.
    """
    horizon = GRID_TOP * HEIGHT
    depth = HEIGHT - horizon
    acc = np.zeros((HEIGHT, WIDTH), dtype=np.float64)

    yy = np.arange(HEIGHT)[:, None]
    xx = np.arange(WIDTH)[None, :]

    # Fade the whole grid out as it approaches the horizon.
    below = (yy >= horizon).astype(np.float64)
    t = np.clip((yy - horizon) / depth, 0.0, 1.0)
    fade = (t ** 1.5) * below

    # Horizontal lines.
    for i in range(1, GRID_ROWS + 1):
        y = horizon + depth * (i / GRID_ROWS) ** 2.2
        acc += np.exp(-(((yy - y) / 1.9) ** 2))

    # Converging vertical lines.
    vx = WIDTH * 0.5
    for i in range(GRID_COLUMNS + 1):
        far = vx + (i - GRID_COLUMNS / 2) * (WIDTH * 0.055)
        near = vx + (i - GRID_COLUMNS / 2) * (WIDTH * 0.34)
        x_at = far + (near - far) * np.clip((yy - horizon) / depth, 0.0, 1.0)
        acc += np.exp(-(((xx - x_at) / 1.7) ** 2))

    a = np.clip(acc, 0.0, 1.0) * fade * GRID_MAX_ALPHA
    return img + GRID_RGB[None, None, :] * a[:, :, None]


def vignette(img: np.ndarray) -> np.ndarray:
    """Darken the corners so windows keep the eye near the centre."""
    x = np.linspace(-1.0, 1.0, WIDTH)[None, :]
    y = np.linspace(-1.0, 1.0, HEIGHT)[:, None]
    r = np.sqrt(x ** 2 + y ** 2) / np.sqrt(2.0)
    return img * (1.0 - 0.30 * r[:, :, None] ** 2.3)


def dither(img: np.ndarray) -> np.ndarray:
    """Break up banding before quantising to 8 bits."""
    rng = np.random.default_rng(20260809)
    return img + rng.uniform(-0.5, 0.5, img.shape)


def main() -> None:
    img = vertical_gradient()
    img = np.repeat(img, WIDTH, axis=1) if img.shape[1] == 1 else img
    img = horizon_glow(img)
    img = perspective_floor(img)
    img = vignette(img)
    img = dither(img)
    out = np.clip(img, 0, 255).astype(np.uint8)
    Image.fromarray(out, mode="RGB").save(OUT, optimize=True)
    print(f"{OUT}  {WIDTH}x{HEIGHT}")
    print(f"luminance moyenne : {out.mean():.1f}/255  (bas = bon pour OLED)")
    print(f"pixel le plus clair : {out.max()}/255")


if __name__ == "__main__":
    main()
