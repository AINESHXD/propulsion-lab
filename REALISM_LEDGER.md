# Realism ledger

Audit of the two engine viewers against `EXTREME_REALISM.md`, before any change, then updated phase by phase.

- **Aero viewer:** JetLab 3D, `/jet/3d/`, source `teardown/jetlab-3d/`.
- **Automotive viewer:** PistonLab 3D, `/piston/3d/`, source `teardown/pistonlab-3d/`.

**Stack.** Both pages are three.js r186 on WebGL2, built with the teardown skill into one offline HTML file each.

**Assets.** All geometry is generated in code from the cycle solve and published hardware data. There are no glTF or Blender assets, so the spec's asset-pipeline items (Draco, KTX2, a Blender export script) do not apply. They are marked `N/A`.

**Baseline.** Captured in `docs/realism/phase1/before/`: 5 shots each for 9 engines, plus `metrics.json`.

Status key: `DONE`, `PARTIAL`, `MISSING`, `BLOCKED`, `N/A`. Viewers: **J** = JetLab, **P** = PistonLab.

## Renderer and pipeline

| Item | Status | Evidence | Engines affected | Notes |
|---|---|---|---|---|
| Tone mapping and exposure | DONE | `stage.js:19-20` (both): AgX, exposure 1.3 | J, P | No user exposure control yet (photo mode, Phase 5) |
| IBL with PMREM | DONE | `stage.js:145` (both): PMREM from a procedural studio scene with HDR soft boxes (intensity up to 5.5) | J, P | |
| Environment variety | DONE (Phase 1) | was MISSING; `teardown/shared/environments.js` | J, P | Studio, test cell, hangar, overcast, with rotation |
| Shadows | PARTIAL | `stage.js:23` VSM, soft, 2048 map | J, P | No PCSS contact hardening |
| Ambient occlusion | DONE | `stage.js:44` GTAO, tiered off on weak GPUs | J, P | No baked per-part AO (no texture pipeline) |
| SSR or planar floor reflections | MISSING | floor is a shadow catcher plus grid | J, P | Deferred to Phase 6 with the performance budget |
| Bloom | DONE | `stage.js:112` selective: emitters only, through a depth prepass | J, P | |
| Depth of field, motion blur, grain | PARTIAL | Phase 4: rotor blur from each row's angular speed at the playback rate (`jetlab-3d/engine.js` `setPlayRate`) | J | DoF and grain in photo mode (Phase 5) |
| Vignette | DONE | `stage.js:121` lens fall-off in the composite shader | J, P | Spec wants it optional; Phase 5 |
| Anti-aliasing | PARTIAL | `stage.js:42` MSAA on the composer target (4x, tiered) | J, P | No TAA or SMAA; thin blades can shimmer |
| WebGPU path | MISSING | WebGL2 only | J, P | Large rewrite of post passes; later |
| Path-traced still mode | BLOCKED | no path tracer in the build's dependencies; adding one (e.g. three-gpu-pathtracer) is a new third-party download and costs page budget | J, P | Phase 5 ships a jittered multi-sample raster still instead: clean edges, no global illumination |

## Materials

| Item | Status | Evidence | Engines affected | Notes |
|---|---|---|---|---|
| Metal-rough PBR on all parts | DONE | `MeshPhysicalMaterial` throughout (`detail.js`, `jetlab-3d/engine.js` materials) | J, P | |
| Clearcoat, anisotropy, iridescence | DONE | 20 uses across `pistonlab-3d/detail.js` and `jetlab-3d/engine.js` | J, P | Transmission and sheen unused |
| Maps on hero parts | PARTIAL | Phase 1: procedural tangent-space normal maps in `teardown/shared/alloys.js` (twill, honeycomb, perforation, turning marks, orange peel, TBC cracks, cast grain); blade lofts now carry UVs | J, P | No baked AO or curvature maps (no texture pipeline) |
| Wear, heat tint, soot, oil | DONE (Phase 3) | `teardown/shared/wear.js`: four service states; oil film at low surfaces, soot on hot metal, TBC fade and spall, leading-edge erosion, paint chalk and chips, cast-iron rust, aluminium oxide bloom, carbon on pistons and exhaust valves, liner rub tracks; heat tint from each part's solver temperature | J, P | No weld beads, lockwire paint marks or fretting at blade roots |
| Alloy-keyed material library | DONE (Phase 1) | was PARTIAL (piston names by role, jet by colour); `teardown/shared/alloys.js` | J, P | |

## Geometry

| Item | Status | Evidence | Engines affected | Notes |
|---|---|---|---|---|
| Blade airfoils: twist, lean, camber, thickness | DONE | `detail.js` `bladeGeometry`: NACA thickness, camber, stagger hub to tip, sweep, lean | J | |
| Blade roots, platforms, tip shrouds, seal fins | DONE (Phase 2) | `jetlab-3d/engine.js` `rotorRow`: platform per blade with gaps, axial dovetail (compressor) or three-lobe fir tree (turbine) filling the disc rim; rows lift radially out of their slots in the exploded view; stator inner shrouds over honeycomb seal lands, knife-edge labyrinth teeth on the drum; turbine NGV outer platforms; disc cover plates | J | No damper pockets; fan blades have no separate root (fan disc is solid) |
| Cooling holes, internal passages | PARTIAL (Phase 2) | `shared/alloys.js` `film`: showerhead and gill rows plus trailing-edge slots on HP turbine blades and NGVs (normal and colour map on the loft UVs); effusion holes on the combustor liner | J | Holes are surface detail, not geometry; internal serpentine passages not modelled (no section cap through blades yet; Phase 5) |
| Bevels and fillets | PARTIAL | `roundedBox` on castings and brackets; casings blend smoothly; blades have rounded NACA leading edges | J, P | Flange edges and blade trailing edges still sharp |
| Fasteners at real counts, lockwire, gaskets | PARTIAL | instanced bolts on every flange; head gasket (P) | J, P | No lockwire; counts by spacing, not per-engine data |
| Pipework, harness, brackets, AGB | DONE | fuel manifold, bleed, harness, AGB with units (J); hoses with clamps, looms, sensors (P) | J, P | |
| Instancing | DONE | `ringOf`, `instances`; per-instance variation in tint, roughness and damage from a hash of each instance's transform (`wear.js`) | J, P | |
| No z-fighting | PARTIAL | known fixes done (thrust reverser band, core nozzle); not swept systematically | J, P | Checked each phase by orbit |

## Teardown and presentation

| Item | Status | Evidence | Engines affected | Notes |
|---|---|---|---|---|
| Exploded view | DONE | `setExplode`: modules along the axis (J), layers (P) | J, P | Assembly order is by module, not exact |
| Section cut with capped faces | PARTIAL (Phase 5) | J: every cut casing is capped at both cut planes from its own profile, hatched at 45° and tinted by material class (`jetlab-3d/engine.js` section caps) | J, P | Rotors are not cut (museum style), so blades and discs have no caps; P still uses an uncapped clipping plane (stencil caps not done) |
| Labels and per-part metadata | DONE | `info.js` cards with solver numbers; Labels overlay | J, P | |
| BOM panel | DONE (Phase 5) | `teardown/shared/bom.js`: Parts tab built from pick metadata, quantities from instance counts, material from the alloy library, rows select the part | J, P | Materials show '-' for piston parts not yet on the alloy library |
| Photo mode and export | DONE (Phase 5) | `teardown/shared/photo.js`: camera presets, focal length, depth of field (BokehPass), exposure, env rotation, UI hidden, 1080p/1440p/4K stills accumulated over up to 64 jittered samples, transparent PNG by difference matting | J, P | |

## Motion and effects

| Item | Status | Evidence | Engines affected | Notes |
|---|---|---|---|---|
| Spool speeds and ratios | DONE | `kin.js` spools; geared fan and turboprop gear trains at tooth ratios | J | |
| Motion blur on rotors | DONE (Phase 4) | a row that turns over 1.5 blade pitches per frame becomes a translucent lit disc whose opacity is its solidity; blended from 0.35 pitches | J | |
| Temperature-driven glow | DONE | black-body colour and T⁴ brightness from solver temperatures | J, P | |
| Afterburner, exhaust, shocks, flow | DONE | flame shader with advected turbulence; plume Mach diamonds (Pack's formula); Euler-swirl streaklines; Phase 4 adds schlieren shading, the isolator shock train, the ramjet terminal normal shock, hydrogen plumes and heat haze | J, P | |
| Piston, valve, crank kinematics | DONE | exact slider-crank; cam lobes from the lift curve (`pistonlab-3d/engine.js`) | P | |

## Coverage of engine configurations

| Item | Status | Evidence | Engines affected | Notes |
|---|---|---|---|---|
| Turbofan signature features | PARTIAL | fan, OGVs, booster, VSVs, combustor, turbines, geared variant, nacelle; no bifurcation, no thrust-reverser pose | J | |
| Turbojet: centrifugal option, cannular, CD nozzle motion | PARTIAL | axial plus annular only; petals static at the solver's area | J | |
| Ramjet: normal shock position, booster | PARTIAL | conical shock drawn; terminal shock not placed | J | |
| Scramjet: cavity, cooled panels, shock train | PARTIAL | struts, ramp shocks; Phase 2 adds a cavity flameholder (L/D 5, 22.5° aft ramp) in the cowl wall and regeneratively cooled panels with feed and collection manifolds on the cut face | J | Shock train in the isolator: Phase 4 |
| Turboprop: pitch change, reverse flow, turboshaft | PARTIAL | free turbine, two-stage epicyclic gearbox; fixed pitch; no reverse-flow layout | J | |
| Auto layouts | PARTIAL | single, I4, I5, I6, V8 (cross- and flat-plane), flat-4, flat-6, diesel I4; no I3, V6, V10, V12, W, rotary | P | The 3D view refuses W and radial; the solver has no rotary model, so rotary is BLOCKED until it does |

## Performance

| Item | Status | Evidence | Engines affected | Notes |
|---|---|---|---|---|
| glTF compression, KTX2, Blender pipeline | N/A | procedural geometry, no image assets | J, P | |
| LOD | DONE (Phase 6) | screen-size LOD for small parts (bolts, clips, probes, sensors under 1.2 % of the engine's size are skipped below 1.5 px, `stage.js` `lodUpdate`); half-detail model build on the lowest tier (`jetlab-3d/engine.js` `DET`) | J, P | |
| Quality tiers and mobile profile | DONE | `live.js` `TIERS`, auto step-down on slow frames | J, P | |
| Shader pre-warm | DONE | `warmComposer` on load | J, P | |
| Frame budget | PARTIAL | Phase 6: 16.6 to 16.7 ms (vsync-capped) at 1920x1080 on 12 engines at every tier, RTX 4070; per-frame load cut by about a third at the top tier | J, P | No integrated GPU available to measure; a software-renderer stand-in shows the lowest tier 6.2x faster on the F136 |

## Honesty and references

| Item | Status | Evidence | Engines affected | Notes |
|---|---|---|---|---|
| Models labelled "representative" | DONE (Phase 1) | was PARTIAL (facts note only); now on every gallery subtitle | J, P | |
| `refs/<engine>.md` per engine | DONE (Phase 1) | was MISSING; `refs/` | J, P | Estimated numbers flagged |
| No logos or livery | DONE | none used | J, P | |

## Suspected defects

| Defect | Where | Status |
|---|---|---|
| Pure-black pixels in lit areas: 7 to 9 % inside the engine's bounds (`before/metrics.json`) | Measurement artefact: the black was the floor's contact shadow inside the bounding box, not the engine. Measured with the floor hidden, the engine has at most 0.04 % (`after/metrics.json`) | Resolved: the metric was fixed, not the render |
| ANGLE compiler warnings X4000 and X4122 on first shader compile | three.js r186 post-processing shaders (not this code), first engine only | Logged; not patched (third-party) |
| Fan blades show pure black faces and blown white highlights | `jetlab-3d` titanium on thin double-sided blades | Fixed in Phase 1: Ti-6Al-4V from the library with span-wise polish; compare `before/jet-cfm56-rotor.jpg` with `after/` |

## Measured performance

| Phase | Engine set | Frame time | Console |
|---|---|---|---|
| Baseline | 9 engines, RTX 4070, 1600x900, top tier | 16.4 to 16.5 ms (vsync) | 2 third-party warnings on first compile |
| Phase 1 | Same 9 engines, same settings | 16.4 to 16.5 ms (vsync) | Same 2 third-party warnings |

## Phase 1: lighting and materials

**Built:**
- `teardown/shared/environments.js`, with four HDR environments:
  - photo studio: soft boxes up to 5.5, a mid-grey cyclorama
  - engine test cell: concrete, fluorescent strips at 9, the inlet stack mouth
  - maintenance hangar: high-bay lights at 14, a painted floor bounce, a daylight door
  - outdoor overcast: a sky dome brightest overhead

  Each one sets its own key, fill and rim lights. The Layers tab has buttons to pick an environment, a rotation slider (`scene.environmentRotation`) and an exposure slider. This applies to both viewers.
- `teardown/shared/alloys.js`, an alloy-keyed material library. Parts ask for an alloy by name:
  - Ti-6Al-4V, Inconel 718, CMSX with TBC, CMC, steel, bearing steel, heat-tinted stainless
  - cast and machined aluminium, cast iron
  - CFRP twill, honeycomb abradable, acoustic liner
  - three paints, bronze, brass, rubber, cordierite, glass

  Each sets metal colour, roughness, anisotropy, clearcoat, sheen, iridescence (thin-film heat tint), transmission and a procedural normal map.
- JetLab now draws all its parts from the library. New parts: an abradable liner over the fan tips and an acoustic liner in the inlet. HP turbine blades carry TBC.
- PistonLab: blocks are cast iron or aluminium from gallery data (iron: 2JZ-GTE, ALH). Steel, rubber and headers come from the library.
- Every engine's subtitle reads "representative model".
- `refs/`: 20 notes, one per engine, each number marked published, estimated or solver.

**Measured.**
- Engine only (floor hidden), hero 3/4: pure black at most 0.04 % and clipped white at most 0.16 % across the 9 engines.
- Frame time is unchanged at 16.4 to 16.5 ms.
- 815 tests pass.

**Acceptance.** Titanium (cool, span-polished), nickel alloy (warm, turned, faint temper tint), TBC (matte cream), cast aluminium (grainy), paint (clearcoat) and CFRP (twill under a clear coat) are distinct at hero zoom (`docs/realism/phase1/after/`). No part reads as flat plastic, except the black polymer parts, which are meant to be plastic.

**Three visible differences that remain against reference photos:**
1. Flanges and casings show no machining facets or weld beads. Phase 2 for geometry, Phase 3 for the weld and heat-affected-zone normal maps.
2. The surfaces are factory clean: no oil weep, soot or tip-rub tracks. Phase 3.
3. Nacelle and cowl paint is one uniform panel, with no panel lines or rows of fasteners. Phase 2.

**Not done in Phase 1, by design:**
- Floor reflections: SSR or a planar reflector. Moved to Phase 5 photo mode, to keep interactive cost flat.
- PCSS contact hardening: VSM stays.
- WebGPU.

## Correction to an earlier statement

An earlier session said the GM LS3 block was cast iron. It is aluminium (the cast-iron LS blocks are the truck engines). The gallery now records it as aluminium.

## Phase 2: geometry detail

**Built (aero):**
- Blade platforms, and roots under every rotor blade: a dovetail on compressor blades, a fir tree on turbine blades. In the exploded view the rows lift radially out of their disc slots.
- Stator inner shrouds sitting on honeycomb seal lands, with three knife-edge teeth on the drum under each.
- NGV outer platforms and turbine disc cover plates.
- Film cooling on HP turbine blades and NGVs: a showerhead, gill rows and trailing-edge slots. Effusion holes on the combustor liner.
- A titanium leading-edge sheath on composite fan blades (LEAP-1A, GE90-115B).
- Finer blade lofts (rotors 8 x 13 sections, stators 5 x 11) and 128-segment discs and drums.
- Scramjet: a cavity flameholder, and regeneratively cooled panels with manifolds.

**Built (automotive):**
- A spring seat washer and a rubber stem seal at every valve.
- Split collets in the retainer on pushrod engines.
- A vane-type cam phaser (VVT) on the intake cam of twin-cam engines.
- Circlips on every wrist pin.
- A re-entrant bowl with a central pip in diesel pistons (VW ALH).

**Measured:**
- Validation set in `docs/realism/phase2/set/` and 4x close-ups in `docs/realism/phase2/before|after/`.
- Pure black at most 0.11 % and clipped white at most 0.16 % (engine only).
- 60 fps on all 14 engines (11 jet, 3 piston) on the RTX 4070.
- 815 tests pass. No new console messages.
- Triangle count rose from about 3.7M to 7.6M on the large turbofans. It is the first item for Phase 6 LOD, since this may not hold 60 fps on an integrated GPU.

**Acceptance.** At 4x, the compressor shows blades on platforms over a drum with seal teeth, with no faceting. The turbine shows shrouded LPT rows, and coated HPT airfoils with cooling-hole rows. The K20A valvetrain section shows cams, buckets, springs and seats. No surface reads as empty.

**Not done in Phase 2:**
- Lockwire, machining facets on flanges, and weld beads. These are surface maps, so Phase 3.
- Damper pockets under platforms, and internal passages in turbine blades. They need section caps (Phase 5).
- Honing cross-hatch on cylinder bores: the bores are drawn as glass in this viewer.
- The new automotive layouts the spec lists (I3, V6, V10, V12, rotary). They need solver support first.

**Three visible differences that remain against reference photos:**
1. Compressor blade rows exposed at the cut read as flat white plates in harsh light. Phase 3 wear and per-instance variation should break this up.
2. The scramjet's outer body is still a plain loft with no panel lines or thermal protection tiles.
3. Piston-engine castings have no draft lines or parting seams.

## Phase 3: wear and service states

**Built:** `teardown/shared/wear.js`, installed on every opaque physical material in both viewers (`applyWear` in each `stage.js`).

- **States.** Four presets (New, Early service, High time, Overhaul) in the Layers tab, plus `LIVE.setWear(id)`. Geometry is unchanged. One uniform moves the shading, so switching state needs no recompile.
- **Spatially plausible wear, by role.** Each part's role comes from its alloy, or is set by the engine:
  - oil film where surfaces are low
  - soot on hot metal, hottest parts first
  - thermal coating that fades and browns, then spalls to the bond coat
  - leading-edge erosion on compressor and fan blades (the loft's leading edge is at u = 0.5)
  - paint that chalks, then chips to bare metal
  - rust on cast iron at low, wet places, and white oxide bloom on aluminium castings
  - carbon on piston crowns and exhaust valves
  - rub tracks on liners
- **Per-instance variation.** Every blade, vane and bolt differs a little in tint, roughness and damage, from a hash of its instance matrix.
- **Temperature drives the heat tint.** The tint is a thin oxide film (iridescence) whose thickness follows each part's temperature from the cycle solve, and whose strength grows with time in service.
  - Jet: turbine-inlet temperature for the HP turbine, the LP turbine inlet and exit temperatures for the cases and nozzle, a discount for cooled metal.
  - Piston: the header wall temperature.
  - Hot parts also soot first, so a hotter cycle sets in a stronger tint.

**Measured:**
- Screenshots in `docs/realism/phase3/`: all four states of the CFM56-7B, new and overhaul of the 2JZ-GTE and LS3, and overhaul of the J85 and the ramjet.
- 815 tests pass, with no console errors.
- 60 fps on all 11 jet engines. The LS3 measured 58 fps once.
- Triangle count unchanged (wear is shading only).

**Acceptance.**
- Factory new and overhaul are clearly different: chipped, chalked cowl paint, a sooted plug and nozzle, straw-to-purple turbine discs, an oily lower block, rust specks, tinted headers.
- They look plausible: wear sits where it should (low, hot, leading edges), not as a uniform overlay.

**Not done in Phase 3:**
- Weld-bead TIG ripple and machining-facet maps.
- Lockwire and torque-paint marks.
- Fretting at blade roots.
- Wear accumulated from a simulated run time (the states are presets).

**Three visible differences that remain against reference photos:**
1. Oil weep is driven by height, not by joints. Real weeps start at flanges and fittings, then run down.
2. Soot is spread by noise. Real soot streaks downstream from the nozzle lip.
3. Paint chips are placed at random over surfaces. Real chips concentrate on edges and fastener heads, which needs curvature data the procedural geometry does not carry.

## Phase 4: dynamics and physics linkage

**Built (aero):**
- **Cycle tab.** Sliders for turbine-inlet temperature (throttle), flight Mach and altitude. The ramjet gets combustor exit temperature instead of throttle, and the scramjet gets equivalence ratio. Each change re-solves through `/simulate/<family>` and rebuilds the model.
  - Pressure ratios move along an operating line: with choked turbine and nozzle, the compressor's temperature rise scales with T4/T2.
  - Spool speeds scale with the square root of compressor work, from Euler's equation (`kin.js` `workOf`, `scaleSpools`).
- **Flow colour.** Streaklines coloured by temperature, velocity or pressure. Velocity and pressure use viridis, with a legend.
- **Thermal analysis view.** The solved station temperatures are interpolated along the gas path onto every part, on the magma scale. Bypass parts take the fan-exit temperature. Has a legend.
- **Rotor blur** from real angular speed. Playback now runs up to 1/10 real time.
- **Heat haze.** Screen-space refraction where the glow pass is bright. Applies to both viewers.
- **Schlieren-style shocks** on a new Shocks layer. Brightness comes from the Rankine-Hugoniot density jump, and edge-on surfaces read as lines. Added: the isolator shock train (reflected oblique shocks), the ramjet's terminal normal shock, and hydrogen plumes behind the scramjet struts.
- **Blade vibration overlay.** First bending and first torsion, with an amplitude slider.
- **Thermal growth.** Modules grow by 13e-6/K times their gas temperature rise. The slider exaggerates this by up to 40x and reports the real tip growth.

**Built (automotive):**
- **Cycle tab.** Engine speed and intake pressure (throttle or boost) re-solve through `/piston/simulate`.
- **Flame front.** A hemisphere from the plug, with volume set by the solver's burned fraction (volume fraction 4xb/(1+3xb)) and colour by black-body at the gas temperature.
- **Fuel spray.** Port-injector cones during each cylinder's intake stroke, and six diesel plumes at start of injection.

**Measured.**
- Acceptance: the visuals change with the cycle inputs. CFM56-7B, turbine-inlet temperature 1530 to 1850 to 1150 K:
  - thrust 65.7, 80.6 and 44.2 kN
  - HP spool 15,183, 17,085 and 12,712 rpm; LP 5,380, 5,683 and 4,997 rpm
  - the flame colour and header glow follow (`docs/realism/phase4/cfm56-T4-*.jpg`)
- K20A at part throttle and 3000 rpm: 153 to 50 to 23 kW, peak pressure 66 to 29 bar.
- 815 tests pass. No console errors.
- Frame rate: 56 to 60 fps. Large turbofans 56 to 59, F136 56 (it was 60). Phase 6 should recover this.

**Not done in Phase 4:**
- Inlet condensation vapour.
- Fuel and oil flow animation inside the pipework.
- Intake charge-motion particles in the cylinders.
- Blade untwist under centrifugal load.
- Run-time-driven heat tint. Wear is still a preset, not accumulated from the run.

**Suspected defects:**
- Ramjet: an orange haze extends above the cowl in side view. Its source (combustor flame versus plume) was not isolated before the session was interrupted. To check first in Phase 5.
- PistonLab: the header wall temperature rises at part throttle (959 to 1178 K at 0.45 bar intake). This is the solver's exhaust temperature, not a viewer error. It is worth a check against the solver's blowdown model.

## Phase 5: teardown polish and photo mode

**Built:**
- **Section caps (jet).** Every cut casing gets a capped face at both cut planes, filled from its own profile. Caps are hatched at 45° and tinted by material class:
  - aluminium grey
  - titanium blue-grey
  - nickel and stainless warm
  - TBC and ceramics cream
  - composites dark
  - liners green-grey
  - paint white
- **Bill of materials (both viewers).** A Parts tab built from the part metadata: quantities from instance counts, material from the alloy library, click to select and fly to a part.
  - CFM56-7B: 49 line items, 3,592 parts.
  - K20A: 116 line items, 609 parts.
- **Photo mode (both viewers).**
  - Camera presets: hero 3/4, front or inlet, side, exhaust or rear, top down, and a detail view (hot section or a cylinder).
  - Controls: focal length from 24 to 135 mm (35 mm equivalent), depth of field focused on the target, exposure, environment rotation. The UI is hidden.
  - Stills at 1080p, 1440p or 4K, accumulated over 1 to 64 Halton-jittered samples. About 1 s for 8 samples at 4K on the RTX 4070.
  - Transparent PNG by difference matting, since the post chain drops alpha. Measured: 46 % fully clear pixels on the CFM56 still, with the engine opaque.
- **Annotations** come from metadata: labels and part cards read the solve and layout (stage, blade count, temperatures, speeds), and the BOM names come from the same cards.

**Defects fixed:**
- Ramjet: orange haze above the cowl. Cause: the large flame's bloom halo. Large flames now enter the glow pass at 0.35 of their strength.
- PistonLab: the engine was framed far too small, with a detached shadow, since Phase 4. Cause: the idle flame-front hemisphere (unit radius) was counted in the engine's bounds. It is now kept at 1e-4 scale when idle.
- BOM rows without cards: `lpc` (booster drum) and `maf` (air-mass sensor) now have cards. A sweep of 13 engines finds no unnamed rows.

**Measured:**
- 4K stills for the CFM56-7B, J85, turboprop, ramjet, scramjet, K20A and 2JZ-GTE in `docs/realism/phase5/4k/`.
- 815 tests pass. No console errors.
- 60 fps on all 14 engines.

**Acceptance.** The 4K exports read as clean product shots with no UI, soft shadows and clean edges. They are usable as portfolio images, with the same caveats as the viewer itself: no logos, a representative geometry label, and studio lighting.

**Not done in Phase 5:**
- A true path tracer. Blocked on a new dependency.
- Stencil section caps in PistonLab.
- Compare mode (two engines or two service states side by side).
- Bolt circles and torque-sequence hints in the exploded view.
- Spiral and along-gas-path cutaway presets.

## Phase 6: performance

**Diagnosis.** The scene was never the problem. The LEAP-1A has 1.54M triangles in 501 meshes, but each frame drew it about five times: main pass, sun shadow map, GTAO normals, glow depth pre-pass, plus overhead. That made 7.6M triangles and 2,222 draw calls. The single largest call count was 135 separate seal-tooth meshes.

**Built:**
- **On-demand shadow map.** Redrawn every 4 frames (top tier), 12 frames (middle), or only on change (lowest). Changes that trigger it: a model rebuild, explode, a layer toggle, LOD visibility. Stills redraw it every sample.
- **Screen-size LOD** for small parts in every pass.
- **Seal teeth** merged to one mesh per stage.
- **Lowest tier rebuilds the jet model at half detail:** lathe segments, blade sections and flow tracers. It also turns off haze, along with the existing AO, glow and MSAA reductions. The auto step-down (slow frames over 2 s) reaches it on weak hardware, and touch or small screens start one tier down.

**Measured, 1920x1080, RTX 4070**

| Engine | Top tier | Lowest tier |
|---|---|---|
| LEAP-1A | 4.96M triangles, 1,413 calls (was 7.6M, 2,222) | 1.02M, 628 |
| GE90-115B | 4.69M, 1,370 | 0.97M, 610 |
| CFM56-7B | 3.83M, 1,227 | 0.81M, 550 |
| F136 | 1.59M, 3,055 | 0.75M, 1,498 |

- Every engine runs at 16.6 to 16.7 ms (vsync-capped) at every tier.
- JS heap: 13 to 47 MB per engine.
- Page size: 956 KB (JetLab) and 935 KB (PistonLab), both inside the 1 MB link-preview budget.
- 815 tests pass. No console errors.

**Software renderer (SwiftShader), as a weak-GPU stand-in.**
- F136: 8.4 s per frame at the top tier, 1.35 s at the lowest, which is 6.2x.
- The LEAP-1A measurement is not clean: on a renderer this slow, the page's own auto step-down fires during the sample window and rebuilds the model. That is the intended behaviour on a slow device, but it contaminates the per-tier timing.

**Acceptance.** Budgets are met on the available hardware. Deviations are documented:
- Not measured on a real integrated GPU or a phone. A real-device run is the next check.
- The PistonLab draw-call count stays high (1,500 to 3,000), because per-cylinder parts are separate meshes. Instancing the per-cylinder valvetrain is the next step if a weak device is CPU-bound.

**Not applicable:** Draco, meshopt and KTX2 compression, and a Blender export pipeline. The geometry is generated in code and there are no image assets.

**Not done:**
- A WebGPU path. Three.js's WebGPU renderer would need the post-processing chain rewritten in its node system.
- Progressive loading. The model builds in tens of milliseconds after the solve returns, so there is no grey-flash state to hide.
