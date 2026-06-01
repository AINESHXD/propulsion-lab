"""Guard tests for the 3D engine viewing suite.

The viewer renders in the browser (not testable headless here), so these checks
keep the committed assets consistent: Three.js + GSAP + GLTFLoader vendored
locally (no runtime CDN), the module wires the PBR / glTF-loading / labelled
camera pieces, the four Blender-built engine models are present, the HTML shell
carries the import map + controls + WebGL fallback, and the console links to it.
"""

from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
MODELS = ("jet_engine_cutaway", "jet_engine_turbojet", "jet_engine_ramjet",
          "jet_engine_scramjet", "jet_engine_turboprop")


def test_three_gsap_gltf_vendored_locally() -> None:
    three = STATIC / "vendor" / "three" / "three.module.js"
    orbit = STATIC / "vendor" / "three" / "OrbitControls.js"
    gltf = STATIC / "vendor" / "three" / "GLTFLoader.js"
    bufutil = STATIC / "vendor" / "three" / "BufferGeometryUtils.js"
    gsap = STATIC / "vendor" / "gsap" / "gsap.min.js"
    assert three.is_file() and three.stat().st_size > 100_000
    assert orbit.is_file() and orbit.stat().st_size > 5_000
    assert gltf.is_file() and gltf.stat().st_size > 50_000
    assert bufutil.is_file()
    assert gsap.is_file() and gsap.stat().st_size > 20_000
    # GLTFLoader resolves 'three' via the import map and its sibling util.
    gl = gltf.read_text(encoding="utf-8")
    assert "from 'three'" in gl and "./BufferGeometryUtils.js" in gl


def test_viewer_module_is_a_labelled_gltf_suite() -> None:
    js = (STATIC / "viewer3d.js").read_text(encoding="utf-8")
    for token in (
        'from "three"',                 # import map resolves
        "OrbitControls", "GLTFLoader",
        "PMREMGenerator", "fromEquirectangular",   # neutral studio IBL
        "ACESFilmicToneMapping", "SRGBColorSpace",
        "ENGINES", "select", "_buildLabels", "_showTip", "_updateLabels",  # labelled suite
        "_frame", "dispose",
    ):
        assert token in js, f"viewer3d.js missing: {token}"
    # All four Blender models are referenced.
    for name in MODELS:
        assert f"{name}.glb" in js, f"viewer3d.js missing model ref: {name}"
    # Shelved-for-Pro features must NOT be present in this build.
    for gone in ("_applyOverlay", "_detailExplode", "_updateFlow", "rebuild("):
        assert gone not in js, f"viewer3d.js should not contain: {gone}"


def test_all_four_engine_models_exist() -> None:
    for name in MODELS:
        p = STATIC / "models" / f"{name}.glb"
        assert p.is_file() and p.stat().st_size > 10_000, f"missing/empty model: {name}"
        assert p.read_bytes()[:4] == b"glTF", f"not a GLB: {name}"


def test_viewer_html_shell_is_self_hosted() -> None:
    html = (STATIC / "viewer3d.html").read_text(encoding="utf-8")
    assert "importmap" in html
    assert "/lab/vendor/three/three.module.js" in html
    assert "/lab/vendor/gsap/gsap.min.js" in html
    assert "cdn." not in html  # nothing loaded from a CDN at runtime
    assert "fallback" in html
    assert 'id="tooltip"' in html and 'id="labels"' in html  # hover-explain labels
    for ctrl in ("engine", "present", "reset"):
        assert f'id="{ctrl}"' in html, f"viewer3d.html missing control: {ctrl}"
    for engine in ("turbofan", "turbojet", "ramjet", "scramjet", "turboprop"):
        assert f'value="{engine}"' in html, f"viewer3d.html missing engine option: {engine}"


def test_console_links_to_viewer() -> None:
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "/lab/viewer3d.html" in index
