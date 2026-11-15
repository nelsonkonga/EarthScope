// JavaScript copy of the yearly trend statistics of detective/stats.py (season / month filter).
// Python is the reference: checks/season_stats_parity.py runs both on the same series and compares.
// Inlined into detective/page.html by report.render (placeholder __STATS_JS__); also loadable in node.
//
//   SeasonStats.seasonTrend(months, values, base, selection, alpha) -> same object as stats.season_trend
//     months: ["1981-01", ...]   values: numbers or null   base: [1981, 2010]   selection: [12, 1, 2]
const SeasonStats = (() => {
  "use strict";
  const NAN = NaN;

  // ------------------------------------------------------------- special functions
  function lgamma(x) {  // Lanczos g=7, n=9 (Godfrey), ~1e-15
    const g = 7, c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
      12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
    if (x < 0.5) return Math.log(Math.PI / Math.abs(Math.sin(Math.PI * x))) - lgamma(1 - x);
    x -= 1;
    let a = c[0];
    const t = x + g + 0.5;
    for (let i = 1; i < g + 2; i++) a += c[i] / (x + i);
    return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
  }
  function betacf(a, b, x) {  // Lentz continued fraction
    const FPMIN = 1e-300, EPS = 1e-16;
    const qab = a + b, qap = a + 1, qam = a - 1;
    let c = 1, d = 1 - qab * x / qap;
    if (Math.abs(d) < FPMIN) d = FPMIN;
    d = 1 / d;
    let hh = d;
    for (let m = 1; m <= 2000; m++) {
      const m2 = 2 * m;
      let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
      d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
      c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
      d = 1 / d; hh *= d * c;
      aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
      d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
      c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
      d = 1 / d;
      const del = d * c;
      hh *= del;
      if (Math.abs(del - 1) < EPS) break;
    }
    return hh;
  }
  function betai(a, b, x) {  // regularized incomplete beta I_x(a, b)
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    const bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
    return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
  }
  function gammaQ(a, x) {  // regularized upper incomplete gamma Q(a, x)
    if (x <= 0) return 1;
    const gln = lgamma(a);
    if (x < a + 1) {
      let ap = a, del = 1 / a, sum = del;
      for (let n = 0; n < 2000; n++) { ap += 1; del *= x / ap; sum += del; if (Math.abs(del) < Math.abs(sum) * 1e-17) break; }
      return 1 - sum * Math.exp(-x + a * Math.log(x) - gln);
    }
    const FPMIN = 1e-300;
    let b = x + 1 - a, c = 1 / FPMIN, d = 1 / b, hh = d;
    for (let i = 1; i < 2000; i++) {
      const an = -i * (i - a);
      b += 2;
      d = an * d + b; if (Math.abs(d) < FPMIN) d = FPMIN;
      c = b + an / c; if (Math.abs(c) < FPMIN) c = FPMIN;
      d = 1 / d;
      const del = d * c;
      hh *= del;
      if (Math.abs(del - 1) < 1e-16) break;
    }
    return Math.exp(-x + a * Math.log(x) - gln) * hh;
  }
  const normSf = (z) => z >= 0 ? 0.5 * gammaQ(0.5, z * z / 2) : 1 - 0.5 * gammaQ(0.5, z * z / 2);
  function normPpf(p) {  // inverse of the normal cdf, by bisection then Newton polish
    if (!(p > 0 && p < 1)) return NAN;
    const q = Math.min(p, 1 - p);  // find z >= 0 with sf(z) = q
    let lo = 0, hi = 40;
    for (let i = 0; i < 200; i++) { const mid = (lo + hi) / 2; if (normSf(mid) > q) lo = mid; else hi = mid; }
    let z = (lo + hi) / 2;
    for (let i = 0; i < 3; i++) { const f = normSf(z) - q, d = Math.exp(-z * z / 2) / Math.sqrt(2 * Math.PI); if (d > 0) z += f / d; }
    return p >= 0.5 ? z : -z;
  }
  function tSf(x, df) {  // survival function of Student's t, non-integer df allowed
    if (Number.isNaN(x) || Number.isNaN(df)) return NAN;
    if (x === Infinity) return 0;
    if (x === -Infinity) return 1;
    const tail = 0.5 * betai(df / 2, 0.5, df / (df + x * x));
    return x > 0 ? tail : 1 - tail;
  }
  function tPpf(p, df) {  // inverse cdf of Student's t, by bisection on the survival function
    if (!(p > 0 && p < 1)) return NAN;
    const q = Math.min(p, 1 - p);
    let lo = 0, hi = 1;
    while (tSf(hi, df) > q && hi < 1e12) hi *= 2;
    for (let i = 0; i < 300; i++) { const mid = (lo + hi) / 2; if (tSf(mid, df) > q) lo = mid; else hi = mid; }
    const x = (lo + hi) / 2;
    return p >= 0.5 ? x : -x;
  }

  // ------------------------------------------------------------------ helpers
  function sum(a) {  // numpy's summation order (8 interleaved partial sums from 8 values on), so that
    // means which tie in exact arithmetic tie here too (Mann-Kendall counts ties)
    const n = a.length;
    if (n < 8) { let s = 0; for (let i = 0; i < n; i++) s += a[i]; return s; }
    if (n <= 128) {
      const r = a.slice(0, 8);
      let i = 8;
      for (; i < n - (n % 8); i += 8) for (let j = 0; j < 8; j++) r[j] += a[i + j];
      let res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
      for (; i < n; i++) res += a[i];
      return res;
    }
    const m = (n >> 1) - ((n >> 1) % 8);
    return sum(a.slice(0, m)) + sum(a.slice(m));
  }
  const mean = (a) => sum(a) / a.length;
  const median = (a) => { const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const sign = (x) => x > 0 ? 1 : x < 0 ? -1 : 0;
  function roundHalfEven(x) {
    const f = Math.floor(x), d = x - f;
    if (d < 0.5) return f;
    if (d > 0.5) return f + 1;
    return f % 2 === 0 ? f : f + 1;
  }
  const pyMin = (a, b) => (b < a ? b : a), pyMax = (a, b) => (b > a ? b : a);
  function rankdata(y) {  // average ranks for ties, like scipy.stats.rankdata
    const n = y.length, idx = [...y.keys()].sort((i, j) => y[i] - y[j]), r = new Array(n);
    for (let i = 0; i < n;) {
      let j = i;
      while (j + 1 < n && y[idx[j + 1]] === y[idx[i]]) j++;
      const avg = (i + j) / 2 + 1;
      for (let k = i; k <= j; k++) r[idx[k]] = avg;
      i = j + 1;
    }
    return r;
  }
  function lag1(x) {
    const m = mean(x), d = x.map((v) => v - m);
    let den = 0; for (const v of d) den += v * v;
    if (!(den > 0 && x.length > 2)) return 0;
    let num = 0; for (let i = 0; i < d.length - 1; i++) num += d[i] * d[i + 1];
    return num / den;
  }
  function acf(x, nlags) {
    const m = mean(x), d = x.map((v) => v - m), n = x.length;
    let den = 0; for (const v of d) den += v * v;
    const out = new Array(nlags + 1).fill(0);
    if (den === 0) return out;
    for (let k = 0; k <= nlags && k < n; k++) { let s = 0; for (let i = 0; i + k < n; i++) s += d[i] * d[i + k]; out[k] = s / den; }
    return out;
  }

  // ------------------------------------------------------------------ statistics
  function ols(t, y, alpha) {
    const n = y.length;
    if (n < 4) return { n, slope: NAN, p: NAN };
    const tm = mean(t), ym = mean(y);
    let sxx = 0, sxy = 0;
    for (let i = 0; i < n; i++) { sxx += (t[i] - tm) ** 2; sxy += (t[i] - tm) * (y[i] - ym); }
    const b = sxy / sxx, a = ym - b * tm;
    const resid = y.map((v, i) => v - (a + b * t[i]));
    let sse = 0; for (const v of resid) sse += v * v;
    const r1 = lag1(resid);
    let neff = r1 > 0 ? n * (1 - r1) / (1 + r1) : n;
    neff = Math.min(n, neff);
    let syy = 0; for (const v of y) syy += (v - ym) ** 2;
    const out = { n, n_eff: neff, r1, slope: b, intercept: a, r2: syy > 0 ? 1 - sse / syy : 0 };
    if (neff <= 3) return { ...out, se: NAN, t: NAN, df: neff - 2, p: NAN, ci: [NAN, NAN] };
    const se = Math.sqrt(sse / (neff - 2) / sxx), df = neff - 2;
    const tstat = se > 0 ? b / se : Infinity;
    const crit = tPpf(1 - alpha / 2, df);
    return { ...out, se, t: tstat, df, p: 2 * tSf(Math.abs(tstat), df), ci: [b - crit * se, b + crit * se] };
  }
  function sVar(y) {
    const n = y.length;
    let s = 0;
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) s += sign(y[j] - y[i]);
    const counts = new Map();
    for (const v of y) counts.set(v, (counts.get(v) || 0) + 1);
    let ties = 0; for (const c of counts.values()) ties += c * (c - 1) * (2 * c + 5);
    return [s, (n * (n - 1) * (2 * n + 5) - ties) / 18];
  }
  function zOf(s, v) {
    if (v <= 0) return 0;
    if (s > 0) return (s - 1) / Math.sqrt(v);
    if (s < 0) return (s + 1) / Math.sqrt(v);
    return 0;
  }
  function pairSlopes(t, y) {
    const out = [], n = y.length;
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) { const dt = t[j] - t[i]; if (dt !== 0) out.push((y[j] - y[i]) / dt); }
    return out;
  }
  const senSlope = (t, y) => median(pairSlopes(t, y));
  function mannKendall(y, alpha) {
    const n = y.length;
    if (n < 4) return { n, S: 0, z: 0, p: NAN, tau: 0, var: 0, factor: 1 };
    const [s, v0] = sVar(y);
    let v = v0;
    const idx = y.map((_, i) => i + 1), b = senSlope(idx, y);
    const ranks = rankdata(y.map((u, i) => u - b * idx[i])), a = acf(ranks, n - 1);
    const band = normPpf(1 - alpha / 2) / Math.sqrt(n);
    let acc = 0;
    for (let k = 1; k < n; k++) if (Math.abs(a[k]) > band) acc += (n - k) * (n - k - 1) * (n - k - 2) * a[k];
    let factor = 1 + 2 * acc / (n * (n - 1) * (n - 2));
    if (factor > 0) v *= factor; else factor = 1;
    const z = zOf(s, v);
    return { n, S: s, var: v, z, p: 2 * normSf(Math.abs(z)), tau: s / (n * (n - 1) / 2), factor };
  }
  function sen(t, y, alpha, varS) {
    const slopes = pairSlopes(t, y).sort((a, b) => a - b), b = median(slopes), N = slopes.length;
    const c = normPpf(1 - alpha / 2) * Math.sqrt(Math.max(varS, 0));
    const lo = roundHalfEven((N - c) / 2) - 1, hi = roundHalfEven((N + c) / 2);
    const clip = (i) => Math.min(Math.max(i, 0), N - 1);
    return { slope: b, intercept: median(y.map((v, i) => v - b * t[i])), ci: [slopes[clip(lo)], slopes[clip(hi)]] };
  }
  function pettitt(y) {
    const n = y.length;
    if (n < 6) return { at: null, K: 0, p: NAN };
    const u = []; let acc = 0;
    for (let i = 0; i < n; i++) { let v = 0; for (let j = 0; j < n; j++) v += sign(y[i] - y[j]); acc += v; u.push(acc); }
    u.pop();
    let t = 0;
    for (let i = 1; i < u.length; i++) if (Math.abs(u[i]) > Math.abs(u[t])) t = i;
    const K = Math.abs(u[t]);
    return { at: t + 1, K, p: Math.min(1, 2 * Math.exp(-6 * K * K / (n ** 3 + n ** 2))), before: mean(y.slice(0, t + 1)), after: mean(y.slice(t + 1)) };
  }
  function yearsToDetect(trend, sigma, phi) {
    if (trend === 0 || !Number.isFinite(trend)) return Infinity;
    phi = Math.min(Math.max(phi, -0.95), 0.95);
    return ((3.3 * sigma / Math.abs(trend)) * Math.sqrt((1 + phi) / (1 - phi))) ** (2 / 3);
  }
  function verdict(pMk, pOls, slope, alpha) {
    const dir = slope > 0 ? "rising" : slope < 0 ? "falling" : "flat";
    if (pMk < alpha && pOls < alpha) return { level: "significant", direction: dir, text: "Significant " + dir + " trend: both tests agree at the 95 % level." };
    if (pyMin(pMk, pOls) < alpha || pyMax(pMk, pOls) < 2 * alpha) return { level: "suggestive", direction: dir, text: "A " + dir + " trend that only one test (or only the 90 % level) supports." };
    return { level: "not significant", direction: dir, text: "A " + dir + " tendency that is not significant (yet): it could be chance." };
  }

  // ------------------------------------------------------------------ season / months
  const ALL = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
  const SEASONS = { DJF: [12, 1, 2], MAM: [3, 4, 5], JJA: [6, 7, 8], SON: [9, 10, 11] };
  function seasonPlan(months) {  // sorted months + those that belong to the next year's season
    const ms = [...new Set(months.map(Number))].sort((a, b) => a - b);
    if (!ms.length || ms[0] < 1 || ms[ms.length - 1] > 12) throw new Error("months must be calendar months 1..12");
    let best = ms[0] + 12 - ms[ms.length - 1], start = 0;
    for (let i = 1; i < ms.length; i++) if (ms[i] - ms[i - 1] > best) { best = ms[i] - ms[i - 1]; start = i; }
    return [ms, new Set(start > 0 ? ms.slice(start) : [])];
  }
  function seasonalAnnualMeans(months, values, sel) {
    const [ms, nxt] = seasonPlan(sel), acc = new Map();
    months.forEach((k, i) => {
      const v = values[i], m = +k.slice(5, 7);
      if (v == null || !ms.includes(m)) return;
      const y = +k.slice(0, 4) + (nxt.has(m) ? 1 : 0);
      if (!acc.has(y)) acc.set(y, new Map());
      acc.get(y).set(m, v);
    });
    const years = [...acc.keys()].filter((y) => acc.get(y).size === ms.length).sort((a, b) => a - b);
    return { years, values: years.map((y) => mean(ms.map((m) => acc.get(y).get(m)))) };
  }
  function climatology(months, values, base) {
    const acc = {};
    months.forEach((k, i) => {
      const y = +k.slice(0, 4), m = +k.slice(5, 7);
      if (values[i] != null && base[0] <= y && y <= base[1]) (acc[m] = acc[m] || []).push(values[i]);
    });
    const out = {}; for (const m of Object.keys(acc)) out[m] = mean(acc[m]);
    return out;
  }
  function seasonTrend(months, values, base, selection, alpha) {
    alpha = alpha == null ? 0.05 : alpha;
    const [ms] = seasonPlan(selection || ALL);
    const ann = seasonalAnnualMeans(months, values, ms), clim = climatology(months, values, base);
    if (ann.years.length < 4 || ms.some((m) => !(m in clim))) return null;
    const bmean = mean(ms.map((m) => clim[m])), ay = ann.years, av = ann.values;
    const yOls = ols(ay, av, alpha), yMk = mannKendall(av, alpha), ySen = sen(ay, av, alpha, yMk.var);
    const change = av.length >= 6 ? pettitt(av) : { at: null, K: 0, p: NAN };
    const rate = ySen.slope;
    const resid = av.map((v, i) => v - (yOls.intercept + yOls.slope * ay[i]));
    const rm = mean(resid);
    let ss = 0; for (const v of resid) ss += (v - rm) ** 2;
    const sigma = Math.sqrt(ss / (resid.length - 1)), phi = lag1(resid);
    const by = ay.map((y, i) => [y, av[i]]).filter(([y]) => base[0] <= y && y <= base[1]).map((p) => p[1]);
    let baseSd = NAN;
    if (by.length > 2) { const bm = mean(by); let s2 = 0; for (const v of by) s2 += (v - bm) ** 2; baseSd = Math.sqrt(s2 / (by.length - 1)); }
    const total = rate * (ay[ay.length - 1] - ay[0]);
    return {
      months: ms, baseline_mean: bmean, baseline_sd: baseSd,
      annual: { years: ay, values: av, ols: yOls, mann_kendall: yMk, sen: ySen, pettitt: { ...change, year: change.at != null ? ay[change.at] : null } },
      per_decade: rate * 10, per_decade_ci: ySen.ci.map((c) => c * 10),
      ols_per_decade: yOls.slope * 10, ols_per_decade_ci: yOls.ci.map((c) => c * 10),
      total_change: total, total_change_sd: baseSd && baseSd > 0 ? total / baseSd : NAN,
      total_change_pct: bmean && bmean > 0 ? 100 * total / bmean : null,
      years: ay[ay.length - 1] - ay[0] + 1, noise_sd: sigma, noise_r1: phi,
      years_needed: yearsToDetect(rate, sigma, phi),
      verdict: verdict(yMk.p, yOls.p, rate, alpha),
      anomalies: av.map((v) => v - bmean),
    };
  }

  return { seasonTrend, seasonalAnnualMeans, seasonPlan, SEASONS, ALL, ols, mannKendall, sen, pettitt, verdict, rankdata, tSf, tPpf, normSf, normPpf, betai };
})();
if (typeof module !== "undefined" && module.exports) module.exports = SeasonStats;
