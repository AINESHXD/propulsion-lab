"""Python-API export (Day 26).

Acceptance: the generated script runs and produces the same numbers as the API.
The script is stdlib-only and POSTs to the API; here we intercept ``urlopen``
with the in-process solver so the test is hermetic (no live server), then check
the script returns exactly the solver's result for the embedded inputs.
"""

from __future__ import annotations

import io
import json

import pytest

from app.engine_core.turbojet import simulate_turbojet_cycle
from app.engine_core.types import TurbojetCycleInputs
from app.main import export_python
from app.python_export import generate_python_script
from app.schemas import PythonExportInput, TurbojetInput


def _exec_script(script: str) -> dict:
    namespace: dict = {}
    exec(compile(script, "<generated>", "exec"), namespace)  # noqa: S102 - generated, trusted
    return namespace


def test_generated_script_compiles_and_embeds_inputs() -> None:
    inputs = TurbojetInput(
        altitude_m=10000.0, mach=0.8, compressor_pressure_ratio=12.0,
        turbine_inlet_temperature_K=1500.0,
    ).model_dump()
    script = generate_python_script("Turbojet", "/simulate/turbojet", inputs)
    ns = _exec_script(script)
    assert ns["ENDPOINT"] == "/simulate/turbojet"
    assert ns["INPUTS"] == inputs           # exact UI state embedded
    assert callable(ns["run"]) and callable(ns["main"])


def test_generated_script_runs_and_matches_solver(monkeypatch) -> None:
    """Day 26 acceptance — the script reproduces the API numbers exactly."""

    inputs = TurbojetInput(
        altitude_m=9000.0, mach=0.85, compressor_pressure_ratio=16.0,
        turbine_inlet_temperature_K=1550.0,
    ).model_dump()
    reference = simulate_turbojet_cycle(TurbojetCycleInputs(**inputs))

    script = generate_python_script("Turbojet", "/simulate/turbojet", inputs)
    ns = _exec_script(script)

    captured = {}

    class _FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request):
        # The script must POST exactly the embedded inputs to the right URL.
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(json.dumps(reference).encode("utf-8"))

    monkeypatch.setattr(ns["urllib"].request, "urlopen", fake_urlopen)

    result = ns["run"]()
    assert captured["url"].endswith("/simulate/turbojet")
    assert captured["body"] == inputs
    assert result["thrust_kN"] == reference["thrust_kN"]
    assert result["TSFC_kg_per_kN_hr"] == reference["TSFC_kg_per_kN_hr"]


def test_export_endpoint_returns_runnable_script() -> None:
    payload = PythonExportInput(
        engine_type="turbofan",
        inputs={"bypass_ratio": 6.0, "turbine_inlet_temperature_K": 1600.0},
    )
    response = export_python(payload)
    assert response.media_type == "text/x-python"
    assert b"attachment" in response.headers["content-disposition"].encode()
    body = response.body.decode("utf-8")
    compile(body, "<endpoint>", "exec")          # valid Python
    assert "/simulate/turbofan" in body
    assert "bypass_ratio" in body


def test_export_endpoint_rejects_bad_inputs() -> None:
    from fastapi import HTTPException
    payload = PythonExportInput(
        engine_type="turbojet",
        inputs={"compressor_pressure_ratio": 0.5},  # < 1.0, invalid
    )
    with pytest.raises(HTTPException) as exc:
        export_python(payload)
    assert exc.value.status_code == 400
