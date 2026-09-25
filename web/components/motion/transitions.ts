import type { Transition, Variants } from "motion/react";

// Strong ease-out: starts fast so UI feels responsive, settles gently.
export const EASE_OUT = [0.23, 1, 0.32, 1] as const;

export const enterTransition: Transition = { duration: 0.25, ease: EASE_OUT };
export const exitTransition: Transition = { duration: 0.12, ease: EASE_OUT };

// Fade + small rise for content entering the conversation.
export const riseIn: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: enterTransition },
};

// Parent variant that cascades `riseIn` children. Keep the stagger short so
// the list never feels like it's making the user wait.
export function staggerChildren(delay = 0.04): Variants {
  return {
    hidden: {},
    visible: { transition: { staggerChildren: delay } },
  };
}

// Crossfade with a touch of blur, which blends the outgoing and incoming
// states so the swap reads as one transformation rather than two objects.
export const blurSwap: Variants = {
  hidden: { opacity: 0, filter: "blur(2px)" },
  visible: { opacity: 1, filter: "blur(0px)", transition: enterTransition },
  exit: { opacity: 0, filter: "blur(2px)", transition: exitTransition },
};
