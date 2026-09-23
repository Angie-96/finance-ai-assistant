"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  CrosshairMode,
  type Time,
} from "lightweight-charts";
import type { HistoricalPrice } from "@/lib/schemas/finance";

type Tooltip = {
  x: number;
  y: number;
  flip: boolean;
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

function isDarkTheme(): boolean {
  return document.documentElement.getAttribute("data-theme") === "dark";
}

function palette(isDark: boolean) {
  return {
    text: isDark ? "#d4d4d8" : "#3f3f46",
    grid: isDark ? "#27272a" : "#f4f4f5",
    border: isDark ? "#3f3f46" : "#e4e4e7",
    up: "#059669",
    down: "#dc2626",
  };
}

function formatChartTime(time: Time): string {
  if (typeof time === "string") return time;
  if (typeof time === "number") {
    return new Date(time * 1000).toISOString().slice(0, 10);
  }
  const { year, month, day } = time;
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function CandlestickChart({ candles }: { candles: HistoricalPrice[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || candles.length === 0) return;

    const colors = palette(isDarkTheme());

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 280,
      layout: {
        background: { color: "transparent" },
        textColor: colors.text,
      },
      grid: {
        vertLines: { color: colors.grid },
        horzLines: { color: colors.grid },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      timeScale: { borderColor: colors.border },
      rightPriceScale: { borderColor: colors.border },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: colors.up,
      downColor: colors.down,
      borderVisible: false,
      wickUpColor: colors.up,
      wickDownColor: colors.down,
    });

    series.setData(
      candles.map((c) => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );

    chart.timeScale().fitContent();

    chart.subscribeCrosshairMove((param) => {
      const candle = param.time && param.point
        ? (param.seriesData.get(series) as
            | { open: number; high: number; low: number; close: number }
            | undefined)
        : undefined;

      if (!param.point || !param.time || !candle) {
        setTooltip(null);
        return;
      }

      setTooltip({
        x: param.point.x,
        y: param.point.y,
        flip: param.point.x > container.clientWidth / 2,
        time: formatChartTime(param.time),
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      });
    });

    const handleResize = () => {
      chart.applyOptions({ width: container.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    const themeObserver = new MutationObserver(() => {
      const next = palette(isDarkTheme());
      chart.applyOptions({
        layout: { textColor: next.text },
        grid: {
          vertLines: { color: next.grid },
          horzLines: { color: next.grid },
        },
        timeScale: { borderColor: next.border },
        rightPriceScale: { borderColor: next.border },
      });
      series.applyOptions({
        upColor: next.up,
        downColor: next.down,
        wickUpColor: next.up,
        wickDownColor: next.down,
      });
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    return () => {
      window.removeEventListener("resize", handleResize);
      themeObserver.disconnect();
      chart.remove();
      setTooltip(null);
    };
  }, [candles]);

  if (candles.length === 0) {
    return (
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        No historical data found.
      </p>
    );
  }

  return (
    <div className="relative w-full rounded-lg border border-zinc-200 dark:border-zinc-800">
      <div ref={containerRef} className="w-full" />
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-zinc-200 bg-white/95 px-2.5 py-1.5 text-xs shadow-md backdrop-blur-sm dark:border-zinc-700 dark:bg-zinc-900/95"
          style={{
            left: tooltip.flip ? tooltip.x - 8 : tooltip.x + 8,
            top: tooltip.y - 8,
            transform: `translate(${tooltip.flip ? "-100%" : "0%"}, -100%)`,
          }}
        >
          <p className="font-mono font-medium text-zinc-900 dark:text-zinc-50">
            {tooltip.time}
          </p>
          <p className="text-zinc-600 dark:text-zinc-400">
            O <span className="font-mono">{tooltip.open.toFixed(2)}</span>{" "}
            H <span className="font-mono">{tooltip.high.toFixed(2)}</span>
          </p>
          <p className="text-zinc-600 dark:text-zinc-400">
            L <span className="font-mono">{tooltip.low.toFixed(2)}</span>{" "}
            C <span className="font-mono">{tooltip.close.toFixed(2)}</span>
          </p>
        </div>
      )}
    </div>
  );
}
