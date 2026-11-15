import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Bar, EASE, Section, Segmented } from "../components/ui.jsx";
import { AM, Axes, Dots, annualScales } from "../components/Annual.jsx";
import { useWidth } from "../lib/chart.js";
import { num, pct, pval, sig } from "../lib/format.js";

const MODES = [
  { value: "pettitt", label: "Test de Pettitt" },
  { value: "eva", label: "Eva" },
];

/** Pettitt's two levels, from the yearly values (`year` = first year of the new level). */
function pettittLevels(s) {
  if (s.pettitt?.before != null) return [s.pettitt.before, s.pettitt.after];
  const yr = typeof s.pettitt === "number" ? s.pettitt : s.pettitt.year;
  const a = [], b = [];
  s.years.forEach((y, j) => (y < yr ? a : b).push(s.annual[j]));
  const mean = (v) => v.reduce((x, w) => x + w, 0) / v.length;
  return [mean(a), mean(b)];
}

/** The same 2·n points for both readings, so one morphs into the other. */
function shapes(s, sc) {
  const yr = typeof s.pettitt === "number" ? s.pettitt : s.pettitt.year;
  const [before, after] = pettittLevels(s);
  const lineAt = (y) => {
    const L = s.lines.find((l) => y >= l.from && y <= l.to) || (y < s.lines[0].from ? s.lines[0] : s.lines[s.lines.length - 1]);
    return (xx) => L.y0 + ((L.y1 - L.y0) * (xx - L.from)) / (L.to - L.from || 1);
  };
  const P = [], E = [];
  s.years.forEach((y) => {
    const lv = y < yr ? before : after;
    P.push([sc.x(y), sc.y(lv)], [sc.x(y + 1), sc.y(lv)]);
    const f = lineAt(y);
    E.push([sc.x(y), sc.y(f(y - 0.5))], [sc.x(y + 1), sc.y(f(y + 0.5))]);
  });
  const d = (pts) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  return { p: d(P), e: d(E), yr, before, after };
}

export default function Change({ unit, amazon, control }) {
  const [mode, setMode] = useState("pettitt");
  const [lead, setLead] = useState(false);
  const [box, W] = useWidth();
  const H = W < 560 ? 230 : 280;

  const s = lead
    ? { ...amazon, key: "amazon", pettitt: amazon.pettitt }
    : { ...unit, lines: unit.eva.lines, pettitt: unit.pettitt };
  const sc = annualScales(s, W, H);
  const sh = shapes(s, sc);
  const eva = mode === "eva";
  const pP = lead ? amazon.pettitt_p : unit.pettitt.p;
  const lines = s.lines;
  const end = lines[lines.length - 1];

  const evaText = lines.length === 1
    ? `une seule dynamique : ${sig(end.per_decade, 2, true)} ${s.units} par décennie`
    : `${lines.map((l) => sig(l.per_decade, 2, true)).join(" puis ")} ${s.units} par décennie`;
  const pettText = `rupture en ${sh.yr} ? p = ${pval(pP)}`;

  return (
    <Section n={3} title="La dynamique a-t-elle changé ?">
      <p className="prose">
        Le <strong>test de Pettitt</strong> cherche l'année où le niveau a sauté, et il en trouve presque toujours une.
        Eva lit la même série à l'année en <strong>dynamiques</strong> : une droite tant que les années suivantes la
        prolongent, une nouvelle seulement si le changement est prouvé au-delà du bruit, ce bruit étant mesuré autour
        de ses propres dynamiques.
      </p>

      <div className="card">
        <div className="card-top">
          <div>
            <div className="card-title">{s.label} · {s.region}</div>
            <div className="card-sub">moyennes annuelles, écart à la normale en {s.units}</div>
          </div>
          <Segmented id="change" label="Lecture" options={MODES} value={mode} onChange={setMode} />
        </div>
        <div className="chart" ref={box}>
          <svg width={W} height={H} role="img" aria-label={eva ? `Eva : ${evaText}` : `Pettitt : ${pettText}`}>
            <Axes sc={sc} W={W} H={H} />
            <Dots series={s} sc={sc} dim />
            <motion.path
              d={eva ? sh.e : sh.p}
              initial={false}
              animate={{ d: eva ? sh.e : sh.p }}
              transition={{ duration: 0.8, ease: EASE }}
              fill="none"
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeLinecap="round"
              style={{ stroke: eva ? "var(--eva)" : "var(--pettitt)", transition: "stroke 0.6s" }}
            />
            <AnimatePresence>
              {!eva && (
                <motion.g key="p" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <line x1={sc.x(sh.yr)} x2={sc.x(sh.yr)} y1={AM.t} y2={H - AM.b} stroke="var(--pettitt)" strokeWidth="1" opacity="0.6" />
                  <Label x={sc.x(sh.yr)} y={AM.t + 4} W={W} text={pettText} />
                </motion.g>
              )}
              {eva && (
                <motion.g key="e" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  {(s.transitions || []).map((t) => (
                    <line key={t} x1={sc.x(t + 0.5)} x2={sc.x(t + 0.5)} y1={AM.t} y2={H - AM.b} stroke="var(--eva)" strokeWidth="1" opacity="0.6" />
                  ))}
                  <Label x={lines.length > 1 ? sc.x(s.transitions[0] + 0.5) : sc.x(1990)} y={AM.t + 4} W={W} text={evaText} />
                </motion.g>
              )}
            </AnimatePresence>
          </svg>
        </div>
        <div className="legend">
          <span><i className="dot" style={{ background: "var(--data)" }} />une année</span>
          <span><i style={{ background: "var(--pettitt)" }} />niveaux de Pettitt</span>
          <span><i style={{ background: "var(--eva)" }} />dynamiques d'Eva</span>
        </div>
        <AnimatePresence mode="wait">
          <motion.p key={`${mode}-${lead}`} className="caption" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.2 }}>
            {!eva && `Pettitt coupe la série en deux niveaux : ${sig(sh.before, 2, true)} puis ${sig(sh.after, 2, true)} ${s.units}. Mais une tendance n'a pas de niveau unique : le test trouve surtout où elle croise sa propre moyenne.`}
            {eva && !lead && lines.length === 1 && "Aucun changement de régime ne sort des écarts d'une année à l'autre : la série suit une seule dynamique régulière depuis 1981."}
            {eva && lead && `Eva voit ici une baisse entre 2004 et 2005, puis un lent déclin. Mais la série est très persistante : sur son propre témoin, Eva y voit deux dynamiques ${pct(amazon.control_eva, 1)} du temps. C'est une piste, pas un résultat.`}
            {eva && !lead && lines.length > 1 && "Eva voit ici plusieurs dynamiques. Sur une série aussi persistante, c'est une piste à vérifier."}
          </motion.p>
        </AnimatePresence>
        <button className="ghost" onClick={() => { setLead(!lead); setMode("eva"); }}>
          {lead ? `Revenir à ${unit.label.toLowerCase()} (${unit.region})` : "Voir une série où Eva voit deux dynamiques : l'évaporation en Amazonie"}
        </button>
      </div>

      <div className="card">
        <div className="card-title">Le témoin : des tendances régulières, sans aucune rupture</div>
        <p className="card-sub" style={{ margin: "2px 0 12px" }}>
          La pente de chacune des {control.series} séries, plus un bruit aussi persistant qu'elle, 40 tirages par série.
          Part des tirages où chacun annonce un changement :
        </p>
        <Bar label="Pettitt" share={control.pettitt} color="var(--pettitt)" text={pct(control.pettitt, 1)} />
        <Bar label="Eva" share={control.eva} color="var(--eva)" text={pct(control.eva, 1)} />
        <p className="note">
          Sur les vraies séries, Pettitt annonce une rupture dans 47 sur 68, Eva un changement dans 8. Ces 8 sont très
          persistantes : sur leur propre témoin, Eva s'y trompe 17 à 45 % du temps. Ce sont des pistes.
        </p>
      </div>
    </Section>
  );
}

function Label({ x, y, W, text }) {
  // beside its marker when it fits, else against the left edge of the plot
  const w = text.length * 6.4;
  let tx = x + 6, anchor = "start";
  if (tx + w > W - AM.r) { tx = x - 6; anchor = "end"; }
  if (anchor === "end" && tx - w < AM.l) { tx = AM.l + 4; anchor = "start"; }
  return (
    <text className="lbl-strong" x={tx} y={y + 8} textAnchor={anchor}>
      {text}
    </text>
  );
}
