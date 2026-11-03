// What each part is and what it is doing in this engine. Numbers come from the cycle solve (J.out), the layout that
// placed the part (J) and the published hardware (J.hw); where a part is drawn but not modelled, the card says so.
const f = (v, d = 0) => (v == null || !isFinite(v) ? '-' : v.toLocaleString(undefined, {minimumFractionDigits: d, maximumFractionDigits: d}));
const mm = (m) => `${f(m * 1e3)} mm`;
const card = (text, rows = [], note = '') =>
  `<p>${text}</p>${rows.length ? `<dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>` : ''}${note ? `<p class="pnote">${note}</p>` : ''}`;
const NOT_MODELLED = 'Drawn for layout and motion; the cycle solver does not model this part’s loads or flow.';
const bar = (p) => `${f(p / 1e5, 2)} bar`;

export function partInfo(id, meta, J) {
  const o = J.out;
  const ex = o.extra ?? {};
  const st = (sid) => J.stations.find((s) => s.id === sid);
  const mod = J.modules.find((m) => m.kind === (meta.module ?? id)) ?? J.modules.find((m) => m.kind === id);
  const rpm = (sp) => J.spools[sp]?.rpm;
  // rotor rows: tip speed, and the tip's Mach number relative to the blade (axial flow plus blade speed)
  const rotorRows = (m) => {
    if (!m) return [];
    const s0 = m.stages[0];
    const s1 = m.stages[m.stages.length - 1];
    const sp = J.spools[m.spool];
    const U = sp ? sp.w * s0.rt : 0;
    const g = m.kind.endsWith('t') ? 1.33 : 1.4;
    const at = J.at((s0.z + (m.z0 ?? s0.z)) / 2);
    const a = Math.sqrt(g * 287 * Math.max(150, at.Tt - (at.V * at.V) / 2010));
    return [
      ['Stages', `${m.n}`],
      ['Blades, first rotor', `${s0.blades}`],
      [m.Pt1 > m.Pt0 ? 'Pressure ratio' : 'Expansion ratio', f(m.Pt1 > m.Pt0 ? m.Pt1 / m.Pt0 : m.Pt0 / m.Pt1, 2)],
      ['Temperature', `${f(m.Tt0)} to ${f(m.Tt1)} K`],
      ['Speed', sp ? `${f(sp.rpm)} rpm` : '-'],
      ['Tip speed, first rotor', sp ? `${f(U)} m/s` : '-'],
      ['Relative tip Mach', sp ? f(Math.sqrt(U * U + at.V * at.V) / a, 2) : '-'],
      ['Tip diameter, first rotor', mm(2 * s0.rt)],
    ];
  };
  const fanRows = () => {
    const F = J.fan;
    const sp = J.spools[J.hw.gear_ratio ? 'fan' : 'lp'];
    const U = sp.w * F.rt;
    const a0 = Math.sqrt(1.4 * 287 * (st('fan')?.T || 250));
    return [
      ['Diameter', mm(2 * F.rt)], ['Blades', `${F.blades}`], ['Material', J.hw.fan_material],
      ['Speed', `${f(sp.rpm)} rpm`], ['Tip speed', `${f(U)} m/s`], ['Relative tip Mach', f(Math.sqrt(U * U + (st('fan')?.V ?? 0) ** 2) / a0, 2)],
      ['Fan pressure ratio', f(ex.fan_pressure_ratio ?? J.input.fan_pressure_ratio, 2)], ['Bypass ratio', f(ex.bypass_ratio ?? J.input.bypass_ratio, 1)],
    ];
  };
  const comb = J.combustor;
  const T = {
    fan: ['Fan', 'rotor', card(`Accelerates a large mass of air gently: ${f((J.mByp / J.mTot) * 100)} % of it goes round the core and makes most of the thrust.`, fanRows(), J.hw.note)],
    'fan-disc': ['Fan disc', 'rotor', card('Holds the fan blades in dovetail slots and carries their centrifugal load to the LP shaft.', fanRows().slice(3, 5), NOT_MODELLED)],
    spinner: ['Spinner', 'rotor', card('Guides the air smoothly onto the fan hub and sheds ice.', [], NOT_MODELLED)],
    'fan-case': ['Fan case', 'casing', card('Contains a released blade (the thick band over the blades is the containment ring) and carries the nacelle.', [['Inner diameter', mm(2 * J.R * 1.005)]], NOT_MODELLED)],
    ogv: ['Outlet guide vanes', 'stator', card('Take the swirl out of the bypass air so it leaves straight, recovering pressure.', [['Bypass total pressure', bar(st('bypass-exit')?.Pt ?? 0)]])],
    'fan-frame': ['Fan frame', 'casing', card('Struts that tie the core to the fan case and carry the front mount; one carries the tower shaft down to the gearbox.', [], NOT_MODELLED)],
    splitter: ['Splitter and core cowl', 'casing', card('Divides the fan stream: the inner part enters the core, the outer part the bypass duct.', [['Core flow', `${f(J.mCore, 1)} kg/s`], ['Bypass flow', `${f(J.mByp, 1)} kg/s`]])],
    booster: ['Booster (LP compressor)', 'rotor', card('Compressor stages on the LP shaft that supercharge the core behind the fan.', rotorRows(mod))],
    lpc: ['Booster drum', 'rotor', card('The drum that carries the booster stages on the LP shaft.', rotorRows(mod), NOT_MODELLED)],
    ipc: ['IP compressor', 'rotor', card('The middle spool’s compressor on a three-shaft engine, turned by its own turbine.', rotorRows(mod))],
    hpc: ['HP compressor', 'rotor', card('Squeezes the core air to the cycle’s peak pressure before it burns.', rotorRows(mod), `Overall pressure ratio ${f(ex.overall_pressure_ratio ?? J.input.compressor_pressure_ratio, 1)} : 1.`)],
    compressor: ['Compressor', 'rotor', card('Axial stages that raise the air’s pressure before combustion.', rotorRows(mod))],
    stator: ['Stator vanes', 'stator', card('Turn the flow back after each rotor, converting its speed into pressure.', rotorRows(mod).slice(0, 4))],
    vsv: ['Variable stator vanes', 'stator', card('The front stators can rotate on their spindles, moved together by a unison ring, so the compressor stays clear of stall at low speed.', [['Variable rows', `${mod?.vsv ?? '-'}`]], NOT_MODELLED)],
    'vsv-actuator': ['VSV actuator', 'casing', card('A fuel-pressure ram that moves the unison rings on the engine computer’s command.', [], NOT_MODELLED)],
    'compressor-case': ['Compressor case', 'casing', card('Holds the stators and keeps the blade tips close; split in halves for maintenance.', [['Pressure at exit', bar(st('hpc-exit')?.Pt ?? 0)]], NOT_MODELLED)],
    disc: ['Rotor disc', 'rotor', card('A forged disc whose rim holds one stage of blades; the bore is thickened to carry the hoop stress.', meta.stage ? [['Stage', `${meta.stage}`], ['Module', meta.module]] : [], NOT_MODELLED)],
    combustor: ['Annular combustor', 'combustor', card('Fuel burns in a ring-shaped liner; holes admit air to cool the walls and dilute the gas before the turbine.', [
      ['Inlet', `${f(comb?.Tin)} K, ${bar(st('hpc-exit')?.Pt ?? 0)}`], ['Exit (turbine inlet)', `${f(comb?.T)} K`], ['Fuel-air ratio', f(o.fuel_air_ratio, 4)], ['Fuel flow', `${f(o.fuel_flow_kg_s, 3)} kg/s`]])],
    flame: ['Flame', 'combustor', card('The burning gas. Its colour follows the gas temperature along the flame: in the main combustor the primary zone burns near stoichiometric, then dilution air brings it down to the turbine-inlet temperature. The turbulence drifts downstream at the gas’s own speed.', [['Exit temperature', `${f(comb?.T ?? J.afterburner?.T)} K`], ['Primary zone (assumed)', comb ? `${f(Math.min(2300, comb.T + 450))} K` : '-']], 'Colour from Planck’s law (Tanner Helland’s fit); brightness grows as T⁴ above the Draper point, 798 K, compressed for the screen.')],
    'fuel-nozzle': ['Fuel nozzles', 'combustor', card('Atomise and swirl the fuel into the liner’s dome.', [['Nozzles', `${comb?.nozzles}`], ['Fuel per nozzle', `${f(((o.fuel_flow_kg_s ?? 0) / (comb?.nozzles || 1)) * 1e3, 1)} g/s`]])],
    igniter: ['Igniters', 'combustor', card('Two spark igniters light the combustor at start and stand by in heavy rain.', [], NOT_MODELLED)],
    'combustor-case': ['Combustor case', 'casing', card('The pressure vessel round the liner, at compressor-exit pressure.', [['Pressure', bar(st('hpc-exit')?.Pt ?? 0)]], NOT_MODELLED)],
    'fuel-manifold': ['Fuel manifold', 'dress', card('Rings round the combustor case that feed every nozzle evenly from the fuel control.', [['Fuel flow', `${f(o.fuel_flow_kg_s, 3)} kg/s`]], NOT_MODELLED)],
    hpt: ['HP turbine', 'rotor', card('Expands the hottest gas to drive the HP compressor. Its blades run hotter than their alloy melts, kept alive by internal cooling air and ceramic coatings.', rotorRows(mod))],
    ipt: ['IP turbine', 'rotor', card('Drives the IP compressor on a three-shaft engine.', rotorRows(mod))],
    lpt: ['LP turbine', 'rotor', card('Many stages that extract the work to turn the fan and booster.', rotorRows(mod), ex.lpt_drop_K ? `Temperature drop across it: ${f(ex.lpt_drop_K)} K.` : '')],
    pt: ['Power turbine', 'rotor', card('A free turbine on its own shaft that drives the propeller through the gearbox.', rotorRows(mod), `Shaft power ${f(o.shaft_power_kW)} kW.`)],
    ngv: ['Nozzle guide vanes', 'stator', card('Accelerate and turn the gas onto each turbine rotor. The first row sees the full turbine-inlet temperature.', [['Gas temperature', `${f(mod?.stages[0]?.Tt)} K`]])],
    'turbine-case': ['Turbine case', 'casing', card('Holds the vanes and the shroud segments over the blade tips; cooled with air from the compressor.', [], NOT_MODELLED)],
    'lp-shaft': ['LP shaft', 'shaft', card('Runs inside the HP shaft, from the LP turbine forward to the fan.', [['Speed', `${f(rpm('lp'))} rpm`]])],
    'hp-shaft': ['HP shaft', 'shaft', card('Joins the HP turbine to the HP compressor.', [['Speed', `${f(rpm('hp'))} rpm`]])],
    'ip-shaft': ['IP shaft', 'shaft', card('Joins the IP turbine to the IP compressor.', [['Speed', `${f(rpm('ip'))} rpm`]])],
    'pt-shaft': ['Power turbine shaft', 'shaft', card('Carries the power turbine’s work forward to the reduction gearbox.', [['Speed', `${f(rpm('pt'))} rpm`]])],
    bearing: ['Bearing', 'shaft', card('Ball bearings take the thrust, roller bearings the radial load; each sits in an oil-fed sump.', [], NOT_MODELLED)],
    'fan-gearbox': ['Fan drive gearbox', 'gearbox', card('A star gearbox: the sun on the LP shaft, five planets on fixed pins, the ring gear driving the fan the other way at a third of the speed.', [['Ratio', `${f(J.hw.gear_ratio, 4)} : 1`], ['LP shaft', `${f(rpm('lp'))} rpm`], ['Fan', `${f(rpm('fan'))} rpm`], ['Teeth', 'sun 32, planets 17, ring 66']])],
    agb: ['Accessory gearbox', 'dress', card(`Takes power off the HP spool through the tower shaft to drive the engine’s pumps and generator. Mounted on the ${J.hw.agb === 'fan' ? 'fan case' : 'core'}.`, [['HP spool', `${f(rpm('hp'))} rpm`]], NOT_MODELLED)],
    'tower-shaft': ['Tower shaft', 'dress', card('A radial shaft, driven by bevel gears off the HP spool, that carries power down to the accessory gearbox and starts the engine.', [['Speed', `${f(rpm('hp'))} rpm (1:1 assumed)`]], NOT_MODELLED)],
    starter: ['Air starter', 'dress', card('An air turbine that spins the HP spool through the gearbox until the engine lights and runs on its own.', [], NOT_MODELLED)],
    'fuel-pump': ['Fuel pump and control', 'dress', card('A gear pump and the metering unit that sets the fuel flow the engine computer asks for.', [['Fuel flow', `${f(o.fuel_flow_kg_s, 3)} kg/s`]], NOT_MODELLED)],
    idg: ['Generator (IDG)', 'dress', card('An integrated drive generator: a constant-speed drive and an alternator giving the aircraft 115 V at 400 Hz.', [], NOT_MODELLED)],
    'hyd-pump': ['Hydraulic pump', 'dress', card('Supplies the aircraft’s hydraulic system.', [], NOT_MODELLED)],
    'oil-pump': ['Lube and scavenge pump', 'dress', card('Feeds oil to the bearing sumps and pumps it back to the tank.', [], NOT_MODELLED)],
    fadec: ['Engine computer (FADEC)', 'dress', card('Full-authority digital control: reads speeds, pressures and temperatures and sets fuel flow and stator angles. Finned for cooling.', [], NOT_MODELLED)],
    harness: ['Harness', 'dress', card('Wiring looms clipped round the cases, carrying sensor signals to the engine computer.', [], NOT_MODELLED)],
    'egt-probe': ['EGT probes', 'dress', card('Thermocouples in the gas path at the LP turbine inlet, averaged into the exhaust gas temperature the crew watches.', [['Gas there', `${f(st('lpt-in')?.Tt)} K`]])],
    bleed: ['Bleed air', 'dress', card('Air taken from the compressor for cabin pressure and anti-ice, through a valve.', [['Bleed fraction', `${f((o.extra?.bleed_fraction_hpc_exit ?? 0) * 100, 1)} %`]], NOT_MODELLED)],
    trf: ['Turbine rear frame', 'casing', card('Struts behind the LP turbine that straighten the exhaust and carry the rear bearing and mount.', [], NOT_MODELLED)],
    'core-nozzle': ['Core nozzle', 'casing', card('Accelerates the hot core gas out of the engine.', [['Exit speed', `${f(o.exit_velocity_m_s)} m/s`], ['Choked', o.nozzle_choked ? 'yes' : 'no'], ['Core thrust', `${f((o.core_thrust_N ?? 0) / 1e3, 1)} kN`]])],
    plug: ['Exhaust plug', 'casing', card('Shapes the core nozzle’s exit and closes the turbine’s centre.', [], NOT_MODELLED)],
    nacelle: ['Nacelle', 'nacelle', card('The aerodynamic housing: the inlet lip slows the air to the fan’s Mach number; the cowls form the bypass duct’s outer wall.', [['Bypass exit speed', `${f(o.bypass_exit_velocity_m_s)} m/s`], ['Bypass thrust', `${f((o.bypass_thrust_N ?? 0) / 1e3, 1)} kN`]])],
    'thrust-reverser': ['Thrust reverser', 'nacelle', card('On landing the sleeve slides back, blocker doors close the bypass duct and cascades turn the fan air forward.', [], NOT_MODELLED)],
    'core-cowl': ['Core cowl', 'nacelle', card('The inner wall of the bypass duct round the core.', [], NOT_MODELLED)],
    afterburner: ['Afterburner', 'casing', card('Burns more fuel in the turbine exhaust, where oxygen is left over, for a large but thirsty boost.', [['Reheat temperature', `${f(J.afterburner?.T)} K`], ['Reheat fuel-air ratio', f(o.afterburner_fuel_air_ratio, 4)]])],
    flameholder: ['Flame holders', 'combustor', card('V-gutters whose wake is a sheltered, slow region where the flame can anchor in the fast gas.', [], NOT_MODELLED)],
    'spray-ring': ['Spray rings', 'combustor', card('Fuel injection rings upstream of the flame holders.', [], NOT_MODELLED)],
    'nozzle-petals': ['Nozzle petals', 'casing', card('Overlapping petals set the exit area; drawn here at the area the solver needs.', [['Exit area', `${f(J.nozzle?.A9, 3)} m²`], ['Choked', o.nozzle_choked ? 'yes' : 'no']])],
    'tail-cone': ['Tail cone', 'casing', card('Closes the turbine’s centre and diffuses the flow into the jet pipe.', [], NOT_MODELLED)],
    tailpipe: ['Tail pipe', 'casing', card('Carries the turbine exhaust to the nozzle.', [], NOT_MODELLED)],
    'inlet-case': ['Inlet', 'casing', card('Delivers the air to the compressor face.', [['Air flow', `${f(J.mTot, 1)} kg/s`]])],
    'inlet-strut': ['Inlet struts', 'casing', card('Carry the front bearing and route oil and air across the inlet.', [], NOT_MODELLED)],
    propeller: ['Propeller', 'rotor', card('Most of the thrust: a big disc of air accelerated a little.', [['Diameter', `${f(J.prop?.D, 2)} m`], ['Blades', `${J.prop?.blades}`], ['Speed', `${f(rpm('prop'))} rpm`], ['Tip Mach', f(ex.propeller_tip_mach, 2)], ['Efficiency', `${f((ex.propeller_efficiency ?? 0) * 100)} %`], ['Propeller thrust', `${f((o.propeller_thrust_N ?? 0) / 1e3, 2)} kN`]])],
    rgb: ['Reduction gearbox', 'gearbox', card('Two epicyclic stages step the power turbine’s speed down to the propeller’s.', [['Ratio', `${f(J.prop?.ratio, 1)} : 1`], ['Power turbine', `${f(rpm('pt'))} rpm`], ['Propeller', `${f(rpm('prop'))} rpm`], ['Shaft power', `${f(o.shaft_power_kW)} kW`]])],
    impeller: ['Centrifugal impeller', 'rotor', card('Flings the air outward to a high pressure in one stage, after the axial stages.', [['Speed', `${f(rpm('hp'))} rpm`], ['Tip speed', `${f((J.spools.hp?.w ?? 0) * (J.impeller?.rOut ?? 0))} m/s`], ['Blades', `${J.impeller?.blades}`]])],
    'impeller-case': ['Impeller shroud and diffuser', 'casing', card('Closes the impeller’s blades and turns the air back toward the combustor.', [], NOT_MODELLED)],
    'intake-screen': ['Intake screen', 'casing', card('Keeps debris out of the compressor.', [], NOT_MODELLED)],
    spike: ['Inlet spike', 'casing', card('Its cone sets up an oblique shock that compresses the supersonic air with no moving parts.', [['Flight Mach', f(J.mach, 2)], ['Cone half-angle', `${f(J.hw.spike_half_angle_deg)}°`], ['Ram pressure ratio', f(ex.ram_pressure_ratio, 1)]])],
    'spike-strut': ['Spike struts', 'casing', card('Hold the centre body in the duct.', [], NOT_MODELLED)],
    cowl: ['Cowl', 'casing', card('The outer wall: a sharp lip that captures the air, the diffuser and combustor walls, the nozzle.', [['Inlet recovery', f(ex.applied_inlet_recovery ?? ex.inlet_pressure_recovery, 3)]])],
    shock: ['Shock', 'shock', card('An oblique shock: a thin layer where the supersonic air is compressed abruptly. Its angle comes from the oblique-shock relation for this Mach number and surface angle.', J.shock ? [['Shock angle', `${f((J.shock.beta * 180) / Math.PI, 1)}°`]] : (J.shocks ?? []).map((s, i) => [`Ramp ${i + 1}`, `${f((s.beta * 180) / Math.PI, 1)}° at Mach ${f(s.M, 1)}`]), J.shock ? 'Drawn with the 2D wedge relation as an approximation for the cone.' : '')],
    forebody: ['Forebody ramps', 'casing', card('The vehicle’s underside: two ramps turn the air and compress it through oblique shocks before the cowl.', [['Contraction ratio', `${f(J.scram?.CR, 1)} : 1`]])],
    sidewall: ['Sidewall', 'casing', card('Closes the flow path at each side.', [], NOT_MODELLED)],
    strut: ['Injector struts', 'combustor', card('Inject hydrogen across the supersonic stream so it mixes and burns within a metre.', [['Equivalence ratio', f(ex.equivalence_ratio, 2)], ['Combustor Mach', f(ex.combustor_mach, 2)]])],
    flow: [meta.stream === 'bypass' ? 'Bypass air' : 'Core gas', 'flow', card('Streaklines: each tracer’s recent path. Along the axis they move at the station speeds; round it they swirl by Euler’s turbine equation, ΔVθ = cp·ΔTt / U, picking up swirl in each rotor and losing it in the next stator, so the trails twist and straighten stage by stage. Colour is the local static temperature.', [
      ['Thrust', `${f(o.thrust_kN, 1)} kN`], ['Swirl after the first core rotor', `${f(J.vtheta((J.modules.find((m) => m.kind !== 'fan')?.stages[0].zr ?? 0) - 0.001))} m/s`],
      ['Turbulence intensity, combustor', `${f(J.tu(J.combustor ? (J.combustor.z0 + J.combustor.z1) / 2 : 0) * 100)} %`]],
      'Axial speeds use assumed axial Mach numbers at each station (typical design values). Turbulence intensities are typical values by region, drawn three times larger than life so the eddies read.')],
    abradable: ['Abradable liner', 'casing', card('A honeycomb-backed liner over the fan tips. The blades cut their own track in it, so the tip gap stays as small as the first run makes it.', [['Fan tip speed', `${f((J.spools[J.hw.gear_ratio ? 'fan' : 'lp']?.w ?? 0) * J.R)} m/s`]], NOT_MODELLED)],
    'acoustic-liner': ['Acoustic liner', 'nacelle', card('A perforated skin over honeycomb cells, each a small resonator tuned to absorb the fan’s blade-passing tone.', [['Blade-passing frequency', `${f((J.fan?.blades ?? 0) * (J.spools[J.hw.gear_ratio ? 'fan' : 'lp']?.rpm ?? 0) / 60)} Hz`]], NOT_MODELLED)],
    seal: ['Labyrinth seal', 'rotor', card('Knife-edge teeth on the drum run against a honeycomb land under each stator. Each tooth throttles the leakage round the vane row; the honeycomb lets the teeth cut in without damage.', [], NOT_MODELLED)],
    cavity: ['Cavity flameholder', 'combustor', card('A recess in the wall with a sloped aft ramp. Air recirculates in it slowly enough for the flame to anchor, then spills into the supersonic stream.', [['Length to depth', '5 (typical)'], ['Aft ramp', '22.5°']], NOT_MODELLED)],
    'cooled-panel': ['Regeneratively cooled panel', 'combustor', card('The combustor walls are cooled by the fuel itself, pumped through channels in the wall before injection; manifolds across the width feed and collect it. The heat it picks up goes back into the cycle.', [['Combustor exit (total)', `${f(J.scram?.T)} K`]], NOT_MODELLED)],
    'normal-shock': ['Terminal normal shock', 'shock', card('At critical operation a normal shock stands at the inlet throat, where the flow behind the cone shock drops to subsonic before the diffuser. Its strength is the density jump for the Mach number behind the cone shock.', J.normalShock ? [['Mach ahead of it', f(J.normalShock.M, 2)], ['Density ratio across it', f(J.normalShock.jump, 2)]] : [], 'Drawn at the critical position; the solver does not model inlet unstart or spillage.')],
    'shock-train': ['Isolator shock train', 'shock', card('The combustor’s back-pressure is held off by a train of oblique shocks reflecting between the isolator walls, each weaker than the last, so the inlet stays started.', J.shockTrain ? [['Reflections drawn', `${J.shockTrain.length}`], ['First density ratio', f(J.shockTrain[0]?.jump, 2)]] : [], 'Angles from the oblique-shock relation for a 4° effective deflection; a representative train, not a CFD result.')],
    'fuel-plume': ['Hydrogen plume', 'combustor', card('Fuel injected from each strut’s base spreads as a mixing layer into the supersonic air, burning as it mixes.', [], NOT_MODELLED)],
    stand: ['Display stand', 'stand', card('A transport stand, the engine on its mounts.', [], '')],
    plume: ['Exhaust plume', 'flow', card('The jet behind the nozzle. A choked nozzle leaves the jet above ambient pressure; it expands and recompresses in a train of shock cells, the bright Mach diamonds.', J.plume ? [
      ['Nozzle pressure ratio', f(J.plume.npr, 2)], ['Fully expanded jet Mach', f(J.plume.Mj, 2)], ['Shock-cell spacing', J.plume.spacing ? mm(J.plume.spacing) : 'no cells: subsonic jet']] : [], 'Cell spacing from Pack’s formula, L = 1.306 D sqrt(Mj² - 1). Plume brightness is illustrative.')],
    fin: ['Tail fins', 'casing', card('Twin canted fins and all-moving horizontal tails for stability and control at hypersonic speed.', [], NOT_MODELLED)],
  };
  const t = T[id];
  return t ? {name: t[0], layer: t[1], html: t[2]} : {name: id, layer: '', html: ''};
}
