# Audi 2.5 TFSI (RS3 (8V))

These are the figures the 3D model is built from, and where they came from. The model is representative: it follows the engine's public layout and numbers, not the maker's drawings.

Each number is marked as one of these:
- **published:** a figure from the maker's public data, recalled from that literature. Not re-checked against a document when this note was written.
- **estimated:** chosen to look right, with no public figure behind it.
- **solver:** the PropulsionLab or PistonLab model's output at the gallery inputs.

| Quantity | Value | Source |
|---|---|---|
| Bore x stroke | 82.5 x 92.8 mm | published |
| Capacity | 2480 cc | published (tests check the solver reproduces it to 0.5 %) |
| Cylinders and layout | 5 (inline) | published |
| Compression ratio | 10 | published |
| Rod ratio | solver default 3.5 | estimated (solver default) |
| Valvetrain | dohc | published |
| Oil system | wet | published |
| Balance shafts | 0 | published |
| Block alloy | aluminium | published |
| Speed | 5850 rpm | near published peak-power speed |
| Power, torque, pressures | - | solver (PistonLab's model, not the maker's data) |

**Layout note.** Drawn with bucket followers; the engine uses roller finger followers.
