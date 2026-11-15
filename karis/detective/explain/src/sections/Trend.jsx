import { useMemo, useState } from "react";
import { motion } from "motion/react";
import { EASE, Num, Section } from "../components/ui.jsx";
import { AM, Axes, Dots, annualScales } from "../components/Annual.jsx";
import { useWidth } from "../lib/chart.js";
import { num, pval, rate, sig } from "../lib/format.js";

/** Mann-Kendall's votes: for each pair of years, does the later one stand higher (+1) or lower (−1)? */
function votes(v) {
  let up = 0, down = 0;
  for (let i = 0; i < v.length; i++)
    for (let j = i + 1; j < v.length; j++) {
      if (v[i] == null || v[j] == null) continue;
      if (v[j] > v[i]) up++;
      else if (v[j] < v[i]) down++;
    }
  return { up, down, pairs: (v.length * (v.length - 1)) / 2 };
}

const LEVEL = {
  significant: { word: "Tendance significative", why: "Mann-Kendall et le test t l'affirment tous les deux à 95 %." },
  suggestive: { word: "Tendance suggérée", why: "un seul des deux tests l'affirme (ou seulement à 90 %)." },
  "not significant": { word: "Pas de tendance nette", why: "aucun des deux tests ne l'affirme." },
};

export default function Trend({ unit }) {
  const [box, W] = useWidth();
  const H = W < 560 ? 230 : 280;
  const sc = annualScales(unit, W, H);
  const [pick, setPick] = useState(0);
  const j = Math.min(pick, unit.years.length - 1);
  const all = useMemo(() => votes(unit.annual), [unit]);
  const v = unit.annual;

  const mine = useMemo(() => {
    let up = 0, down = 0;
    v.forEach((w, i) => {
      if (i === j || w == null || v[j] == null) return;
      const later = i > j ? w : v[j], earlier = i > j ? v[j] : w;
      if (later > earlier) up++;
      else if (later < earlier) down++;
    });
    return { up, down };
  }, [unit, j]);

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const tt = 1981 + ((e.clientX - r.left - AM.l) / (W - AM.l - AM.r)) * 45;
    const k = Math.round(tt - 0.5 - unit.years[0]);
    if (k >= 0 && k < unit.years.length) setPick(k);
  };

  const { slope, intercept } = unit.trend;
  const y0 = unit.years[0], y1 = unit.years[unit.years.length - 1];
  const sen = (yr) => slope * yr + intercept;
  const L = LEVEL[unit.trend.level] || LEVEL["not significant"];
  const sx0 = sc.x(y0 + 0.5), sy0 = sc.y(sen(y0)), sx1 = sc.x(y1 + 0.5), sy1 = sc.y(sen(y1));

  return (
    <Section n={2} title="Une tendance, ou du hasard ?">
      <p className="prose">
        Prenez deux années : la plus récente est-elle plus haute ou plus basse ? Le <strong>test de Mann-Kendall</strong> pose
        la question pour toutes les paires et compte les montées moins les descentes. Sans tendance, ce compte reste
        près de zéro. La <strong>pente de Sen</strong> est la médiane des pentes de toutes ces paires : une année folle ne
        la tire pas.
      </p>

      <div className="card">
        <div className="card-top">
          <div>
            <div className="card-title">{unit.label} · {unit.region}</div>
            <div className="card-sub">moyennes annuelles, écart à la normale en {unit.units}</div>
          </div>
          <div className="card-sub" aria-live="polite">
            <b style={{ color: "var(--ink)" }}>{unit.years[j]}</b> : {mine.up} paires montent, {mine.down} descendent
          </div>
        </div>
        <div className="chart" ref={box} onPointerMove={onMove} onPointerDown={onMove}>
          <svg width={W} height={H} role="img" aria-label={`Moyennes annuelles et pente de Sen : ${rate(unit)}`}>
            <Axes sc={sc} W={W} H={H} />
            <g key={`${unit.key}-${j}`}>
              {v.map((w, i) => {
                if (i === j || w == null || v[j] == null) return null;
                const later = i > j ? w : v[j], earlier = i > j ? v[j] : w;
                const rise = later > earlier;
                const x1 = sc.x(unit.years[j] + 0.5), y1_ = sc.y(v[j]), x2 = sc.x(unit.years[i] + 0.5), y2 = sc.y(w);
                return (
                  <motion.path
                    key={i}
                    d={`M${x1} ${y1_}L${x2} ${y2}`}
                    stroke={rise ? "var(--up)" : "var(--down)"}
                    strokeWidth="1"
                    fill="none"
                    initial={{ pathLength: 0, opacity: 0 }}
                    animate={{ pathLength: 1, opacity: 0.45 }}
                    transition={{ duration: 0.35, delay: Math.abs(i - j) * 0.006, ease: EASE }}
                  />
                );
              })}
            </g>
            <motion.path
              key={unit.key}
              d={`M${sx0} ${sy0}L${sx1} ${sy1}`}
              stroke="var(--ink)"
              strokeWidth="2"
              strokeLinecap="round"
              initial={{ pathLength: 0 }}
              whileInView={{ pathLength: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 1.2, ease: EASE, delay: 0.2 }}
            />
            <Dots series={unit} sc={sc} active={j} dim />
          </svg>
        </div>
        <div className="legend">
          <span><i className="dot" style={{ background: "var(--data)" }} />une année</span>
          <span><i style={{ background: "var(--ink)" }} />pente de Sen</span>
          <span><i style={{ background: "var(--up)" }} />la plus récente est plus haute</span>
          <span><i style={{ background: "var(--down)" }} />plus basse</span>
        </div>
        <p className="caption">Survolez ou touchez une année : chaque paire qu'elle forme vote.</p>
      </div>

      <div className="facts">
        <Fact k="Paires d'années" v={<Num value={all.pairs} />} s={`${unit.years.length} années`} />
        <Fact k="Montées" v={<Num value={all.up} />} s="la plus récente plus haute" />
        <Fact k="Descentes" v={<Num value={all.down} />} s="la plus récente plus basse" />
        <Fact k="Montées − descentes" v={<Num value={all.up - all.down} format={(x) => num(Math.round(x), 0, true)} />} s="0 si rien ne bouge" />
      </div>

      <div className="verdict">
        <span className="mark" style={{ background: unit.trend.level === "significant" ? "var(--ink)" : "var(--axis)" }} />
        <p>
          <b>{L.word} : {rate(unit)}</b> (de {sig(unit.trend.ci[0], 2, true)} à {sig(unit.trend.ci[1], 2, true)} à 95 %).{" "}
          Le détective ne dit « significative » que si deux tests l'affirment, corrigés de l'autocorrélation (une année
          ressemble un peu à la précédente) : ici, {L.why} Mann-Kendall p = {pval(unit.trend.mk_p)}, test t p = {pval(unit.trend.t_p)}.
          {unit.trend.level !== "significant" && unit.trend.years_needed > 45 && unit.trend.years_needed < 1000 && (
            <> Avec cette variabilité, il faudrait environ {num(unit.trend.years_needed, 0)} ans de données pour qu'une
              tendance de cette taille sorte du bruit (45 jusqu'ici).</>
          )}
        </p>
      </div>
    </Section>
  );
}

function Fact({ k, v, s }) {
  return (
    <div className="fact">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className="s">{s}</div>
    </div>
  );
}
