# Honda CRF450R (motocross single)

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Bore x stroke | 96.0 x 62.1 mm | published |
| Capacity | 449 cc | published (tests check the solver reproduces it to 0.5 %) |
| Cylinders and layout | 1 (single) | published |
| Compression ratio | 13.5 | published |
| Rod ratio | solver default 3.5 | estimated (solver default) |
| Valvetrain | dohc | published |
| Oil system | wet | published |
| Balance shafts | 1 | published |
| Block alloy | aluminium | published |
| Speed | 9000 rpm | near published peak-power speed |
| Power, torque, pressures | - | solver (PistonLab's model, not the maker's data) |

**Layout note.** Drawn as DOHC; the real engine uses Honda's Unicam single cam with an exhaust rocker. One primary balance shaft.
