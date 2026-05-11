import { ExternalLink, Search, SortAsc, SortDesc } from "lucide-react";
import { useMemo, useState } from "react";
import type { TransactionItem } from "../types/api";
import type { ChainId } from "../lib/chains";
import { shortenAddress } from "../lib/address";
import { explorerTxUrl } from "../lib/explorers";
import { Skeleton } from "./Skeleton";

type SortKey = "hash" | "from" | "to" | "amount" | "date";
type SortDir = "asc" | "desc";

type Props = {
  chain: ChainId;
  unit: string;
  items: TransactionItem[];
  loading?: boolean;
  filterQuery?: string;
  onClearFilterQuery?: () => void;
  page: number;
  limit: number;
  total: number;
  startDate?: Date | null;
  endDate?: Date | null;
  onPrev: () => void;
  onNext: () => void;
  onClearDates?: () => void;
};

function formatNum(value: number | string) {
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return String(value);
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 8 }).format(
    n,
  );
}

function sortValue(t: TransactionItem, key: SortKey): string | number {
  if (key === "amount")
    return typeof t.amount === "string" ? Number(t.amount) : t.amount;
  if (key === "date") return new Date(t.date).getTime();
  return String((t as Record<string, unknown>)[key] ?? "");
}

export function TransactionTable({
  chain,
  unit,
  items,
  loading,
  filterQuery,
  onClearFilterQuery,
  page,
  limit,
  total,
  startDate,
  endDate,
  onPrev,
  onNext,
  onClearDates,
}: Props) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const filteredSorted = useMemo(() => {
    const q = (filterQuery ?? query).trim().toLowerCase();
    const filtered = q
      ? items.filter((t) => {
          const h = (t.hash ?? "").toLowerCase();
          const f = (t.from ?? "").toLowerCase();
          const to = (t.to ?? "").toLowerCase();
          return h.includes(q) || f.includes(q) || to.includes(q);
        })
      : items;
    const sorted = [...filtered].sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [items, filterQuery, query, sortDir, sortKey]);

  const maxPage = Math.max(1, Math.ceil(total / limit));
  const canPrev = page > 1 && !loading;
  const canNext = page < maxPage && !loading;

  const startIdx = (page - 1) * limit + 1;
  const endIdx = Math.min(page * limit, total);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDir("asc");
  };

  const SortIcon = sortDir === "asc" ? SortAsc : SortDesc;

  const hasDateFilter = startDate || endDate;

  return (
    <div className="glass w-full overflow-hidden">
      {hasDateFilter && (
        <div className="flex items-center justify-between bg-blue-500/10 border-b border-blue-500/20 px-4 py-2.5 text-xs text-blue-200">
          <div className="flex items-center gap-2">
            <span className="font-medium">Active Filter:</span>
            <span>
              Transactions from{" "}
              <span className="text-white font-semibold">
                {startDate ? startDate.toLocaleDateString() : "Beginning"}
              </span>{" "}
              to{" "}
              <span className="text-white font-semibold">
                {endDate ? endDate.toLocaleDateString() : "Latest"}
              </span>
            </span>
          </div>
          {onClearDates && (
            <button
              onClick={onClearDates}
              className="text-blue-300 hover:text-white underline underline-offset-2 transition"
            >
              Clear Filter
            </button>
          )}
        </div>
      )}

      <div className="flex flex-col gap-3 border-b border-white/10 p-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-sm font-semibold text-gray-100">
            Transaction history
          </div>
          <div className="mt-1 text-xs text-gray-400">
            Click headers to sort. Filter by TX hash.
          </div>
        </div>

        <div className="flex w-full max-w-md flex-col gap-2">
          {filterQuery ? (
            <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-gray-200">
              <span className="truncate">Filtered by: {filterQuery}</span>
              {onClearFilterQuery ? (
                <button
                  type="button"
                  className="text-gray-300 hover:text-white"
                  onClick={onClearFilterQuery}
                >
                  Clear
                </button>
              ) : null}
            </div>
          ) : null}
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="input pl-10"
              placeholder="Search by tx hash / from / to…"
              disabled={Boolean(filterQuery)}
            />
          </div>
        </div>
      </div>

      <div className="w-full overflow-x-auto">
        <table className="min-w-[980px] w-full text-left text-sm">
          <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-gray-400">
            <tr>
              {[
                { key: "hash", label: "TX Hash" },
                { key: "type", label: "Type" },
                { key: "from", label: "From" },
                { key: "to", label: "To" },
                { key: "amount", label: "Amount" },
                { key: "date", label: "Date" },
              ].map((h) => (
                <th key={h.key} className="px-4 py-3">
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 hover:text-gray-200"
                    onClick={() => toggleSort(h.key as SortKey)}
                  >
                    {h.label}
                    {sortKey === h.key ? (
                      <SortIcon className="h-3.5 w-3.5" />
                    ) : null}
                  </button>
                </th>
              ))}
              <th className="px-4 py-3">Link</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-white/10">
            {loading ? (
              Array.from({ length: 10 }).map((_, i) => (
                <tr key={i} className="hover:bg-white/[0.02]">
                  <td className="px-4 py-3">
                    <Skeleton className="h-4 w-48" />
                  </td>
                  <td className="px-4 py-3">
                    <Skeleton className="h-4 w-16" />
                  </td>
                  <td className="px-4 py-3">
                    <Skeleton className="h-4 w-40" />
                  </td>
                  <td className="px-4 py-3">
                    <Skeleton className="h-4 w-40" />
                  </td>
                  <td className="px-4 py-3">
                    <Skeleton className="h-4 w-24" />
                  </td>
                  <td className="px-4 py-3">
                    <Skeleton className="h-4 w-36" />
                  </td>
                  <td className="px-4 py-3">
                    <Skeleton className="h-4 w-10" />
                  </td>
                </tr>
              ))
            ) : filteredSorted.length === 0 ? (
              <tr>
                <td
                  className="px-4 py-10 text-center text-sm text-gray-400"
                  colSpan={6}
                >
                  No transactions found for the current filters.
                </td>
              </tr>
            ) : (
              filteredSorted.map((t) => (
                <tr key={t.hash} className="hover:bg-white/[0.02]">
                  <td className="px-4 py-3 font-mono text-xs text-gray-200">
                    {shortenAddress(t.hash, 12, 8)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={[
                        "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
                        t.type === "swap"
                          ? "bg-indigo-500/20 text-indigo-300"
                          : t.type === "send"
                          ? "bg-rose-500/20 text-rose-300"
                          : t.type === "receive"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : t.type === "buy"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-gray-500/20 text-gray-400",
                      ].join(" ")}
                    >
                      {t.type || "transfer"}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-300">
                    {t.from ? shortenAddress(t.from) : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-300">
                    {t.to ? shortenAddress(t.to) : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-100">
                    {formatNum(t.amount)} {unit}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {t.date ? new Date(t.date).toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <a
                      href={explorerTxUrl(chain, t.hash)}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-gray-200 transition hover:bg-white/[0.06]"
                    >
                      View <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-3 border-t border-white/10 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-xs text-gray-400">
          Showing{" "}
          <span className="text-gray-200">
            {startIdx}-{endIdx}
          </span>{" "}
          of{" "}
          <span className="text-gray-200">
            {new Intl.NumberFormat().format(total)}
          </span>{" "}
          transactions
          {maxPage > 1 && (
            <span className="ml-2">
              • Page {page} of {maxPage}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-ghost"
            onClick={onPrev}
            disabled={!canPrev}
          >
            Previous
          </button>
          <button
            type="button"
            className="btn-ghost"
            onClick={onNext}
            disabled={!canNext}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
