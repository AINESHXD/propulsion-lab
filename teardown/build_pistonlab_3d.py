"""Build the PistonLab 3D page with the teardown skill and drop it into the site.

    python teardown/build_pistonlab_3d.py

Needs Node and the teardown skill (github.com/elvarofficial/teardown) installed at
~/.claude/skills/teardown, or TEARDOWN_DIR pointing at it. The output is one
self-contained HTML file (three.js inlined), committed as
app/static/piston/3d/index.html so the site itself stays buildless.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SKILL = pathlib.Path(os.environ.get("TEARDOWN_DIR", pathlib.Path.home() / ".claude" / "skills" / "teardown"))
OUT = ROOT / "app" / "static" / "piston" / "3d" / "index.html"
TITLE = "PistonLab 3D | DAS LABS"
DESCRIPTION = "Real engines and your own PistonLab build in 3D, every part driven by the cycle solver."


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["node", str(SKILL / "sims" / "build.mjs"), str(HERE / "pistonlab-3d")], cwd=tmp, check=True)
        html = (pathlib.Path(tmp) / "teardown-out" / "dist" / "pistonlab-3d.html").read_text(encoding="utf-8")
    head = (f"<title>{TITLE}</title>\n<meta name=\"description\" content=\"{DESCRIPTION}\">\n"
            "<link rel=\"icon\" href=\"/lab/favicon.ico\">")
    html = html.replace("<title>pistonlab-3d</title>", head, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(html) // 1024} KB")


if __name__ == "__main__":
    main()
