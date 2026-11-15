// French numbers: decimal comma, real minus sign, p-values as 3·10⁻⁵.
const SUP = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };

export function num(x, digits = 2, sign = false) {
  if (x == null || Number.isNaN(x)) return "–";
  const s = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: digits, minimumFractionDigits: 0 }).format(Math.abs(x));
  if (x < 0 && Number(s.replace(",", ".").replace(/\s/g, "")) !== 0) return "−" + s;
  return (sign && x > 0 ? "+" : "") + s;
}

/** Rounded to `sig` significant digits, French style. */
export function sig(x, s = 2, sign = false) {
  if (x == null || x === 0) return num(x, 0, sign);
  const d = Math.max(0, s - 1 - Math.floor(Math.log10(Math.abs(x))));
  return num(x, Math.min(d, 4), sign);
}

export function pval(p) {
  if (p == null) return "–";
  if (p >= 0.001) return num(p, p >= 0.01 ? 2 : 3);
  let e = Math.floor(Math.log10(p));
  let m = Math.round(p / 10 ** e);
  if (m === 10) { m = 1; e += 1; }
  return `${m}·10${String(e).split("").map((c) => SUP[c]).join("")}`;
}

export const pct = (x, d = 0) => `${num(100 * x, d)} %`;

export function rate(u, x = u.trend.per_decade) {
  return `${sig(x, 2, true)} ${u.units} par décennie`;
}

export const MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

/** Month index t (0 = first month of the series) → "mars 2014". */
export function monthLabel(start, t) {
  const [y, m] = start.split("-").map(Number);
  const k = m - 1 + t;
  return `${MONTHS[k % 12]} ${y + Math.floor(k / 12)}`;
}
