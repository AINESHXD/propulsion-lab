# CFM56-7B (Boeing 737 NG)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | turbofan | - |
| Inlet or fan diameter | 1.55 m | published |
| Fan blades | 24 | published |
| Booster (LP compressor) stages | 3 | published |
| HP compressor stages | 9 | published |
| HP turbine stages | 1 | published |
| LP turbine stages | 4 | published |
| LP spool speed | 5380 rpm | published, approximate 100 % speed |
| HP spool speed | 15183 rpm | published, approximate 100 % speed |
| Fan hub/tip ratio | 0.31 | estimated |
| Fan chord / diameter | 0.17 | estimated |
| Fuel nozzles | 20 | estimated |
| Variable stator rows | 4 | estimated |
| Cycle inputs | nozzle_configuration=separate, altitude_m=10000, mach=0.78, total_mass_flow_air_kg_s=350, bypass_ratio=5.2, fan_pressure_ratio=1.6, core_compressor_pressure_ratio=22, turbine_inlet_temperature_K=1530 | cruise-point values from the PropulsionLab case studies |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** Two spools: fan and 3-stage booster on the LP shaft, 9-stage HP compressor on the HP shaft.
