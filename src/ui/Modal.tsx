import { createPortal } from "react-dom";
import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { fr } from "../config/strings.fr";

export function Modal({
  title,
  onClose,
  children,
  wide = false,
  onKeyDown,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
  onKeyDown?: (event: KeyboardEvent<HTMLDialogElement>) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.focus();
  }, []);
  return createPortal(
    <>
      <div className="modal-backdrop" onClick={onClose} />
      <dialog ref={dialog} className={wide ? "chart-dialog chart-stage" : "chart-dialog"} open aria-label={title} tabIndex={-1} onKeyDown={onKeyDown}>
        <div className="panel-head">
          <h2>{title}</h2>
          <button type="button" className="text-btn" onClick={onClose}>
            {fr.close}
          </button>
        </div>
        {children}
      </dialog>
    </>,
    document.body,
  );
}
