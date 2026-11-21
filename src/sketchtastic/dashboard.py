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
  max-width: 190px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
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
"""


_APP_JS = r"""
(function () {
  "use strict";

  const DATA = JSON.parse(document.getElementById("skt-data").textContent);
  const PALETTE = [
    "#58a6ff", "#3fb950", "#d29922", "#bc8cff", "#f778ba",
    "#39c5cf", "#ffa657", "#ff7b72", "#79c0ff", "#56d364"
  ];

  const state = {
    theme: "dark",
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
    sortBy: "count",
    sortDir: "desc",
    showAllTokens: false,
    page: 1,
    pageSize: 25,
    expandedIds: new Set(),
    driftIdx: DATA.history.drift.length ? DATA.history.drift.length - 1 : 0,
    charts: {}
  };

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
    const lowRank = Math.floor((total + 1) / 2);
    const highRank = total % 2 === 0 ? Math.floor(total / 2) + 1 : lowRank;
    let run = 0, lo = null, hi = null;
    for (const [v, w] of arr) {
      run += w;
      if (lo === null && run >= lowRank) lo = v;
      if (hi === null && run >= highRank) { hi = v; break; }
    }
    return (lo + hi) / 2;
  }

  function plainMedian(nums) {
    if (!nums.length) return null;
    const s = nums.slice().sort((a, b) => a - b);
    const m = Math.floor(s.length / 2);
    return s.length % 2 === 1 ? s[m] : (s[m - 1] + s[m]) / 2;
  }

  function computeFields(skits, totalObs) {
    const keys = DATA.fields.map(f => f.key);
    const nSkits = skits.length;
    return keys.map(key => {
      const byVal = new Map();
      for (const s of skits) {
        const val = Object.prototype.hasOwnProperty.call(s.tokens, key) ? s.tokens[key] : "NULL";
        const cur = byVal.get(val) || [0, 0];
        cur[0] += s.count;
        cur[1] += 1;
        byVal.set(val, cur);
      }
      const entries = Array.from(byVal.entries()).sort((a, b) => (b[1][0] - a[1][0]) || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
      const values = entries.map(([value, [count, skit_count]]) => ({
        value,
        count,
        weight_pct: totalObs ? (100 * count) / totalObs : null,
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
        null_pct: totalObs ? (100 * nullObs) / totalObs : null,
        values
      };
    });
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
        } else if (typeof raw === "object" && !Array.isArray(raw)) {
          if (typeof raw.SUM === "number") { sumTotal += raw.SUM; hasSum = true; }
          if (typeof raw.COUNT === "number") { countTotal += raw.COUNT; hasCount = true; }
          if (isAvgObj(raw.AVG)) {
            hasAvg = true;
            if (raw.AVG.count > 0) { avgSum += raw.AVG.sum; avgCount += raw.AVG.count; }
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
        outliers: active.slice(0, 15)
      };
    });
  }

  function computeConcentration(skits, totalObs) {
    const targets = [50, 80, 90, 95, 99];
    const ordered = skits.slice().sort((a, b) => (b.count - a.count) || (a.id < b.id ? -1 : 1));
    return targets.map(t => {
      if (!totalObs || !ordered.length) return { target_pct: t, skits_needed: 0, skit_pct: null };
      let cum = 0, needed = 0;
      const cutoff = totalObs * (t / 100);
      for (const s of ordered) {
        cum += s.count; needed += 1;
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

  function renderChips() {
    const wrap = document.getElementById("active-chips");
    clear(wrap);
    let any = false;
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

  function renderKPIs(skits, totalObs, conc) {
    const allObs = DATA.meta.total_observations;
    const allSkits = DATA.meta.total_skits;
    const singletons = skits.filter(s => s.count === 1).length;
    const status = document.getElementById("filter-status");
    status.textContent =
      "Showing " + fmtInt(skits.length) + " / " + fmtInt(allSkits) + " skits (" +
      fmtInt(totalObs) + " / " + fmtInt(allObs) + " obs" +
      (allObs ? ", " + fmtPct((100 * totalObs) / allObs) : "") + ")";

    const grid = document.getElementById("kpi-grid");
    clear(grid);
    const top1 = skits.length && totalObs ? (100 * skits[0].count) / totalObs : null;
    const cards = [
      ["Observations", fmtInt(totalObs), allObs && totalObs !== allObs ? fmtPct((100 * totalObs) / allObs) + " of sketch" : "100% of sketch"],
      ["Distinct Skits", fmtInt(skits.length), allSkits && skits.length !== allSkits ? fmtPct((100 * skits.length) / allSkits) + " of kinds" : "profile-defined kinds"],
      ["Singletons (count = 1)", fmtInt(singletons), totalObs ? fmtPct((100 * singletons) / totalObs) + " of obs" : "N/A"],
      ["Top Skit Share", fmtPct(top1), skits.length ? skits[0].id.slice(0, 10) + " (" + fmtInt(skits[0].count) + ")" : "No skits"],
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
      const label = c.target_pct + "% obs -> " + fmtInt(c.skits_needed) + " skits" +
        (c.skit_pct !== null ? " (" + fmtPct(c.skit_pct) + ")" : "");
      strip.appendChild(el("span", { class: "badge" }, label));
    }
  }

  function renderPareto(skits, totalObs) {
    destroyChart("pareto");
    const canvas = document.getElementById("chart-pareto");
    const empty = document.getElementById("pareto-empty");
    if (!skits.length || !totalObs) {
      canvas.style.display = "none";
      empty.style.display = "";
      return;
    }
    canvas.style.display = "";
    empty.style.display = "none";

    const ordered = skits.slice().sort((a, b) => (b.count - a.count) || (a.id < b.id ? -1 : 1));
    const slice = ordered.slice(0, state.paretoTop);
    let cum = 0;
    const labels = [];
    const counts = [];
    const cumPcts = [];
    for (const s of slice) {
      cum += s.count;
      labels.push(s.id.slice(0, 8));
      counts.push(s.count);
      cumPcts.push(Number(((100 * cum) / totalObs).toFixed(2)));
    }
    const tc = themeColors();
    state.charts.pareto = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Observations",
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
          y: { beginAtZero: true, ticks: { color: tc.muted }, grid: { color: tc.border + "55" }, title: { display: true, text: "Observations", color: tc.muted } },
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
                return preview || s.id;
              }
            }
          }
        }
      }
    });
  }

  function renderFieldsSection(fields) {
    const tbody = document.getElementById("fields-tbody");
    clear(tbody);
    const sel = document.getElementById("field-select");
    clear(sel);
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
        renderFieldsSection(fields);
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
      if (f.is_constant) diagTd.appendChild(el("span", { class: "badge warn" }, "Constant"));
      if (f.is_high_cardinality) diagTd.appendChild(el("span", { class: "badge danger" }, "High-Card"));
      if (!f.is_constant && !f.is_high_cardinality) diagTd.appendChild(el("span", { class: "muted" }, "OK"));
      tr.appendChild(diagTd);
      tbody.appendChild(tr);
    }

    const activeField = fields.find(f => f.key === state.selectedField);
    renderFieldChartAndValues(activeField);
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

  function renderFieldChartAndValues(field) {
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
      " (click any bar or row to filter)";

    const isObs = state.weightMode === "observations";
    const sortedVals = field.values.slice().sort((a, b) =>
      isObs ? ((b.count - a.count) || (a.value < b.value ? -1 : 1)) : ((b.skit_count - a.skit_count) || (a.value < b.value ? -1 : 1))
    );

    const activeSet = state.fieldFilters.get(field.key);
    for (const v of sortedVals.slice(0, 100)) {
      const isSel = activeSet && activeSet.has(v.value);
      const tr = el("tr", { class: "clickable" + (isSel ? " selected" : "") });
      tr.addEventListener("click", () => toggleFieldFilter(field.key, v.value));
      tr.appendChild(el("td", { class: "mono" }, v.value));
      tr.appendChild(el("td", { class: "num" }, fmtInt(v.count)));
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
          label: isObs ? "Observation Weight %" : "Distinct Skit Share %",
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
                return "Obs: " + fmtInt(item.count) + " (" + fmtPct(item.weight_pct) + ") | Skits: " + fmtInt(item.skit_count) + " (" + fmtPct(item.skit_pct) + ")";
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
    if (!agg || !agg.outliers.length) {
      canvas.style.display = "none";
      empty.style.display = "";
      empty.textContent = agg ? "No numeric per-skit values for '" + agg.key + "' (" + agg.kind + ") in current filter." : "No aggregate selected.";
      return;
    }
    canvas.style.display = "";
    empty.style.display = "none";
    const tc = themeColors();

    if (state.aggView === "histogram" && agg.all_values.length >= 2) {
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

  function sortKey(skit) {
    if (state.sortBy === "count") return skit.count;
    if (state.sortBy === "first_seen") return skit.first_seen || "";
    if (state.sortBy === "last_seen") return skit.last_seen || "";
    if (state.sortBy.startsWith("agg:")) {
      const k = state.sortBy.slice(4);
      const p = extractPrimaryMetric(skit.aggregates ? skit.aggregates[k] : null);
      return p.val === null || p.val === undefined ? -Infinity : p.val;
    }
    return skit.count;
  }

  function renderExplorer(skits, totalObs) {
    const sorted = skits.slice().sort((a, b) => {
      const av = sortKey(a), bv = sortKey(b);
      let cmp = av < bv ? -1 : av > bv ? 1 : 0;
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

    let running = sorted.slice(0, start).reduce((s, r) => s + r.count, 0);
    for (const s of pageRows) {
      running += s.count;
      const wPct = totalObs ? (100 * s.count) / totalObs : 0;
      const cPct = totalObs ? (100 * running) / totalObs : 0;
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

      tr.appendChild(el("td", { class: "num" }, fmtInt(s.count)));
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
        renderExplorer(skits, totalObs);
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

  function render() {
    updateSliderUI();
    renderChips();
    const skits = filterSkits();
    const totalObs = skits.reduce((sum, s) => sum + s.count, 0);
    const conc = computeConcentration(skits, totalObs);
    const fields = computeFields(skits, totalObs);
    const aggs = computeAggregates(skits);

    renderKPIs(skits, totalObs, conc);
    renderPareto(skits, totalObs);
    renderFieldsSection(fields);
    renderAggregatesSection(aggs);
    renderExplorer(skits, totalObs);
  }

  function initControls() {
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

    document.getElementById("reset-btn").addEventListener("click", () => {
      state.fieldFilters.clear();
      state.search = "";
      document.getElementById("search-input").value = "";
      syncSliderLimits();
      state.page = 1;
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
    btnOut.addEventListener("click", () => {
      state.aggView = "outliers";
      btnOut.classList.add("active");
      btnHist.classList.remove("active");
      render();
    });
    btnHist.addEventListener("click", () => {
      state.aggView = "histogram";
      btnHist.classList.add("active");
      btnOut.classList.remove("active");
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
  }

  document.addEventListener("DOMContentLoaded", () => {
    initControls();
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
      <button id="theme-btn" type="button">Toggle Light/Dark</button>
      <button id="reset-btn" type="button">Reset Filters</button>
    </div>
  </header>

  <section class="filter-bar" aria-label="Dashboard filters">
    <div class="filter-row">
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
              <tr><th>Value</th><th class="num">Observations</th><th class="num">Obs %</th><th class="num">Skits</th><th class="num">Skit %</th></tr>
            </thead>
            <tbody id="field-values-tbody"></tbody>
          </table>
        </div>
      </div>
      <h3 style="margin-top:16px">All Fields — Min, Max, Weighted Mean / Median &amp; Diagnostics</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Field</th><th>Type</th><th class="num">Cardinality</th><th>Min</th><th>Max</th>
              <th>Mode (Obs %)</th><th class="num">Weighted Mean</th><th class="num">Weighted Median</th>
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
          <h2>Aggregates — Global Rollups, Across-Skit Mean/Median &amp; Outliers</h2>
        </div>
        <div class="hdr-actions">
          <select id="agg-select" aria-label="Select aggregate"></select>
          <button id="agg-outliers" type="button" class="small active">Top Outliers</button>
          <button id="agg-histogram" type="button" class="small">Across-Skit Distribution</button>
        </div>
      </div>
      <div class="note">
        <strong>Statistical scope:</strong> Global Min, Max, Sum, and Obs-Weighted Mean (<code>AVG.sum / AVG.count</code>) cover all observations in the filtered skits. Across-Skit Median and Mean summarize the per-skit metric across active skits (sketches do not retain raw per-event quantiles).
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Aggregate</th><th>Kind</th><th class="num">Global Min</th><th class="num">Global Max</th>
              <th class="num">Global Sum</th><th class="num">Obs-Weighted Mean</th>
              <th class="num">Across-Skit Median</th><th class="num">Across-Skit Mean</th><th class="num">Active Skits</th>
            </tr>
          </thead>
          <tbody id="aggs-tbody"></tbody>
        </table>
      </div>
      <div class="chart-wrap" style="margin-top:14px">
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
              <th>Skit ID</th><th class="num">Count</th><th class="num">Weight %</th><th class="num">Cum %</th>
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
