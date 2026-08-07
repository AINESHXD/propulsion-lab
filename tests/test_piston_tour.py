"""PistonLab's guided tour and the ghost-trace comparison.

Both ship as static JS, so these assert the contract rather than driving a
browser: every step the tour points at must be an anchor that actually exists in
the page, and the ghost trace must share its axes with the live loop (a ghost on
its own scale would make a smaller loop look identical to a bigger one).
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PISTON = _ROOT / "app" / "static" / "piston"

_HTML = (_PISTON / "index.html").read_text(encoding="utf-8")
_TOUR = (_PISTON / "piston-tour.js").read_text(encoding="utf-8")
_CONSOLE = (_PISTON / "piston.js").read_text(encoding="utf-8")
# Both tours share a lineage, so a positioning fix belongs in both.
_PL_TOUR = (_ROOT / "app" / "static" / "tour.js").read_text(encoding="utf-8")
_BOTH_TOURS = {"piston-tour.js": _TOUR, "tour.js": _PL_TOUR}


# --------------------------------------------------------------------------- #
# tour
# --------------------------------------------------------------------------- #
def test_the_tour_ships_with_the_console() -> None:
    assert 'src="/lab/piston/piston-tour.js' in _HTML
    assert 'id="tutorialButton"' in _HTML


def test_every_step_points_at_an_anchor_that_exists() -> None:
    # A selector that matches nothing shows a card with no ring and silently
    # loses the step, which is exactly the failure a reader would never report.
    selectors = re.findall(r'sel:\s*"#([A-Za-z0-9_-]+)"', _TOUR)
    assert len(selectors) >= 10, "tour lost most of its steps"
    for anchor in selectors:
        assert f'id="{anchor}"' in _HTML, f"tour points at #{anchor}, which the page lacks"


def test_the_tour_survives_the_enthusiast_engineer_split() -> None:
    # Half the cards are hidden by the mode toggle. The tour filters to what is
    # on screen instead of ringing a display:none card.
    assert "function visible(" in _TOUR
    assert "getBoundingClientRect" in _TOUR
    assert "ALL_STEPS.filter" in _TOUR
    # And it still tells the reader what the other mode holds.
    assert "#modeToggle" in _TOUR


def test_the_tour_does_not_fight_the_builder_overlay() -> None:
    # The builder is a full-screen overlay; a ring drawn under it is invisible.
    assert "builderOverlay" in _TOUR


def test_the_tour_replays_and_remembers() -> None:
    assert "plab_tour_seen_v1" in _TOUR
    assert "localStorage" in _TOUR
    # Escape and the arrow keys, same as the PropulsionLab tour.
    for key in ("Escape", "ArrowRight", "ArrowLeft"):
        assert key in _TOUR


def test_the_tour_wears_pistonlab_orange_not_propulsionlab_blue() -> None:
    assert "#e8923e" in _TOUR
    assert "#7ba7eb" not in _TOUR


# --------------------------------------------------------------------------- #
# ring placement — the reader must be able to SEE what is being pointed at
# --------------------------------------------------------------------------- #
def test_both_tours_reserve_room_for_the_header_and_their_own_card() -> None:
    # Centring in the raw viewport put the lower part of a tall card under the
    # tooltip, so the tour appeared to point at something off screen.
    for name, src in _BOTH_TOURS.items():
        assert "function safeBand(" in src, f"{name} does not measure a usable band"
        assert "mission-bar" in src, f"{name} ignores the sticky header"
        assert "els.tip" in src, f"{name} ignores its own card"


def test_both_tours_scroll_by_delta_and_remeasure() -> None:
    # `rect.top + scrollY` is not a stable document coordinate for a sticky
    # element, so a single absolute destination sends the target off screen.
    for name, src in _BOTH_TOURS.items():
        assert "function bringIntoView(" in src, f"{name} still computes one destination"
        assert "window.scrollY + delta" in src, f"{name} does not correct by delta"
        assert "for (let pass = 0" in src, f"{name} does not re-measure"


def test_both_tours_release_only_over_tall_sticky_ancestors() -> None:
    # The controls column is sticky and taller than the viewport, which traps
    # its lower cards. The mission bar is sticky *so that* it stays visible —
    # releasing that one scrolls the target away instead.
    for name, src in _BOTH_TOURS.items():
        assert "function unstick(" in src, f"{name} cannot escape a sticky column"
        assert "height > window.innerHeight" in src, f"{name} releases short sticky elements too"
        assert "function restick(" in src, f"{name} never restores the page"


def test_both_tours_hand_the_page_back_unchanged() -> None:
    # A tour that leaves inline styles behind has edited the site.
    for name, src in _BOTH_TOURS.items():
        end = src.split("function end(")[1].split("function ")[0]
        assert "restick()" in end, f"{name} leaves sticky ancestors released on exit"


# --------------------------------------------------------------------------- #
# ghost traces
# --------------------------------------------------------------------------- #
def test_the_ghost_is_captured_before_the_edit_not_after() -> None:
    # "The previous solve" is useless while dragging — the solver re-runs every
    # 180 ms and the ghost would sit on top of the live loop. It has to be armed
    # when the gesture starts.
    assert "function armGhost(" in _CONSOLE
    assert "function disarmGhost(" in _CONSOLE
    assert 'addEventListener("pointerdown", armGhost)' in _CONSOLE
    assert 'addEventListener("keydown", armGhost)' in _CONSOLE
    assert "ghostArmed" in _CONSOLE


def test_the_ghost_shares_the_axes_with_the_live_loop() -> None:
    # This is the whole point: two loops on one scale. If the ghost were scaled
    # to itself, a change in size would be invisible.
    assert "Math.min(...xs, ...gxs)" in _CONSOLE
    assert "Math.max(...xs, ...gxs)" in _CONSOLE
    assert "Math.min(...ys, ...gys)" in _CONSOLE
    assert "Math.max(...ys, ...gys)" in _CONSOLE


def test_the_dyno_only_ghosts_a_comparable_sweep() -> None:
    # A sweep of a different parameter has a different x axis, so ghosting it
    # would draw a curve that means nothing.
    assert "ghostSweep.param === lastSweep.param" in _CONSOLE
    assert "Math.max(...power, ...gPower)" in _CONSOLE
    assert "Math.max(...torque, ...gTorque)" in _CONSOLE


def test_the_faint_line_explains_itself() -> None:
    # An unlabelled dashed line reads as a rendering bug.
    assert "before this change" in _CONSOLE
    assert "previous sweep" in _CONSOLE
