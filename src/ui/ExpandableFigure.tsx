import { useState, type ReactNode } from "react";
import { ui } from "../config/strings";
import { Icon } from "./icons";
import { Modal } from "./Modal";

/**
 * A chart that opens in a large view. The whole figure is the target, and a visible
 * caption tells the reader they can click it. `interactive` charts (which already use
 * clicks to pick a date) only expand through the labelled button, never on a plain click.
 */
export function ExpandableFigure({
  title,
  subtitle,
  children,
  large,
  interactive = false,
  onExpand,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** The enlarged rendering. Defaults to the same content, stretched to the dialog. */
  large?: () => ReactNode;
  interactive?: boolean;
  /** Controlled mode: the parent owns the dialog. */
  onExpand?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const expand = () => (onExpand ? onExpand() : setOpen(true));
  return (
    <figure className={interactive ? "expandable is-interactive" : "expandable"}>
      {interactive ? (
        <div className="expandable-body">{children}</div>
      ) : (
        <button type="button" className="expandable-body" onClick={expand} aria-label={`${ui.expandChart}: ${title}`}>
          {children}
        </button>
      )}
      <figcaption className="expandable-hint">
        <span>{interactive ? ui.expandHintInteractive : ui.expandHint}</span>
        <button type="button" className="expand-btn" onClick={expand} aria-label={`${ui.expandChart}: ${title}`}>
          <Icon name="expand" />
          <span>{ui.expand}</span>
        </button>
      </figcaption>
      {open && (
        <Modal wide title={title} onClose={() => setOpen(false)}>
          {subtitle && <p className="unit">{subtitle}</p>}
          <div className="expanded-figure">{large ? large() : children}</div>
        </Modal>
      )}
    </figure>
  );
}
