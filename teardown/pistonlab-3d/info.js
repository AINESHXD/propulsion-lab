// What each part is and what it is doing in this engine. Every number is read from the solve (E.out) or from the same
// geometry that draws the part (E); where a part is drawn but not modelled, the card says so.
const f = (v, d = 0) => (v == null || !isFinite(v) ? '-' : v.toLocaleString(undefined, {minimumFractionDigits: d, maximumFractionDigits: d}));
const mm = (m, d = 1) => `${f(m * 1e3, d)} mm`;
const card = (text, rows = [], note = '') =>
  `<p>${text}</p>${rows.length ? `<dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>` : ''}${note ? `<p class="pnote">${note}</p>` : ''}`;
const NOT_MODELLED = 'Drawn for layout and motion; PistonLab does not model this part’s loads or flow.';

export function partInfo(id, meta, E) {
  const o = E.out;
  const vt = E.vt;
  const w = (E.rpm * 2 * Math.PI) / 60;
  const lam = E.L / E.r;
  const cyl = meta.cyl ? ` ${meta.cyl}` : '';
  const vtName = {dohc: 'double overhead cam', sohc: 'single overhead cam', ohv: 'pushrod (cam in block)'}[E.hw.valvetrain];
  const inDur = 180 + vt.intake_open_btdc_deg + vt.intake_close_abdc_deg;
  const exDur = 180 + vt.exhaust_open_bbdc_deg + vt.exhaust_close_atdc_deg;
  const liftIn = E.vg.max_lift_ratio * E.vg.intake_valve_diameter_ratio * E.bore;
  const liftEx = E.vg.max_lift_ratio * E.vg.exhaust_valve_diameter_ratio * E.bore;
  const pIn = o.boost_pressure_Pa > 0 ? o.boost_pressure_Pa : E.input.intake_pressure_Pa ?? 1e5;
  const camRows = [
    ['Speed', `${f(E.rpm / 2)} rpm (half crank)`],
    ['Intake', `opens ${f(vt.intake_open_btdc_deg)}° BTDC, closes ${f(vt.intake_close_abdc_deg)}° ABDC (${f(inDur)}°)`],
    ['Exhaust', `opens ${f(vt.exhaust_open_bbdc_deg)}° BBDC, closes ${f(vt.exhaust_close_atdc_deg)}° ATDC (${f(exDur)}°)`],
    ['Overlap', `${f(o.valve_overlap_deg ?? vt.intake_open_btdc_deg + vt.exhaust_close_atdc_deg)}°`],
  ];
  const lobe = 'Each lobe is generated from the lift curve that lifts its valve, so lobe, follower and valve cannot disagree.';
  const T = {
    crank: ['Crankshaft', 'rotating', card(`Turns the pistons’ push into torque. ${o.layout?.description ?? ''}`, [
      ['Speed', `${f(E.rpm)} rpm`], ['Stroke', `${mm(E.stroke)} (throw ${mm(E.r)})`],
      ['Crank-pin angles', `${new Set(E.cyl.map((c) => Math.round(c.pin) % 360)).size}`],
      ['Firing order', E.order.join('-')], ['Brake torque', `${f(o.brake_torque_Nm)} N·m`],
    ], o.layout?.balance_verdict)],
    flywheel: ['Flywheel', 'rotating', card('Stores energy between power strokes and carries the starter ring gear.', [
      ['Brake torque', `${f(o.brake_torque_Nm)} N·m`], ['Brake power', `${f(o.brake_power_W / 1e3)} kW`]])],
    balance: ['Balance shaft', 'rotating', card('A counter-rotating eccentric weight that cancels shaking the crank cannot.', [
      ['Speed', `${f(E.rpm * (E.hw.balance_shafts > 1 ? 2 : 1))} rpm`]], o.layout?.balance_verdict)],
    piston: [`Piston${cyl}`, 'rotating', card('Seals the chamber with its rings and carries the gas load to the rod through the wrist pin.', [
      ['Bore', mm(E.bore)], ['Mean piston speed', `${f((2 * E.stroke * E.rpm) / 60, 1)} m/s`],
      ['Peak acceleration', `${f((E.r * w * w * (1 + 1 / lam)) / 9.81)} g at TDC`],
      ['Peak gas load', `${f((o.peak_pressure_Pa * E.area) / 1e3, 1)} kN`]])],
    rod: [`Connecting rod${cyl}`, 'rotating', card('Links the wrist pin to the crank pin; its angle sets the piston side load.', [
      ['Length', mm(E.L)], ['Rod ratio', f(lam, 2)], ['Max angle', `${f((Math.asin(1 / lam) * 180) / Math.PI, 1)}°`]])],
    charge: [`Charge${cyl}`, 'charge', card('The gas in the cylinder, coloured by what it is doing: fresh charge, compressed, burning, exhaust.', [
      ['Clearance volume', `${f(E.vc * 1e6, 1)} cm³`], ['Swept volume', `${f(E.swept * 1e6, 0)} cm³`],
      ['Peak pressure', `${f(o.peak_pressure_Pa / 1e5)} bar`], ['Peak temperature', `${f(o.peak_temperature_K)} K`],
    ], 'Pressure, temperature and burn come from the PistonLab cycle solver.')],
    liner: [`Cylinder bore${cyl}`, 'block', card('The bore the piston runs in.', [['Bore', mm(E.bore)], ['Compression ratio', `${f(E.cr, 1)} : 1`]])],
    block: ['Cylinder block', 'block', card('Carries the bores and, below them, the crankcase.', [
      ['Cylinders', `${E.cyl.length}`], ['Capacity', `${f(o.total_displacement_m3 * 1e3, 3)} L`]], 'Bore spacing drawn at 1.18 bores.')],
    crankcase: ['Crankcase', 'block', card('Encloses the crank; the main bearing caps bolt to it.', [], NOT_MODELLED)],
    mains: ['Main bearing cap', 'block', card('Holds the crank in its main bearings; each is fed oil from the main gallery.', [], NOT_MODELLED)],
    head: ['Cylinder head', 'head', card(`Closes the bores and carries the ports and the ${vtName} valvetrain.`, [
      ['Clearance per cylinder', `${f(E.vc * 1e6, 1)} cm³`],
      ['Valves per cylinder', `${E.vg.intake_valves_per_cylinder} intake, ${E.vg.exhaust_valves_per_cylinder} exhaust`]])],
    cover: [E.hw.valvetrain === 'ohv' ? 'Rocker cover' : 'Cam cover', 'head', card('Seals the valvetrain and keeps its oil in.', [], NOT_MODELLED)],
    'valve-in': [`Intake valve${cyl}`, 'valvetrain', card('Lets the fresh charge in.', [
      ['Head diameter', mm(E.vg.intake_valve_diameter_ratio * E.bore)], ['Max lift', mm(liftIn)],
      ['Lift / diameter', f(E.vg.max_lift_ratio, 2)], ['Inlet Mach index', f(o.inlet_mach_index, 2)]], o.breathing_verdict || '')],
    'valve-ex': [`Exhaust valve${cyl}`, 'valvetrain', card('Lets the burned gas out.', [
      ['Head diameter', mm(E.vg.exhaust_valve_diameter_ratio * E.bore)], ['Max lift', mm(liftEx)],
      ['Exhaust Mach index', f(o.exhaust_mach_index, 2)]])],
    spring: [`Valve spring${cyl}`, 'valvetrain', card('Closes the valve and keeps the follower on the lobe.', [], NOT_MODELLED)],
    bucket: [`Bucket follower${cyl}`, 'valvetrain', card('Sits between lobe and valve; the lobe pushes it straight down.', [], E.hw.note || NOT_MODELLED)],
    'cam-in': ['Intake camshaft', 'valvetrain', card(`One lobe per intake valve. ${lobe}`, camRows)],
    'cam-ex': ['Exhaust camshaft', 'valvetrain', card(`One lobe per exhaust valve. ${lobe}`, camRows)],
    'cam-sohc': ['Camshaft', 'valvetrain', card(`One cam works both valves of every cylinder. ${lobe}`, camRows, E.hw.note)],
    'cam-block': ['Camshaft (in the block)', 'valvetrain', card(`One cam in the valley works every valve through lifters, pushrods and rockers. ${lobe}`, [
      ...camRows, ['Rocker ratio', `${f(E.hw.rocker_ratio, 2)} : 1`], ['Intake lobe lift', mm(liftIn / E.hw.rocker_ratio)]])],
    lifter: [`Lifter${cyl}`, 'valvetrain', card('Rides the cam lobe and pushes the pushrod.', [['Intake lobe lift', mm(liftIn / E.hw.rocker_ratio)]])],
    pushrod: [`Pushrod${cyl}`, 'valvetrain', card('Carries the lifter’s motion up to the rocker.', [], NOT_MODELLED)],
    rocker: [`Rocker arm${cyl}`, 'valvetrain', card('Turns the pushrod’s lift over and multiplies it.', [
      ['Ratio', `${f(E.hw.rocker_ratio, 2)} : 1`], ['Intake valve lift', mm(liftIn)]])],
    sprockets: ['Cam drive sprockets', 'timing', card('Each cam sprocket has twice the crank sprocket’s teeth, so the cams turn once for every two crank turns.', [
      ['Ratio', '2 : 1'], ['Cam speed', `${f(E.rpm / 2)} rpm`]])],
    chain: ['Timing chain', 'timing', card('Ties the cams to the crank. Its links move at the crank sprocket’s pitch-line speed.', [
      ['Path length', mm(E.timingLength, 0)]], 'Sprocket sizes are drawn to scale with each other, not taken from the maker.')],
    tensioner: ['Chain tensioner', 'timing', card('A hydraulic plunger presses a guide into the slack run so the chain cannot slap or jump a tooth.', [], NOT_MODELLED)],
    guide: ['Chain guide', 'timing', card('A nylon-faced rail that steadies a straight run of chain.', [], NOT_MODELLED)],
    maf: ['Air-mass sensor', 'intake', card('A heated-film sensor in the intake duct that measures the air mass flowing to the engine, from which the engine computer meters the fuel.', [['Air-fuel ratio', f(o.air_fuel_ratio, 1)]], NOT_MODELLED)],
    'stem-seal': ['Valve stem seal and spring seat', 'valvetrain', card('A rubber lip seal on top of the valve guide meters a little oil down the stem and no more; the hardened washer under it seats the spring.', [], NOT_MODELLED)],
    phaser: ['Cam phaser (VVT)', 'timing', card('A vane-type phaser between sprocket and intake cam: engine oil fed to one side of its vanes or the other turns the cam a few tens of degrees against the sprocket, moving the intake timing with load and speed.', [['Intake opens', `${f(vt.intake_open_btdc_deg)}° BTDC at this point`]], 'Drawn at a fixed phase; PistonLab models fixed timing.')],
    'flame-front': [`Flame front${cyl}`, 'charge', card('The burned gas spreading from the spark. Its volume is the burned share of the cylinder at this crank angle from the solver’s burn curve; burned gas is about four times less dense than the charge, so a mass fraction xb fills 4xb / (1 + 3xb) of the volume.', [['Burn duration', `${f(E.input.burn_duration_deg ?? 50)}°`]], 'Drawn as a hemisphere from the plug; real flame fronts wrinkle and are pushed by the charge motion.')],
    spray: [`Fuel spray${cyl}`, 'ignition', card(E.hw.diesel ? 'Six plumes from the injector nozzle into the bowl at the start of injection.' : 'The port injector sprays onto the back of the intake valve while that cylinder draws in its charge.', [['Air-fuel ratio', f(o.air_fuel_ratio, 1)]], 'Timing drawn, not modelled: PistonLab assumes a fully mixed charge.')],
    gasket: ['Head gasket', 'head', card('Multi-layer steel between block and head, with a fire ring round each bore to hold combustion pressure.', [
      ['Peak cylinder pressure', `${f(o.peak_pressure_Pa / 1e5)} bar`]], NOT_MODELLED)],
    'cam-cap': ['Cam bearing cap', 'valvetrain', card('Clamps the camshaft into its journals in the head.', [], NOT_MODELLED)],
    'pulley-crank': ['Crank pulley', 'accessory', card('Drives the accessory belt.', [['Speed', `${f(E.rpm)} rpm`]])],
    'water-pump': ['Water pump', 'accessory', card('Circulates coolant through the block and heads.', [], `Its speed follows the drawn pulley ratio. ${NOT_MODELLED}`)],
    alternator: ['Alternator', 'accessory', card('Charges the battery from the belt.', [], NOT_MODELLED)],
    idler: ['Idler pulley', 'accessory', card('Guides the belt and keeps it in tension.', [], NOT_MODELLED)],
    belt: ['Accessory belt', 'accessory', card('One belt drives every accessory; it cannot slip, so each pulley turns at the crank pulley’s rim speed.', [], NOT_MODELLED)],
    'sump-wet': ['Wet sump', 'lube', card('The oil lives in the pan under the crank; the pump draws it up through the pickup.', [], NOT_MODELLED)],
    'sump-dry': ['Dry sump pan', 'lube', card('A shallow pan pumped dry by its own scavenge pump, so hard cornering cannot starve the pickup.', [], NOT_MODELLED)],
    'oil-tank': ['Oil tank', 'lube', card('Holds the dry sump’s oil away from the crank; the pressure pump draws from its base.', [], NOT_MODELLED)],
    scavenge: ['Scavenge pump', 'lube', card('Pulls oil out of the pan and sends it back to the tank.', [], NOT_MODELLED)],
    'oil-pump': ['Oil pump', 'lube', card('A gerotor on the crank nose; its inner rotor turns with the crank.', [['Speed', `${f(E.rpm)} rpm`]], NOT_MODELLED)],
    pickup: ['Oil pickup', 'lube', card('Draws oil from the bottom of the sump through a strainer.', [], NOT_MODELLED)],
    filter: ['Oil filter', 'lube', card('Cleans the oil before it reaches the main gallery.', [], NOT_MODELLED)],
    gallery: ['Oil galleries', 'lube', card('Feed the main bearings and rise to the heads. The dashes move with the crank.', [
      ['Main bearings fed', `${E.mains?.length ?? '-'}`]], NOT_MODELLED)],
    dipstick: ['Dipstick', 'lube', card('Reads the sump level.', [], NOT_MODELLED)],
    runner: [`Intake runner${cyl}`, 'intake', card('Carries the charge from the plenum to one cylinder.', [
      ['Intake pressure', `${f(pIn / 1e5, 2)} bar`], ['Volumetric efficiency', `${f((o.volumetric_efficiency ?? 0) * 100)} %`]])],
    plenum: ['Intake plenum', 'intake', card('A volume that feeds every runner evenly.', [['Charge temperature', `${f(o.mixed_temperature_K)} K`]])],
    throttle: ['Throttle body', 'intake', card('The butterfly that sets the airflow, drawn part open.', [], NOT_MODELLED)],
    injector: [`Port injector${cyl}`, 'ignition', card('Sprays fuel into the runner ahead of the intake valve.', [
      ['Fuel', o.fuel ?? E.input.fuel ?? '-'], ['Air-fuel ratio', f(o.air_fuel_ratio, 1)], ['Fuel per cycle', `${f(o.fuel_mass_per_cycle_kg * 1e6, 1)} mg`]])],
    rail: ['Fuel rail', 'ignition', card('Feeds every injector at one pressure.', [], NOT_MODELLED)],
    'diesel-injector': [`Injector${cyl}`, 'ignition', card('Sprays diesel straight into the hot compressed air, which lights it.', [
      ['Injection starts', `${f(-(E.input.combustion_start_deg ?? -8))}° BTDC`], ['Air-fuel ratio', f(o.air_fuel_ratio, 1)]])],
    plug: [`Spark plug${cyl}`, 'ignition', card('Lights the charge; it glows on this page as it fires.', [
      ['Spark', `${f(-(E.input.combustion_start_deg ?? -15))}° BTDC`], ['Burn duration', `${f(E.input.burn_duration_deg ?? 50)}°`]])],
    coil: [`Ignition coil${cyl}`, 'ignition', card('Coil on plug: steps the battery voltage up to fire one plug.', [], NOT_MODELLED)],
    header: [`Exhaust header${cyl}`, 'exhaust', card('Carries one cylinder’s exhaust to the collector. It glows as a black body at its wall temperature: steel starts to glow at the Draper point, 798 K, and brightens as T⁴.', [['Gas at valve opening', `${f(o.exhaust_temperature_K)} K`], ['Port gas after blowdown', `${f(E.portTemp)} K`], ['Wall (estimate)', `${f(E.wallTemp)} K`]], 'Port gas: isentropic blowdown from the solver’s pressure at valve opening to the exhaust pressure. Wall taken 150 K below it, an assumption.')],
    collector: ['Exhaust collector', 'exhaust', card('Merges the headers of a bank.', [['Back pressure', `${f(o.exhaust_pressure_Pa / 1e5, 2)} bar`]])],
    downpipe: ['Downpipe', 'exhaust', card('Takes the exhaust away from the engine.', [], NOT_MODELLED)],
    turbo: ['Turbocharger', 'exhaust', card('Exhaust spins the turbine; the compressor on the same shaft pushes air into the intake.', [
      ['Boost (absolute)', `${f(o.boost_pressure_Pa / 1e5, 2)} bar`], ['Turbine pressure ratio', f(o.turbine_pressure_ratio, 2)],
      ['Compressor power', `${f(o.compressor_power_W / 1e3, 1)} kW`],
      ['Sustainable', o.boost_sustainable === false ? 'no: the exhaust cannot drive this boost' : 'yes']],
      `The wheels turn only so the part reads as rotating; shaft speed is not modelled. ${E.hw.note}`)],
    'charge-pipe': ['Charge pipe', 'intake', card('Carries compressed air from the turbo to the throttle.', [], NOT_MODELLED)],
    'timing-cover': ['Timing cover', 'timing', card('Encloses the cam drive and keeps its oil in; the crank nose passes through a seal in it.', [['Chain length', mm(E.timingLength ?? NaN, 0)]], NOT_MODELLED)],
    bellhousing: ['Bellhousing', 'block', card('Bolts the gearbox to the back of the block and shrouds the flywheel and clutch.', [], NOT_MODELLED)],
    starter: ['Starter motor', 'accessory', card('Throws a small pinion into the flywheel’s ring gear and spins the engine until it fires.', [], NOT_MODELLED)],
    mount: ['Engine mount', 'block', card('A rubber bush between block and chassis that carries the engine’s weight and torque reaction and soaks up its vibration.', [['Torque reacted', `${f(o.brake_torque_Nm)} N·m`]], NOT_MODELLED)],
    'ac-compressor': ['A/C compressor', 'accessory', card('Driven by the belt through a clutch; it pumps refrigerant for the cabin air conditioning.', [], NOT_MODELLED)],
    'oil-cap': ['Oil filler cap', 'head', card('Where the oil goes in, on top of the cam cover.', [], NOT_MODELLED)],
    harness: ['Engine harness', 'ignition', card('The wiring looms that connect the coils, injectors and sensors to the engine computer.', [], NOT_MODELLED)],
    catalyst: ['Catalytic converter', 'exhaust', card('A ceramic honeycomb coated in platinum-group metals that oxidises CO and hydrocarbons and reduces NOx.', [], NOT_MODELLED)],
    'o2-sensor': ['Lambda sensor', 'exhaust', card('Measures the oxygen left in the exhaust, so the engine computer can hold the mixture.', [['Air-fuel ratio', f(o.air_fuel_ratio, 1)]], NOT_MODELLED)],
    'air-filter': ['Air filter', 'intake', card('A pleated element that cleans the air before the throttle.', [], NOT_MODELLED)],
    'knock-sensor': ['Knock sensor', 'block', card('A piezo accelerometer on the block that hears detonation, so the engine computer can retard the spark.', [], NOT_MODELLED)],
    'cam-sensor': ['Cam position sensor', 'head', card('Reads a target wheel on the cam so the engine computer knows which stroke each cylinder is on.', [['Cam speed', `${f(E.rpm / 2)} rpm`]], NOT_MODELLED)],
    'crank-sensor': ['Crank position sensor', 'timing', card('Counts teeth on a wheel behind the crank pulley: engine speed and crank angle for spark and injection timing.', [['Crank speed', `${f(E.rpm)} rpm`]], NOT_MODELLED)],
    'oil-sensor': ['Oil pressure sender', 'lube', card('Reads the pressure in the main gallery for the gauge and the warning light.', [], NOT_MODELLED)],
    'map-sensor': ['MAP sensor', 'intake', card('Reads the absolute pressure in the plenum, from which the engine computer works out the air mass going in.', [['Intake pressure', `${f(pIn / 1e5, 2)} bar`]], NOT_MODELLED)],
    'coolant-sensor': ['Coolant temperature sender', 'accessory', card('Tells the engine computer how warm the engine is, for cold-start fuelling and the fan.', [], NOT_MODELLED)],
    pcv: ['Crankcase vent (PCV)', 'intake', card('Draws the gas that leaks past the rings out of the crankcase and back into the intake to be burned.', [], NOT_MODELLED)],
    'booster-hose': ['Brake booster hose', 'intake', card('Plenum vacuum to the brake servo.', [], NOT_MODELLED)],
    'fuel-line': ['Fuel feed line', 'ignition', card('Brings fuel from the tank pump to the rail.', [], NOT_MODELLED)],
    'heater-hose': ['Heater hose', 'accessory', card('Takes hot coolant to the cabin heater core and back.', [], NOT_MODELLED)],
    'turbo-oil': ['Turbo oil lines', 'exhaust', card('Pressure oil in to the turbo’s bearings from the block, and a gravity drain back to the sump.', [], NOT_MODELLED)],
    thermostat: ['Thermostat and upper hose', 'accessory', card('A wax valve that stays shut until the coolant is warm, then lets it out to the radiator.', [], NOT_MODELLED)],
  };
  const t = T[id];
  return t ? {name: t[0], layer: t[1], html: t[2]} : {name: id, layer: '', html: ''};
}
