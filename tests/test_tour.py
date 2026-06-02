"""Guard tests for the guided product tour.

The tour spotlights real elements by CSS selector, so these checks keep it wired
up and keep its anchors from silently drifting out of the page.
"""

from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def test_tour_script_exists_and_exposes_api() -> None:
    js = (STATIC / "tour.js").read_text(encoding="utf-8")
    for token in ("STEPS", "function start", "function end", "window.PLTour", "localStorage"):
        assert token in js, f"tour.js missing: {token}"


def test_index_loads_tour_and_has_button() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "tour.js" in html
    assert 'id="tutorialButton"' in html


def test_tour_anchors_exist_in_page() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    # Every element the tour highlights must be present in the console markup.
    for anchor in (
        'class="engine-card-grid"', 'id="presetSelect"', 'id="simulationForm"',
        'id="runSimulationButton"', "results-panel", 'id="cycleInsights"',
        'id="emissionsPanel"', 'class="console-tabs"', 'id="shareLinkButton"',
        "/lab/viewer3d.html", "/lab/mlsuite.html",
    ):
        assert anchor in html, f"tour anchor missing from index.html: {anchor}"
