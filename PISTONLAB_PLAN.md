# PistonLab — One-Month Day-by-Day Build Plan

> **Status:** Living document. Update at the end of each day.
> **Progress: Week 1 complete + Days 6-9 + console rebuild.** Python crank-angle
> first-law solver in `app/engine_core/piston/`: `geometry`, `wiebe`, `cycle`
> (midpoint integrator), `heat_transfer` (Woschni), `friction` (Chen-Flynn),
> pumping loop, `aspiration` NA / turbo / supercharged (Day 6), `fuel`
> thermochemistry (Day 7), and `limits` knock / smoke / lean (Day 8). **Day 9
> exposed it over HTTP** (`/piston/simulate`, `/piston/sweep` with Pydantic
> schemas in `app/schemas_piston.py`, gated from the public schema), and **the
> `/piston` console was rebuilt to PropulsionLab level** — a live client on the
> solver with the real P–V loop / P–θ / T–θ from the trace, the indicated→brake
> MEP ladder, knock/smoke badges, fuel & aspiration controls, real-engine
> presets, an rpm dyno curve and an SI/US toggle, in the DAS LABS design
> language (warm amber). Loss stack: finite burn + wall heat + friction +
> pumping; boost packs a denser charge so IMEP/power rise (NA 62 kW → boosted
> 120 kW at 1.8 bar). The turbo/super split is modelled honestly: a
> supercharger's belt compression power is debited from brake (super 110 kW =
> turbo 120 − 9.8 kW parasitic), a turbo (first cut) is not. **Fuelling is now
> physical:** pick a fuel (gasoline / diesel / ethanol / methanol) and an
> equivalence ratio φ, and the heat release follows from the fuel's chemistry
> (q = (φ/AFR_stoich)·LHV·η_comb) instead of a raw kJ/kg. Stoichiometric AFR is
> *derived* from the C/H/O mass balance and lands on the textbook numbers
> (gasoline 14.7, diesel 14.5, ethanol 9.0, methanol 6.4); λ = 1/φ; richer
> mixtures release more heat and IMEP, lean burn is more efficient. The raw-heat
> path is retained (fuel=None) and the fuel path provably reduces to it.
> **Operating limits are flagged, not fatal:** an SI knock proxy (end-gas
> autoignition vs an octane- and pressure-dependent threshold) fires at high
> CR/boost on low octane — gasoline is clear NA at CR 10.5 but knocks at CR 13
> or under 1.8 bar boost, while ethanol's octane downgrades the same point to a
> caution; a CI smoke proxy fires when a diesel is over-fuelled past φ≈0.7; lean
> SI mixtures flag misfire. A knocking point still returns a full result. Energy
> closes to machine precision; throttling lowers brake efficiency.
> **Custom engine builder (2026-07-26).** A branching wizard over the solver,
> plus the physics to back it. `layout.py` computes firing intervals and
> reciprocating balance from cylinder axes and crank phases — the classic
> results fall out rather than being tabulated (inline-4 leaves a unit secondary
> shaking force, inline-6 and V12 cancel everything, a boxer twin is
> force-balanced with a rocking couple, a 90 deg V6 is odd-fire at 90/150 and a
> 30 deg split pin brings it back to even, and a cross-plane crank cancels the
> secondary force a flat-plane V8 leaves). `valvetrain.py` moves the integration
> window off BDC: compression now starts at intake-valve close and expansion
> ends at exhaust-valve open, so the **effective** compression ratio diverges
> from the geometric one and Miller/Atkinson is a consequence of the geometry
> rather than a special mode. Breathing is valve-limited through Taylor's inlet
> Mach index (a reduced-order correlation, labelled as such), and exhaust
> restriction raises back-pressure and therefore PMEP. All of it is optional:
> omit the new inputs and the solver behaves exactly as before. **191 PistonLab
> tests, 496 total.** The console now runs the real solver; still gated behind
> the portal's "coming soon" (no portal link) until the Week-4 launch.
>
> Note: this pulls **variable valve timing** and the **firing-order / balance
> visualiser** forward from the Deferred list below, at the user's request.
>
> **Turbo back-pressure + residual gas (2026-07-26).** Two gaps the app used to
> disclose are now closed. A **turbocharger** no longer gets a free ride: the
> turbine's expansion ratio is solved from the turbo *shaft power balance*
> (`eta_m * W_turbine = W_compressor`), and the exhaust manifold sits that far
> above whatever is downstream, so back-pressure is charged to the pumping loop.
> Turbo still beats supercharger, but by the supercharger's parasitic load
> *minus* the turbo's pumping tax, and that identity closes to 1e-9. **Valve
> overlap** now does physical work instead of being a readout: burned gas left
> in the clearance volume is sized from the exhaust state, and overlap couples
> the intake/exhaust pressure ratio into it — boost scavenges it out (0.4% on a
> race cam at 1.8 bar), throttling draws it back in (35% on the same cam at
> 0.5 bar), which is exactly why a big cam pulls hard and idles terribly. The
> residual is hot (raises charge temperature at IVC) and already burned (only
> the fresh mass carries fuel), and the mixing closes algebraically so it costs
> one extra solve, not an iteration. **229 PistonLab tests, 534 total.**
>
> **Variable specific heats + two-zone combustion (2026-07-26).** The constant
> `gamma = 1.35` is gone. `thermo.py` carries cp(T) for air and for the products
> of PistonLab's own gasoline chemistry, fitted offline against **Cantera**
> (GRI-Mech 3.0) to better than 0.5% over 250-3500 K and hard-coded, so the
> solver has no runtime Cantera dependency; the tests re-validate against
> Cantera whenever it is importable. The integrator now marches **internal
> energy** and inverts for temperature, which conserves energy by construction
> even as composition shifts. Effect on an NA petrol engine: peak temperature
> **3342 -> 2805 K**, peak pressure **75.7 -> 62.9 bar**, indicated efficiency
> **46.3 -> 40.8%** — all moving into the band real engines occupy. The
> methodology card's "peak temperatures run optimistically high" caveat is
> retired.
>
> **Combustion is now two-zone.** Burned and unburned gas are tracked at a
> shared pressure: the unburned zone follows the exact variable-cp isentropic
> relation (`phi(T) - R ln p` conserved), its volume follows from the ideal-gas
> law, the burned zone takes the rest, and a secant on pressure closes the
> energy. Temperatures order correctly — burned 3056 K > bulk 2805 K > end-gas
> 1016 K. **Knock is now judged on the tracked end gas** instead of the
> isentropic proxy, so it responds to intercooling, boost *and* residual
> dilution raising the charge temperature at IVC, which the proxy structurally
> could not see. Real gas is on by default at the API layer. **279 PistonLab
> tests, 584 total.**
>
> Caveats carried forward: composition is **frozen** — dissociation is not
> modelled, so the burned-zone temperature (~3050 K) still reads a few hundred
> kelvin above the ~2800-3000 K a real charge reaches, and the turbine
> back-pressure model inherits some of that through the EVO temperature.
> Two-zone costs ~69 ms per solve against ~4 ms constant-gamma; fine
> interactively, noticeable on a multi-point sweep.
>
> **Cosmetic pass (2026-07-26).** The hero band had gone stale under the physics
> work — it claimed 18 solver parameters against an actual 49, and 4 loss models
> against 6 — so the stats, the hero copy and the meta description were all
> brought back in line, and "Fuels 4" was swapped for "Combustion zones 2". The
> **live engine now draws the flame front**: the trace carries burned *volume*
> fraction and both zone temperatures, so the chamber renders as a flame kernel
> growing from the plug with hot burned gas behind it and cool end-gas pushed to
> the periphery, each tinted against its own peak. Burned volume runs well ahead
> of burned mass (0.26 mass -> 0.53 volume) because burned gas is far less dense,
> which is what makes the sweep visible. When the knock flag fires the far
> corners of the chamber take a hot edge — which is exactly where knock starts.
> The **configuration card** had grown to 21 undifferentiated rows and is now
> grouped under *Architecture / Breathing & gas exchange / Gas model*.
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
