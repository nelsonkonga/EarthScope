import { useEffect, useState } from "react";
import { navigate } from "../../app/router";
import { useI18n } from "../../i18n";
import { ThemeProvider, useTheme } from "../theme/theme";
import { AboutDialog, type AboutSection } from "./components/AboutDialog";
import { AssistantDrawer } from "./components/AssistantDrawer";
import { ClosingSection } from "./components/ClosingSection";
import { HeroSection } from "./components/HeroSection";
import { LandingFooter } from "./components/LandingFooter";
import { LandingHeader } from "./components/LandingHeader";
import { MissionSection } from "./components/MissionSection";
import { ProblemSection } from "./components/ProblemSection";
import "./styles/landing.css";

type Panel = { kind: "about"; section: AboutSection } | { kind: "assistant" } | null;

function useDocumentMeta() {
  const { t, locale } = useI18n();
  useEffect(() => {
    document.title = t.meta.title;
    const set = (selector: string, attribute: string, value: string) => {
      document.querySelector(selector)?.setAttribute(attribute, value);
    };
    set('meta[name="description"]', "content", t.meta.description);
    set('meta[property="og:title"]', "content", t.meta.title);
    set('meta[property="og:description"]', "content", t.meta.description);
    set('meta[property="og:locale"]', "content", locale === "fr" ? "fr_FR" : "en_GB");
  }, [locale, t]);
}

function Landing() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const [panel, setPanel] = useState<Panel>(null);
  useDocumentMeta();

  useEffect(() => {
    document.body.dataset.surface = "landing";
    document.body.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#121a16" : theme === "soft" ? "#f1ebdf" : "#f5f8f5");
    return () => {
      delete document.body.dataset.surface;
      delete document.body.dataset.theme;
    };
  }, [theme]);

  const enter = () => navigate("/app");
  const about = (section: AboutSection = "intro") => setPanel({ kind: "about", section });
  const assistant = () => setPanel({ kind: "assistant" });
  const approach = () => {
    const target = document.getElementById("approche");
    target?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    target?.focus({ preventScroll: true });
  };

  return (
    <div className="landing" data-theme={theme}>
      <a className="ts-skip" href="#ts-main">
        {t.skip}
      </a>
      <LandingHeader onAbout={() => about()} onAssistant={assistant} onEnter={enter} />
      <main id="ts-main" tabIndex={-1}>
        <HeroSection onEnter={enter} onApproach={approach} />
        <ProblemSection />
        <MissionSection onAssistant={assistant} />
        <ClosingSection onEnter={enter} />
      </main>
      <LandingFooter onAbout={() => about()} onAssistant={assistant} onEnter={enter} onPolicy={() => about("transparency")} />
      {panel?.kind === "about" && <AboutDialog section={panel.section} onClose={() => setPanel(null)} />}
      {panel?.kind === "assistant" && <AssistantDrawer onClose={() => setPanel(null)} onAbout={() => about("sources")} />}
    </div>
  );
}

export function LandingPage() {
  return (
    <ThemeProvider>
      <Landing />
    </ThemeProvider>
  );
}
