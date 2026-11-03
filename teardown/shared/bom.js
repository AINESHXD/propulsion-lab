// The bill of materials, shared by the JetLab and PistonLab 3D viewers, built from the parts' own metadata: every
// object tagged with a pick id is counted (an instanced row counts each instance), named by the viewer's part
// cards, and given the alloy its material was made from. Nothing is typed by hand per row.
const ALLOY_NAME = {
  ti64: 'Ti-6Al-4V', inconel718: 'Inconel 718', cmsxTbc: 'Single-crystal Ni + TBC', cmsxFilm: 'Single-crystal Ni + TBC, film-cooled',
  tbcEffusion: 'Ni alloy + TBC, effusion-cooled', cmc: 'Ceramic-matrix composite', steel: 'Steel', bearing: 'Bearing steel',
  stainlessHot: 'Stainless steel', alCast: 'Cast aluminium', alMachined: 'Machined aluminium', castIron: 'Grey cast iron',
  cfrp: 'Carbon-fibre composite', honeycomb: 'Honeycomb abradable', acoustic: 'Acoustic liner', paintWhite: 'Painted metal',
  paintGrey: 'Painted metal', paintBlack: 'Painted metal', bronze: 'Bronze', brass: 'Brass', rubber: 'Elastomer',
  cordierite: 'Cordierite ceramic', glass: 'Glass', coolPanel: 'Copper alloy, regeneratively cooled',
};

/** rows: [{key, name, layer, qty, material, hit}], sorted by layer then name */
export function buildBOM(root, info, layerName) {
  const rows = new Map();
  root.traverse((o) => {
    const pk = o.userData.pick;
    if (!pk) return;
    const inf = info(pk.id, pk.meta ?? {});
    const key = inf.name;
    let qty = 0;
    let alloy = null;
    o.traverse((m) => {
      if (m !== o && m.userData.pick) return;
      if (m.isInstancedMesh) qty += m.count;
      if (!alloy) alloy = [].concat(m.material ?? [])[0]?.userData?.alloy ?? null;
    });
    const r = rows.get(key) ?? {key, name: inf.name, layer: layerName(inf.layer), qty: 0, materials: new Set(), hit: {obj: o, id: pk.id, meta: pk.meta ?? {}}};
    r.qty += Math.max(1, qty);
    if (alloy) r.materials.add(ALLOY_NAME[alloy] ?? alloy);
    rows.set(key, r);
  });
  return [...rows.values()]
    .map((r) => ({...r, material: [...r.materials].join(', ') || '-'}))
    .sort((a, b) => a.layer.localeCompare(b.layer) || a.name.localeCompare(b.name, undefined, {numeric: true}));
}

/** the BOM as an HTML table inside box; clicking a row selects the part */
export function renderBOM(box, rows, onPick, esc) {
  box.innerHTML = `<div class="bomsum mono">${rows.length} line items, ${rows.reduce((a, r) => a + r.qty, 0).toLocaleString()} parts</div>
    <table class="bom"><thead><tr><th>Part</th><th>Qty</th><th>Material</th></tr></thead><tbody>${rows
      .map((r, i) => `<tr data-i="${i}" tabindex="0"><td><b>${esc(r.name)}</b><small>${esc(r.layer)}</small></td><td class="mono">${r.qty.toLocaleString()}</td><td>${esc(r.material)}</td></tr>`)
      .join('')}</tbody></table>`;
  const pick = (e) => {
    const tr = e.target.closest('tr[data-i]');
    if (tr) onPick(rows[Number(tr.dataset.i)].hit);
  };
  box.querySelector('tbody').onclick = pick;
  box.querySelector('tbody').onkeydown = (e) => e.key === 'Enter' && pick(e);
}

export const SHARED_CSS = `
.photo .ui { visibility: hidden; }
.photo-panel { position: fixed; right: 16px; top: 16px; width: 280px; max-height: calc(100vh - 32px); overflow: auto; z-index: 30; padding: 12px; }
.photo-panel .phead { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.photo-panel .quick { flex-wrap: wrap; margin-bottom: 8px; }
.photo-panel .envrow { grid-template-columns: 70px 1fr 62px; }
.photo-panel .envrow .mono { font-size: 11px; text-align: right; white-space: nowrap; }
.photo-panel input[type=range] { accent-color: #e8923e; }
.photo-panel .primary { width: 100%; margin-top: 8px; background: #e8923e; color: #111; border-color: #e8923e; font-weight: 600; }
.bomsum { font-size: 11px; color: var(--ink-3, #8a8f98); margin: 2px 2px 8px; }
table.bom { width: 100%; border-collapse: collapse; font-size: 12px; }
table.bom th { text-align: left; font-weight: 600; font-size: 10px; letter-spacing: .06em; text-transform: uppercase; color: var(--ink-3, #8a8f98); padding: 4px; border-bottom: 1px solid rgba(255,255,255,.08); }
table.bom td { padding: 5px 4px; border-bottom: 1px solid rgba(255,255,255,.05); vertical-align: top; }
table.bom td small { display: block; color: var(--ink-3, #8a8f98); font-size: 10px; }
table.bom tr[data-i] { cursor: pointer; }
table.bom tr[data-i]:hover, table.bom tr[data-i]:focus { background: rgba(232,146,62,.08); outline: none; }
#pane-bom { max-height: calc(100vh - 220px); overflow: auto; }
`;
