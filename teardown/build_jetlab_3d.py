"""Build the JetLab 3D page with the teardown skill and drop it into the site.

    python teardown/build_jetlab_3d.py

Needs Node and the teardown skill (github.com/elvarofficial/teardown) installed at
~/.claude/skills/teardown, or TEARDOWN_DIR pointing at it. The output is one
self-contained HTML file (three.js inlined), committed as
app/static/jet/3d/index.html so the site itself stays buildless.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from app import seo  # noqa: E402

SKILL = pathlib.Path(os.environ.get("TEARDOWN_DIR", pathlib.Path.home() / ".claude" / "skills" / "teardown"))
OUT = ROOT / "app" / "static" / "jet" / "3d" / "index.html"
TITLE = 'JetLab 3D: interactive jet engine cutaways | DAS LABS'
DESCRIPTION = 'Free 3D jet engine cutaways: turbofans, a turbojet, a turboprop, a ramjet and a scramjet, every part driven by a cycle solver.'
GALLERY = json.loads((HERE / 'jetlab-3d' / "gallery.json").read_text(encoding="utf-8"))
NOSCRIPT = seo.noscript('Jet engines in 3D', 'Cutaway 3D models of real jet engines in your browser, every part sized and driven by the PropulsionLab cycle solver.',
                        [(g["name"], (f"/lab/case-studies/{g['id']}.html" if g["id"] in seo.CASE_STUDIES else None)) for g in GALLERY])


def _minify_css(html: str) -> str:
    """The kit inlines the page's stylesheet as written; drop its comments and spare whitespace (conservatively: a
    space around ':' is left alone, since it can matter in a selector)."""

    def squeeze(m: re.Match) -> str:
        css = re.sub(r"/\*.*?\*/", "", m.group(2), flags=re.S)
        css = re.sub(r"\s+", " ", css)
        css = re.sub(r"\s*([{};,>])\s*", r"\1", css).replace(";}", "}")
        return f"{m.group(1)}{css.strip()}{m.group(3)}"

    return re.sub(r"(<style>)(.*?)(</style>)", squeeze, html, count=1, flags=re.S)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["node", str(SKILL / "sims" / "build.mjs"), str(HERE / "jetlab-3d")], cwd=tmp, check=True)
        html = (pathlib.Path(tmp) / "teardown-out" / "dist" / "jetlab-3d.html").read_text(encoding="utf-8")
    head = seo.head_tags('/jet/3d/', TITLE, DESCRIPTION, 'jetlab-3d.jpg', indent="",
                         jsonld=seo.web_app('JetLab 3D', '/jet/3d/'))
    head += '\n<link rel="icon" href="/lab/favicon.ico">'
    html = html.replace("<body>", "<body>\n" + NOSCRIPT, 1)
    html = _minify_css(html.replace("<title>jetlab-3d</title>", head, 1))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}  {len(html) // 1024} KB")


if __name__ == "__main__":
    main()
