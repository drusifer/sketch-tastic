function sortKey(skit, wm) {
  if (state.sortBy === "weight") return skitWeight(skit, wm);
  if (state.sortBy === "count") return skit.count;
  if (state.sortBy === "first_seen") return skit.first_seen || "";
  if (state.sortBy === "last_seen") return skit.last_seen || "";
  if (state.sortBy.startsWith("agg:")) {
    const k = state.sortBy.slice(4);
    const rawAgg = (skit.aggregates && Object.prototype.hasOwnProperty.call(skit.aggregates, k))
      ? skit.aggregates[k]
      : null;
    const p = extractPrimaryMetric(rawAgg);
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
    if (s.covered !== null && s.covered !== undefined) {
      idTd.appendChild(el("span", { class: "badge " + (s.covered ? "ok" : "warn"), style: "margin-left:6px" }, s.covered ? "covered" : "uncovered"));
    }
    tr.appendChild(idTd);

    const metricTd = el("td", { class: "num", title: wm.isCount ? "" : (fmtInt(s.count) + " observations") }, fmtWeight(w, wm));
    tr.appendChild(metricTd);
    tr.appendChild(el("td", { class: "num" }, fmtPct(wPct)));
    tr.appendChild(el("td", { class: "num" }, fmtPct(cPct)));
    tr.appendChild(el("td", { class: "mono", style: "white-space:nowrap" }, fmtAny(s.first_seen) + " / " + fmtAny(s.last_seen)));

    const tokTd = el("td");
    const entries = Object.entries(s.tokens);
    const shown = state.showAllTokens ? entries : entries.filter(([, v]) => v !== null && v !== "FALSE");
    const list = shown.length ? shown : entries.slice(0, 4);
    for (const [k, v] of list) {
      const label = tokenLabel(v);
      const pill = el("span", { class: "token-pill", title: k + " = " + label }, k + "=" + label);
      pill.style.cursor = "pointer";
      pill.addEventListener("click", () => toggleFieldFilter(k, tokenKey(v)));
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

