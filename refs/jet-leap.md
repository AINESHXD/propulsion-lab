# CFM LEAP-1A (Airbus A320neo)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | turbofan | - |
| Inlet or fan diameter | 1.98 m | published |
| Fan blades | 18 | published |
| Booster (LP compressor) stages | 3 | published |
| HP compressor stages | 10 | published |
| HP turbine stages | 2 | published |
| LP turbine stages | 7 | published |
| LP spool speed | 3894 rpm | published, approximate 100 % speed |
| HP spool speed | 16645 rpm | published, approximate 100 % speed |
| Fan hub/tip ratio | 0.28 | estimated |
| Fan chord / diameter | 0.2 | estimated |
| Fuel nozzles | 19 | estimated |
| Variable stator rows | 4 | estimated |
| LP turbine radius growth | 1.55 | estimated |
| Cycle inputs | nozzle_configuration=separate, altitude_m=10500, mach=0.78, total_mass_flow_air_kg_s=360, bypass_ratio=10.0, fan_pressure_ratio=1.5, core_compressor_pressure_ratio=30, turbine_inlet_temperature_K=1600 | cruise-point values from the PropulsionLab case studies |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** 3D-woven carbon fan blades with titanium leading edges; 7-stage LP turbine for the slow, large fan.
