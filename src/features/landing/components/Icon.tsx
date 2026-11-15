export type IconName =
  | "sun"
  | "moon"
  | "soft"
  | "chat"
  | "roots"
  | "ecosystem"
  | "aquifer"
  | "satellite"
  | "trend"
  | "dialogue"
  | "menu"
  | "close"
  | "arrow"
  | "arrowDown"
  | "send"
  | "external"
  | "info";

/** Inline SVG icons, 24-unit grid, 1.6 stroke. Decorative unless `label` is given. */
export function Icon({ name, size = 20, label }: { name: IconName; size?: number; label?: string }) {
  const s = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden={label ? undefined : true} role={label ? "img" : undefined} aria-label={label} focusable="false">
      {name === "sun" && (
        <>
          <circle {...s} cx="12" cy="12" r="3.8" />
          <path {...s} d="M12 3v1.8M12 19.2V21M3 12h1.8M19.2 12H21M5.6 5.6l1.3 1.3M17.1 17.1l1.3 1.3M5.6 18.4l1.3-1.3M17.1 6.9l1.3-1.3" />
        </>
      )}
      {name === "moon" && <path {...s} d="M19.5 14.5A7.6 7.6 0 0 1 9.5 4.5a7.6 7.6 0 1 0 10 10Z" />}
      {name === "soft" && (
        <>
          <path {...s} d="M4 15.5h16M6.5 19h11" />
          <path {...s} d="M7.5 15.5a4.5 4.5 0 0 1 9 0" />
          <path {...s} d="M12 5.5v2.2M5.8 8.6l1.4 1.4M18.2 8.6l-1.4 1.4" />
        </>
      )}
      {name === "chat" && (
        <>
          <path {...s} d="M4.5 5.5h15v10h-9l-4 3.2v-3.2h-2Z" />
          <path {...s} d="M8 11.5l1.8-2.2 2 2.6 2-3.4 2.2 3" />
        </>
      )}
      {name === "roots" && (
        <>
          <path {...s} d="M3 10h18" />
          <path {...s} d="M12 10V4.5M12 6.8c-1.6 0-2.8-1-3.2-2.6 1.7 0 2.9.9 3.2 2.6ZM12 6c.3-1.6 1.5-2.6 3.2-2.6-.4 1.6-1.6 2.6-3.2 2.6Z" />
          <path {...s} d="M12 10v4.5M12 12.5l-3 2.5M12 13.5l2.8 2.2M9 15l-1 3M14.8 15.7l.6 2.8" opacity="0.7" />
        </>
      )}
      {name === "ecosystem" && (
        <>
          <path {...s} d="M3 19.5h18" />
          <path {...s} d="M7 19.5v-5M7 14.5c-2 0-3-1.6-3-3.3 0-1.9 1.4-3.2 3-3.2s3 1.3 3 3.2c0 1.7-1 3.3-3 3.3Z" />
          <path {...s} d="M13 16.5c1.4-1.2 3-1.2 4.4 0s3 1.2 3.6.4" opacity="0.75" />
          <path {...s} d="M16.5 9.5c.9 1.2 1.4 2 1.4 2.6a1.4 1.4 0 0 1-2.8 0c0-.6.5-1.4 1.4-2.6Z" />
        </>
      )}
      {name === "aquifer" && (
        <>
          <path {...s} d="M3 7.5h18" />
          <path {...s} d="M3 12c2-1.3 4-1.3 6 0s4 1.3 6 0 4-1.3 6 0" opacity="0.55" />
          <path {...s} d="M3 16.5c2-1.3 4-1.3 6 0s4 1.3 6 0 4-1.3 6 0" />
          <path {...s} d="M12 7.5v4" strokeDasharray="1.4 1.8" />
        </>
      )}
      {name === "satellite" && (
        <>
          <rect {...s} x="9.5" y="9.5" width="5" height="5" rx="0.8" transform="rotate(45 12 12)" />
          <path {...s} d="M6.3 6.3 8.5 8.5M15.5 15.5l2.2 2.2M3.8 8.8l5-5M15.2 20.2l5-5" />
          <path {...s} d="M16.5 3.5a4 4 0 0 1 4 4" opacity="0.6" />
        </>
      )}
      {name === "trend" && (
        <>
          <path {...s} d="M4 4v16h16" />
          <path {...s} d="M7 13l3-3 3 2.5 4-5.5" />
          <path {...s} d="M7 16.5 18 9" strokeDasharray="1.6 2" opacity="0.7" />
        </>
      )}
      {name === "dialogue" && (
        <>
          <path {...s} d="M4 5h11v7.5H9L6 15v-2.5H4Z" />
          <path {...s} d="M18 9h2v7.5h-2v2.5l-3-2.5h-5v-2" opacity="0.7" />
        </>
      )}
      {name === "menu" && <path {...s} d="M4 7h16M4 12h16M4 17h10" />}
      {name === "close" && <path {...s} d="M6 6l12 12M18 6 6 18" />}
      {name === "arrow" && <path {...s} d="M5 12h14M13.5 6.5 19 12l-5.5 5.5" />}
      {name === "arrowDown" && <path {...s} d="M12 5v14M6.5 13.5 12 19l5.5-5.5" />}
      {name === "send" && <path {...s} d="M4.5 12 19.5 4.5l-4.5 15-3.2-6.3Z" />}
      {name === "external" && <path {...s} d="M14 4.5h5.5V10M19.5 4.5 11 13M17.5 14v4.5a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1H10" />}
      {name === "info" && (
        <>
          <circle {...s} cx="12" cy="12" r="8.5" />
          <path {...s} d="M12 11v5.5M12 7.8v.2" />
        </>
      )}
    </svg>
  );
}
