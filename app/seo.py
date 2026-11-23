"""Search and link-preview metadata for the public DAS LABS pages.

One place for the canonical address of each page, the head tags that tell search engines and link previews
(LinkedIn, Reddit, WhatsApp) what a page is, and the sitemap. The hand-written pages carry the output of
``head_tags`` in their <head>; the generated pages (case studies, the two 3D viewers) call it when they build.
"""

from __future__ import annotations

import html
import json

SITE = "https://daslabs.uk"
OG = "/lab/assets/og"

# Every page meant to be found, by its canonical path. A page reachable at two addresses (/inverse/ and
# /lab/inverse.html, / and /lab/portal.html) is listed once, at the address its canonical tag names.
CASE_STUDIES = ["jt8d", "cf6", "pw4000", "v2500", "cfm56", "ge90", "genx", "leap", "gtf", "trentxwb"]
SITEMAP = [
    "/",
    "/lab/",
    "/jet/3d/",
    "/piston/",
    "/piston/3d/",
    "/lab/case-studies/",
    *[f"/lab/case-studies/{c}.html" for c in CASE_STUDIES],
    "/lab/sections/turbojet.html",
    "/lab/methodology.html",
    "/validation/",
    "/inverse/",
    "/privacy",
]

# Not for search: API docs, runtime config, the gated CFD jobs, the solver endpoints.
ROBOTS = f"""User-agent: *
Allow: /
Disallow: /docs
Disallow: /redoc
Disallow: /openapi.json
Disallow: /config
Disallow: /cfd/
Disallow: /simulate/

Sitemap: {SITE}/sitemap.xml
"""

AUTHOR = {
    "@type": "Person",
    "name": "Ainesh Das",
    "sameAs": ["https://www.linkedin.com/in/ainesh-das/", "https://www.instagram.com/das.labs/"],
}


def web_app(name: str, path: str, description: str | None = None, features: list[str] | None = None) -> dict:
    """schema.org WebApplication for a free, browser-based educational tool."""

    app = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": name,
        "url": SITE + path,
        "applicationCategory": "EducationalApplication",
        "operatingSystem": "Any (runs in a web browser)",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "GBP"},
        "creator": AUTHOR,
    }
    if description:  # optional: pages that are near their size budget already carry it in the meta tags
        app["description"] = description
    if features:
        app["featureList"] = features
    return app


def head_tags(path: str, title: str, description: str, image: str | None = None, *,
              noindex: bool = False, jsonld: dict | list | None = None, og_type: str = "website",
              indent: str = "    ") -> str:
    """The <title>, description, canonical, Open Graph, Twitter card and JSON-LD tags for one page."""

    e = lambda s: html.escape(s, quote=True)  # noqa: E731
    url = SITE + path
    lines = [
        f"<title>{e(title)}</title>",
        f'<meta name="description" content="{e(description)}" />',
        f'<link rel="canonical" href="{e(url)}" />',
    ]
    if noindex:
        lines.append('<meta name="robots" content="noindex" />')
    lines += [
        f'<meta property="og:type" content="{og_type}" />',
        '<meta property="og:site_name" content="DAS LABS" />',
        f'<meta property="og:title" content="{e(title)}" />',
        f'<meta property="og:description" content="{e(description)}" />',
        f'<meta property="og:url" content="{e(url)}" />',
    ]
    if image:
        lines += [
            f'<meta property="og:image" content="{SITE}{OG}/{image}" />',
            '<meta property="og:image:width" content="1200" />',
            '<meta property="og:image:height" content="630" />',
            '<meta name="twitter:card" content="summary_large_image" />',
        ]
    if jsonld:
        body = json.dumps(jsonld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        lines.append(f'<script type="application/ld+json">{body}</script>')
    return ("\n" + indent).join(lines)


def noscript(heading: str, text: str, items: list[tuple[str, str | None]]) -> str:
    """What a reader without JavaScript, and a search engine, sees on a script-built page: what it is, and a list
    (each item a name and an optional link)."""

    e = html.escape
    li = "".join(f'<li><a href="{e(href)}">{e(name)}</a></li>' if href else f"<li>{e(name)}</li>" for name, href in items)
    return f"<noscript><main><h1>{e(heading)}</h1><p>{e(text)}</p><ul>{li}</ul></main></noscript>"


def sitemap_xml() -> str:
    urls = "".join(f"<url><loc>{SITE}{p}</loc></url>" for p in SITEMAP)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
