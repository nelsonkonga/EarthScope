import { useRef, useState } from "react";
import { motion, useInView } from "motion/react";
import { EASE, Section, Tip } from "../components/ui.jsx";
import { YEAR_TICKS, linear, useWidth } from "../lib/chart.js";
import { pct, pval } from "../lib/format.js";

const M = { l: 46, r: 14, t: 26, b: 26 };

/** A bar from the baseline to `v`, its data end rounded (4px), square on the baseline. */
function barPath(x, w, y0, y1) {
  const h = Math.abs(y1 - y0);
  const r = Math.min(4, w / 2, h);
  if (h < 0.5) return "";
  if (y1 < y0) // upwards
    return `M${x} ${y0}V${y1 + r}Q${x} ${y1} ${x + r} ${y1}H${x + w - r}Q${x + w} ${y1} ${x + w} ${y1 + r}V${y0}Z`;
  return `M${x} ${y0}V${y1 - r}Q${x} ${y1} ${x + r} ${y1}H${x + w - r}Q${x + w} ${y1} ${x + w} ${y1 - r}V${y0}Z`;
}

export default function Norm({ unit }) {
  const [box, W] = useWidth();
  const H = W < 560 ? 200 : 240;
  const ref = useRef(null);
  const seen = useInView(ref, { once: true, margin: "-60px" });
  const [hover, setHover] = useState(null);
  const n = unit.norm;

  const head = (
    <p className="prose">
      C'est la lecture propre à Eva. Sur 1981–2010, elle apprend sa <strong>norme</strong> : où tombe chaque mois parmi
      les mois semblables de ces trente ans, et ce qu'elle attend d'un mois au suivant. Puis elle lit 2011–2025 sans
      plus rien apprendre, chaque mois depuis le mois d'avant et depuis le mois d'après : une transition se lit dans
      les deux sens. Si rien n'avait changé, la moitié des mois tomberaient plus haut que prévu, l'autre moitié plus bas.
    </p>
  );
  if (!n)
    return (
      <Section n={4} title="Depuis 2011, a-t-elle quitté sa norme ?">
        {head}
        <div className="verdict">
          <span className="mark" style={{ background: "var(--axis)" }} />
          <p>Cette série ne commence qu'en 1984 : il lui manque le début de la période 1981–2010, Eva ne l'a donc pas lue avec sa norme. Choisissez une autre variable.</p>
        </div>
      </Section>
    );

  const years = Object.keys(n.by_year).map(Number);
  const vals = years.map((y) => n.by_year[y]);
  const lim = Math.max(0.12, ...vals.map(Math.abs)) * 1.1;
  const x = linear([1981, 2026], [M.l, W - M.r]);
  const y = linear([-lim, lim], [H - M.b, M.t]);
  const slot = x(1982) - x(1981);
  const bw = Math.min(24, Math.max(2, slot - 2));
  const split = Number(n.from.slice(0, 4));
  const share = n.direction === "up" ? n.above : 1 - n.above;
  const left = n.level === "left its norm";

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const yr = Math.floor(1981 + ((e.clientX - r.left - M.l) / (W - M.l - M.r)) * 45);
    setHover(n.by_year[yr] != null ? yr : null);
  };

  return (
    <Section n={4} title="Depuis 2011, a-t-elle quitté sa norme ?">
      {head}
      <div className="card" ref={ref}>
        <div className="card-top">
          <div>
            <div className="card-title">{unit.label} · {unit.region}</div>
            <div className="card-sub">chaque année : où ses mois tombent dans ce que la norme attendait</div>
          </div>
        </div>
        <div className="chart" ref={box} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
          <svg width={W} height={H} role="img" aria-label="Écart de chaque année à ce qu'attendait la norme d'Eva">
            <text className="tick" x={x(1981)} y={12}>apprentissage, 1981–2010</text>
            <text className="tick" x={x(split)} y={12}>lecture sans apprendre</text>
            <line x1={x(split)} x2={x(split)} y1={4} y2={H - M.b} stroke="var(--axis)" />
            <text className="tick" x={M.l - 8} y={y(lim * 0.8) + 4} textAnchor="end">plus haut</text>
            <text className="tick" x={M.l - 8} y={y(-lim * 0.8) + 4} textAnchor="end">plus bas</text>
            <g key={unit.key}>
              {years.map((yr, i) => {
                const v = vals[i];
                return (
                  <motion.path
                    key={yr}
                    d={barPath(x(yr + 0.5) - bw / 2, bw, y(0), y(v))}
                    fill={v >= 0 ? "var(--up)" : "var(--down)"}
                    opacity={yr < split ? 0.35 : hover === yr ? 0.8 : 1}
                    style={{ originY: v >= 0 ? 1 : 0, transformBox: "fill-box" }}
                    initial={{ scaleY: 0 }}
                    animate={{ scaleY: seen ? 1 : 0 }}
                    transition={{ duration: 0.5, ease: EASE, delay: seen ? 0.15 + i * 0.018 : 0 }}
                  />
                );
              })}
            </g>
            <line x1={M.l} x2={W - M.r} y1={y(0)} y2={y(0)} stroke="var(--axis)" />
            {YEAR_TICKS.map((yr) => (
              <text key={yr} className="tick" x={x(yr + 0.5)} y={H - 6} textAnchor="middle">{yr}</text>
            ))}
          </svg>
          {hover != null && (
            <Tip x={x(hover + 0.5)} y={y(n.by_year[hover])} width={W}>
              <b>rang moyen {pct(0.5 + n.by_year[hover])}</b>
              <br />
              <span className="k">{hover} · 50 % : comme la norme l'attendait</span>
            </Tip>
          )}
        </div>
        <div className="legend">
          <span><i className="box" style={{ background: "var(--up)" }} />plus haut que la norme l'attendait</span>
          <span><i className="box" style={{ background: "var(--down)" }} />plus bas</span>
        </div>
      </div>

      <div className="card">
        <div className="card-top">
          <div className="card-title">Depuis {split} : {pct(share)} des mois tombent plus {n.direction === "up" ? "haut" : "bas"} que prévu</div>
          <div className="card-sub">50 % si rien n'avait changé</div>
        </div>
        <Split above={n.above} seen={seen} />
      </div>
      <div className="verdict">
        <span className="mark" style={{ background: left ? "var(--eva)" : "var(--axis)" }} />
        <p>
          {left
            ? <><b>Elle a quitté la norme apprise en 1981–2010</b> (p = {pval(n.p)}, la persistance d'un mois au suivant prise en compte).</>
            : <><b>Rien de net : elle reste dans sa norme</b> (p = {pval(n.p)}).{unit.trend.level === "significant" &&
              " Sa tendance est pourtant significative : les deux lectures ne posent pas la même question. La tendance compare 1981 à 2025 ; la norme compare 2011–2025 à ce qu'Eva a appris sur 1981–2010, mois après mois."}</>}
        </p>
      </div>
    </Section>
  );
}

/** One whole split in two: months below / above what the norm expected, with the 50 % mark. */
function Split({ above, seen }) {
  return (
    <div style={{ position: "relative", padding: "6px 0 22px" }}>
      <div style={{ display: "flex", gap: 2, height: 10 }}>
        <motion.div
          style={{ background: "var(--down)", borderRadius: "999px 0 0 999px" }}
          initial={{ flexBasis: "50%" }}
          animate={{ flexBasis: seen ? `${100 * (1 - above)}%` : "50%" }}
          transition={{ duration: 1, ease: EASE, delay: 0.2 }}
        />
        <motion.div
          style={{ background: "var(--up)", borderRadius: "0 999px 999px 0", flexGrow: 1 }}
          initial={{ flexBasis: "50%" }}
          animate={{ flexBasis: seen ? `${100 * above}%` : "50%" }}
          transition={{ duration: 1, ease: EASE, delay: 0.2 }}
        />
      </div>
      <div style={{ position: "absolute", left: "50%", top: 2, height: 18, width: 1, background: "var(--ink)" }} />
      <div className="card-sub" style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
        <span>plus bas : {pct(1 - above)}</span>
        <span>50 %</span>
        <span>plus haut : {pct(above)}</span>
      </div>
    </div>
  );
}
