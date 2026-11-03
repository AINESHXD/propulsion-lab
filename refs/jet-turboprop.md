# Free-turbine turboprop (regional airliner class)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Family | turboprop | - |
| Inlet or fan diameter | 0.5 m | estimated |
| Axial compressor stages | 3 | estimated |
| Centrifugal stages | 1 | estimated |
| HP turbine stages | 1 | estimated |
| Power turbine stages | 2 | estimated |
| HP spool speed | 31000 rpm | estimated |
| PT spool speed | 20000 rpm | estimated |
| Fan hub/tip ratio | 0.5 | estimated |
| Fuel nozzles | 14 | estimated |
| Variable stator rows | 1 | estimated |
| Cycle inputs | solver defaults | solver defaults |
| Casing radii | from annulus area at assumed axial Mach numbers, scaled to the diameter | solver + assumption (kin.js AX_MACH) |
| Swirl, turbulence, flame temperatures | Euler's equation; typical intensities; primary zone T4 + 450 K | solver + assumption |

**Layout note.** A gas generator (3 axial stages and a centrifugal impeller, driven by one turbine) feeds a free power turbine that turns the propeller through a reduction gearbox. A representative layout, not one maker's engine.

**Not a specific engine.** This is a representative layout of its type, with no single real engine behind it.
