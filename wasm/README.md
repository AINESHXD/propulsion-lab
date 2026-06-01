# PropulsionLab WASM core

A Rust port of the reduced-order cycle core, compiled to WebAssembly so the
browser can run the physics directly (Month 3 of the plan). It runs alongside
the Python/FastAPI solver, which stays the source of truth; the WASM build is a
client-side accelerator with a Python fallback.

## Status

- **Day 61–62 (done):** crate + `wasm-pack` pipeline; the ISA atmosphere is
  ported with a native parity test against the Python reference (≤ 1e-9), and a
  browser smoke test confirms the module loads and matches.
- **Day 63+ (next):** port `compressor`, `turbine`, `combustor`, then the
  turbojet/turbofan orchestration, each behind a native parity test.

## Layout

```
wasm/propulsion-core/        Rust crate (cdylib + rlib)
  src/lib.rs                 ported physics + native parity tests
app/static/wasm/propulsion-core/   generated JS package (committed, served)
app/static/wasm/wasm-smoke.html    browser load + parity check
```

## Toolchain

The MSVC host linker is not required — this uses the **GNU** host toolchain,
which ships its own linker:

```bash
rustup toolchain install stable-x86_64-pc-windows-gnu --profile minimal
rustup target add wasm32-unknown-unknown --toolchain stable-x86_64-pc-windows-gnu
rustup default stable-x86_64-pc-windows-gnu
# wasm-pack: prebuilt binary from https://github.com/rustwasm/wasm-pack/releases
```

## Build

Native parity tests:

```bash
cd wasm/propulsion-core
cargo test
```

Generate the browser package into the static tree:

```bash
cd wasm/propulsion-core
wasm-pack build --release --target web \
  --out-dir ../../app/static/wasm/propulsion-core --out-name propulsion_core
```

Then open `http://127.0.0.1:8000/lab/wasm/wasm-smoke.html` — it loads the module
and prints the Rust-vs-Python parity error (expected < 1e-9).

Notes:
- `wasm-opt` (binaryen) is disabled in `Cargo.toml` so the build has no extra
  binary dependency; re-enable it for size optimisation once binaryen is local.
- The generated package is committed (no JS build step), consistent with the
  rest of the buildless frontend. The Rust `target/` directory is git-ignored.
