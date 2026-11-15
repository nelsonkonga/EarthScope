import { motion } from "motion/react";
import { EASE, Section } from "../components/ui.jsx";

const ITEMS = [
  [
    "Un lien n'est pas une cause.",
    "Il dit que les mêmes mois font bouger deux variables. Un décalage (la pluie d'abord, le sol un mois après) dit l'ordre, pas encore la cause.",
  ],
  [
    "Une réanalyse est un modèle.",
    "Là où les observations manquent, dans les mers polaires surtout, c'est MERRA-2 qui parle. Un lien entre deux de ses variables se confirme avec un instrument indépendant.",
  ],
  [
    "Une piste reste une piste.",
    "Sur les séries très persistantes, le témoin d'Eva se trompe plus souvent : les changements de dynamique qu'elle y voit sont à vérifier avant d'en parler.",
  ],
  [
    "Seules les données de NASA POWER sont lues.",
    "MODIS, GPM ou AIRS passent par les outils Harmony d'earthdata-mcp, qui demandent un compte Earthdata.",
  ],
];

export default function Limits() {
  return (
    <Section n={6} title="Ce qu'Eva ne dit pas">
      <ul className="limits prose">
        {ITEMS.map(([b, t], i) => (
          <motion.li
            key={b}
            initial={{ opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.45, ease: EASE, delay: i * 0.07 }}
          >
            <b>{b}</b> {t}
          </motion.li>
        ))}
      </ul>
    </Section>
  );
}
