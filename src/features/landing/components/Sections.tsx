import { useLandingLanguage } from '../context/LandingContext';
import type { LandingCatalog } from '../api/landingData';
import type { PhotoSlot } from '../photos';
import { SectionReveal } from './SectionReveal';
import { ChartIcon, LayersIcon, LeafIcon, MessageIcon, SoilIcon, WaterIcon } from './Icons';
import { Photo, hasPhoto } from './Photo';
import { TrendPreview } from './TrendPreview';

function GlobeIconSafe({ size = 22 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3.5 9h17M3.5 15h17M12 3c2.4 2.5 3.5 5.5 3.5 9S14.4 18.5 12 21c-2.4-2.5-3.5-5.5-3.5-9S9.6 5.5 12 3Z"/></svg>;
}

const problemIcons = [SoilIcon, LeafIcon, WaterIcon];
const problemPhotos: PhotoSlot[] = ['agriculture', 'ecosystem', 'water'];
const capabilityIcons = [GlobeIconSafe, ChartIcon, LayersIcon];
const capabilityPhotos: PhotoSlot[] = ['satellite', 'trends', 'results'];

export function ProblemSection() {
  const { t } = useLandingLanguage();
  return (
    <section className="ts-section ts-section--problem" id="problem" aria-labelledby="ts-problem-title">
      <div className="ts-container">
        <SectionReveal className="ts-section-heading ts-section-heading--split">
          <div><span className="ts-overline">{t.problem.eyebrow}</span><h2 id="ts-problem-title">{t.problem.title}</h2></div>
          <p>{t.problem.intro}</p>
        </SectionReveal>
        <ol className="ts-impact-grid">
          {t.problem.cards.map((card, index) => {
            const Icon = problemIcons[index];
            const slot = problemPhotos[index];
            const withPhoto = hasPhoto(slot);
            return (
              <li key={card.number}>
                <SectionReveal delay={index * 90}>
                  <article className={`ts-impact-card ts-impact-card--${index + 1} ${withPhoto ? 'ts-impact-card--photo' : ''}`}>
                    {withPhoto && <Photo slot={slot} className="ts-impact-card__photo" sizes="(max-width: 900px) 100vw, 33vw" />}
                    <div className="ts-impact-card__body">
                      <div className="ts-impact-card__top"><span className="ts-impact-card__number" aria-hidden="true">{card.number}</span><span className="ts-impact-card__icon" aria-hidden="true"><Icon size={25} /></span></div>
                      <span className="ts-overline">{card.tag}</span>
                      <h3>{card.title}</h3>
                      <p>{card.text}</p>
                      {card.note && <p className="ts-impact-card__note">{card.note}</p>}
                      <span className="ts-impact-card__rule" aria-hidden="true" />
                    </div>
                  </article>
                </SectionReveal>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}

export function MissionSection({ onAssistant }: { onAssistant: () => void }) {
  const { t } = useLandingLanguage();
  return (
    <section className="ts-section ts-section--mission" id="mission" aria-labelledby="ts-mission-title">
      <div className="ts-container">
        <SectionReveal className="ts-mission-intro">
          <span className="ts-overline">{t.mission.eyebrow}</span>
          <h2 id="ts-mission-title"><span>{t.mission.titleA}</span><span>{t.mission.titleB} <em>{t.mission.titleC}</em></span></h2>
          <p>{t.mission.description}</p>
        </SectionReveal>
        <div className="ts-capabilities">
          {t.mission.capabilities.map((item, index) => {
            const Icon = capabilityIcons[index];
            const slot = capabilityPhotos[index];
            const photo = hasPhoto(slot);
            return (
              <SectionReveal key={item.title} delay={index * 100}>
                <article className={`ts-capability ${photo ? 'ts-capability--photo' : ''}`}>
                  {photo && <Photo slot={slot} className="ts-capability__photo" sizes="(max-width: 900px) 100vw, 33vw" />}
                  <div className="ts-capability__icon" aria-hidden="true"><Icon size={25} /></div>
                  <span className="ts-overline">{item.label}</span>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                  {index === 2 && (
                    <button type="button" className="ts-text-link ts-capability__action" onClick={onAssistant}>
                      <MessageIcon size={16} />{t.nav.assistant}
                    </button>
                  )}
                  <span className="ts-capability__index" aria-hidden="true">0{index + 1}</span>
                </article>
              </SectionReveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function ScienceSection({ catalog }: { catalog: LandingCatalog }) {
  const { t } = useLandingLanguage();
  return (
    <section className="ts-section ts-section--science" id="method" aria-labelledby="ts-science-title">
      <div className="ts-container">
        <SectionReveal className="ts-section-heading ts-section-heading--center">
          <span className="ts-overline">{t.science.eyebrow}</span>
          <h2 id="ts-science-title">{t.science.title}</h2>
          <p>{t.science.description}</p>
        </SectionReveal>
        <div className="ts-science-grid">
          <div className="ts-method-list">
            {t.science.methods.map((method, index) => (
              <SectionReveal key={method.title} delay={index * 80}>
                <article className="ts-method-item">
                  <span className="ts-method-item__number" aria-hidden="true">0{index + 1}</span>
                  <div><span className="ts-overline">{method.label}</span><h3>{method.title}</h3><p>{method.text}</p></div>
                </article>
              </SectionReveal>
            ))}
          </div>
          <SectionReveal delay={130} className="ts-science-chart-wrap">
            <TrendPreview catalog={catalog} />
          </SectionReveal>
        </div>
        <div className="ts-source-strip">
          <span>{t.science.sources}</span>
          <div className="ts-source-strip__links">
            {t.about.sources.slice(0, 4).map((source) => (
              <a key={source.name} href={source.url} target="_blank" rel="noreferrer noopener">{source.name} <span aria-hidden="true">↗</span><span className="ts-sr-only"> ({t.common.externalLink})</span></a>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
