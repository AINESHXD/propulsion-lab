# Rolls-Royce Trent XWB (Airbus A350)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | turbofan | - |
| Inlet or fan diameter | 3.0 m | published |
| Fan blades | 22 | published |
| IP compressor stages | 8 | published |
| HP compressor stages | 6 | published |
| HP turbine stages | 1 | published |
| IP turbine stages | 1 | published |
| LP turbine stages | 6 | published |
| LP spool speed | 2700 rpm | published, approximate 100 % speed |
| IP spool speed | 8000 rpm | published, approximate 100 % speed |
| HP spool speed | 12500 rpm | published, approximate 100 % speed |
| Fan hub/tip ratio | 0.29 | estimated |
| Fan chord / diameter | 0.21 | estimated |
| Fuel nozzles | 20 | estimated |
| Variable stator rows | 3 | estimated |
| LP turbine radius growth | 1.45 | estimated |
| Cycle inputs | nozzle_configuration=separate, altitude_m=10500, mach=0.85, total_mass_flow_air_kg_s=1350, bypass_ratio=9.3, fan_pressure_ratio=1.5, core_compressor_pressure_ratio=33, turbine_inlet_temperature_K=1650 | cruise-point values from the PropulsionLab case studies |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** Three spools: the fan on the LP shaft, an 8-stage IP compressor on the IP shaft, a 6-stage HP compressor on the HP shaft; each turned by its own turbine.
