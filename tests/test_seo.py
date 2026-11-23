"""Search and link-preview metadata: robots.txt, the sitemap, and the head tags on every public page.

Handlers are called directly, as in the rest of the suite. Each sitemap address is resolved to the file it serves
(a route's FileResponse, or the /lab static mount), so a page in the sitemap that 404s, or one that lost its canonical
or preview tags, fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app import seo
from app.main import STATIC_PATH, app, robots_txt, sitemap_xml

NOINDEX = ["pro/index.html", "social.html", "cfd.html"]


def _file_for(path: str) -> Path:
    """The file a public address serves: a page route's FileResponse, else the /lab static mount."""

    for r in app.routes:
        if isinstance(r, APIRoute) and r.path == path and "GET" in r.methods:
            return Path(r.endpoint().path)
    assert path.startswith("/lab/"), f"no route serves {path}"
    rel = path[len("/lab/"):]
    return STATIC_PATH / (rel + "index.html" if rel.endswith("/") or not rel else rel)


def test_robots_allows_the_site_and_names_the_sitemap() -> None:
    body = robots_txt().body.decode()
    assert "Allow: /" in body and f"Sitemap: {seo.SITE}/sitemap.xml" in body
    for private in ("/docs", "/config", "/cfd/", "/simulate/"):
        assert f"Disallow: {private}" in body


def test_sitemap_lists_every_public_page() -> None:
    body = sitemap_xml().body.decode()
    locs = re.findall(r"<loc>(.*?)</loc>", body)
    assert locs == [seo.SITE + p for p in seo.SITEMAP]
    for must in ("/", "/lab/", "/jet/3d/", "/piston/", "/piston/3d/", "/lab/case-studies/cfm56.html"):
        assert seo.SITE + must in locs


@pytest.mark.parametrize("path", seo.SITEMAP)
def test_each_sitemap_page_exists_and_carries_its_tags(path: str) -> None:
    f = _file_for(path)
    assert f.is_file(), f"{path} -> {f}"
    html = f.read_text(encoding="utf-8")
    assert len(re.findall(r"<title>", html)) == 1
    assert re.search(r'<meta name="description" content="[^"]{50,}"', html)
    # the canonical names the address listed in the sitemap, so search engines index one copy
    assert f'<link rel="canonical" href="{seo.SITE}{path}"' in html
    for tag in ("og:title", "og:description", "og:url"):
        assert f'property="{tag}"' in html
    assert 'name="robots" content="noindex"' not in html
    assert len(re.findall(r"<h1[\s>]", html)) <= 1


@pytest.mark.parametrize("path", ["/", "/lab/", "/jet/3d/", "/piston/", "/piston/3d/"])
def test_main_pages_have_a_preview_image_and_structured_data(path: str) -> None:
    html = _file_for(path).read_text(encoding="utf-8")
    m = re.search(r'property="og:image" content="([^"]+)"', html)
    assert m, path
    image = STATIC_PATH / m.group(1).split("/lab/", 1)[1]
    assert image.is_file() and image.stat().st_size < 300_000
    assert 'application/ld+json' in html


@pytest.mark.parametrize("rel", NOINDEX)
def test_unfinished_pages_stay_out_of_the_index(rel: str) -> None:
    assert 'name="robots" content="noindex"' in (STATIC_PATH / rel).read_text(encoding="utf-8")


def test_duplicate_addresses_point_at_one_canonical() -> None:
    # / and /lab/portal.html are the same file; /m is the phone build of /lab/
    assert f'href="{seo.SITE}/"' in (STATIC_PATH / "portal.html").read_text(encoding="utf-8")
    assert f'rel="canonical" href="{seo.SITE}/lab/"' in (STATIC_PATH / "m" / "index.html").read_text(encoding="utf-8")


def test_home_links_the_3d_viewers_and_case_studies() -> None:
    html = (STATIC_PATH / "portal.html").read_text(encoding="utf-8")
    for href in ("/jet/3d/", "/piston/3d/", "/lab/case-studies/"):
        assert f'href="{href}"' in html
    assert len(re.findall(r"<h1[\s>]", html)) == 1


def test_3d_viewers_have_crawlable_text() -> None:
    for page in ("jet/3d/index.html", "piston/3d/index.html"):
        html = (STATIC_PATH / page).read_text(encoding="utf-8")
        m = re.search(r"<noscript><main><h1>.*?</main></noscript>", html, re.S)
        assert m and len(re.sub(r"<[^>]+>", " ", m.group(0)).split()) > 40
