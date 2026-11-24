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
  document.getElementById("coverage-select").value = state.coverageFilter;
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
  state.coverageFilter = DATA.coverage && ["covered", "uncovered"].includes(p.get("cv")) ? p.get("cv") : "all";
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
  if (state.coverageFilter !== "all") p.set("cv", state.coverageFilter);
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

