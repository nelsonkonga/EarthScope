import type { LandingCatalog } from '../api/landingData';
import { useLandingLanguage } from '../context/LandingContext';
import { ArrowRight, ArrowUpRight } from './Icons';
import { HeroArtwork } from './BrandMark';
import { Photo, hasPhoto } from './Photo';

function year(value: string | undefined) {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value.slice(0, 4) : String(date.getUTCFullYear());
}

export function HeroSection({ onNavigate, catalog }: { onNavigate: () => void; catalog: LandingCatalog }) {
  const { t, locale } = useLandingLanguage();
  const period = catalog.periodStart && catalog.periodEnd ? `${year(catalog.periodStart)} – ${year(catalog.periodEnd)}` : undefined;
  const count = (value: number) => (catalog.isCatalogLoading ? '···' : catalog.isCatalogError ? '—' : value.toLocaleString(locale));
  const withPhoto = hasPhoto('hero');

  return (
    <section className={`ts-hero ${withPhoto ? 'ts-hero--photo' : ''}`} id="top" aria-labelledby="ts-hero-title">
      <div className="ts-hero__ambient ts-hero__ambient--one" aria-hidden="true" />
      <div className="ts-hero__ambient ts-hero__ambient--two" aria-hidden="true" />
      <div className="ts-container ts-hero__grid">
        <div className="ts-hero__copy">
          <div className="ts-challenge-badge"><span className="ts-live-dot" aria-hidden="true" />{t.hero.eyebrow}</div>
          <h1 id="ts-hero-title"><span>{t.hero.titleA}</span><span className="ts-hero__headline-middle">{t.hero.titleB}</span><em>{t.hero.titleC}</em></h1>
          <p className="ts-hero__description">{t.hero.description}</p>
          <div className="ts-hero__actions">
            <button className="ts-button ts-button--hero" type="button" onClick={onNavigate} aria-describedby="ts-hero-cta-hint">{t.hero.primaryCta}<ArrowUpRight size={17} /></button>
            <a className="ts-text-link" href="#mission">{t.hero.secondaryCta}<ArrowRight size={15} /></a>
          </div>
          <p id="ts-hero-cta-hint" className="ts-hero__cta-hint">{t.hero.primaryCtaHint}</p>
          <dl className="ts-hero__metrics" aria-live="polite">
            <div className="ts-metric"><dt>{t.hero.zones}</dt><dd>{count(catalog.zones.length)}</dd></div>
            <div className="ts-metric"><dt>{t.hero.variables}</dt><dd>{count(catalog.variables.length)}</dd></div>
            <div className="ts-metric"><dt>{t.hero.period}</dt><dd className="ts-metric__period">{catalog.isCatalogLoading ? '···' : catalog.isCatalogError ? '—' : period ?? t.hero.periodUnavailable}</dd></div>
          </dl>
          <p className="ts-hero__data-note">{catalog.isCatalogError ? t.hero.catalogUnavailable : catalog.isCatalogLoading ? t.hero.catalogLoading : t.hero.dataNote}</p>
        </div>
        <div className="ts-hero__visual">
          {withPhoto && <Photo slot="hero" priority className="ts-hero__photo" sizes="(max-width: 900px) 100vw, 52vw" />}
          <HeroArtwork />
          <div className="ts-hero__visual-note"><span className="ts-hero__visual-note-dot" aria-hidden="true" /><div><strong>{t.hero.visualLabel}</strong><span>{t.hero.visualCaption}</span></div></div>
        </div>
      </div>
      <div className="ts-hero__footline"><span>01 — 04</span><span>{t.hero.sequence}</span><a href="#problem"><span aria-hidden="true" />{t.hero.scrollNext}</a></div>
    </section>
  );
}
