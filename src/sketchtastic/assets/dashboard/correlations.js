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

function computeNetworkLayout(ordered, clusterOf, edges) {
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
  return { cx, cy, pos };
}

function showCorrEdgeInspector(e, wm) {
  const box = document.getElementById("corr-net-inspector");
  clear(box);
  const top = el("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap" });
  top.appendChild(el("strong", { class: "mono" }, e.a + (e.phi >= 0 ? "  <->  " : "  (repels)  ") + e.b));
  const fBtn = el("button", { type: "button", class: "small" }, "Filter dashboard to pair");
  fBtn.addEventListener("click", () => {
    state.fieldFilters.set(e.fa, new Set([e.ta]));
    state.fieldFilters.set(e.fb, new Set([e.tb]));
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

function showCorrNodeInspector(nId, itemMap, edges, wm) {
  const info = itemMap.get(nId);
  const links = edges.filter(e => e.a === nId || e.b === nId).sort((a, b) => Math.abs(b.phi) - Math.abs(a.phi));
  const box = document.getElementById("corr-net-inspector");
  clear(box);
  const top = el("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap" });
  top.appendChild(el("strong", { class: "mono" }, nId + (info ? " — " + fmtWeight(info.count, wm) + " " + wm.shortLabel + " (" + fmtPct(info.pct) + ")" : "")));
  if (info) {
    const fBtn = el("button", { type: "button", class: "small" }, "Toggle filter: " + shortTokenLabel(info.field, info.value));
    fBtn.addEventListener("click", () => toggleFieldFilter(info.field, info.token));
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

function renderNetworkEdges(svg, edges, layout, clusterOf, sel, wm) {
  const { cx, cy, pos } = layout;
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
    path.addEventListener("mouseenter", () => showCorrEdgeInspector(e, wm));
    path.addEventListener("click", () => showCorrEdgeInspector(e, wm));
    svg.appendChild(path);
  }
}

function renderNetworkNodes(svg, ordered, layout, ctx) {
  const { pos } = layout;
  const { itemMap, edges, clusterOf, sel, connected, corr, wm } = ctx;
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
      showCorrNodeInspector(n, itemMap, edges, wm);
    });
    g.addEventListener("mouseenter", () => { if (!state.corrSelectedNode) showCorrNodeInspector(n, itemMap, edges, wm); });
    svg.appendChild(g);
  }
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

  const layout = computeNetworkLayout(ordered, clusterOf, edges);
  const sel = state.corrSelectedNode && nodeIds.has(state.corrSelectedNode) ? state.corrSelectedNode : null;
  const connected = new Set();
  if (sel) {
    connected.add(sel);
    for (const e of edges) {
      if (e.a === sel) connected.add(e.b);
      if (e.b === sel) connected.add(e.a);
    }
  }
  renderNetworkEdges(svg, edges, layout, clusterOf, sel, wm);
  renderNetworkNodes(svg, ordered, layout, { itemMap, edges, clusterOf, sel, connected, corr, wm });
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
          s.add(it.token);
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
      if (it) pill.addEventListener("click", () => toggleFieldFilter(it.field, it.token));
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
      state.fieldFilters.set(e.fa, new Set([e.ta]));
      state.fieldFilters.set(e.fb, new Set([e.tb]));
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

