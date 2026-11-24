function skitWeight(skit, wm) {
  const m = wm || { isCount: true };
  if (m.isCount) return skit.count;
  if (skit.weights && Object.prototype.hasOwnProperty.call(skit.weights, m.key)) {
    const v = Number(skit.weights[m.key]);
    return Number.isFinite(v) && v > 0 ? v : 0;
  }
  return 0;
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

function computeFields(skits, fieldKeys, totalW, wm) {
  const keys = fieldKeys || [];
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
    if (next.mode === "log") return { mode: "log", count: next.count, bins: Object.assign(Object.create(null), next.bins) };
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

function computeAggregates(skits, aggDescriptors) {
  return (aggDescriptors || []).map(meta => {
    const key = meta.key;
    let sumTotal = 0, hasSum = false;
    let countTotal = 0, hasCount = false;
    let avgSum = 0, avgCount = 0, hasAvg = false;
    let gMin = null, gMax = null;
    let histState = null;
    let metricName = meta.metric || "VALUE";
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
      const raw = (s.aggregates && Object.prototype.hasOwnProperty.call(s.aggregates, key))
        ? s.aggregates[key]
        : undefined;
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


function computeAblation(skits, fieldKeys) {
  const keys = fieldKeys || [];
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

function computeMarginals(skits, keys, wm) {
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
  return { marginals, ent };
}

function computeFieldMatrices(keys, skits, marginals, ent, totalW, wm) {
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
  return { cramers, theils };
}

function computeRedundancyMaps(keys, ent, theils) {
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
  return { redundant_with, determined_by };
}

function computeValueCooccurrence(keys, skits, marginals, totalW, wm) {
  const m = wm || { isCount: true };
  const minSup = m.isCount
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
  return { items, edges: edges.slice(0, 250) };
}

function computeCorrelations(skits, fieldKeys, totalW, wm) {
  const keys = fieldKeys || [];
  if (!skits.length || !totalW || keys.length < 2) {
    return { fields: [], cramers: new Map(), theils: new Map(), redundant_with: new Map(), determined_by: new Map(), items: [], edges: [] };
  }
  const { marginals, ent } = computeMarginals(skits, keys, wm);
  const { cramers, theils } = computeFieldMatrices(keys, skits, marginals, ent, totalW, wm);
  const { redundant_with, determined_by } = computeRedundancyMaps(keys, ent, theils);
  const { items, edges } = computeValueCooccurrence(keys, skits, marginals, totalW, wm);
  return { fields: keys, cramers, theils, redundant_with, determined_by, items, edges };
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

