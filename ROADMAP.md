# PropulsionLab roadmap

A living view of where the project is. It is honest about what is finished, what is
partial, and what is only planned — including the things deliberately *not* claimed yet.

## Done

- **Core turbojet cycle** — station-based, dual-cp (cold/hot) perfect-gas solver with
  dry and afterburning variants, choked/unchoked convergent nozzle, and a full station
  table (total/static T and P, Mach, velocity).
- **Five engine families** — turbojet, separate-flow turbofan, gas-generator turboprop,
  subsonic-combustion ramjet, supersonic-combustion scramjet.
- **Bleed and turbine cooling** — HPC-exit bleed and HPT-inlet cooling fractions plumbed
  through the shared secondary-air path.
- **Variable-cycle / 3-stream turbofan** — an optional outer bypass stream with a mode
  switch (high-thrust = closed, high-efficiency = open). Opening it raises total airflow
  and effective bypass ratio, lowering specific thrust and SFC; the stream is pumped by
  the fan and debited from the LP turbine, so the gain is energy-consistent, not free.
- **Off-design matching** — calibrate-once-then-match operating line for the turbojet
  (Newton–Raphson) and the two-spool turbofan (fixed-point on fuel-air ratio), holding
  the choked-turbine ratios and turbine corrected flow constant. Reproduces the design
  point exactly.
- **Mission integration** — leg-by-leg flight (altitude, Mach, throttle, duration) with
  off-design matching per leg and fuel integrated over time.
- **Optional real-gas hot section** — frozen-composition, variable-cp turbine/nozzle
  temperatures via Cantera when installed; additive and off by default.
- **Conservation-law verification** — automated checks that the solver's own outputs obey
  spool-power, combustor-energy, and thrust-reconstruction balances to machine precision.
- **Tooling** — single-parameter sweeps, engine comparison, T-s / P-v and performance
  charts, branded PDF report, stdlib-only Python API-client export, shareable URL state.
- **Case studies** — ten original long-form engine write-ups (JT8D through Trent XWB)
  plus a crawlable index at `/lab/case-studies/`, each loadable into the turbofan
  simulator as a starting design point.
- **Input hardening** — geometric-area and other inputs are validated; invalid values are
  rejected and unusual-but-valid ones are flagged rather than silently producing garbage.
- **Deployment** — Docker + Fly.io + Gunicorn/Uvicorn artifacts and a deploy guide.

## In progress / partial

- **Component maps** — beta-line compressor and turbine maps (bilinear lookup, analytic
  gradients, 2-D inverse) are implemented, and a turbojet running line now converges on the
  compressor map (`POST /simulate/turbojet/map-match`) with the map plotted in the console.
  The maps are currently *synthetic, illustrative* characteristics; sourcing verified
  datasets (and extending map matching to the two-spool turbofan) is the remaining work.
- **WebAssembly cycle core** — a Rust crate (`wasm/propulsion-core`) compiled to WASM via
  `wasm-pack`, running client-side alongside the Python solver. The ISA atmosphere,
  compressor, combustor, turbine and the full **turbojet and separate-flow turbofan cycle
  orchestration** are ported, each behind a native parity test (components ≤ 1e-9,
  cycles ≤ 1e-6). A frontend integration layer (`wasm-engine.js`) runs cycles locally in
  WASM with automatic fallback to the Python API for unsupported configs or load failures,
  and a benchmark page (`wasm-bench.html`) reports the WASM-vs-API latency and parity.
  Python remains the source of truth. Next: optional binaryen size-optimisation and a
  runtime toggle wired into the main console.
- **3D engine viewer** — a Three.js viewer (`viewer3d.html`, Three.js vendored locally,
  no CDN) that builds procedural turbojet/turbofan geometry from cycle parameters: the
  bypass ratio drives the fan and nacelle size, compressor PR drives the compressor length,
  and TIT drives the combustor glow. Orbit controls, station-label billboards with
  click-to-inspect, and a WebGL-availability fallback to the 2D console. Remaining:
  Playwright e2e (needs Node) and deeper geometry fidelity.
- **Copy and voice pass** — tightening prose across the site toward a consistent,
  human register.

## Planned

- **Verified map datasets** — replace the synthetic maps with sourced, citable compressor
  and turbine characteristics, and converge surge margin against them.
- **Map matching on the turbofan** — extend the on-map running line to the two-spool fan +
  HPC, including a bypass-ratio shift driven by a fan map.
- **Real-gas chemistry everywhere** — variable-cp / equilibrium products through the whole
  cycle, not just the optional hot-section correction.
- **Variable-geometry** — variable-area nozzle scheduling and afterburner flame-stability
  limits (mixed-flow exhaust and the variable-cycle third stream are done).
- **Optimisation and batch** — multi-parameter sweeps and design optimisation as
  background jobs with exportable results.
- **Transient spool dynamics** and, further out, ML surrogate models.

## Explicitly not claimed

- **Manufacturer-level validation.** The model has not been matched to flight-test or
  manufacturer data for a named engine. Reference cases are left empty rather than filled
  with figures that cannot be sourced and cited. See "Validation and integrity" in the
  README.
- **Certification-grade results.** Everything is reduced-order and educational.

## Open questions

- **License.** Currently closed-source while the project is evaluated; an open-core vs
  closed decision is pending. No license file is committed yet by design.
- **PropulsionLab Pro.** A higher-fidelity, server-side direction (component maps, full
  chemistry, batch/optimisation, an authenticated API) is sketched at `/pro` as a preview
  only — no accounts, payments, or data collection exist.
