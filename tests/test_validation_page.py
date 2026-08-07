"""The validation page and the report endpoint behind it.

The page's entire worth is that it publishes disagreement it did not have to
publish. These tests defend that specifically: the figures must be computed
server-side from the live solver rather than baked into the HTML, the page must
state what it does *not* validate, and it must not quietly become a marketing
page if the numbers get worse.
"""

from __future__ import annotations

from pathlib import Path

from app.main import validation_page, validation_report

_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _ROOT / "app" / "static"
_PAGE = (_STATIC / "validation.html").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #
def test_the_page_is_served_at_a_clean_url() -> None:
    response = validation_page()
    assert Path(response.path).name == "validation.html"
    assert Path(response.path).exists()


def test_the_report_is_reachable_and_complete() -> None:
    report = validation_report()
    assert report.summary.count >= 20
    assert len(report.cases) == report.summary.count
    for case in report.cases:
        assert case.icao_uid
        assert case.reference_tsfc_kg_per_N_s > 0
        assert case.predicted_tsfc_kg_per_N_s > 0


# --------------------------------------------------------------------------- #
# the page must not be able to drift from the solver
# --------------------------------------------------------------------------- #
def test_the_figures_are_fetched_not_hard_coded() -> None:
    # If the numbers were typed into the HTML they would silently go stale the
    # first time the solver changed, and the page would be quietly lying.
    assert 'fetch("/validation/report")' in _PAGE
    # No engine's measured error should appear as a literal in the markup.
    for case in validation_report().cases:
        assert f"{case.error_percent:.1f}%" not in _PAGE


def test_the_page_carries_no_physics_of_its_own() -> None:
    # Unit conversion and drawing only. Anything resembling a cycle calculation
    # in the page would be a second, divergent implementation.
    for banned in ("gamma", "enthalpy", "isentropic", "pressure_ratio *"):
        assert banned not in _PAGE


# --------------------------------------------------------------------------- #
# honesty surface
# --------------------------------------------------------------------------- #
def test_the_page_says_what_it_does_not_validate() -> None:
    report = validation_report()
    assert "mass flow" in report.not_validated
    assert "circular" in report.not_validated
    # Rendered as its own labelled block, not buried in a run-on paragraph.
    assert 'id="vNotValidated"' in _PAGE, "the page must render what it cannot validate"
    assert 'id="vValidated"' in _PAGE
    assert "Not validated" in _PAGE


def test_the_page_states_the_no_tuning_rule() -> None:
    # This is the claim that separates validation from curve-fitting, so it has
    # to be visible to a reader, not just true in the source.
    low = _PAGE.lower()
    assert "identically to all 26 engines" in low or "identically to every engine" in low
    assert "not fitted per engine" in low or "nothing is fitted per engine" in low


def test_the_page_shows_the_bias_as_prominently_as_the_win() -> None:
    # Rank correlation flatters the model; mean error does not. Both are stat
    # cards of the same kind — the bad number must not be relegated to prose.
    assert "Rank correlation" in _PAGE
    assert "Mean error" in _PAGE
    assert "Worst case" in _PAGE


def test_the_page_credits_its_sources() -> None:
    assert "icao-aircraft-engine-emissions-databank" in _PAGE
    assert "TUDelft-CNS-ATM/openap" in _PAGE
    # And every row is traceable by UID.
    assert "icao_uid" in _PAGE


def test_the_reported_bias_is_still_the_honest_direction() -> None:
    # Every engine is over-predicted. If that ever flips to a mix of signs the
    # page's explanation ("a one-sided bias") stops being true and the copy
    # needs rewriting, so fail loudly rather than publish a stale claim.
    report = validation_report()
    signs = {case.error_percent > 0 for case in report.cases}
    assert signs == {True}, "the page claims a one-sided bias; the data no longer agrees"
