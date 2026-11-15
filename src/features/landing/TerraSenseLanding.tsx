import { useEffect, useState } from 'react';
import { useLandingLanguage, useLandingTheme } from './context/LandingContext';
import { useLandingCatalog } from './api/landingData';
import { SiteHeader } from './components/SiteHeader';
import { HeroSection } from './components/HeroSection';
import { ProblemSection, MissionSection, ScienceSection } from './components/Sections';
import { AboutDialog } from './components/AboutDialog';
import { AssistantDialog, type AssistantController } from './components/AssistantDialog';
import { LiveAssistantDialog } from './components/LiveAssistantDialog';
import { SiteFooter } from './components/SiteFooter';
import { ArrowUpRight } from './components/Icons';
import './styles/terra-sense.css';

export type TerraSenseLandingProps = {
  onNavigateToApp?: () => void;
  /** Optional adapter. Without it the landing connects to the app's own assistant. */
  assistantController?: AssistantController;
};

function useDocumentMeta() {
  const { t, language } = useLandingLanguage();
  const { rawTheme } = useLandingTheme();
  useEffect(() => {
    document.title = t.meta.title;
    document.querySelector('meta[name="description"]')?.setAttribute('content', t.meta.description);
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', t.meta.title);
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', t.meta.description);
    document.querySelector('meta[property="og:locale"]')?.setAttribute('content', language === 'fr' ? 'fr_FR' : 'en_US');
  }, [language, t]);
  useEffect(() => {
    document.body.dataset.surface = 'landing';
    document.body.dataset.theme = rawTheme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', rawTheme === 'dark' ? '#121a16' : rawTheme === 'soft' ? '#f2eee5' : '#f5f8f5');
    return () => {
      delete document.body.dataset.surface;
      delete document.body.dataset.theme;
    };
  }, [rawTheme]);
}

export default function TerraSenseLanding({ onNavigateToApp, assistantController }: TerraSenseLandingProps) {
  const [about, setAbout] = useState<{ open: boolean; section?: 'credits' }>({ open: false });
  const [assistantOpen, setAssistantOpen] = useState(false);
  const catalog = useLandingCatalog();
  const { theme } = useLandingTheme();
  const { t } = useLandingLanguage();
  useDocumentMeta();
  const navigate = onNavigateToApp ?? (() => {
    window.history.pushState({}, '', '/app');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  const openAbout = (section?: 'credits') => setAbout({ open: true, section });

  return (
    <div className="terra-sense-site" data-theme={theme}>
      <a className="ts-skip-link" href="#ts-main">{t.nav.skip}</a>
      <SiteHeader onAbout={() => openAbout()} onAssistant={() => setAssistantOpen(true)} onNavigate={navigate} />
      <main id="ts-main" tabIndex={-1}>
        <HeroSection onNavigate={navigate} catalog={catalog} />
        <ProblemSection />
        <MissionSection onAssistant={() => setAssistantOpen(true)} />
        <ScienceSection catalog={catalog} />
        <section className="ts-closing-cta" aria-labelledby="ts-closing-title">
          <div className="ts-container ts-closing-cta__inner">
            <span className="ts-overline">{t.closing.eyebrow}</span>
            <h2 id="ts-closing-title">{t.closing.title}</h2>
            <button className="ts-button ts-button--light" onClick={navigate} type="button">{t.closing.cta}<ArrowUpRight size={16} /></button>
            <div className="ts-closing-cta__contour" aria-hidden="true"><svg viewBox="0 0 640 260"><path d="M-20 140C100 20 210 30 305 112s180 112 355-4M-30 171C92 52 215 59 312 139s181 113 362 1M-30 203C91 86 222 91 322 169s185 105 358-8M-10 235C112 119 236 122 334 198s177 99 338-10"/></svg></div>
          </div>
        </section>
      </main>
      <SiteFooter onAbout={() => openAbout()} onCredits={() => openAbout('credits')} onAssistant={() => setAssistantOpen(true)} onNavigate={navigate} />
      <AboutDialog open={about.open} section={about.section} catalog={catalog} onClose={() => setAbout({ open: false })} />
      {assistantOpen && (assistantController
        ? <AssistantDialog open onClose={() => setAssistantOpen(false)} controller={assistantController} />
        : <LiveAssistantDialog onClose={() => setAssistantOpen(false)} />)}
    </div>
  );
}
