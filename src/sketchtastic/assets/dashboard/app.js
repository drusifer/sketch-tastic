function render() {
  const wm = activeWeightMeta();
  const fieldKeys = DATA.fields.map(f => f.key);
  updateSliderUI();
  renderChips(wm);
  const skits = filterSkits();
  const totalObs = skits.reduce((sum, s) => sum + s.count, 0);
  const totalW = skits.reduce((sum, s) => sum + skitWeight(s, wm), 0);
  const conc = computeConcentration(skits, totalW, wm);
  const fields = computeFields(skits, fieldKeys, totalW, wm);
  const ablation = computeAblation(skits, fieldKeys);
  const corr = computeCorrelations(skits, fieldKeys, totalW, wm);
  for (const f of fields) {
    f.redundant_with = corr.redundant_with.get(f.key) || [];
    f.determined_by = corr.determined_by.get(f.key) || [];
  }
  const aggs = computeAggregates(skits, DATA.aggregates);

  renderKPIs(skits, totalObs, totalW, conc, wm);
  renderPareto(skits, totalW, wm);
  renderFieldsSection(fields, wm);
  renderAblationSection(ablation, fields);
  renderCorrelations(corr, wm);
  syncSankeySelectors(fields, ablation);
  renderSankey(skits, totalW, wm);
  renderAggregatesSection(aggs);
  renderCoverageSection(skits, totalW, wm);
  renderExplorer(skits, totalW, wm);
  syncUrlState();
}

function initFilterBarControls() {
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
    state.sliderLo = Math.min(Number(loEl.value), state.sliderHi);
    loEl.value = String(state.sliderLo);
    state.page = 1;
    render();
  });
  hiEl.addEventListener("input", () => {
    state.sliderHi = Math.max(Number(hiEl.value), state.sliderLo);
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
}

function initHeaderControls() {
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
    state.coverageFilter = "all";
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
}

function initChartToggleControls() {
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
  const setAggView = (view, activeBtn) => {
    state.aggView = view;
    [btnOut, btnHist, btnEv].forEach(b => b.classList.toggle("active", b === activeBtn));
    render();
  };
  btnOut.addEventListener("click", () => setAggView("outliers", btnOut));
  btnHist.addEventListener("click", () => setAggView("histogram", btnHist));
  btnEv.addEventListener("click", () => { if (!btnEv.disabled) setAggView("events", btnEv); });
}

function initExplorerControls() {
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

function initCorrelationAndSankeyControls() {
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
}

function initControls() {
  initFilterBarControls();
  initHeaderControls();
  initChartToggleControls();
  initExplorerControls();
  initCorrelationAndSankeyControls();
  initCoverageControls();
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
