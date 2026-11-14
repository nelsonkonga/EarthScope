import { createPortal } from "react-dom";
import type { ReactNode } from "react";
import { fr } from "../config/strings.fr";

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return createPortal(
    <>
      <div className="modal-backdrop" onClick={onClose} />
      <dialog className="chart-dialog" open aria-label={title}>
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
