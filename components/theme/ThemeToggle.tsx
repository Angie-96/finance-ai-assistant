"use client";

import { useLayoutEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { EASE_OUT } from "@/components/motion/transitions";

type Theme = "light" | "dark";

function readActiveTheme(): Theme {
  const stored = window.localStorage.getItem("theme");
  if (stored === "dark" || stored === "light") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function ThemeToggle() {
  // Always starts as "light" so the server render and the initial client
  // hydration render match exactly (the server has no access to
  // localStorage/matchMedia). The real theme is applied right after mount,
  // before paint, via useLayoutEffect below.
  const [theme, setTheme] = useState<Theme>("light");
  // Only animate the icon swap once the user has clicked; the post-mount
  // correction to the stored theme should swap instantly.
  const [hasToggled, setHasToggled] = useState(false);

  useLayoutEffect(() => {
    const active = readActiveTheme();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- correcting SSR-unknowable state (localStorage/matchMedia) once after mount, before paint; this is the one-time hydration fixup, not an external-state subscription.
    setTheme(active);
    document.documentElement.setAttribute("data-theme", active);
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    setHasToggled(true);
    document.documentElement.setAttribute("data-theme", next);
    window.localStorage.setItem("theme", next);
  };

  const label =
    theme === "dark" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="relative flex h-9 w-9 items-center justify-center rounded-full text-zinc-500 transition-transform hover:bg-zinc-100 active:scale-90 dark:text-zinc-400 dark:hover:bg-zinc-800"
    >
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={theme}
          initial={{ opacity: 0, rotate: -90, scale: 0.8 }}
          animate={{ opacity: 1, rotate: 0, scale: 1 }}
          exit={{ opacity: 0, rotate: 90, scale: 0.8 }}
          transition={
            hasToggled ? { duration: 0.2, ease: EASE_OUT } : { duration: 0 }
          }
          className="flex"
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}

function SunIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      className="h-5 w-5"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden="true"
    >
      <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" />
    </svg>
  );
}
