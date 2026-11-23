"""Build the PistonLab 3D page with the teardown skill and drop it into the site.

    python teardown/build_pistonlab_3d.py

Needs Node and the teardown skill (github.com/elvarofficial/teardown) installed at
~/.claude/skills/teardown, or TEARDOWN_DIR pointing at it. The output is one
self-contained HTML file (three.js inlined), committed as
app/static/piston/3d/index.html so the site itself stays buildless.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from app import seo  # noqa: E402

SKILL = pathlib.Path(os.environ.get("TEARDOWN_DIR", pathlib.Path.home() / ".claude" / "skills" / "teardown"))
OUT = ROOT / "app" / "static" / "piston" / "3d" / "index.html"
TITLE = 'PistonLab 3D: interactive piston engine cutaways, from a Honda K20A to an F1 V6 | DAS LABS'
DESCRIPTION = 'Free interactive 3D piston engines: inline, V and flat engines from a Honda K20A to a Ferrari V8 and a Formula 1 V6 turbo hybrid, every part driven by the PistonLab cycle solver.'
GALLERY = json.loads((HERE / 'pistonlab-3d' / "gallery.json").read_text(encoding="utf-8"))
NOSCRIPT = seo.noscript('Piston engines in 3D', 'Glass, section and exploded 3D models of real piston engines that run in your browser. The PistonLab solver works out the crank layout and firing order; pistons, rods and valves move from the exact crank geometry and cam timing, and each cylinder glows with the burn it computes.',
                        [(g["name"], None) for g in GALLERY])


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["node", str(SKILL / "sims" / "build.mjs"), str(HERE / "pistonlab-3d")], cwd=tmp, check=True)
        html = (pathlib.Path(tmp) / "teardown-out" / "dist" / "pistonlab-3d.html").read_text(encoding="utf-8")
    head = seo.head_tags('/piston/3d/', TITLE, DESCRIPTION, 'pistonlab-3d.jpg', indent="",
                         jsonld=seo.web_app('PistonLab 3D', '/piston/3d/'))
    head += '\n<link rel="icon" href="/lab/favicon.ico">'
    html = html.replace("<body>", "<body>\n" + NOSCRIPT, 1)
    html = html.replace("<title>pistonlab-3d</title>", head, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(html) // 1024} KB")


if __name__ == "__main__":
    main()
