// The page you drive. One clock poses the engine and feeds every readout: spools turn at their own speeds, the gas
// moves at the solver's station speeds, and the station panel reads the same layout the parts were placed on. Drag
// to orbit, wheel or pinch to zoom, click a part to inspect it, pick a station to follow the gas through the engine,
// switch layers off, pull the modules apart. Left alone for 25 s it tours itself.
import {warmComposer} from 'teardown-kit/warm.js';
import {Box3, Vector3} from 'three';
import {LAYERS} from './engine.js';
import {GALLERY} from './gallery.js';
import {partInfo} from './info.js';
import {makeJet, scaleSpools, workOf} from './kin.js';
import {createStage} from './stage.js';
import {initPhoto} from '../shared/photo.js';
import {SHARED_CSS, buildBOM, renderBOM} from '../shared/bom.js';
import {STATES as WEAR_STATES} from '../shared/wear.js';

const IDLE = 25;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const PLAYS = [1 / 10000, 1 / 3000, 1 / 1000, 1 / 300, 1 / 100, 1 / 30, 1 / 10];
// the cycle inputs a visitor can move, per family: [field, label, min, max, step, unit, default]. Ranges sit inside
// the solver's own validation limits.
const CYCLE = {
  turbofan: [['turbine_inlet_temperature_K', 'Turbine inlet temperature (throttle)', 1100, 1900, 10, 'K', 1550], ['mach', 'Flight Mach', 0, 0.9, 0.01, '', 0.78], ['altitude_m', 'Altitude', 0, 13000, 250, 'm', 10000]],
  turbojet: [['turbine_inlet_temperature_K', 'Turbine inlet temperature (throttle)', 900, 1500, 10, 'K', 1400], ['afterburner_exit_temperature_K', 'Afterburner exit temperature', 900, 2200, 20, 'K', null], ['mach', 'Flight Mach', 0, 1.6, 0.01, '', 0.8], ['altitude_m', 'Altitude', 0, 15000, 250, 'm', 10000]],
  turboprop: [['turbine_inlet_temperature_K', 'Turbine inlet temperature (throttle)', 900, 1500, 10, 'K', 1250], ['mach', 'Flight Mach', 0, 0.6, 0.01, '', 0.35], ['altitude_m', 'Altitude', 0, 9000, 250, 'm', 5000]],
  ramjet: [['combustor_exit_temperature_K', 'Combustor exit temperature', 1400, 2400, 20, 'K', 1900], ['mach', 'Flight Mach', 1.5, 4, 0.05, '', 2.2], ['altitude_m', 'Altitude', 5000, 25000, 500, 'm', 15000]],
  scramjet: [['equivalence_ratio', 'Equivalence ratio (fuel)', 0.3, 1.2, 0.02, '', 0.7], ['mach', 'Flight Mach', 4, 10, 0.1, '', 5], ['altitude_m', 'Altitude', 15000, 35000, 500, 'm', 22000]],
};
const VIEWS = {
  '3/4': {az: 0.95, el: 0.3},
  Front: {az: 0.02, el: 0.06},
  Side: {az: Math.PI / 2, el: 0.06},
  Top: {az: 0.6, el: 1.25},
};
const CUTS = ['Cutaway', 'Half', 'Solid'];
const FAMILY = {turbofan: 'Turbofans', turbojet: 'Turbojet', turboprop: 'Turboprop', ramjet: 'Ramjet', scramjet: 'Scramjet'};
const api = () => new URLSearchParams(location.search).get('api') || '';
const fmt = (v, d = 0) => (v == null || !isFinite(v) ? '-' : v.toLocaleString(undefined, {minimumFractionDigits: d, maximumFractionDigits: d}));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
};
const sizeCanvas = (c) => {
  const w = Math.max(1, Math.round(c.clientWidth));
  const h = Math.max(1, Math.round(c.clientHeight));
  const pr = Math.min(3, devicePixelRatio || 1);
  const bw = Math.min(2048, Math.round(w * pr));
  const bh = Math.min(2048, Math.round(h * pr));
  if (c.width !== bw || c.height !== bh) {
    c.width = bw;
    c.height = bh;
  }
  const g = c.getContext('2d');
  g.setTransform(bw / w, 0, 0, bh / h, 0, 0);
  return {g, w, h};
};

export function runLive() {
  const app = document.getElementById('app');
  const canvas = el('canvas');
  canvas.id = 'gl';
  canvas.setAttribute('aria-label', 'Interactive 3D engine cutaway. Drag to orbit, scroll to zoom, click a part to inspect it.');
  canvas.setAttribute('role', 'img');
  app.appendChild(canvas);
  const st = createStage({canvas});

  // ------------------------------------------------------------ overlay
  const ui = el('div', 'ui');
  app.appendChild(ui);
  ui.appendChild(el('div', 'overlay', '<svg id="ov-svg" aria-hidden="true"></svg><div id="ov-labels"></div>'));
  const top = el('header', 'bar');
  top.innerHTML = `
    <a class="brand" href="/" aria-label="DAS LABS home">
      <img class="brand-mark" src="/lab/assets/das_labs_logo_dark.png?v=20260529-2" alt="DAS LABS" onerror="this.outerHTML='<b class=&quot;brand-txt&quot;>DAS LABS</b>'">
      <span class="brand-dot"></span>
      <img class="brand-product" src="/lab/assets/propulsionlab_wordmark.png" alt="PropulsionLab" onerror="this.outerHTML='<span class=&quot;brand-txt2&quot;>PropulsionLab</span>'">
      <span class="pill">3D</span>
    </a>
    <div class="pl-title"><b id="t-name">Engine</b><span id="t-sub"></span></div>
    <div class="tools">
      <div class="seg" role="group" aria-label="Camera view" id="g-view"></div>
      <div class="seg" role="group" aria-label="Cutaway" id="g-cut"></div>
      <div class="seg" role="group" aria-label="Overlays">
        <button id="b-explode" aria-pressed="false" title="Pull the modules apart">Explode</button>
        <button id="b-photo" title="Photo mode: presets, focal length, depth of field, high-resolution stills">Photo</button>
        <button id="b-labels" aria-pressed="false" title="Name the main parts">Labels</button>
      </div>
      <a class="ghost" href="/lab/">Console</a>
    </div>`;
  ui.appendChild(top);

  const side = el('nav', 'pl-side panel');
  side.setAttribute('aria-label', 'Engines and layers');
  side.innerHTML = `
    <div class="tabs" role="tablist">
      <button role="tab" id="tab-eng" aria-selected="true">Engines</button>
      <button role="tab" id="tab-lay" aria-selected="false">Layers</button>
      <button role="tab" id="tab-cyc" aria-selected="false">Cycle</button>
      <button role="tab" id="tab-bom" aria-selected="false">Parts</button>
    </div>
    <div id="pane-eng"></div>
    <div id="pane-bom" hidden></div>
    <div id="pane-cyc" hidden>
      <p class="cycnote">Move an input and the cycle is solved again: the casings resize, the flame and glow follow the new temperatures, the spools change speed and the gas its velocities.</p>
      <div id="cyc"></div>
      <div class="cycstat mono" id="cyc-stat"></div>
      <button id="cyc-reset">Back to the design point</button>
      <div class="lbl envlbl">Flow colour</div>
      <div class="quick" id="flowc"></div>
      <div class="legend" id="flow-leg"></div>
      <div class="lbl envlbl">Analysis</div>
      <label class="layer"><input type="checkbox" id="an-thermal"><span>Thermal view (gas temperature on every part)</span></label>
      <div class="legend" id="therm-leg" hidden></div>
      <label class="layer"><input type="checkbox" id="an-haze" checked><span>Heat haze</span></label>
      <div class="lbl envlbl">Blade vibration</div>
      <div class="quick" id="vibm"></div>
      <label class="envrow"><span class="lbl">Amplitude</span><input type="range" id="vib-amp" min="0" max="100" value="40" aria-label="Vibration amplitude"></label>
      <label class="envrow"><span class="lbl">Growth x</span><input type="range" id="grow" min="0" max="40" value="0" aria-label="Exaggerate thermal growth"></label>
      <div class="cycstat mono" id="grow-stat"></div>
    </div>
    <div id="pane-lay" hidden>
      <div class="lbl">Explode</div>
      <input type="range" id="explode" min="0" max="100" value="0" aria-label="Pull the modules apart">
      <div class="quick"><button id="l-all">Show all</button><button id="l-core">Gas path</button><button id="l-rot">Rotors</button></div>
      <div id="layers"></div>
      <div class="lbl envlbl">Service state</div>
      <div class="quick" id="wears"></div>
      <div class="lbl envlbl">Environment</div>
      <div class="quick" id="envs"></div>
      <label class="envrow"><span class="lbl">Rotate</span><input type="range" id="env-rot" min="0" max="360" value="0" aria-label="Rotate the environment"></label>
      <label class="envrow"><span class="lbl">Exposure</span><input type="range" id="env-exp" min="60" max="200" value="130" aria-label="Exposure"></label>
    </div>`;
  ui.appendChild(side);

  const right = el('div', 'rightcol');
  const panel = el('section', 'panel cyl');
  panel.setAttribute('aria-label', 'Station');
  panel.innerHTML = `
    <div class="lbl" id="p-cyl">Station</div>
    <div class="stroke"><b id="p-stroke">INLET</b><span class="mono" id="p-ang"></span></div>
    <div class="grid mono">
      <div><span class="lbl">Total temp</span><span class="v" id="p-T"></span></div>
      <div><span class="lbl">Total press</span><span class="v" id="p-p"></span></div>
      <div><span class="lbl">Axial speed</span><span class="v" id="p-V"></span></div>
      <div><span class="lbl">Thrust</span><span class="v" id="p-F"></span></div>
      <div><span class="lbl">TSFC</span><span class="v" id="p-sfc"></span></div>
      <div><span class="lbl" id="p-xl">Bypass</span><span class="v" id="p-x"></span></div>
    </div>
    <canvas class="chart" id="c-tp" aria-label="Total temperature and pressure along the engine"></canvas>
    <div class="spools mono" id="spools"></div>`;
  const pcard = el('section', 'panel part');
  pcard.hidden = true;
  pcard.setAttribute('aria-live', 'polite');
  right.append(panel, pcard);
  ui.appendChild(right);

  const bottom = el('div', 'bottom panel');
  bottom.innerHTML = `
    <div><div class="lbl">Follow the gas</div><div class="order" id="order" role="group" aria-label="Stations"></div></div>
    <div class="play">
      <button id="b-play" aria-label="Pause">Pause</button>
    </div>
    <label class="speed"><span class="lbl"><span class="long" id="s-lbl">Speed</span><span class="short" id="s-lbl2">Speed</span></span><input type="range" id="s-play" min="0" max="${PLAYS.length - 1}" step="1"></label>`;
  ui.appendChild(bottom);
  const mob = el('div', 'mobtabs');
  mob.innerHTML = '<button id="m-eng" aria-expanded="false">Engines</button><button id="m-lay" aria-expanded="false">Layers</button>';
  ui.appendChild(mob);
  ui.appendChild(el('div', 'hint', 'Click a part to inspect it &middot; drag to orbit &middot; scroll to zoom'));
  const tourChip = el('button', 'tourchip', '<i></i>Auto tour');
  tourChip.setAttribute('aria-label', 'Auto tour running. Click to take control.');
  ui.appendChild(tourChip);
  const msg = el('div', 'msg panel');
  msg.hidden = true;
  ui.appendChild(msg);
  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------ quality tiers
  // quality tiers: MSAA, ambient occlusion, shadow map size and cadence, pixel ratio, glow, model detail
  const TIERS = [
    {samples: 4, ao: true, shadow: 2048, pr: 2, glow: true, every: 4, detail: 1},
    {samples: 2, ao: false, shadow: 1024, pr: 1.5, glow: true, every: 12, detail: 1},
    {samples: 0, ao: false, shadow: 1024, pr: 1, glow: false, every: 0, detail: 0.5},
  ];
  const coarse = matchMedia('(pointer: coarse)').matches || Math.min(innerWidth, innerHeight) < 700;
  let tier = coarse ? 1 : 0;
  const fit = () => st.resize(innerWidth, innerHeight, Math.min(devicePixelRatio || 1, TIERS[tier].pr));
  const applyTier = () => {
    const {pr, every, detail, ...q} = TIERS[tier];
    st.setQuality(q);
    st.setShadowEvery(every);
    st.setHaze?.(tier < 2);
    fit();
    // the lowest tier rebuilds the model at half detail (fewer lathe segments, coarser blades, fewer tracers)
    // (window.LIVE exists only once the page is set up, so the first call, before the model loads, skips this)
    const Jn = window.LIVE?.J;
    if (Jn && (Jn.detail ?? 1) !== detail) {
      Jn.detail = detail;
      window.LIVE.rebuild();
    }
  };
  applyTier();
  addEventListener('resize', fit);

  // ------------------------------------------------------------ state
  let J = null;
  let t = 0;
  let paused = false;
  let playI = 2;
  let stationI = 0;
  let cut = 'Cutaway';
  let view = '3/4';
  let explode = 0;
  let explodeTo = 0;
  let selected = null;
  const shownLayers = Object.fromEntries(LAYERS.map((l) => [l.id, true]));
  const K0 = 0.62;
  const cam = {...VIEWS['3/4'], k: K0, target: null};
  const camTo = {...cam};
  let current = null;
  let lastInput = -1e9;
  let tourOn = true;
  let tourT0 = 0;
  let T = 0;
  const press = (id, on) => $(id).setAttribute('aria-pressed', String(on));

  const segs = (box, items, get, set) => {
    box.innerHTML = '';
    for (const it of items) {
      const b = el('button', null, it);
      b.setAttribute('aria-pressed', String(get() === it));
      b.onclick = () => {
        takeOver();
        set(it);
        refreshSegs();
      };
      box.appendChild(b);
    }
  };
  const refreshSegs = () => {
    for (const [id, get] of [['g-view', () => view], ['g-cut', () => cut]]) for (const x of $(id).children) x.setAttribute('aria-pressed', String(x.textContent === get()));
  };
  const setView = (v) => {
    view = v;
    Object.assign(camTo, VIEWS[v], {k: K0});
    unfocus();
  };
  segs($('g-view'), Object.keys(VIEWS), () => view, setView);
  // a different cut is a different model: the cut is built into the casings' geometry
  const setCutMode = (c) => {
    cut = c;
    if (J) rebuild();
  };
  segs($('g-cut'), CUTS, () => cut, setCutMode);

  // ------------------------------------------------------------ side panel
  const showTab = (which) => {
    for (const k of ['eng', 'lay', 'cyc', 'bom']) {
      $(`tab-${k}`).setAttribute('aria-selected', String(which === k));
      $(`pane-${k}`).hidden = which !== k;
    }
  };
  $('tab-cyc').onclick = () => showTab('cyc');
  $('tab-bom').onclick = () => {
    showTab('bom');
    refreshBOM();
  };
  $('tab-eng').onclick = () => showTab('eng');
  $('tab-lay').onclick = () => showTab('lay');
  const openSheet = (which) => {
    const open = !(side.classList.contains('open') && !$(`pane-${which}`).hidden);
    side.classList.toggle('open', open);
    showTab(which);
    $('m-eng').setAttribute('aria-expanded', String(open && which === 'eng'));
    $('m-lay').setAttribute('aria-expanded', String(open && which === 'lay'));
  };
  $('m-eng').onclick = () => openSheet('eng');
  $('m-lay').onclick = () => openSheet('lay');
  const renderLayers = () => {
    const box = $('layers');
    box.innerHTML = '';
    for (const L of LAYERS) {
      const row = el('label', 'layer', `<input type="checkbox" id="ly-${L.id}" ${shownLayers[L.id] ? 'checked' : ''}><span>${L.name}</span>`);
      row.querySelector('input').onchange = (e) => {
        takeOver();
        setLayer(L.id, e.target.checked);
      };
      box.appendChild(row);
    }
  };
  const setLayer = (id, on) => {
    shownLayers[id] = on;
    st.eng?.setLayer(id, on);
    st.markShadows();
    const box = $(`ly-${id}`);
    if (box) box.checked = on;
    if (!on && selected && partInfo(selected.id, selected.meta, J).layer === id) select(null);
  };
  const preset = (ids) => {
    takeOver();
    for (const L of LAYERS) setLayer(L.id, !ids || ids.includes(L.id));
  };
  $('l-all').onclick = () => preset(null);
  $('l-core').onclick = () => preset(['rotor', 'stator', 'combustor', 'flow', 'shaft']);
  $('l-rot').onclick = () => preset(['rotor', 'shaft', 'gearbox']);
  $('explode').oninput = (e) => {
    takeOver();
    explodeTo = Number(e.target.value) / 100;
    press('b-explode', explodeTo > 0.01);
  };
  renderLayers();
  // service state: from factory new to overhaul condition, without changing the geometry
  let wearId = 'new';
  const renderWears = () => {
    const box = $('wears');
    box.innerHTML = '';
    for (const s of WEAR_STATES) {
      const b = el('button', null, s.name);
      b.setAttribute('aria-pressed', String(wearId === s.id));
      b.onclick = () => {
        takeOver();
        wearId = s.id;
        st.setWear(s.wear);
        renderWears();
      };
      box.appendChild(b);
    }
  };
  renderWears();
  // the lighting environment: four presets, a rotation, an exposure
  const ENVS = {studio: 'Studio', testcell: 'Test cell', hangar: 'Hangar', overcast: 'Overcast'};
  const renderEnvs = () => {
    const box = $('envs');
    box.innerHTML = '';
    for (const [id, name] of Object.entries(ENVS)) {
      const b = el('button', null, name);
      b.setAttribute('aria-pressed', String(st.envName === id));
      b.onclick = () => {
        takeOver();
        st.setEnvironment(id);
        renderEnvs();
      };
      box.appendChild(b);
    }
  };
  renderEnvs();
  $('env-rot').oninput = (e) => {
    takeOver();
    st.setEnvRotation((Number(e.target.value) * Math.PI) / 180);
  };
  $('env-exp').oninput = (e) => {
    takeOver();
    st.setExposure(Number(e.target.value) / 100);
  };

  const parseHash = () => {
    const h = new URLSearchParams(location.hash.slice(1));
    return GALLERY.find((x) => x.id === h.get('g')) ?? null;
  };
  const renderEngines = () => {
    const pane = $('pane-eng');
    pane.innerHTML = '';
    let fam = '';
    for (const g of GALLERY) {
      if (g.family !== fam) {
        fam = g.family;
        pane.appendChild(el('div', 'lbl famlbl', FAMILY[fam]));
      }
      const b = el('button', 'eng', `<b>${esc(g.name)}</b><small>${esc(g.sub)}</small>`);
      b.setAttribute('aria-current', String(current?.id === g.id));
      b.onclick = () => {
        takeOver();
        side.classList.remove('open');
        history.replaceState(null, '', `#g=${g.id}`);
        load(g);
      };
      pane.appendChild(b);
    }
    const facts = el('dl', 'facts');
    facts.id = 'facts';
    pane.appendChild(facts);
    if (J) fillFacts();
  };
  const fillFacts = () => {
    const o = J.out;
    const ex = o.extra ?? {};
    const rows = [['Thrust', `${fmt(o.thrust_kN, 1)} kN`], ['TSFC', `${fmt(o.TSFC_kg_per_kN_hr, 1)} kg/kN/h`]];
    if (J.family === 'turbofan') rows.push(['Bypass ratio', fmt(ex.bypass_ratio ?? J.input.bypass_ratio, 1)], ['Overall pressure ratio', `${fmt(ex.overall_pressure_ratio, 1)} : 1`]);
    if (J.family === 'turbojet') rows.push(['Pressure ratio', `${fmt(J.input.compressor_pressure_ratio, 1)} : 1`]);
    if (J.family === 'turboprop') rows.push(['Shaft power', `${fmt(o.shaft_power_kW)} kW`], ['Propeller efficiency', `${fmt((ex.propeller_efficiency ?? 0) * 100)} %`]);
    if (J.family === 'ramjet' || J.family === 'scramjet') rows.push(['Flight Mach', fmt(J.mach, 1)], ['Ram pressure ratio', fmt(ex.ram_pressure_ratio, 1)]);
    const s4 = J.stations.find((s) => /hpt-in|comb-exit/.test(s.id));
    rows.push(['Peak gas temperature', `${fmt(Math.max(s4?.Tt ?? 0, J.afterburner?.T ?? 0))} K`], ['Air flow', `${fmt(J.mTot, 1)} kg/s`]);
    if (J.family === 'turbofan' || J.family === 'turbojet' || J.family === 'turboprop') rows.push([J.family === 'turbofan' ? 'Fan diameter' : 'Inlet diameter', `${fmt(J.D, 2)} m`]);
    rows.push(['Thermal efficiency', `${fmt((o.thermal_efficiency_estimate ?? 0) * 100, 1)} %`]);
    const f = $('facts');
    f.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd class="mono">${v}</dd>`).join('');
    const notes = [J.hw.note, `Flight condition: Mach ${fmt(J.mach, 2)}${J.input.altitude_m != null ? `, ${fmt(J.input.altitude_m)} m` : ', at the solver’s default altitude'}.`,
      'Casing radii come from the area each station needs to pass the solver’s mass flow at its state, at assumed axial Mach numbers, scaled to the published diameter. Stage and blade counts are published figures; spool speeds approximate. Thrust and temperatures are PropulsionLab’s model, not the maker’s data.'];
    f.insertAdjacentHTML('beforeend', notes.filter(Boolean).map((n) => `<div class="note">${esc(n)}</div>`).join(''));
  };

  // ------------------------------------------------------------ part inspector
  const unfocus = () => {
    if (!camTo.target) return;
    camTo.target = null;
    camTo.k = K0;
  };
  const select = (hit) => {
    selected = hit;
    st.highlight(hit?.obj ?? null);
    if (!hit) {
      pcard.hidden = true;
      right.classList.remove('has-part');
      unfocus();
      return;
    }
    const f = st.focusOf(hit.obj);
    camTo.target = f.center;
    if (!cam.target) cam.target = st.fit.center.clone();
    camTo.k = clamp((Math.max(f.radius, 0.25 * J.D) / st.fit.radius) * 1.8, 0.16, K0);
    const info = partInfo(hit.id, hit.meta, J);
    const lname = LAYERS.find((l) => l.id === info.layer)?.name ?? '';
    pcard.innerHTML = `<div class="phead"><div><div class="lbl">${esc(lname)}</div><b>${esc(info.name)}</b></div><button class="x" id="p-close" aria-label="Close part details">&times;</button></div><div class="pbody">${info.html}</div>`;
    pcard.hidden = false;
    right.classList.add('has-part');
    $('p-close').onclick = () => select(null);
  };

  // ------------------------------------------------------------ labels: one per major part, laid out in two columns
  let labelsOn = false;
  $('b-explode').onclick = () => {
    takeOver();
    explodeTo = explodeTo > 0.01 ? 0 : 0.7;
    $('explode').value = Math.round(explodeTo * 100);
    press('b-explode', explodeTo > 0.01);
  };
  $('b-labels').onclick = () => {
    takeOver();
    labelsOn = !labelsOn;
    press('b-labels', labelsOn);
  };
  const LABEL_IDS = ['fan', 'spinner', 'ogv', 'booster', 'ipc', 'hpc', 'compressor', 'impeller', 'combustor', 'fuel-nozzle', 'hpt', 'ipt', 'lpt', 'pt', 'plug', 'core-nozzle', 'nacelle', 'agb', 'fadec', 'fan-gearbox', 'propeller', 'rgb', 'afterburner', 'nozzle-petals', 'spike', 'cowl', 'flameholder', 'forebody', 'strut', 'shock', 'vsv'];
  let anchors = [];
  const collectAnchors = () => {
    anchors = [];
    const seen = new Set();
    st.eng.root.updateMatrixWorld(true);
    st.eng.root.traverse((o) => {
      const pk = o.userData.pick;
      if (!pk || !LABEL_IDS.includes(pk.id) || seen.has(pk.id)) return;
      seen.add(pk.id);
      // the part's centre in its parent's frame, so it follows the explode
      const c = new Box3().setFromObject(o).getCenter(new Vector3());
      anchors.push({obj: o, id: pk.id, meta: pk.meta, local: o.parent.worldToLocal(c.clone())});
    });
  };
  const shownInScene = (o) => {
    for (let x = o; x; x = x.parent) if (!x.visible) return false;
    return true;
  };
  const proj = new Vector3();
  const toScreen = (v) => {
    proj.copy(v).project(st.camera);
    if (proj.z > 1 || Math.abs(proj.x) > 1.05 || Math.abs(proj.y) > 1.05) return null;
    return [(proj.x * 0.5 + 0.5) * innerWidth, (-proj.y * 0.5 + 0.5) * innerHeight];
  };
  const drawOverlay = (fa) => {
    let lines = '';
    let html = '';
    if (labelsOn && J && innerWidth > 700) {
      const Wd = innerWidth;
      const lx = fa.l + 14;
      const rx = Wd - fa.rt - 14;
      const cx = (fa.l + Wd - fa.rt) / 2;
      const items = [];
      for (const a of anchors) {
        if (!shownInScene(a.obj)) continue;
        const sp = toScreen(a.obj.parent.localToWorld(a.local.clone()));
        if (!sp) continue;
        items.push({a, sp, name: partInfo(a.id, a.meta, J).name, left: sp[0] < cx});
      }
      for (const sideL of [true, false]) {
        const col = items.filter((x) => x.left === sideL).sort((u, v) => u.sp[1] - v.sp[1]);
        const topY = fa.t + 16;
        const bot = innerHeight - fa.b - 16;
        let y = topY;
        for (const it of col) {
          it.y = Math.max(it.sp[1], y);
          y = it.y + 24;
        }
        let over = col.length ? col[col.length - 1].y - bot : 0;
        for (let i = col.length - 1; i >= 0 && over > 0; i--) {
          col[i].y -= over;
          over = i > 0 ? Math.max(0, col[i - 1].y + 24 - col[i].y) : 0;
        }
        for (const it of col) {
          const x = sideL ? lx : rx;
          const ex = sideL ? x + 150 : x - 150;
          const elbow = sideL ? ex + 24 : ex - 24;
          const sel = selected && selected.obj === it.a.obj ? 'sel' : '';
          lines += `<polyline points="${ex},${it.y} ${elbow},${it.y} ${it.sp[0]},${it.sp[1]}" class="${sel}"/><circle cx="${it.sp[0]}" cy="${it.sp[1]}" r="2.6" class="${sel}"/>`;
          html += `<button class="tag ${sideL ? 'l' : 'r'} ${sel}" style="top:${it.y - 10}px;${sideL ? `left:${x}px` : `right:${Wd - x}px`}" data-id="${it.a.id}">${esc(it.name)}</button>`;
        }
      }
    }
    $('ov-svg').innerHTML = lines;
    $('ov-labels').innerHTML = html;
  };
  $('ov-labels').addEventListener('click', (e) => {
    const tg = e.target.closest('.tag');
    if (!tg) return;
    takeOver();
    const a = anchors.find((x) => x.id === tg.dataset.id);
    if (a) select({obj: a.obj, id: a.id, meta: a.meta});
  });

  // ------------------------------------------------------------ solve and build
  let loadSeq = 0;
  const showMsg = (html, retry) => {
    msg.innerHTML = html + (retry ? '<br><button id="m-retry">Try again</button>' : '');
    msg.hidden = false;
    if (retry) $('m-retry').onclick = retry;
  };
  const rebuild = () => {
    J.cut = cut.toLowerCase();
    select(null);
    const eng = st.setEngine(J);
    for (const L of LAYERS) eng.setLayer(L.id, shownLayers[L.id]);
    eng.setExplode(explode);
    applyOverlays();
    collectAnchors();
  };
  // ------------------------------------------------------------ the cycle and physics overlays
  let overrides = {};
  let designWork = null;
  let flowMode = 'temperature';
  let vibMode = 0;
  const fmtIn = (v, step, unit) => `${fmt(v, step < 0.1 ? 2 : step < 1 ? 1 : 0)}${unit ? ` ${unit}` : ''}`;
  const renderCycle = () => {
    const box = $('cyc');
    box.innerHTML = '';
    for (const [k, label, lo, hi, step, unit, def] of CYCLE[current.family] ?? []) {
      const base = current.body[k] ?? def;
      if (k === 'afterburner_exit_temperature_K' && base == null) continue;
      const v = overrides[k] ?? base;
      const row = el('label', 'cycrow', `<span class="lbl">${label}</span><span class="mono" id="cv-${k}">${fmtIn(v, step, unit)}</span><input type="range" min="${lo}" max="${hi}" step="${step}" value="${v}" aria-label="${label}">`);
      const inp = row.querySelector('input');
      inp.oninput = () => {
        takeOver();
        $(`cv-${k}`).textContent = fmtIn(Number(inp.value), step, unit);
        overrides[k] = Number(inp.value);
        resolveSoon();
      };
      box.appendChild(row);
    }
    cycStat();
  };
  const cycStat = () => {
    if (!J) return;
    const o = J.out;
    const sp = Object.entries(J.speedRatio ?? {}).map(([k, r]) => `${k.toUpperCase()} ${fmt(r * 100)} %`).join(', ');
    const prs = Object.keys(overrides).length ? Object.entries(J_op).map(([k, v]) => `${k.startsWith('fan') ? 'fan' : 'core'} PR ${fmt(v, k.startsWith('fan') ? 2 : 1)}`).join(', ') : '';
    $('cyc-stat').innerHTML = `Thrust ${fmt(o.thrust_kN, 1)} kN &middot; TSFC ${fmt(o.TSFC_kg_per_kN_hr, 1)}<br>Peak gas ${fmt(Math.max(...J.stations.map((x) => x.Tt)))} K${prs ? `<br>On the operating line: ${prs}` : ''}${sp ? `<br>Spool speed vs design: ${sp}` : ''}`;
  };
  // The operating line. With the turbine nozzle guide vanes and the exhaust nozzle choked, the turbine's temperature
  // ratio is fixed, and the work balance gives a compressor temperature rise proportional to T4 / T2:
  //   (tau_c - 1) = (tau_c,design - 1) * (T4 / T4,design) * (T2,design / T2)
  // so pressure ratios (and with them, by Euler's equation, spool speeds) follow the throttle and the flight
  // condition instead of staying at their design values. Ambient temperature from the ISA.
  const isaT = (h) => (h < 11000 ? 288.15 - 0.0065 * h : 216.65);
  const DEF = {turbofan: {T4: 1550, M: 0.78, h: 10000}, turbojet: {T4: 1400, M: 0.8, h: 10000}, turboprop: {T4: 1250, M: 0.35, h: 5000}};
  const PRS = {turbofan: [['core_compressor_pressure_ratio', 18, 0.88, 50], ['fan_pressure_ratio', 1.55, 0.89, 3.5]], turbojet: [['compressor_pressure_ratio', 12, 0.86, 40]], turboprop: [['compressor_pressure_ratio', 9, 0.84, 30]]};
  const operatingLine = (g, ov) => {
    const d = DEF[g.family];
    if (!d || !Object.keys(ov).length) return {};
    const b = g.body;
    const T2 = (h, M) => isaT(h) * (1 + 0.2 * M * M);
    const k = ((ov.turbine_inlet_temperature_K ?? b.turbine_inlet_temperature_K ?? d.T4) / (b.turbine_inlet_temperature_K ?? d.T4)) * (T2(b.altitude_m ?? d.h, b.mach ?? d.M) / T2(ov.altitude_m ?? b.altitude_m ?? d.h, ov.mach ?? b.mach ?? d.M));
    const res = {};
    for (const [f, def, eta, max] of PRS[g.family]) {
      const pr = b[f] ?? def;
      const tau = 1 + ((Math.pow(pr, 0.2857) - 1) / eta) * k;
      res[f] = Math.min(max, Math.max(1.05, Math.pow(1 + eta * (tau - 1), 3.5)));
    }
    J_op = res;
    return res;
  };
  let J_op = {};
  let resolveTimer = 0;
  const resolveSoon = () => {
    clearTimeout(resolveTimer);
    resolveTimer = setTimeout(() => load(current, true), 280);
  };
  $('cyc-reset').onclick = () => {
    takeOver();
    overrides = {};
    load(current, true).then(renderCycle);
  };
  const FLOW = {temperature: 'Temperature', velocity: 'Velocity', pressure: 'Pressure'};
  const renderFlow = () => {
    const box = $('flowc');
    box.innerHTML = '';
    for (const [id, name] of Object.entries(FLOW)) {
      const b = el('button', null, name);
      b.setAttribute('aria-pressed', String(flowMode === id));
      b.onclick = () => {
        takeOver();
        flowMode = id;
        st.eng?.setFlowColor(id);
        renderFlow();
      };
      box.appendChild(b);
    }
    if (!J) return;
    const r = st.eng?.flowRange ?? {V: 0, P: 0};
    const viridis = 'linear-gradient(90deg,#440154,#3b528b,#21918c,#5ec962,#fde725)';
    const temp = 'linear-gradient(90deg,#8fb2ff,#d9ecff,#ffffff,#ffb36b,#ff7a1f)';
    const [g, lo, hi] = flowMode === 'velocity' ? [viridis, '0', `${fmt(r.V)} m/s`] : flowMode === 'pressure' ? [viridis, '0', `${fmt(r.P / 1e5, 1)} bar`] : [temp, 'cold', 'hot'];
    $('flow-leg').innerHTML = `<i style="background:${g}"></i><span>${lo}</span><span>${hi}</span>`;
  };
  const VIB = ['Off', '1st bending', '1st torsion'];
  const renderVib = () => {
    const box = $('vibm');
    box.innerHTML = '';
    VIB.forEach((name, i) => {
      const b = el('button', null, name);
      b.setAttribute('aria-pressed', String(vibMode === i));
      b.onclick = () => {
        takeOver();
        vibMode = i;
        st.eng?.setVibration(vibMode, Number($('vib-amp').value) / 100);
        renderVib();
      };
      box.appendChild(b);
    });
  };
  $('vib-amp').oninput = () => st.eng?.setVibration(vibMode, Number($('vib-amp').value) / 100);
  const growStat = () => {
    const k = Number($('grow').value);
    const hpt = J?.modules.find((m) => m.kind === 'hpt');
    $('grow-stat').textContent = k && hpt ? `HP turbine tip radius grows ${fmt(13e-6 * ((hpt.Tt0 + hpt.Tt1) / 2 - 293) * hpt.stages[0].rt * 1e3, 2)} mm in reality, shown x${k}` : '';
  };
  $('grow').oninput = () => {
    takeOver();
    st.eng?.setGrowth(Number($('grow').value));
    growStat();
  };
  $('an-thermal').onchange = (e) => {
    takeOver();
    st.eng?.setThermal(e.target.checked);
    thermLegend();
  };
  $('an-haze').onchange = (e) => st.setHaze(e.target.checked);
  const thermLegend = () => {
    const on = $('an-thermal').checked;
    $('therm-leg').hidden = !on;
    if (on && st.eng) $('therm-leg').innerHTML = `<i style="background:linear-gradient(90deg,#0b0723,#51127c,#b63679,#fb8761,#fcfdbf)"></i><span>${fmt(st.eng.info.Tmin)} K</span><span>${fmt(st.eng.info.Tmax)} K</span>`;
  };
  const applyOverlays = () => {
    const e = st.eng;
    e.setFlowColor(flowMode);
    e.setVibration(vibMode, Number($('vib-amp').value) / 100);
    e.setGrowth(Number($('grow').value));
    e.setThermal($('an-thermal').checked);
    renderFlow();
    thermLegend();
    growStat();
  };
  renderVib();
  async function load(g, resolve = false) {
    const seq = ++loadSeq;
    if (!resolve) {
      overrides = {};
      designWork = null;
    }
    current = g;
    select(null);
    renderEngines();
    $('t-name').textContent = g.name;
    // every model is representative: engineering-plausible, not the maker's drawings
    $('t-sub').textContent = `${g.sub} · representative model`;
    document.title = `${g.name} in 3D | PropulsionLab`;
    const body = {...g.body, ...overrides, ...operatingLine(g, overrides)};
    if (resolve) $('cyc-stat').textContent = 'Solving...';
    else showMsg('Solving the cycle...');
    let out;
    try {
      const res = await fetch(`${api()}/simulate/${g.family}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(typeof e.detail === 'string' ? e.detail : `The solver answered ${res.status}.`);
      }
      out = await res.json();
    } catch (e) {
      if (seq !== loadSeq) return;
      if (resolve) {
        $('cyc-stat').textContent = `The solver could not run this point: ${e.message || ''}`;
        return;
      }
      return showMsg(`Could not solve this engine. ${esc(e.message || '')}`, () => load(g));
    }
    if (seq !== loadSeq) return;
    msg.hidden = true;
    J = makeJet(g.family, body, out, g.hardware);
    J.detail = TIERS[tier].detail;
    if (!designWork) designWork = workOf(J);
    else scaleSpools(J, designWork);
    rebuild();
    if (resolve) {
      fillFacts();
      cycStat();
      return;
    }
    renderCycle();
    // a scramjet is a flat vehicle: look at it from low down, where the flow path shows
    VIEWS['3/4'].el = g.family === 'scramjet' ? 0.1 : 0.3;
    if (view === '3/4') camTo.el = VIEWS['3/4'].el;
    stationI = 0;
    buildStations();
    fillFacts();
    $('s-play').value = playI;
    await warmComposer(st.renderer, st.composer, st.scene, st.camera).catch(() => {});
  }

  const buildStations = () => {
    const box = $('order');
    box.innerHTML = '';
    J.stations.forEach((s, i) => {
      const b = el('button', 'chip mono', `${i + 1}<span class="flash"></span>`);
      b.dataset.i = i;
      b.title = s.label;
      b.setAttribute('aria-label', `Follow the gas at ${s.label}`);
      b.onclick = () => {
        takeOver();
        setStation(i, true);
      };
      box.appendChild(b);
    });
    setStation(0);
  };
  const setStation = (i, fly = false) => {
    stationI = i;
    for (const b of $('order').children) b.setAttribute('aria-pressed', String(Number(b.dataset.i) === i));
    if (fly) {
      const s = J.stations[i];
      camTo.target = new Vector3(0, 0, s.z);
      if (!cam.target) cam.target = st.fit.center.clone();
      camTo.k = 0.42;
    }
  };

  // ------------------------------------------------------------ the station panel and its chart
  const INK = '#f4f4f5';
  const GRID = 'rgba(255,255,255,0.07)';
  const AXIS = 'rgba(244,244,245,0.42)';
  const HOT = '#e8923e';
  const COLD = '#7fb6ff';
  const drawChart = () => {
    const c = $('c-tp');
    if (!c.clientWidth) return;
    const {g, w, h} = sizeCanvas(c);
    g.clearRect(0, 0, w, h);
    const sts = J.coreStations;
    const z0 = sts[0].z;
    const z1 = sts[sts.length - 1].z;
    const L = 30;
    const X = (z) => L + ((z0 - z) / (z0 - z1)) * (w - L - 30);
    const Tm = Math.max(...sts.map((s) => s.Tt)) * 1.1;
    const Pm = Math.max(...sts.map((s) => s.Pt)) * 1.1;
    const YT = (v) => h - 18 - (v / Tm) * (h - 30);
    const YP = (v) => h - 18 - (v / Pm) * (h - 30);
    g.strokeStyle = GRID;
    g.lineWidth = 1;
    for (let k = 1; k <= 3; k++) {
      g.beginPath();
      g.moveTo(L, YT((Tm * k) / 4));
      g.lineTo(w - 30, YT((Tm * k) / 4));
      g.stroke();
    }
    g.font = '10px "JetBrains Mono", monospace';
    g.fillStyle = HOT;
    g.fillText('K', 4, 12);
    g.fillText(fmt(Tm / 1.1), 2, YT(Tm / 1.1) + 3);
    g.fillStyle = COLD;
    g.fillText('bar', w - 26, 12);
    g.fillText(fmt(Pm / 1.1 / 1e5, 1), w - 28, YP(Pm / 1.1) + 3);
    for (const [col, Y, key] of [[HOT, YT, 'Tt'], [COLD, YP, 'Pt']]) {
      g.strokeStyle = col;
      g.lineWidth = 1.5;
      g.beginPath();
      sts.forEach((s, i) => (i ? g.lineTo(X(s.z), Y(s[key])) : g.moveTo(X(s.z), Y(s[key]))));
      g.stroke();
    }
    g.fillStyle = AXIS;
    g.font = '9px Inter, sans-serif';
    g.fillText('front', L, h - 4);
    g.fillText('back', w - 52, h - 4);
    const s = J.stations[stationI];
    if (sts.includes(s)) {
      g.fillStyle = INK;
      for (const [Y, key] of [[YT, 'Tt'], [YP, 'Pt']]) {
        g.beginPath();
        g.arc(X(s.z), Y(s[key]), 3.6, 0, Math.PI * 2);
        g.fill();
      }
      g.strokeStyle = 'rgba(244,244,245,0.25)';
      g.beginPath();
      g.moveTo(X(s.z), 6);
      g.lineTo(X(s.z), h - 16);
      g.stroke();
    }
  };
  const readouts = () => {
    const s = J.stations[stationI];
    const o = J.out;
    $('p-cyl').textContent = `Station ${stationI + 1} of ${J.stations.length}`;
    $('p-stroke').textContent = s.label.toUpperCase();
    $('p-stroke').classList.toggle('hot', s.Tt > 1100);
    $('p-ang').textContent = `M ${fmt(s.M, 2)}`;
    $('p-T').textContent = `${fmt(s.Tt)} K`;
    $('p-p').textContent = `${fmt(s.Pt / 1e5, 2)} bar`;
    $('p-V').textContent = `${fmt(s.V)} m/s`;
    $('p-F').textContent = `${fmt(o.thrust_kN, 1)} kN`;
    $('p-sfc').textContent = `${fmt(o.TSFC_kg_per_kN_hr, 1)}`;
    const ex = o.extra ?? {};
    const xs = J.family === 'turbofan' ? ['Bypass', fmt(ex.bypass_ratio ?? J.input.bypass_ratio, 1)] : J.family === 'turboprop' ? ['Shaft', `${fmt(o.shaft_power_kW)} kW`] : ['Exit V', `${fmt(o.exit_velocity_m_s)} m/s`];
    $('p-xl').textContent = xs[0];
    $('p-x').textContent = xs[1];
    drawChart();
    const p = PLAYS[playI];
    const names = {lp: 'LP', ip: 'IP', hp: 'HP', pt: 'Power turbine', fan: 'Fan', prop: 'Propeller'};
    $('spools').innerHTML = Object.entries(J.spools).map(([k, v]) => `<span><i>${names[k] ?? k}</i> ${fmt(v.rpm)} rpm</span>`).join('') || '<span>No moving parts: the shocks do the compressing</span>';
    $('s-lbl').textContent = `Speed: 1/${fmt(Math.round(1 / p))} of real time`;
    $('s-lbl2').textContent = `1/${fmt(Math.round(1 / p))} speed`;
  };

  // ------------------------------------------------------------ controls
  $('s-play').oninput = (e) => {
    takeOver();
    playI = Number(e.target.value);
  };
  $('b-play').onclick = () => {
    takeOver();
    paused = !paused;
    $('b-play').textContent = paused ? 'Play' : 'Pause';
    $('b-play').setAttribute('aria-label', paused ? 'Play' : 'Pause');
  };
  tourChip.onclick = () => takeOver();
  const takeOver = () => {
    lastInput = T;
    if (tourOn) {
      tourOn = false;
      tourChip.classList.remove('on');
      explodeTo = Number($('explode').value) / 100;
    }
  };
  const startTour = () => {
    tourOn = true;
    tourT0 = T;
    paused = false;
    $('b-play').textContent = 'Pause';
    tourChip.classList.add('on');
  };

  const ptrs = new Map();
  let pinch0 = 0;
  let down = null;
  canvas.addEventListener('pointerdown', (e) => {
    takeOver();
    canvas.setPointerCapture(e.pointerId);
    ptrs.set(e.pointerId, [e.clientX, e.clientY]);
    down = ptrs.size === 1 ? [e.clientX, e.clientY] : null;
    canvas.classList.add('drag');
    if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      pinch0 = Math.hypot(a[0] - b[0], a[1] - b[1]);
    }
  });
  let hoverAt = null;
  canvas.addEventListener('pointermove', (e) => {
    if (!ptrs.has(e.pointerId)) {
      if (e.pointerType === 'mouse') hoverAt = [e.clientX, e.clientY];
      return;
    }
    const prev = ptrs.get(e.pointerId);
    ptrs.set(e.pointerId, [e.clientX, e.clientY]);
    if (ptrs.size === 1) {
      camTo.az -= (e.clientX - prev[0]) * 0.006;
      camTo.el = clamp(camTo.el + (e.clientY - prev[1]) * 0.005, -0.3, 1.4);
      if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) {
        down = null;
        view = '';
        refreshSegs();
      }
    } else if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (pinch0 > 0) camTo.k = clamp(camTo.k * (pinch0 / d), 0.08, 1.8);
      pinch0 = d;
    }
  });
  const up = (e) => {
    if (down && ptrs.size === 1 && J) select(st.pick(e.clientX, e.clientY));
    down = null;
    ptrs.delete(e.pointerId);
    if (!ptrs.size) canvas.classList.remove('drag');
    pinch0 = 0;
  };
  canvas.addEventListener('pointerup', up);
  canvas.addEventListener('pointercancel', (e) => {
    down = null;
    up(e);
  });
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    takeOver();
    camTo.k = clamp(camTo.k * Math.exp(e.deltaY * 0.001), 0.08, 1.8);
  }, {passive: false});
  addEventListener('keydown', (e) => {
    if (e.target.closest?.('input,select,textarea')) return;
    if (e.key === ' ') {
      e.preventDefault();
      $('b-play').click();
    } else if (e.key === 'ArrowLeft' && J) setStation(Math.max(0, stationI - 1), true);
    else if (e.key === 'ArrowRight' && J) setStation(Math.min(J.stations.length - 1, stationI + 1), true);
    else if (e.key === 'Escape') select(null);
  });
  addEventListener('hashchange', () => {
    const g = parseHash();
    if (g && g !== current) load(g);
  });

  const freeArea = () => {
    const Wd = innerWidth;
    const H = innerHeight;
    const narrow = Wd <= 700;
    const r = (e) => e.getBoundingClientRect();
    const vis = (e) => getComputedStyle(e).display !== 'none' && !e.hidden;
    const l = !narrow && vis(side) && !side.classList.contains('open') ? r(side).right : 0;
    const rt = !narrow ? Wd - r(right).left : 0;
    const tp = r(top).bottom;
    const b = narrow ? H - r(right).top : H - r(bottom).top;
    const fw = Math.max(120, Wd - l - rt);
    const fh = Math.max(120, H - tp - b);
    return {sx: (l - rt) / 2, sy: (tp - b) / 2, fill: Math.max(Wd / fw, H / fh), l, rt, t: tp, b};
  };

  // ------------------------------------------------------------ the loop
  let last = performance.now();
  let slow = 0;
  let frames = 0;
  const loop = (now) => {
    if (st.hold) {
      last = now;
      requestAnimationFrame(loop);
      return;
    }
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    T += dt;
    if (!tourOn && T - lastInput > IDLE) startTour();
    if (J && msg.hidden) {
      if (!paused) t += dt * PLAYS[playI];
      st.eng.setPlayRate(paused ? 0 : PLAYS[playI]);
      if (tourOn) {
        const u = T - tourT0;
        camTo.az = VIEWS['3/4'].az + 0.55 * Math.sin(u * 0.07);
        camTo.el = 0.28 + 0.12 * Math.sin(u * 0.19);
        camTo.k = K0;
        camTo.target = null;
        // every 40 s the modules pull apart for a while; the followed station steps through the engine
        const ph = u % 40;
        explodeTo = ph > 22 && ph < 34 ? 0.6 : 0;
        press('b-explode', explodeTo > 0.01);
        const si = Math.floor(u / 3) % J.stations.length;
        if (si !== stationI) setStation(si);
      }
      const ease = 1 - Math.exp(-dt * 5);
      for (const k of ['az', 'el', 'k']) cam[k] += (camTo[k] - cam[k]) * ease;
      if (cam.target) {
        const goal = camTo.target ?? st.fit.center;
        cam.target.lerp(goal, ease);
        if (!camTo.target && cam.target.distanceTo(goal) < 1e-4) cam.target = null;
      }
      const ex = explode + (explodeTo - explode) * (1 - Math.exp(-dt * 4));
      if (Math.abs(ex - explode) > 1e-4) {
        explode = ex;
        st.eng.setExplode(explode);
        st.markShadows();
        if (tourOn) $('explode').value = Math.round(explode * 100);
      }
      const fa = freeArea();
      st.frame(t, {...cam, ...fa});
      readouts();
      drawOverlay(fa);
      if (hoverAt) {
        canvas.style.cursor = st.pick(...hoverAt) ? 'pointer' : '';
        hoverAt = null;
      }
      frames++;
      if (dt > 0.034) slow += dt;
      if (frames > 120) {
        if (slow > 2 && tier < TIERS.length - 1) {
          tier++;
          applyTier();
        }
        frames = 0;
        slow = 0;
      }
    }
    requestAnimationFrame(loop);
  };

  // ------------------------------------------------------------ photo mode and the bill of materials
  const sharedStyle = document.createElement('style');
  sharedStyle.textContent = SHARED_CSS;
  document.head.appendChild(sharedStyle);
  const photo = initPhoto({st, cam, camTo, app, takeOver: () => takeOver(), name: () => (current?.id ?? 'engine'),
    presets: () => [{name: 'Hero 3/4', az: 0.95, el: 0.3, k: 0.62}, {name: 'Front inlet', az: 0.12, el: 0.08, k: 0.55}, {name: 'Side', az: Math.PI / 2, el: 0.04, k: 0.62},
      {name: 'Exhaust', az: Math.PI - 0.6, el: 0.2, k: 0.62}, {name: 'Top down', az: 0.6, el: 1.3, k: 0.7},
      {name: 'Hot section', az: 0.9, el: 0.25, k: 0.28, target: () => {
        const c = J.combustor ?? {z0: 0, z1: 0, r1: J.R};
        return new Vector3(0, (c.r1 ?? J.R) * 0.4, (c.z0 + c.z1) / 2);
      }}],
    renderFrame: (jx, jy) => st.frame(t, {...cam, sx: jx, sy: jy, fill: 1}, {}),
    restore: () => fit()});
  $('b-photo').onclick = () => (photo.active ? photo.leave() : photo.enter());
  const refreshBOM = () => {
    if (!st.eng || !J) return;
    const rows = buildBOM(st.eng.root, (id, meta) => partInfo(id, meta, J), (l) => LAYERS.find((x) => x.id === l)?.name ?? '');
    renderBOM($('pane-bom'), rows, (hit) => {
      takeOver();
      select(hit);
    }, esc);
  };
  current = parseHash() || GALLERY[0];
  renderEngines();
  load(current).then(startTour);
  requestAnimationFrame(loop);
  window.LIVE = {rebuild: () => rebuild(), setTier: (n) => {
    tier = n;
    applyTier();
  }, photo: () => photo, refreshBOM: () => refreshBOM(), setPlay: (i) => {
    playI = i;
    $('s-play').value = i;
  }, setOverride: (k, v) => {
    overrides[k] = v;
    return load(current, true);
  }, setFlow: (m) => {
    flowMode = m;
    st.eng.setFlowColor(m);
    renderFlow();
  }, setWear: (id) => {
    const s = WEAR_STATES.find((x) => x.id === id);
    wearId = s.id;
    st.setWear(s.wear);
    renderWears();
  }, setEnv: (n) => (st.setEnvironment(n), renderEnvs()), st, cam, camTo, get J() {
    return J;
  }, setT: (v) => (t = v), takeOver, select, setLayer, setStation, setCut: (c) => setCutMode(c), setExplode: (v) => {
    explodeTo = explode = v;
    st.eng.setExplode(v);
  }};
}
