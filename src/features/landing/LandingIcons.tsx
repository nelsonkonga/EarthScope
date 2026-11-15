export type LandingIconName =
  | "logo"
  | "sun"
  | "moon"
  | "dim"
  | "chat"
  | "crop"
  | "herd"
  | "aquifer"
  | "satellite"
  | "proof"
  | "explain"
  | "menu"
  | "close"
  | "arrow"
  | "send"
  | "external";

/** Inline SVG only: no bitmap, no icon font. Decorative unless a label is given. */
export function LandingIcon({ name, size = 22, label }: { name: LandingIconName; size?: number; label?: string }) {
  const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden={label ? undefined : true} role={label ? "img" : undefined} aria-label={label}>
      {name === "logo" && (
        <>
          <path {...stroke} d="M2.5 15.5c2.4-2.2 4.6-2.2 7 0s4.6 2.2 7 0 3.6-1.8 5 -.6" />
          <path {...stroke} d="M2.5 19.5c2.4-2.2 4.6-2.2 7 0s4.6 2.2 7 0 3.6-1.8 5-.6" opacity="0.55" />
          <circle cx="12" cy="7.5" r="2.4" fill="currentColor" />
          <path {...stroke} d="M8.2 4.6a5.4 5.4 0 0 1 7.6 0" opacity="0.7" />
        </>
      )}
      {name === "sun" && (
        <>
          <circle {...stroke} cx="12" cy="12" r="4" />
          <path {...stroke} d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M5.5 18.5l1.4-1.4M17.1 6.9l1.4-1.4" />
        </>
      )}
      {name === "moon" && <path {...stroke} d="M19.5 14.6A7.8 7.8 0 0 1 9.4 4.5a7.8 7.8 0 1 0 10.1 10.1Z" />}
      {name === "dim" && (
        <>
          <circle {...stroke} cx="12" cy="12" r="7.5" />
          <path d="M12 4.5a7.5 7.5 0 0 1 0 15Z" fill="currentColor" opacity="0.45" />
        </>
      )}
      {name === "chat" && (
        <>
          <path {...stroke} d="M4 5.5h16v10.5H10l-4.5 3.5V16H4Z" />
          <path {...stroke} d="M7.5 11.5l2-2.5 2 3 2-4 2.5 3.5" />
        </>
      )}
      {name === "crop" && (
        <>
          <path {...stroke} d="M12 21V9" />
          <path {...stroke} d="M12 13c-3.5 0-5.5-2-5.5-5.5C10 7.5 12 9.5 12 13Z" />
          <path {...stroke} d="M12 10.5c0-3.5 2-5.5 5.5-5.5 0 3.5-2 5.5-5.5 5.5Z" />
          <path {...stroke} d="M5 21h14" />
        </>
      )}
      {name === "herd" && (
        <>
          <path {...stroke} d="M4 11.5c0-2 1.6-3.5 3.6-3.5h7.2c2.3 0 4.2 1.9 4.2 4.2V14" />
          <path {...stroke} d="M19 10l2-1.5M6.5 15v4M10 15v4M14.5 15v4M17.5 14v5" />
          <path {...stroke} d="M4 11.5V15h15" />
          <path {...stroke} d="M3 22h18" opacity="0.6" />
        </>
      )}
      {name === "aquifer" && (
        <>
          <path {...stroke} d="M3 8h18" />
          <path {...stroke} d="M3 13c2-1.4 4-1.4 6 0s4 1.4 6 0 4-1.4 6 0" opacity="0.7" />
          <path {...stroke} d="M3 17.5c2-1.4 4-1.4 6 0s4 1.4 6 0 4-1.4 6 0" />
          <path {...stroke} d="M12 2.5c1.6 2 2.4 3.2 2.4 4.1a2.4 2.4 0 0 1-4.8 0c0-.9.8-2.1 2.4-4.1Z" />
        </>
      )}
      {name === "satellite" && (
        <>
          <rect {...stroke} x="9.2" y="9.2" width="5.6" height="5.6" rx="1" transform="rotate(45 12 12)" />
          <path {...stroke} d="M5 5l3 3M16 16l3 3M3 7l4-4M17 21l4-4" />
          <path {...stroke} d="M15.5 4.5a4 4 0 0 1 4 4M15.5 1.8a6.7 6.7 0 0 1 6.7 6.7" opacity="0.6" />
        </>
      )}
      {name === "proof" && (
        <>
          <path {...stroke} d="M4 20V4M4 20h16" />
          <circle cx="8" cy="15" r="1.1" fill="currentColor" />
          <circle cx="11" cy="13.5" r="1.1" fill="currentColor" />
          <circle cx="14" cy="11" r="1.1" fill="currentColor" />
          <circle cx="17.5" cy="8.5" r="1.1" fill="currentColor" />
          <path {...stroke} d="M6.5 16.5 19 7" strokeDasharray="2 2" />
        </>
      )}
      {name === "explain" && (
        <>
          <circle {...stroke} cx="12" cy="12" r="8.5" />
          <path {...stroke} d="M12 12V3.5M12 12l6.5 5.5" />
          <path d="M12 3.5a8.5 8.5 0 0 1 6.5 14L12 12Z" fill="currentColor" opacity="0.28" />
        </>
      )}
      {name === "menu" && <path {...stroke} d="M4 7h16M4 12h16M4 17h10" />}
      {name === "close" && <path {...stroke} d="M6 6l12 12M18 6 6 18" />}
      {name === "arrow" && <path {...stroke} d="M5 12h14M13 6l6 6-6 6" />}
      {name === "send" && <path {...stroke} d="M4 12 20 4l-5 16-3.5-6.5Z" />}
      {name === "external" && <path {...stroke} d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />}
    </svg>
  );
}
