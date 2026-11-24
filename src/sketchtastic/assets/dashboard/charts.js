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
              const preview = Object.entries(s.tokens).filter(([, v]) => v !== null && v !== "FALSE").slice(0, 3).map(([k, v]) => k + "=" + tokenLabel(v)).join(", ");
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
    const typeLabel = f.field_type === "boolean" ? "Boolean" : f.field_type === "numeric" ? "Numeric" : f.field_type === "enumset" ? "Enum set" : "Enum";
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
    else typeTd.appendChild(el("span", { class: "muted" }, f.field_type === "enumset" ? "Enum set" : "Enum"));
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
  const typeLabel = field.field_type === "boolean" ? "Boolean" : field.field_type === "numeric" ? "Numeric" : field.field_type === "enumset" ? "Enum set" : "Enum";
  metaBox.textContent =
    field.key + " [" + typeLabel + "] — Min: " + fmtAny(field.min) + " | Max: " + fmtAny(field.max) +
    (field.is_boolean && field.true_pct !== null ? " | True rate: " + fmtPct(field.true_pct) : "") +
    (field.is_numeric ? " | Weighted Mean: " + fmtNum(field.weighted_mean) + " | Weighted Median: " + fmtNum(field.weighted_median) : "") +
    (wm.isCount ? "" : " | Weighted by " + wm.label) +
    (field.field_type === "enumset" ? " | Exact set combinations" : "") +
    " | Missing: " + fmtPct(field.missing_pct) + " | Null: " + fmtPct(field.null_pct) +
    " (click any bar or row to filter)";

  const isObs = state.weightMode === "observations";
  const sortedVals = field.values.slice().sort((a, b) =>
    isObs ? ((b.count - a.count) || (b.skit_count - a.skit_count) || (a.value < b.value ? -1 : 1)) : ((b.skit_count - a.skit_count) || (a.value < b.value ? -1 : 1))
  );

  const activeSet = state.fieldFilters.get(field.key);
  for (const v of sortedVals.slice(0, 100)) {
    const isSel = activeSet && activeSet.has(v.token);
    const tr = el("tr", { class: "clickable" + (isSel ? " selected" : "") });
    tr.addEventListener("click", () => toggleFieldFilter(field.key, v.token));
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
    if (activeSet && activeSet.has(v.token)) return "#bc8cff";
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
          toggleFieldFilter(field.key, chartItems[idx].token);
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

function renderAggQuantileStrip(agg, hasEvHist) {
  const qStrip = document.getElementById("agg-quantiles");
  if (!qStrip) return;
  clear(qStrip);
  if (!hasEvHist) {
    qStrip.style.display = "none";
    return;
  }
  qStrip.style.display = "";
  const h = agg.histogram;
  qStrip.appendChild(el("span", { class: "badge ok" }, "Per-Event HISTOGRAM (" + h.mode + ") · " + fmtInt(h.count) + " values"));
  for (const pKey of ["p50", "p90", "p95", "p99"]) {
    if (h.quantiles[pKey] !== null && h.quantiles[pKey] !== undefined) {
      qStrip.appendChild(el("span", { class: "badge" }, pKey + " ≈ " + fmtNum(h.quantiles[pKey])));
    }
  }
}

function renderAggEventHistogram(canvas, agg, tc) {
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
}

function renderAggSkitHistogram(canvas, agg, tc) {
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
}

function renderAggOutliers(canvas, agg, tc) {
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
              return "Skit count: " + fmtInt(it.count) + " | " + Object.entries(it.tokens).filter(([, v]) => v !== null && v !== "FALSE").slice(0, 3).map(([k, v]) => k + "=" + tokenLabel(v)).join(", ");
            }
          }
        }
      }
    }
  });
}

function renderAggChart(agg) {
  destroyChart("agg");
  const canvas = document.getElementById("chart-agg");
  const empty = document.getElementById("agg-empty");
  const btnEv = document.getElementById("agg-events");
  const btnOut = document.getElementById("agg-outliers");
  const btnHist = document.getElementById("agg-histogram");
  const hasEvHist = Boolean(agg && agg.histogram && agg.histogram.bins.length);
  if (btnEv) {
    btnEv.disabled = !hasEvHist;
    btnEv.title = hasEvHist ? "Per-event distribution merged from HISTOGRAM aggregate" : "Add HISTOGRAM to this aggregate in profile.yaml to enable";
  }
  renderAggQuantileStrip(agg, hasEvHist);

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
    renderAggEventHistogram(canvas, agg, tc);
    return;
  }
  if (effectiveView === "histogram" && agg.all_values.length >= 2) {
    renderAggSkitHistogram(canvas, agg, tc);
    return;
  }
  renderAggOutliers(canvas, agg, tc);
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

  fillRows("drift-new-tbody", 4, cur.new_skits, r => [
    [r.id.slice(0, 10), "mono"], [fmtInt(r.count), "num"], [fmtPct(r.weight_pct), "num"], [tokenSummary(r.tokens), "mono"]
  ]);
  fillRows("drift-gone-tbody", 4, cur.disappeared_skits, r => [
    [r.id.slice(0, 10), "mono"], [fmtInt(r.prev_count), "num"], [fmtPct(r.prev_weight_pct), "num"], [tokenSummary(r.tokens), "mono"]
  ]);
  fillRows("drift-shift-tbody", 4, cur.top_shifts, r => [
    [r.id.slice(0, 10), "mono"],
    [fmtInt(r.prev_count) + " -> " + fmtInt(r.curr_count), "num"],
    [(r.delta_pct >= 0 ? "+" : "") + r.delta_pct.toFixed(2) + " pp", "num"],
    [tokenSummary(r.tokens), "mono"]
  ]);
}

