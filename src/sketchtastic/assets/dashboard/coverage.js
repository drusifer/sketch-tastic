// Regression coverage: live over the filtered skits, plus per-run history from the payload.
// A kind is covered when the regression corpus has at least one record with its skit ID.

function renderCoverageSection(skits, totalW, wm) {
  const cov = DATA.coverage;
  const card = document.getElementById("coverage-card");
  if (!cov) {
    card.style.display = "none";
    return;
  }
  card.style.display = "";

  const covered = skits.filter(s => s.covered);
  const coveredW = covered.reduce((sum, s) => sum + skitWeight(s, wm), 0);
  const kindPct = skits.length ? (100 * covered.length) / skits.length : null;
  const weightPct = totalW ? (100 * coveredW) / totalW : null;
  const kpis = document.getElementById("coverage-kpis");
  clear(kpis);
  const kpi = (label, value, sub) => {
    const box = el("div", { class: "kpi" });
    box.appendChild(el("div", { class: "kpi-label" }, label));
    box.appendChild(el("div", { class: "kpi-value" }, value));
    box.appendChild(el("div", { class: "kpi-sub" }, sub));
    kpis.appendChild(box);
  };
  kpi("Kind Coverage", kindPct === null ? "N/A" : fmtPct(kindPct),
    fmtInt(covered.length) + " / " + fmtInt(skits.length) + " kinds in view");
  kpi(wm.isCount ? "Frequency-Weighted Coverage" : "Coverage by " + wm.label,
    weightPct === null ? "N/A" : fmtPct(weightPct),
    fmtWeight(coveredW, wm) + " / " + fmtWeight(totalW, wm));
  kpi("Regression Corpus", fmtInt(cov.regression_records) + " records",
    fmtInt(cov.regression_kinds) + " kinds; repeats add no coverage");
  kpi("Not in Baseline", fmtInt(cov.unknown_count),
    "regression kinds this sketch never observed");

  fillRows("coverage-unknown-tbody", 3, cov.unknown, r => [
    [r.id.slice(0, 10), "mono"], [fmtInt(r.records), "num"], [tokenSummary(r.tokens), "mono"]
  ]);
  renderCoverageHistory(cov.runs.filter(r => r.comparable));
}

function renderCoverageHistory(runs) {
  const empty = document.getElementById("coverage-history-empty");
  const content = document.getElementById("coverage-history");
  destroyChart("coverage");
  if (!runs.length) {
    empty.style.display = "";
    content.style.display = "none";
    return;
  }
  empty.style.display = "none";
  content.style.display = "";

  const tc = themeColors();
  const line = (label, key, color, dashed) => ({
    label, data: runs.map(r => r[key]), borderColor: color, backgroundColor: color,
    borderWidth: 2, borderDash: dashed ? [6, 4] : [], spanGaps: true
  });
  state.charts.coverage = new Chart(document.getElementById("chart-coverage").getContext("2d"), {
    type: "line",
    data: {
      labels: runs.map(r => r.id),
      datasets: [
        line("Run: frequency-weighted %", "event_pct", tc.accent, false),
        line("Run: kind %", "kind_pct", tc.accent2, false),
        line("Cumulative: frequency-weighted %", "cum_event_pct", tc.accent, true),
        line("Cumulative: kind %", "cum_kind_pct", tc.accent2, true)
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: tc.muted }, grid: { color: tc.border + "44" } },
        y: { min: 0, max: 100, ticks: { color: tc.muted }, grid: { color: tc.border + "55" }, title: { display: true, text: "Coverage %", color: tc.muted } }
      },
      plugins: { legend: { labels: { color: tc.text } } }
    }
  });

  fillRows("coverage-runs-tbody", 6, runs, r => [
    [r.id, "mono"],
    [fmtInt(r.covered_kinds) + " / " + fmtInt(r.kinds) + " (" + fmtPct(r.kind_pct) + ")", "num"],
    [fmtInt(r.covered_events) + " / " + fmtInt(r.events) + " (" + fmtPct(r.event_pct) + ")", "num"],
    [fmtPct(r.cum_event_pct), "num"],
    [fmtInt(r.new_kinds), "num"],
    [fmtInt(r.new_uncovered_count), "num"]
  ]);

  const sel = document.getElementById("coverage-run-select");
  const idx = state.coverageRunIdx >= 0 && state.coverageRunIdx < runs.length ? state.coverageRunIdx : runs.length - 1;
  clear(sel);
  runs.forEach((r, i) => {
    const opt = el("option", { value: String(i) }, "New uncovered kinds in " + r.id + " (" + r.new_uncovered_count + ")");
    if (i === idx) opt.selected = true;
    sel.appendChild(opt);
  });
  fillRows("coverage-new-tbody", 3, runs[idx].new_uncovered, r => [
    [r.id.slice(0, 10), "mono"], [fmtInt(r.count), "num"], [tokenSummary(r.tokens), "mono"]
  ]);
}

function initCoverageControls() {
  const filterSel = document.getElementById("coverage-select");
  if (!DATA.coverage) {
    filterSel.style.display = "none";
    return;
  }
  filterSel.addEventListener("change", () => {
    state.coverageFilter = filterSel.value;
    state.page = 1;
    render();
  });
  document.getElementById("coverage-run-select").addEventListener("change", e => {
    state.coverageRunIdx = Number(e.target.value);
    render();
  });
}
