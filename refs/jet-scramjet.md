# Scramjet (Mach 5, hydrogen)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | scramjet | - |
| Inlet or fan diameter | 0.7 m | estimated |
| width_m | 0.7 | estimated |
| ramp_angles_deg | [6, 6] | estimated |
| forebody_m | 3.0 | estimated |
| isolator_m | 0.6 | estimated |
| combustor_m | 1.0 | estimated |
| nozzle_m | 2.0 | estimated |
| struts | 3 | estimated |
| Cycle inputs | solver defaults | solver defaults |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** Two forebody ramps and the cowl compress the air while it stays supersonic; struts inject the fuel; the vehicle's underside is the nozzle. A representative 2D layout in the X-43 family.

**Not a specific engine.** This is a representative layout of its type, with no single real engine behind it.
