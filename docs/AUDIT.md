# daslabs.uk audit

Phase 1 of a debug and UI pass. Measured 2026-10-02 against commit `267a680`,
locally on uvicorn and against the deployed site at https://daslabs.uk.

Physics and numerical results are out of scope. Nothing in this document changes
a solver, a correlation or a reported figure. Anything that looked like a physics
problem is recorded under "Not touched" rather than fixed.

## Stack map

| Layer | What it actually is |
|---|---|
| Backend | FastAPI + Pydantic v2, 60 Python modules under `app/` |
| Frontend | Buildless vanilla ES modules. No `package.json`, no bundler, no build step |
| Templating | None. Static HTML served by `StaticFiles` mounted at `/lab` |
| 3D | Three.js r160 (vendored) + GLTFLoader, driven by `app/static/viewer3d.js` |
| Animation | GSAP, vendored at `app/static/vendor/gsap/gsap.min.js` |
| Native code | Rust compiled to WASM at `app/static/wasm/propulsion-core/` |
| Styling | 4 hand-written CSS files, no preprocessor |
| Deploy | Docker image to Fly.io (`fly.toml`, `Dockerfile`) |
| Tests | 670 pytest tests, all passing |

### Assumptions recorded

The buildless design is deliberate: there is no Node toolchain on the development
machine. Every recommendation below is constrained to what is achievable without
introducing a bundler, and no fix proposes one.

Lighthouse is npm-only and cannot run here. The Core Web Vitals below were
measured directly through `PerformanceObserver` in headless Chromium. They are
real measurements but they are not Lighthouse scores and should not be quoted as
such.

## Measured baseline

Local, headless Chromium, 1440x900, after networkidle plus 2.5 s.

| Route | Console errors | Failed requests | LCP (ms) | CLS | Long tasks (ms) | Transfer (KB) |
|---|---|---|---|---|---|---|
| `/` | 0 | 0 | 360 | 0.000 | 0 | 171 |
| `/lab/` | 0 | 0 | 3392 | 0.004 | 3357 | 5357 (see H1) |
| `/validation/` | 0 | 0 | 504 | 0.066 | 0 | 257 |
| `/inverse/` | 0 | 0 | 504 | 0.010 | 0 | 264 |
| `/piston/` | 0 | 0 | 520 | 0.009 | 0 | 456 |
| `/lab/methodology.html` | 0 | 0 | 496 | 0.000 | 0 | 169 |
| `/pro/` | 0 | 0 | 484 | 0.000 | 0 | 164 |
| `/privacy/` | 0 | 0 | 520 | 0.000 | 0 | 168 |

## What already passes

Recorded because an audit that lists only faults misrepresents the codebase.

- Zero console errors, zero uncaught exceptions and zero failed requests on all
  eight routes.
- Input validation is sound. `POST /simulate/turbojet` rejects negative mass
  flow, zero mass flow, NaN, a turbine temperature of 99999 K and a pressure
  ratio of 1e9 with 422 or 400, and returns 200 for a valid case.
- Three.js resources are disposed properly: 78 `.dispose()` calls, 47
  `removeEventListener`, `webglcontextlost` handled, device pixel ratio capped at
  2 (`app/static/viewer3d.js:128`).
- `prefers-reduced-motion` is already respected across 8 files, including both
  tours, both consoles and the 3D viewer.
- No positive `tabindex`, no `img` without `alt`, no heading-order jumps.
- Versioned assets cache correctly: a `?v=` request returns
  `public, max-age=31536000, immutable`.

## Bug list

### Critical

**C1. No HTTP compression anywhere.** There is no `GZipMiddleware` and nothing
compresses at the Fly proxy. Verified against production:

    GET https://daslabs.uk/lab/vendor/three/three.module.js
    content-length: 1272972        (no content-encoding header at all)

`app.js` ships 179,323 bytes uncompressed on the same request. Text assets
compress by roughly 70 to 80 percent, so this is close to 1 MB of waste on the
console's first load. Highest value fix on this list, and the smallest.

### High

**H1. `/lab/` costs 5.2 MB and 3.4 s of main-thread long tasks.** Driven by H2,
H3 and H7. LCP is 3392 ms locally with no network latency and no CPU throttling,
so the figure on a real phone is worse.

Measuring this correctly matters and took two attempts. The 3D viewer is an
iframe (`index.html:278`), and `performance.getEntriesByType('resource')` in the
top frame does **not** include an iframe's sub-resources, so a Resource Timing
measurement reports a misleadingly small 206 KB. The figures here come from
Playwright `request.sizes()`, which counts every frame.

After C1 the same page is **2728 KB** over the wire, of which the single cutaway
GLB is 1987 KB. Compression has taken this as far as it can; the remaining cost
is the model itself.

**H2. `three.module.js` is the unminified development build.** 1.21 MB, r160,
licence comments and readable identifiers intact. The minified module build is
roughly half the size before compression.

**H3. The five GLB models are uncompressed and uncacheable.** 8.6 MB total,
largest 3.29 MB, and none carries `KHR_draco_mesh_compression` or
`EXT_meshopt_compression`. `viewer3d.js:21-67` requests them with a `?m=` token rather than `?v=`, and
`glb` is absent from the versioned-extension allowlist in the cache middleware
(`app/main.py:228-230`), so the rule misses on both counts and production returns
no `Cache-Control` header at all for a 3.4 MB file. The same applies to the WASM
payload.

Post-compression the cutaway GLB is still 1987 KB, 73 percent of everything
`/lab/` transfers. Mesh compression is the only lever left on it.

**H4. Horizontal overflow breaks the tablet and landscape-phone layouts.**

| Route | Viewport | scrollWidth vs clientWidth | First offenders |
|---|---|---|---|
| `/lab/` | 768x1024 | 1168 vs 768 | `A.mission-link`, `SECTION.hero-band`, `DIV.hero-copy` |
| `/lab/` | 1024x768 | 1180 vs 1024 | `SECTION.hero-band`, `DIV.hero-copy`, `H1.hero-title` |
| `/lab/` | 812x375 | 1168 vs 812 | as above |
| `/validation/` | 768x1024 | 990 vs 768 | `SECTION.section`, `DIV.section-header`, `P.eyebrow` |
| `/validation/` | 812x375 | 1276 vs 812 | as above |
| `/validation/` | 320x640 | 339 vs 320 | the per-engine table |
| `/` | 320x640 | 334 vs 320 | `IMG.logo` |

**H5. The 404 page is raw JSON.** `GET /definitely-not-a-page` returns
`{"detail":"Not Found"}`, unstyled, with no route back into the site.

**H6. No Open Graph, Twitter card or canonical tags on any page.** Zero across
`portal.html`, `index.html`, `validation.html`, `inverse.html`,
`methodology.html`, `piston/index.html` and `pro/index.html`. Every daslabs.uk
link shared on LinkedIn renders a bare preview with no title card, no description
and no image, which directly undercuts the launch posts. `index.html` also has no
meta description.

**H7. Both `.woff` and `.woff2` of the same face are downloaded.** 83 KB and
48 KB respectively on every `/lab/` load, 131 KB for one typeface. Every browser
released in the last decade takes woff2; the woff is pure duplication.

**H8. The 3D iframe's `loading="lazy"` defers nothing.** It sits in the hero
(`index.html:278`), inside the initial viewport, so it loads immediately. The
`/lab/` transfer is identical with and without scrolling, which is how this was
confirmed. The attribute reads as an optimisation but is inert where it is.

### Medium

**M1. HEAD returns 405** on `/`, `/validation/`, `/inverse/`, `/piston/` and
`/api`. Only the `/lab/` static mount answers it. FastAPI's `@app.get` registers
GET alone, and uptime monitors, link checkers and some crawlers try HEAD first.

**M2. 94 form controls have no accessible name**: 51 on `/lab/`, 24 on
`/inverse/`, 19 on `/piston/`. Examples include `#presetSelect`, `#altitude_m`,
`#mach` and every PistonLab range slider. No `label for`, no `aria-label`.

**M3. Heading structure.** `/lab/` has three `h1` elements; `/` has none.

**M4. 21 canvas elements have no text fallback or `aria-label`** (16 on `/lab/`,
4 on `/piston/`, 1 on `/validation/`). Every plot is invisible to a screen
reader.

**M5. No security headers.** No HSTS, `X-Content-Type-Options`,
`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` or CSP is set anywhere
in `app/`.

**M6. No `robots.txt` and no `sitemap.xml`.** Both 404 in production.

**M7. The 3D viewer never pauses.** `viewer3d.js` has no `IntersectionObserver`
and no `visibilitychange` handler, so the render loop keeps running while the
canvas is scrolled out of view. Hidden tabs are throttled by the browser anyway;
the scrolled-away case is not.

**M8. `/validation/` CLS is 0.066**, above the 0.05 target. The stat cards and
the parity plot arrive after the surrounding text.

**M9. GLB files are served as `application/octet-stream`** rather than
`model/gltf-binary`.

**M10. `main` landmark missing** on `methodology.html`, `pro/index.html` and the
privacy page.

### Low

**L1.** The Plausible script carries no `integrity` attribute. Noted for
completeness only: a CDN script that auto-updates cannot carry a stable SRI hash
without self-hosting it.

**L2.** The cache middleware tests `request.url.query.startswith("v=")`
(`app/main.py:228`), so a URL where `v` is not the first query parameter silently
loses its immutable cache.

## Fix order

1. C1, compression. Two lines, no visual risk.
2. H3 caching and H2 minified build. Both are asset swaps, no code logic.
3. H6 and H5. Metadata and an error page, no effect on existing behaviour.
4. M1, M5, M6, M9. Server-side, independently testable.
5. H4. Real CSS work and the only item here that can change how the site looks.
6. M2, M3, M4, M10. Accessibility markup.

## Not touched

- No physics or numerical defect was found. The one thing worth flagging is not
  a bug: the validation library reports a one-sided +19.2 percent bias with a 95
  percent interval of +16.9 to +21.3, and that is deliberate, documented and
  tested behaviour.
- The phone consoles are gated behind a development notice on purpose. The
  responsive faults in H4 are at tablet and landscape widths, which are not
  gated, so they are genuine; no fix proposed here re-opens the phone build.
