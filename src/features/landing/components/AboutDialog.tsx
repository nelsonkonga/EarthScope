import { useEffect, useRef } from "react";
import { format, monthYear, useI18n } from "../../../i18n";
import { useCatalogFacts } from "../hooks/useCatalogFacts";
import { Dialog } from "./Dialog";
import { Icon } from "./Icon";

export type AboutSection = "intro" | "sources" | "methods" | "freshness" | "transparency";

export function AboutDialog({ onClose, section = "intro" }: { onClose: () => void; section?: AboutSection }) {
  const { t, locale } = useI18n();
  const a = t.about;
  const facts = useCatalogFacts();
  const body = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const dates = { start: monthYear(facts.start, locale), end: monthYear(facts.end, locale) };

  useEffect(() => {
    if (section === "intro") return;
    body.current?.querySelector(`#ts-about-${section}`)?.scrollIntoView({ block: "start" });
  }, [section]);

  const jump = (id: AboutSection) => {
    const target = body.current?.querySelector<HTMLElement>(`#ts-about-${id}`);
    target?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    target?.focus({ preventScroll: true });
  };

  return (
    <Dialog labelledBy="ts-about-title" variant="wide" onClose={onClose} initialFocus={closeRef}>
      <header className="ts-panel-head">
        <div>
          <p className="ts-overline">{t.brand}</p>
          <h2 id="ts-about-title">{a.title}</h2>
        </div>
        <button ref={closeRef} type="button" className="ts-icon-btn" onClick={onClose} aria-label={a.close}>
          <Icon name="close" />
        </button>
      </header>
      <nav className="ts-about-tabs" aria-label={a.sectionsLabel}>
        {(Object.keys(a.sections) as AboutSection[]).map((key) => (
          <button key={key} type="button" onClick={() => jump(key)}>
            {a.sections[key]}
          </button>
        ))}
      </nav>
      <div ref={body} className="ts-panel-body ts-about">
        <section id="ts-about-intro" tabIndex={-1} aria-label={a.sections.intro}>
          {a.intro.map((paragraph) => (
            <p key={paragraph} className="ts-about-lead">
              {paragraph}
            </p>
          ))}
        </section>

        <section id="ts-about-sources" tabIndex={-1} aria-labelledby="ts-about-sources-title">
          <h3 id="ts-about-sources-title">{a.sources.title}</h3>
          <p>{a.sources.intro}</p>
          <ul className="ts-source-list">
            {a.sources.items.map((source) => (
              <li key={source.name}>
                <a href={source.url} target="_blank" rel="noreferrer noopener" className="ts-source-name">
                  {source.name}
                  <Icon name="external" size={14} />
                  <span className="ts-sr">({t.dialog.newTab})</span>
                </a>
                <dl>
                  <div>
                    <dt>{a.sources.identifier}</dt>
                    <dd>
                      <code>{source.id}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>{a.sources.role}</dt>
                    <dd>{source.role}</dd>
                  </div>
                  {source.limits && (
                    <div>
                      <dt>{a.sources.limits}</dt>
                      <dd>{source.limits}</dd>
                    </div>
                  )}
                </dl>
              </li>
            ))}
          </ul>
        </section>

        <section id="ts-about-methods" tabIndex={-1} aria-labelledby="ts-about-methods-title">
          <h3 id="ts-about-methods-title">{a.methods.title}</h3>
          <dl className="ts-method-list">
            {a.methods.items.map((method) => (
              <div key={method.name}>
                <dt>{method.name}</dt>
                <dd>{method.text}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section id="ts-about-freshness" tabIndex={-1} aria-labelledby="ts-about-freshness-title">
          <h3 id="ts-about-freshness-title">{a.freshness.title}</h3>
          <p>{format(a.freshness.text, dates)}</p>
        </section>

        <section id="ts-about-transparency" tabIndex={-1} aria-labelledby="ts-about-transparency-title">
          <h3 id="ts-about-transparency-title">{a.transparency.title}</h3>
          <dl className="ts-method-list">
            {a.transparency.items.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{format(item.text, dates)}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </Dialog>
  );
}
