import { useI18n } from "../../../i18n";
import { useReveal } from "../hooks/useReveal";
import { Icon } from "./Icon";
import { TrendFigure } from "./TrendFigure";

export function MissionSection({ onAssistant }: { onAssistant: () => void }) {
  const { t } = useI18n();
  const m = t.mission;
  const intro = useReveal<HTMLDivElement>();
  const observe = useReveal<HTMLElement>();
  const trends = useReveal<HTMLElement>();
  const understand = useReveal<HTMLElement>();
  return (
    <section className="ts-section ts-mission" id="approche" aria-labelledby="ts-mission-title" tabIndex={-1}>
      <div className="ts-shell">
        <div ref={intro.ref} className={`ts-mission-intro ${intro.revealClass}`}>
          <p className="ts-overline">{m.eyebrow}</p>
          <h2 id="ts-mission-title" className="ts-heading ts-heading-xl">
            {m.titleStart} <span className="ts-accent-text">{m.titleMark}</span>
          </h2>
          <p className="ts-section-lead">{m.lead}</p>
        </div>

        <div className="ts-capabilities">
          <article ref={trends.ref} className={`ts-capability ts-capability-trends ${trends.revealClass}`} aria-labelledby="ts-cap-trends">
            <div className="ts-capability-text">
              <p className="ts-kicker">
                <Icon name="trend" size={18} />
                {m.trends.kicker}
              </p>
              <h3 id="ts-cap-trends">{m.trends.title}</h3>
              <p>{m.trends.text}</p>
            </div>
            <TrendFigure />
          </article>

          <article ref={observe.ref} className={`ts-capability ts-capability-observe ${observe.revealClass}`} aria-labelledby="ts-cap-observe">
            <p className="ts-kicker">
              <Icon name="satellite" size={18} />
              {m.observe.kicker}
            </p>
            <h3 id="ts-cap-observe">{m.observe.title}</h3>
            <p>{m.observe.text}</p>
            <ul className="ts-datasets">
              {m.observe.datasets.map((dataset) => (
                <li key={dataset.id}>
                  <code>{dataset.id}</code>
                  <span>{dataset.what}</span>
                </li>
              ))}
            </ul>
          </article>

          <article ref={understand.ref} className={`ts-capability ts-capability-understand ${understand.revealClass}`} aria-labelledby="ts-cap-understand">
            <p className="ts-kicker">
              <Icon name="dialogue" size={18} />
              {m.understand.kicker}
            </p>
            <h3 id="ts-cap-understand">{m.understand.title}</h3>
            <p>{m.understand.text}</p>
            <button type="button" className="ts-secondary" onClick={onAssistant}>
              <Icon name="chat" size={18} />
              {m.understand.ask}
            </button>
            <p className="ts-future">
              <span className="ts-future-tag">SHAP</span>
              {m.understand.future}
            </p>
          </article>
        </div>
      </div>
    </section>
  );
}
