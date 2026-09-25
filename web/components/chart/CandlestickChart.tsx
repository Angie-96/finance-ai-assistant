"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  CrosshairMode,
  type Time,
} from "lightweight-charts";
import type { HistoricalPrice } from "@/lib/schemas/finance";
import { formatDate } from "@/lib/format-date";

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
  if (typeof time === "string") return formatDate(time);
  if (typeof time === "number") return formatDate(new Date(time * 1000));
  const { year, month, day } = time;
  return formatDate(new Date(Date.UTC(year, month - 1, day)));
}

function describeCandles(candles: HistoricalPrice[], symbol?: string): string {
  const first = candles[0];
  const last = candles[candles.length - 1];
  const change = ((last.close - first.close) / first.close) * 100;
  const low = Math.min(...candles.map((c) => c.low));
  const high = Math.max(...candles.map((c) => c.high));
  return [
    `${symbol ? `${symbol} daily` : "Daily"} price chart, ${formatDate(first.time)} to ${formatDate(last.time)}.`,
    `Closed at $${first.close.toFixed(2)}, then $${last.close.toFixed(2)} (${change >= 0 ? "+" : ""}${change.toFixed(2)}%).`,
    `Range: low $${low.toFixed(2)}, high $${high.toFixed(2)}.`,
  ].join(" ");
}

export function CandlestickChart({
  candles,
  symbol,
}: {
  candles: HistoricalPrice[];
  symbol?: string;
}) {
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
        // Attribution is a visible link under the chart instead, which keeps
        // it reachable while the canvas is hidden from assistive tech.
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: colors.grid },
        horzLines: { color: colors.grid },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      localization: { timeFormatter: formatChartTime },
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
      const candle =
        param.time && param.point
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
    <figure className="flex flex-col gap-1">
      {/* The canvas and hover tooltip are pointer-only; screen readers get the
        summary and data table in the figcaption instead. */}
      <div
        aria-hidden="true"
        className="relative w-full rounded-lg border border-zinc-200 dark:border-zinc-800"
      >
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
              O <span className="font-mono">{tooltip.open.toFixed(2)}</span> H{" "}
              <span className="font-mono">{tooltip.high.toFixed(2)}</span>
            </p>
            <p className="text-zinc-600 dark:text-zinc-400">
              L <span className="font-mono">{tooltip.low.toFixed(2)}</span> C{" "}
              <span className="font-mono">{tooltip.close.toFixed(2)}</span>
            </p>
          </div>
        )}
      </div>
      <figcaption className="flex justify-end text-[11px] text-zinc-500 dark:text-zinc-400">
        <span className="sr-only">{describeCandles(candles, symbol)}</span>
        <a
          href="https://www.tradingview.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline-offset-2 hover:underline"
        >
          Chart by TradingView
        </a>
      </figcaption>
      {/* sr-only goes on a wrapper: tables ignore height/overflow, so an
          sr-only <table> still grows to its full height and adds scroll. */}
      <div className="sr-only">
        <table>
          <caption>{symbol ?? "Daily"} prices</caption>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Open</th>
              <th scope="col">High</th>
              <th scope="col">Low</th>
              <th scope="col">Close</th>
            </tr>
          </thead>
          <tbody>
            {candles.map((c) => (
              <tr key={c.time}>
                <th scope="row">{formatDate(c.time)}</th>
                <td>{c.open.toFixed(2)}</td>
                <td>{c.high.toFixed(2)}</td>
                <td>{c.low.toFixed(2)}</td>
                <td>{c.close.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
