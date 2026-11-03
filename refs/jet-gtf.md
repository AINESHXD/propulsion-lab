# PW1100G GTF (Airbus A320neo)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | turbofan | - |
| Inlet or fan diameter | 2.06 m | published |
| Fan blades | 20 | published |
| Booster (LP compressor) stages | 3 | published |
| HP compressor stages | 8 | published |
| HP turbine stages | 2 | published |
| LP turbine stages | 3 | published |
| Fan gear ratio | 3.0625 | published |
| LP spool speed | 10047 rpm | published, approximate 100 % speed |
| HP spool speed | 22300 rpm | published, approximate 100 % speed |
| Fan hub/tip ratio | 0.3 | estimated |
| Fan chord / diameter | 0.19 | estimated |
| Fuel nozzles | 18 | estimated |
| Variable stator rows | 4 | estimated |
| LP turbine radius growth | 1.2 | estimated |
| Cycle inputs | nozzle_configuration=separate, altitude_m=10500, mach=0.78, total_mass_flow_air_kg_s=350, bypass_ratio=11.0, fan_pressure_ratio=1.45, core_compressor_pressure_ratio=31, turbine_inlet_temperature_K=1600 | cruise-point values from the PropulsionLab case studies |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** A 3.06:1 epicyclic gearbox lets the fan turn slowly while the LP turbine and booster run fast, so the LP turbine needs only 3 stages.
