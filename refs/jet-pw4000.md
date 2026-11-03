# PW4000-94 (Boeing 747-400, 767)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | turbofan | - |
| Inlet or fan diameter | 2.37 m | published |
| Fan blades | 38 | published |
| Booster (LP compressor) stages | 4 | published |
| HP compressor stages | 11 | published |
| HP turbine stages | 2 | published |
| LP turbine stages | 4 | published |
| LP spool speed | 3600 rpm | published, approximate 100 % speed |
| HP spool speed | 10450 rpm | published, approximate 100 % speed |
| Fan hub/tip ratio | 0.34 | estimated |
| Fan chord / diameter | 0.13 | estimated |
| Fuel nozzles | 24 | estimated |
| Variable stator rows | 5 | estimated |
| Cycle inputs | nozzle_configuration=separate, altitude_m=10000, mach=0.8, total_mass_flow_air_kg_s=800, bypass_ratio=5.5, fan_pressure_ratio=1.6, core_compressor_pressure_ratio=20, turbine_inlet_temperature_K=1500 | cruise-point values from the PropulsionLab case studies |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** Narrow-chord titanium fan of 38 blades, of the generation before wide-chord fans.
