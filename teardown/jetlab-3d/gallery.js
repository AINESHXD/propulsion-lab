// Real engines and representative layouts, as PropulsionLab solver inputs (gallery.json, which the tests also read).
// Fan diameters, stage and blade counts are published figures; spool speeds are approximate published 100% speeds.
// Cycle inputs are cruise-point values; the thermodynamics is PropulsionLab's own model, not the maker's data.
import data from './gallery.json';

export const GALLERY = data;
