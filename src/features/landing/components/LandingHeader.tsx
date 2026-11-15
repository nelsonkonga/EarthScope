import { useEffect, useRef, useState } from "react";
import { THEMES, useTheme, type Theme } from "../../theme/theme";
import { useI18n, type Locale } from "../../../i18n";
import { BrandMark } from "./BrandMark";
import { Dialog } from "./Dialog";
import { Icon, type IconName } from "./Icon";

const THEME_ICON: Record<Theme, IconName> = { light: "sun", dark: "moon", soft: "soft" };

function LanguageSwitch() {
  const { locale, setLocale, t } = useI18n();
  return (
    <div className="ts-segment" role="group" aria-label={t.nav.language}>
      {(["fr", "en"] as Locale[]).map((code) => (
        <button key={code} type="button" lang={code} aria-pressed={locale === code} aria-label={t.nav.languageNames[code]} onClick={() => setLocale(code)}>
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

function ThemeSwitch({ withLabels = false }: { withLabels?: boolean }) {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();
  return (
    <div className={withLabels ? "ts-segment ts-segment-labelled" : "ts-segment"} role="group" aria-label={t.nav.theme}>
      {THEMES.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={theme === option}
          aria-label={withLabels ? undefined : t.nav.themes[option]}
          title={t.nav.themes[option]}
          onClick={() => setTheme(option)}
        >
          <Icon name={THEME_ICON[option]} size={17} />
          {withLabels && <span>{t.nav.themes[option]}</span>}
        </button>
      ))}
    </div>
  );
}

export function LandingHeader({ onAbout, onAssistant, onEnter }: { onAbout: () => void; onAssistant: () => void; onEnter: () => void }) {
  const { t } = useI18n();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const sentinel = useRef<HTMLDivElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const node = sentinel.current;
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => setScrolled(!entry.isIntersecting));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const fromMenu = (action: () => void) => () => {
    setMenuOpen(false);
    window.setTimeout(action, 0);
  };

  return (
    <>
      <div ref={sentinel} className="ts-sentinel" aria-hidden="true" />
      <header className={scrolled ? "ts-header is-scrolled" : "ts-header"}>
        <div className="ts-header-inner">
          <a
            className="ts-brand"
            href="#top"
            aria-label={t.nav.home}
            onClick={(event) => {
              event.preventDefault();
              window.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
            }}
          >
            <BrandMark />
            <span className="ts-wordmark">{t.brand}</span>
          </a>
          <nav className="ts-nav" aria-label={t.nav.label}>
            <LanguageSwitch />
            <ThemeSwitch />
            <span className="ts-nav-rule" aria-hidden="true" />
            <button type="button" className="ts-quiet" onClick={onAbout}>
              {t.nav.about}
            </button>
            <button type="button" className="ts-quiet" onClick={onAssistant} aria-label={t.nav.assistantLabel}>
              <Icon name="chat" size={18} />
              <span>{t.nav.assistant}</span>
            </button>
            <button type="button" className="ts-primary" onClick={onEnter} aria-label={t.nav.visualizeLabel}>
              {t.nav.visualize}
              <Icon name="arrow" size={16} />
            </button>
          </nav>
          <button ref={menuButton} type="button" className="ts-menu-btn" onClick={() => setMenuOpen(true)} aria-label={t.nav.menu} aria-expanded={menuOpen} aria-haspopup="dialog">
            <Icon name="menu" size={22} />
          </button>
        </div>
      </header>
      {menuOpen && (
        <Dialog labelledBy="ts-menu-title" variant="menu" onClose={() => setMenuOpen(false)}>
          <div className="ts-menu-head">
            <span id="ts-menu-title" className="ts-brand ts-brand-static">
              <BrandMark size={24} />
              <span className="ts-wordmark">{t.brand}</span>
            </span>
            <button type="button" className="ts-icon-btn" onClick={() => setMenuOpen(false)} aria-label={t.nav.closeMenu}>
              <Icon name="close" />
            </button>
          </div>
          <div className="ts-menu-body">
            <button type="button" className="ts-primary ts-primary-block" onClick={fromMenu(onEnter)}>
              {t.nav.visualize}
              <Icon name="arrow" size={16} />
            </button>
            <button type="button" className="ts-menu-link" onClick={fromMenu(onAssistant)}>
              <Icon name="chat" />
              {t.nav.assistant}
            </button>
            <button type="button" className="ts-menu-link" onClick={fromMenu(onAbout)}>
              <Icon name="info" />
              {t.nav.about}
            </button>
            <div className="ts-menu-group">
              <p className="ts-overline">{t.nav.language}</p>
              <LanguageSwitch />
            </div>
            <div className="ts-menu-group">
              <p className="ts-overline">{t.nav.theme}</p>
              <ThemeSwitch withLabels />
            </div>
          </div>
        </Dialog>
      )}
    </>
  );
}
