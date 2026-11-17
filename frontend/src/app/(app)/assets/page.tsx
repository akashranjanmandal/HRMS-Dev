"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Asset {
  id: number;
  asset_code: string;
  name: string;
  category: string;
  custodian_employee_id: number | null;
  custodian_name: string | null;
  condition: string;
  status: string;
  purchase_value: number;
}

interface Employee {
  id: number;
  full_name: string;
  employee_code: string;
}

const STATUS_CHIP: Record<string, string> = {
  in_store: "chip-mute",
  issued: "chip-ok",
  pending_return_approval: "chip-warn",
  disposed: "chip-bad",
};

const CATEGORIES = ["field_equipment", "it_equipment", "vehicle", "furniture", "other"];

export default function AssetsPage() {
  const { hasPermission } = useAuth();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [issueFor, setIssueFor] = useState<Asset | null>(null);
  const [newAsset, setNewAsset] = useState({ name: "", category: "field_equipment", purchase_value: "" });
  const [issueEmployeeId, setIssueEmployeeId] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  const canCreate = hasPermission("asset:create");
  const canEdit = hasPermission("asset:edit");
  const canDelete = hasPermission("asset:delete");

  const load = () => {
    api.get<Asset[]>("/api/assets").then(setAssets).catch(() => {});
    api.get<Employee[]>("/api/employees").then(setEmployees).catch(() => {});
  };
  useEffect(load, []);

  const counts = useMemo(() => {
    const byStatus: Record<string, number> = {};
    for (const a of assets) byStatus[a.status] = (byStatus[a.status] ?? 0) + 1;
    return byStatus;
  }, [assets]);

  const totalValue = useMemo(() => assets.reduce((sum, a) => sum + a.purchase_value, 0), [assets]);

  const filtered = assets.filter((a) => {
    const q = query.toLowerCase();
    const matchesQuery = a.name.toLowerCase().includes(q) || a.asset_code.toLowerCase().includes(q) || (a.custodian_name ?? "").toLowerCase().includes(q);
    const matchesStatus = !statusFilter || a.status === statusFilter;
    return matchesQuery && matchesStatus;
  });

  async function createAsset(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/api/assets", {
        name: newAsset.name,
        category: newAsset.category,
        purchase_value: newAsset.purchase_value ? Number(newAsset.purchase_value) : 0,
      });
      setShowNew(false);
      setNewAsset({ name: "", category: "field_equipment", purchase_value: "" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the asset");
    }
  }

  async function issue(e: React.FormEvent) {
    e.preventDefault();
    if (!issueFor) return;
    setError("");
    try {
      await api.post(`/api/assets/${issueFor.id}/issue`, { employee_id: Number(issueEmployeeId) });
      setIssueFor(null);
      setIssueEmployeeId("");
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not issue the asset");
    }
  }

  async function returnAsset(asset: Asset) {
    setError("");
    try {
      await api.post(`/api/assets/${asset.id}/return`, {});
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start the return");
    }
  }

  async function dispose(asset: Asset) {
    setError("");
    try {
      await api.post(`/api/assets/${asset.id}/dispose`, { notes: "Disposed via asset register" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not dispose the asset");
    }
  }

  return (
    <div className="grid gap-5 max-w-6xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
            Asset Register
          </h1>
          <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
            {assets.length} {assets.length === 1 ? "asset" : "assets"} · ₹{totalValue.toLocaleString()} total value
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--color-ink-faint)" }} />
            <input className="input pl-9 w-56" placeholder="Search assets…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          {canCreate && (
            <button className="btn btn-primary" onClick={() => setShowNew((s) => !s)}>
              <Plus size={16} /> New asset
            </button>
          )}
        </div>
      </div>

      {error && <div className="card chip-bad">{error}</div>}

      <div className="grid gap-3 sm:grid-cols-4">
        <AssetStatTile label="In store" value={counts.in_store ?? 0} tone="mute" />
        <AssetStatTile label="Issued" value={counts.issued ?? 0} tone="ok" />
        <AssetStatTile label="Pending return" value={counts.pending_return_approval ?? 0} tone="warn" />
        <AssetStatTile label="Disposed" value={counts.disposed ?? 0} tone="bad" />
      </div>

      <div className="flex gap-2 flex-wrap">
        <button className={`chip ${statusFilter === null ? "chip-info" : "chip-mute"}`} onClick={() => setStatusFilter(null)}>
          All
        </button>
        {Object.keys(STATUS_CHIP).map((s) => (
          <button key={s} className={`chip ${statusFilter === s ? "chip-info" : "chip-mute"}`} onClick={() => setStatusFilter(s)}>
            {s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {showNew && (
        <form onSubmit={createAsset} className="card grid gap-3 sm:grid-cols-3">
          <div className="sm:col-span-1">
            <label className="label">Name</label>
            <input className="input" required value={newAsset.name} onChange={(e) => setNewAsset({ ...newAsset, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Category</label>
            <select className="input" value={newAsset.category} onChange={(e) => setNewAsset({ ...newAsset, category: e.target.value })}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Purchase value (₹)</label>
            <input
              className="input"
              type="number"
              min={0}
              value={newAsset.purchase_value}
              onChange={(e) => setNewAsset({ ...newAsset, purchase_value: e.target.value })}
            />
          </div>
          <div className="sm:col-span-3">
            <button className="btn btn-primary">Create</button>
          </div>
        </form>
      )}

      {issueFor && (
        <form onSubmit={issue} className="card grid gap-3 sm:grid-cols-[1fr_auto_auto]">
          <div>
            <label className="label">Issue &ldquo;{issueFor.name}&rdquo; to</label>
            <select className="input" required value={issueEmployeeId} onChange={(e) => setIssueEmployeeId(e.target.value)}>
              <option value="">Select employee…</option>
              {employees.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.full_name} ({e.employee_code})
                </option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary self-end">Issue</button>
          <button type="button" className="btn btn-ghost self-end" onClick={() => setIssueFor(null)}>
            Cancel
          </button>
        </form>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
              <th className="pb-2 font-medium">Code</th>
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Category</th>
              <th className="pb-2 font-medium">Custodian</th>
              <th className="pb-2 font-medium">Condition</th>
              <th className="pb-2 font-medium">Status</th>
              {(canEdit || canDelete) && <th className="pb-2 font-medium"></th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr key={a.id} style={{ borderTop: "1px solid var(--color-line)" }}>
                <td className="py-2 font-mono text-xs">{a.asset_code}</td>
                <td className="py-2 font-medium">{a.name}</td>
                <td className="py-2">{a.category.replace(/_/g, " ")}</td>
                <td className="py-2">{a.custodian_name ?? "—"}</td>
                <td className="py-2">{a.condition.replace(/_/g, " ")}</td>
                <td className="py-2">
                  <span className={`chip ${STATUS_CHIP[a.status] ?? "chip-mute"}`}>{a.status.replace(/_/g, " ")}</span>
                </td>
                {(canEdit || canDelete) && (
                  <td className="py-2 text-right whitespace-nowrap">
                    {canEdit && a.status === "in_store" && (
                      <button className="btn btn-ghost h-7 px-2 text-xs" onClick={() => setIssueFor(a)}>
                        Issue
                      </button>
                    )}
                    {canEdit && a.status === "issued" && (
                      <button className="btn btn-ghost h-7 px-2 text-xs" onClick={() => returnAsset(a)}>
                        Return
                      </button>
                    )}
                    {canDelete && a.status === "in_store" && (
                      <button className="btn btn-ghost h-7 px-2 text-xs" style={{ color: "var(--color-bad)" }} onClick={() => dispose(a)}>
                        Dispose
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-10 text-center grid gap-1">
            <p className="text-sm font-medium">{assets.length === 0 ? "No assets registered yet." : "No assets match these filters."}</p>
            {assets.length > 0 && (
              <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
                Try clearing the search or status filter above.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function AssetStatTile({ label, value, tone }: { label: string; value: number; tone: "ok" | "warn" | "bad" | "mute" }) {
  const colors = {
    ok: { bg: "var(--color-ok-tint)", fg: "var(--color-ok)" },
    warn: { bg: "var(--color-warn-tint)", fg: "var(--color-warn)" },
    bad: { bg: "var(--color-bad-tint)", fg: "var(--color-bad)" },
    mute: { bg: "var(--color-surface-2)", fg: "var(--color-ink-soft)" },
  }[tone];
  return (
    <div className="card flex items-center justify-between">
      <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
        {label}
      </span>
      <span className="text-lg font-bold px-3 py-1 rounded-full" style={{ background: colors.bg, color: colors.fg }}>
        {value}
      </span>
    </div>
  );
}
