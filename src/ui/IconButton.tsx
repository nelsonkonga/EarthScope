import type { ReactNode } from "react";

export function IconButton({
  label,
  pressed,
  disabled,
  onClick,
  children,
}: {
  label: string;
  pressed?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button type="button" className="icon-btn" aria-label={label} aria-pressed={pressed} title={label} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}
