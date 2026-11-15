import { useLandingLanguage } from '../context/LandingContext';

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`ts-brand ${compact ? 'ts-brand--compact' : ''}`}>
      <svg className="ts-brand__symbol" viewBox="0 0 42 42" aria-hidden="true" focusable="false">
        <rect x="1" y="1" width="40" height="40" rx="13" fill="currentColor" opacity=".08" />
        <path d="M7 16.5c5.2-3.8 9.4 2.8 14.5-1.2 4.8-3.8 8.3-3.5 13.5-.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M7 22.5c5.2-3.8 9.4 2.8 14.5-1.2 4.8-3.8 8.3-3.5 13.5-.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" opacity=".72" />
        <path d="M7 28.5c5.2-3.8 9.4 2.8 14.5-1.2 4.8-3.8 8.3-3.5 13.5-.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" opacity=".45" />
        <circle cx="29.7" cy="10.7" r="2.4" fill="#C68B5F" />
      </svg>
      {compact ? <span className="ts-sr-only">Terra Sense</span> : <span className="ts-brand__wordmark">Terra <span>Sense</span></span>}
    </span>
  );
}

export function HeroArtwork() {
  const { t } = useLandingLanguage();
  return (
    <div className="ts-hero-art" aria-label={t.hero.visualAria} role="img">
      <div className="ts-hero-art__topline"><span className="ts-live-dot" /> <span>{t.hero.artTop}</span><span>{t.hero.artSystem}</span></div>
      <svg className="ts-hero-art__drawing" viewBox="0 0 720 560" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <linearGradient id="soilTop" x1="80" y1="135" x2="620" y2="350" gradientUnits="userSpaceOnUse"><stop stopColor="#D7E1D2"/><stop offset="1" stopColor="#A8BBA8"/></linearGradient>
          <linearGradient id="soilMid" x1="112" y1="280" x2="590" y2="490" gradientUnits="userSpaceOnUse"><stop stopColor="#C6A988"/><stop offset="1" stopColor="#A98A6A"/></linearGradient>
          <linearGradient id="soilDeep" x1="90" y1="405" x2="610" y2="550" gradientUnits="userSpaceOnUse"><stop stopColor="#806C59"/><stop offset="1" stopColor="#A18A70"/></linearGradient>
          <linearGradient id="moisture" x1="80" y1="0" x2="570" y2="180" gradientUnits="userSpaceOnUse"><stop stopColor="#7FA99A" stopOpacity=".1"/><stop offset=".5" stopColor="#6F9B8A" stopOpacity=".48"/><stop offset="1" stopColor="#D4B18C" stopOpacity=".1"/></linearGradient>
          <filter id="softShadow" x="34" y="50" width="660" height="490" filterUnits="userSpaceOnUse"><feGaussianBlur stdDeviation="18"/></filter>
          <clipPath id="soilClip"><path d="M82 178 356 91l281 87v236l-281 93-274-93V178Z"/></clipPath>
        </defs>
        <ellipse cx="367" cy="465" rx="255" ry="42" fill="#657F70" opacity=".12" filter="url(#softShadow)"/>
        <path d="M82 178 356 91l281 87-281 91L82 178Z" fill="url(#soilTop)" stroke="#718E7B" strokeOpacity=".75" strokeWidth="1.5"/>
        <g clipPath="url(#soilClip)">
          <path d="M82 178 356 269l281-91v92l-281 92L82 270v-92Z" fill="url(#soilMid)"/>
          <path d="M82 270 356 362l281-92v115l-281 92L82 385V270Z" fill="url(#soilDeep)"/>
          <path d="M82 178 356 269l281-91" stroke="#F7F8F1" strokeOpacity=".75" strokeWidth="2"/>
          <path d="M82 270 356 362l281-92" stroke="#F1E6D7" strokeOpacity=".58" strokeWidth="1.5"/>
          <path d="M82 385 356 477l281-92" stroke="#F1E6D7" strokeOpacity=".3" strokeWidth="1.5"/>
          <path d="M113 209c52-25 91-29 139-10 49 20 82 12 133-6 51-18 91-16 137 2 32 12 59 11 93-3" stroke="#658E7C" strokeOpacity=".65" strokeWidth="2" strokeLinecap="round"/>
          <path d="M109 236c59-17 94 24 143 23 50-1 91-44 143-38 47 5 85 37 136 28 34-6 62-24 88-20" stroke="#E8D9C3" strokeOpacity=".8" strokeWidth="1.5" strokeLinecap="round"/>
          <path d="M180 305c20 15 32 31 38 57m-38-57c-12 15-18 28-20 44m20-44 3-52m92 68c17 18 28 39 31 66m-31-66 2-69m0 69c-15 7-25 18-33 33m125-31c15 17 23 37 25 58m-25-58-2-65m2 65c-18 6-29 18-37 32" stroke="#E9E1CE" strokeWidth="2" strokeLinecap="round" opacity=".7"/>
          <path d="M112 275c32 4 49 25 75 31 35 9 54-11 83-5 27 6 39 32 68 38 26 5 49-9 75-7 32 3 48 28 80 28 34 0 56-21 94-20" stroke="url(#moisture)" strokeWidth="16" strokeLinecap="round"/>
          <path d="M143 406c46-18 80-12 119 0 35 11 65 14 103-1 41-16 71-18 110-5 42 13 68 16 111-3" stroke="#C6D5C7" strokeOpacity=".35" strokeWidth="2" strokeDasharray="4 8"/>
          <g fill="#D6E6D9" opacity=".85"><circle cx="205" cy="216" r="4"/><circle cx="280" cy="240" r="3"/><circle cx="421" cy="223" r="3.5"/><circle cx="523" cy="211" r="3"/><circle cx="335" cy="316" r="3.5"/><circle cx="477" cy="340" r="3"/><circle cx="236" cy="400" r="2.5"/></g>
          <path d="M82 178 356 269v208L82 385V178Z" fill="#E9E5D9" opacity=".09"/>
        </g>
        <path d="M356 91v178" stroke="#F7F8F1" strokeOpacity=".65" strokeDasharray="4 7"/>
        <path d="M356 92c-5-24-16-35-27-48m27 48c4-23 13-35 26-47m-26 47c-1-31 1-44 0-63" stroke="#6E937E" strokeWidth="3" strokeLinecap="round"/>
        <path d="M329 43c-15-3-22-13-21-23 14 0 24 7 27 19m47-17c-13 1-22 10-23 21 14 0 23-7 27-18" fill="#8DAE98"/>
        <circle cx="356" cy="92" r="8" fill="#C68B5F" stroke="#F8F7F0" strokeWidth="4"/>
        <path d="M500 132c33-15 52-15 83-3" stroke="#789687" strokeWidth="1.4" strokeDasharray="3 6"/>
        <circle cx="588" cy="129" r="4" fill="#C68B5F"/>
        <path d="M572 358c29-9 47-4 71 8" stroke="#E7D8C5" strokeWidth="2" strokeLinecap="round"/>
        <path d="M593 372c23-4 36 0 54 9" stroke="#E7D8C5" strokeWidth="1.5" strokeLinecap="round" opacity=".6"/>
      </svg>
      <div className="ts-hero-art__label ts-hero-art__label--top"><span className="ts-label-point" />{t.hero.artSurface}</div>
      <div className="ts-hero-art__label ts-hero-art__label--left"><span>01</span><b>{t.hero.artProfile}</b></div>
      <div className="ts-hero-art__label ts-hero-art__label--bottom"><span>{t.hero.artObserve}</span><i /> <span>{t.hero.artInterpret}</span></div>
      <div className="ts-hero-art__caption">{t.hero.artCaption}</div>
    </div>
  );
}
