import type { LandingCatalog } from '../api/landingData';
import { format, useLandingLanguage } from '../context/LandingContext';
import { AccessibleDialog } from './AccessibleDialog';
import { ArrowUpRight, CheckIcon } from './Icons';
import { Photo } from './Photo';

export function AboutDialog({ open, onClose, catalog }: { open: boolean; onClose: () => void; catalog: LandingCatalog }) {
  const { t, locale } = useLandingLanguage();
  const month = (value?: string) => (value ? new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(value)) : '—');
  const dates = { start: month(catalog.periodStart), end: month(catalog.periodEnd) };


  return (
    <AccessibleDialog open={open} onClose={onClose} title={t.about.title} size="large">
      <div className="ts-about-content">
        <Photo slot="fieldwork" className="ts-about-photo" sizes="(max-width: 900px) 100vw, 760px" />
        <p className="ts-dialog-lead">{t.about.intro}</p>
        <div className="ts-about-grid">
          <section className="ts-about-block"><span className="ts-overline">{t.about.scopeLabel}</span><h3>{t.about.scopeTitle}</h3><p>{format(t.about.scopeText, dates)}</p></section>
          <section className="ts-about-block"><h3>{t.about.kindsTitle}</h3><p>{t.about.kindsText}</p></section>
          <section className="ts-about-block ts-about-block--sources"><span className="ts-overline">{t.about.sourcesLabel}</span><h3>{t.about.sourcesTitle}</h3><p>{t.about.sourcesText}</p>
            <ul className="ts-about-source-list">
              {t.about.sources.map((source) => (
                <li key={source.name}>
                  <a href={source.url} target="_blank" rel="noreferrer noopener">{source.name} <ArrowUpRight size={14} /><span className="ts-sr-only"> ({t.common.externalLink})</span></a>
                  <span>{source.detail}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className="ts-about-block ts-about-methods"><span className="ts-overline">{t.about.methodLabel}</span><h3>{t.about.methodTitle}</h3>
            <article><h4>{t.about.mkTitle}</h4><p>{t.about.mkText}</p></article>
            <article><h4>{t.about.tsTitle}</h4><p>{t.about.tsText}</p></article>
            <article><h4>{t.about.shapTitle}</h4><p>{t.about.shapText}</p></article>
          </section>
          <section className="ts-about-block ts-about-block--note"><span className="ts-about-check" aria-hidden="true"><CheckIcon /></span><div><h3>{t.about.updatedTitle}</h3><p>{format(t.about.updatedText, dates)}</p></div></section>
        </div>
        <p className="ts-about-disclaimer">{t.about.disclaimer}</p>
      </div>
    </AccessibleDialog>
  );
}
