import { useState } from 'react';
import { useLandingLanguage } from '../context/LandingContext';
import { ArrowUpRight, PlayIcon } from './Icons';
import { SectionReveal } from './SectionReveal';

/** The project film on YouTube (Trivia channel, published 2026-11-17). */
const FILM_ID = 'z4xjLWbAUmA';

/**
 * The 2-minute project film. A local poster stands in for the player: nothing is requested from
 * YouTube until the visitor presses play, then the privacy-enhanced player starts on its own.
 */
export function FilmSection() {
  const { t, language } = useLandingLanguage();
  const [playing, setPlaying] = useState(false);
  return (
    <section className="ts-section ts-section--film" id="film" aria-labelledby="ts-film-title">
      <div className="ts-container">
        <SectionReveal className="ts-section-heading ts-section-heading--center">
          <span className="ts-overline">{t.film.eyebrow}</span>
          <h2 id="ts-film-title">{t.film.title}</h2>
          <p>{t.film.description}</p>
        </SectionReveal>
        <SectionReveal delay={100}>
          <div className="ts-film">
            {playing ? (
              <iframe
                src={`https://www.youtube-nocookie.com/embed/${FILM_ID}?autoplay=1&rel=0&hl=${language}`}
                title={t.film.playerTitle}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                referrerPolicy="strict-origin-when-cross-origin"
                allowFullScreen
              />
            ) : (
              <button type="button" className="ts-film__poster" onClick={() => setPlaying(true)}>
                <img src="/images/terra-sense-film-poster.webp" width={1280} height={720} alt="" loading="lazy" decoding="async" />
                <span className="ts-film__cue" aria-hidden="true">
                  <span className="ts-film__play"><PlayIcon size={17} /></span>{t.film.watch}<span className="ts-film__duration">2:27</span>
                </span>
                <span className="ts-sr-only">{t.film.play}</span>
              </button>
            )}
          </div>
          <p className="ts-film__note">
            <span>{t.film.note}</span>
            <a className="ts-text-link" href={`https://youtu.be/${FILM_ID}`} target="_blank" rel="noreferrer noopener">
              {t.film.youtube}<ArrowUpRight size={15} /><span className="ts-sr-only"> ({t.common.externalLink})</span>
            </a>
          </p>
        </SectionReveal>
      </div>
    </section>
  );
}
