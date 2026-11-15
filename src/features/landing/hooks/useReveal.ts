import { useEffect, useRef, useState } from "react";

/**
 * Marks an element visible the first time it enters the viewport. Content is visible by default
 * (no JavaScript, reduced motion, or no IntersectionObserver): only the entrance is skipped.
 */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [state, setState] = useState<"static" | "waiting" | "shown">("static");
  useEffect(() => {
    const node = ref.current;
    if (!node || !("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const box = node.getBoundingClientRect();
    if (box.top < window.innerHeight * 0.92) return;
    setState("waiting");
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setState("shown");
        observer.disconnect();
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return { ref, revealClass: state === "static" ? "" : state === "waiting" ? "ts-reveal" : "ts-reveal is-shown" };
}
