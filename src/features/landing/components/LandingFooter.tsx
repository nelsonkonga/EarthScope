import { format, useI18n } from "../../../i18n";
import { BrandMark } from "./BrandMark";

export function LandingFooter({ onAbout, onAssistant, onEnter, onPolicy }: { onAbout: () => void; onAssistant: () => void; onEnter: () => void; onPolicy: () => void }) {
  const { t } = useI18n();
  const f = t.footer;
  const sources = t.about.sources.items.filter((item) => item.name !== "geoBoundaries");
  return (
    <footer className="ts-footer">
      <div className="ts-shell ts-footer-grid">
        <div className="ts-footer-brand">
          <p className="ts-brand ts-brand-static">
            <BrandMark size={26} />
            <span className="ts-wordmark">{t.brand}</span>
          </p>
          <p className="ts-footer-tagline">{t.tagline}</p>
          <p className="ts-footer-attribution">{f.attribution}</p>
        </div>
        <nav aria-labelledby="ts-footer-nav">
          <p id="ts-footer-nav" className="ts-overline">
            {f.navTitle}
          </p>
          <ul>
            <li>
              <button type="button" className="ts-footer-link" onClick={onEnter}>
                {f.visualize}
              </button>
            </li>
            <li>
              <button type="button" className="ts-footer-link" onClick={onAssistant}>
                {f.assistant}
              </button>
            </li>
            <li>
              <button type="button" className="ts-footer-link" onClick={onAbout}>
                {f.about}
              </button>
            </li>
            <li>
              <button type="button" className="ts-footer-link" onClick={onPolicy}>
                {f.policy}
              </button>
            </li>
          </ul>
        </nav>
        <div>
          <p className="ts-overline">{f.sourcesTitle}</p>
          <ul>
            {sources.map((source) => (
              <li key={source.name}>
                <a className="ts-footer-link" href={source.url} target="_blank" rel="noreferrer noopener">
                  {source.name}
                </a>
              </li>
            ))}
            <li className="ts-footer-small">{f.boundaries}</li>
          </ul>
        </div>
      </div>
      <div className="ts-shell ts-footer-base">
        <p>{format(f.copyright, { year: new Date().getFullYear() })}</p>
        <p>{f.disclaimer}</p>
      </div>
    </footer>
  );
}
