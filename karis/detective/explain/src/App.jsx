import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import DATA from "./data/cases.json";
import { Chips, EASE } from "./components/ui.jsx";
import Levels from "./sections/Levels.jsx";
import Trend from "./sections/Trend.jsx";
import Change from "./sections/Change.jsx";
import Norm from "./sections/Norm.jsx";
import Together from "./sections/Together.jsx";
import Limits from "./sections/Limits.jsx";

export default function App() {
  const [caseKey, setCaseKey] = useState("arctic");
  const kase = DATA.cases.find((c) => c.key === caseKey);
  const [unitKey, setUnitKey] = useState(kase.units[0].key);
  const unit = kase.units.find((u) => u.key === unitKey) || kase.units[0];

  const pickCase = (k) => {
    setCaseKey(k);
    const c = DATA.cases.find((x) => x.key === k);
    // keep the same variable when the new case has it
    const same = c.units.find((u) => u.var === unit.var);
    setUnitKey((same || c.units[0]).key);
  };

  const multiRegion = kase.regions.length > 1;
  const unitItems = useMemo(
    () => kase.units.map((u) => ({ value: u.key, label: multiRegion ? `${u.short} · ${u.region.replace("Mer de ", "")}` : u.label })),
    [kase, multiRegion],
  );

  // the picker gets a hairline once it sticks to the top
  const sentinel = useRef(null);
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const io = new IntersectionObserver(([e]) => setStuck(!e.isIntersecting));
    if (sentinel.current) io.observe(sentinel.current);
    return () => io.disconnect();
  }, []);

  return (
    <>
      <header className="wrap hero">
        <p className="overline">NASA Space Apps 2026 · Be an Earth System Trend Detective!</p>
        <h1>Comment Eva lit les tendances de la Terre</h1>
        <p className="prose">
          Eva ne connaît aucune règle de climat. Elle lit 45 ans de données de la NASA comme le reste :
          en cherchant des dynamiques, leur norme, et ce qui en sort ensemble. Choisissez un cas et une
          variable, toute la page les suit.
        </p>
      </header>
      <div ref={sentinel} />
      <nav className={`picker${stuck ? " stuck" : ""}`} aria-label="Cas étudié">
        <div className="wrap">
          <Chips id="case" label="Région" items={DATA.cases.map((c) => ({ value: c.key, label: c.title }))} value={caseKey} onChange={pickCase} />
          <Chips id="unit" label="Variable" small items={unitItems} value={unit.key} onChange={setUnitKey} />
        </div>
      </nav>

      <main className="wrap">
        <AnimatePresence mode="wait">
          <motion.p
            key={kase.key}
            className="prose"
            style={{ color: "var(--ink-2)", margin: "20px 0 0", fontSize: 15 }}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.25, ease: EASE }}
          >
            {kase.lead}
          </motion.p>
        </AnimatePresence>
        <Levels unit={unit} />
        <Trend unit={unit} />
        <Change unit={unit} amazon={DATA.amazon} control={DATA.control} />
        <Norm unit={unit} />
        <Together kase={kase} unit={unit} />
        <Limits />
      </main>

      <footer className="wrap">
        <p className="prose">
          Données : NASA POWER (réanalyse MERRA-2 et flux CERES), mensuelles 1981–2025 ; catalogue CMR de la NASA
          interrogé avec le serveur earthdata-mcp. Chiffres : <code>RESULTS.md</code> § 24 et § 27 du dépôt Eva3.
        </p>
        <p className="prose">
          Refaire une enquête : <code>python -m detective investigate --region sahel --vars PRECTOTCORR,GWETROOT</code>.
          Régénérer cette page : <code>cd detective/explain && npm run data && npm run build</code>.
        </p>
      </footer>
    </>
  );
}
