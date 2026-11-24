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

function buildSankeyStages(uniqueStages, skits, wm) {
  const MAX_NODES = 8;
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
    stageTopSets.push(new Set(top.map(x => x[0])));
    const list = top.map(([v, c]) => ({ key: v, label: v, count: c, isOther: false }));
    if (rest.length) {
      list.push({ key: "__OTHER__", label: "Other (" + rest.length + ")", count: rest.reduce((a, x) => a + x[1], 0), isOther: true });
    }
    stageNodes.push(list);
  }
  return { stageTopSets, stageNodes };
}

function layoutSankeyNodes(uniqueStages, stageNodes, totalW, colXs) {
  const H = 360, topY = 34, botPad = 18, usableH = H - topY - botPad, gap = 7;
  const nodePos = [];
  for (let si = 0; si < uniqueStages.length; si++) {
    const list = stageNodes[si];
    const availH = Math.max(60, usableH - Math.max(0, list.length - 1) * gap);
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
  return nodePos;
}

function drawSankeyRibbons(svg, uniqueStages, stageTopSets, nodePos, skits, totalW, wm) {
  const nodeW = 16;
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
      const x0 = nA.x + nodeW, x1 = nB.x, mx = (x0 + x1) / 2;
      const y0t = nA.y + nA.outOff, y0b = y0t + hA;
      const y1t = nB.y + nB.inOff, y1b = y1t + hB;
      nA.outOff += hA;
      nB.inOff += hB;
      const d =
        "M " + x0 + " " + y0t.toFixed(1) +
        " C " + mx + " " + y0t.toFixed(1) + ", " + mx + " " + y1t.toFixed(1) + ", " + x1 + " " + y1t.toFixed(1) +
        " L " + x1 + " " + y1b.toFixed(1) +
        " C " + mx + " " + y1b.toFixed(1) + ", " + mx + " " + y0b.toFixed(1) + ", " + x0 + " " + y0b.toFixed(1) + " Z";
      const rib = svgEl("path", { d, fill: nA.color, "fill-opacity": "0.34", style: "cursor:pointer" });
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
}

function drawSankeyNodes(svg, uniqueStages, nodePos, totalW, wm) {
  const nodeW = 16;
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

function renderSankey(skits, totalW, wm) {
  const svg = document.getElementById("sankey-svg");
  clear(svg);
  const uniqueStages = [];
  for (const s of state.sankeyFields.filter(Boolean)) {
    if (!uniqueStages.includes(s)) uniqueStages.push(s);
  }
  if (uniqueStages.length < 2 || !skits.length || !totalW) {
    svg.appendChild(svgEl("text", { x: 460, y: 170, "text-anchor": "middle", fill: "var(--muted)", "font-size": 13 },
      "Select at least 2 distinct fields with positive weight to render a Sankey flow."));
    return;
  }
  const colXs = uniqueStages.length === 2 ? [150, 750] : [130, 452, 774];
  const { stageTopSets, stageNodes } = buildSankeyStages(uniqueStages, skits, wm);
  const nodePos = layoutSankeyNodes(uniqueStages, stageNodes, totalW, colXs);
  uniqueStages.forEach((fk, si) => {
    svg.appendChild(svgEl("text", {
      x: colXs[si] + 8, y: 18, "text-anchor": "middle",
      fill: "var(--muted)", "font-size": 12, "font-weight": 600, "font-family": "monospace"
    }, fk));
  });
  drawSankeyRibbons(svg, uniqueStages, stageTopSets, nodePos, skits, totalW, wm);
  drawSankeyNodes(svg, uniqueStages, nodePos, totalW, wm);
}

