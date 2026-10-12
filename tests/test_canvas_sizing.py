"""Canvas sizing must never read its own pixel buffer back as a size.

A canvas's width and height attributes are its pixel buffer. Each draw sets
them to the displayed size times the pixel density, so a sizing function that
falls back to reading them (as all four did for a hidden canvas, and the phone
console's did on every draw) multiplies the buffer on every redraw. On a phone
at density 3 the PropulsionLab charts reached a requested 287 GB after four
runs, which drew them "zoomed out" and crashed the tab.

Each sizing function now records the design size once, before the first draw,
in a data attribute. These tests pin that.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
FILES = ["app.js", "m/mobile.js", "piston/piston.js"]


@pytest.mark.parametrize("rel", FILES)
def test_no_size_is_read_back_from_the_pixel_buffer(rel) -> None:
    src = (STATIC / rel).read_text(encoding="utf-8")
    # The only permitted read of the attributes is the one-time capture into
    # dataset.designW / dataset.designH.
    reads = re.findall(r"[^\n]*getAttribute\(\s*[\"'](?:width|height)[\"']\s*\)[^\n]*", src)
    bad = [line.strip() for line in reads if "dataset.design" not in line]
    assert not bad, f"{rel} reads the canvas buffer back as a size: {bad}"


@pytest.mark.parametrize("rel", FILES)
def test_the_design_size_is_captured_once(rel) -> None:
    src = (STATIC / rel).read_text(encoding="utf-8")
    assert re.search(r"if \(!canvas\.dataset\.design[WH]\)", src), rel


def test_the_console_caps_its_buffers() -> None:
    src = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "MAX_CANVAS_PX" in src
