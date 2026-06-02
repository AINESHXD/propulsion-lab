"""Guard tests for the per-feature help buttons."""

from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def test_help_script_exists_and_covers_each_feature() -> None:
    js = (STATIC / "help.js").read_text(encoding="utf-8")
    for token in ("HELP", "How to use it", "Where it's used", "window.PLHelp", "help-i"):
        assert token in js, f"help.js missing: {token}"
    # Every analysis tab gets a help entry.
    for key in ("graphs", "compare", "offdesign", "mission", "compressormap", "optimize"):
        assert f"{key}:" in js, f"help.js missing entry: {key}"


def test_index_loads_help_script() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "help.js" in html
    # The panels the help buttons attach to must exist.
    for key in ("graphs", "compare", "offdesign", "mission", "compressormap", "optimize"):
        assert f'data-tab-panel="{key}"' in html, f"missing panel for help: {key}"
