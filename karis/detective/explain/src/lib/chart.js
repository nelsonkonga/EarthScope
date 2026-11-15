import { useLayoutEffect, useRef, useState } from "react";

/** Width of an element, kept up to date. */
export function useWidth(initial = 720) {
  const ref = useRef(null);
  const [w, setW] = useState(initial);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(260, Math.round(e.contentRect.width))));
    ro.observe(el);
    setW(Math.max(260, Math.round(el.getBoundingClientRect().width)));
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

export const lerp = (a, b, t) => a + (b - a) * t;

export function linear([d0, d1], [r0, r1]) {
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
  return (x) => r0 + (x - d0) * k;
}

/** Clean ticks covering [a, b]. */
export function ticks(a, b, n = 4) {
  const span = b - a || 1;
  const raw = span / n;
  const p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * p).find((s) => s >= raw) || 10 * p;
  const out = [];
  for (let v = Math.ceil(a / step) * step; v <= b + 1e-9; v += step) out.push(Math.abs(v) < 1e-9 ? 0 : v);
  return out;
}

export function extent(xs, pad = 0.06) {
  let lo = Infinity, hi = -Infinity;
  for (const x of xs) if (x != null) { if (x < lo) lo = x; if (x > hi) hi = x; }
  const m = (hi - lo || Math.abs(hi) || 1) * pad;
  return [lo - m, hi + m];
}

/** "M x y L x y ..." through points, skipping gaps (null y). */
export function path(pts) {
  let d = "", pen = false;
  for (const [x, y] of pts) {
    if (y == null || Number.isNaN(y)) { pen = false; continue; }
    d += `${pen ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
    pen = true;
  }
  return d;
}

export const YEAR_TICKS = [1985, 1995, 2005, 2015, 2025];
