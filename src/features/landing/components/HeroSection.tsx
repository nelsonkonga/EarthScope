import { format, monthYear, useI18n } from "../../../i18n";
import { useCatalogFacts } from "../hooks/useCatalogFacts";
import { Icon } from "./Icon";
import { ScientificVisual } from "./ScientificVisual";

export function HeroSection({ onEnter, onApproach }: { onEnter: () => void; onApproach: () => void }) {
  const { t, locale } = useI18n();
  const facts = useCatalogFacts();
  const h = t.hero;
  const items = [
    { value: format(h.facts.coverage, { start: monthYear(facts.start, locale, "short"), end: monthYear(facts.end, locale, "short") }), label: h.facts.coverageLabel },
    { value: h.facts.cadence, label: h.facts.cadenceLabel },
    { value: h.facts.resolution, label: h.facts.resolutionLabel },
    { value: h.facts.methods, label: h.facts.methodsLabel },
  ];
  return (
    <section className="ts-hero" aria-labelledby="ts-hero-title" id="top">
      <div className="ts-hero-atmosphere" aria-hidden="true">
        <div className="ts-hero-grid" />
        <div className="ts-field ts-field-sage" />
        <div className="ts-field ts-field-amber" />
        <div className="ts-field ts-field-water" />
      </div>
      <div className="ts-shell ts-hero-layout">
        <div className="ts-hero-copy">
          <p className="ts-badge">
            <span className="ts-badge-dot" aria-hidden="true" />
            {h.badge}
          </p>
          <h1 id="ts-hero-title" className="ts-display">
            <span className="ts-line">
              {h.titleStart} <mark className="ts-mark-amber">{h.titleMark}</mark>
            </span>{" "}
            <span className="ts-line ts-line-quiet">{h.titleEnd}</span>
          </h1>
          <p className="ts-hero-lead">{h.lead}</p>
          <div className="ts-hero-actions">
            <button type="button" className="ts-primary ts-primary-lg" onClick={onEnter} aria-describedby="ts-cta-hint">
              {h.cta}
              <Icon name="arrow" size={18} />
            </button>
            <button type="button" className="ts-link-action" onClick={onApproach}>
              {h.secondary}
              <Icon name="arrowDown" size={16} />
            </button>
          </div>
          <p id="ts-cta-hint" className="ts-cta-hint">
            {h.ctaHint}
          </p>
        </div>
        <div className="ts-hero-visual">
          <ScientificVisual />
        </div>
        <div className="ts-facts">
          <dl aria-label={h.factsLabel}>
            {items.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
          <p className="ts-facts-source">{h.factsSource}</p>
        </div>
      </div>
    </section>
  );
}
