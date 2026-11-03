// The page you drive. One crank angle poses the engine and feeds every readout: the tracked cylinder's stroke,
// pressure, temperature, volume and burn come from the same makeEngine() that moves the parts. Drag to orbit, wheel or
// pinch to zoom, click a part to inspect it, switch layers off, pull the engine apart with the explode slider, pick a
// cylinder from the firing order. Left alone for 25 s it tours itself: a slow orbit that follows the firing order and
// opens the engine up now and then.
import {warmComposer} from 'teardown-kit/warm.js';
import {LAYERS} from './engine.js';
import {GALLERY, ROD_PUBLISHED} from './gallery.js';
import {partInfo} from './info.js';
import {makeEngine, mod, strokeOf} from './kin.js';
import {Vector3 as THREE_V3} from 'three';
import {createStage} from './stage.js';
import {initPhoto} from '../shared/photo.js';
import {SHARED_CSS, buildBOM, renderBOM} from '../shared/bom.js';
import {STATES as WEAR_STATES} from '../shared/wear.js';

const IDLE = 25;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const PLAYS = [1 / 400, 1 / 200, 1 / 100, 1 / 50, 1 / 20, 1 / 10];
const VIEWS = {
  '3/4': {az: 0.62, el: 0.32},
  Front: {az: 0, el: 0.06},
  Side: {az: Math.PI / 2, el: 0.08},
  Top: {az: 0.25, el: 1.25},
};
const CUTS = ['Glass', 'Section', 'Solid'];
const api = () => new URLSearchParams(location.search).get('api') || '';

const b64 = {
  enc: (o) => btoa(unescape(encodeURIComponent(JSON.stringify(o)))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''),
  dec: (s) => JSON.parse(decodeURIComponent(escape(atob(s.replace(/-/g, '+').replace(/_/g, '/'))))),
};
const fmt = (v, d = 0) => (v == null || !isFinite(v) ? '-' : v.toLocaleString(undefined, {minimumFractionDigits: d, maximumFractionDigits: d}));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
};

/** a canvas sized from its CSS box, never from its own buffer size (that feedback grew buffers without bound before) */
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
  canvas.setAttribute('aria-label', 'Interactive 3D engine. Drag to orbit, scroll to zoom, click a part to inspect it.');
  canvas.setAttribute('role', 'img');
  app.appendChild(canvas);
  const st = createStage({canvas});

  // ------------------------------------------------------------ overlay
  const ui = el('div', 'ui');
  app.appendChild(ui);
  const ov = el('div', 'overlay', '<svg id="ov-svg" aria-hidden="true"></svg><div id="ov-labels"></div>');
  ui.appendChild(ov);
  const top = el('header', 'bar');
  top.innerHTML = `
    <a class="brand" href="/" aria-label="DAS LABS home">
      <img class="brand-mark" src="/lab/assets/das_labs_logo_dark.png?v=20260529-2" alt="DAS LABS" onerror="this.outerHTML='<b class=&quot;brand-txt&quot;>DAS LABS</b>'">
      <span class="brand-dot"></span>
      <img class="brand-product" src="/lab/assets/pistonlab_wordmark.png" alt="PistonLab" onerror="this.outerHTML='<span class=&quot;brand-txt2&quot;>PistonLab</span>'">
      <span class="pill">3D</span>
    </a>
    <div class="pl-title"><b id="t-name">Engine</b><span id="t-sub"></span></div>
    <div class="tools">
      <div class="seg" role="group" aria-label="Camera view" id="g-view"></div>
      <div class="seg" role="group" aria-label="Cutaway" id="g-cut"></div>
      <div class="seg" role="group" aria-label="Overlays">
        <button id="b-explode" aria-pressed="false" title="Pull the engine apart">Explode</button>
        <button id="b-photo" title="Photo mode: presets, focal length, depth of field, high-resolution stills">Photo</button>
        <button id="b-labels" aria-pressed="false" title="Name the main parts">Labels</button>
        <button id="b-dims" aria-pressed="false" title="Bore, stroke, throw and rod on the tracked cylinder">Dims</button>
      </div>
      <a class="ghost" href="/piston/">Console</a>
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
      <p class="cycnote">Move an input and the engine is solved again: the charge's pressure and temperature, the flame front's growth, the header glow and the crank speed all follow.</p>
      <div id="cyc"></div>
      <div class="cycstat mono" id="cyc-stat"></div>
      <button id="cyc-reset">Back to the published point</button>
      <div class="lbl envlbl">Analysis</div>
      <label class="layer"><input type="checkbox" id="an-haze" checked><span>Heat haze</span></label>
    </div>
    <div id="pane-lay" hidden>
      <div class="lbl">Explode</div>
      <input type="range" id="explode" min="0" max="100" value="0" aria-label="Explode the engine">
      <div class="quick"><button id="l-all">Show all</button><button id="l-core">Moving parts</button><button id="l-vt">Valvetrain</button></div>
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
  panel.setAttribute('aria-label', 'Tracked cylinder');
  panel.innerHTML = `
    <div class="lbl" id="p-cyl">Cylinder 1</div>
    <div class="stroke"><b id="p-stroke">POWER</b><span class="mono" id="p-ang"></span></div>
    <div class="grid mono">
      <div><span class="lbl">Pressure</span><span class="v" id="p-p"></span></div>
      <div><span class="lbl">Gas temp</span><span class="v" id="p-T"></span></div>
      <div><span class="lbl">Volume</span><span class="v" id="p-V"></span></div>
      <div><span class="lbl">Burned</span><span class="v" id="p-xb"></span></div>
      <div><span class="lbl">In. lift</span><span class="v" id="p-li"></span></div>
      <div><span class="lbl">Ex. lift</span><span class="v" id="p-le"></span></div>
    </div>
    <canvas class="chart" id="c-pv" aria-label="Pressure against volume for the tracked cylinder"></canvas>
    <canvas class="chart short" id="c-pt" aria-label="Pressure through the 720 degree cycle"></canvas>`;
  const pcard = el('section', 'panel part');
  pcard.hidden = true;
  pcard.setAttribute('aria-live', 'polite');
  right.append(panel, pcard);
  ui.appendChild(right);

  const bottom = el('div', 'bottom panel');
  bottom.innerHTML = `
    <div><div class="lbl" id="o-lbl">Firing order</div><div class="order" id="order" role="group" aria-label="Track a cylinder"></div></div>
    <div class="play">
      <button id="b-back" aria-label="Back 15 degrees">&minus;15&deg;</button>
      <button id="b-play" aria-label="Pause">Pause</button>
      <button id="b-fwd" aria-label="Forward 15 degrees">+15&deg;</button>
    </div>
    <label class="speed"><span class="lbl"><span class="long" id="s-lbl">Speed</span><span class="short" id="s-lbl2">Speed</span></span><input type="range" id="s-play" min="0" max="${PLAYS.length - 1}" step="1"></label>`;
  ui.appendChild(bottom);
  const mob = el('div', 'mobtabs');
  mob.innerHTML = '<button id="m-eng" aria-expanded="false">Engines</button><button id="m-lay" aria-expanded="false">Layers</button>';
  ui.appendChild(mob);
  const hint = el('div', 'hint', 'Click a part to inspect it &middot; drag to orbit &middot; scroll to zoom');
  ui.appendChild(hint);
  const tourChip = el('button', 'tourchip', '<i></i>Auto tour');
  tourChip.setAttribute('aria-label', 'Auto tour running. Click to take control.');
  ui.appendChild(tourChip);
  const msg = el('div', 'msg panel');
  msg.hidden = true;
  ui.appendChild(msg);
  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------ quality tiers
  const TIERS = [
    {samples: 4, ao: true, shadow: 2048, pr: 2, glow: true, every: 3},
    {samples: 2, ao: false, shadow: 1024, pr: 1.5, glow: true, every: 8},
    {samples: 0, ao: false, shadow: 1024, pr: 1, glow: false, every: 0},
  ];
  const coarse = matchMedia('(pointer: coarse)').matches || Math.min(innerWidth, innerHeight) < 700;
  let tier = coarse ? 1 : 0;
  const fit = () => st.resize(innerWidth, innerHeight, Math.min(devicePixelRatio || 1, TIERS[tier].pr));
  const applyTier = () => {
    const {pr, every, ...q} = TIERS[tier];
    st.setQuality(q);
    st.setShadowEvery(every);
    st.setHaze?.(tier < 2);
    fit();
  };
  applyTier();
  addEventListener('resize', fit);

  // ------------------------------------------------------------ state
  let E = null;
  let th = 0;
  let paused = false;
  let playI = 2;
  let track = 1;
  let cut = 'Glass';
  let view = '3/4';
  let explode = 0;
  let explodeTo = 0;
  let selected = null;
  const shownLayers = Object.fromEntries(LAYERS.map((l) => [l.id, true]));
  const K0 = 0.72;
  const cam = {...VIEWS['3/4'], k: K0, target: null};
  const camTo = {...cam};
  let current = null;
  let lastInput = -1e9;
  let tourOn = true;
  let tourT0 = 0;
  let T = 0;

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
  const cylOf = (n) => E.cyl.find((c) => c.n === n) || E.cyl[0];
  const setCutMode = (c) => {
    cut = c;
    if (E) st.setCut(c.toLowerCase(), cylOf(track).z);
  };
  segs($('g-cut'), CUTS, () => cut, setCutMode);

  // ------------------------------------------------------------ side panel: engines and layers
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
  // ------------------------------------------------------------ the cycle panel: speed and load re-solve the engine
  let overrides = {};
  const renderCycle = () => {
    const b = current?.body ?? {};
    const box = $('cyc');
    box.innerHTML = '';
    const pIn = b.intake_pressure_Pa ?? 100000;
    const rows = [['rpm', 'Engine speed', 1000, Math.round((b.rpm ?? 6000) * 1.25 / 100) * 100, 100, 'rpm', b.rpm ?? 6000],
      ['intake_pressure_Pa', b.aspiration === 'turbocharged' ? 'Intake pressure (boost)' : 'Intake pressure (throttle)', 30000, Math.max(110000, pIn * 1.2), 1000, 'bar', pIn]];
    for (const [k, label, lo, hi, step, unit, def] of rows) {
      const v = overrides[k] ?? def;
      const show = (x) => (unit === 'bar' ? `${fmt(x / 1e5, 2)} bar` : `${fmt(x)} rpm`);
      const row = el('label', 'cycrow', `<span class="lbl">${label}</span><span class="mono" id="cv-${k}">${show(v)}</span><input type="range" min="${lo}" max="${hi}" step="${step}" value="${v}" aria-label="${label}">`);
      const inp = row.querySelector('input');
      inp.oninput = () => {
        takeOver();
        $(`cv-${k}`).textContent = show(Number(inp.value));
        overrides[k] = Number(inp.value);
        clearTimeout(resolveTimer);
        resolveTimer = setTimeout(() => load(current, true), 280);
      };
      box.appendChild(row);
    }
  };
  let resolveTimer = 0;
  const cycStat = () => {
    if (!E) return;
    const o = E.out;
    $('cyc-stat').innerHTML = `Power ${fmt(o.brake_power_W / 1e3)} kW &middot; torque ${fmt(o.brake_torque_Nm)} N&middot;m<br>Peak pressure ${fmt((E.out.peak_pressure_Pa ?? 0) / 1e5)} bar &middot; header wall ${fmt(E.wallTemp)} K`;
  };
  $('cyc-reset').onclick = () => {
    takeOver();
    overrides = {};
    load(current, true).then(renderCycle);
  };
  $('an-haze').onchange = (e) => st.setHaze(e.target.checked);
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
      const id = `ly-${L.id}`;
      const row = el('label', 'layer', `<input type="checkbox" id="${id}" ${shownLayers[L.id] ? 'checked' : ''}><span>${L.name}</span>`);
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
    if (!on && selected && partInfo(selected.id, selected.meta, E).layer === id) select(null);
  };
  const preset = (ids) => {
    takeOver();
    for (const L of LAYERS) setLayer(L.id, !ids || ids.includes(L.id));
  };
  $('l-all').onclick = () => preset(null);
  $('l-core').onclick = () => preset(['rotating', 'valvetrain', 'timing', 'charge']);
  $('l-vt').onclick = () => preset(['valvetrain', 'timing', 'rotating']);
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

  let custom = null;
  const parseHash = () => {
    const h = new URLSearchParams(location.hash.slice(1));
    if (h.get('e')) {
      try {
        custom = {id: 'custom', name: 'Your engine', sub: 'from the PistonLab console', body: b64.dec(h.get('e')), hardware: {}};
        return custom;
      } catch {
        return null;
      }
    }
    const g = GALLERY.find((x) => x.id === h.get('g'));
    return g ? {...g, sub: g.car} : null;
  };
  const renderEngines = () => {
    const pane = $('pane-eng');
    pane.innerHTML = '';
    const list = (custom ? [custom] : []).concat(GALLERY.map((g) => ({...g, sub: g.car})));
    for (const g of list) {
      const b = el('button', 'eng', `<b>${esc(g.name)}</b><small>${esc(g.sub)}</small>`);
      b.setAttribute('aria-current', String(current?.id === g.id));
      b.onclick = () => {
        takeOver();
        side.classList.remove('open');
        load(g);
      };
      pane.appendChild(b);
    }
    const facts = el('dl', 'facts');
    facts.id = 'facts';
    pane.appendChild(facts);
    if (E) fillFacts();
  };
  const fillFacts = () => {
    const o = E.out;
    const rodNote = current.id === 'custom' || ROD_PUBLISHED.has(current.id) ? '' : ' (assumed)';
    const vtName = {dohc: 'DOHC', sohc: 'SOHC', ohv: 'Pushrod'}[E.hw.valvetrain];
    const rows = [
      ['Bore x stroke', `${fmt(E.bore * 1e3, 1)} x ${fmt(E.stroke * 1e3, 1)} mm`],
      ['Capacity', `${fmt(o.total_displacement_m3 * 1e3, 3)} L`],
      ['Compression', `${fmt(E.cr, 1)} : 1`],
      ['Rod ratio', `${fmt(E.rodRatio, 2)}${rodNote}`],
      ['Valvetrain', `${vtName}, ${E.vg.intake_valves_per_cylinder + E.vg.exhaust_valves_per_cylinder} valves`],
      ['Oil', E.hw.oil === 'dry' ? 'Dry sump' : 'Wet sump'],
      ['Speed', `${fmt(E.rpm)} rpm`],
      ['Brake power', `${fmt(o.brake_power_W / 1e3)} kW`],
      ['Brake torque', `${fmt(o.brake_torque_Nm)} N·m`],
      ['Brake efficiency', `${fmt(o.brake_thermal_efficiency * 100, 1)} %`],
    ];
    const f = $('facts');
    f.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd class="mono">${v}</dd>`).join('');
    const notes = [o.layout?.balance_verdict, E.hw.note,
      current.id === 'custom' ? 'Your engine as the console last solved it.'
        : 'Bore, stroke, compression and layout are published figures. Power and pressures are PistonLab’s model at these inputs, not the maker’s data. Cylinders are numbered front to back on bank 1, then bank 2, which can differ from the maker’s numbering.'];
    f.insertAdjacentHTML('beforeend', notes.filter(Boolean).map((n) => `<div class="note">${esc(n)}</div>`).join(''));
  };

  // ------------------------------------------------------------ part inspector
  // the camera flies to a picked part and back out when it is closed
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
    camTo.k = clamp((Math.max(f.radius, 0.6 * E.bore) / st.fit.radius) * 2.2, 0.18, K0);
    const info = partInfo(hit.id, hit.meta, E);
    const lname = LAYERS.find((l) => l.id === info.layer)?.name ?? '';
    pcard.innerHTML = `<div class="phead"><div><div class="lbl">${esc(lname)}</div><b>${esc(info.name)}</b></div><button class="x" id="p-close" aria-label="Close part details">&times;</button></div><div class="pbody">${info.html}<div class="now" id="p-now-wrap" hidden><div class="lbl">Now, at this crank angle</div><dl id="p-now"></dl></div></div>`;
    pcard.hidden = false;
    right.classList.add('has-part');
    $('p-close').onclick = () => select(null);
  };

  // ------------------------------------------------------------ overlays: explode button, labels, dimensions
  let labelsOn = false;
  let dimsOn = false;
  const press = (id, on) => $(id).setAttribute('aria-pressed', String(on));
  $('b-explode').onclick = () => {
    takeOver();
    explodeTo = explodeTo > 0.01 ? 0 : 0.65;
    $('explode').value = Math.round(explodeTo * 100);
    press('b-explode', explodeTo > 0.01);
  };
  $('b-labels').onclick = () => {
    takeOver();
    labelsOn = !labelsOn;
    press('b-labels', labelsOn);
  };
  $('b-dims').onclick = () => {
    takeOver();
    dimsOn = !dimsOn;
    press('b-dims', dimsOn);
  };
  // the parts worth naming; for the per-cylinder ones the tracked cylinder's part is named
  const LABEL_IDS = ['crank', 'flywheel', 'timing-cover', 'bellhousing', 'starter', 'catalyst', 'ac-compressor', 'piston', 'rod', 'cam-in', 'cam-ex', 'cam-sohc', 'cam-block', 'valve-in', 'rocker', 'sprockets', 'tensioner',
    'oil-pump', 'filter', 'sump-wet', 'sump-dry', 'oil-tank', 'plenum', 'throttle', 'collector', 'turbo', 'water-pump', 'alternator', 'plug', 'diesel-injector', 'balance'];
  let anchorPool = {};
  const collectAnchors = () => {
    anchorPool = {};
    st.eng.root.traverse((o) => {
      const pk = o.userData.pick;
      if (!pk || !LABEL_IDS.includes(pk.id)) return;
      (anchorPool[pk.id] ||= []).push({obj: o, ...pk});
    });
  };
  const shownInScene = (o) => {
    for (let x = o; x; x = x.parent) if (!x.visible) return false;
    return true;
  };
  const proj = new THREE_V3();
  const toScreen = (v) => {
    proj.copy(v).project(st.camera);
    if (proj.z > 1 || Math.abs(proj.x) > 1.05 || Math.abs(proj.y) > 1.05) return null;
    return [(proj.x * 0.5 + 0.5) * innerWidth, (-proj.y * 0.5 + 0.5) * innerHeight];
  };
  const drawOverlay = (fa) => {
    let lines = '';
    let html = '';
    if (labelsOn && E && innerWidth > 700) {
      const Wd = innerWidth;
      const lx = fa.l + 14;
      const rx = Wd - fa.rt - 14;
      const cx = (fa.l + Wd - fa.rt) / 2;
      const items = [];
      for (const id of LABEL_IDS) {
        const pool = anchorPool[id];
        if (!pool) continue;
        const a = pool.find((x) => x.meta.cyl === track) || pool[0];
        if (!shownInScene(a.obj)) continue;
        const sp = toScreen(a.obj.getWorldPosition(new THREE_V3()));
        if (!sp) continue;
        items.push({a, sp, name: partInfo(a.id, a.meta, E).name, left: sp[0] < cx});
      }
      for (const side of [true, false]) {
        const col = items.filter((x) => x.left === side).sort((u, v) => u.sp[1] - v.sp[1]);
        const top = fa.t + 16;
        const bot = innerHeight - fa.b - 16;
        let y = top;
        for (const it of col) {
          it.y = Math.max(it.sp[1], y);
          y = it.y + 24;
        }
        // a column pushed off the bottom slides back up
        let over = col.length ? col[col.length - 1].y - bot : 0;
        for (let i = col.length - 1; i >= 0 && over > 0; i--) {
          col[i].y -= over;
          over = i > 0 ? Math.max(0, col[i - 1].y + 24 - col[i].y) : 0;
        }
        for (const it of col) {
          const x = side ? lx : rx;
          const ex = side ? x + 150 : x - 150;
          const elbow = side ? ex + 24 : ex - 24;
          const sel = selected && selected.obj === it.a.obj ? 'sel' : '';
          lines += `<polyline points="${ex},${it.y} ${elbow},${it.y} ${it.sp[0]},${it.sp[1]}" class="${sel}"/><circle cx="${it.sp[0]}" cy="${it.sp[1]}" r="2.6" class="${sel}"/>`;
          html += `<button class="tag ${side ? 'l' : 'r'} ${sel}" style="top:${it.y - 10}px;${side ? `left:${x}px` : `right:${Wd - x}px`}" data-id="${it.a.id}" data-cyl="${it.a.meta.cyl ?? ''}">${esc(it.name)}</button>`;
        }
      }
    }
    if (dimsOn && E) {
      const c = cylOf(track);
      const at = (d, w = 0) => new THREE_V3(d * c.b[0] + w * c.p[0], d * c.b[1] + w * c.p[1], c.z);
      const B = E.bore;
      const dim = (a, b, text) => {
        const A = toScreen(a);
        const Bp = toScreen(b);
        if (!A || !Bp) return;
        const dx = Bp[0] - A[0];
        const dy = Bp[1] - A[1];
        const L = Math.hypot(dx, dy) || 1;
        const nx = (-dy / L) * 5;
        const ny = (dx / L) * 5;
        lines += `<line x1="${A[0]}" y1="${A[1]}" x2="${Bp[0]}" y2="${Bp[1]}" class="dim"/>`;
        lines += `<line x1="${A[0] - nx}" y1="${A[1] - ny}" x2="${A[0] + nx}" y2="${A[1] + ny}" class="dim"/><line x1="${Bp[0] - nx}" y1="${Bp[1] - ny}" x2="${Bp[0] + nx}" y2="${Bp[1] + ny}" class="dim"/>`;
        html += `<span class="dimtxt" style="left:${(A[0] + Bp[0]) / 2 + nx * 3}px;top:${(A[1] + Bp[1]) / 2 + ny * 3}px">${text}</span>`;
      };
      const {s: sNow, P} = E.pistonS(c, th);
      dim(at(E.deck + 0.08 * B, -B / 2), at(E.deck + 0.08 * B, B / 2), `bore ${fmt(B * 1e3, 1)}`);
      dim(at(E.sTDC + E.crownH, 0.9 * B), at(E.sBDC + E.crownH, 0.9 * B), `stroke ${fmt(E.stroke * 1e3, 1)}`);
      dim(new THREE_V3(0, 0, c.z), new THREE_V3(P[0], P[1], c.z), `throw ${fmt(E.r * 1e3, 1)}`);
      dim(new THREE_V3(P[0], P[1], c.z), at(sNow), `rod ${fmt(E.L * 1e3, 1)}`);
    }
    $('ov-svg').innerHTML = lines;
    $('ov-labels').innerHTML = html;
  };
  $('ov-labels').addEventListener('click', (e) => {
    const t = e.target.closest('.tag');
    if (!t) return;
    takeOver();
    const pool = anchorPool[t.dataset.id] || [];
    const a = pool.find((x) => String(x.meta.cyl ?? '') === t.dataset.cyl) || pool[0];
    if (a) select(a);
  });

  // live kinematics for the selected part, from the same slider-crank that moves it
  const nowRows = () => {
    if (!selected || !E) return null;
    const c = cylOf(selected.meta.cyl ?? track);
    const w = (E.rpm * Math.PI) / 30;
    const h = 0.25;
    const R2D = 180 / Math.PI;
    const sOf = (cc, t) => E.pistonS(cc, t).s;
    const s0 = sOf(c, th);
    // derivatives of the exact slider-crank by central differences, per radian of crank
    const d1 = ((sOf(c, th + h) - sOf(c, th - h)) / (2 * h)) * R2D;
    const d2 = ((sOf(c, th + h) - 2 * s0 + sOf(c, th - h)) / (h * h)) * R2D * R2D;
    const ps = E.psi(c, th);
    const gas = E.gas(ps);
    // net gas force on the crown, taking 1 bar under the piston
    const F = (gas.p - 1e5) * E.area;
    // virtual work: torque = force times the piston's travel per radian of crank
    const torqueOf = (cc) => {
      const dd = ((sOf(cc, th + h) - sOf(cc, th - h)) / (2 * h)) * R2D;
      return -(E.gas(E.psi(cc, th)).p - 1e5) * E.area * dd;
    };
    const {P} = E.pistonS(c, th);
    const Wp = [s0 * c.b[0], s0 * c.b[1]];
    const rodAng = Math.acos(Math.min(1, ((Wp[0] - P[0]) * c.b[0] + (Wp[1] - P[1]) * c.b[1]) / E.L)) * R2D;
    const lift = (kind) => (kind === 'in' ? E.liftIn(ps) * E.vg.intake_valve_diameter_ratio : E.liftEx(ps) * E.vg.exhaust_valve_diameter_ratio) * E.vg.max_lift_ratio * E.bore * 1e3;
    const crankRows = [['Crank angle', `${fmt(mod(th, 720))}° of 720`], ['Gas torque, all cylinders', `${fmt(E.cyl.reduce((a, cc) => a + torqueOf(cc), 0))} N·m`], ['Mean indicated torque', `${fmt(E.out.indicated_torque_Nm)} N·m`]];
    const pistonRows = [['Cylinder', `${c.n}, ${fmt(ps)}° of 720`], ['From TDC', `${fmt((E.sTDC - s0) * 1e3, 1)} mm`], ['Velocity', `${fmt(d1 * w, 2)} m/s`], ['Acceleration', `${fmt((d2 * w * w) / 9.81)} g`], ['Gas force', `${fmt(F / 1e3, 2)} kN`]];
    const camRow = [['Cam angle', `${fmt(mod(th / 2, 360))}° of 360`]];
    const T = {
      crank: crankRows, flywheel: crankRows, balance: crankRows,
      piston: pistonRows,
      charge: [['Pressure', `${fmt(gas.p / 1e5, 1)} bar`], ['Temperature', `${fmt(gas.T)} K`], ['Burned', `${fmt(gas.xb * 100)} %`], ['Volume', `${fmt(E.volume(c, th) * 1e6)} cm³`]],
      rod: [pistonRows[0], ['Rod angle', `${fmt(rodAng, 1)}°`], ['Gas force', `${fmt(F / 1e3, 2)} kN`], ['Torque from this cylinder', `${fmt(torqueOf(c))} N·m`]],
      'valve-in': [['Lift', `${fmt(lift('in'), 2)} mm`]],
      'valve-ex': [['Lift', `${fmt(lift('ex'), 2)} mm`]],
      'cam-in': camRow, 'cam-ex': camRow, 'cam-sohc': camRow, 'cam-block': camRow,
      rocker: [['Valve lift', `${fmt(lift('in'), 2)} mm`], ['Pushrod lift', `${fmt(lift('in') / E.hw.rocker_ratio, 2)} mm`]],
      bucket: [['Intake lift', `${fmt(lift('in'), 2)} mm`], ['Exhaust lift', `${fmt(lift('ex'), 2)} mm`]],
    };
    return T[selected.id] || null;
  };

  // ------------------------------------------------------------ solve and build
  let loadSeq = 0;
  const showMsg = (html, retry) => {
    msg.innerHTML = html + (retry ? '<br><button id="m-retry">Try again</button>' : '');
    msg.hidden = false;
    if (retry) $('m-retry').onclick = retry;
  };
  async function load(g, resolve = false) {
    const seq = ++loadSeq;
    if (!resolve) overrides = {};
    current = g;
    select(null);
    renderEngines();
    $('t-name').textContent = g.name;
    // every model is representative: engineering-plausible, not the maker's drawings
    $('t-sub').textContent = `${g.sub} · representative model`;
    document.title = `${g.name} in 3D | PistonLab`;
    const body = {...g.body, ...overrides, include_trace: true};
    if ((body.strokes_per_cycle ?? 4) !== 4) return showMsg('Two-stroke engines are not in the 3D view yet. The PistonLab console still solves them.');
    const kind = body.layout?.kind ?? ((body.cylinders ?? 4) === 1 ? 'single' : 'inline');
    if (!['single', 'inline', 'vee', 'flat'].includes(kind)) return showMsg(`${kind === 'w' ? 'W' : 'Radial'} engines are not in the 3D view yet. Inline, V, flat and single-cylinder engines are.`);
    if (!body.layout) body.layout = {kind};
    if (resolve) $('cyc-stat').textContent = 'Solving...';
    else showMsg('Solving the engine...');
    let out;
    try {
      const res = await fetch(`${api()}/piston/simulate`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      if (!res.ok) {
        const t = await res.json().catch(() => ({}));
        throw new Error(typeof t.detail === 'string' ? t.detail : `The solver answered ${res.status}.`);
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
    E = makeEngine(body, out, g.hardware || {});
    const eng = st.setEngine(E);
    for (const L of LAYERS) eng.setLayer(L.id, shownLayers[L.id]);
    eng.setExplode(explode);
    track = E.order[0];
    th = E.cyl[0].fire - 30;
    const want = 60 / E.rpm;
    playI = PLAYS.reduce((bi, p, i) => (Math.abs(Math.log(p / want)) < Math.abs(Math.log(PLAYS[bi] / want)) ? i : bi), 0);
    $('s-play').value = playI;
    buildOrder();
    setTrack(track);
    fillFacts();
    setCutMode(cut);
    precomputeCycle();
    collectAnchors();
    if (!resolve) renderCycle();
    cycStat();
    await warmComposer(st.renderer, st.composer, st.scene, st.camera).catch(() => {});
  }

  const buildOrder = () => {
    const box = $('order');
    box.innerHTML = '';
    $('o-lbl').textContent = E.order.length > 1 ? 'Firing order' : 'Cylinder';
    for (const n of E.order) {
      const b = el('button', 'chip mono', `${n}<span class="flash"></span>`);
      b.dataset.n = n;
      b.setAttribute('aria-label', `Track cylinder ${n}`);
      b.onclick = () => {
        takeOver();
        setTrack(n);
      };
      box.appendChild(b);
    }
  };
  const setTrack = (n) => {
    track = n;
    for (const b of $('order').children) b.setAttribute('aria-pressed', String(Number(b.dataset.n) === n));
    if (cut === 'Section') st.setCut('section', cylOf(n).z);
  };

  let cyc = null;
  const precomputeCycle = () => {
    const c = E.cyl[0];
    const ps = [];
    const p = [];
    const v = [];
    for (let a = 0; a <= 720; a += 2) {
      ps.push(a);
      p.push(E.gas(a).p / 1e5);
      v.push(E.volume(c, c.fire + a) * 1e6);
    }
    cyc = {ps, p, v, pMax: Math.max(...p) * 1.08, vMax: Math.max(...v) * 1.05};
  };

  const INK = '#f4f4f5';
  const GRID = 'rgba(255,255,255,0.07)';
  const AXIS = 'rgba(244,244,245,0.42)';
  const HOT = '#e8923e';
  const drawCharts = (ps, pNow, vNow) => {
    if (!cyc) return;
    {
      const c = $('c-pv');
      if (c.clientWidth) {
        const {g, w, h} = sizeCanvas(c);
        const L = 34;
        const Bm = 20;
        g.clearRect(0, 0, w, h);
        const X = (V) => L + (V / cyc.vMax) * (w - L - 8);
        const Y = (P) => h - Bm - (P / cyc.pMax) * (h - Bm - 8);
        g.strokeStyle = GRID;
        g.lineWidth = 1;
        g.font = '10px "JetBrains Mono", monospace';
        g.fillStyle = AXIS;
        const step = cyc.pMax > 120 ? 40 : cyc.pMax > 60 ? 20 : 10;
        for (let q = 0; Y(q) > 20; q += step) {
          g.beginPath();
          g.moveTo(L, Y(q));
          g.lineTo(w - 8, Y(q));
          g.stroke();
          g.fillText(String(q), 4, Y(q) + 3);
        }
        g.fillText('bar', 4, 10);
        g.fillText('volume, cm³', w - 82, h - 5);
        g.strokeStyle = HOT;
        g.globalAlpha = 0.9;
        g.lineWidth = 1.4;
        g.beginPath();
        cyc.v.forEach((V, i) => (i ? g.lineTo(X(V), Y(cyc.p[i])) : g.moveTo(X(V), Y(cyc.p[i]))));
        g.stroke();
        g.globalAlpha = 1;
        g.fillStyle = INK;
        g.beginPath();
        g.arc(X(vNow), Y(pNow), 4, 0, Math.PI * 2);
        g.fill();
      }
    }
    {
      const c = $('c-pt');
      if (c.clientWidth) {
        const {g, w, h} = sizeCanvas(c);
        g.clearRect(0, 0, w, h);
        const X = (a) => 4 + (a / 720) * (w - 8);
        const Y = (P) => h - 14 - (P / cyc.pMax) * (h - 20);
        g.fillStyle = 'rgba(255,255,255,0.03)';
        for (let k = 0; k < 4; k += 2) g.fillRect(X(k * 180), 0, X(180) - X(0), h - 12);
        g.font = '9px Inter, sans-serif';
        g.fillStyle = AXIS;
        ['POWER', 'EXHAUST', 'INTAKE', 'COMPRESSION'].forEach((s, k) => g.fillText(s, X(k * 180) + 3, h - 3));
        g.strokeStyle = HOT;
        g.lineWidth = 1.3;
        g.beginPath();
        cyc.ps.forEach((a, i) => (i ? g.lineTo(X(a), Y(cyc.p[i])) : g.moveTo(X(a), Y(cyc.p[i]))));
        g.stroke();
        g.strokeStyle = INK;
        g.lineWidth = 1;
        g.beginPath();
        g.moveTo(X(ps), 0);
        g.lineTo(X(ps), h - 12);
        g.stroke();
      }
    }
  };

  const readouts = () => {
    const c = cylOf(track);
    const ps = E.psi(c, th);
    const gas = E.gas(ps);
    const V = E.volume(c, th) * 1e6;
    const s = strokeOf(ps);
    $('p-cyl').textContent = `Cylinder ${c.n}${new Set(E.cyl.map((x) => x.bank)).size > 1 ? `, bank ${c.bank + 1}` : ''}`;
    const sb = $('p-stroke');
    sb.textContent = s;
    sb.classList.toggle('hot', s === 'POWER' && gas.T > 1200);
    $('p-ang').textContent = `${fmt(ps)}° of 720`;
    $('p-p').textContent = `${fmt(gas.p / 1e5, 1)} bar`;
    $('p-T').textContent = `${fmt(gas.T)} K`;
    $('p-V').textContent = `${fmt(V, 0)} cm³`;
    $('p-xb').textContent = `${fmt(gas.xb * 100)} %`;
    $('p-li').textContent = `${fmt(E.liftIn(ps) * E.vg.max_lift_ratio * E.vg.intake_valve_diameter_ratio * E.bore * 1e3, 1)} mm`;
    $('p-le').textContent = `${fmt(E.liftEx(ps) * E.vg.max_lift_ratio * E.vg.exhaust_valve_diameter_ratio * E.bore * 1e3, 1)} mm`;
    drawCharts(ps, gas.p / 1e5, V);
    for (const b of $('order').children) {
      const k = E.psi(cylOf(Number(b.dataset.n)), th);
      b.firstElementChild.style.opacity = k < 60 ? String(1 - k / 60) : '0';
    }
    const p = PLAYS[playI];
    $('s-lbl').textContent = `Speed: 1/${Math.round(1 / p)} of ${fmt(E.rpm)} rpm`;
    $('s-lbl2').textContent = `1/${Math.round(1 / p)} speed`;
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
  $('b-back').onclick = () => {
    takeOver();
    th -= 15;
  };
  $('b-fwd').onclick = () => {
    takeOver();
    th += 15;
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

  // orbit, zoom, pinch; a click that did not move picks a part
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
      camTo.el = clamp(camTo.el + (e.clientY - prev[1]) * 0.005, -0.2, 1.4);
      if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) {
        down = null;
        view = '';
        refreshSegs();
      }
    } else if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (pinch0 > 0) camTo.k = clamp(camTo.k * (pinch0 / d), 0.12, 1.8);
      pinch0 = d;
    }
  });
  const up = (e) => {
    if (down && ptrs.size === 1 && E) select(st.pick(e.clientX, e.clientY));
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
    camTo.k = clamp(camTo.k * Math.exp(e.deltaY * 0.001), 0.12, 1.8);
  }, {passive: false});
  addEventListener('keydown', (e) => {
    if (e.target.closest?.('input,select,textarea')) return;
    if (e.key === ' ') {
      e.preventDefault();
      $('b-play').click();
    } else if (e.key === 'ArrowLeft') $('b-back').click();
    else if (e.key === 'ArrowRight') $('b-fwd').click();
    else if (e.key === 'Escape') select(null);
  });
  addEventListener('hashchange', () => {
    const g = parseHash();
    if (g) load(g);
  });

  // the part of the screen the overlay leaves free: the engine is centred and sized in it
  const freeArea = () => {
    const Wd = innerWidth;
    const H = innerHeight;
    const narrow = Wd <= 700;
    const r = (e) => e.getBoundingClientRect();
    const vis = (e) => getComputedStyle(e).display !== 'none' && !e.hidden;
    const l = !narrow && vis(side) && !side.classList.contains('open') ? r(side).right : 0;
    const rt = !narrow ? Wd - r(right).left : 0;
    const t = r(top).bottom;
    const b = narrow ? H - r(right).top : H - r(bottom).top;
    const fw = Math.max(120, Wd - l - rt);
    const fh = Math.max(120, H - t - b);
    return {sx: (l - rt) / 2, sy: (t - b) / 2, fill: Math.max(Wd / fw, H / fh), l, rt, t, b};
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
    if (E && msg.hidden) {
      if (!paused) th += dt * E.rpm * 6 * PLAYS[playI];
      if (tourOn) {
        const u = T - tourT0;
        camTo.az += dt * 0.12;
        camTo.el = 0.28 + 0.12 * Math.sin(u * 0.21);
        camTo.k = K0;
        // every 45 s the engine opens up for a while, then closes again
        const ph = u % 45;
        explodeTo = ph > 24 && ph < 38 ? 0.55 : 0;
        press('b-explode', explodeTo > 0.01);
        const c = cylOf(track);
        const nextN = E.order[(E.order.indexOf(track) + 1) % E.order.length];
        if (E.order.length > 1 && u > 3 && mod(E.psi(cylOf(nextN), th), 720) < 6 && E.psi(c, th) > 90) setTrack(nextN);
      }
      const ease = 1 - Math.exp(-dt * 6);
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
      st.frame(th, {...cam, ...fa}, {track, cut: cut.toLowerCase()});
      readouts();
      drawOverlay(fa);
      const rows = nowRows();
      const nw = $('p-now-wrap');
      if (nw) {
        nw.hidden = !rows;
        if (rows) $('p-now').innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');
      }
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
    presets: () => [{name: 'Hero 3/4', az: 0.62, el: 0.32, k: 0.72}, {name: 'Front', az: 0.02, el: 0.08, k: 0.7}, {name: 'Side', az: Math.PI / 2, el: 0.06, k: 0.72},
      {name: 'Rear', az: Math.PI - 0.5, el: 0.25, k: 0.72}, {name: 'Top down', az: 0.25, el: 1.3, k: 0.75},
      {name: 'Cylinder', az: 0.3, el: 0.2, k: 0.3, target: () => new THREE_V3(0, E.deck * 0.9, cylOf(track).z)}],
    renderFrame: (jx, jy) => st.frame(th, {...cam, sx: jx, sy: jy, fill: 1}, {track, cut: cut.toLowerCase()}),
    restore: () => fit()});
  $('b-photo').onclick = () => (photo.active ? photo.leave() : photo.enter());
  const refreshBOM = () => {
    if (!st.eng || !E) return;
    const rows = buildBOM(st.eng.root, (id, meta) => partInfo(id, meta, E), (l) => LAYERS.find((x) => x.id === l)?.name ?? '');
    renderBOM($('pane-bom'), rows, (hit) => {
      takeOver();
      select(hit);
    }, esc);
  };
  current = parseHash() || {...GALLERY[0], sub: GALLERY[0].car};
  renderEngines();
  load(current).then(startTour);
  requestAnimationFrame(loop);
  window.LIVE = {setTier: (n) => {
    tier = n;
    applyTier();
  }, photo: () => photo, refreshBOM: () => refreshBOM(), setOverride: (k, v) => {
    overrides[k] = v;
    return load(current, true);
  }, setWear: (id) => {
    const s = WEAR_STATES.find((x) => x.id === id);
    wearId = s.id;
    st.setWear(s.wear);
    renderWears();
  }, setEnv: (n) => (st.setEnvironment(n), renderEnvs()), st, cam, camTo, get E() {
    return E;
  }, setTh: (v) => (th = v), setTrack, takeOver, select, setLayer, setExplode: (v) => {
    explodeTo = explode = v;
    st.eng.setExplode(v);
  }, link: (body) => `#e=${b64.enc(body)}`};
}
