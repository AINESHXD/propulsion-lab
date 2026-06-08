"""Generate favicon assets from the existing das_labs_logo.png.

The source asset is a 1536x1024 RGBA lockup of an icon mark on the left
and the DAS LABS wordmark on the right, separated by a ~120px gap. We
crop just the mark portion (the wing/arrow at the left), trim it to its
content bounding box, then fit it into each target square on a brand-
dark background — so the favicon reads as the *mark*, not the whole
lockup which is illegible below ~180px.

Outputs (written to app/static/):
  favicon.ico          multi-resolution 16/32/48 — for legacy browsers
  favicon-16.png       16x16  modern tab icon
  favicon-32.png       32x32  modern tab icon, retina
  apple-touch-icon.png 180x180 iOS home-screen icon
  icon-192.png         192x192 PWA / Android home-screen
  icon-512.png         512x512 PWA / OG fallback
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "static" / "assets" / "das_labs_logo.png"
OUT_DIR = ROOT / "app" / "static"

# Brand dark surface (matches the console). Solid square background so the
# favicon never shows browser-chrome through transparent corners.
BG = (12, 14, 18, 255)


def _fit_into_square(logo: Image.Image, size: int, inset_fraction: float = 0.10) -> Image.Image:
    """Fit ``logo`` (any aspect ratio) into a square of side ``size``,
    leaving a small inset margin so the mark breathes inside the icon.

    Logo aspect is preserved; the limiting dimension determines the scale.
    """

    canvas = Image.new("RGBA", (size, size), BG)
    inset = max(1, int(round(size * inset_fraction)))
    inner = size - 2 * inset

    ratio = min(inner / logo.width, inner / logo.height)
    new_w = max(1, int(round(logo.width * ratio)))
    new_h = max(1, int(round(logo.height * ratio)))
    resized = logo.resize((new_w, new_h), Image.LANCZOS)

    x = (size - new_w) // 2
    y = (size - new_h) // 2
    canvas.alpha_composite(resized, (x, y))
    return canvas


def _extract_mark(logo: Image.Image) -> Image.Image:
    """Crop just the mark out of the das_labs_logo.png lockup.

    The source has a TRANSPARENT background (alpha = 0) with the wing/arrow
    icon and the DAS LABS wordmark drawn as opaque shapes. The icon sits
    on the left, separated from the wordmark by a wide horizontal gap of
    fully-transparent columns. We:
      1. Find columns that contain any opaque pixel.
      2. Walk left-to-right to find the first wide all-transparent gap
         (>=50 px); that's the gap between mark and wordmark.
      3. Crop to everything left of that gap, then tighten to the content
         bounding box.
      4. Re-ink the mark to white-on-transparent so it composites cleanly
         onto the brand-dark canvas used by the favicons (the source is
         dark-grey-on-transparent, which would disappear into the dark
         favicon background).
    """
    import numpy as np

    a = np.array(logo)
    alpha = a[:, :, 3]
    col_has_content = (alpha > 8).any(axis=0)

    # Walk left-to-right but ignore the leading transparent margin: only
    # start tracking gaps AFTER we've entered the first content column.
    entered_content = False
    in_gap = False
    gap_start = 0
    mark_end = logo.width
    for x in range(logo.width):
        if col_has_content[x]:
            if entered_content and in_gap and (x - gap_start) >= 50:
                mark_end = gap_start
                break
            entered_content = True
            in_gap = False
        else:
            if entered_content and not in_gap:
                in_gap = True
                gap_start = x

    # Tighten to the mark's bounding box within the left crop, using the
    # same alpha>8 threshold so single-pixel anti-aliasing dust at the
    # edges doesn't expand the bbox.
    mark_alpha = alpha[:, :mark_end] > 8
    rows = mark_alpha.any(axis=1)
    cols = mark_alpha.any(axis=0)
    if not rows.any() or not cols.any():
        return logo                          # safety: fall back to whole image
    top, bot = int(rows.argmax()), int(len(rows) - rows[::-1].argmax())
    left, right = int(cols.argmax()), int(len(cols) - cols[::-1].argmax())
    cropped_arr = a[top:bot, left:right, :].copy()

    # Re-ink shapes as WHITE preserving the source alpha so anti-aliasing
    # carries over. The favicon canvas is dark, so a white mark reads.
    out = cropped_arr.copy()
    out[:, :, 0] = 255
    out[:, :, 1] = 255
    out[:, :, 2] = 255
    return Image.fromarray(out, mode="RGBA")


def main() -> None:
    logo = Image.open(SOURCE).convert("RGBA")
    print(f"source: {SOURCE.name} {logo.size}")
    logo = _extract_mark(logo)
    print(f"mark crop: {logo.size}")

    targets = [
        ("favicon-16.png", 16, 0.08),
        ("favicon-32.png", 32, 0.10),
        ("apple-touch-icon.png", 180, 0.12),
        ("icon-192.png", 192, 0.12),
        ("icon-512.png", 512, 0.14),
    ]
    for name, size, inset in targets:
        out = OUT_DIR / name
        _fit_into_square(logo, size, inset).save(out, "PNG", optimize=True)
        print(f"  wrote {out.name}  {size}x{size}")

    # Multi-resolution ICO: 16, 32, 48 packed together for legacy clients.
    ico_path = OUT_DIR / "favicon.ico"
    ico = _fit_into_square(logo, 48, 0.10)
    ico.save(ico_path, "ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"  wrote {ico_path.name}  multi-res 16/32/48")


if __name__ == "__main__":
    main()
