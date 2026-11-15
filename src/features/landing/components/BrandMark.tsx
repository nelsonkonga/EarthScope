/**
 * Terra Sense mark: two soil horizons (contour lines) under a sensor point and its signal arc.
 * Uses currentColor so it follows the theme.
 */
export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden="true" focusable="false" className="ts-mark">
      <path d="M3 19.5c3.2-2.6 6.2-2.6 9.4 0s6.2 2.6 9.4 0c2.4-1.9 4.6-2.3 7.2-.9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M3 25c3.2-2.2 6.2-2.2 9.4 0s6.2 2.2 9.4 0c2.4-1.6 4.6-1.9 7.2-.7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity="0.45" />
      <circle cx="16" cy="11" r="2.6" fill="currentColor" />
      <path d="M11 7.4a7 7 0 0 1 10 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" opacity="0.7" />
      <path d="M16 13.6v3.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeDasharray="1 2" />
    </svg>
  );
}
