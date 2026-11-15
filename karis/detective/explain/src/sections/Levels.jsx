import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, animate, motion, useMotionValue, useMotionValueEvent } from "motion/react";
import { EASE, Section, Segmented, Tip } from "../components/ui.jsx";
import { YEAR_TICKS, extent, lerp, linear, path, ticks, useWidth } from "../lib/chart.js";
import { MONTHS, num, sig } from "../lib/format.js";

const STAGES = [
  { value: 0, label: "Mois bruts" },
  { value: 1, label: "Sans les saisons" },
  { value: 2, label: "À l'année" },
];

const CAPTIONS = [
  "Chaque point est un mois, moyenné sur toute la région. Les saisons dominent : on voit surtout le cycle de l'année.",
  "On retire à chaque mois la moyenne du même mois sur 1981–2010. Il reste l'écart à la normale, sans les saisons.",
  "Un mois ressemble au précédent : lue mois par mois, Eva voyait autant de « régimes » dans un bruit sans aucune tendance que dans les vraies séries. Une tendance de 45 ans se lit à l'année.",
];

const M = { l: 46, r: 14, t: 18, b: 26 };

export default function Levels({ unit }) {
  const [stage, setStage] = useState(0);
  const mv = useMotionValue(0);
  const [p, setP] = useState(0);
  useMotionValueEvent(mv, "change", setP);
  useEffect(() => {
    const c = animate(mv, stage, { duration: 1.1, ease: EASE });
    return () => c.stop();
  }, [stage]);

  const [box, W] = useWidth();
  const H = W < 560 ? 230 : 290;
  const [hover, setHover] = useState(null);

  const s = useMemo(() => {
    const [y0, m0] = unit.start.split("-").map(Number);
    const at = new Map(unit.years.map((y, i) => [y, unit.annual[i]]));
    const t = [], raw = [], anom = [], yc = [], ann = [], mon = [];
    unit.anom.forEach((a, i) => {
      const k = m0 - 1 + i, year = y0 + Math.floor(k / 12), m = k % 12;
      t.push(year + (m + 0.5) / 12);
      mon.push([year, m]);
      anom.push(a);
      raw.push(a == null ? null : a + unit.clim[m]);
      yc.push(year + 0.5);
      ann.push(at.get(year) ?? null);
    });
    return { t, raw, anom, yc, ann, mon, dRaw: extent(raw), dAnom: extent(anom), dAnn: extent(unit.annual, 0.18) };
  }, [unit]);

  const a = Math.min(1, p), q = Math.max(0, p - 1);
  const dom = p <= 1 ? [lerp(s.dRaw[0], s.dAnom[0], a), lerp(s.dRaw[1], s.dAnom[1], a)]
    : [lerp(s.dAnom[0], s.dAnn[0], q), lerp(s.dAnom[1], s.dAnn[1], q)];
  const x = linear([1981, 2026], [M.l, W - M.r]);
  const y = linear(dom, [H - M.b, M.t]);
  const val = (i) => (p <= 1 ? (s.raw[i] == null ? null : lerp(s.raw[i], s.anom[i], a)) : s.anom[i] == null ? null : lerp(s.anom[i], s.ann[i], q));
  const pts = s.t.map((ti, i) => [x(lerp(ti, s.yc[i], q)), val(i) == null ? null : y(val(i))]);
  const yt = ticks(dom[0], dom[1], H < 250 ? 4 : 5);
  const step = yt.length > 1 ? yt[1] - yt[0] : 1;
  const dig = step >= 1 ? 0 : step >= 0.1 ? 1 : 2;

  const yearly = stage === 2;
  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left;
    const tt = 1981 + ((px - M.l) / (W - M.l - M.r)) * 45;
    if (yearly) {
      const j = Math.round(tt - 0.5 - unit.years[0]);
      if (j < 0 || j >= unit.years.length) return setHover(null);
      setHover({ kind: "year", j });
    } else {
      let best = -1, bd = Infinity;
      s.t.forEach((ti, i) => { const d = Math.abs(ti - tt); if (d < bd && s.anom[i] != null) { bd = d; best = i; } });
      setHover(best < 0 || bd > 0.2 ? null : { kind: "month", i: best });
    }
  };

  let tip = null;
  if (hover && p === stage) {
    if (hover.kind === "year") {
      const yr = unit.years[hover.j], v = unit.annual[hover.j];
      tip = { px: x(yr + 0.5), py: y(v), title: `${sig(v, 2, true)} ${unit.units}`, sub: `${yr}, écart à la normale` };
    } else {
      const i = hover.i, [yr, m] = s.mon[i];
      const v = stage === 0 ? s.raw[i] : s.anom[i];
      tip = {
        px: x(s.t[i]), py: y(v),
        title: `${sig(v, 3, stage === 1)} ${stage === 0 ? unit.raw_units : unit.units}`,
        sub: `${MONTHS[m]} ${yr}${stage === 1 ? ", écart à la normale" : ""}`,
      };
    }
  }

  return (
    <Section n={1} title="Les données, et le niveau où les lire">
      <p className="prose">
        Le catalogue de la NASA (CMR, interrogé avec le serveur <strong>earthdata-mcp</strong>) dit quels jeux de
        données couvrent la région. Les séries viennent de <strong>NASA POWER</strong> : la réanalyse MERRA-2, un
        modèle météo recalé sans cesse sur les observations, mois par mois depuis 1981.
      </p>
      <div className="flow">
        <Node k="Chercher" v="Catalogue NASA (CMR)" s="via earthdata-mcp : mots-clés officiels, jeux de données, DOI" />
        <div className="arrow"><span className="pulse" /></div>
        <Node k="Télécharger" v="NASA POWER" s={`${unit.source} · ${unit.collection}${unit.cells ? ` · moyenne de ${unit.cells} mailles` : ""}`} />
        <div className="arrow"><span className="pulse" style={{ animationDelay: "0.8s" }} /></div>
        <Node k="Lire" v="Eva" s="aucune règle de climat : des dynamiques, leur norme, et ce qui en sort" />
      </div>

      <div className="card">
        <div className="card-top">
          <div>
            <div className="card-title">{unit.label} · {unit.region}</div>
            <div className="card-sub">
              {stage === 0 ? `valeur mensuelle, ${unit.raw_units}` : `écart à la normale 1981–2010, ${unit.units}`}
            </div>
          </div>
          <Segmented id="levels" label="Niveau de lecture" options={STAGES} value={stage} onChange={(v) => { setHover(null); setStage(v); }} />
        </div>
        <div className="chart" ref={box} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
          <svg width={W} height={H} role="img" aria-label={`${unit.label}, ${STAGES[stage].label.toLowerCase()}`}>
            <rect x={x(1981)} y={M.t - 6} width={x(2011) - x(1981)} height={H - M.b - M.t + 6} fill="var(--wash)" rx="4" />
            <text className="tick" x={x(1981) + 6} y={M.t + 6}>référence 1981–2010</text>
            {yt.map((v) => (
              <g key={v}>
                <line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} stroke="var(--grid)" />
                <text className="tick" x={M.l - 8} y={y(v) + 4} textAnchor="end">{num(v, dig, true)}</text>
              </g>
            ))}
            {YEAR_TICKS.map((yr) => (
              <text key={yr} className="tick" x={x(yr + 0.5)} y={H - 6} textAnchor="middle">{yr}</text>
            ))}
            <line x1={M.l} x2={W - M.r} y1={y(0)} y2={y(0)} stroke="var(--axis)" opacity={a} />
            <path d={path(pts)} fill="none" stroke="var(--data)" strokeWidth={lerp(1.2, 2, q)} strokeLinejoin="round" strokeLinecap="round" />
            {q > 0.02 && unit.years.map((yr, j) => unit.annual[j] != null && (
              <circle key={yr} cx={x(yr + 0.5)} cy={y(unit.annual[j])} r={4 * q} fill="var(--data)" stroke="var(--surface)" strokeWidth="2" />
            ))}
            {tip && (
              <g pointerEvents="none">
                <line x1={tip.px} x2={tip.px} y1={M.t} y2={H - M.b} stroke="var(--axis)" />
                <circle cx={tip.px} cy={tip.py} r="5" fill="var(--data)" stroke="var(--surface)" strokeWidth="2" />
              </g>
            )}
          </svg>
          {tip && <Tip x={tip.px} y={tip.py} width={W}><b>{tip.title}</b><br /><span className="k">{tip.sub}</span></Tip>}
        </div>
        <AnimatePresence mode="wait">
          <motion.p
            key={stage}
            className="caption"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
          >
            {CAPTIONS[stage]}
          </motion.p>
        </AnimatePresence>
      </div>
    </Section>
  );
}

function Node({ k, v, s }) {
  return (
    <div className="node">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className="s">{s}</div>
    </div>
  );
}
