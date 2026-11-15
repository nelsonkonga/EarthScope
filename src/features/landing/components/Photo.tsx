import { useState, type CSSProperties } from 'react';
import { PHOTOS, type PhotoSlot } from '../photos';
import { useLandingLanguage } from '../context/LandingContext';

type Props = {
  slot: PhotoSlot;
  className?: string;
  /** Above-the-fold image: eager, high fetch priority. Everything else is lazy. */
  priority?: boolean;
  sizes?: string;
};

/**
 * A local photograph. Renders nothing when the slot has no verified photo, and falls back to a neutral surface (no broken-image icon) if the file fails to load.
 */
export function Photo({ slot, className = '', priority = false, sizes = '100vw' }: Props) {
  const photo = PHOTOS[slot];
  const { language } = useLandingLanguage();
  const [failed, setFailed] = useState(false);
  if (!photo) return null;
  const style = {
    '--photo-position': photo.position?.desktop ?? '50% 50%',
    '--photo-position-mobile': photo.position?.mobile ?? photo.position?.desktop ?? '50% 50%',
  } as CSSProperties;
  const loading = priority ? { loading: 'eager' as const, fetchpriority: 'high' } : { loading: 'lazy' as const };
  return (
    <figure className={`ts-photo ${failed ? 'is-failed' : ''} ${className}`} style={style} data-slot={slot}>
      {!failed && (
        <picture>
          {photo.mobileSrc && (
            <source media="(max-width: 640px)" srcSet={photo.mobileSrc} width={photo.mobileWidth} height={photo.mobileHeight} type="image/webp" />
          )}
          <img
            src={photo.src}
            width={photo.width}
            height={photo.height}
            alt={photo.alt[language]}
            sizes={sizes}
            decoding="async"
            onError={() => setFailed(true)}
            {...loading}
          />
        </picture>
      )}
    </figure>
  );
}

export function hasPhoto(slot: PhotoSlot) {
  return Boolean(PHOTOS[slot]);
}
