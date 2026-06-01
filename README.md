# PropulsionLab

PropulsionLab is an educational and preliminary-performance gas turbine simulation platform
for students, lecturers, and early-stage aerospace learners. The long-term goal is to make
gas turbine thermodynamics easier to inspect, vary, explain, and eventually connect to
dashboards, reports, optimisation workflows, and real engine presets.

## Current scope

The core solver is a station-based, design-point turbojet cycle:

- 0: ambient / freestream static state
- 2: inlet / diffuser exit and compressor inlet stagnation state
- 3: compressor exit
- 4: combustor exit and turbine inlet
- 5: turbine exit and nozzle inlet
- 7: afterburner exit and nozzle inlet when reheat is enabled
- 9: nozzle exit

The API is built with FastAPI and Pydantic v2. The numerical model uses NumPy and keeps
the governing equations visible in small component modules. The frontend is vanilla
JS + Canvas/SVG with no build step, served by FastAPI from `app/static/`.

### What it does today

- **Five engine families** — turbojet (dry + afterburning), separate-flow turbofan,
  gas-generator turboprop, subsonic-combustion ramjet, supersonic-combustion scramjet.
- **Design-point analysis** — full station table (total/static T and P, Mach, velocity),
  thrust breakdown, TSFC, and educational efficiency estimates, with caution flags when
  an input is outside its physically sensible band.
- **Off-design matching** — a calibrate-once-then-match operating line for the turbojet
  (Newton–Raphson) and the two-spool turbofan (fixed-point on fuel-air ratio), holding
  the choked-turbine ratios and turbine corrected flow constant. Reproduces the design
  point exactly and scrubs thrust/TSFC down the throttle.
- **Mission integration** — fly a sequence of legs (altitude, Mach, throttle, duration);
  the engine is matched off-design at each leg and fuel is integrated over time.
- **Optional real-gas hot section** — a frozen-composition, variable-cp correction to
  turbine-exit and nozzle-exit temperatures using Cantera when it is installed. It is
  additive and off by default; the constant-cp station table is never altered.
- **Tooling** — single-parameter sweeps, engine comparison, T-s / P-v and performance
  charts, a branded PDF report, a stdlib-only Python API-client export, and shareable
  URLs that encode the full input deck.
- **Case studies** — original long-form write-ups of real engine families, each loadable
  straight into the turbofan simulator as a starting design point.

These solvers are useful for comparing architecture behaviour and trends. They are
**not** map-matched against a named engine — see "Validation and integrity" below.

## Assumptions

- Educational-level steady 1D cycle model
- Perfect gas model
- Constant cp/gamma in v1
- Different properties for air and combustion gas
- No compressor/turbine maps yet
- No detailed chemical equilibrium yet
- No blade-row aerodynamics yet
- No afterburner flame stability, cooling, or variable-area nozzle scheduling yet
- No heat transfer except through energy balances
- Not certified design software

## Validation and integrity

This project draws a deliberate line between two very different claims:

- **Conservation-law verification (done).** `app/validation.py` runs the solver and
  checks that its *own* outputs obey the governing balances — spool power balance,
  combustor energy balance, and thrust reconstruction from momentum + pressure terms.
  Residuals come back at machine precision (~1e-14). This proves the code is internally
  consistent with the model it claims to implement.
- **External-data validation (not claimed).** The model has **not** been matched against
  manufacturer or flight-test numbers for a named engine. The reference-case table in
  `validation.py` (`VALIDATION_CASES`) is intentionally left empty rather than populated
  with numbers that cannot be sourced and cited honestly.

In short: the numbers are physically meaningful and self-consistent for the reduced-order
model, and every quantity in the UI is either computed or clearly labelled as an estimate.
They are educational, not certification-grade, and the project never fabricates a reference
figure to look more validated than it is.

Run the checks with `pytest` (the suite includes the conservation cases).

## Equations used

ISA atmosphere, troposphere to 11 km:

```text
T = T_SL - L*h
P = P_SL * (T/T_SL)^(g0/(R*L))
rho = P/(R*T)
```

Lower stratosphere above 11 km:

```text
T = 216.65 K
P = P_11 * exp(-g0*(h-11000)/(R*T))
rho = P/(R*T)
```

Freestream:

```text
a = sqrt(gamma_air * R_air * T)
V0 = M*a
T0 = T*(1 + (gamma - 1)/2*M^2)
P0 = P*(1 + (gamma - 1)/2*M^2)^(gamma/(gamma - 1))
```

Compressor:

```text
P03 = P02 * pressure_ratio
T03s = T02 * pressure_ratio^((gamma_air - 1)/gamma_air)
T03 = T02 + (T03s - T02)/compressor_efficiency
w_c = cp_air * (T03 - T02)
```

Combustor:

```text
P04 = P03 * (1 - pressure_loss_fraction)
f = (cp_gas*T04 - cp_air*T03) / (eta_b*LHV - cp_gas*T04)
```

Turbine:

```text
(1+f)*cp_gas*(T04 - T05)*eta_mech = cp_air*(T03 - T02)
T05s = T04 - (T04 - T05)/eta_t
P05 = P04 * (T05s/T04)^(gamma_gas/(gamma_gas - 1))
```

Optional afterburner:

```text
P07 = P05 * (1 - afterburner_pressure_loss_fraction)
f_ab = (1+f_core)*cp_gas*(T07 - T05) / (eta_ab*LHV - cp_gas*T07)
f_total = f_core + f_ab
```

Nozzle:

```text
P_critical = P05 * (2/(gamma_gas+1))^(gamma_gas/(gamma_gas-1))
```

If choked, station 9 is set to Mach 1. If unchoked, the exit pressure is ambient and
the exit velocity comes from the ideal static temperature drop with nozzle efficiency.

Thrust:

```text
F_momentum = mdot_air*((1+f)*V9 - V0)
F_pressure = (P9 - P_ambient)*A9
F_net = F_momentum + F_pressure
TSFC = mdot_fuel/F_net
```

Efficiency estimates:

```text
jet_kinetic_power_change = 0.5*mdot_air*((1+f)*V9^2 - V0^2)
pressure_thrust_power = F_pressure*V0
jet_power_available = jet_kinetic_power_change + pressure_thrust_power
propulsive_power = F_net*V0
thermal_efficiency = jet_power_available/fuel_power
propulsive_efficiency = propulsive_power/jet_power_available
overall_efficiency = propulsive_power/fuel_power
```

## Install

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

Cantera (the optional real-gas dependency) is heavy and not required. If it is absent the
real-gas hot-section correction degrades gracefully and the constant-cp model is used.

## Run

From the `propulsion_lab` directory:

```bash
uvicorn app.main:app --reload
```

| What | URL |
| --- | --- |
| Frontend lab | `http://127.0.0.1:8000/lab/` |
| Interactive API docs | `http://127.0.0.1:8000/docs` |

The DAS LABS dashboard is served by FastAPI static files from `app/static/`.

## Test

```bash
pytest
```

The suite covers each engine solver, off-design matching, mission integration, the
real-gas path, the cycle diagrams, the Python export, and the conservation-law checks.

## Example request

```json
{
  "altitude_m": 10000,
  "mach": 0.8,
  "mass_flow_air_kg_s": 50.0,
  "compressor_pressure_ratio": 12.0,
  "compressor_efficiency": 0.86,
  "turbine_inlet_temperature_K": 1400.0,
  "turbine_efficiency": 0.88,
  "combustor_efficiency": 0.99,
  "combustor_pressure_loss_fraction": 0.05,
  "mechanical_efficiency": 0.99,
  "nozzle_efficiency": 0.95,
  "inlet_pressure_recovery": 0.98,
  "fuel_heating_value_J_kg": 43000000.0,
  "nozzle_exit_area_m2": null,
  "include_pressure_thrust": true
}
```

## Example response

Values will vary if inputs change. A default case returns this shape:

```json
{
  "thrust_N": 36040.17,
  "thrust_kN": 36.04,
  "specific_thrust_N_per_kg_s": 720.8,
  "fuel_air_ratio": 0.02572,
  "fuel_flow_kg_s": 1.2859,
  "TSFC_kg_per_N_s": 0.00003568,
  "TSFC_kg_per_kN_hr": 128.45,
  "exit_velocity_m_s": 595.64,
  "freestream_velocity_m_s": 239.55,
  "nozzle_choked": true,
  "nozzle_exit_pressure_Pa": 93491.03,
  "ambient_pressure_Pa": 26429.7,
  "pressure_thrust_N": 17469.64,
  "momentum_thrust_N": 18570.53,
  "thermal_efficiency_estimate": 0.2143,
  "propulsive_efficiency_estimate": 0.7287,
  "overall_efficiency_estimate": 0.1561,
  "station_table": {
    "0": {
      "station": 0,
      "name": "Ambient / freestream",
      "static_temperature_K": 223.15,
      "static_pressure_Pa": 26429.7,
      "stagnation_temperature_K": 251.7,
      "stagnation_pressure_Pa": 40287.85,
      "mach": 0.8,
      "velocity_m_s": 239.55
    }
  },
  "warnings": []
}
```

## Useful endpoints

Full, always-current list at `GET /` and `GET /docs`. Highlights:

**Design point**
- `POST /simulate/turbojet` · `/turbofan` · `/turboprop` · `/ramjet` · `/scramjet`
- `POST /simulate/{engine}/sweep` — single-parameter sweep
- `POST /compare/engines`

**Off-design, maps and mission**
- `POST /simulate/turbojet/off-design` · `POST /simulate/turbofan/off-design`
- `POST /simulate/turbojet/map-match` — running line converged on the compressor map
- `GET /maps/compressor` — synthetic compressor characteristic for the map viewer
- `POST /mission/turbojet` · `POST /mission/turbofan`

**Profiles, presets, exports**
- `POST /simulate/turbojet/from-profile`
- `POST /simulate/{engine_type}/from-preset/{preset_name}`
- `POST /reports/{engine_type}/pdf` — branded PDF report
- `POST /export/python` — stdlib-only Python API-client script
- `GET /presets`

## Graphs and reports

The `/lab/` frontend has a `Graphs & Reports` tab with:

- Station stagnation temperature
- Station stagnation pressure
- T-s diagram with process labels
- P-v diagram
- Sweep thrust
- Sweep TSFC
- Efficiency estimates
- Momentum and pressure thrust breakdown

The `Download PDF` button calls `POST /reports/turbojet/pdf` with the current input
deck and returns a branded DAS LABS performance report with input summary, station
table, warnings, assumptions, and educational disclaimer.

The dashboard station table includes total/static temperature and pressure, Mach,
velocity, notes, row hover highlighting, and CSV export.

The compare tab currently compares turbojet dry and reheat parameter sets only. It does
not claim completed turbofan, ramjet, or scramjet validation.

## Inlet area mass flow

By default, air mass flow is a direct input. For inlet sizing experiments, enable
`use_inlet_area_mass_flow` and provide `inlet_capture_area_m2`. The model estimates:

```text
mdot_air = rho_ambient * V0 * inlet_capture_area
```

This is a first-order capture-area estimate, not an inlet distortion or boundary-layer
model.

## Custom jet profiles

The frontend can save custom jet profiles in browser local storage. The backend also
accepts one-off custom profile simulations with `POST /simulate/turbojet/from-profile`.
Profiles are not persisted on the server yet.

```json
{
  "name": "My Custom Reheat Jet",
  "engine_type": "afterburning_turbojet",
  "default_inputs": {
    "engine_variant": "afterburning_turbojet",
    "altitude_m": 6000,
    "mach": 0.85,
    "mass_flow_air_kg_s": 42,
    "compressor_pressure_ratio": 10,
    "turbine_inlet_temperature_K": 1350,
    "afterburner_exit_temperature_K": 1800
  }
}
```

## Example sweep request

```json
{
  "base_input": {
    "altitude_m": 10000,
    "mach": 0.8,
    "mass_flow_air_kg_s": 50,
    "compressor_pressure_ratio": 12,
    "turbine_inlet_temperature_K": 1400
  },
  "sweep_parameter": "compressor_pressure_ratio",
  "values": [6, 10, 14, 18]
}
```

## My first study

Use the frontend lab at `http://127.0.0.1:8000/lab/`.

1. Choose the `PLab-01 Student Turbojet` preset.
2. Run the baseline simulation and record `thrust_kN` and `TSFC_kg_per_kN_hr`.
3. Run a sweep with:

```json
{
  "sweep_parameter": "compressor_pressure_ratio",
  "values": [6, 8, 10, 12, 14, 16]
}
```

4. Compare how thrust and TSFC change as compressor pressure ratio rises.

Conclusion template to rewrite:

```text
In my first PropulsionLab study, increasing compressor pressure ratio from __ to __ made thrust __ and TSFC __. The nozzle was __ across the cases. My explanation is that the compressor raised the core pressure and temperature before combustion, changing the available nozzle expansion and fuel required for the selected turbine inlet temperature.
```

## Deployment

Production artifacts (Docker, Fly.io, Gunicorn/Uvicorn) and a step-by-step guide live in
[`DEPLOY.md`](DEPLOY.md). The production image deliberately excludes Cantera to stay light;
the real-gas path degrades gracefully without it.

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) for what is done, in progress, and planned. In short: the
five engine families, off-design matching, mission integration, the optional real-gas
hot section, and the reporting/export tooling are in place; component maps, full real-gas
chemistry through the whole cycle, and optimisation are the main planned steps.

## License

Released under the [MIT License](LICENSE).

## Sponsor

If PropulsionLab is useful to you, you can support its development:
[💛 Sponsor @AINESHXD on GitHub](https://github.com/sponsors/AINESHXD)
