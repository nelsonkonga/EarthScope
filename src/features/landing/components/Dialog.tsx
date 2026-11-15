import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal side panel. Traps focus, closes on Escape or backdrop, gives focus back to the opener,
 * and locks page scroll while open. `variant` sets the width and the side it enters from.
 */
export function Dialog({
  labelledBy,
  onClose,
  children,
  variant = "drawer",
  initialFocus,
}: {
  labelledBy: string;
  onClose: () => void;
  children: ReactNode;
  variant?: "drawer" | "wide" | "menu";
  initialFocus?: React.RefObject<HTMLElement | null>;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const node = panel.current;
    (initialFocus?.current ?? node?.querySelector<HTMLElement>(FOCUSABLE) ?? node)?.focus();
    document.body.classList.add("ts-locked");
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close.current();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((item) => item.offsetParent !== null);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        last.focus();
        event.preventDefault();
      } else if (!event.shiftKey && document.activeElement === last) {
        first.focus();
        event.preventDefault();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("ts-locked");
      opener?.focus?.();
    };
    // Mount and unmount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return createPortal(
    <div className="ts-layer">
      <div className="ts-scrim" onClick={() => close.current()} aria-hidden="true" />
      <div ref={panel} className={`ts-panel ts-panel-${variant}`} role="dialog" aria-modal="true" aria-labelledby={labelledBy} tabIndex={-1}>
        {children}
      </div>
    </div>,
    document.querySelector(".landing") ?? document.body,
  );
}
