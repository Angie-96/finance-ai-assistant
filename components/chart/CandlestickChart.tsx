"use client";

import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries, type IChartApi } from "lightweight-charts";
import type { HistoricalPrice } from "@/lib/schemas/finance";

export function CandlestickChart({ candles }: { candles: HistoricalPrice[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || candles.length === 0) return;

    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 256,
      layout: {
        background: { color: "transparent" },
        textColor: isDark ? "#d4d4d8" : "#3f3f46",
      },
      grid: {
        vertLines: { color: isDark ? "#27272a" : "#f4f4f5" },
        horzLines: { color: isDark ? "#27272a" : "#f4f4f5" },
      },
      timeScale: { borderColor: isDark ? "#3f3f46" : "#e4e4e7" },
      rightPriceScale: { borderColor: isDark ? "#3f3f46" : "#e4e4e7" },
    });
    chartRef.current = chart;

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#059669",
      downColor: "#dc2626",
      borderVisible: false,
      wickUpColor: "#059669",
      wickDownColor: "#dc2626",
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

    const handleResize = () => {
      chart.applyOptions({ width: container.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
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
    <div
      ref={containerRef}
      className="w-full rounded-lg border border-zinc-200 dark:border-zinc-800"
    />
  );
}
