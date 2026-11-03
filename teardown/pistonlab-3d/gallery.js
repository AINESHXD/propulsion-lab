// Real engines, as PistonLab inputs (gallery.json, which the tests also read). Bore, stroke, compression ratio and
// layout are the published figures; the speed is near each engine's published peak-power speed. Rod ratio (rod length
// over crank radius) is given only where the rod length is published; elsewhere the solver's default of 3.5 stands.
// Boost pressures are approximate stock values. The thermodynamics is PistonLab's own model at these inputs, not the
// maker's data.
import data from './gallery.json';

export const GALLERY = data;
export const ROD_PUBLISHED = new Set(data.filter((g) => g.rod_ratio_published).map((g) => g.id));
