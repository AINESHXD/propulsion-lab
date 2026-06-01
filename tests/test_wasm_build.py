"""Guard tests for the committed WASM core package (Day 61-62).

The Rust-vs-Python parity is enforced by `cargo test` in wasm/propulsion-core.
These Python-side checks keep the *committed* browser package honest in CI: the
generated files must exist, the binary must be valid WebAssembly, and the JS
glue must export the expected entry points. (Run `wasm-pack build` to refresh.)
"""

from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent / "app" / "static" / "wasm" / "propulsion-core"


def test_wasm_package_files_exist() -> None:
    for name in (
        "propulsion_core.js",
        "propulsion_core_bg.wasm",
        "propulsion_core.d.ts",
    ):
        assert (PKG / name).is_file(), f"missing generated WASM artifact: {name}"


def test_wasm_binary_has_valid_magic() -> None:
    data = (PKG / "propulsion_core_bg.wasm").read_bytes()
    # WebAssembly module header: 0x00 'a' 's' 'm' then version 1.
    assert data[:4] == b"\x00asm"
    assert data[4:8] == b"\x01\x00\x00\x00"
    assert len(data) > 1000  # a real module, not a stub


def test_wasm_glue_exports_entry_points() -> None:
    js = (PKG / "propulsion_core.js").read_text(encoding="utf-8")
    for token in (
        "isa_atmosphere",
        "core_version",
        "class Atmosphere",
        "compressor_exit",
        "combustor_exit",
        "turbine_exit",
        "turbojet_cycle",
        "turbofan_cycle",
    ):
        assert token in js, f"WASM JS glue missing export: {token}"


def test_wasm_engine_integration_layer_present() -> None:
    """The Day 68-69 integration layer + bench page must exist and reference the
    WASM cycle entry points and the API fallback."""

    wasm_dir = PKG.parent
    engine = (wasm_dir / "wasm-engine.js").read_text(encoding="utf-8")
    for token in ("runCycle", "benchmark", "loadWasm", "wasmSupports", "runApi",
                  "turbojet_cycle", "turbofan_cycle", "/simulate/"):
        assert token in engine, f"wasm-engine.js missing: {token}"
    assert (wasm_dir / "wasm-bench.html").is_file()


@pytest.mark.parametrize("alt", [0.0, 10000.0, 20000.0])
def test_python_reference_still_matches_embedded_rust_values(alt: float) -> None:
    """The Rust parity test embeds these Python outputs; assert they are stable
    so a Python-side change can't silently drift from the committed WASM build."""

    from app.engine_core.atmosphere import isa_atmosphere

    expected = {
        0.0: (101325.0, 1.2252256827617731),
        10000.0: (26429.700111057547, 0.4126800243122905),
        20000.0: (5471.9350719501235, 0.08800358116987489),
    }[alt]
    a = isa_atmosphere(alt)
    assert a.pressure_Pa == pytest.approx(expected[0], rel=1e-12)
    assert a.density_kg_m3 == pytest.approx(expected[1], rel=1e-12)
