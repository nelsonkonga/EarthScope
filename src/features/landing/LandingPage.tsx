import { useEffect, useRef, useState, type ReactNode } from "react";
import { useVariableCatalog } from "../../api/queries";
import { navigate } from "../../app/router";
import { format, useLocale, type Dictionary, type Locale } from "../../i18n";
import { LandingAssistant } from "./LandingAssistant";
import { LandingIcon, type LandingIconName } from "./LandingIcons";
import "./landing.css";

type Theme = "light" | "dark" | "dim";
const THEME_KEY = "terrasense.theme";
const THEMES: Theme[] = ["light", "dark", "dim"];

/** Values of the published catalog. Used until the API answers, and if it never does. */
const FALLBACK = { start: "2002-07-01", end: "2014-11-01", count: 7 };

function readTheme(): Theme {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === "dark" || value === "dim" ? value : "light";
  } catch {
    return "light";
  }
}

function monthYear(date: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "fr" ? "fr-FR" : "en-GB", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(date));
}

function useCatalogFacts() {
  const variables = useVariableCatalog();
  const list = variables.data?.variables ?? [];
  const monthly = list.filter((variable) => variable.defaultResolution === "month");
  const pool = monthly.length ? monthly : list;
  if (pool.length === 0) return FALLBACK;
  const start = pool.map((variable) => variable.availableDateRange.start).sort()[0];
  const end = pool.map((variable) => variable.availableDateRange.end).sort().at(-1) ?? FALLBACK.end;
  return { start, end, count: list.length };
}

/** Slide-over used for About. Escape and the backdrop close it; focus returns to the opener. */
function Drawer({ label, onClose, children, wide = false }: { label: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
    };
    window.addEventListener("keydown", onKey);
    document.body.classList.add("ts-locked");
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.classList.remove("ts-locked");
      opener?.focus?.();
    };
  }, []);
  return (
    <div className="ts-overlay">
      <div className="ts-backdrop" onClick={onClose} aria-hidden="true" />
      <div className={wide ? "ts-drawer-wrap is-wide" : "ts-drawer-wrap"} aria-label={label}>
        {children}
      </div>
    </div>
  );
}

function About({ t, facts, locale, onClose }: { t: Dictionary; facts: typeof FALLBACK; locale: Locale; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => closeRef.current?.focus(), []);
  return (
    <div className="ts-drawer ts-about" role="dialog" aria-modal="true" aria-labelledby="ts-about-title">
      <header className="ts-drawer-head">
        <h2 id="ts-about-title">{t.about.title}</h2>
        <button ref={closeRef} type="button" className="ts-icon-btn" onClick={onClose} aria-label={t.about.close}>
          <LandingIcon name="close" />
        </button>
      </header>
      <div className="ts-drawer-body">
        {t.about.intro.map((paragraph) => (
          <p key={paragraph}>{paragraph}</p>
        ))}
        <h3 id="sources">{t.about.sourcesTitle}</h3>
        <ul className="ts-sources">
          {t.about.sources.map((source) => (
            <li key={source.name}>
              <a href={source.url} target="_blank" rel="noreferrer noopener">
                {source.name}
                <LandingIcon name="external" size={14} />
              </a>
              <span>{source.detail}</span>
            </li>
          ))}
        </ul>
        <h3>{t.about.methodTitle}</h3>
        <dl className="ts-methods">
          {t.about.methods.map((method) => (
            <div key={method.name}>
              <dt>{method.name}</dt>
              <dd>{method.text}</dd>
            </div>
          ))}
        </dl>
        <h3>{t.about.updatedTitle}</h3>
        <p>{format(t.about.updated, { start: monthYear(facts.start, locale), end: monthYear(facts.end, locale) })}</p>
      </div>
    </div>
  );
}

function Card({ icon, title, tag, text }: { icon: string; title: string; tag?: string; text: string }) {
  return (
    <article className="ts-card">
      <span className="ts-card-icon">
        <LandingIcon name={icon as LandingIconName} size={24} />
      </span>
      <h3>{title}</h3>
      {tag && <p className="ts-tag">{tag}</p>}
      <p>{text}</p>
    </article>
  );
}

export function LandingPage() {
  const { locale, setLocale, t } = useLocale();
  const [theme, setTheme] = useState<Theme>(readTheme);
  const [panel, setPanel] = useState<"about" | "assistant" | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const sentinel = useRef<HTMLDivElement>(null);
  const facts = useCatalogFacts();
  const years = Math.max(1, Math.round((Date.parse(facts.end) - Date.parse(facts.start)) / (365.25 * 864e5)));

  useEffect(() => {
    document.title = `${t.brand} · ${locale === "fr" ? "Observatoire du stress hydrique des sols" : "Soil water stress observatory"}`;
  }, [locale, t.brand]);

  useEffect(() => {
    document.body.dataset.surface = "landing";
    document.body.dataset.theme = theme;
    return () => {
      delete document.body.dataset.surface;
      delete document.body.dataset.theme;
    };
  }, [theme]);

  useEffect(() => {
    const target = sentinel.current;
    if (!target) return;
    const observer = new IntersectionObserver(([entry]) => setScrolled(!entry.isIntersecting));
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  const chooseTheme = (next: Theme) => {
    setTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* the choice lasts for this page only */
    }
  };

  const open = (next: "about" | "assistant") => {
    setMenuOpen(false);
    setPanel(next);
  };

  const enter = () => navigate("/app");
  const themeLabel: Record<Theme, string> = { light: t.nav.themeLight, dark: t.nav.themeDark, dim: t.nav.themeDim };
  const themeIcon: Record<Theme, LandingIconName> = { light: "sun", dark: "moon", dim: "dim" };
  const nextTheme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];

  const actions = (
    <>
      <div className="ts-segment" role="group" aria-label={t.nav.language}>
        {(["fr", "en"] as const).map((code) => (
          <button key={code} type="button" aria-pressed={locale === code} onClick={() => setLocale(code)} lang={code}>
            {code.toUpperCase()}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="ts-icon-btn"
        onClick={() => chooseTheme(nextTheme)}
        aria-label={`${t.nav.theme} : ${themeLabel[theme]}. ${themeLabel[nextTheme]} ?`}
        title={`${t.nav.theme} : ${themeLabel[theme]}`}
      >
        <LandingIcon name={themeIcon[theme]} />
      </button>
      <button type="button" className="ts-text-btn" onClick={() => open("about")}>
        {t.nav.about}
      </button>
      <button type="button" className="ts-text-btn ts-with-icon" onClick={() => open("assistant")} aria-label={t.nav.assistantLabel}>
        <LandingIcon name="chat" size={20} />
        <span>{t.nav.assistant}</span>
      </button>
      <button type="button" className="ts-btn" onClick={enter}>
        {t.nav.visualize}
      </button>
    </>
  );

  return (
    <div className="landing" data-theme={theme}>
      <a className="ts-skip" href="#ts-main">
        {t.skip}
      </a>
      <div ref={sentinel} className="ts-sentinel" aria-hidden="true" />
      <header className={scrolled ? "ts-header is-scrolled" : "ts-header"}>
        <a className="ts-brand" href="/" onClick={(event) => event.preventDefault()} aria-label={t.brand}>
          <LandingIcon name="logo" size={28} />
          <span>{t.brand}</span>
        </a>
        <nav className="ts-nav" aria-label="Navigation">
          {actions}
        </nav>
        <button type="button" className="ts-icon-btn ts-menu-btn" onClick={() => setMenuOpen(true)} aria-label={t.nav.menu} aria-expanded={menuOpen}>
          <LandingIcon name="menu" />
        </button>
      </header>
      {menuOpen && (
        <div className="ts-overlay">
          <div className="ts-backdrop" onClick={() => setMenuOpen(false)} aria-hidden="true" />
          <nav className="ts-mobile-menu" aria-label="Navigation">
            <button type="button" className="ts-icon-btn ts-menu-close" onClick={() => setMenuOpen(false)} aria-label={t.nav.closeMenu}>
              <LandingIcon name="close" />
            </button>
            {actions}
          </nav>
        </div>
      )}

      <main id="ts-main">
        <section className="ts-hero" aria-labelledby="ts-hero-title">
          <div className="ts-hero-bg" aria-hidden="true">
            <div className="ts-grid" />
            <div className="ts-blob ts-blob-a" />
            <div className="ts-blob ts-blob-b" />
            <div className="ts-blob ts-blob-c" />
          </div>
          <div className="ts-hero-inner">
            <p className="ts-badge">
              <span className="ts-pulse-dot" aria-hidden="true" />
              {t.hero.badge}
            </p>
            <h1 id="ts-hero-title">
              {t.hero.titleStart} <em className="ts-accent">{t.hero.titleAccent}</em>
              <br />
              {t.hero.titleEnd} <mark>{t.hero.titleMark}</mark> {t.hero.titleClose}
            </h1>
            <p className="ts-lead">{t.hero.lead}</p>
            <div className="ts-cta-row">
              <button type="button" className="ts-btn ts-btn-hero" onClick={enter}>
                {t.hero.cta}
                <LandingIcon name="arrow" size={18} />
              </button>
              <button type="button" className="ts-text-btn" onClick={() => open("about")}>
                {t.hero.ctaSecondary}
              </button>
            </div>
            <dl className="ts-stats" aria-label={t.hero.statsLabel}>
              <div>
                <dt>{format(t.hero.statYears, { years })}</dt>
                <dd>{format(t.hero.statYearsDetail, { start: facts.start.slice(0, 4), end: facts.end.slice(0, 4) })}</dd>
              </div>
              <div>
                <dt>{t.hero.statGrid}</dt>
                <dd>{t.hero.statGridDetail}</dd>
              </div>
              <div>
                <dt>{format(t.hero.statVariables, { count: facts.count })}</dt>
                <dd>{t.hero.statVariablesDetail}</dd>
              </div>
              <div>
                <dt>{t.hero.statMethod}</dt>
                <dd>{format(t.hero.statMethodDetail, { end: monthYear(facts.end, locale) })}</dd>
              </div>
            </dl>
            <p className="ts-source">
              {t.hero.source} ·{" "}
              <button type="button" className="ts-link" onClick={() => open("about")}>
                {t.footer.aboutLink}
              </button>
            </p>
          </div>
        </section>

        <section className="ts-section ts-tinted" aria-labelledby="ts-problem-title">
          <div className="ts-container">
            <p className="ts-eyebrow">{t.problem.eyebrow}</p>
            <h2 id="ts-problem-title">{t.problem.title}</h2>
            <p className="ts-section-lead">{t.problem.lead}</p>
            <div className="ts-cards">
              {t.problem.cards.map((card) => (
                <Card key={card.title} {...card} />
              ))}
            </div>
          </div>
        </section>

        <section className="ts-section" aria-labelledby="ts-mission-title">
          <div className="ts-container">
            <p className="ts-eyebrow">{t.mission.eyebrow}</p>
            <h2 id="ts-mission-title">
              {t.mission.titleStart} <em className="ts-accent">{t.mission.titleAccent}</em>
            </h2>
            <p className="ts-section-lead">{t.mission.lead}</p>
            <div className="ts-cards">
              {t.mission.cards.map((card) => (
                <Card key={card.title} {...card} />
              ))}
            </div>
            <div className="ts-center">
              <button type="button" className="ts-btn" onClick={enter}>
                {t.mission.cta}
                <LandingIcon name="arrow" size={18} />
              </button>
            </div>
          </div>
        </section>
      </main>

      <footer className="ts-footer">
        <div className="ts-container ts-footer-grid">
          <div>
            <p className="ts-footer-brand">
              <LandingIcon name="logo" size={24} />
              {t.brand}
            </p>
            <p>{t.footer.project}</p>
            <p>{t.footer.built}</p>
          </div>
          <div>
            <p className="ts-label">{t.footer.sources}</p>
            <ul>
              <li>
                <a href="https://giovanni.gsfc.nasa.gov/giovanni/" target="_blank" rel="noreferrer noopener">
                  {t.footer.giovanni}
                </a>
              </li>
              <li>
                <a href="https://www.earthdata.nasa.gov/" target="_blank" rel="noreferrer noopener">
                  {t.footer.earthdata}
                </a>
              </li>
              <li>{t.footer.boundaries}</li>
            </ul>
          </div>
          <div>
            <ul>
              <li>
                <button type="button" className="ts-link" onClick={() => open("about")}>
                  {t.footer.aboutLink}
                </button>
              </li>
              <li>
                <button type="button" className="ts-link" onClick={() => open("about")}>
                  {t.footer.dataPolicy}
                </button>
              </li>
            </ul>
          </div>
        </div>
        <p className="ts-container ts-copyright">{format(t.footer.copyright, { year: new Date().getFullYear() })}</p>
      </footer>

      {panel === "about" && (
        <Drawer label={t.about.title} onClose={() => setPanel(null)} wide>
          <About t={t} facts={facts} locale={locale} onClose={() => setPanel(null)} />
        </Drawer>
      )}
      {panel === "assistant" && (
        <Drawer label={t.assistant.title} onClose={() => setPanel(null)}>
          <LandingAssistant t={t} locale={locale} onClose={() => setPanel(null)} onAbout={() => setPanel("about")} />
        </Drawer>
      )}
    </div>
  );
}
