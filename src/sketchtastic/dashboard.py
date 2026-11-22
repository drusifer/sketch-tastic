"""Self-contained offline HTML interactive dashboard renderer (STORY-SKT-12, -13, -14).

Bundles vendored MIT Chart.js v4.4.9 and embeds the analysis payload using script-safe JSON
escaping under a strict offline Content Security Policy. Zero network calls or external CDNs.
"""

from __future__ import annotations

import html
import json
from functools import cache
from importlib.resources import files
from typing import Any

_CSP = (
    "default-src 'none'; "
    "style-src 'unsafe-inline'; "
    "script-src 'unsafe-inline'; "
    "img-src data:; "
    "font-src 'none'; "
    "connect-src 'none';"
)


@cache
def _chartjs_source() -> str:
    return files("sketchtastic").joinpath("assets/chart.umd.min.js").read_text("utf-8")


def _safe_json_for_script(value: Any) -> str:
    """Serialize JSON safe to embed inside an HTML `<script>` element."""
    raw = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    return (
        raw.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


_CSS = """\
:root {
  --bg: #0f1117;
  --surface: #171a23;
  --surface-2: #1f2430;
  --border: #2c3345;
  --text: #e6ebf5;
  --muted: #98a3b8;
  --accent: #58a6ff;
  --accent-2: #3fb950;
  --warn: #d29922;
  --danger: #f85149;
  --chip-bg: #232a3b;
  --radius: 10px;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
[data-theme="light"] {
  --bg: #f6f8fa;
  --surface: #ffffff;
  --surface-2: #f0f3f7;
  --border: #d0d7de;
  --text: #1f2328;
  --muted: #59636e;
  --accent: #0969da;
  --accent-2: #1a7f37;
  --warn: #9a6700;
  --danger: #cf222e;
  --chip-bg: #eaeef2;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: 14px;
  line-height: 1.45;
}
header {
  padding: 18px 24px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
h1 { margin: 0; font-size: 20px; font-weight: 700; }
h2 { margin: 0 0 10px; font-size: 16px; font-weight: 600; }
h3 { margin: 0 0 8px; font-size: 14px; font-weight: 600; color: var(--muted); }
.subtitle { color: var(--muted); font-size: 12px; margin-top: 3px; font-family: var(--mono); }
.hdr-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
button, select, input[type="search"] {
  background: var(--surface-2);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  font-family: inherit;
}
button { cursor: pointer; }
button:hover { border-color: var(--accent); }
button.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
button.small { padding: 3px 8px; font-size: 12px; }
button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.filter-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.slider-box {
  flex: 1 1 320px;
  min-width: 260px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
}
.slider-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-family: var(--mono);
  color: var(--muted);
  margin-bottom: 6px;
  gap: 8px;
}
.dual-range {
  position: relative;
  height: 22px;
  display: flex;
  align-items: center;
}
.dual-track {
  position: absolute;
  left: 0;
  right: 0;
  height: 5px;
  background: var(--border);
  border-radius: 3px;
}
.dual-fill {
  position: absolute;
  height: 5px;
  background: var(--accent);
  border-radius: 3px;
}
.dual-range input[type="range"] {
  position: absolute;
  width: 100%;
  margin: 0;
  background: none;
  pointer-events: none;
  -webkit-appearance: none;
  appearance: none;
  height: 22px;
}
.dual-range input[type="range"]::-webkit-slider-thumb {
  pointer-events: auto;
  -webkit-appearance: none;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--surface);
  cursor: pointer;
}
.dual-range input[type="range"]::-moz-range-thumb {
  pointer-events: auto;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--surface);
  cursor: pointer;
}
.chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--chip-bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-family: var(--mono);
}
.chip button {
  border: none;
  background: none;
  padding: 0 2px;
  color: var(--muted);
  font-weight: 700;
}
.chip button:hover { color: var(--danger); }
.badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: var(--chip-bg);
  color: var(--text);
  border: 1px solid var(--border);
}
.badge.ok { color: var(--accent-2); border-color: var(--accent-2); }
.badge.warn { color: var(--warn); border-color: var(--warn); }
.badge.danger { color: var(--danger); border-color: var(--danger); }
main {
  max-width: 1440px;
  margin: 0 auto;
  padding: 18px 24px 48px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
  gap: 12px;
}
.kpi {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
}
.kpi-label { font-size: 12px; color: var(--muted); }
.kpi-value { font-size: 22px; font-weight: 700; margin-top: 4px; font-family: var(--mono); }
.kpi-sub { font-size: 12px; color: var(--muted); margin-top: 3px; }
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
}
.card-hdr {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.grid-2 {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: 16px;
}
@media (max-width: 960px) { .grid-2 { grid-template-columns: 1fr; } }
.chart-wrap { position: relative; height: 320px; width: 100%; }
.chart-wrap.tall { height: 360px; }
.table-wrap { overflow-x: auto; max-height: 440px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td {
  padding: 7px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
th {
  position: sticky;
  top: 0;
  background: var(--surface-2);
  font-weight: 600;
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}
tr.clickable { cursor: pointer; }
tr.clickable:hover { background: var(--surface-2); }
tr.selected { background: rgba(88, 166, 255, 0.14); }
.num { text-align: right; font-family: var(--mono); white-space: nowrap; }
.mono { font-family: var(--mono); }
.clip {
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
#fields-table th, #fields-table td, #aggs-table th, #aggs-table td { padding: 6px 8px; font-size: 12px; }
#fields-table td:last-child { white-space: nowrap; }
.muted { color: var(--muted); }
.note {
  background: var(--surface-2);
  border-left: 3px solid var(--accent);
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 12px;
}
.warn-box {
  background: var(--surface-2);
  border-left: 3px solid var(--warn);
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  margin-bottom: 12px;
}
.token-pill {
  display: inline-block;
  font-family: var(--mono);
  font-size: 11px;
  background: var(--chip-bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
  margin: 1px 3px 1px 0;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}
.sample-box {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  margin-top: 6px;
}
pre.json-pre {
  margin: 6px 0 0;
  padding: 8px;
  background: var(--surface-2);
  border-radius: 6px;
  overflow-x: auto;
  max-height: 280px;
  font-family: var(--mono);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
.pager { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; gap: 8px; flex-wrap: wrap; }
.empty-state { padding: 24px; text-align: center; color: var(--muted); }
.cov-strip { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.sub-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.sub-panel { display: none; }
.sub-panel.active { display: block; }
.inspector {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 10px;
  font-size: 12px;
  min-height: 46px;
}
.clusters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.cluster-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 8px;
  padding: 10px 12px;
}
.cluster-hdr {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
}
.ctrl-inline { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: center; margin-bottom: 10px; font-size: 12px; }
.svg-wrap { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 8px; overflow-x: auto; }
.svg-wrap svg text { user-select: none; }
.legend-row { display: flex; flex-wrap: wrap; gap: 12px; font-size: 11px; color: var(--muted); margin-top: 8px; align-items: center; }
.leg-line { display: inline-block; width: 18px; height: 2px; vertical-align: middle; margin-right: 5px; }
.leg-line.pos { background: var(--accent); }
.leg-line.neg { border-top: 2px dashed var(--danger); height: 0; }
"""


_APP_JS = r"""
(function () {
  "use strict";

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

  function skitWeight(skit, wm) {
    const m = wm || activeWeightMeta();
    if (m.isCount) return skit.count;
    if (skit.weights && Object.prototype.hasOwnProperty.call(skit.weights, m.key)) {
      const v = Number(skit.weights[m.key]);
      return Number.isFinite(v) && v > 0 ? v : 0;
    }
    return 0;
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

  function asNum(v) {
    if (typeof v === "number") return Number.isFinite(v) ? v : null;
    if (typeof v !== "string") return null;
    const t = v.trim();
    if (!t) return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  }

  function asBool(v) {
    if (typeof v !== "string") return null;
    const t = v.trim().toLowerCase();
    if (t === "true") return true;
    if (t === "false") return false;
    return null;
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

  function weightedMedian(pairs) {
    const arr = pairs.filter(p => p[1] > 0).sort((a, b) => a[0] - b[0]);
    const total = arr.reduce((s, p) => s + p[1], 0);
    if (total <= 0) return null;
    const half = total / 2;
    let run = 0;
    for (let i = 0; i < arr.length; i++) {
      run += arr[i][1];
      if (Math.abs(run - half) <= 1e-12) {
        return i + 1 < arr.length ? (arr[i][0] + arr[i + 1][0]) / 2 : arr[i][0];
      }
      if (run > half) return arr[i][0];
    }
    return arr[arr.length - 1][0];
  }

  function plainMedian(nums) {
    if (!nums.length) return null;
    const s = nums.slice().sort((a, b) => a - b);
    const m = Math.floor(s.length / 2);
    return s.length % 2 === 1 ? s[m] : (s[m - 1] + s[m]) / 2;
  }

  function computeFields(skits, totalW, wm) {
    const keys = DATA.fields.map(f => f.key);
    const nSkits = skits.length;
    return keys.map(key => {
      const byVal = new Map();
      for (const s of skits) {
        const val = Object.prototype.hasOwnProperty.call(s.tokens, key) ? s.tokens[key] : "NULL";
        const cur = byVal.get(val) || [0, 0];
        cur[0] += skitWeight(s, wm);
        cur[1] += 1;
        byVal.set(val, cur);
      }
      const entries = Array.from(byVal.entries()).sort((a, b) => (b[1][0] - a[1][0]) || (b[1][1] - a[1][1]) || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
      const values = entries.map(([value, [count, skit_count]]) => ({
        value,
        count,
        weight_pct: totalW ? (100 * count) / totalW : null,
        skit_count,
        skit_pct: nSkits ? (100 * skit_count) / nSkits : null
      }));
      const nonNull = entries.filter(([v]) => v !== "NULL");
      const nullObs = byVal.has("NULL") ? byVal.get("NULL")[0] : 0;
      let isBoolean = nonNull.length > 0;
      const boolPairs = [];
      for (const [v, [obs]] of nonNull) {
        const b = asBool(v);
        if (b === null) { isBoolean = false; break; }
        boolPairs.push([b, v, obs]);
      }
      let isNumeric = !isBoolean && nonNull.length > 0;
      const numPairs = [];
      if (isNumeric) {
        for (const [v, [obs]] of nonNull) {
          const parsed = asNum(v);
          if (parsed === null) { isNumeric = false; break; }
          numPairs.push([parsed, obs]);
        }
      }
      let fieldType = "enum";
      let minVal = null, maxVal = null, wMean = null, wMed = null, truePct = null;
      if (isBoolean) {
        fieldType = "boolean";
        boolPairs.sort((a, b) => (a[0] === b[0] ? (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0) : (a[0] ? 1 : -1)));
        minVal = boolPairs[0][1];
        maxVal = boolPairs[boolPairs.length - 1][1];
        const bTotal = boolPairs.reduce((a, p) => a + p[2], 0);
        const tObs = boolPairs.reduce((a, p) => a + (p[0] ? p[2] : 0), 0);
        truePct = bTotal > 0 ? (100 * tObs) / bTotal : null;
      } else if (isNumeric) {
        fieldType = "numeric";
        const nums = numPairs.map(p => p[0]);
        minVal = Math.min(...nums);
        maxVal = Math.max(...nums);
        const wTotal = numPairs.reduce((a, p) => a + p[1], 0);
        if (wTotal > 0) {
          wMean = numPairs.reduce((a, p) => a + p[0] * p[1], 0) / wTotal;
          wMed = weightedMedian(numPairs);
        }
      } else if (nonNull.length) {
        const strs = nonNull.map(([v]) => v).sort();
        minVal = strs[0];
        maxVal = strs[strs.length - 1];
      } else if (entries.length) {
        minVal = "NULL";
        maxVal = "NULL";
      }
      return {
        key,
        field_type: fieldType,
        cardinality: values.length,
        is_constant: values.length <= 1,
        is_high_cardinality: nSkits > 0 && values.length > 20 && (values.length / nSkits) >= 0.5,
        is_boolean: isBoolean,
        is_numeric: isNumeric,
        true_pct: truePct,
        min: minVal,
        max: maxVal,
        mode: values.length ? values[0] : null,
        weighted_mean: wMean,
        weighted_median: wMed,
        null_pct: totalW ? (100 * nullObs) / totalW : null,
        values
      };
    });
  }

  const HIST_MANTISSAS = [1.0, 1.5, 2.0, 3.0, 5.0, 7.0];

  function isHistObj(v) {
    if (!v || typeof v !== "object" || Array.isArray(v)) return false;
    if (v.mode === "log") return v.bins && typeof v.bins === "object" && typeof v.count === "number";
    if (v.mode === "fixed") {
      return Array.isArray(v.bounds) && Array.isArray(v.counts) &&
        typeof v.count === "number" && v.counts.length === v.bounds.length + 1;
    }
    return false;
  }

  function mergeHistStates(acc, next) {
    if (!next || !next.count) return acc;
    if (!acc) {
      if (next.mode === "log") return { mode: "log", count: next.count, bins: Object.assign({}, next.bins) };
      return { mode: "fixed", count: next.count, bounds: next.bounds.slice(), counts: next.counts.slice() };
    }
    if (acc.mode !== next.mode) return acc;
    if (acc.mode === "log") {
      acc.count += next.count;
      for (const [k, cnt] of Object.entries(next.bins)) {
        if (cnt > 0) acc.bins[k] = (Object.prototype.hasOwnProperty.call(acc.bins, k) ? acc.bins[k] : 0) + cnt;
      }
      return acc;
    }
    if (acc.bounds.length !== next.bounds.length || acc.bounds.some((b, i) => b !== next.bounds[i])) return acc;
    acc.count += next.count;
    for (let i = 0; i < acc.counts.length; i++) acc.counts[i] += next.counts[i];
    return acc;
  }

  function fmtBinEdge(v) {
    if (v === 0) return "0";
    const mag = Math.abs(v);
    const sign = v < 0 ? "-" : "";
    for (const [scale, suffix] of [[1e9, "G"], [1e6, "M"], [1e3, "k"]]) {
      if (mag >= scale) return sign + Number((mag / scale).toPrecision(4)) + suffix;
    }
    return String(Number(v.toPrecision(4)));
  }

  function logBinBounds(key) {
    if (key === "0") return [0, 0];
    const sign = key[0] === "+" ? 1 : -1;
    const idx = Number(key.slice(1));
    const n = HIST_MANTISSAS.length;
    const exp = Math.floor(idx / n);
    const step = idx - exp * n;
    const scale = Math.pow(10, exp);
    const loMag = Number((HIST_MANTISSAS[step] * scale).toPrecision(6));
    const hiMag = Number(((step + 1 < n ? HIST_MANTISSAS[step + 1] : 10.0) * scale).toPrecision(6));
    return sign > 0 ? [loMag, hiMag] : [-hiMag, -loMag];
  }

  function expandHistogram(h) {
    if (!h || !h.count) return null;
    const total = h.count;
    let bins = [];
    if (h.mode === "log") {
      const rows = [];
      for (const [k, cnt] of Object.entries(h.bins)) {
        if (cnt > 0) {
          const [lo, hi] = logBinBounds(k);
          rows.push([lo, hi, cnt]);
        }
      }
      rows.sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
      bins = rows.map(([lo, hi, cnt]) => ({
        lo, hi,
        label: (lo === 0 && hi === 0) ? "0" : (fmtBinEdge(lo) + "–" + fmtBinEdge(hi)),
        count: cnt,
        pct: (100 * cnt) / total
      }));
    } else {
      bins = h.counts.map((cnt, idx) => {
        const lo = idx === 0 ? null : h.bounds[idx - 1];
        const hi = idx === h.bounds.length ? null : h.bounds[idx];
        const label = lo === null ? ("≤" + fmtBinEdge(hi)) : (hi === null ? (">" + fmtBinEdge(lo)) : (fmtBinEdge(lo) + "–" + fmtBinEdge(hi)));
        return { lo, hi, label, count: cnt, pct: (100 * cnt) / total };
      });
    }
    const quantiles = {};
    for (const [name, prob] of [["p50", 0.5], ["p90", 0.9], ["p95", 0.95], ["p99", 0.99]]) {
      const rank = prob * total;
      let cum = 0, est = null;
      for (const b of bins) {
        if (b.count <= 0) continue;
        if (cum + b.count >= rank) {
          const frac = Math.max(0, Math.min(1, (rank - cum) / b.count));
          if (b.lo !== null && b.hi !== null) est = b.lo + frac * (b.hi - b.lo);
          else if (b.lo === null && b.hi !== null) est = b.hi >= 0 ? frac * b.hi : b.hi;
          else if (b.lo !== null) est = b.lo;
          break;
        }
        cum += b.count;
      }
      quantiles[name] = est;
    }
    return { mode: h.mode, count: total, bins, quantiles };
  }

  function isAvgObj(v) {
    return v && typeof v === "object" && !Array.isArray(v) &&
      Object.prototype.hasOwnProperty.call(v, "avg") &&
      Object.prototype.hasOwnProperty.call(v, "sum") &&
      Object.prototype.hasOwnProperty.call(v, "count") &&
      Object.keys(v).length === 3;
  }

  function extractPrimaryMetric(raw) {
    if (raw === null || raw === undefined) return { val: null, metric: "VALUE" };
    if (typeof raw === "number") return { val: raw, metric: "VALUE" };
    if (isAvgObj(raw)) return { val: raw.avg, metric: "AVG" };
    if (isHistObj(raw)) return { val: null, metric: "HISTOGRAM" };
    if (typeof raw === "object" && !Array.isArray(raw)) {
      if (Object.prototype.hasOwnProperty.call(raw, "AVG") && isAvgObj(raw.AVG)) {
        return { val: raw.AVG.avg, metric: "AVG" };
      }
      if (typeof raw.SUM === "number") return { val: raw.SUM, metric: "SUM" };
      if (typeof raw.COUNT === "number") return { val: raw.COUNT, metric: "COUNT" };
      if (typeof raw.MAX === "number") return { val: raw.MAX, metric: "MAX" };
    }
    return { val: null, metric: "VALUE" };
  }

  function computeAggregates(skits) {
    return DATA.aggregates.map(meta => {
      const key = meta.key;
      let sumTotal = 0, hasSum = false;
      let countTotal = 0, hasCount = false;
      let avgSum = 0, avgCount = 0, hasAvg = false;
      let gMin = null, gMax = null;
      let histState = null;
      let metricName = meta.skit_stats ? meta.skit_stats.metric : "VALUE";
      const active = [];

      function pushMin(v) {
        if (v === null || v === undefined) return;
        if (gMin === null || v < gMin) gMin = v;
      }
      function pushMax(v) {
        if (v === null || v === undefined) return;
        if (gMax === null || v > gMax) gMax = v;
      }

      for (const s of skits) {
        const raw = s.aggregates ? s.aggregates[key] : undefined;
        if (raw === null || raw === undefined) continue;
        if (typeof raw === "number") {
          sumTotal += raw; hasSum = true;
          pushMin(raw); pushMax(raw);
          active.push({ id: s.id, count: s.count, value: raw, tokens: s.tokens });
        } else if (isAvgObj(raw)) {
          hasAvg = true;
          if (raw.count > 0) { avgSum += raw.sum; avgCount += raw.count; }
          if (typeof raw.avg === "number") active.push({ id: s.id, count: s.count, value: raw.avg, tokens: s.tokens });
        } else if (isHistObj(raw)) {
          histState = mergeHistStates(histState, raw);
          metricName = "HISTOGRAM";
        } else if (typeof raw === "object" && !Array.isArray(raw)) {
          if (typeof raw.SUM === "number") { sumTotal += raw.SUM; hasSum = true; }
          if (typeof raw.COUNT === "number") { countTotal += raw.COUNT; hasCount = true; }
          if (isAvgObj(raw.AVG)) {
            hasAvg = true;
            if (raw.AVG.count > 0) { avgSum += raw.AVG.sum; avgCount += raw.AVG.count; }
          }
          if (isHistObj(raw.HISTOGRAM)) {
            histState = mergeHistStates(histState, raw.HISTOGRAM);
          }
          if (raw.MIN !== undefined && raw.MIN !== null) pushMin(raw.MIN);
          if (raw.MAX !== undefined && raw.MAX !== null) pushMax(raw.MAX);
          const p = extractPrimaryMetric(raw);
          metricName = p.metric;
          if (typeof p.val === "number") {
            active.push({ id: s.id, count: s.count, value: p.val, tokens: s.tokens });
          }
        } else if (typeof raw === "string") {
          pushMin(raw); pushMax(raw);
        }
      }
      const nums = active.map(x => x.value);
      active.sort((a, b) => (b.value - a.value) || (b.count - a.count));
      return {
        key,
        kind: meta.kind,
        global_sum: hasSum ? sumTotal : (hasAvg ? avgSum : null),
        global_count: hasCount ? countTotal : (hasAvg ? avgCount : null),
        global_min: gMin,
        global_max: gMax,
        weighted_mean: (hasAvg && avgCount > 0) ? (avgSum / avgCount) : null,
        skit_stats: {
          metric: metricName,
          active_skits: nums.length,
          min: nums.length ? Math.min(...nums) : null,
          max: nums.length ? Math.max(...nums) : null,
          mean: nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null,
          median: plainMedian(nums)
        },
        all_values: nums,
        outliers: active.slice(0, 15),
        histogram: expandHistogram(histState)
      };
    });
  }

  function computeConcentration(skits, totalW, wm) {
    const targets = [50, 80, 90, 95, 99];
    const ordered = skits.slice().sort((a, b) => (skitWeight(b, wm) - skitWeight(a, wm)) || (b.count - a.count) || (a.id < b.id ? -1 : 1));
    return targets.map(t => {
      if (!totalW || !ordered.length) return { target_pct: t, skits_needed: 0, skit_pct: null };
      let cum = 0, needed = 0;
      const cutoff = totalW * (t / 100);
      for (const s of ordered) {
        cum += skitWeight(s, wm); needed += 1;
        if (cum + 1e-9 >= cutoff) break;
      }
      return { target_pct: t, skits_needed: needed, skit_pct: (100 * needed) / ordered.length };
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

  function renderKPIs(skits, totalObs, totalW, conc, wm) {
    const allObs = DATA.meta.total_observations;
    const allSkits = DATA.meta.total_skits;
    const singletons = skits.filter(s => s.count === 1).length;
    const singletonW = skits.reduce((sum, s) => sum + (s.count === 1 ? skitWeight(s, wm) : 0), 0);
    const weightedSkits = skits.filter(s => skitWeight(s, wm) > 0).length;
    const status = document.getElementById("filter-status");
    if (wm.isCount) {
      status.textContent =
        "Showing " + fmtInt(skits.length) + " / " + fmtInt(allSkits) + " skits (" +
        fmtInt(totalObs) + " / " + fmtInt(allObs) + " obs" +
        (allObs ? ", " + fmtPct((100 * totalObs) / allObs) : "") + ")";
    } else {
      status.textContent =
        "Showing " + fmtInt(skits.length) + " / " + fmtInt(allSkits) + " skits · Weight: " + wm.label + " (" +
        fmtNum(totalW) + (wm.totalAll ? ", " + fmtPct((100 * totalW) / wm.totalAll) : "") + ")";
    }

    const grid = document.getElementById("kpi-grid");
    clear(grid);
    const ordered = skits.slice().sort((a, b) => (skitWeight(b, wm) - skitWeight(a, wm)) || (b.count - a.count));
    const topSkit = ordered.length ? ordered[0] : null;
    const topW = topSkit ? skitWeight(topSkit, wm) : 0;
    const top1 = topSkit && totalW ? (100 * topW) / totalW : null;
    const firstCard = wm.isCount
      ? ["Observations", fmtInt(totalObs), allObs && totalObs !== allObs ? fmtPct((100 * totalObs) / allObs) + " of sketch" : "100% of sketch"]
      : ["Total " + wm.label, fmtNum(totalW), fmtInt(weightedSkits) + " / " + fmtInt(skits.length) + " skits > 0" + (wm.totalAll && Math.abs(totalW - wm.totalAll) > 1e-9 ? " (" + fmtPct((100 * totalW) / wm.totalAll) + ")" : "")];
    const secondSub = wm.isCount
      ? (allSkits && skits.length !== allSkits ? fmtPct((100 * skits.length) / allSkits) + " of kinds" : "profile-defined kinds")
      : (fmtInt(totalObs) + " observations");
    const cards = [
      firstCard,
      ["Distinct Skits", fmtInt(skits.length), secondSub],
      ["Singletons (count = 1)", fmtInt(singletons), totalW ? fmtPct((100 * singletonW) / totalW) + " of " + wm.shortLabel : "N/A"],
      ["Top Skit Share", fmtPct(top1), topSkit ? topSkit.id.slice(0, 10) + " (" + fmtWeight(topW, wm) + ")" : "No skits"],
      ["Fields / Aggregates", DATA.fields.length + " / " + DATA.aggregates.length, "History runs: " + DATA.history.runs.length]
    ];
    for (const [label, val, sub] of cards) {
      const c = el("div", { class: "kpi" });
      c.appendChild(el("div", { class: "kpi-label" }, label));
      c.appendChild(el("div", { class: "kpi-value" }, val));
      c.appendChild(el("div", { class: "kpi-sub" }, sub));
      grid.appendChild(c);
    }

    const strip = document.getElementById("cov-strip");
    clear(strip);
    for (const c of conc) {
      const label = c.target_pct + "% " + wm.shortLabel + " -> " + fmtInt(c.skits_needed) + " skits" +
        (c.skit_pct !== null ? " (" + fmtPct(c.skit_pct) + ")" : "");
      strip.appendChild(el("span", { class: "badge" }, label));
    }
  }

  function renderPareto(skits, totalW, wm) {
    destroyChart("pareto");
    const canvas = document.getElementById("chart-pareto");
    const empty = document.getElementById("pareto-empty");
    if (!skits.length || !totalW) {
      canvas.style.display = "none";
      empty.style.display = "";
      return;
    }
    canvas.style.display = "";
    empty.style.display = "none";

    const ordered = skits
      .filter(s => wm.isCount || skitWeight(s, wm) > 0)
      .sort((a, b) => (skitWeight(b, wm) - skitWeight(a, wm)) || (b.count - a.count) || (a.id < b.id ? -1 : 1));
    const slice = ordered.slice(0, state.paretoTop);
    let cum = 0;
    const labels = [];
    const counts = [];
    const cumPcts = [];
    for (const s of slice) {
      const w = skitWeight(s, wm);
      cum += w;
      labels.push(s.id.slice(0, 8));
      counts.push(w);
      cumPcts.push(Number(((100 * cum) / totalW).toFixed(2)));
    }
    const tc = themeColors();
    state.charts.pareto = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: wm.label,
            data: counts,
            backgroundColor: tc.accent + "cc",
            borderRadius: 3,
            yAxisID: "y"
          },
          {
            label: "Cumulative %",
            data: cumPcts,
            type: "line",
            borderColor: tc.accent2,
            backgroundColor: tc.accent2,
            borderWidth: 2,
            pointRadius: slice.length <= 40 ? 2.5 : 0,
            tension: 0.15,
            yAxisID: "y1"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        onClick: (_evt, els) => {
          if (!els.length) return;
          const s = slice[els[0].index];
          if (s) {
            state.search = s.id.slice(0, 12);
            document.getElementById("search-input").value = state.search;
            state.expandedIds.add(s.id);
            state.page = 1;
            render();
          }
        },
        scales: {
          x: { ticks: { color: tc.muted, maxRotation: 45 }, grid: { color: tc.border + "44" } },
          y: { beginAtZero: true, ticks: { color: tc.muted }, grid: { color: tc.border + "55" }, title: { display: true, text: wm.label, color: tc.muted } },
          y1: { beginAtZero: true, max: 100, position: "right", ticks: { color: tc.muted, callback: v => v + "%" }, grid: { drawOnChartArea: false }, title: { display: true, text: "Cumulative %", color: tc.muted } }
        },
        plugins: {
          legend: { labels: { color: tc.text } },
          tooltip: {
            callbacks: {
              afterTitle: items => {
                const s = slice[items[0].dataIndex];
                if (!s) return "";
                const preview = Object.entries(s.tokens).filter(([, v]) => v !== "NULL" && v !== "FALSE").slice(0, 3).map(([k, v]) => k + "=" + v).join(", ");
                return (preview || s.id) + (wm.isCount ? "" : " (" + fmtInt(s.count) + " obs)");
              }
            }
          }
        }
      }
    });
  }

  function renderFieldsSection(fields, wm) {
    wm = wm || activeWeightMeta();
    const tbody = document.getElementById("fields-tbody");
    clear(tbody);
    const sel = document.getElementById("field-select");
    clear(sel);
    const wObsBtn = document.getElementById("weight-obs");
    if (wObsBtn) wObsBtn.textContent = wm.isCount ? "Observation Weight %" : (wm.label + " Weight %");
    const colM = document.getElementById("field-col-metric");
    const colP = document.getElementById("field-col-pct");
    if (colM) colM.textContent = wm.isCount ? "Observations" : wm.label;
    if (colP) colP.textContent = wm.isCount ? "Obs %" : "Weight %";
    if (!fields.length) {
      const tr = el("tr");
      const td = el("td", { colspan: "10", class: "empty-state" }, "No fields observed.");
      tr.appendChild(td);
      tbody.appendChild(tr);
      destroyChart("field");
      clear(document.getElementById("field-values-tbody"));
      return;
    }
    if (!fields.some(f => f.key === state.selectedField)) {
      state.selectedField = fields[0].key;
    }
    for (const f of fields) {
      const typeLabel = f.field_type === "boolean" ? "Boolean" : f.field_type === "numeric" ? "Numeric" : "Enum";
      const opt = el("option", { value: f.key }, f.key + " [" + typeLabel + ", " + f.cardinality + "]");
      if (f.key === state.selectedField) opt.selected = true;
      sel.appendChild(opt);

      const tr = el("tr", { class: "clickable" + (f.key === state.selectedField ? " selected" : "") });
      tr.addEventListener("click", () => {
        state.selectedField = f.key;
        renderFieldsSection(fields, wm);
        syncUrlState();
      });
      tr.appendChild(el("td", { class: "mono" }, f.key));
      const typeTd = el("td");
      if (f.field_type === "boolean") typeTd.appendChild(el("span", { class: "badge ok" }, "Boolean"));
      else if (f.field_type === "numeric") typeTd.appendChild(el("span", { class: "badge" }, "Numeric"));
      else typeTd.appendChild(el("span", { class: "muted" }, "Enum"));
      tr.appendChild(typeTd);
      tr.appendChild(el("td", { class: "num" }, fmtInt(f.cardinality)));
      tr.appendChild(el("td", { class: "mono clip", title: fmtAny(f.min) }, fmtAny(f.min)));
      tr.appendChild(el("td", { class: "mono clip", title: fmtAny(f.max) }, fmtAny(f.max)));
      const modeText = f.mode ? f.mode.value + " (" + fmtPct(f.mode.weight_pct) + ")" : "-";
      tr.appendChild(el("td", { class: "mono clip", title: modeText }, modeText));
      tr.appendChild(el("td", { class: "num" }, f.is_numeric ? fmtNum(f.weighted_mean) : "-"));
      tr.appendChild(el("td", { class: "num" }, f.is_numeric ? fmtNum(f.weighted_median) : "-"));
      tr.appendChild(el("td", { class: "num" }, fmtPct(f.null_pct)));
      const diagTd = el("td");
      let anyDiag = false;
      if (f.is_constant) { diagTd.appendChild(el("span", { class: "badge warn" }, "Constant")); anyDiag = true; }
      if (f.is_high_cardinality) { diagTd.appendChild(el("span", { class: "badge danger" }, "High-Card")); anyDiag = true; }
      if (f.redundant_with && f.redundant_with.length) {
        const list = f.redundant_with.join(", ");
        diagTd.appendChild(el("span", { class: "badge warn", title: "1:1 locked (Theil's U >= 0.99 both ways) with: " + list }, "≡ " + f.redundant_with[0] + (f.redundant_with.length > 1 ? " +" + (f.redundant_with.length - 1) : "")));
        anyDiag = true;
      } else if (f.determined_by && f.determined_by.length) {
        const list = f.determined_by.join(", ");
        diagTd.appendChild(el("span", { class: "badge", title: "Determined (Theil's U >= 0.99) by: " + list }, "← " + f.determined_by[0]));
        anyDiag = true;
      }
      if (!anyDiag) diagTd.appendChild(el("span", { class: "muted" }, "OK"));
      tr.appendChild(diagTd);
      tbody.appendChild(tr);
    }

    const activeField = fields.find(f => f.key === state.selectedField);
    renderFieldChartAndValues(activeField, wm);
  }

  function toggleFieldFilter(fieldKey, value) {
    let set = state.fieldFilters.get(fieldKey);
    if (!set) { set = new Set(); state.fieldFilters.set(fieldKey, set); }
    if (set.has(value)) {
      set.delete(value);
      if (!set.size) state.fieldFilters.delete(fieldKey);
    } else {
      set.add(value);
    }
    state.page = 1;
    render();
  }

  function renderFieldChartAndValues(field, wm) {
    destroyChart("field");
    const vt = document.getElementById("field-values-tbody");
    clear(vt);
    const metaBox = document.getElementById("field-detail-meta");
    if (!field || !field.values.length) {
      metaBox.textContent = "No observed values in current filter.";
      return;
    }
    const typeLabel = field.field_type === "boolean" ? "Boolean" : field.field_type === "numeric" ? "Numeric" : "Enum";
    metaBox.textContent =
      field.key + " [" + typeLabel + "] — Min: " + fmtAny(field.min) + " | Max: " + fmtAny(field.max) +
      (field.is_boolean && field.true_pct !== null ? " | True rate: " + fmtPct(field.true_pct) : "") +
      (field.is_numeric ? " | Weighted Mean: " + fmtNum(field.weighted_mean) + " | Weighted Median: " + fmtNum(field.weighted_median) : "") +
      (wm.isCount ? "" : " | Weighted by " + wm.label) +
      " (click any bar or row to filter)";

    const isObs = state.weightMode === "observations";
    const sortedVals = field.values.slice().sort((a, b) =>
      isObs ? ((b.count - a.count) || (b.skit_count - a.skit_count) || (a.value < b.value ? -1 : 1)) : ((b.skit_count - a.skit_count) || (a.value < b.value ? -1 : 1))
    );

    const activeSet = state.fieldFilters.get(field.key);
    for (const v of sortedVals.slice(0, 100)) {
      const isSel = activeSet && activeSet.has(v.value);
      const tr = el("tr", { class: "clickable" + (isSel ? " selected" : "") });
      tr.addEventListener("click", () => toggleFieldFilter(field.key, v.value));
      tr.appendChild(el("td", { class: "mono" }, v.value));
      tr.appendChild(el("td", { class: "num" }, fmtWeight(v.count, wm)));
      tr.appendChild(el("td", { class: "num" }, fmtPct(v.weight_pct)));
      tr.appendChild(el("td", { class: "num" }, fmtInt(v.skit_count)));
      tr.appendChild(el("td", { class: "num" }, fmtPct(v.skit_pct)));
      vt.appendChild(tr);
    }

    const MAX_BARS = 18;
    const chartItems = sortedVals.slice(0, MAX_BARS);
    const rest = sortedVals.slice(MAX_BARS);
    const labels = chartItems.map(v => v.value.length > 36 ? v.value.slice(0, 33) + "..." : v.value);
    const values = chartItems.map(v => isObs ? Number((v.weight_pct || 0).toFixed(2)) : Number((v.skit_pct || 0).toFixed(2)));
    const colors = chartItems.map((v, i) => {
      if (activeSet && activeSet.has(v.value)) return "#bc8cff";
      if (field.is_boolean) {
        const b = asBool(v.value);
        if (b === true) return "#3fb950";
        if (b === false) return "#58a6ff";
        return "#6e7681";
      }
      return PALETTE[i % PALETTE.length];
    });
    if (rest.length) {
      labels.push("Other (" + rest.length + " values)");
      const restPct = rest.reduce((s, r) => s + (isObs ? (r.weight_pct || 0) : (r.skit_pct || 0)), 0);
      values.push(Number(restPct.toFixed(2)));
      colors.push("#6e7681");
    }

    const tc = themeColors();
    const canvas = document.getElementById("chart-field");
    state.charts.field = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: isObs ? (wm.isCount ? "Observation Weight %" : wm.label + " Weight %") : "Distinct Skit Share %",
          data: values,
          backgroundColor: colors,
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        onClick: (_evt, els) => {
          if (!els.length) return;
          const idx = els[0].index;
          if (idx < chartItems.length) {
            toggleFieldFilter(field.key, chartItems[idx].value);
          }
        },
        scales: {
          x: { beginAtZero: true, max: 100, ticks: { color: tc.muted, callback: v => v + "%" }, grid: { color: tc.border + "55" } },
          y: { ticks: { color: tc.text, font: { family: "monospace", size: 11 } }, grid: { display: false } }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => {
                const idx = ctx.dataIndex;
                if (idx >= chartItems.length) return ctx.raw + "% across " + rest.length + " values";
                const item = chartItems[idx];
                return wm.label + ": " + fmtWeight(item.count, wm) + " (" + fmtPct(item.weight_pct) + ") | Skits: " + fmtInt(item.skit_count) + " (" + fmtPct(item.skit_pct) + ")";
              }
            }
          }
        }
      }
    });
  }

  function renderAggregatesSection(aggs) {
    const tbody = document.getElementById("aggs-tbody");
    clear(tbody);
    const sel = document.getElementById("agg-select");
    clear(sel);
    if (!aggs.length) {
      const tr = el("tr");
      tr.appendChild(el("td", { colspan: "9", class: "empty-state" }, "This sketch has no profile aggregates."));
      tbody.appendChild(tr);
      destroyChart("agg");
      return;
    }
    if (!aggs.some(a => a.key === state.selectedAgg)) {
      state.selectedAgg = aggs[0].key;
    }
    for (const a of aggs) {
      const opt = el("option", { value: a.key }, a.key + " [" + a.kind + "]");
      if (a.key === state.selectedAgg) opt.selected = true;
      sel.appendChild(opt);

      const tr = el("tr", { class: "clickable" + (a.key === state.selectedAgg ? " selected" : "") });
      tr.addEventListener("click", () => {
        state.selectedAgg = a.key;
        renderAggregatesSection(aggs);
        syncUrlState();
      });
      tr.appendChild(el("td", { class: "mono" }, a.key));
      tr.appendChild(el("td", null, a.kind));
      tr.appendChild(el("td", { class: "num" }, fmtAny(a.global_min)));
      tr.appendChild(el("td", { class: "num" }, fmtAny(a.global_max)));
      tr.appendChild(el("td", { class: "num" }, a.global_sum !== null ? fmtNum(a.global_sum) : "-"));
      tr.appendChild(el("td", { class: "num" }, a.weighted_mean !== null ? fmtNum(a.weighted_mean) : "-"));
      tr.appendChild(el("td", { class: "num" }, a.skit_stats.median !== null ? fmtNum(a.skit_stats.median) : "-"));
      tr.appendChild(el("td", { class: "num" }, a.skit_stats.mean !== null ? fmtNum(a.skit_stats.mean) : "-"));
      tr.appendChild(el("td", { class: "num" }, fmtInt(a.skit_stats.active_skits) + " (" + a.skit_stats.metric + ")"));
      tbody.appendChild(tr);
    }

    const activeAgg = aggs.find(a => a.key === state.selectedAgg);
    renderAggChart(activeAgg);
  }

  function renderAggChart(agg) {
    destroyChart("agg");
    const canvas = document.getElementById("chart-agg");
    const empty = document.getElementById("agg-empty");
    const qStrip = document.getElementById("agg-quantiles");
    const btnEv = document.getElementById("agg-events");
    const btnOut = document.getElementById("agg-outliers");
    const btnHist = document.getElementById("agg-histogram");
    const hasEvHist = Boolean(agg && agg.histogram && agg.histogram.bins.length);
    if (btnEv) {
      btnEv.disabled = !hasEvHist;
      btnEv.title = hasEvHist ? "Per-event distribution merged from HISTOGRAM aggregate" : "Add HISTOGRAM to this aggregate in profile.yaml to enable";
    }
    if (qStrip) {
      clear(qStrip);
      if (hasEvHist) {
        qStrip.style.display = "";
        const h = agg.histogram;
        qStrip.appendChild(el("span", { class: "badge ok" }, "Per-Event HISTOGRAM (" + h.mode + ") · " + fmtInt(h.count) + " values"));
        for (const pKey of ["p50", "p90", "p95", "p99"]) {
          if (h.quantiles[pKey] !== null && h.quantiles[pKey] !== undefined) {
            qStrip.appendChild(el("span", { class: "badge" }, pKey + " ≈ " + fmtNum(h.quantiles[pKey])));
          }
        }
      } else {
        qStrip.style.display = "none";
      }
    }

    const effectiveView = (hasEvHist && (state.aggView === "events" || !agg.outliers.length))
      ? "events"
      : (state.aggView === "events" ? "outliers" : state.aggView);
    if (btnEv) btnEv.classList.toggle("active", effectiveView === "events");
    if (btnOut) btnOut.classList.toggle("active", effectiveView === "outliers");
    if (btnHist) btnHist.classList.toggle("active", effectiveView === "histogram");

    if (!agg || (!agg.outliers.length && !hasEvHist)) {
      canvas.style.display = "none";
      empty.style.display = "";
      empty.textContent = agg ? "No numeric per-skit values for '" + agg.key + "' (" + agg.kind + ") in current filter." : "No aggregate selected.";
      return;
    }
    canvas.style.display = "";
    empty.style.display = "none";
    const tc = themeColors();

    if (effectiveView === "events" && hasEvHist) {
      const h = agg.histogram;
      let cum = 0;
      const cumPcts = h.bins.map(b => { cum += b.count; return Number(((100 * cum) / h.count).toFixed(2)); });
      state.charts.agg = new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: h.bins.map(b => b.label),
          datasets: [
            {
              label: "Event values (" + agg.key + ")",
              data: h.bins.map(b => b.count),
              backgroundColor: tc.accent + "cc",
              borderRadius: 4,
              yAxisID: "y"
            },
            {
              label: "Cumulative %",
              data: cumPcts,
              type: "line",
              borderColor: tc.accent2,
              backgroundColor: tc.accent2,
              borderWidth: 2,
              pointRadius: 2.5,
              tension: 0.15,
              yAxisID: "y1"
            }
          ]
        },
        options: {
          animation: false,
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          scales: {
            x: { ticks: { color: tc.muted, maxRotation: 40 }, grid: { color: tc.border + "44" } },
            y: { beginAtZero: true, ticks: { color: tc.muted }, grid: { color: tc.border + "55" }, title: { display: true, text: "Event Values", color: tc.muted } },
            y1: { beginAtZero: true, max: 100, position: "right", ticks: { color: tc.muted, callback: v => v + "%" }, grid: { drawOnChartArea: false }, title: { display: true, text: "Cumulative %", color: tc.muted } }
          },
          plugins: {
            legend: { labels: { color: tc.text } },
            tooltip: {
              callbacks: {
                afterLabel: ctx => {
                  if (ctx.datasetIndex !== 0) return "";
                  const b = h.bins[ctx.dataIndex];
                  return b ? fmtPct(b.pct) + " of " + fmtInt(h.count) + " values" : "";
                }
              }
            }
          }
        }
      });
      return;
    }

    if (effectiveView === "histogram" && agg.all_values.length >= 2) {
      const min = Math.min(...agg.all_values);
      const max = Math.max(...agg.all_values);
      const bins = Math.min(16, Math.max(4, Math.ceil(Math.sqrt(agg.all_values.length))));
      const span = max - min;
      const counts = new Array(bins).fill(0);
      const labels = [];
      for (let i = 0; i < bins; i++) {
        const lo = min + (span * i) / bins;
        const hi = min + (span * (i + 1)) / bins;
        labels.push(fmtNum(lo, 1) + "–" + fmtNum(hi, 1));
      }
      for (const v of agg.all_values) {
        const idx = span === 0 ? 0 : Math.min(bins - 1, Math.floor(((v - min) / span) * bins));
        counts[idx] += 1;
      }
      state.charts.agg = new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels,
          datasets: [{ label: "Skits per bin (" + agg.key + " " + agg.skit_stats.metric + ")", data: counts, backgroundColor: tc.accent + "cc", borderRadius: 4 }]
        },
        options: {
          animation: false,
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { ticks: { color: tc.muted, maxRotation: 40 }, grid: { color: tc.border + "44" } },
            y: { beginAtZero: true, ticks: { color: tc.muted }, grid: { color: tc.border + "55" }, title: { display: true, text: "Skits", color: tc.muted } }
          },
          plugins: { legend: { labels: { color: tc.text } } }
        }
      });
      return;
    }

    const items = agg.outliers;
    state.charts.agg = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: items.map(x => x.id.slice(0, 8)),
        datasets: [{
          label: agg.key + " (" + agg.skit_stats.metric + ")",
          data: items.map(x => x.value),
          backgroundColor: tc.accent2 + "cc",
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        onClick: (_evt, els) => {
          if (!els.length) return;
          const item = items[els[0].index];
          if (item) {
            state.search = item.id.slice(0, 12);
            document.getElementById("search-input").value = state.search;
            state.expandedIds.add(item.id);
            state.page = 1;
            render();
          }
        },
        scales: {
          x: { beginAtZero: true, ticks: { color: tc.muted }, grid: { color: tc.border + "55" } },
          y: { ticks: { color: tc.text, font: { family: "monospace", size: 11 } }, grid: { display: false } }
        },
        plugins: {
          legend: { labels: { color: tc.text } },
          tooltip: {
            callbacks: {
              afterLabel: ctx => {
                const it = items[ctx.dataIndex];
                return "Skit count: " + fmtInt(it.count) + " | " + Object.entries(it.tokens).filter(([, v]) => v !== "NULL" && v !== "FALSE").slice(0, 3).map(([k, v]) => k + "=" + v).join(", ");
              }
            }
          }
        }
      }
    });
  }

  function renderHistorySection() {
    const runs = DATA.history.runs || [];
    const drift = DATA.history.drift || [];
    const warns = DATA.history.warnings || [];
    const warnBox = document.getElementById("history-warnings");
    clear(warnBox);
    if (warns.length) {
      warnBox.style.display = "";
      warnBox.textContent = warns.join(" | ");
    } else {
      warnBox.style.display = "none";
    }

    const empty = document.getElementById("history-empty");
    const content = document.getElementById("history-content");
    const driftSel = document.getElementById("drift-select");
    if (!runs.length) {
      empty.style.display = "";
      content.style.display = "none";
      driftSel.style.display = "none";
      destroyChart("history");
      return;
    }
    empty.style.display = "none";
    content.style.display = "";

    destroyChart("history");
    const tc = themeColors();
    state.charts.history = new Chart(document.getElementById("chart-history").getContext("2d"), {
      type: "bar",
      data: {
        labels: runs.map(r => r.id),
        datasets: [
          { label: "Events", data: runs.map(r => r.observed_events), backgroundColor: tc.accent + "cc", yAxisID: "y" },
          { label: "Distinct Skits", data: runs.map(r => r.skit_count), type: "line", borderColor: tc.accent2, backgroundColor: tc.accent2, borderWidth: 2, yAxisID: "y1" }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: tc.muted }, grid: { color: tc.border + "44" } },
          y: { beginAtZero: true, ticks: { color: tc.muted }, grid: { color: tc.border + "55" }, title: { display: true, text: "Events", color: tc.muted } },
          y1: { beginAtZero: true, position: "right", ticks: { color: tc.muted }, grid: { drawOnChartArea: false }, title: { display: true, text: "Skits", color: tc.muted } }
        },
        plugins: { legend: { labels: { color: tc.text } } }
      }
    });

    const driftBox = document.getElementById("drift-box");
    clear(driftSel);
    if (!drift.length) {
      driftBox.style.display = "none";
      driftSel.style.display = "none";
      return;
    }
    driftBox.style.display = "";
    driftSel.style.display = "";
    drift.forEach((d, idx) => {
      const opt = el("option", { value: String(idx) }, d.from_run + " -> " + d.to_run + " (+" + d.new_count + " / -" + d.disappeared_count + ")");
      if (idx === state.driftIdx) opt.selected = true;
      driftSel.appendChild(opt);
    });
    const cur = drift[state.driftIdx] || drift[0];
    const badges = document.getElementById("drift-badges");
    clear(badges);
    badges.appendChild(el("span", { class: "badge ok" }, "+" + cur.new_count + " New"));
    badges.appendChild(el("span", { class: "badge danger" }, "-" + cur.disappeared_count + " Disappeared"));
    badges.appendChild(el("span", { class: "badge" }, cur.persisted_count + " Persisted"));

    function fillDrift(tbodyId, rows, mapper) {
      const tb = document.getElementById(tbodyId);
      clear(tb);
      if (!rows.length) {
        const tr = el("tr");
        tr.appendChild(el("td", { colspan: "4", class: "muted" }, "None"));
        tb.appendChild(tr);
        return;
      }
      for (const r of rows) {
        const tr = el("tr");
        for (const [txt, cls] of mapper(r)) tr.appendChild(el("td", { class: cls || "" }, txt));
        tb.appendChild(tr);
      }
    }

    function tokStr(toks) {
      return Object.entries(toks || {}).filter(([, v]) => v !== "NULL" && v !== "FALSE").slice(0, 4).map(([k, v]) => k + "=" + v).join(", ") || "(all NULL/FALSE)";
    }

    fillDrift("drift-new-tbody", cur.new_skits, r => [
      [r.id.slice(0, 10), "mono"], [fmtInt(r.count), "num"], [fmtPct(r.weight_pct), "num"], [tokStr(r.tokens), "mono"]
    ]);
    fillDrift("drift-gone-tbody", cur.disappeared_skits, r => [
      [r.id.slice(0, 10), "mono"], [fmtInt(r.prev_count), "num"], [fmtPct(r.prev_weight_pct), "num"], [tokStr(r.tokens), "mono"]
    ]);
    fillDrift("drift-shift-tbody", cur.top_shifts, r => [
      [r.id.slice(0, 10), "mono"],
      [fmtInt(r.prev_count) + " -> " + fmtInt(r.curr_count), "num"],
      [(r.delta_pct >= 0 ? "+" : "") + r.delta_pct.toFixed(2) + " pp", "num"],
      [tokStr(r.tokens), "mono"]
    ]);
  }

  function sortKey(skit, wm) {
    if (state.sortBy === "weight") return skitWeight(skit, wm);
    if (state.sortBy === "count") return skit.count;
    if (state.sortBy === "first_seen") return skit.first_seen || "";
    if (state.sortBy === "last_seen") return skit.last_seen || "";
    if (state.sortBy.startsWith("agg:")) {
      const k = state.sortBy.slice(4);
      const p = extractPrimaryMetric(skit.aggregates ? skit.aggregates[k] : null);
      return p.val === null || p.val === undefined ? -Infinity : p.val;
    }
    return skitWeight(skit, wm);
  }

  function renderExplorer(skits, totalW, wm) {
    const colHdr = document.getElementById("skits-col-metric");
    if (colHdr) colHdr.textContent = wm.isCount ? "Count" : wm.label;
    const sortOpt = document.getElementById("sort-weight-opt");
    if (sortOpt) sortOpt.textContent = wm.isCount ? "Sort: Weight (Count)" : "Sort: Weight (" + wm.label + ")";

    const sorted = skits.slice().sort((a, b) => {
      const av = sortKey(a, wm), bv = sortKey(b, wm);
      let cmp = av < bv ? -1 : av > bv ? 1 : 0;
      if (cmp === 0) cmp = a.count - b.count;
      if (cmp === 0) cmp = a.id < b.id ? -1 : 1;
      return state.sortDir === "desc" ? -cmp : cmp;
    });
    const totalPages = Math.max(1, Math.ceil(sorted.length / state.pageSize));
    if (state.page > totalPages) state.page = totalPages;
    const start = (state.page - 1) * state.pageSize;
    const pageRows = sorted.slice(start, start + state.pageSize);

    const tbody = document.getElementById("skits-tbody");
    clear(tbody);
    if (!pageRows.length) {
      const tr = el("tr");
      tr.appendChild(el("td", { colspan: "7", class: "empty-state" }, "No skits match the current filters."));
      tbody.appendChild(tr);
    }

    let running = sorted.slice(0, start).reduce((s, r) => s + skitWeight(r, wm), 0);
    for (const s of pageRows) {
      const w = skitWeight(s, wm);
      running += w;
      const wPct = totalW ? (100 * w) / totalW : 0;
      const cPct = totalW ? (100 * running) / totalW : 0;
      const tr = el("tr");

      const idTd = el("td", { class: "mono", style: "white-space:nowrap" });
      idTd.appendChild(el("span", { title: s.id }, s.id.slice(0, 10) + " "));
      const cpBtn = el("button", { type: "button", class: "small", title: "Copy full skit ID" }, "Copy");
      cpBtn.addEventListener("click", () => {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(s.id).then(() => { cpBtn.textContent = "Copied"; setTimeout(() => { cpBtn.textContent = "Copy"; }, 1200); });
        }
      });
      idTd.appendChild(cpBtn);
      tr.appendChild(idTd);

      const metricTd = el("td", { class: "num", title: wm.isCount ? "" : (fmtInt(s.count) + " observations") }, fmtWeight(w, wm));
      tr.appendChild(metricTd);
      tr.appendChild(el("td", { class: "num" }, fmtPct(wPct)));
      tr.appendChild(el("td", { class: "num" }, fmtPct(cPct)));
      tr.appendChild(el("td", { class: "mono", style: "white-space:nowrap" }, fmtAny(s.first_seen) + " / " + fmtAny(s.last_seen)));

      const tokTd = el("td");
      const entries = Object.entries(s.tokens);
      const shown = state.showAllTokens ? entries : entries.filter(([, v]) => v !== "NULL" && v !== "FALSE");
      const list = shown.length ? shown : entries.slice(0, 4);
      for (const [k, v] of list) {
        const pill = el("span", { class: "token-pill", title: k + " = " + v }, k + "=" + v);
        pill.style.cursor = "pointer";
        pill.addEventListener("click", () => toggleFieldFilter(k, v));
        tokTd.appendChild(pill);
      }
      tr.appendChild(tokTd);

      const actTd = el("td", { style: "white-space:nowrap" });
      const expanded = state.expandedIds.has(s.id);
      const expBtn = el("button", { type: "button", class: "small" }, expanded ? "Hide" : "Inspect");
      expBtn.addEventListener("click", () => {
        if (state.expandedIds.has(s.id)) state.expandedIds.delete(s.id);
        else state.expandedIds.add(s.id);
        renderExplorer(skits, totalW, wm);
      });
      actTd.appendChild(expBtn);
      tr.appendChild(actTd);
      tbody.appendChild(tr);

      if (expanded) {
        const detTr = el("tr");
        const detTd = el("td", { colspan: "7" });
        const box = el("div", { class: "sample-box" });
        box.appendChild(el("div", { class: "mono", style: "font-size:12px" }, "Full ID: " + s.id));
        box.appendChild(el("div", { class: "mono muted", style: "font-size:12px;margin-top:2px" }, "Sample locator: " + s.sample_locator));
        box.appendChild(el("h3", { style: "margin-top:10px" }, "All Tokens"));
        box.appendChild(el("pre", { class: "json-pre" }, JSON.stringify(s.tokens, null, 2)));
        if (s.aggregates && Object.keys(s.aggregates).length) {
          box.appendChild(el("h3", { style: "margin-top:10px" }, "Aggregates"));
          box.appendChild(el("pre", { class: "json-pre" }, JSON.stringify(s.aggregates, null, 2)));
        }
        box.appendChild(el("h3", { style: "margin-top:10px" }, "Retained First Record"));
        box.appendChild(el("pre", { class: "json-pre" }, s.first_record !== null ? JSON.stringify(s.first_record, null, 2) : "(no retained first record)"));
        if (s.last_record !== null) {
          box.appendChild(el("h3", { style: "margin-top:10px" }, "Retained Last Record (distinct)"));
          box.appendChild(el("pre", { class: "json-pre" }, JSON.stringify(s.last_record, null, 2)));
        }
        detTd.appendChild(box);
        detTr.appendChild(detTd);
        tbody.appendChild(detTr);
      }
    }

    document.getElementById("pager-info").textContent =
      "Page " + state.page + " of " + totalPages + " (" + fmtInt(sorted.length) + " filtered skits)";
    document.getElementById("prev-page").disabled = state.page <= 1;
    document.getElementById("next-page").disabled = state.page >= totalPages;
  }

  function computeAblation(skits) {
    const keys = DATA.fields.map(f => f.key);
    const totalSkits = skits.length;
    if (!totalSkits || !keys.length) return [];
    const totalSingletons = skits.reduce((n, s) => n + (s.count === 1 ? 1 : 0), 0);
    const results = keys.map(dropKey => {
      const otherKeys = keys.filter(k => k !== dropKey);
      const grouped = new Map();
      const allVals = new Set();
      const nonSingletonVals = new Set();
      for (const s of skits) {
        const val = Object.prototype.hasOwnProperty.call(s.tokens, dropKey) ? s.tokens[dropKey] : "NULL";
        allVals.add(val);
        if (s.count > 1) nonSingletonVals.add(val);
        const parts = [];
        for (const k of otherKeys) {
          const ov = Object.prototype.hasOwnProperty.call(s.tokens, k) ? s.tokens[k] : "NULL";
          parts.push(ov.length + ":" + ov);
        }
        const compKey = parts.join("|");
        grouped.set(compKey, (grouped.get(compKey) || 0) + s.count);
      }
      let remainingSingletons = 0;
      for (const cnt of grouped.values()) {
        if (cnt === 1) remainingSingletons += 1;
      }
      let singletonOnly = 0;
      for (const v of allVals) {
        if (!nonSingletonVals.has(v)) singletonOnly += 1;
      }
      const remainingSkits = grouped.size;
      const skitsCollapsed = totalSkits - remainingSkits;
      const singletonsRemoved = totalSingletons - remainingSingletons;
      return {
        key: dropKey,
        cardinality: allVals.size,
        singleton_only_values: singletonOnly,
        skits_collapsed: skitsCollapsed,
        skits_collapsed_pct: totalSkits ? (100 * skitsCollapsed) / totalSkits : null,
        singletons_removed: singletonsRemoved,
        singletons_removed_pct: totalSingletons ? (100 * singletonsRemoved) / totalSingletons : null,
        remaining_skits: remainingSkits,
        remaining_singletons: remainingSingletons
      };
    });
    results.sort((a, b) =>
      (b.skits_collapsed - a.skits_collapsed) ||
      (b.singletons_removed - a.singletons_removed) ||
      (a.key < b.key ? -1 : a.key > b.key ? 1 : 0)
    );
    return results;
  }

  function renderAblationSection(ablation, fields) {
    destroyChart("ablation");
    const tbody = document.getElementById("ablation-tbody");
    clear(tbody);
    const canvas = document.getElementById("chart-ablation");
    const empty = document.getElementById("ablation-empty");
    if (!ablation.length) {
      const tr = el("tr");
      tr.appendChild(el("td", { colspan: "7", class: "empty-state" }, "No fields to ablate in the current filter."));
      tbody.appendChild(tr);
      canvas.style.display = "none";
      empty.style.display = "";
      return;
    }
    canvas.style.display = "";
    empty.style.display = "none";

    for (const r of ablation) {
      const tr = el("tr", { class: "clickable" });
      tr.addEventListener("click", () => {
        state.selectedField = r.key;
        renderFieldsSection(fields);
        syncUrlState();
        document.getElementById("field-select").scrollIntoView({ behavior: "smooth", block: "center" });
      });
      tr.appendChild(el("td", { class: "mono" }, r.key));
      tr.appendChild(el("td", { class: "num" }, fmtInt(r.cardinality)));
      tr.appendChild(el("td", { class: "num" }, fmtInt(r.singleton_only_values)));
      const skTxt = r.skits_collapsed > 0
        ? "-" + fmtInt(r.skits_collapsed) + " (" + fmtPct(r.skits_collapsed_pct) + ")"
        : "0";
      const sgTxt = r.singletons_removed > 0
        ? "-" + fmtInt(r.singletons_removed) + " (" + fmtPct(r.singletons_removed_pct) + ")"
        : "0";
      tr.appendChild(el("td", { class: "num" }, skTxt));
      tr.appendChild(el("td", { class: "num" }, sgTxt));
      tr.appendChild(el("td", { class: "num" }, fmtInt(r.remaining_skits)));
      tr.appendChild(el("td", { class: "num" }, fmtInt(r.remaining_singletons)));
      tbody.appendChild(tr);
    }

    const nonZero = ablation.filter(r => r.skits_collapsed > 0 || r.singletons_removed > 0);
    const chartRows = (nonZero.length ? nonZero : ablation).slice(0, 15);
    const tc = themeColors();
    state.charts.ablation = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: chartRows.map(r => r.key),
        datasets: [
          {
            label: "Skits Collapsed",
            data: chartRows.map(r => r.skits_collapsed),
            backgroundColor: tc.accent + "cc",
            borderRadius: 4
          },
          {
            label: "Singletons Removed",
            data: chartRows.map(r => r.singletons_removed),
            backgroundColor: "#d29922cc",
            borderRadius: 4
          }
        ]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        onClick: (_evt, els) => {
          if (!els.length) return;
          const row = chartRows[els[0].index];
          if (row) {
            state.selectedField = row.key;
            renderFieldsSection(fields);
            syncUrlState();
          }
        },
        scales: {
          x: { beginAtZero: true, ticks: { color: tc.muted }, grid: { color: tc.border + "55" }, title: { display: true, text: "Count collapsed if field omitted", color: tc.muted } },
          y: { ticks: { color: tc.text, font: { family: "monospace", size: 11 } }, grid: { display: false } }
        },
        plugins: {
          legend: { labels: { color: tc.text } },
          tooltip: {
            callbacks: {
              afterLabel: ctx => {
                const r = chartRows[ctx.dataIndex];
                return "Remaining: " + fmtInt(r.remaining_skits) + " skits (" + fmtInt(r.remaining_singletons) + " singletons)";
              }
            }
          }
        }
      }
    });
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

  function entropyMap(countsMap) {
    let total = 0;
    for (const c of countsMap.values()) total += c;
    if (total <= 0) return 0;
    let h = 0;
    for (const c of countsMap.values()) {
      if (c > 0) {
        const p = c / total;
        h -= p * Math.log2(p);
      }
    }
    return h;
  }

  function computeCorrelations(skits, totalW, wm) {
    const keys = DATA.fields.map(f => f.key);
    if (!skits.length || !totalW || keys.length < 2) {
      return { fields: [], cramers: new Map(), theils: new Map(), redundant_with: new Map(), determined_by: new Map(), items: [], edges: [] };
    }
    const marginals = new Map();
    const ent = new Map();
    for (const f of keys) {
      const m = new Map();
      for (const s of skits) {
        const w = skitWeight(s, wm);
        if (w <= 0) continue;
        const v = Object.prototype.hasOwnProperty.call(s.tokens, f) ? s.tokens[f] : "NULL";
        m.set(v, (m.get(v) || 0) + w);
      }
      marginals.set(f, m);
      ent.set(f, entropyMap(m));
    }
    const cramers = new Map();
    const theils = new Map();
    for (const f of keys) {
      cramers.set(f, new Map([[f, 1]]));
      theils.set(f, new Map([[f, 1]]));
    }
    for (let i = 0; i < keys.length; i++) {
      const f1 = keys[i], m1 = marginals.get(f1), e1 = ent.get(f1);
      for (let j = i + 1; j < keys.length; j++) {
        const f2 = keys[j], m2 = marginals.get(f2), e2 = ent.get(f2);
        const joint = new Map();
        for (const s of skits) {
          const w = skitWeight(s, wm);
          if (w <= 0) continue;
          const v1 = Object.prototype.hasOwnProperty.call(s.tokens, f1) ? s.tokens[f1] : "NULL";
          const v2 = Object.prototype.hasOwnProperty.call(s.tokens, f2) ? s.tokens[f2] : "NULL";
          const jk = v1.length + ":" + v1 + "|" + v2;
          joint.set(jk, [v1, v2, (joint.has(jk) ? joint.get(jk)[2] : 0) + w]);
        }
        let chi2 = -totalW;
        const jCounts = new Map();
        for (const [jk, [v1, v2, obs]] of joint.entries()) {
          const exp = (m1.get(v1) * m2.get(v2)) / totalW;
          if (exp > 0) chi2 += (obs * obs) / exp;
          jCounts.set(jk, obs);
        }
        chi2 = Math.max(0, chi2);
        const k = Math.min(m1.size, m2.size) - 1;
        const v = k > 0 ? Math.min(1, Math.sqrt(chi2 / (totalW * k))) : 0;
        const mi = Math.max(0, e1 + e2 - entropyMap(jCounts));
        const u12 = e2 > 1e-12 ? Math.min(1, mi / e2) : 0;
        const u21 = e1 > 1e-12 ? Math.min(1, mi / e1) : 0;
        cramers.get(f1).set(f2, v); cramers.get(f2).set(f1, v);
        theils.get(f1).set(f2, u12); theils.get(f2).set(f1, u21);
      }
    }
    const redundant_with = new Map();
    const determined_by = new Map();
    for (const f1 of keys) {
      const rw = [], db = [];
      if (ent.get(f1) > 1e-12) {
        for (const f2 of keys) {
          if (f1 === f2 || ent.get(f2) <= 1e-12) continue;
          if (theils.get(f2).get(f1) >= 0.99) {
            if (theils.get(f1).get(f2) >= 0.99) rw.push(f2);
            else db.push(f2);
          }
        }
      }
      redundant_with.set(f1, rw);
      determined_by.set(f1, db);
    }

    const minSup = wm.isCount
      ? (totalW >= 500 ? 5 : (totalW >= 10 ? 2 : 1))
      : Math.max(1e-9, totalW * 0.00025);
    const items = [];
    const skitMaps = new Map();
    for (const f of keys) {
      for (const [v, cnt] of marginals.get(f).entries()) {
        if (v === "NULL" || v === "FALSE" || cnt < minSup) continue;
        const id = f + "=" + v;
        items.push({ id, field: f, value: v, count: cnt, pct: (100 * cnt) / totalW });
        const sm = new Map();
        for (let idx = 0; idx < skits.length; idx++) {
          const w = skitWeight(skits[idx], wm);
          if (w <= 0) continue;
          const sv = Object.prototype.hasOwnProperty.call(skits[idx].tokens, f) ? skits[idx].tokens[f] : "NULL";
          if (sv === v) sm.set(idx, w);
        }
        skitMaps.set(id, sm);
      }
    }
    const edges = [];
    for (let i = 0; i < items.length; i++) {
      const a = items[i], sa = skitMaps.get(a.id);
      for (let j = i + 1; j < items.length; j++) {
        const b = items[j];
        if (a.field === b.field) continue;
        const sb = skitMaps.get(b.id);
        let n11 = 0;
        for (const [idx, c] of sa.entries()) { if (sb.has(idx)) n11 += c; }
        const n10 = a.count - n11, n01 = b.count - n11, n00 = totalW - a.count - b.count + n11;
        const denom = Math.sqrt(Math.max(0, a.count * (totalW - a.count) * b.count * (totalW - b.count)));
        const phi = denom > 0 ? (n11 * n00 - n10 * n01) / denom : 0;
        const lift = (a.count > 0 && b.count > 0) ? (n11 * totalW) / (a.count * b.count) : 0;
        const keepPos = n11 >= minSup && (Math.abs(phi) >= 0.05 || lift >= 1.5);
        const keepNeg = n11 === 0 && Math.abs(phi) >= 0.10;
        if (!keepPos && !keepNeg) continue;
        edges.push({
          a: a.id, b: b.id, fa: a.field, va: a.value, fb: b.field, vb: b.value,
          n11, support_pct: (100 * n11) / totalW,
          conf_ab: (100 * n11) / a.count, conf_ba: (100 * n11) / b.count,
          lift, phi
        });
      }
    }
    edges.sort((x, y) => (Math.abs(y.phi) - Math.abs(x.phi)) || (y.n11 - x.n11));
    return { fields: keys, cramers, theils, redundant_with, determined_by, items, edges: edges.slice(0, 250) };
  }

  function filterCorrEdges(corr) {
    return corr.edges.filter(e => {
      const ap = Math.abs(e.phi);
      if (ap < state.corrMinPhi) return false;
      if (state.corrHideLocks && ap >= 0.95) return false;
      if (state.corrSign === "pos" && e.phi < 0) return false;
      if (state.corrSign === "neg" && e.phi > 0) return false;
      return true;
    });
  }

  function findPositiveClusters(edges) {
    const adj = new Map();
    for (const e of edges) {
      if (e.phi <= 0) continue;
      if (!adj.has(e.a)) adj.set(e.a, []);
      if (!adj.has(e.b)) adj.set(e.b, []);
      adj.get(e.a).push(e.b);
      adj.get(e.b).push(e.a);
    }
    const seen = new Set();
    const clusters = [];
    for (const node of adj.keys()) {
      if (seen.has(node)) continue;
      const comp = [], q = [node];
      seen.add(node);
      while (q.length) {
        const cur = q.shift();
        comp.push(cur);
        for (const nb of (adj.get(cur) || [])) {
          if (!seen.has(nb)) { seen.add(nb); q.push(nb); }
        }
      }
      const cSet = new Set(comp);
      const cEdges = edges.filter(e => e.phi > 0 && cSet.has(e.a) && cSet.has(e.b));
      clusters.push({
        nodes: comp,
        edges: cEdges,
        maxPhi: Math.max(...cEdges.map(e => e.phi)),
        maxLift: Math.max(...cEdges.map(e => e.lift))
      });
    }
    clusters.sort((a, b) => (b.nodes.length - a.nodes.length) || (b.maxPhi - a.maxPhi));
    return clusters;
  }

  function renderCorrNetwork(corr, wm) {
    const svg = document.getElementById("corr-net-svg");
    clear(svg);
    const edges = filterCorrEdges(corr);
    const itemMap = new Map(corr.items.map(it => [it.id, it]));
    const nodeIds = new Set();
    for (const e of edges) { nodeIds.add(e.a); nodeIds.add(e.b); }
    const clusters = findPositiveClusters(edges);
    const clusterOf = new Map();
    clusters.forEach((c, idx) => c.nodes.forEach(n => clusterOf.set(n, idx)));

    const ordered = [];
    clusters.forEach(c => c.nodes.forEach(n => ordered.push(n)));
    for (const n of nodeIds) { if (!clusterOf.has(n)) ordered.push(n); }

    document.getElementById("corr-net-summary").textContent =
      ordered.length + " active tokens · " + edges.length + " links · " + clusters.length + " positive cluster(s)" +
      (wm.isCount ? "" : " · weighted by " + wm.label);

    if (!ordered.length) {
      svg.appendChild(svgEl("text", { x: 460, y: 210, "text-anchor": "middle", fill: "var(--muted)", "font-size": 13 },
        "No token pairs pass the current |φ| threshold. Lower the slider or uncheck Hide 1:1 locks."));
      return;
    }

    const cx = 460, cy = 210, rx = 310, ry = 148;
    const negDeg = new Map();
    for (const e of edges) {
      if (e.phi < 0) {
        negDeg.set(e.a, (negDeg.get(e.a) || 0) + 1);
        negDeg.set(e.b, (negDeg.get(e.b) || 0) + 1);
      }
    }
    const hubs = ordered.filter(n => !clusterOf.has(n) && (negDeg.get(n) || 0) >= 3);
    const ring = ordered.filter(n => !hubs.includes(n));
    const pos = new Map();
    hubs.forEach((n, i) => {
      const a = (2 * Math.PI * i) / Math.max(1, hubs.length);
      pos.set(n, { x: cx + (hubs.length > 1 ? 45 * Math.cos(a) : 0), y: cy + (hubs.length > 1 ? 45 * Math.sin(a) : 0) });
    });
    ring.forEach((n, i) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(1, ring.length);
      pos.set(n, { x: cx + rx * Math.cos(angle), y: cy + ry * Math.sin(angle), angle });
    });

    const sel = state.corrSelectedNode && nodeIds.has(state.corrSelectedNode) ? state.corrSelectedNode : null;
    const connected = new Set();
    if (sel) {
      connected.add(sel);
      for (const e of edges) {
        if (e.a === sel) connected.add(e.b);
        if (e.b === sel) connected.add(e.a);
      }
    }

    function showEdgeInspector(e) {
      const box = document.getElementById("corr-net-inspector");
      clear(box);
      const top = el("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap" });
      top.appendChild(el("strong", { class: "mono" }, e.a + (e.phi >= 0 ? "  <->  " : "  (repels)  ") + e.b));
      const fBtn = el("button", { type: "button", class: "small" }, "Filter dashboard to pair");
      fBtn.addEventListener("click", () => {
        state.fieldFilters.set(e.fa, new Set([e.va]));
        state.fieldFilters.set(e.fb, new Set([e.vb]));
        state.page = 1;
        render();
      });
      top.appendChild(fBtn);
      box.appendChild(top);
      const row = el("div", { style: "margin-top:6px;display:flex;flex-wrap:wrap;gap:6px" });
      row.appendChild(el("span", { class: "badge " + (e.phi >= 0 ? "ok" : "danger") }, "φ = " + (e.phi >= 0 ? "+" : "") + e.phi.toFixed(3)));
      row.appendChild(el("span", { class: "badge" }, "Lift " + e.lift.toFixed(2) + "x"));
      row.appendChild(el("span", { class: "badge" }, "Support " + fmtWeight(e.n11, wm) + " (" + e.support_pct.toFixed(1) + "%)"));
      row.appendChild(el("span", { class: "badge" }, "P(B|A) " + e.conf_ab.toFixed(1) + "%"));
      row.appendChild(el("span", { class: "badge" }, "P(A|B) " + e.conf_ba.toFixed(1) + "%"));
      box.appendChild(row);
    }

    function showNodeInspector(nId) {
      const info = itemMap.get(nId);
      const links = edges.filter(e => e.a === nId || e.b === nId).sort((a, b) => Math.abs(b.phi) - Math.abs(a.phi));
      const box = document.getElementById("corr-net-inspector");
      clear(box);
      const top = el("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap" });
      top.appendChild(el("strong", { class: "mono" }, nId + (info ? " — " + fmtWeight(info.count, wm) + " " + wm.shortLabel + " (" + fmtPct(info.pct) + ")" : "")));
      if (info) {
        const fBtn = el("button", { type: "button", class: "small" }, "Toggle filter: " + shortTokenLabel(info.field, info.value));
        fBtn.addEventListener("click", () => toggleFieldFilter(info.field, info.value));
        top.appendChild(fBtn);
      }
      box.appendChild(top);
      const row = el("div", { style: "margin-top:6px;display:flex;flex-wrap:wrap;gap:6px" });
      for (const e of links.slice(0, 8)) {
        const of = e.a === nId ? e.fb : e.fa;
        const ov = e.a === nId ? e.vb : e.va;
        const conf = e.a === nId ? e.conf_ab : e.conf_ba;
        row.appendChild(el("span", { class: "badge " + (e.phi >= 0 ? "ok" : "danger") },
          (e.phi >= 0 ? "+" : "") + e.phi.toFixed(2) + " " + shortTokenLabel(of, ov) + " (Lift " + e.lift.toFixed(1) + "x, " + conf.toFixed(0) + "%)"));
      }
      box.appendChild(row);
    }

    for (const e of edges) {
      const p1 = pos.get(e.a), p2 = pos.get(e.b);
      if (!p1 || !p2) continue;
      const isHi = !sel || (e.a === sel || e.b === sel);
      const mx = (p1.x + p2.x) / 2 * 0.78 + cx * 0.22;
      const my = (p1.y + p2.y) / 2 * 0.78 + cy * 0.22;
      const cIdx = clusterOf.has(e.a) ? clusterOf.get(e.a) % PALETTE.length : 0;
      const stroke = e.phi >= 0 ? PALETTE[cIdx] : "#f85149";
      const sw = Math.max(1.3, Math.min(5.5, Math.abs(e.phi) * 6.5));
      const path = svgEl("path", {
        d: "M " + p1.x.toFixed(1) + " " + p1.y.toFixed(1) + " Q " + mx.toFixed(1) + " " + my.toFixed(1) + " " + p2.x.toFixed(1) + " " + p2.y.toFixed(1),
        fill: "none", stroke, "stroke-width": sw.toFixed(1),
        "stroke-opacity": isHi ? (sel ? "0.9" : "0.62") : "0.10",
        "stroke-dasharray": e.phi < 0 ? "5 4" : "none",
        style: "cursor:pointer"
      });
      path.addEventListener("mouseenter", () => showEdgeInspector(e));
      path.addEventListener("click", () => showEdgeInspector(e));
      svg.appendChild(path);
    }

    for (const n of ordered) {
      const p = pos.get(n);
      const info = itemMap.get(n);
      const r = Math.max(6, Math.min(18, 4.5 + Math.sqrt((info ? info.pct : 1)) * 1.45));
      const cIdx = clusterOf.has(n) ? clusterOf.get(n) % PALETTE.length : null;
      const fill = cIdx !== null ? PALETTE[cIdx] : "#f85149";
      const isHi = !sel || connected.has(n);
      const g = svgEl("g", { style: "cursor:pointer", opacity: isHi ? "1" : "0.22" });
      g.appendChild(svgEl("circle", {
        cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: r.toFixed(1),
        fill, stroke: sel === n ? "var(--text)" : "var(--surface)",
        "stroke-width": sel === n ? "2.5" : "1.8"
      }));
      const lbl = info ? shortTokenLabel(info.field, info.value) : n;
      let lx = p.x, ly = p.y - r - 6, anchor = "middle";
      if (p.angle !== undefined) {
        const ca = Math.cos(p.angle), sa = Math.sin(p.angle);
        lx = p.x + ca * (r + 8);
        ly = p.y + sa * (r + 10) + 3;
        anchor = ca > 0.25 ? "start" : ca < -0.25 ? "end" : "middle";
      }
      g.appendChild(svgEl("text", {
        x: lx.toFixed(1), y: ly.toFixed(1), "text-anchor": anchor,
        fill: "var(--text)", "font-size": 11, "font-family": "monospace"
      }, lbl));
      g.addEventListener("click", () => {
        state.corrSelectedNode = state.corrSelectedNode === n ? null : n;
        renderCorrNetwork(corr, wm);
        showNodeInspector(n);
      });
      g.addEventListener("mouseenter", () => { if (!state.corrSelectedNode) showNodeInspector(n); });
      svg.appendChild(g);
    }
  }

  function renderCorrHeatmap(corr) {
    const svg = document.getElementById("corr-heat-svg");
    clear(svg);
    const fields = corr.fields;
    if (fields.length < 2) {
      svg.appendChild(svgEl("text", { x: 300, y: 80, fill: "var(--muted)", "font-size": 13 }, "Need at least 2 fields for a correlation matrix."));
      return;
    }
    const n = fields.length;
    const cell = Math.max(18, Math.min(28, Math.floor(540 / n)));
    const leftPad = 120, topPad = 100;
    const width = leftPad + n * cell + 24;
    const height = topPad + n * cell + 16;
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.style.height = Math.min(540, height) + "px";

    const mat = state.corrMatMetric === "theils" ? corr.theils : corr.cramers;
    const tc = themeColors();

    for (let i = 0; i < n; i++) {
      svg.appendChild(svgEl("text", {
        x: leftPad - 6, y: topPad + i * cell + cell * 0.68,
        "text-anchor": "end", fill: "var(--muted)", "font-size": 10.5, "font-family": "monospace"
      }, shortFieldName(fields[i])));
      const tx = leftPad + i * cell + cell * 0.55;
      const ty = topPad - 6;
      svg.appendChild(svgEl("text", {
        x: tx, y: ty, transform: "rotate(-45 " + tx + " " + ty + ")",
        "text-anchor": "start", fill: "var(--muted)", "font-size": 10.5, "font-family": "monospace"
      }, shortFieldName(fields[i])));
    }

    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) {
        const f1 = fields[r], f2 = fields[c];
        const val = mat.get(f1).get(f2);
        const isDiag = r === c;
        const rect = svgEl("rect", {
          x: leftPad + c * cell + 1, y: topPad + r * cell + 1,
          width: cell - 2, height: cell - 2, rx: 3,
          fill: isDiag ? "var(--surface-2)" : (val >= 0.95 ? tc.accent2 : tc.accent),
          "fill-opacity": isDiag ? "1" : Math.max(0.06, val).toFixed(2),
          stroke: "var(--border)", "stroke-width": 0.5, style: "cursor:pointer"
        });
        rect.addEventListener("mouseenter", () => {
          const box = document.getElementById("corr-heat-inspector");
          clear(box);
          box.appendChild(el("strong", { class: "mono" }, f1 + "  ->  " + f2));
          const row = el("div", { style: "margin-top:6px;display:flex;flex-wrap:wrap;gap:6px" });
          row.appendChild(el("span", { class: "badge" }, "Cramér's V = " + corr.cramers.get(f1).get(f2).toFixed(3)));
          row.appendChild(el("span", { class: "badge ok" }, "Theil's U(" + f2 + " | " + f1 + ") = " + corr.theils.get(f1).get(f2).toFixed(3)));
          row.appendChild(el("span", { class: "badge" }, "Theil's U(" + f1 + " | " + f2 + ") = " + corr.theils.get(f2).get(f1).toFixed(3)));
          box.appendChild(row);
        });
        svg.appendChild(rect);
        if (!isDiag && val >= 0.2) {
          svg.appendChild(svgEl("text", {
            x: leftPad + c * cell + cell / 2, y: topPad + r * cell + cell * 0.68,
            "text-anchor": "middle", fill: val >= 0.55 ? "#0f1117" : "var(--text)",
            "font-size": 9, "font-family": "monospace", "pointer-events": "none"
          }, val >= 0.995 ? "1" : val.toFixed(1).replace("0.", ".")));
        }
      }
    }
  }

  function renderCorrClustersTab(corr, wm) {
    const edges = filterCorrEdges(corr);
    const itemMap = new Map(corr.items.map(it => [it.id, it]));
    const clusters = findPositiveClusters(edges);
    const grid = document.getElementById("corr-clusters-grid");
    clear(grid);
    if (!clusters.length) {
      grid.appendChild(el("div", { class: "empty-state" }, "No positive clusters at current |φ| threshold."));
    }
    clusters.forEach((c, idx) => {
      const card = el("div", { class: "cluster-card", style: "border-left-color:" + PALETTE[idx % PALETTE.length] });
      const hdr = el("div", { class: "cluster-hdr" });
      hdr.appendChild(el("span", null, "Cluster " + (idx + 1) + " (" + c.nodes.length + " tokens · max φ +" + c.maxPhi.toFixed(2) + ")"));
      const fBtn = el("button", { type: "button", class: "small" }, "Filter");
      fBtn.addEventListener("click", () => {
        for (const n of c.nodes) {
          const it = itemMap.get(n);
          if (it) {
            let s = state.fieldFilters.get(it.field);
            if (!s) { s = new Set(); state.fieldFilters.set(it.field, s); }
            s.add(it.value);
          }
        }
        state.page = 1;
        render();
      });
      hdr.appendChild(fBtn);
      card.appendChild(hdr);
      for (const n of c.nodes) {
        const it = itemMap.get(n);
        const pctLbl = it ? (it.pct > 0 && it.pct < 0.1 ? "<0.1%" : it.pct.toFixed(1) + "%") : "";
        const pill = el("span", { class: "token-pill", style: "cursor:pointer", title: n },
          (it ? shortTokenLabel(it.field, it.value) + " (" + pctLbl + ")" : n));
        if (it) pill.addEventListener("click", () => toggleFieldFilter(it.field, it.value));
        card.appendChild(pill);
      }
      grid.appendChild(card);
    });

    const tb = document.getElementById("corr-pairs-tbody");
    clear(tb);
    if (!edges.length) {
      const tr = el("tr");
      tr.appendChild(el("td", { colspan: "7", class: "empty-state" }, "No correlated pairs at current threshold."));
      tb.appendChild(tr);
      return;
    }
    for (const e of edges.slice(0, 40)) {
      const tr = el("tr", { class: "clickable" });
      tr.addEventListener("click", () => {
        state.fieldFilters.set(e.fa, new Set([e.va]));
        state.fieldFilters.set(e.fb, new Set([e.vb]));
        state.page = 1;
        render();
      });
      tr.appendChild(el("td", { class: "mono" }, shortTokenLabel(e.fa, e.va)));
      tr.appendChild(el("td", { class: "mono" }, shortTokenLabel(e.fb, e.vb)));
      tr.appendChild(el("td", { class: "num" }, (e.phi >= 0 ? "+" : "") + e.phi.toFixed(3)));
      tr.appendChild(el("td", { class: "num" }, e.lift.toFixed(2) + "x"));
      tr.appendChild(el("td", { class: "num" }, fmtWeight(e.n11, wm) + " (" + e.support_pct.toFixed(1) + "%)"));
      tr.appendChild(el("td", { class: "num" }, e.conf_ab.toFixed(1) + "%"));
      tr.appendChild(el("td", { class: "num" }, e.conf_ba.toFixed(1) + "%"));
      tb.appendChild(tr);
    }
  }

  function renderCorrelations(corr, wm) {
    if (state.corrTab === "network") renderCorrNetwork(corr, wm);
    else if (state.corrTab === "heatmap") renderCorrHeatmap(corr);
    else renderCorrClustersTab(corr, wm);
  }

  function pickDefaultSankeyFields(fields, ablation) {
    const nonConst = fields.filter(f => !f.is_constant);
    const ranked = ablation.map(a => a.key).filter(k => nonConst.some(f => f.key === k));
    const chosen = [];
    for (const k of ranked) {
      const f = fields.find(x => x.key === k);
      if (f && f.redundant_with && f.redundant_with.some(r => chosen.includes(r))) continue;
      chosen.push(k);
      if (chosen.length === 3) break;
    }
    for (const f of nonConst) {
      if (!chosen.includes(f.key) && chosen.length < 3) chosen.push(f.key);
    }
    return chosen;
  }

  function syncSankeySelectors(fields, ablation) {
    const keys = fields.map(f => f.key);
    if (!state.sankeyFields.length || !state.sankeyFields.every(k => !k || keys.includes(k))) {
      const defs = pickDefaultSankeyFields(fields, ablation);
      state.sankeyFields = [defs[0] || "", defs[1] || "", defs[2] || ""];
    }
    const ids = ["sankey-f1", "sankey-f2", "sankey-f3"];
    ids.forEach((id, idx) => {
      const sel = document.getElementById(id);
      clear(sel);
      if (idx === 2) sel.appendChild(el("option", { value: "" }, "(None — 2 stages)"));
      for (const f of fields) {
        const opt = el("option", { value: f.key }, f.key + " (" + f.cardinality + ")");
        if (state.sankeyFields[idx] === f.key) opt.selected = true;
        sel.appendChild(opt);
      }
    });
  }

  function renderSankey(skits, totalW, wm) {
    const svg = document.getElementById("sankey-svg");
    clear(svg);
    const stages = state.sankeyFields.filter(Boolean);
    const uniqueStages = [];
    for (const s of stages) { if (!uniqueStages.includes(s)) uniqueStages.push(s); }
    if (uniqueStages.length < 2 || !skits.length || !totalW) {
      svg.appendChild(svgEl("text", { x: 460, y: 170, "text-anchor": "middle", fill: "var(--muted)", "font-size": 13 },
        "Select at least 2 distinct fields with positive weight to render a Sankey flow."));
      return;
    }

    const MAX_NODES = 8;
    const W = 920, H = 360, topY = 34, botPad = 18, usableH = H - topY - botPad;
    const nodeW = 16, gap = 7;
    const colXs = uniqueStages.length === 2 ? [150, 750] : [130, 452, 774];

    // Roll up each stage to top MAX_NODES values + Other
    const stageTopSets = [];
    const stageNodes = [];
    for (let si = 0; si < uniqueStages.length; si++) {
      const fk = uniqueStages[si];
      const counts = new Map();
      for (const s of skits) {
        const w = skitWeight(s, wm);
        if (w <= 0) continue;
        const v = Object.prototype.hasOwnProperty.call(s.tokens, fk) ? s.tokens[fk] : "NULL";
        counts.set(v, (counts.get(v) || 0) + w);
      }
      const sorted = Array.from(counts.entries()).sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1));
      const top = sorted.slice(0, MAX_NODES);
      const rest = sorted.slice(MAX_NODES);
      const topSet = new Set(top.map(x => x[0]));
      stageTopSets.push(topSet);
      const list = top.map(([v, c]) => ({ key: v, label: v, count: c, isOther: false }));
      if (rest.length) {
        list.push({ key: "__OTHER__", label: "Other (" + rest.length + ")", count: rest.reduce((a, x) => a + x[1], 0), isOther: true });
      }
      stageNodes.push(list);
    }

    // Position nodes vertically in each column
    const nodePos = [];
    for (let si = 0; si < uniqueStages.length; si++) {
      const list = stageNodes[si];
      const totalGap = Math.max(0, list.length - 1) * gap;
      const availH = Math.max(60, usableH - totalGap);
      let y = topY;
      const posMap = new Map();
      list.forEach((n, idx) => {
        const h = Math.max(4, (n.count / totalW) * availH);
        posMap.set(n.key, {
          field: uniqueStages[si], key: n.key, label: n.label, count: n.count, isOther: n.isOther,
          x: colXs[si], y, h, outOff: 0, inOff: 0, color: PALETTE[(si * 3 + idx) % PALETTE.length]
        });
        y += h + gap;
      });
      nodePos.push(posMap);
    }

    // Column headers
    uniqueStages.forEach((fk, si) => {
      svg.appendChild(svgEl("text", {
        x: colXs[si] + nodeW / 2, y: 18, "text-anchor": "middle",
        fill: "var(--muted)", "font-size": 12, "font-weight": 600, "font-family": "monospace"
      }, fk));
    });

    // Draw curved ribbons between adjacent stages
    for (let si = 0; si < uniqueStages.length - 1; si++) {
      const fA = uniqueStages[si], fB = uniqueStages[si + 1];
      const topA = stageTopSets[si], topB = stageTopSets[si + 1];
      const flows = new Map();
      for (const s of skits) {
        const w = skitWeight(s, wm);
        if (w <= 0) continue;
        const rawA = Object.prototype.hasOwnProperty.call(s.tokens, fA) ? s.tokens[fA] : "NULL";
        const rawB = Object.prototype.hasOwnProperty.call(s.tokens, fB) ? s.tokens[fB] : "NULL";
        const kA = topA.has(rawA) ? rawA : "__OTHER__";
        const kB = topB.has(rawB) ? rawB : "__OTHER__";
        const fk = kA.length + ":" + kA + "|" + kB;
        flows.set(fk, [kA, kB, (flows.has(fk) ? flows.get(fk)[2] : 0) + w]);
      }
      const flowList = Array.from(flows.values()).sort((a, b) => b[2] - a[2]);
      const pMapA = nodePos[si], pMapB = nodePos[si + 1];

      for (const [kA, kB, cnt] of flowList) {
        const nA = pMapA.get(kA), nB = pMapB.get(kB);
        if (!nA || !nB || cnt <= 0) continue;
        const hA = (cnt / nA.count) * nA.h;
        const hB = (cnt / nB.count) * nB.h;
        const x0 = nA.x + nodeW, x1 = nB.x;
        const mx = (x0 + x1) / 2;
        const y0t = nA.y + nA.outOff, y0b = y0t + hA;
        const y1t = nB.y + nB.inOff, y1b = y1t + hB;
        nA.outOff += hA;
        nB.inOff += hB;
        const d =
          "M " + x0 + " " + y0t.toFixed(1) +
          " C " + mx + " " + y0t.toFixed(1) + ", " + mx + " " + y1t.toFixed(1) + ", " + x1 + " " + y1t.toFixed(1) +
          " L " + x1 + " " + y1b.toFixed(1) +
          " C " + mx + " " + y1b.toFixed(1) + ", " + mx + " " + y0b.toFixed(1) + ", " + x0 + " " + y0b.toFixed(1) + " Z";
        const rib = svgEl("path", {
          d, fill: nA.color, "fill-opacity": "0.34", style: "cursor:pointer"
        });
        rib.addEventListener("mouseenter", () => {
          rib.setAttribute("fill-opacity", "0.68");
          const box = document.getElementById("sankey-inspector");
          clear(box);
          box.appendChild(el("strong", { class: "mono" }, fA + "=" + nA.label + "  ->  " + fB + "=" + nB.label));
          const row = el("div", { style: "margin-top:5px;display:flex;gap:6px;flex-wrap:wrap" });
          row.appendChild(el("span", { class: "badge ok" }, fmtWeight(cnt, wm) + " " + wm.shortLabel + " (" + fmtPct((100 * cnt) / totalW) + " of filtered)"));
          row.appendChild(el("span", { class: "badge" }, fmtPct((100 * cnt) / nA.count) + " of " + nA.label));
          row.appendChild(el("span", { class: "badge" }, fmtPct((100 * cnt) / nB.count) + " of " + nB.label));
          box.appendChild(row);
        });
        rib.addEventListener("mouseleave", () => rib.setAttribute("fill-opacity", "0.34"));
        rib.addEventListener("click", () => {
          if (!nA.isOther) state.fieldFilters.set(fA, new Set([nA.key]));
          if (!nB.isOther) state.fieldFilters.set(fB, new Set([nB.key]));
          state.page = 1;
          render();
        });
        svg.appendChild(rib);
      }
    }

    // Draw nodes and labels
    for (let si = 0; si < uniqueStages.length; si++) {
      for (const n of nodePos[si].values()) {
        const rect = svgEl("rect", {
          x: n.x, y: n.y.toFixed(1), width: nodeW, height: n.h.toFixed(1), rx: 3,
          fill: n.color, stroke: "var(--surface)", "stroke-width": 1, style: "cursor:pointer"
        });
        rect.addEventListener("click", () => { if (!n.isOther) toggleFieldFilter(n.field, n.key); });
        rect.addEventListener("mouseenter", () => {
          const box = document.getElementById("sankey-inspector");
          clear(box);
          box.appendChild(el("strong", { class: "mono" }, n.field + "=" + n.label + " — " + fmtWeight(n.count, wm) + " " + wm.shortLabel + " (" + fmtPct((100 * n.count) / totalW) + ")"));
        });
        svg.appendChild(rect);
        const isRight = si === uniqueStages.length - 1;
        const lbl = n.label.replace("app.bsky.embed.", "").replace(/app\.bsky\.richtext\.facet#/g, "#");
        const clipped = lbl.length > 18 ? lbl.slice(0, 16) + ".." : lbl;
        const txtX = isRight ? n.x + nodeW + 6 : (si === 0 ? n.x - 6 : n.x + nodeW + 6);
        const anchor = si === 0 ? "end" : "start";
        if (n.h >= 10) {
          svg.appendChild(svgEl("text", {
            x: txtX, y: (n.y + n.h / 2 + 3.5).toFixed(1), "text-anchor": anchor,
            fill: "var(--text)", "font-size": 10.5, "font-family": "monospace"
          }, clipped + " (" + ((100 * n.count) / totalW).toFixed(0) + "%)"));
        }
      }
    }
  }

  function syncDomFromState() {
    document.documentElement.setAttribute("data-theme", state.theme);
    const wSel = document.getElementById("weight-select");
    if (wSel) wSel.value = state.weighting;
    const axisSel = document.getElementById("axis-select");
    if (axisSel && state.axisId) axisSel.value = state.axisId;
    document.getElementById("range-mode").value = state.rangeMode;
    document.getElementById("range-lo").value = String(state.sliderLo);
    document.getElementById("range-hi").value = String(state.sliderHi);
    document.getElementById("search-input").value = state.search;
    document.getElementById("pareto-top").value = String(state.paretoTop);
    document.getElementById("weight-obs").classList.toggle("active", state.weightMode === "observations");
    document.getElementById("weight-skits").classList.toggle("active", state.weightMode === "skits");
    document.getElementById("agg-outliers").classList.toggle("active", state.aggView === "outliers");
    document.getElementById("agg-histogram").classList.toggle("active", state.aggView === "histogram");
    const aggEv = document.getElementById("agg-events");
    if (aggEv) aggEv.classList.toggle("active", state.aggView === "events");
    document.getElementById("sort-select").value = state.sortBy;
    document.getElementById("sort-dir").textContent = state.sortDir === "desc" ? "Desc" : "Asc";
    document.getElementById("toggle-all-tokens").checked = state.showAllTokens;
    document.getElementById("page-size").value = String(state.pageSize);
    document.querySelectorAll("[data-corr-tab]").forEach(b => b.classList.toggle("active", b.dataset.corrTab === state.corrTab));
    document.querySelectorAll(".corr-sub-panel").forEach(p => p.classList.toggle("active", p.id === "corr-panel-" + state.corrTab));
    const phiSlider = document.getElementById("corr-phi-slider");
    phiSlider.value = String(state.corrMinPhi);
    document.getElementById("corr-phi-val").textContent = state.corrMinPhi.toFixed(2);
    document.querySelectorAll("[data-corr-sign]").forEach(b => b.classList.toggle("active", b.dataset.corrSign === state.corrSign));
    document.getElementById("corr-hide-locks").checked = state.corrHideLocks;
    document.querySelectorAll("[data-corr-mat]").forEach(b => b.classList.toggle("active", b.dataset.corrMat === state.corrMatMetric));
  }

  function readUrlState() {
    let raw = "";
    try { raw = (window.location.hash || "").replace(/^#/, ""); } catch (_) { return; }
    if (!raw) return;
    const p = new URLSearchParams(raw);
    const fieldSet = new Set(DATA.fields.map(f => f.key));
    const aggSet = new Set(DATA.aggregates.map(a => a.key));
    const weightSet = new Set((DATA.weightings || []).map(w => w.key));
    const axisSet = new Set(DATA.time_axes.map(a => a.id));

    if (p.has("th")) {
      const th = p.get("th");
      if (th === "light" || th === "dark") state.theme = th;
    }
    if (p.has("w")) {
      const wv = p.get("w");
      if (wv === "count") state.weighting = "count";
      else {
        const k = wv.startsWith("agg:") ? wv.slice(4) : wv;
        if (weightSet.has(k)) state.weighting = "agg:" + k;
      }
    }
    if (p.has("ax") && axisSet.has(p.get("ax"))) {
      state.axisId = p.get("ax");
      syncSliderLimits();
    }
    if (p.has("rm") && ["overlap", "first", "contained"].includes(p.get("rm"))) {
      state.rangeMode = p.get("rm");
    }
    const ax = getAxis();
    if (ax) {
      const maxLim = ax.kind === "runs" ? Math.max(0, ax.runs.length - 1) : 1000;
      if (p.has("lo")) {
        const lo = Number(p.get("lo"));
        if (Number.isFinite(lo)) state.sliderLo = Math.max(0, Math.min(maxLim, Math.round(lo)));
      }
      if (p.has("hi")) {
        const hi = Number(p.get("hi"));
        if (Number.isFinite(hi)) state.sliderHi = Math.max(state.sliderLo, Math.min(maxLim, Math.round(hi)));
      }
    }
    state.fieldFilters.clear();
    for (const pair of p.getAll("f")) {
      const idx = pair.indexOf(":");
      if (idx <= 0) continue;
      const fk = pair.slice(0, idx), fv = pair.slice(idx + 1);
      if (!fieldSet.has(fk)) continue;
      let s = state.fieldFilters.get(fk);
      if (!s) { s = new Set(); state.fieldFilters.set(fk, s); }
      s.add(fv);
    }
    state.search = p.get("q") || "";
    if (p.has("fld") && fieldSet.has(p.get("fld"))) state.selectedField = p.get("fld");
    if (p.has("wm") && (p.get("wm") === "observations" || p.get("wm") === "skits")) state.weightMode = p.get("wm");
    if (p.has("pt")) {
      const pt = Number(p.get("pt"));
      if ([20, 40, 80, 150].includes(pt)) state.paretoTop = pt;
    }
    if (p.has("ct") && ["network", "heatmap", "clusters"].includes(p.get("ct"))) state.corrTab = p.get("ct");
    if (p.has("cphi")) {
      const phi = Number(p.get("cphi"));
      if (Number.isFinite(phi) && phi >= 0.05 && phi <= 0.95) state.corrMinPhi = Number(phi.toFixed(2));
    }
    if (p.has("cs") && ["all", "pos", "neg"].includes(p.get("cs"))) state.corrSign = p.get("cs");
    if (p.has("cl")) state.corrHideLocks = p.get("cl") !== "0";
    if (p.has("cm") && ["theils", "cramers"].includes(p.get("cm"))) state.corrMatMetric = p.get("cm");
    if (p.has("sk")) {
      const parts = p.get("sk").split(",").slice(0, 3).map(k => (k && fieldSet.has(k) ? k : ""));
      if (parts.filter(Boolean).length >= 2) {
        state.sankeyFields = [parts[0] || "", parts[1] || "", parts[2] || ""];
        state.sankeyCustom = true;
      }
    }
    if (p.has("agg") && aggSet.has(p.get("agg"))) state.selectedAgg = p.get("agg");
    if (p.has("av") && ["outliers", "histogram", "events"].includes(p.get("av"))) state.aggView = p.get("av");
    if (p.has("sort")) {
      const sv = p.get("sort");
      if (["weight", "count", "first_seen", "last_seen"].includes(sv) || (sv.startsWith("agg:") && aggSet.has(sv.slice(4)))) {
        state.sortBy = sv;
      }
    }
    if (p.has("dir") && (p.get("dir") === "asc" || p.get("dir") === "desc")) state.sortDir = p.get("dir");
    if (p.has("pg")) {
      const pg = Number(p.get("pg"));
      if (Number.isInteger(pg) && pg >= 1) state.page = pg;
    }
    if (p.has("ps")) {
      const ps = Number(p.get("ps"));
      if ([25, 50, 100].includes(ps)) state.pageSize = ps;
    }
    if (p.has("tok")) state.showAllTokens = p.get("tok") === "1";
    syncDomFromState();
  }

  function syncUrlState() {
    const p = new URLSearchParams();
    if (state.theme !== "dark") p.set("th", state.theme);
    if (state.weighting !== DEFAULT_WEIGHTING) {
      p.set("w", state.weighting.startsWith("agg:") ? state.weighting.slice(4) : state.weighting);
    }
    const defAxis = DATA.time_axes.length ? DATA.time_axes[0].id : "";
    if (state.axisId && state.axisId !== defAxis) p.set("ax", state.axisId);
    const ax = getAxis();
    if (isSliderNarrowed(ax)) {
      if (state.rangeMode !== "overlap") p.set("rm", state.rangeMode);
      p.set("lo", String(state.sliderLo));
      p.set("hi", String(state.sliderHi));
    }
    for (const [fk, vals] of state.fieldFilters.entries()) {
      for (const v of vals) p.append("f", fk + ":" + v);
    }
    if (state.search.trim()) p.set("q", state.search.trim());
    const defField = DATA.fields.length ? DATA.fields[0].key : "";
    if (state.selectedField && state.selectedField !== defField) p.set("fld", state.selectedField);
    if (state.weightMode !== "observations") p.set("wm", state.weightMode);
    if (state.paretoTop !== 40) p.set("pt", String(state.paretoTop));
    if (state.corrTab !== "network") p.set("ct", state.corrTab);
    if (Math.abs(state.corrMinPhi - 0.14) > 1e-6) p.set("cphi", state.corrMinPhi.toFixed(2));
    if (state.corrSign !== "all") p.set("cs", state.corrSign);
    if (!state.corrHideLocks) p.set("cl", "0");
    if (state.corrMatMetric !== "theils") p.set("cm", state.corrMatMetric);
    if (state.sankeyCustom && state.sankeyFields.filter(Boolean).length >= 2) {
      p.set("sk", state.sankeyFields.join(","));
    }
    const defAgg = DATA.aggregates.length ? DATA.aggregates[0].key : "";
    if (state.selectedAgg && state.selectedAgg !== defAgg) p.set("agg", state.selectedAgg);
    if (state.aggView !== "outliers") p.set("av", state.aggView);
    if (state.sortBy !== "weight") p.set("sort", state.sortBy);
    if (state.sortDir !== "desc") p.set("dir", state.sortDir);
    if (state.page > 1) p.set("pg", String(state.page));
    if (state.pageSize !== 25) p.set("ps", String(state.pageSize));
    if (state.showAllTokens) p.set("tok", "1");

    const qs = p.toString();
    const targetHash = qs ? "#" + qs : "";
    try {
      if (window.location.hash !== targetHash) {
        const base = window.location.pathname + window.location.search;
        window.history.replaceState(null, "", targetHash ? base + targetHash : base);
      }
    } catch (_) {
      // Sandboxed iframe / opaque origin: ignore URL update safely
    }
  }

  function render() {
    const wm = activeWeightMeta();
    updateSliderUI();
    renderChips(wm);
    const skits = filterSkits();
    const totalObs = skits.reduce((sum, s) => sum + s.count, 0);
    const totalW = skits.reduce((sum, s) => sum + skitWeight(s, wm), 0);
    const conc = computeConcentration(skits, totalW, wm);
    const fields = computeFields(skits, totalW, wm);
    const ablation = computeAblation(skits);
    const corr = computeCorrelations(skits, totalW, wm);
    for (const f of fields) {
      f.redundant_with = corr.redundant_with.get(f.key) || [];
      f.determined_by = corr.determined_by.get(f.key) || [];
    }
    const aggs = computeAggregates(skits);

    renderKPIs(skits, totalObs, totalW, conc, wm);
    renderPareto(skits, totalW, wm);
    renderFieldsSection(fields, wm);
    renderAblationSection(ablation, fields);
    renderCorrelations(corr, wm);
    syncSankeySelectors(fields, ablation);
    renderSankey(skits, totalW, wm);
    renderAggregatesSection(aggs);
    renderExplorer(skits, totalW, wm);
    syncUrlState();
  }

  function initControls() {
    const weightSel = document.getElementById("weight-select");
    clear(weightSel);
    const weightings = DATA.weightings || [];
    if (!weightings.length) {
      weightSel.style.display = "none";
    } else {
      weightSel.appendChild(el("option", { value: "count" }, "Weight by: Observations (count)"));
      for (const w of weightings) {
        const opt = el("option", { value: "agg:" + w.key }, "Weight by: " + w.key + " (" + w.source + ")");
        if (state.weighting === "agg:" + w.key) opt.selected = true;
        weightSel.appendChild(opt);
      }
      weightSel.addEventListener("change", () => {
        state.weighting = weightSel.value;
        state.page = 1;
        render();
      });
    }

    const axisSel = document.getElementById("axis-select");
    clear(axisSel);
    if (!DATA.time_axes.length) {
      axisSel.style.display = "none";
    } else {
      for (const ax of DATA.time_axes) {
        const opt = el("option", { value: ax.id }, "Range Axis: " + ax.label);
        if (ax.id === state.axisId) opt.selected = true;
        axisSel.appendChild(opt);
      }
    }
    syncSliderLimits();

    axisSel.addEventListener("change", () => {
      state.axisId = axisSel.value;
      syncSliderLimits();
      state.page = 1;
      render();
    });

    const loEl = document.getElementById("range-lo");
    const hiEl = document.getElementById("range-hi");
    loEl.addEventListener("input", () => {
      const v = Number(loEl.value);
      state.sliderLo = Math.min(v, state.sliderHi);
      loEl.value = String(state.sliderLo);
      state.page = 1;
      render();
    });
    hiEl.addEventListener("input", () => {
      const v = Number(hiEl.value);
      state.sliderHi = Math.max(v, state.sliderLo);
      hiEl.value = String(state.sliderHi);
      state.page = 1;
      render();
    });

    document.getElementById("range-mode").addEventListener("change", e => {
      state.rangeMode = e.target.value;
      state.page = 1;
      render();
    });

    document.getElementById("search-input").addEventListener("input", e => {
      state.search = e.target.value;
      state.page = 1;
      render();
    });

    document.getElementById("copy-link-btn").addEventListener("click", e => {
      syncUrlState();
      const btn = e.currentTarget;
      const url = window.location.href;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(() => {
          btn.textContent = "View Link Copied";
          setTimeout(() => { btn.textContent = "Copy View Link"; }, 1400);
        });
      }
    });

    document.getElementById("reset-btn").addEventListener("click", () => {
      state.fieldFilters.clear();
      state.search = "";
      state.weighting = DEFAULT_WEIGHTING;
      state.sankeyCustom = false;
      state.sankeyFields = [];
      state.corrTab = "network";
      state.corrMinPhi = 0.14;
      state.corrSign = "all";
      state.corrHideLocks = true;
      state.corrSelectedNode = null;
      state.corrMatMetric = "theils";
      state.sortBy = "weight";
      state.sortDir = "desc";
      state.page = 1;
      syncSliderLimits();
      syncDomFromState();
      render();
    });

    document.getElementById("theme-btn").addEventListener("click", () => {
      state.theme = state.theme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", state.theme);
      render();
      renderHistorySection();
    });

    document.getElementById("pareto-top").addEventListener("change", e => {
      state.paretoTop = Number(e.target.value);
      render();
    });

    document.getElementById("field-select").addEventListener("change", e => {
      state.selectedField = e.target.value;
      render();
    });

    const btnObs = document.getElementById("weight-obs");
    const btnSkits = document.getElementById("weight-skits");
    btnObs.addEventListener("click", () => {
      state.weightMode = "observations";
      btnObs.classList.add("active");
      btnSkits.classList.remove("active");
      render();
    });
    btnSkits.addEventListener("click", () => {
      state.weightMode = "skits";
      btnSkits.classList.add("active");
      btnObs.classList.remove("active");
      render();
    });

    document.getElementById("agg-select").addEventListener("change", e => {
      state.selectedAgg = e.target.value;
      render();
    });

    const btnOut = document.getElementById("agg-outliers");
    const btnHist = document.getElementById("agg-histogram");
    const btnEv = document.getElementById("agg-events");
    btnOut.addEventListener("click", () => {
      state.aggView = "outliers";
      btnOut.classList.add("active");
      btnHist.classList.remove("active");
      btnEv.classList.remove("active");
      render();
    });
    btnHist.addEventListener("click", () => {
      state.aggView = "histogram";
      btnHist.classList.add("active");
      btnOut.classList.remove("active");
      btnEv.classList.remove("active");
      render();
    });
    btnEv.addEventListener("click", () => {
      if (btnEv.disabled) return;
      state.aggView = "events";
      btnEv.classList.add("active");
      btnOut.classList.remove("active");
      btnHist.classList.remove("active");
      render();
    });

    const sortSel = document.getElementById("sort-select");
    for (const a of DATA.aggregates) {
      if (a.kind === "numeric") {
        sortSel.appendChild(el("option", { value: "agg:" + a.key }, "Aggregate: " + a.key));
      }
    }
    sortSel.addEventListener("change", () => {
      state.sortBy = sortSel.value;
      state.page = 1;
      render();
    });

    document.getElementById("sort-dir").addEventListener("click", e => {
      state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
      e.target.textContent = state.sortDir === "desc" ? "Desc" : "Asc";
      state.page = 1;
      render();
    });

    document.getElementById("toggle-all-tokens").addEventListener("change", e => {
      state.showAllTokens = e.target.checked;
      render();
    });

    document.getElementById("page-size").addEventListener("change", e => {
      state.pageSize = Number(e.target.value);
      state.page = 1;
      render();
    });
    document.getElementById("prev-page").addEventListener("click", () => {
      if (state.page > 1) { state.page -= 1; render(); }
    });
    document.getElementById("next-page").addEventListener("click", () => {
      state.page += 1;
      render();
    });

    document.getElementById("drift-select").addEventListener("change", e => {
      state.driftIdx = Number(e.target.value);
      renderHistorySection();
    });

    // Correlation explorer controls
    document.querySelectorAll("[data-corr-tab]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-corr-tab]").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".corr-sub-panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        state.corrTab = btn.dataset.corrTab;
        document.getElementById("corr-panel-" + state.corrTab).classList.add("active");
        render();
      });
    });
    const phiSlider = document.getElementById("corr-phi-slider");
    phiSlider.addEventListener("input", () => {
      state.corrMinPhi = Number(phiSlider.value);
      document.getElementById("corr-phi-val").textContent = state.corrMinPhi.toFixed(2);
      render();
    });
    document.querySelectorAll("[data-corr-sign]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-corr-sign]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.corrSign = btn.dataset.corrSign;
        render();
      });
    });
    document.getElementById("corr-hide-locks").addEventListener("change", e => {
      state.corrHideLocks = e.target.checked;
      render();
    });
    document.querySelectorAll("[data-corr-preset]").forEach(btn => {
      btn.addEventListener("click", () => {
        state.corrSelectedNode = null;
        const p = btn.dataset.corrPreset;
        if (p === "behavioral") { state.corrMinPhi = 0.14; state.corrHideLocks = true; state.corrSign = "all"; }
        else if (p === "schema") { state.corrMinPhi = 0.35; state.corrHideLocks = false; state.corrSign = "pos"; }
        else if (p === "replies") { state.corrMinPhi = 0.10; state.corrHideLocks = true; state.corrSign = "neg"; }
        phiSlider.value = String(state.corrMinPhi);
        document.getElementById("corr-phi-val").textContent = state.corrMinPhi.toFixed(2);
        document.getElementById("corr-hide-locks").checked = state.corrHideLocks;
        document.querySelectorAll("[data-corr-sign]").forEach(b => b.classList.toggle("active", b.dataset.corrSign === state.corrSign));
        render();
      });
    });
    document.querySelectorAll("[data-corr-mat]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-corr-mat]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.corrMatMetric = btn.dataset.corrMat;
        render();
      });
    });
    ["sankey-f1", "sankey-f2", "sankey-f3"].forEach((id, idx) => {
      document.getElementById(id).addEventListener("change", e => {
        state.sankeyFields[idx] = e.target.value;
        state.sankeyCustom = true;
        render();
      });
    });

    window.addEventListener("hashchange", () => {
      readUrlState();
      render();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initControls();
    readUrlState();
    render();
    renderHistorySection();
  });
})();
"""


def render_dashboard(payload: dict[str, Any], title: str | None = None) -> str:
    """Render a complete, offline, single-file HTML analysis dashboard."""
    meta = payload.get("meta", {})
    raw_title = title if title else f"Sketch Analysis — {meta.get('sketch_name', 'sketch')}"
    safe_title = html.escape(raw_title, quote=True)
    safe_path = html.escape(str(meta.get("sketch_path", "")), quote=True)
    safe_profile = html.escape(str(meta.get("profile_id") or "none"), quote=True)
    safe_run = html.escape(str(meta.get("last_run") or "none"), quote=True)
    data_json = _safe_json_for_script(payload)
    chart_js = _chartjs_source()

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="{_CSP}">
  <title>{safe_title}</title>
  <style>{_CSS}</style>
</head>
<body>
  <header>
    <div>
      <h1>{safe_title}</h1>
      <div class="subtitle">Sketch: {safe_path} · Profile: {safe_profile} · Last run: {safe_run} · Offline report</div>
    </div>
    <div class="hdr-actions">
      <span id="filter-status" class="badge"></span>
      <button id="copy-link-btn" type="button">Copy View Link</button>
      <button id="theme-btn" type="button">Toggle Light/Dark</button>
      <button id="reset-btn" type="button">Reset Filters</button>
    </div>
  </header>

  <section class="filter-bar" aria-label="Dashboard filters">
    <div class="filter-row">
      <select id="weight-select" aria-label="Weight statistics by"></select>
      <select id="axis-select" aria-label="Time or run axis"></select>
      <select id="range-mode" aria-label="Range match mode">
        <option value="overlap">Overlap window</option>
        <option value="first">First appeared in window</option>
        <option value="contained">Fully contained in window</option>
      </select>
      <div id="slider-box" class="slider-box">
        <div class="slider-meta">
          <span id="slider-lo-label">From: -</span>
          <span id="slider-hi-label">To: -</span>
        </div>
        <div class="dual-range">
          <div class="dual-track"></div>
          <div id="dual-fill" class="dual-fill"></div>
          <input id="range-lo" type="range" min="0" max="1000" value="0" aria-label="Range minimum">
          <input id="range-hi" type="range" min="0" max="1000" value="1000" aria-label="Range maximum">
        </div>
      </div>
      <input id="search-input" type="search" placeholder="Search skit ID or token..." aria-label="Search skits">
    </div>
    <div id="active-chips" class="chips"></div>
  </section>

  <main>
    <section aria-label="Key metrics">
      <div id="kpi-grid" class="kpi-grid"></div>
    </section>

    <section class="card">
      <div class="card-hdr">
        <div>
          <h2>Overview &amp; Concentration Curve (Pareto)</h2>
          <div class="muted" style="font-size:12px">Observations in this sketch only — not a complete population inventory. Click a bar to inspect that skit.</div>
        </div>
        <div>
          <label class="muted" style="font-size:12px">Top skits:
            <select id="pareto-top">
              <option value="20">20</option>
              <option value="40" selected>40</option>
              <option value="80">80</option>
              <option value="150">150</option>
            </select>
          </label>
        </div>
      </div>
      <div id="cov-strip" class="cov-strip"></div>
      <div class="chart-wrap">
        <canvas id="chart-pareto"></canvas>
        <div id="pareto-empty" class="empty-state" style="display:none">No skits to chart in the current filter.</div>
      </div>
    </section>

    <section class="card">
      <div class="card-hdr">
        <div>
          <h2>Enumerated Field Distributions &amp; Field Min / Max / Numeric Stats</h2>
          <div id="field-detail-meta" class="muted" style="font-size:12px"></div>
        </div>
        <div class="hdr-actions">
          <select id="field-select" aria-label="Select field"></select>
          <button id="weight-obs" type="button" class="small active">Observation Weight %</button>
          <button id="weight-skits" type="button" class="small">Distinct Skits %</button>
        </div>
      </div>
      <div class="grid-2">
        <div class="chart-wrap tall"><canvas id="chart-field"></canvas></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Value</th><th id="field-col-metric" class="num">Observations</th><th id="field-col-pct" class="num">Obs %</th><th class="num">Skits</th><th class="num">Skit %</th></tr>
            </thead>
            <tbody id="field-values-tbody"></tbody>
          </table>
        </div>
      </div>
      <h3 style="margin-top:16px">All Fields — Min, Max, Weighted Mean / Median &amp; Diagnostics</h3>
      <div class="table-wrap">
        <table id="fields-table">
          <thead>
            <tr>
              <th>Field</th><th>Type</th><th class="num">Card.</th><th>Min</th><th>Max</th>
              <th>Mode (Obs %)</th><th class="num">Wtd Mean</th><th class="num">Wtd Median</th>
              <th class="num">NULL %</th><th>Diagnostics</th>
            </tr>
          </thead>
          <tbody id="fields-tbody"></tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <div class="card-hdr">
        <div>
          <h2>Profile Diagnostics — Drop-One Field Ablation</h2>
          <div class="muted" style="font-size:12px">Skits and singletons collapsed if each field is removed alone (holding all other fields fixed). Click any field to inspect its distribution above.</div>
        </div>
      </div>
      <div class="chart-wrap">
        <canvas id="chart-ablation"></canvas>
        <div id="ablation-empty" class="empty-state" style="display:none">No fields to ablate in the current filter.</div>
      </div>
      <div class="table-wrap" style="margin-top:14px">
        <table>
          <thead>
            <tr>
              <th>Field Dropped</th><th class="num">Cardinality</th><th class="num">Singleton-Only Vals</th>
              <th class="num">Skits Collapsed</th><th class="num">Singletons Removed</th>
              <th class="num">Remaining Skits</th><th class="num">Remaining Singletons</th>
            </tr>
          </thead>
          <tbody id="ablation-tbody"></tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <div class="card-hdr">
        <div>
          <h2>Correlated Value Clusters &amp; Field Associations</h2>
          <div class="muted" style="font-size:12px">Exact observation-weighted Cramér's V, directional Theil's U, and token co-occurrence φ / Lift. Recomputes live on slider and filter changes.</div>
        </div>
      </div>
      <div class="sub-tabs" role="tablist">
        <button type="button" class="small active" data-corr-tab="network">1. Value Cluster Graph</button>
        <button type="button" class="small" data-corr-tab="heatmap">2. Field Matrix (Theil's U / Cramér's V)</button>
        <button type="button" class="small" data-corr-tab="clusters">3. Discovered Clusters &amp; Rules</button>
      </div>

      <div id="corr-panel-network" class="sub-panel corr-sub-panel active">
        <div class="ctrl-inline">
          <label class="muted">Min |φ|:
            <input id="corr-phi-slider" type="range" min="0.05" max="0.95" step="0.01" value="0.14" style="vertical-align:middle">
            <span id="corr-phi-val" class="mono">0.14</span>
          </label>
          <div class="hdr-actions">
            <button type="button" class="small active" data-corr-sign="all">All (±)</button>
            <button type="button" class="small" data-corr-sign="pos">Positive (+)</button>
            <button type="button" class="small" data-corr-sign="neg">Anti (−)</button>
          </div>
          <label style="cursor:pointer"><input id="corr-hide-locks" type="checkbox" checked> Hide 1:1 schema locks (|φ|≥0.95)</label>
          <div class="hdr-actions">
            <button type="button" class="small" data-corr-preset="behavioral">Behavioral Signals</button>
            <button type="button" class="small" data-corr-preset="schema">Schema Locks</button>
            <button type="button" class="small" data-corr-preset="replies">Anti-Correlations</button>
          </div>
          <span id="corr-net-summary" class="muted" style="margin-left:auto"></span>
        </div>
        <div class="svg-wrap">
          <svg id="corr-net-svg" viewBox="0 0 920 420" style="width:100%;height:420px;display:block"></svg>
        </div>
        <div class="legend-row">
          <span><span class="leg-line pos"></span>Positive correlation (+φ, co-occur)</span>
          <span><span class="leg-line neg"></span>Negative correlation (−φ, repel)</span>
          <span>Node size = log(observations) · Color = positive cluster · Click node or link to inspect &amp; cross-filter</span>
        </div>
        <div id="corr-net-inspector" class="inspector">Click or hover any node or edge to inspect Support, Lift, φ, and directional Confidence P(B|A), or click to cross-filter the dashboard.</div>
      </div>

      <div id="corr-panel-heatmap" class="sub-panel corr-sub-panel">
        <div class="ctrl-inline">
          <button type="button" class="small active" data-corr-mat="theils">Theil's U(col | row) — Directional</button>
          <button type="button" class="small" data-corr-mat="cramers">Cramér's V — Symmetric</button>
          <span class="muted">Row X predicts Column Y (1.00 = knowing X completely determines Y).</span>
        </div>
        <div class="svg-wrap">
          <svg id="corr-heat-svg" viewBox="0 0 600 460" style="width:100%;height:460px;display:block"></svg>
        </div>
        <div id="corr-heat-inspector" class="inspector">Hover any cell to compare Cramér's V against directional Theil's U(col|row) and U(row|col).</div>
      </div>

      <div id="corr-panel-clusters" class="sub-panel corr-sub-panel">
        <div id="corr-clusters-grid" class="clusters-grid"></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Token A</th><th>Token B</th><th class="num">φ</th><th class="num">Lift</th>
                <th class="num">Support</th><th class="num">P(B|A)</th><th class="num">P(A|B)</th>
              </tr>
            </thead>
            <tbody id="corr-pairs-tbody"></tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-hdr">
        <div>
          <h2>Alluvial / Sankey Flow Explorer (2–3 Fields)</h2>
          <div class="muted" style="font-size:12px">Traces exact observation volume flowing between correlated field buckets. Click any node or ribbon to cross-filter the dashboard.</div>
        </div>
        <div class="hdr-actions">
          <label class="muted" style="font-size:12px">Stage 1: <select id="sankey-f1" aria-label="Sankey stage 1"></select></label>
          <label class="muted" style="font-size:12px">Stage 2: <select id="sankey-f2" aria-label="Sankey stage 2"></select></label>
          <label class="muted" style="font-size:12px">Stage 3: <select id="sankey-f3" aria-label="Sankey stage 3"></select></label>
        </div>
      </div>
      <div class="svg-wrap">
        <svg id="sankey-svg" viewBox="0 0 920 360" style="width:100%;height:360px;display:block"></svg>
      </div>
      <div id="sankey-inspector" class="inspector">Hover any node or ribbon to inspect exact observation flow and conditional share; click to filter.</div>
    </section>

    <section class="card">
      <div class="card-hdr">
        <div>
          <h2>Aggregates — Global Rollups, Across-Skit Mean/Median &amp; Outliers</h2>
        </div>
        <div class="hdr-actions">
          <select id="agg-select" aria-label="Select aggregate"></select>
          <button id="agg-outliers" type="button" class="small active">Top Outliers</button>
          <button id="agg-histogram" type="button" class="small">Across-Skit Distribution</button>
          <button id="agg-events" type="button" class="small">Per-Event Histogram</button>
        </div>
      </div>
      <div class="note">
        <strong>Statistical scope:</strong> Global Min, Max, Sum, and Obs-Weighted Mean (<code>AVG.sum / AVG.count</code>) cover all observations in the filtered skits. Across-Skit Median and Mean summarize the per-skit metric across active skits. Aggregates configured with <code>HISTOGRAM</code> also merge exact per-event bins and interpolated p50/p90/p95/p99 quantiles live.
      </div>
      <div class="table-wrap">
        <table id="aggs-table">
          <thead>
            <tr>
              <th>Aggregate</th><th>Kind</th><th class="num">Min</th><th class="num">Max</th>
              <th class="num">Sum</th><th class="num">Obs Mean</th>
              <th class="num">Skit Median</th><th class="num">Skit Mean</th><th class="num">Skits</th>
            </tr>
          </thead>
          <tbody id="aggs-tbody"></tbody>
        </table>
      </div>
      <div id="agg-quantiles" class="cov-strip" style="margin-top:12px;display:none"></div>
      <div class="chart-wrap" style="margin-top:10px">
        <canvas id="chart-agg"></canvas>
        <div id="agg-empty" class="empty-state" style="display:none"></div>
      </div>
    </section>

    <section class="card">
      <div class="card-hdr">
        <h2>History &amp; Run-over-Run Drift</h2>
        <select id="drift-select" aria-label="Select run transition"></select>
      </div>
      <div id="history-warnings" class="warn-box" style="display:none"></div>
      <div id="history-empty" class="empty-state">
        No run history directory found. History files are written automatically by <code>sketchtastic merge</code> under <code>&lt;sketch&gt;.history/</code>, or supply <code>--history DIR</code>.
      </div>
      <div id="history-content" style="display:none">
        <div class="chart-wrap"><canvas id="chart-history"></canvas></div>
        <div id="drift-box" style="margin-top:16px">
          <div id="drift-badges" class="cov-strip"></div>
          <div class="grid-2">
            <div>
              <h3>Newly Appeared Skits</h3>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Skit</th><th class="num">Count</th><th class="num">Weight</th><th>Tokens</th></tr></thead>
                  <tbody id="drift-new-tbody"></tbody>
                </table>
              </div>
            </div>
            <div>
              <h3>Disappeared Skits</h3>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Skit</th><th class="num">Prev Count</th><th class="num">Prev Weight</th><th>Tokens</th></tr></thead>
                  <tbody id="drift-gone-tbody"></tbody>
                </table>
              </div>
            </div>
          </div>
          <h3 style="margin-top:14px">Biggest Share Shifts (Persisted Skits)</h3>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Skit</th><th class="num">Count Change</th><th class="num">Share Shift</th><th>Tokens</th></tr></thead>
              <tbody id="drift-shift-tbody"></tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-hdr">
        <h2>Interactive Skit Explorer &amp; Retained Sample Inspector</h2>
        <div class="hdr-actions">
          <label class="muted" style="font-size:12px"><input id="toggle-all-tokens" type="checkbox"> Show NULL/FALSE tokens</label>
          <select id="sort-select" aria-label="Sort skits by">
            <option id="sort-weight-opt" value="weight" selected>Sort: Weight (Count)</option>
            <option value="count">Sort: Count</option>
            <option value="first_seen">Sort: First Seen</option>
            <option value="last_seen">Sort: Last Seen</option>
          </select>
          <button id="sort-dir" type="button" class="small">Desc</button>
          <select id="page-size" aria-label="Rows per page">
            <option value="25" selected>25 / page</option>
            <option value="50">50 / page</option>
            <option value="100">100 / page</option>
          </select>
        </div>
      </div>
      <div class="table-wrap" style="max-height:none">
        <table>
          <thead>
            <tr>
              <th>Skit ID</th><th id="skits-col-metric" class="num">Count</th><th class="num">Weight %</th><th class="num">Cum %</th>
              <th>First / Last Seen</th><th>Tokens (click to filter)</th><th>Sample</th>
            </tr>
          </thead>
          <tbody id="skits-tbody"></tbody>
        </table>
      </div>
      <div class="pager">
        <span id="pager-info" class="muted" style="font-size:12px"></span>
        <div class="hdr-actions">
          <button id="prev-page" type="button" class="small">Previous</button>
          <button id="next-page" type="button" class="small">Next</button>
        </div>
      </div>
    </section>
  </main>

  <script id="skt-data" type="application/json">{data_json}</script>
  <script>{chart_js}</script>
  <script id="skt-app-script">{_APP_JS}</script>
</body>
</html>
"""
