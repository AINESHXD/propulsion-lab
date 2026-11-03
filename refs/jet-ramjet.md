# Axisymmetric ramjet (Mach 2.2 cruise)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | ramjet | - |
| Inlet or fan diameter | 0.5 m | estimated |
| Fuel nozzles | 16 | estimated |
| spike_half_angle_deg | 22 | estimated |
| gutters | 2 | estimated |
| fuel_nozzles | 16 | estimated |
| Cycle inputs | solver defaults | solver defaults |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** No moving parts: the spike's shocks compress the air, V-gutters hold the flame, a convergent-divergent nozzle accelerates it. A representative layout.

**Not a specific engine.** This is a representative layout of its type, with no single real engine behind it.
