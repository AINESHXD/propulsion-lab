"""The inverse solver's page and route contract.

The page ships as static HTML with inline JS, so these assert the contract it
depends on — that its routes exist, that every key it can send is one the API
accepts, and that the ML suite it replaced is fully gone.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.engine_core.inverse import OBSERVABLE_KEYS, SOLVABLE_PARAMETERS
from app.main import app

_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _ROOT / "app" / "static"
_PAGE = (_STATIC / "inverse.html").read_text(encoding="utf-8")


def test_the_page_and_its_routes_exist() -> None:
    assert (_STATIC / "inverse.html").exists()
    paths = {r.path for r in app.routes}
    for p in ("/inverse", "/inverse/", "/inverse/catalogue", "/inverse/solve"):
        assert p in paths, p


def test_the_solver_endpoints_are_published() -> None:
    # Unlike the old ML suite, this is a real API anyone can call.
    schema = set(app.openapi()["paths"])
    assert "/inverse/solve" in schema
    assert "/inverse/catalogue" in schema


def test_the_page_reads_its_vocabulary_from_the_api() -> None:
    # The selectable observables and parameters are built from the fetched
    # catalogue, so the page cannot drift from what the solver supports. Naming
    # a couple of keys as sensible starting defaults is fine; enumerating the
    # whole vocabulary in the markup would not be.
    assert "/inverse/catalogue" in _PAGE
    assert "catalogue.observables.map" in _PAGE
    assert "Object.keys(catalogue.parameters)" in _PAGE

    named = {k for k in OBSERVABLE_KEYS if f'"{k}"' in _PAGE}
    assert len(named) < len(OBSERVABLE_KEYS) / 2, (
        f"page names {len(named)} of {len(OBSERVABLE_KEYS)} observables; that is a "
        f"hard-coded list, not defaults"
    )
    for key in SOLVABLE_PARAMETERS:
        assert f'value="{key}"' not in _PAGE, f"{key} checkbox looks hard-coded"


def test_the_fixed_inputs_the_page_sends_are_all_accepted() -> None:
    from app.schemas_inverse import InverseSolveInput

    block = _PAGE.split("const FIXED = [")[1].split("]")[0]
    sent = set(re.findall(r'"(\w+)"', block))
    allowed = set(InverseSolveInput.model_fields)
    assert sent, "no fixed inputs parsed"
    assert sent <= allowed, f"page sends unknown fields: {sorted(sent - allowed)}"


def test_the_page_is_honest_about_what_an_inverse_fit_means() -> None:
    # The whole reason this replaced a black-box predictor is that it explains
    # when its own answer is meaningless. That has to be on the page.
    low = _PAGE.lower()
    assert "identifiab" in low or "not determined" in low
    assert "uncertainty" in low or "error bar" in low or "± " in _PAGE
    assert "verdict" in low


def test_the_page_carries_no_form_or_payment_machinery() -> None:
    low = _PAGE.lower()
    for bad in ("stripe", "paypal", "checkout", "password"):
        assert bad not in low


def test_the_ml_suite_is_gone_everywhere() -> None:
    assert not (_STATIC / "mlsuite.html").exists()
    assert not (_ROOT / "app" / "engine_core" / "surrogate.py").exists()
    assert not (_STATIC / "models" / "surrogate_turbojet.json").exists()
    for page in ("index.html", "m/index.html"):
        assert "mlsuite" not in (_STATIC / page).read_text(encoding="utf-8")
    assert "mlsuite" not in (_STATIC / "tour.js").read_text(encoding="utf-8")


def test_the_3d_viewer_models_survived_the_removal() -> None:
    # The surrogate JSON lived beside the viewer's engine meshes; those stay.
    models = _STATIC / "models"
    for mesh in ("jet_engine_cutaway.glb", "jet_engine_turbojet.glb",
                 "jet_engine_turboprop.glb", "jet_engine_ramjet.glb",
                 "jet_engine_scramjet.glb"):
        assert (models / mesh).exists(), f"{mesh} must not have been deleted"
