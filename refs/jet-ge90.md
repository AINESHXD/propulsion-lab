# GE90-115B (Boeing 777-300ER)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | turbofan | - |
| Inlet or fan diameter | 3.25 m | published |
| Fan blades | 22 | published |
| Booster (LP compressor) stages | 4 | published |
| HP compressor stages | 9 | published |
| HP turbine stages | 2 | published |
| LP turbine stages | 6 | published |
| LP spool speed | 2550 rpm | published, approximate 100 % speed |
| HP spool speed | 9332 rpm | published, approximate 100 % speed |
| Fan hub/tip ratio | 0.3 | estimated |
| Fan chord / diameter | 0.21 | estimated |
| Fuel nozzles | 24 | estimated |
| Variable stator rows | 4 | estimated |
| LP turbine radius growth | 1.5 | estimated |
| Cycle inputs | nozzle_configuration=separate, altitude_m=10500, mach=0.84, total_mass_flow_air_kg_s=1350, bypass_ratio=8.5, fan_pressure_ratio=1.55, core_compressor_pressure_ratio=27, turbine_inlet_temperature_K=1600 | cruise-point values from the PropulsionLab case studies |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** Swept carbon-composite fan blades; the largest turbofan in service until the GE9X.
