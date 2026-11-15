import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { EASE, SPRING, Section, Tip } from "../components/ui.jsx";
import { YEAR_TICKS, linear, useWidth } from "../lib/chart.js";
import { monthLabel, num, pval } from "../lib/format.js";

const ROW = 20, GAP = 10, TOP = 6;

function rowName(u, multi) {
  return multi ? `${u.short} · ${u.region.replace("Mer de ", "")}` : u.short;
}

function how(L, A, B) {
  const sense = L.sign < 0 ? "en sens opposé" : "dans le même sens";
  if (L.lag === 0) return `le même mois, ${sense}`;
  const k = Math.abs(L.lag), [first, then] = L.lag > 0 ? [A, B] : [B, A];
  return `${then} ${k === 1 ? "un mois" : `${k} mois`} après ${first}${L.sign < 0 ? ", en sens opposé" : ""}`;
}

export default function Together({ kase, unit }) {
  const multi = kase.regions.length > 1;
  const rows = kase.units.filter((u) => u.extreme);
  const byKey = Object.fromEntries(rows.map((u) => [u.key, u]));
  const links = kase.links;
  const [sel, setSel] = useState(0);
  const [more, setMore] = useState(false);
  useEffect(() => {
    const k = links.findIndex((l) => l.a === unit.key || l.b === unit.key);
    setSel(k < 0 ? 0 : k);
    setMore(k >= 5);
  }, [kase.key, unit.key]);
  const L = links[Math.min(sel, links.length - 1)];

  const [box, W] = useWidth();
  const lab = multi ? (W < 560 ? 104 : 130) : W < 560 ? 80 : 116;
  const x = linear([0, 540], [lab, W - 8]);
  const cw = Math.max(1, x(1) - x(0));
  const order = useMemo(() => {
    if (!L) return rows.map((u) => u.key);
    return [L.a, L.b, ...rows.map((u) => u.key).filter((k) => k !== L.a && k !== L.b)];
  }, [kase.key, L]);
  const yOf = (k) => TOP + order.indexOf(k) * (ROW + GAP);
  const H = TOP + rows.length * (ROW + GAP) + 18;
  const hitA = new Set(L ? L.at : []), hitB = new Set(L ? L.at.map((t) => t + L.lag) : []);
  const [tip, setTip] = useState(null);

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left, py = e.clientY - r.top;
    const t = Math.floor(((px - lab) / (W - 8 - lab)) * 540);
    const i = Math.floor((py - TOP + GAP / 2) / (ROW + GAP));
    const u = byKey[order[i]];
    if (!u || t < 0 || t >= 540) return setTip(null);
    // the nearest month out of norm within a cell or two, so thin cells are easy to hit
    let best = null;
    for (const d of [0, -1, 1, -2, 2]) if (u.extreme[t + d] && u.extreme[t + d] !== ".") { best = t + d; break; }
    setTip(best == null ? null : { u, t: best, px: x(best + 0.5), py: yOf(u.key) });
  };

  return (
    <Section n={5} title="Ce qui sort de sa norme ensemble">
      <p className="prose">
        Au-delà de ses 10ᵉ ou 90ᵉ percentiles, une variable <strong>sort de sa norme</strong> : chaque trait coloré est un
        tel mois. Eva cherche ensuite la <strong>transformation</strong> qui porte les sorties de l'une sur celles de
        l'autre : le même mois, le sens opposé (un miroir), ou un à trois mois de décalage. Rien ne nomme une variable
        ni un processus.
      </p>
      <p className="prose">
        Un lien n'est retenu que si le hasard, lu <strong>au même moment</strong> du relevé, en donnerait bien moins :
        deux tendances font sortir deux variables de leur norme en fin de relevé sans qu'un même mois les fasse bouger
        ensemble. Et le seuil est divisé par le nombre d'essais : à force de chercher, on finit toujours par trouver.
      </p>

      {kase.same_process.length > 0 && (
        <div className="verdict" style={{ marginBottom: 4 }}>
          <span className="mark" style={{ background: "var(--eva)" }} />
          <p>
            <b>Un seul processus aux deux pôles.</b> À Barents comme à Ross, la glace et l'air sortent de leur norme les
            mêmes mois en sens opposé, alors que leurs tendances y sont inverses : la glace recule à Barents et progresse à Ross.
          </p>
        </div>
      )}

      <div className="card">
        <div className="card-top">
          <div>
            <div className="card-title">Les mois hors norme, 1981–2025</div>
            <div className="card-sub">les deux variables du lien choisi montent en tête</div>
          </div>
        </div>
        <div className="chart" ref={box} onPointerMove={onMove} onPointerLeave={() => setTip(null)}>
          <svg width={W} height={H} role="img" aria-label="Mois où chaque variable sort de sa norme">
            {rows.map((u) => {
              const inLink = L && (u.key === L.a || u.key === L.b);
              const hits = u.key === L?.a ? hitA : hitB;
              return (
                <motion.g key={u.key} initial={false} animate={{ y: yOf(u.key), opacity: !L || inLink ? 1 : 0.28 }} transition={SPRING}>
                  <text className={inLink ? "lbl-strong" : "lbl"} x={0} y={ROW / 2 + 4}>{rowName(u, multi)}</text>
                  <rect x={lab} y={ROW / 2} width={W - 8 - lab} height="1" fill="var(--grid)" />
                  {[...u.extreme].map((c, t) => c !== "." && (
                    <rect
                      key={t}
                      x={x(t)}
                      y={c === "+" ? 0 : ROW / 2 + 1}
                      width={cw}
                      height={ROW / 2 - 1}
                      fill={c === "+" ? "var(--up)" : "var(--down)"}
                      opacity={inLink && !hits.has(t) ? 0.22 : 0.95}
                      style={{ transition: "opacity 0.3s" }}
                    />
                  ))}
                </motion.g>
              );
            })}
            <AnimatePresence>
              {L && (
                <motion.g
                  key={`${kase.key}-${sel}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1, transition: { delay: 0.3, duration: 0.4 } }}
                  exit={{ opacity: 0, transition: { duration: 0.1 } }}
                  pointerEvents="none"
                >
                  {L.at.map((t) => (
                    <line key={t} x1={x(t + 0.5)} x2={x(t + L.lag + 0.5)} y1={TOP + ROW} y2={TOP + ROW + GAP} stroke="var(--ink)" strokeWidth="1" opacity="0.5" />
                  ))}
                </motion.g>
              )}
            </AnimatePresence>
            {YEAR_TICKS.map((yr) => (
              <text key={yr} className="tick" x={x((yr - 1981) * 12 + 6)} y={H - 2} textAnchor="middle">{yr}</text>
            ))}
          </svg>
          {tip && (
            <Tip x={tip.px} y={tip.py + 14} width={W}>
              <b>{tip.u.extreme[tip.t] === "+" ? "au-dessus de sa norme" : "en dessous de sa norme"}</b>
              <br />
              <span className="k">{rowName(tip.u, multi)} · {monthLabel(tip.u.start, tip.t)}</span>
            </Tip>
          )}
        </div>
        <div className="legend">
          <span><i className="box" style={{ background: "var(--up)" }} />au-dessus du 90ᵉ percentile</span>
          <span><i className="box" style={{ background: "var(--down)" }} />en dessous du 10ᵉ</span>
          <span><i style={{ background: "var(--ink)", opacity: 0.5, width: 2, height: 10 }} />un mois où le lien tient</span>
        </div>

        <div className="links" role="radiogroup" aria-label="Liens trouvés">
          {links.slice(0, more ? links.length : 5).map((l, i) => {
            const A = rowName(byKey[l.a], multi), B = rowName(byKey[l.b], multi);
            const on = i === sel;
            return (
              <motion.button key={`${kase.key}-${i}`} role="radio" aria-checked={on} className={`link${on ? " on" : ""}`} onClick={() => setSel(i)} whileTap={{ scale: 0.99 }}>
                {on && <motion.span layoutId="link-bg" className="bg" transition={SPRING} />}
                <span>
                  {A} ↔ {B}
                  <span className="tag">{l.level === "proven" ? "prouvé" : "suggéré"}</span>
                  {l.union && <span className="tag">une seule dynamique</span>}
                  <br />
                  <span className="how">{how(l, A, B)}</span>
                </span>
                <span className="n">
                  <b>{l.hits}</b> fois, hasard {num(l.expected, 0)}
                  <br />
                  <span className="how">p = {pval(l.p)}</span>
                </span>
              </motion.button>
            );
          })}
        </div>
        {links.length > 5 && (
          <button className="ghost" onClick={() => setMore(!more)}>
            {more ? "Moins de liens" : `Voir les ${links.length} liens`}
          </button>
        )}
        {links.length === 0 && <p className="note">Aucun lien ne passe le seuil dans ce cas.</p>}
        <AnimatePresence mode="wait">
          {L && (
            <motion.p key={`${kase.key}-${sel}`} className="caption" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2, ease: EASE }}>
              {L.union
                ? "Le lien couvre presque toutes leurs sorties de norme, dans les deux sens : Eva les simplifie en une seule dynamique, vue à travers la transformation."
                : `${L.hits} mois où les deux sortent de leur norme comme la transformation le dit ; le hasard au même moment en donnerait ${num(L.expected, 0)}.`}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
      {links.some((l) => l.model) && (
        <p className="note prose">
          Ces séries viennent toutes de la même réanalyse MERRA-2 : un lien entre deux d'entre elles peut venir de la
          construction du modèle. C'est une validation (Eva retrouve sa physique sans qu'on la lui donne), pas une
          découverte, tant qu'un instrument indépendant ne la confirme pas.
        </p>
      )}
    </Section>
  );
}
