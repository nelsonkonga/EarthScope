import { useEffect, useRef, useState } from "react";
import { animate, motion, useInView, useMotionValue, useMotionValueEvent } from "motion/react";

export const EASE = [0.22, 1, 0.36, 1];
export const SPRING = { type: "spring", stiffness: 520, damping: 40 };

/** A numbered step of the explanation; fades in once when it reaches the screen. */
export function Section({ n, title, children, id }) {
  return (
    <motion.section
      id={id}
      className="section"
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, ease: EASE }}
    >
      <p className="num">{String(n).padStart(2, "0")}</p>
      <h2>{title}</h2>
      {children}
    </motion.section>
  );
}

/** Segmented control: the thumb slides to the chosen option. */
export function Segmented({ id, options, value, onChange, label }) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={o.value} role="radio" aria-checked={on} className={on ? "on" : ""} onClick={() => onChange(o.value)}>
            {on && <motion.span layoutId={id} className="thumb" transition={SPRING} />}
            <span>{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Chips with a sliding pill (the case and variable pickers). */
export function Chips({ id, items, value, onChange, small, label }) {
  return (
    <div className={`chips${small ? " small" : ""}`} role="radiogroup" aria-label={label}>
      {items.map((it) => {
        const on = it.value === value;
        return (
          <motion.button
            key={it.value}
            role="radio"
            aria-checked={on}
            className={`chip${on ? " on" : ""}`}
            onClick={() => onChange(it.value)}
            whileTap={{ scale: 0.96 }}
          >
            {on && <motion.span layoutId={id} className="pill" transition={SPRING} />}
            <span>{it.label}</span>
          </motion.button>
        );
      })}
    </div>
  );
}

/** A number that counts to its value when it first shows, then glides between values. */
export function Num({ value, format = (v) => Math.round(v), duration = 0.9 }) {
  const ref = useRef(null);
  const seen = useInView(ref, { once: true });
  const mv = useMotionValue(0);
  const [shown, setShown] = useState(0);
  useMotionValueEvent(mv, "change", setShown);
  useEffect(() => {
    if (!seen) return;
    const c = animate(mv, value, { duration, ease: EASE });
    return () => c.stop();
  }, [seen, value]);
  return <span ref={ref}>{format(shown)}</span>;
}

/** A thin horizontal bar that fills to `share` (0–1) when it shows. */
export function Bar({ label, share, color, text }) {
  const ref = useRef(null);
  const seen = useInView(ref, { once: true, margin: "-40px" });
  return (
    <div className="bar-row" ref={ref}>
      <span>{label}</span>
      <div className="bar-track">
        <motion.div
          className="bar-fill"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: seen ? `${100 * share}%` : 0 }}
          transition={{ duration: 1.1, ease: EASE, delay: 0.1 }}
        />
      </div>
      <span className="v">{text}</span>
    </div>
  );
}

/** Tooltip placed near (x, y) inside the chart box, kept inside it. */
export function Tip({ x, y, width, children }) {
  const left = Math.min(Math.max(x + 12, 4), width - 170);
  return (
    <div className="tip" style={{ left, top: Math.max(0, y - 52) }}>
      {children}
    </div>
  );
}
