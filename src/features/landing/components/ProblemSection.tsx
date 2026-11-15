import { useI18n } from "../../../i18n";
import { useReveal } from "../hooks/useReveal";
import { Icon, type IconName } from "./Icon";

function ImpactCard({ index, icon, title, text, note }: { index: number; icon: string; title: string; text: string; note?: string }) {
  const { ref, revealClass } = useReveal<HTMLLIElement>();
  return (
    <li ref={ref} className={`ts-impact ts-impact-${index + 1} ${revealClass}`} style={{ transitionDelay: `${index * 90}ms` }}>
      <span className="ts-impact-index" aria-hidden="true">
        {String(index + 1).padStart(2, "0")}
      </span>
      <span className="ts-impact-icon" aria-hidden="true">
        <Icon name={icon as IconName} size={26} />
      </span>
      <div className="ts-impact-body">
        <h3>{title}</h3>
        <p>{text}</p>
        {note && (
          <p className="ts-impact-note">
            <Icon name="info" size={16} />
            <span>{note}</span>
          </p>
        )}
      </div>
    </li>
  );
}

export function ProblemSection() {
  const { t } = useI18n();
  const { ref, revealClass } = useReveal<HTMLDivElement>();
  return (
    <section className="ts-section ts-problem" aria-labelledby="ts-problem-title">
      <div className="ts-shell ts-problem-layout">
        <div ref={ref} className={`ts-problem-intro ${revealClass}`}>
          <p className="ts-overline">{t.problem.eyebrow}</p>
          <h2 id="ts-problem-title" className="ts-heading">
            {t.problem.title}
          </h2>
          <p className="ts-section-lead">{t.problem.lead}</p>
        </div>
        <ol className="ts-impacts">
          {t.problem.items.map((item, index) => (
            <ImpactCard key={item.title} index={index} {...item} />
          ))}
        </ol>
      </div>
    </section>
  );
}
