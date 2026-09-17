"""Compose a LinkedIn launch image (1200x627) from the existing brand PNGs.

Uses only the assets already in ``app/static/assets/``:
  * das_labs_logo_dark.png        — small DAS LABS wordmark (horizontal)
  * propulsionlab_wordmark.png    — main PropulsionLab wordmark

Layout: dark surface, DAS LABS wordmark at top, PropulsionLab wordmark
centred as the announcement, a short tagline below. No new vector marks,
no decorative graphics. Output: app/static/brand/linkedin-launch.png.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "static" / "assets"
OUT_DIR = ROOT / "app" / "static" / "brand"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# LinkedIn recommends 1200x627 for landscape link/post images.
W, H = 1200, 627
BG = (12, 14, 18, 255)           # #0c0e12, matches the console surface
SUBTLE = (139, 144, 153, 255)    # #8b9099, the dim text used on the dashboard
TEXT = (243, 244, 246, 255)      # #f3f4f6, primary text


def _load(name: str) -> Image.Image:
    """Open a brand PNG with its alpha channel preserved."""
    return Image.open(ASSETS / name).convert("RGBA")


def _scale_to_width(im: Image.Image, target_w: int) -> Image.Image:
    """Proportional resize to ``target_w`` pixels wide (Lanczos for crisp wordmarks)."""
    ratio = target_w / im.width
    return im.resize((target_w, int(round(im.height * ratio))), Image.LANCZOS)


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Return Inter/Segoe/Arial in order of preference; fall back if absent."""
    for candidate in (
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/SFNSText.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_centered_text(draw: ImageDraw.ImageDraw, text: str, y: int,
                        font: ImageFont.FreeTypeFont, fill, letter_spacing: int = 0) -> None:
    """Center-anchored text at vertical pixel ``y``. Implements letter-spacing
    manually because Pillow's draw.text does not expose a tracking option."""
    if letter_spacing <= 0:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) // 2, y), text, font=font, fill=fill)
        return
    widths = [draw.textbbox((0, 0), ch, font=font)[2] for ch in text]
    total = sum(widths) + letter_spacing * (len(text) - 1)
    x = (W - total) // 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + letter_spacing


def main() -> None:
    # --- Canvas ------------------------------------------------------------
    canvas = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(canvas)

    # --- DAS LABS wordmark (small, at the top) ----------------------------
    daslabs = _load("das_labs_logo_dark.png")
    daslabs_scaled = _scale_to_width(daslabs, 360)         # 822 -> 360 wide
    daslabs_y = 76
    canvas.alpha_composite(daslabs_scaled,
                           ((W - daslabs_scaled.width) // 2, daslabs_y))

    # --- PropulsionLab wordmark (large, hero element) ---------------------
    propulsion = _load("propulsionlab_wordmark.png")
    propulsion_scaled = _scale_to_width(propulsion, 920)   # 1249 -> 920 wide
    # Centred a touch above mid so the tagline + footer have room below.
    propulsion_y = 230
    canvas.alpha_composite(propulsion_scaled,
                           ((W - propulsion_scaled.width) // 2, propulsion_y))

    # --- Tagline (calm, monospace, tracked) -------------------------------
    tagline_font = _font(22)
    tagline_y = propulsion_y + propulsion_scaled.height + 56
    _draw_centered_text(draw, "EDUCATIONAL GAS-TURBINE CYCLE SIMULATOR",
                        tagline_y, tagline_font, SUBTLE, letter_spacing=6)

    # --- A single thin underline rule that visually grounds the block. ----
    line_y = tagline_y + 50
    line_w = 220
    draw.line([((W - line_w) // 2, line_y),
               ((W + line_w) // 2, line_y)],
              fill=(243, 244, 246, 38), width=1)

    # --- Footer: short status line ---------------------------------------
    footer_font = _font(20)
    _draw_centered_text(draw, "NOW LIVE",
                        line_y + 22, footer_font, TEXT, letter_spacing=8)

    # --- Save ------------------------------------------------------------
    out = OUT_DIR / "linkedin-launch.png"
    canvas.save(out, "PNG", optimize=True)
    print(f"wrote {out}  ({W}x{H})")


if __name__ == "__main__":
    main()
