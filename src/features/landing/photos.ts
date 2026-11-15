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

export const PHOTOS: Partial<Record<PhotoSlot, Photo>> = {};
