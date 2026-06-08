"""Generate favicon assets from the existing das_labs_logo.png.

The source asset is a 1536x1024 RGBA lockup. We fit it into each
target square at slight inset on a brand-dark background, so the
favicon reads cleanly at every size from 16px through 512px.

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


def main() -> None:
    logo = Image.open(SOURCE).convert("RGBA")
    print(f"source: {SOURCE.name} {logo.size}")

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
