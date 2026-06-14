# PistonLab — One-Month Day-by-Day Build Plan

> **Status:** Living document. Update at the end of each day.
> **Progress:** Days 1–4 done. Python crank-angle first-law solver
> (`app/engine_core/piston/`: `geometry` slider-crank V(θ), `wiebe` finite
> heat release, `cycle` second-order midpoint integrator, `heat_transfer`
> Woschni wall loss) **+ `friction` Chen-Flynn FMEP and the indicated→brake
> split (Day 4)**. Energy closes to machine precision; finite-burn η below the
> air-standard ceiling. Brake numbers now reported (BMEP, brake torque/power,
> mechanical efficiency, BSFC): brake always below indicated, FMEP rises with
> speed and peak pressure, mechanical efficiency falls with rpm
> (93%→87% over 1500→7000 rpm). Nominal ~62 kW / 199 N·m, BSFC ~190 g/kWh.
> **44 PistonLab tests** (past the Week-2 gate of 22). Still fully gated.
> **Owner:** Solo developer, mechanical-engineering undergraduate.
> **Goal:** Turn the air-standard *scaffold* into a **credible reciprocating-engine
> simulator** — the DAS LABS sibling to PropulsionLab — over ~20 working days, without
> diluting PropulsionLab. Stays gated behind the portal's "coming soon" until the end.

---

## Guiding principles (inherited from PropulsionLab)

1. **Depth over breadth.** Air-standard η = 1 − 1/r^(γ−1) is a homework formula. The month
   is about everything *past* it: finite burn, heat loss, friction, aspiration, real fuels.
2. **Every feature lands behind a green pytest.** Python is the source of truth.
3. **Honesty is a feature.** Indicated vs *brake* numbers are clearly separated; every
   assumption is stated; nothing is calibrated to fake a match to a real engine.
4. **No scope creep.** The 3D viewing suite and variable valve timing are explicitly
   parked for *after* this month (see "Deferred").
5. **PropulsionLab comes first.** PistonLab work never blocks a PropulsionLab launch task.

## Test gate ladder

Start: **5 PistonLab tests** (route + page contract). Each week raises the floor.

| Week end | Min PistonLab tests | New coverage |
|---|---|---|
| W1 | 14 | Wiebe burn, crank-angle integrator, wall heat loss, friction/FMEP, pumping |
| W2 | 22 | aspiration (NA/turbo/SC), fuel thermochem, knock/smoke limits, API endpoints |
| W3 | 28 | preset sanity, sweep/dyno curves, engine comparison |
| W4 | 34 | validation cases, tutorial/help contract, portal-gating flip |

## Already done (the scaffold — Day 0)

- Air-standard **Otto / Diesel / Dual** solver, client-side, with closed-form efficiency
  cross-check.
- Live **P–V and T–s** canvas diagrams, state-point table, indicated power/torque/MEP from
  real bore/stroke/cylinder/rpm geometry.
- Four presets, black/amber theme, honest "ideal air-standard" caveat.
- Served at `/piston/`; **not** linked from the portal (still "coming soon").
- 5 pytests; physics hand-verified (Otto r=10 → 60.2%).

---

# Part 1 — The day-by-day

## Week 1 — Real combustion (textbook toy → credible engine)

**Day 1 — Wiebe finite heat release.** Replace instantaneous heat addition with a
crank-angle burn fraction `x(θ) = 1 − exp(−a·((θ−θ_soc)/Δθ)^(m+1))`. Inputs: start of
combustion, burn duration, form factors.
*Verify:* integrated heat equals `q_in`; resulting η is **below** the air-standard ceiling.

**Day 2 — Crank-angle cycle integrator.** Slider-crank volume `V(θ)` from bore/stroke/rod
ratio; march the first law `dU = δQ − p·dV` over 720°. This is the engine that makes the
P–V loop *physical* instead of four straight segments.
*Verify:* closed cycle returns to its start state within tolerance; net work from the loop
area matches `q_in − q_out`.

**Day 3 — Wall heat transfer.** Add convective loss to the cylinder walls with a
Woschni-style heat-transfer coefficient and a wall-temperature input.
*Verify:* efficiency falls monotonically as the heat-transfer multiplier rises; the energy
balance (fuel = work + exhaust + wall loss) closes to machine precision.

**Day 4 — Friction & FMEP → brake numbers.** Chen-Flynn-style friction mean effective
pressure (rubbing + load + pumping terms). Introduce the **indicated vs brake** split:
BMEP, brake torque, brake power, BSFC.
*Verify:* brake < indicated always; FMEP rises with speed and peak pressure.

**Day 5 — Pumping loop (part-load SI).** Model the intake/exhaust strokes so a throttled
spark engine shows the negative pumping loop and its efficiency penalty at part load.
*Verify:* throttling reduces brake efficiency; wide-open vs part-load behave correctly.
**Gate: 14 tests.**

## Week 2 — Aspiration, fuels, backend

**Day 6 — Aspiration.** Naturally aspirated / turbocharged / supercharged: boost pressure
sets intake density; a supercharger debits crank work, a turbo (first cut) does not.
*Verify:* boost raises IMEP and power; the supercharger's parasitic loss shows in brake.

**Day 7 — Fuel thermochemistry.** Real air-fuel ratio, lower heating value per fuel
(gasoline / diesel), equivalence ratio λ → fuelling drives `q_in` instead of a raw kJ/kg.
*Verify:* stoichiometric AFR ≈ 14.7 (gasoline) / 14.5 (diesel); a λ sweep is sane.

**Day 8 — Operating limits.** SI **knock** ceiling (compression ratio × boost vs octane)
and CI **smoke/AFR** limit, surfaced as *flagged warnings*, not hard failures.
*Verify:* the knock flag fires at high CR + boost; the smoke flag fires when over-fuelled.

**Day 9 — Python backend core.** `app/engine_core/piston/` module + FastAPI endpoints
(`/piston/simulate`, `/piston/sweep`) mirroring PropulsionLab; Pydantic schemas.
*Verify:* endpoint smoke tests green; Python is the source of truth the JS will mirror.

**Day 10 — Real-engine presets.** Honda B16 (NA petrol), VW 1.9 TDI (turbo diesel), a
turbo petrol, a truck diesel — each as **knob settings + metadata** (layout, cylinders).
*Verify:* every preset solves; brake power/torque land in an honest band vs published.
**Gate: 22 tests.**

## Week 3 — Frontend depth & tooling

**Day 11 — Wire the deep physics to the console.** Port the crank-angle solver to JS (or
call the API), so the live P–V loop shows the *real* rounded burn and pumping loop.
*Verify:* console P–V matches the Python loop; no console errors.

**Day 12 — Brake-centric readouts.** Add BMEP, BSFC, volumetric efficiency, AFR/λ, boost,
and the indicated-vs-brake distinction to the results panel.
*Verify:* numbers track the backend; UI updates live on every input.

**Day 13 — The dyno curve.** Sweep rpm (and CR / boost / λ) to draw **torque & power vs
rpm** — the most relatable output a car person wants.
*Verify:* curve shape is physical (torque peak, power peak higher up); sweep endpoint test.

**Day 14 — Engine comparison.** Petrol vs diesel, NA vs turbo, side by side at their own
operating points.
*Verify:* comparison renders; cross-family caveats shown.

**Day 15 — Preset browser by taxonomy.** Families **petrol / diesel**, then aspiration,
with layout + cylinder count as *metadata* (not separate physics — per the design call).
*Verify:* selecting a preset loads its knobs; metadata displayed honestly.
**Gate: 28 tests.**

## Week 4 — Honesty, validation, polish, portal

**Day 16 — Validation page.** Model vs published brake power/torque for 2–3 real engines,
with **stated assumptions and honest error bands** — no curve-fitting to force a match.
*Verify:* page builds; deltas are reported, not hidden.

**Day 17 — Assumptions & per-feature help.** A clear "what you're looking at" panel and
ⓘ info buttons (mirroring PropulsionLab) explaining each feature and where it's used.
*Verify:* help contract test (buttons/modals present).

**Day 18 — Docs & test floor.** `PISTONLAB_ROADMAP` honest status (done / partial / not
claimed), README section, raise the pytest floor.
*Verify:* **Gate: 34 tests.**

**Day 19 — Tutorial, mobile, copy.** Reuse the spotlight-tour pattern for a genuine
walkthrough; responsive pass; de-AI copy sweep (commas, no em-dashes).
*Verify:* tour steps track; mobile layout holds at 360 px.

**Day 20 — Portal flip & launch-ready.** Swap the portal's PistonLab card from
"coming soon" to **live**, link `/piston/`, full QA sweep in a real browser, deploy.
*Verify:* portal links the live console; all endpoints 200; no console errors. **Launch.**

---

# Part 2 — Deferred (explicitly NOT this month)

These are good ideas parked to protect the month's scope:

- **3D viewing suite** — animated slider-crank driven by the *same* crank-angle kinematics,
  4-stroke walkthrough synced to the P–V marker, inline/V/boxer layouts, turbo. This is the
  differentiator and a whole milestone on its own (≈ a second month).
- **Variable valve timing / Atkinson-Miller** — a valve-strategy *feature toggle*, not a
  family.
- **Multi-cylinder firing order & balance visualiser** — belongs with the 3D suite.

# Part 3 — CV positioning

One honest line per capability, the way a reviewer reads it:

- "Crank-angle-resolved first-law engine cycle with **Wiebe** combustion, **Woschni** wall
  heat transfer, and a **friction/FMEP** model separating indicated and brake performance."
- "Aspiration (NA / turbo / supercharged) and real fuel thermochemistry with knock and
  smoke limits."
- "From-scratch Python solver behind a tested FastAPI; browser console with live P–V/T–s
  and dyno curves; validated against published engine data with stated error bands."

That reads as *thermodynamics + numerical methods + honest engineering*, which is exactly
the signal a mechanical-engineering CV wants — and it pairs with PropulsionLab to show a
**platform**, not a one-off.

# Explicitly not claimed (until earned)

- No manufacturer-level validation; reference deltas are reported, never fabricated.
- Everything is reduced-order and educational. Brake numbers are model estimates, not dyno
  readings.
