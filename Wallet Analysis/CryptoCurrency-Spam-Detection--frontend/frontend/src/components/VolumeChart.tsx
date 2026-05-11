import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TransactionItem } from "../types/api";
import { Skeleton } from "./Skeleton";

type Props = {
  items: TransactionItem[];
  unit: string;
  loading?: boolean;
};

type Point = { day: string; volume: number };

function parseAmount(v: number | string): number {
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : 0;
}

export function VolumeChart({ items, unit, loading }: Props) {
  const data = useMemo<Point[]>(() => {
    const map = new Map<string, number>();
    for (const t of items) {
      if (!t.date) continue;
      const d = new Date(t.date);
      if (Number.isNaN(d.getTime())) continue;
      const key = d.toISOString().slice(0, 10); // YYYY-MM-DD
      map.set(key, (map.get(key) ?? 0) + Math.abs(parseAmount(t.amount)));
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([day, volume]) => ({ day, volume }));
  }, [items]);

  return (
    <div className="glass glass-hover w-full p-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-100">
            Volume (derived)
          </div>
          <div className="mt-1 text-xs text-gray-400">
            Aggregated from loaded transactions (not mock data).
          </div>
        </div>
        <div className="pill">{unit}</div>
      </div>

      <div className="relative mt-4 h-64 w-full min-w-0">
        {loading ? (
          <Skeleton className="h-full w-full rounded-2xl" />
        ) : data.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-white/10 bg-white/[0.02] text-sm text-gray-400">
            No chart data yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={256}>
            <AreaChart
              data={data}
              margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="vol" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor="rgb(124, 58, 237)"
                    stopOpacity={0.45}
                  />
                  <stop
                    offset="100%"
                    stopColor="rgb(124, 58, 237)"
                    stopOpacity={0.05}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis
                dataKey="day"
                tick={{ fill: "rgba(229,231,235,0.6)", fontSize: 12 }}
                axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "rgba(229,231,235,0.6)", fontSize: 12 }}
                axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(0,0,0,0.85)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  borderRadius: 12,
                }}
                labelStyle={{ color: "rgba(229,231,235,0.9)" }}
              />
              <Area
                type="monotone"
                dataKey="volume"
                stroke="rgb(124, 58, 237)"
                fill="url(#vol)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
