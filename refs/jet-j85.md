# GE J85-21 (Northrop F-5E)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | turbojet | - |
| Inlet or fan diameter | 0.45 m | published |
| HP compressor stages | 9 | published |
| HP turbine stages | 2 | published |
| HP spool speed | 16500 rpm | published, approximate 100 % speed |
| Fan hub/tip ratio | 0.42 | estimated |
| Fuel nozzles | 12 | estimated |
| Variable stator rows | 4 | estimated |
| Cycle inputs | altitude_m=0, mach=0.0, mass_flow_air_kg_s=24, compressor_pressure_ratio=8.3, turbine_inlet_temperature_K=1250, afterburner_exit_temperature_K=1900 | cruise-point values from the PropulsionLab case studies |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** A single-spool afterburning turbojet: 9 axial compressor stages driven by a 2-stage turbine, then a reheat pipe and a variable nozzle.
