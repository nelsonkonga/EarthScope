import { useLandingLanguage } from '../context/LandingContext';
import { PHOTOS } from '../photos';
import { BrandMark } from './BrandMark';
import { ArrowUpRight } from './Icons';

export function SiteFooter({ onAbout, onCredits, onAssistant, onNavigate }: { onAbout: () => void; onCredits: () => void; onAssistant: () => void; onNavigate: () => void }) {
  const { t } = useLandingLanguage();
  const hasPhotos = Object.keys(PHOTOS).length > 0;
  return (
    <footer className="ts-footer">
      <div className="ts-container">
        <div className="ts-footer__main">
          <div className="ts-footer__brand"><BrandMark /><p>{t.footer.tagline}</p><span className="ts-footer__attribution">{t.footer.project}</span></div>
          <nav className="ts-footer__column" aria-label={t.footer.links}>
            <span className="ts-overline">{t.footer.links}</span>
            <button type="button" onClick={onNavigate}>{t.footer.visualization}</button>
            <button type="button" onClick={onAssistant}>{t.footer.assistant}</button>
            <button type="button" onClick={onAbout}>{t.footer.about}</button>
            <button type="button" onClick={onAbout}>{t.footer.dataPolicy}</button>
            {hasPhotos && <button type="button" onClick={onCredits}>{t.footer.photoCredits}</button>}
          </nav>
          <div className="ts-footer__column">
            <span className="ts-overline">{t.footer.resources}</span>
            {t.about.sources.slice(0, 5).map((source) => (
              <a key={source.name} href={source.url} target="_blank" rel="noreferrer noopener">{source.name} <ArrowUpRight size={13} /><span className="ts-sr-only"> ({t.common.externalLink})</span></a>
            ))}
          </div>
        </div>
        <div className="ts-footer__bottom"><span>© {new Date().getFullYear()} Terra Sense. {t.footer.copyright}</span><span className="ts-footer__signature">SOIL TREND DETECTIVE <i aria-hidden="true" /> {t.footer.signature}</span></div>
      </div>
    </footer>
  );
}
