import {
  ChevronDown,
  RefreshCcw,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { RiskFactor } from "../types/api";

type Props = {
  factors: RiskFactor[];
  onSelectFactor: (factor: RiskFactor) => void;
  onRecalculate: () => void;
  loading?: boolean;
};

const RISK_CATEGORIES = [
  "OFAC sanctions",
  "Phishing / Scam",
  "Mixer (Tornado Cash)",
  "Ransomware",
  "Stolen funds",
  "Darknet market",
] as const;

function sevPill(severity: RiskFactor["severity"]) {
  if (severity === "High")
    return "border-rose-400/20 bg-rose-500/10 text-rose-200";
  if (severity === "Medium")
    return "border-amber-400/20 bg-amber-500/10 text-amber-200";
  return "border-emerald-400/20 bg-emerald-500/10 text-emerald-200";
}

function mapToCategory(title: string, description: string): string | null {
  const text = `${title} ${description}`.toLowerCase();
  if (text.includes("sanction") || text.includes("ofac")) return "OFAC sanctions";
  if (text.includes("phish") || text.includes("scam") || text.includes("fraud"))
    return "Phishing / Scam";
  if (
    text.includes("mixer") ||
    text.includes("tornado") ||
    text.includes("tumbler")
  )
    return "Mixer (Tornado Cash)";
  if (text.includes("ransom")) return "Ransomware";
  if (
    text.includes("stolen") ||
    text.includes("theft") ||
    text.includes("hack")
  )
    return "Stolen funds";
  if (text.includes("darknet") || text.includes("dark web")) return "Darknet market";
  return null;
}

export function RiskBreakdownPanel({
  factors,
  onSelectFactor,
  onRecalculate,
  loading,
}: Props) {
  const [open, setOpen] = useState(true);

  const hasFactors = factors.length > 0;

  const categoryDetected = useMemo(() => {
    const detected: Record<string, boolean> = {};
    RISK_CATEGORIES.forEach((cat) => (detected[cat] = false));

    factors.forEach((f) => {
      const cat = mapToCategory(f.title, f.description || "");
      if (cat) {
        detected[cat] = true;
      }
    });
    return detected;
  }, [factors]);

  const summary = useMemo(() => {
    const counts = { Low: 0, Medium: 0, High: 0 } as Record<
      RiskFactor["severity"],
      number
    >;
    for (const f of factors) counts[f.severity] = (counts[f.severity] ?? 0) + 1;
    return counts;
  }, [factors]);

  return (
    <div className="glass w-full overflow-hidden">
      <div className="flex w-full items-center justify-between gap-4 border-b border-white/10 p-4 text-left">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-2">
            <ShieldAlert className="h-5 w-5 text-violet-300" />
          </div>
          <div>
            <div className="text-sm font-semibold text-gray-100">
              Risk Analysis
            </div>
            <div className="mt-1 text-xs text-gray-400">
              {hasFactors
                ? `${summary.High} high • ${summary.Medium} medium • ${summary.Low} low`
                : "No factors returned yet"}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-ghost"
            onClick={(e) => {
              e.stopPropagation();
              onRecalculate();
            }}
            disabled={loading}
          >
            <RefreshCcw
              className={["h-4 w-4", loading ? "animate-spin" : ""].join(" ")}
            />
            Recalculate Risk
          </button>
        </div>
      </div>

      <div className="p-4 space-y-6">
        <div>
          <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-gray-500">
            <TriangleAlert className="h-3.5 w-3.5" />
            Risk Category Breakdown
          </div>
          <div className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.02]">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 bg-white/[0.03] text-xs uppercase text-gray-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Risk Category</th>
                  <th className="px-4 py-2 text-right font-medium">Is Detected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {RISK_CATEGORIES.map((cat) => (
                  <tr
                    key={cat}
                    className="hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="px-4 py-2.5 text-gray-300">{cat}</td>
                    <td
                      className={`px-4 py-2.5 text-right font-mono ${
                        categoryDetected[cat]
                          ? "text-rose-400 font-bold"
                          : "text-gray-500"
                      }`}
                    >
                      {categoryDetected[cat] ? "Yes" : "No"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <button
            type="button"
            className="mb-3 flex w-full items-center justify-between text-xs font-bold uppercase tracking-wider text-gray-500"
            onClick={() => setOpen(!open)}
          >
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-3.5 w-3.5" />
              Specific Risk Factors
            </div>
            <ChevronDown
              className={["h-4 w-4 transition", open ? "rotate-180" : ""].join(
                " ",
              )}
            />
          </button>

          {open && (
            <div className="grid gap-3">
              {factors.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">
                  No specific risk factors detected for this address.
                </div>
              ) : (
                factors.map((f, idx) => (
                  <button
                    key={f.id ?? `${f.title}-${idx}`}
                    type="button"
                    className="glass glass-hover flex w-full items-start justify-between gap-4 p-4 text-left"
                    onClick={() => onSelectFactor(f)}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-gray-100">
                        {f.title}
                      </div>
                      <div className="mt-1 text-xs text-gray-400">
                        {f.description ?? "Click to filter transactions"}
                      </div>
                    </div>
                    <div
                      className={`shrink-0 rounded-full border px-3 py-1 text-xs ${sevPill(
                        f.severity,
                      )}`}
                    >
                      {f.severity}
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
