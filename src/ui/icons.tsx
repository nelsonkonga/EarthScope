type Name = "variables" | "zones" | "chat" | "plus" | "minus" | "compass" | "expand" | "close" | "play" | "pause" | "back" | "forward";

export function Icon({ name }: { name: Name }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
      {name === "variables" && <path {...common} d="M4 6h12M4 10h12M4 14h8" />}
      {name === "zones" && <path {...common} d="M10 3.5 16 7.2v5.6L10 16.5 4 12.8V7.2L10 3.5Z" />}
      {name === "chat" && <path {...common} d="M4 5.5h12v8H8l-4 2.5V5.5Z" />}
      {name === "plus" && <path {...common} d="M10 4.5v11M4.5 10h11" />}
      {name === "minus" && <path {...common} d="M4.5 10h11" />}
      {name === "compass" && (
        <>
          <circle {...common} cx="10" cy="10" r="6.5" />
          <path {...common} d="M10 5.2v2.2M12.8 12.2 8.6 10.6 10.2 6.4l2.6 5.8Z" />
        </>
      )}
      {name === "expand" && <path {...common} d="M7 4.5H4.5V7M13 4.5h2.5V7M7 15.5H4.5V13M13 15.5h2.5V13" />}
      {name === "close" && <path {...common} d="M5.5 5.5l9 9M14.5 5.5l-9 9" />}
      {name === "play" && <path {...common} d="M7 4.8v10.4l8-5.2-8-5.2Z" />}
      {name === "pause" && <path {...common} d="M7 5v10M13 5v10" />}
      {name === "back" && <path {...common} d="M12.5 4.8 7 10l5.5 5.2" />}
      {name === "forward" && <path {...common} d="M7.5 4.8 13 10l-5.5 5.2" />}
    </svg>
  );
}
