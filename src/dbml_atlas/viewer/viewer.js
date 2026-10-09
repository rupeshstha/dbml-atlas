// dbml-atlas interactive viewer
(() => {

// ── Data & DOM refs ───────────────────────────────────────────────────────────

const data = JSON.parse(document.getElementById('data').textContent);
const stage = document.getElementById('stage');
const svg = stage.querySelector('svg');
const side = document.getElementById('side');
const tip = document.getElementById('tip');
const searchInput = document.getElementById('q');
const minimap = document.getElementById('minimap');
const minimapVp = minimap.querySelector('.vp');

// Index SVG elements by name/index for O(1) lookup
const tableEls = {};
svg.querySelectorAll('.tbl').forEach(g => { tableEls[g.dataset.t] = g; });

const edgeEls = [];
svg.querySelector('#edges').querySelectorAll('.edge').forEach(p => { edgeEls[+p.dataset.i] = p; });

// ── Utilities ─────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// Minimal markdown: backtick code, **bold**, newlines
function md(s) {
  return esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/\n{2,}/g, '<br><br>')
    .replace(/\n/g, ' ');
}

// ── Viewport ──────────────────────────────────────────────────────────────────

const FULL = { x: 0, y: 0, w: data.W, h: data.H };
let viewBox = { ...FULL };

// Fast path used during drag — only updates the SVG viewBox, skips minimap
function setViewBox() {
  svg.setAttribute('viewBox', `${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`);
}

// Full update used for zoom, fit, and after drag ends — also syncs minimap
function applyViewBox() {
  setViewBox();
  updateMinimap();
}

function stageAspect() {
  return stage.clientWidth / Math.max(1, stage.clientHeight);
}

function fitRect(r, pad = 30, minW = 0) {
  let w = Math.max(r.w + 2 * pad, minW);
  let h = r.h + 2 * pad;
  let x = r.x + r.w / 2 - w / 2;
  let y = r.y + r.h / 2 - h / 2;
  const aspect = stageAspect();
  if (w / h < aspect) {
    const nw = h * aspect;
    x -= (nw - w) / 2;
    w = nw;
  } else {
    const nh = w / aspect;
    y -= (nh - h) / 2;
    h = nh;
  }
  viewBox = { x, y, w, h };
  applyViewBox();
}

function fit() {
  fitRect(FULL, 0);
}

function toSvgCoords(clientX, clientY) {
  const r = stage.getBoundingClientRect();
  return {
    x: viewBox.x + (clientX - r.left) / r.width * viewBox.w,
    y: viewBox.y + (clientY - r.top) / r.height * viewBox.h,
  };
}

function zoomAt(clientX, clientY, factor) {
  const p = toSvgCoords(clientX, clientY);
  const newW = Math.min(Math.max(viewBox.w * factor, 120), FULL.w * 3);
  factor = newW / viewBox.w;
  viewBox.x = p.x - (p.x - viewBox.x) * factor;
  viewBox.y = p.y - (p.y - viewBox.y) * factor;
  viewBox.w *= factor;
  viewBox.h *= factor;
  applyViewBox();
}

// ── Pan / zoom / pinch ────────────────────────────────────────────────────────

const pointers = new Map(); // pointerId → { x, y }
let dragMoved = 0;
let pointerDownTarget = null;
let pinchDist = 0;

stage.addEventListener('pointerdown', e => {
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  dragMoved = 0;
  pointerDownTarget = e.target;
  stage.classList.add('drag');
  if (pointers.size === 2) {
    const [firstPointer, secondPointer] = [...pointers.values()];
    pinchDist = Math.hypot(firstPointer.x - secondPointer.x, firstPointer.y - secondPointer.y);
  }
});

stage.addEventListener('pointermove', e => {
  const p = pointers.get(e.pointerId);
  if (!p) return;

  if (pointers.size === 1) {
    const dx = e.clientX - p.x;
    const dy = e.clientY - p.y;
    dragMoved += Math.abs(dx) + Math.abs(dy);
    const scale = viewBox.w / stage.clientWidth;
    viewBox.x -= dx * scale;
    viewBox.y -= dy * scale;
    setViewBox(); // fast path — skip minimap on every move
  }

  p.x = e.clientX;
  p.y = e.clientY;

  if (pointers.size === 2) {
    const [firstPointer, secondPointer] = [...pointers.values()];
    const dist = Math.hypot(firstPointer.x - secondPointer.x, firstPointer.y - secondPointer.y);
    if (pinchDist) zoomAt((firstPointer.x + secondPointer.x) / 2, (firstPointer.y + secondPointer.y) / 2, pinchDist / dist);
    pinchDist = dist;
    dragMoved = 99; // suppress click after pinch
  }
});

function onPointerUp(e) {
  pointers.delete(e.pointerId);
  if (pointers.size < 2) pinchDist = 0;
  if (pointers.size === 0) {
    stage.classList.remove('drag');
    updateMinimap(); // sync minimap once drag ends
    if (dragMoved < 5 && pointerDownTarget) handleClick(pointerDownTarget);
  }
}

stage.addEventListener('pointerup', onPointerUp);
stage.addEventListener('pointercancel', onPointerUp);

stage.addEventListener('wheel', e => {
  e.preventDefault();
  zoomAt(e.clientX, e.clientY, Math.exp(e.deltaY * (e.ctrlKey ? 0.01 : 0.0016)));
}, { passive: false });

window.addEventListener('resize', () => {
  const cy = viewBox.y + viewBox.h / 2;
  viewBox.h = viewBox.w / stageAspect();
  viewBox.y = cy - viewBox.h / 2;
  applyViewBox();
});

// ── Highlight & selection ─────────────────────────────────────────────────────

let selectedTable = null;
let highlightedEdges = [];

function clearHighlight() {
  highlightedEdges.forEach(p => p.classList.remove('hl'));
  highlightedEdges = [];
}

function highlightTableEdges(tableName) {
  clearHighlight();
  (data.tEdges[tableName] || []).forEach(i => {
    const p = edgeEls[i];
    if (p) { p.classList.add('hl'); highlightedEdges.push(p); }
  });
}

function clearDim() {
  Object.values(tableEls).forEach(g => g.classList.remove('dim', 'sel'));
  edgeEls.forEach(p => p && p.classList.remove('dim'));
}

function selectTable(name, zoom) {
  if (!data.tables[name]) return;
  selectedTable = name;
  clearDim();
  highlightTableEdges(name);

  // Dim everything except the selected table and its direct neighbours
  const neighbors = new Set([name]);
  (data.tEdges[name] || []).forEach(i => {
    const e = data.edges[i];
    neighbors.add(e[0]);
    neighbors.add(e[2]);
  });
  for (const tableName in tableEls) tableEls[tableName].classList.toggle('dim', !neighbors.has(tableName));
  tableEls[name].classList.add('sel');
  edgeEls.forEach(p => p && !p.classList.contains('hl') && p.classList.add('dim'));

  renderSidePanel(name);
  side.classList.add('open');

  if (zoom) {
    const b = data.tables[name].box;
    fitRect({ x: b[0], y: b[1], w: b[2], h: b[3] }, 120, 900);
  }
}

function clearSelection() {
  selectedTable = null;
  clearDim();
  clearHighlight();
  side.classList.remove('open');
}

function handleClick(el) {
  const g = el.closest && el.closest('.tbl');
  if (g) selectTable(g.dataset.t, false);
  else clearSelection();
}

// ── Hover tooltip ─────────────────────────────────────────────────────────────

svg.addEventListener('mouseover', e => {
  const g = e.target.closest('.tbl');
  if (g && !selectedTable) highlightTableEdges(g.dataset.t);
  if (e.target.classList.contains('row') && g) {
    const tbl = data.tables[g.dataset.t];
    const col = tbl.cols.find(c => c.n === e.target.dataset.c);
    if (col) showTooltip(e, tbl, col);
  }
});

svg.addEventListener('mousemove', e => {
  if (tip.style.display === 'block') {
    tip.style.left = Math.min(e.clientX + 14, innerWidth - 350) + 'px';
    tip.style.top = (e.clientY + 16) + 'px';
  }
});

svg.addEventListener('mouseout', e => {
  const g = e.target.closest('.tbl');
  if (g && !selectedTable && !g.contains(e.relatedTarget)) clearHighlight();
  if (e.target.classList.contains('row')) tip.style.display = 'none';
});

function columnFlags(col) {
  return [
    col.pk && 'PK',
    col.fk && 'FK',
    col.uq && 'unique',
    (col.nn || col.pk) && 'not null',
    col.inc && 'auto-increment',
  ].filter(Boolean);
}

function findFKEdge(tableName, colName) {
  return data.edges.find(e => e[0] === tableName && e[1] === colName);
}

function showTooltip(e, tbl, col) {
  const fk = findFKEdge(tbl.name, col.n);
  tip.innerHTML =
    `<div class="t">${esc(col.n)} <span class="m">${esc(col.t)}</span></div>` +
    `<div class="m">` +
      `${esc(columnFlags(col).join(' · '))}` +
      `${fk ? ' → ' + esc(fk[2] + '.' + fk[3]) : ''}` +
      `${col.d != null ? ' · default ' + esc(col.d) : ''}` +
    `</div>` +
    (col.note ? `<div style="margin-top:4px">${md(col.note)}</div>` : '');
  tip.style.display = 'block';
  tip.style.left = (e.clientX + 14) + 'px';
  tip.style.top = (e.clientY + 16) + 'px';
}

// ── Side panel ────────────────────────────────────────────────────────────────

function renderSidePanel(name) {
  const tbl = data.tables[name];
  const cat = data.cats[tbl.cat] || ['#fff', 'Custom'];

  const colsHtml = tbl.cols.map(col => {
    const fk = findFKEdge(name, col.n);
    const enumVals = data.enums[col.t];
    return (
      `<div class="col">` +
        `<div class="col-top">` +
          `<b>${esc(col.n)}</b>` +
          `<span class="ty">${esc(col.t)}</span>` +
          (col.pk ? '<span class="tag pk">PK</span>' : '') +
          (col.fk ? '<span class="tag fk">FK</span>' : '') +
          (col.uq && !col.pk ? '<span class="tag">UQ</span>' : '') +
          ((col.nn || col.pk) ? '<span class="tag nn">NOT NULL</span>' : '') +
          (col.inc ? '<span class="tag">AUTO</span>' : '') +
          (fk ? `<span>→ <a class="go" data-go="${esc(fk[2])}">${esc(fk[2] + '.' + fk[3])}</a></span>` : '') +
        `</div>` +
        (col.d != null ? `<div class="col-note">default <code>${esc(col.d)}</code></div>` : '') +
        `<div class="col-note">${col.note ? md(col.note) : '<span class="none">no note</span>'}</div>` +
        (enumVals ? `<div class="col-note">values: ${enumVals.map(v => `<code title="${esc(v[1])}">${esc(v[0])}</code>`).join(' ')}</div>` : '') +
      `</div>`
    );
  }).join('');

  const incoming = data.edges.filter(e => e[2] === name);

  side.innerHTML =
    `<header>` +
      `<button class="x" title="Close (Esc)">✕</button>` +
      `<button class="copylink" title="Copy link to this table" data-copylink="${esc(name)}">⎘ Link</button>` +
      `<h2>${esc(name)}</h2>` +
      `<div class="crumbs">${esc(tbl.path.join(' › '))}</div>` +
      `<span class="cat" style="background:${cat[0]}">${esc(cat[1])}</span>` +
    `</header>` +
    `<section>` +
      `<h3>Notes</h3>` +
      `<div class="note">${tbl.note ? md(tbl.note) : '<span class="none">No table note. Add <code>Note: \'...\'</code> in the DBML.</span>'}</div>` +
      (tbl.gnote ? `<div class="col-note" style="margin-top:8px"><b>${esc(tbl.path[tbl.path.length - 1])}:</b> ${md(tbl.gnote)}</div>` : '') +
    `</section>` +
    `<section>` +
      `<h3>Columns (${tbl.cols.length})</h3>` +
      colsHtml +
    `</section>` +
    `<section>` +
      `<h3>Referenced by (${incoming.length})</h3>` +
      (incoming.length
        ? `<ul class="refs">${incoming.map(e =>
            `<li><a class="go" data-go="${esc(e[0])}">${esc(e[0] + '.' + e[1])}</a> → ${esc(e[3])}</li>`
          ).join('')}</ul>`
        : '<span class="none">nothing</span>') +
    `</section>`;
}

side.addEventListener('click', e => {
  if (e.target.closest('.x')) return clearSelection();

  const goEl = e.target.closest('[data-go]');
  if (goEl) return selectTable(goEl.dataset.go, true);

  const copyEl = e.target.closest('[data-copylink]');
  if (copyEl) {
    const url = location.origin + location.pathname + '#' + encodeURIComponent(copyEl.dataset.copylink);
    navigator.clipboard?.writeText(url).catch(() => {});
    const orig = copyEl.textContent;
    copyEl.textContent = '✓ Copied';
    setTimeout(() => { copyEl.textContent = orig; }, 1500);
  }
});

// ── Search ────────────────────────────────────────────────────────────────────

const tableNames = Object.keys(data.tables).sort();
document.getElementById('tlist').innerHTML = tableNames.map(n => `<option value="${esc(n)}">`).join('');

function searchMatches(query) {
  query = query.toLowerCase();
  return tableNames.filter(tableName =>
    tableName.toLowerCase().includes(query) ||
    data.tables[tableName].cols.some(col => col.n.toLowerCase().includes(query))
  );
}

searchInput.addEventListener('input', () => {
  const query = searchInput.value.trim();
  if (selectedTable) clearSelection();
  if (!query) { clearDim(); return; }
  if (data.tables[query]) { selectTable(query, true); return; }
  const matches = new Set(searchMatches(query));
  for (const tableName in tableEls) tableEls[tableName].classList.toggle('dim', !matches.has(tableName));
});

searchInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    const query = searchInput.value.trim();
    const hits = data.tables[query] ? [query] : searchMatches(query);
    if (hits.length) selectTable(hits[0], true);
  }
  if (e.key === 'Escape') {
    searchInput.value = '';
    clearSelection();
    searchInput.blur();
  }
});

// ── Area chips ────────────────────────────────────────────────────────────────

const areasEl = document.getElementById('areas');
areasEl.innerHTML = data.areas.map((a, i) =>
  `<button class="chip" data-a="${i}" title="Zoom to ${esc(a.name)}">` +
    `<i style="background:${a.color}"></i>${esc(a.name)}` +
  `</button>`
).join(' ');

areasEl.addEventListener('click', e => {
  const btn = e.target.closest('[data-a]');
  if (btn) {
    const a = data.areas[+btn.dataset.a].box;
    fitRect({ x: a[0], y: a[1], w: a[2], h: a[3] }, 20);
  }
});

// ── Toolbar ───────────────────────────────────────────────────────────────────

document.getElementById('fit').onclick = fit;

const focusBtn = document.getElementById('focus');
focusBtn.onclick = () => {
  svg.classList.toggle('focus');
  focusBtn.classList.toggle('on');
};

document.getElementById('pr').onclick = () => print();

// Save/restore viewbox around print so the full diagram is printed
let printSavedViewBox = null;
addEventListener('beforeprint', () => { printSavedViewBox = { ...viewBox }; viewBox = { ...FULL }; applyViewBox(); });
addEventListener('afterprint', () => { if (printSavedViewBox) { viewBox = printSavedViewBox; applyViewBox(); } });

document.getElementById('dl').onclick = () => {
  const clone = svg.cloneNode(true);
  clone.setAttribute('viewBox', `0 0 ${data.W} ${data.H}`);
  clone.setAttribute('width', data.W);
  clone.setAttribute('height', data.H);
  clone.classList.remove('focus');
  clone.querySelectorAll('.dim,.hl,.sel').forEach(n => n.classList.remove('dim', 'hl', 'sel'));
  clone.querySelectorAll('.row').forEach(n => n.remove());
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: 'image/svg+xml' }));
  a.download = (data.slug || 'schema') + '.svg';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};

// ── Dark mode ─────────────────────────────────────────────────────────────────

const darkBtn = document.getElementById('dark');
if (localStorage.getItem('dbml-dark') === '1') document.documentElement.classList.add('dark');
darkBtn.textContent = document.documentElement.classList.contains('dark') ? 'Light' : 'Dark';
darkBtn.onclick = () => {
  const on = document.documentElement.classList.toggle('dark');
  localStorage.setItem('dbml-dark', on ? '1' : '0');
  darkBtn.textContent = on ? 'Light' : 'Dark';
};

// ── Keyboard shortcuts ────────────────────────────────────────────────────────

addEventListener('keydown', e => {
  if (e.target === searchInput) return;
  if (e.key === '/') { e.preventDefault(); searchInput.focus(); }
  else if (e.key === 'Escape') clearSelection();
  else if (e.key === 'f' || e.key === 'F') fit();
  else if (e.key === 'l' || e.key === 'L') focusBtn.click();
});

// ── Minimap ───────────────────────────────────────────────────────────────────

function updateMinimap() {
  const scaleX = minimap.clientWidth / data.W;
  const scaleY = minimap.clientHeight / data.H;
  minimapVp.setAttribute('x', viewBox.x * scaleX);
  minimapVp.setAttribute('y', viewBox.y * scaleY);
  minimapVp.setAttribute('width', viewBox.w * scaleX);
  minimapVp.setAttribute('height', viewBox.h * scaleY);
}

// Clone the full SVG into the minimap once, without interactive hit-rects
{
  const clone = svg.cloneNode(true);
  clone.removeAttribute('style');
  clone.setAttribute('width', '100%');
  clone.setAttribute('height', '100%');
  clone.setAttribute('viewBox', `0 0 ${data.W} ${data.H}`);
  clone.querySelectorAll('.row').forEach(n => n.remove());
  minimap.querySelector('svg').insertBefore(clone, minimapVp);
}

// ── Init ──────────────────────────────────────────────────────────────────────

fit();
updateMinimap();

// Deep-link: #TableName in URL selects that table on load
const initialHash = location.hash.slice(1);
if (initialHash) {
  const name = decodeURIComponent(initialHash);
  if (data.tables[name]) selectTable(name, true);
}

})();
