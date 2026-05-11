import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { TriangleAlert, BadgeCheck } from "lucide-react";
import type { ChainId } from "../lib/chains";
import { fetchAddressApprovals, fetchAddressDapps } from "../lib/endpoints";
import type {
  ApprovalItem,
  ApprovalsResponse,
  DappProtocol,
  DappsResponse,
} from "../types/api";
import { Skeleton } from "./Skeleton";

type Props = {
  address: string;
  chain: ChainId;
  onFilterTransactions: (query: string) => void;
};

function riskPill(risk: string) {
  if (risk === "High") return "border-rose-400/20 bg-rose-500/10 text-rose-200";
  if (risk === "Medium")
    return "border-amber-400/20 bg-amber-500/10 text-amber-200";
  return "border-emerald-400/20 bg-emerald-500/10 text-emerald-200";
}

function protoColor(name: string) {
  const k = name.toLowerCase();
  if (k.includes("uni")) return "from-pink-500/30 to-violet-500/10";
  if (k.includes("aave")) return "from-sky-500/30 to-violet-500/10";
  if (k.includes("curve")) return "from-emerald-500/30 to-sky-500/10";
  if (k.includes("compound")) return "from-emerald-500/30 to-emerald-500/10";
  if (k.includes("opensea")) return "from-sky-500/30 to-sky-500/10";
  return "from-violet-500/30 to-cyan-500/10";
}

export function DappsPanel({ address, chain, onFilterTransactions }: Props) {
  const [loading, setLoading] = useState(false);
  const [dapps, setDapps] = useState<DappsResponse | null>(null);
  const [approvals, setApprovals] = useState<ApprovalsResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, a] = await Promise.all([
        fetchAddressDapps(address, chain),
        fetchAddressApprovals(address, chain),
      ]);
      setDapps(d);
      setApprovals(a);
    } catch {
      toast.error("Failed to load DApp data");
    } finally {
      setLoading(false);
    }
  }, [address, chain]);

  useEffect(() => {
    load();
  }, [load]);

  const protocols = useMemo(
    () => (dapps?.protocols ?? []) as DappProtocol[],
    [dapps?.protocols],
  );
  const approvalItems = useMemo(
    () => (approvals?.items ?? []) as ApprovalItem[],
    [approvals?.items],
  );

  return (
    <div className="grid gap-4">
      <div className="glass glass-hover p-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-gray-100">
              DeFi & DApp interactions
            </div>
            <div className="mt-1 text-xs text-gray-400">
              Protocols + token approvals.
            </div>
          </div>
          <button
            type="button"
            className="btn-primary"
            onClick={load}
            disabled={loading}
          >
            {loading ? "Loading…" : "Reload"}
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass p-4">
          <div className="text-sm font-semibold text-gray-100">Protocols</div>
          <div className="mt-3 grid gap-3">
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))
            ) : protocols.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-sm text-gray-400">
                No protocol interactions returned by API.
              </div>
            ) : (
              protocols.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="glass glass-hover flex w-full items-center justify-between gap-4 p-4 text-left"
                  onClick={() => onFilterTransactions(p.name)}
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div
                      className={`h-10 w-10 rounded-2xl border border-white/10 bg-gradient-to-br ${protoColor(
                        p.name,
                      )}`}
                    />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-gray-100">
                        {p.name}
                      </div>
                      <div className="mt-1 text-xs text-gray-400">
                        {p.txCount} tx • Vol {p.totalVolume}
                      </div>
                      <div className="mt-1 text-[11px] text-gray-500">
                        {p.firstInteraction
                          ? `First: ${new Date(
                              p.firstInteraction,
                            ).toLocaleDateString()}`
                          : "First: —"}{" "}
                        •{" "}
                        {p.lastInteraction
                          ? `Last: ${new Date(
                              p.lastInteraction,
                            ).toLocaleDateString()}`
                          : "Last: —"}
                      </div>
                    </div>
                  </div>
                  <div
                    className={`shrink-0 rounded-full border px-3 py-1 text-xs ${riskPill(
                      p.risk,
                    )}`}
                  >
                    {p.risk}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="glass p-4">
          <div className="text-sm font-semibold text-gray-100">
            Token approvals
          </div>
          <div className="mt-1 text-xs text-gray-400">
            Warnings for unlimited approvals.
          </div>
          <div className="mt-3 w-full overflow-x-auto">
            <table className="min-w-[820px] w-full text-left text-sm">
              <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="px-4 py-3">Token</th>
                  <th className="px-4 py-3">Spender</th>
                  <th className="px-4 py-3">Allowance</th>
                  <th className="px-4 py-3">Approval date</th>
                  <th className="px-4 py-3">Revoke risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 5 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-32" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : approvalItems.length === 0 ? (
                  <tr>
                    <td
                      className="px-4 py-10 text-center text-sm text-gray-400"
                      colSpan={5}
                    >
                      No approvals returned by API.
                    </td>
                  </tr>
                ) : (
                  approvalItems.map((a, idx) => (
                    <tr
                      key={`${a.token}-${idx}`}
                      className="hover:bg-white/[0.02]"
                    >
                      <td className="px-4 py-3 text-gray-200">{a.token}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-300">
                        {a.spender}
                      </td>
                      <td className="px-4 py-3 text-gray-200">
                        <span className="inline-flex items-center gap-2">
                          {a.allowance}
                          {a.unlimited ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/20 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-200">
                              <TriangleAlert className="h-3.5 w-3.5" />
                              Unlimited
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/20 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-200">
                              <BadgeCheck className="h-3.5 w-3.5" />
                              Limited
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-300">
                        {a.approvalDate
                          ? new Date(a.approvalDate).toLocaleString()
                          : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full border px-3 py-1 text-xs ${riskPill(
                            a.revokeRisk,
                          )}`}
                        >
                          {a.revokeRisk}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
