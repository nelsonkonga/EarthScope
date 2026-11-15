import { useEffect, useState } from 'react';
import { useLandingLanguage, useLandingTheme } from '../context/LandingContext';
import { BrandMark } from './BrandMark';
import { ArrowUpRight, MenuIcon, MessageIcon, SunMoon } from './Icons';
import { AccessibleDialog } from './AccessibleDialog';

function LanguageSwitch() {
  const { language, setLanguage, t } = useLandingLanguage();
  return (
    <div className="ts-language-switch" role="group" aria-label={t.nav.language}>
      <button type="button" lang="fr" onClick={() => setLanguage('fr')} aria-pressed={language === 'fr'} aria-label={t.common.frName}>{t.common.fr}</button>
      <span aria-hidden="true" />
      <button type="button" lang="en" onClick={() => setLanguage('en')} aria-pressed={language === 'en'} aria-label={t.common.enName}>{t.common.en}</button>
    </div>
  );
}

export function SiteHeader({ onAbout, onAssistant, onNavigate }: { onAbout: () => void; onAssistant: () => void; onNavigate: () => void }) {
  const { t } = useLandingLanguage();
  const { theme, cycleTheme } = useLandingTheme();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 12);
    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const choose = (action: () => void) => {
    setMobileOpen(false);
    action();
  };

  return (
    <>
      <header className={`ts-header ${scrolled ? 'ts-header--scrolled' : ''}`}>
        <div className="ts-header__inner">
          <a className="ts-header__brand" href="#top" onClick={(event) => { event.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); }} aria-label={t.nav.homeLabel}>
            <BrandMark />
          </a>
          <nav className="ts-header__nav" aria-label={t.nav.navigationLabel}>
            <button type="button" className="ts-nav-link" onClick={onAbout}>{t.nav.about}</button>
            <button type="button" className="ts-nav-link ts-nav-link--assistant" onClick={onAssistant}><MessageIcon size={16} />{t.nav.assistant}</button>
            <div className="ts-header__utilities">
              <LanguageSwitch />
              <button type="button" className="ts-icon-button ts-theme-button" onClick={cycleTheme} aria-label={`${t.nav.theme}: ${theme === 'light' ? t.common.light : theme === 'dark' ? t.common.dark : t.common.dusk}`} title={theme === 'light' ? t.common.light : theme === 'dark' ? t.common.dark : t.common.dusk}>
                <SunMoon />
              </button>
            </div>
            <button type="button" className="ts-button ts-button--small" onClick={onNavigate}>{t.nav.visualization}<ArrowUpRight size={15} /></button>
          </nav>
          <button type="button" className="ts-mobile-menu-button" onClick={() => setMobileOpen(true)} aria-label={t.nav.menu} aria-haspopup="dialog" aria-expanded={mobileOpen}><MenuIcon /></button>
        </div>
      </header>
      <AccessibleDialog open={mobileOpen} onClose={() => setMobileOpen(false)} title="Terra Sense" size="medium">
        <div className="ts-mobile-menu">
          <button type="button" onClick={() => choose(onAbout)}>{t.nav.about}</button>
          <button type="button" onClick={() => choose(onAssistant)}>{t.nav.assistant}</button>
          <div className="ts-mobile-menu__row">
            <span>{t.nav.language}</span>
            <LanguageSwitch />
          </div>
          <div className="ts-mobile-menu__row">
            <span>{t.nav.theme}</span>
            <button type="button" className="ts-mobile-theme" onClick={cycleTheme}><SunMoon />{theme === 'light' ? t.common.light : theme === 'dark' ? t.common.dark : t.common.dusk}</button>
          </div>
          <button type="button" className="ts-button" onClick={() => choose(onNavigate)}>{t.nav.visualization}<ArrowUpRight size={15} /></button>
        </div>
      </AccessibleDialog>
    </>
  );
}
