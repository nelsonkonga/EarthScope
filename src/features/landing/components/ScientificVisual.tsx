import { useI18n } from "../../../i18n";

/**
 * Fig. 01: a conceptual soil cross-section. Nothing here is a measurement. The two moist layers
 * are the depths GLDAS Noah reports (0–10 and 10–40 cm), the probes stand for those outputs,
 * and the groundwater band is drawn dashed because these data do not measure it.
 */
export function ScientificVisual() {
  const { t } = useI18n();
  const f = t.hero.figure;
  const surface = "M0 214 C 60 204, 110 222, 170 214 S 280 200, 340 210 S 450 224, 520 208";
  return (
    <figure className="ts-figure">
      <div className="ts-figure-plate">
        <svg viewBox="0 0 520 560" role="img" aria-labelledby="ts-fig-title ts-fig-caption" className="ts-figure-svg">
          <title id="ts-fig-title">{f.alt}</title>
          <defs>
            <linearGradient id="tsTop" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--viz-moist-1)" />
              <stop offset="1" stopColor="var(--viz-moist-2)" />
            </linearGradient>
            <linearGradient id="tsMid" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--viz-moist-2)" />
              <stop offset="1" stopColor="var(--viz-moist-3)" />
            </linearGradient>
            <linearGradient id="tsSwath" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--viz-signal)" stopOpacity="0.28" />
              <stop offset="1" stopColor="var(--viz-signal)" stopOpacity="0.02" />
            </linearGradient>
            <pattern id="tsPores" width="18" height="16" patternUnits="userSpaceOnUse">
              <circle cx="4" cy="5" r="1.6" fill="var(--viz-pore)" />
              <circle cx="13" cy="12" r="1.2" fill="var(--viz-pore)" />
            </pattern>
            <pattern id="tsPoresSparse" width="26" height="22" patternUnits="userSpaceOnUse">
              <circle cx="6" cy="7" r="1.3" fill="var(--viz-pore)" />
              <circle cx="19" cy="17" r="1" fill="var(--viz-pore)" />
            </pattern>
            <pattern id="tsGrain" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(30)">
              <path d="M0 7h14" stroke="var(--viz-grain)" strokeWidth="1" />
            </pattern>
            <clipPath id="tsGround">
              <path d={`${surface} L520 560 L0 560 Z`} />
            </clipPath>
          </defs>

          {/* Relief: contour lines of the land above the section. */}
          <g className="ts-viz-contours" fill="none" stroke="var(--viz-contour)" strokeWidth="1">
            <path d="M0 176 C 70 150, 140 168, 210 154 S 340 128, 400 146 S 480 170, 520 150" />
            <path d="M0 190 C 80 170, 150 186, 220 174 S 340 152, 410 166 S 490 186, 520 170" />
            <path d="M40 160 C 90 136, 150 140, 190 132 S 260 120, 300 128" opacity="0.6" />
          </g>

          {/* Orbit and observation swath. */}
          <path d="M-10 118 C 120 40, 330 12, 530 48" fill="none" stroke="var(--viz-orbit)" strokeWidth="1" strokeDasharray="3 6" />
          <polygon className="ts-viz-swath" points="392,66 262,206 478,212" fill="url(#tsSwath)" />
          <g transform="translate(392 62)" className="ts-viz-sat">
            <rect x="-7" y="-5" width="14" height="10" rx="2" fill="var(--viz-ink)" />
            <rect x="-30" y="-3.5" width="19" height="7" rx="1" fill="none" stroke="var(--viz-ink)" strokeWidth="1.2" />
            <rect x="11" y="-3.5" width="19" height="7" rx="1" fill="none" stroke="var(--viz-ink)" strokeWidth="1.2" />
            <path d="M-21 -3.5v7M20 -3.5v7" stroke="var(--viz-ink)" strokeWidth="1" />
          </g>
          <text x="392" y="34" textAnchor="middle" className="ts-viz-label">{f.orbit}</text>

          {/* Soil horizons. */}
          <g clipPath="url(#tsGround)">
            <rect x="0" y="190" width="520" height="104" fill="url(#tsTop)" />
            <rect x="0" y="190" width="520" height="104" fill="url(#tsPores)" className="ts-viz-moisture" />
            <rect x="0" y="294" width="520" height="122" fill="url(#tsMid)" />
            <rect x="0" y="294" width="520" height="122" fill="url(#tsPoresSparse)" className="ts-viz-moisture ts-viz-moisture-slow" />
            <rect x="0" y="416" width="520" height="70" fill="var(--viz-deep)" />
            <rect x="0" y="416" width="520" height="70" fill="url(#tsGrain)" />
            <rect x="0" y="486" width="520" height="74" fill="var(--viz-water)" />
          </g>
          <path d={surface} fill="none" stroke="var(--viz-ink)" strokeWidth="1.6" />
          <path d="M0 294 C 120 288, 260 300, 520 292" fill="none" stroke="var(--viz-horizon)" strokeWidth="1" />
          <path d="M0 416 C 140 410, 300 422, 520 414" fill="none" stroke="var(--viz-horizon)" strokeWidth="1" />
          <g fill="none" stroke="var(--viz-water-line)" strokeWidth="1.2" strokeDasharray="4 5">
            <path d="M0 500 C 40 494, 80 506, 120 500 S 200 494, 240 500 S 320 506, 360 500 S 440 494, 520 500" />
            <path d="M0 520 C 40 514, 80 526, 120 520 S 200 514, 240 520 S 320 526, 360 520 S 440 514, 520 520" opacity="0.6" />
          </g>

          {/* Probes standing for the two modelled layers. */}
          <g className="ts-viz-probes">
            <line x1="300" y1="206" x2="300" y2="248" stroke="var(--viz-ink)" strokeWidth="1.4" />
            <circle cx="300" cy="250" r="5" fill="var(--viz-paper)" stroke="var(--viz-ink)" strokeWidth="1.6" />
            <circle cx="300" cy="250" r="5" className="ts-viz-ping" fill="none" stroke="var(--viz-signal)" strokeWidth="1.4" />
            <line x1="420" y1="212" x2="420" y2="352" stroke="var(--viz-ink)" strokeWidth="1.4" />
            <circle cx="420" cy="354" r="5" fill="var(--viz-paper)" stroke="var(--viz-ink)" strokeWidth="1.6" />
            <line x1="150" y1="210" x2="150" y2="250" stroke="var(--viz-ink)" strokeWidth="1.4" opacity="0.55" />
            <circle cx="150" cy="252" r="4" fill="var(--viz-paper)" stroke="var(--viz-ink)" strokeWidth="1.4" opacity="0.55" />
          </g>

          {/* Depth labels. */}
          <g className="ts-viz-scale">
            <text x="20" y="198" className="ts-viz-label">{f.surface}</text>
            <text x="20" y="254" className="ts-viz-value">{f.layer1}</text>
            <text x="20" y="360" className="ts-viz-value">{f.layer2}</text>
            <text x="20" y="456" className="ts-viz-label ts-viz-label-muted">{f.deep}</text>
            <text x="20" y="544" className="ts-viz-label ts-viz-label-muted">{f.aquifer}</text>
          </g>
        </svg>
      </div>
      <figcaption id="ts-fig-caption">
        <span className="ts-fig-label">{f.label}</span> {f.caption}
      </figcaption>
    </figure>
  );
}
