const DATA = JSON.parse(document.getElementById("skt-data").textContent);
const PALETTE = [
  "#58a6ff", "#3fb950", "#d29922", "#bc8cff", "#f778ba",
  "#39c5cf", "#ffa657", "#ff7b72", "#79c0ff", "#56d364"
];

const DEFAULT_WEIGHTING = (DATA.meta && DATA.meta.default_weighting) ? DATA.meta.default_weighting : "count";

const state = {
  theme: "dark",
  weighting: DEFAULT_WEIGHTING, // "count" | "agg:<key>"
  axisId: DATA.time_axes.length ? DATA.time_axes[0].id : "",
  sliderLo: 0,
  sliderHi: 1000,
  rangeMode: "overlap", // overlap | first | contained
  fieldFilters: new Map(), // fieldKey -> Set(values)
  search: "",
  weightMode: "observations", // observations | skits
  selectedField: DATA.fields.length ? DATA.fields[0].key : "",
  selectedAgg: DATA.aggregates.length ? DATA.aggregates[0].key : "",
  aggView: "outliers", // outliers | histogram
  paretoTop: 40,
  sortBy: "weight",
  sortDir: "desc",
  showAllTokens: false,
  page: 1,
  pageSize: 25,
  expandedIds: new Set(),
  driftIdx: DATA.history.drift.length ? DATA.history.drift.length - 1 : 0,
  corrTab: "network", // network | heatmap | clusters
  corrMinPhi: 0.14,
  corrSign: "all", // all | pos | neg
  corrHideLocks: true,
  corrSelectedNode: null,
  corrMatMetric: "theils", // theils | cramers
  sankeyFields: [],
  sankeyCustom: false,
  charts: {}
};

function activeWeightMeta() {
  if (state.weighting && state.weighting.startsWith("agg:")) {
    const k = state.weighting.slice(4);
    const found = (DATA.weightings || []).find(w => w.key === k);
    if (found) {
      return {
        id: "agg:" + found.key,
        key: found.key,
        label: found.key,
        shortLabel: found.key,
        source: found.source,
        totalAll: found.total,
        isCount: false
      };
    }
  }
  return {
    id: "count",
    key: "count",
    label: "Observations",
    shortLabel: "obs",
    source: "COUNT",
    totalAll: DATA.meta.total_observations,
    isCount: true
  };
}


function fmtWeight(n, wm) {
  const m = wm || activeWeightMeta();
  return m.isCount ? fmtInt(n) : fmtNum(n);
}

function el(tag, attrs, text) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "style") node.setAttribute("style", v);
      else node.setAttribute(k, String(v));
    }
  }
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function fmtInt(n) {
  return (n === null || n === undefined || Number.isNaN(n)) ? "N/A" : Math.round(n).toLocaleString();
}

function fmtNum(n, digits) {
  if (n === null || n === undefined || Number.isNaN(n)) return "N/A";
  const d = digits !== undefined ? digits : (Math.abs(n) >= 100 || Number.isInteger(n) ? 1 : 3);
  if (Number.isInteger(n)) return n.toLocaleString();
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: d });
}

function fmtPct(p) {
  return (p === null || p === undefined || Number.isNaN(p)) ? "N/A" : p.toFixed(1) + "%";
}

function fmtMs(ms, isDate) {
  if (ms === null || ms === undefined) return "N/A";
  const iso = new Date(ms).toISOString();
  return isDate ? iso.slice(0, 10) : iso.replace("T", " ").slice(0, 19) + "Z";
}

function fmtAny(v) {
  if (v === null || v === undefined) return "-";
  if (typeof v === "number") return fmtNum(v);
  const s = String(v);
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(s)) {
    return s.slice(0, 19).replace("T", " ") + "Z";
  }
  return s;
}


function getAxis() {
  return DATA.time_axes.find(a => a.id === state.axisId) || null;
}

function sliderBoundsForAxis(axis) {
  if (!axis) return null;
  if (axis.kind === "runs") {
    const runs = axis.runs || [];
    if (!runs.length) return null;
    const loIdx = Math.max(0, Math.min(runs.length - 1, Math.round(state.sliderLo)));
    const hiIdx = Math.max(loIdx, Math.min(runs.length - 1, Math.round(state.sliderHi)));
    return { kind: "runs", loIdx, hiIdx, runs };
  }
  const span = axis.max_ms - axis.min_ms;
  const loMs = span > 0 ? Math.round(axis.min_ms + (span * state.sliderLo) / 1000) : axis.min_ms;
  const hiMs = span > 0 ? Math.round(axis.min_ms + (span * state.sliderHi) / 1000) : axis.max_ms;
  return { kind: axis.kind, loMs, hiMs };
}

function syncSliderLimits() {
  const axis = getAxis();
  const loEl = document.getElementById("range-lo");
  const hiEl = document.getElementById("range-hi");
  const box = document.getElementById("slider-box");
  const modeEl = document.getElementById("range-mode");
  if (!axis) {
    box.style.display = "none";
    modeEl.style.display = "none";
    return;
  }
  box.style.display = "";
  modeEl.style.display = "";
  if (axis.kind === "runs") {
    const maxIdx = Math.max(0, axis.runs.length - 1);
    loEl.min = "0";
    loEl.max = String(maxIdx);
    hiEl.min = "0";
    hiEl.max = String(maxIdx);
    state.sliderLo = 0;
    state.sliderHi = maxIdx;
    loEl.value = "0";
    hiEl.value = String(maxIdx);
    loEl.disabled = maxIdx === 0;
    hiEl.disabled = maxIdx === 0;
  } else {
    loEl.min = "0";
    loEl.max = "1000";
    hiEl.min = "0";
    hiEl.max = "1000";
    state.sliderLo = 0;
    state.sliderHi = 1000;
    loEl.value = "0";
    hiEl.value = "1000";
    const flat = axis.min_ms === axis.max_ms;
    loEl.disabled = flat;
    hiEl.disabled = flat;
  }
}

function isSliderNarrowed(axis) {
  if (!axis) return false;
  if (axis.kind === "runs") {
    return state.sliderLo > 0 || state.sliderHi < Math.max(0, axis.runs.length - 1);
  }
  return state.sliderLo > 0 || state.sliderHi < 1000;
}

function matchesRange(skit, axis, bounds) {
  if (!axis || !bounds || !isSliderNarrowed(axis)) return true;
  if (bounds.kind === "runs") {
    const idxMap = new Map();
    bounds.runs.forEach((r, i) => idxMap.set(r.id, i));
    const f = idxMap.has(skit.first_seen) ? idxMap.get(skit.first_seen) : null;
    const l = idxMap.has(skit.last_seen) ? idxMap.get(skit.last_seen) : f;
    if (f === null || l === null) return false;
    const lo = Math.min(f, l), hi = Math.max(f, l);
    if (state.rangeMode === "first") return lo >= bounds.loIdx && lo <= bounds.hiIdx;
    if (state.rangeMode === "contained") return lo >= bounds.loIdx && hi <= bounds.hiIdx;
    return hi >= bounds.loIdx && lo <= bounds.hiIdx;
  }
  const tb = skit.time_bounds && skit.time_bounds[axis.id];
  if (!tb) return false;
  const [lo, hi] = tb;
  if (state.rangeMode === "first") return lo >= bounds.loMs && lo <= bounds.hiMs;
  if (state.rangeMode === "contained") return lo >= bounds.loMs && hi <= bounds.hiMs;
  return hi >= bounds.loMs && lo <= bounds.hiMs;
}

function filterSkits() {
  const axis = getAxis();
  const bounds = sliderBoundsForAxis(axis);
  const q = state.search.trim().toLowerCase();
  return DATA.skits.filter(skit => {
    if (!matchesRange(skit, axis, bounds)) return false;
    for (const [fk, allowed] of state.fieldFilters.entries()) {
      if (!allowed.size) continue;
      const val = Object.prototype.hasOwnProperty.call(skit.tokens, fk) ? skit.tokens[fk] : "NULL";
      if (!allowed.has(val)) return false;
    }
    if (q) {
      if (skit.id.toLowerCase().includes(q)) return true;
      for (const [k, v] of Object.entries(skit.tokens)) {
        if (k.toLowerCase().includes(q) || String(v).toLowerCase().includes(q)) return true;
      }
      return false;
    }
    return true;
  });
}


function themeColors() {
  const cs = getComputedStyle(document.documentElement);
  return {
    text: cs.getPropertyValue("--text").trim(),
    muted: cs.getPropertyValue("--muted").trim(),
    border: cs.getPropertyValue("--border").trim(),
    accent: cs.getPropertyValue("--accent").trim(),
    accent2: cs.getPropertyValue("--accent-2").trim()
  };
}

function destroyChart(name) {
  if (state.charts[name]) {
    state.charts[name].destroy();
    delete state.charts[name];
  }
}

function updateSliderUI() {
  const axis = getAxis();
  if (!axis) return;
  const bounds = sliderBoundsForAxis(axis);
  const lblLo = document.getElementById("slider-lo-label");
  const lblHi = document.getElementById("slider-hi-label");
  const fill = document.getElementById("dual-fill");
  let pLo = 0, pHi = 100;
  if (axis.kind === "runs") {
    const maxIdx = Math.max(1, axis.runs.length - 1);
    pLo = (bounds.loIdx / maxIdx) * 100;
    pHi = axis.runs.length <= 1 ? 100 : (bounds.hiIdx / maxIdx) * 100;
    const rLo = axis.runs[bounds.loIdx];
    const rHi = axis.runs[bounds.hiIdx];
    lblLo.textContent = "From: " + rLo.id + (rLo.started ? " (" + rLo.started.slice(0, 16) + ")" : "");
    lblHi.textContent = "To: " + rHi.id + (rHi.finished ? " (" + rHi.finished.slice(0, 16) + ")" : "");
  } else {
    pLo = (state.sliderLo / 1000) * 100;
    pHi = (state.sliderHi / 1000) * 100;
    const isDate = axis.kind === "date";
    lblLo.textContent = "From: " + fmtMs(bounds.loMs, isDate);
    lblHi.textContent = "To: " + fmtMs(bounds.hiMs, isDate);
  }
  fill.style.left = pLo + "%";
  fill.style.width = Math.max(0, pHi - pLo) + "%";
}

function renderChips(wm) {
  const wrap = document.getElementById("active-chips");
  clear(wrap);
  let any = false;
  if (!wm.isCount) {
    any = true;
    const chip = el("span", { class: "chip" });
    chip.appendChild(el("span", null, "weight: " + wm.label + " (" + wm.source + ")"));
    const btn = el("button", { type: "button", title: "Reset weighting to Observations" }, "×");
    btn.addEventListener("click", () => {
      state.weighting = "count";
      const wSel = document.getElementById("weight-select");
      if (wSel) wSel.value = "count";
      state.page = 1;
      render();
    });
    chip.appendChild(btn);
    wrap.appendChild(chip);
  }
  for (const [fk, vals] of state.fieldFilters.entries()) {
    for (const v of vals) {
      any = true;
      const chip = el("span", { class: "chip" });
      chip.appendChild(el("span", null, fk + " = " + v));
      const btn = el("button", { type: "button", title: "Remove filter" }, "×");
      btn.addEventListener("click", () => {
        vals.delete(v);
        if (!vals.size) state.fieldFilters.delete(fk);
        state.page = 1;
        render();
      });
      chip.appendChild(btn);
      wrap.appendChild(chip);
    }
  }
  if (state.search.trim()) {
    any = true;
    const chip = el("span", { class: "chip" });
    chip.appendChild(el("span", null, 'search: "' + state.search.trim() + '"'));
    const btn = el("button", { type: "button" }, "×");
    btn.addEventListener("click", () => {
      state.search = "";
      document.getElementById("search-input").value = "";
      state.page = 1;
      render();
    });
    chip.appendChild(btn);
    wrap.appendChild(chip);
  }
  const axis = getAxis();
  if (isSliderNarrowed(axis)) {
    any = true;
    const chip = el("span", { class: "chip" });
    chip.appendChild(el("span", null, "range: " + axis.label + " (" + state.rangeMode + ")"));
    const btn = el("button", { type: "button" }, "×");
    btn.addEventListener("click", () => {
      syncSliderLimits();
      state.page = 1;
      render();
    });
    chip.appendChild(btn);
    wrap.appendChild(chip);
  }
  if (!any) {
    wrap.appendChild(el("span", { class: "muted", style: "font-size:12px" }, "No active filters — click any field bar or drag the time/run slider to slice."));
  }
}


const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs, text) {
  const node = document.createElementNS(SVG_NS, tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  }
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function shortTokenLabel(f, v) {
  if (v === "TRUE") return f.replace("media_", "m_").replace("_present", ":pres").replace("_any", ":any").replace("_multiple", ":2+");
  let sv = String(v).replace("app.bsky.embed.", "").replace(/app\.bsky\.richtext\.facet#/g, "#").replace("recordWithMedia", "quote+media");
  if (sv.length > 20) sv = sv.slice(0, 18) + "...";
  if (f === "embed_type") return "embed:" + sv;
  if (f === "media_type") return "media:" + sv;
  if (f === "facet_types") return "facet:" + sv;
  if (f === "labels") return "label:" + sv;
  return f + ":" + sv;
}

function shortFieldName(f) {
  const s = f
    .replace("media_images_", "m_img_")
    .replace("media_gallery_", "m_gal_")
    .replace("images_", "img_")
    .replace("gallery_", "gal_")
    .replace("embed_type", "embed")
    .replace("media_type", "media")
    .replace("facet_types", "facets")
    .replace("_present", "_p")
    .replace("_multiple", "_2+");
  return s.length > 14 ? s.slice(0, 13) + "." : s;
}

