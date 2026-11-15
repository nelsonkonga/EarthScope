/**
 * Pexels photographs used on the landing page. Files live in public/images/ and are served
 * locally (no hotlinking). Every entry must match a row of public/images/PEXELS-SOURCES.md:
 * a slot without a verified download stays absent, and the page renders without it.
 */
export type PhotoSlot = 'hero' | 'agriculture' | 'ecosystem' | 'water' | 'satellite' | 'fieldwork';

export type Photo = {
  /** Path under public/, e.g. /images/hero-soil-landscape.webp */
  src: string;
  /** Optional dedicated crop for narrow screens (max-width: 640px). */
  mobileSrc?: string;
  width: number;
  height: number;
  mobileWidth?: number;
  mobileHeight?: number;
  /** Empty string for a purely decorative image. */
  alt: { en: string; fr: string };
  photographer: string;
  pexelsUrl: string;
  /** CSS object-position for wide and narrow layouts. */
  position?: { desktop: string; mobile: string };
};

export const PHOTOS: Partial<Record<PhotoSlot, Photo>> = {
  hero: {
    src: '/images/hero-soil-landscape.webp',
    width: 1600,
    height: 900,
    mobileSrc: '/images/hero-soil-landscape-mobile.webp',
    mobileWidth: 960,
    mobileHeight: 720,
    alt: {
      en: 'Close-up of fine plant roots running through brown soil.',
      fr: 'Gros plan de fines racines qui traversent une terre brune.',
    },
    photographer: 'Mikhail Nilov',
    pexelsUrl: 'https://www.pexels.com/photo/roots-in-brown-soil-7675949/',
    position: { desktop: '50% 50%', mobile: '50% 50%' },
  },
  agriculture: {
    src: '/images/agriculture-field.webp',
    width: 1200,
    height: 800,
    alt: {
      en: 'Aerial view of long, straight rows of green crops.',
      fr: 'Vue aérienne de longs rangs rectilignes de cultures vertes.',
    },
    photographer: 'Jan van der Wolf',
    pexelsUrl: 'https://www.pexels.com/photo/aerial-view-of-expansive-green-crop-field-40950120/',
    position: { desktop: '50% 45%', mobile: '50% 45%' },
  },
  ecosystem: {
    src: '/images/ecosystem-savanna.webp',
    width: 1200,
    height: 800,
    alt: {
      en: 'Open savanna with scattered acacia trees and hills on the horizon.',
      fr: 'Savane ouverte parsemée d’acacias, avec des collines à l’horizon.',
    },
    photographer: 'Abdallah Mallya',
    pexelsUrl: 'https://www.pexels.com/photo/trees-on-savanna-16253414/',
    position: { desktop: '38% 55%', mobile: '38% 55%' },
  },
  water: {
    src: '/images/water-resource.webp',
    width: 1200,
    height: 800,
    alt: {
      en: 'A woman draws water from a deep stone well in a brick courtyard.',
      fr: 'Une femme puise de l’eau dans un puits profond, dans une cour en briques.',
    },
    photographer: 'Mehmet Turgut Kirkgoz',
    pexelsUrl: 'https://www.pexels.com/photo/a-woman-fetching-water-from-a-deep-well-12068384/',
    position: { desktop: '56% 60%', mobile: '58% 60%' },
  },
  satellite: {
    src: '/images/satellite-earth-observation.webp',
    width: 1400,
    height: 788,
    alt: {
      en: 'Illustration of a satellite in orbit above cloud-covered Earth.',
      fr: 'Illustration d’un satellite en orbite au-dessus d’une Terre nuageuse.',
    },
    photographer: 'Zelch Csaba',
    pexelsUrl: 'https://www.pexels.com/photo/earth-view-with-satellite-from-space-30596312/',
    position: { desktop: '72% 55%', mobile: '74% 55%' },
  },
  fieldwork: {
    src: '/images/soil-research-fieldwork.webp',
    width: 1400,
    height: 788,
    alt: {
      en: 'Gloved hands loosening soil before planting.',
      fr: 'Des mains gantées ameublissent la terre avant la plantation.',
    },
    photographer: 'Greta Hoffman',
    pexelsUrl: 'https://www.pexels.com/photo/crop-farmer-preparing-soil-for-planting-7728051/',
    position: { desktop: '50% 58%', mobile: '50% 55%' },
  },
};
