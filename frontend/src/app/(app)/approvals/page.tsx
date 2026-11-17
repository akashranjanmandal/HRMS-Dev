"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, X, Undo2, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api";

interface ApprovalStep {
  id: number;
  level_order: number;
  approver_name: string;
  action: string;
  remark: string;
  created_at: string;
}

interface ApprovalRequest {
  id: number;
  request_type: string;
  object_id: number;
  requested_by_name: string | null;
  status: string;
  current_level_order: number;
  summary: string;
  created_at: string;
  steps: ApprovalStep[];
}

interface ApprovalCount {
  request_type: string;
  label: string;
  pending_count: number;
}

type ViewMode = "board" | "list";

export default function ApprovalsPage() {
  const [requests, setRequests] = useState<ApprovalRequest[]>([]);
  const [counts, setCounts] = useState<ApprovalCount[]>([]);
  const [filter, setFilter] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<ViewMode>("board");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [remarks, setRemarks] = useState<Record<number, string>>({});

  const load = () => {
    const q = filter ? `?request_type=${filter}` : "";
    api.get<ApprovalRequest[]>(`/api/approvals${q}`).then(setRequests).catch(() => {});
    api.get<ApprovalCount[]>("/api/approvals/counts").then(setCounts).catch(() => {});
  };

  useEffect(load, [filter]);

  const filteredRequests = useMemo(() => {
    const q = query.toLowerCase();
    if (!q) return requests;
    return requests.filter((r) => r.summary.toLowerCase().includes(q) || (r.requested_by_name ?? "").toLowerCase().includes(q));
  }, [requests, query]);

  const columns = useMemo(() => {
    const byType = new Map<string, ApprovalRequest[]>();
    for (const r of filteredRequests) {
      const list = byType.get(r.request_type) ?? [];
      list.push(r);
      byType.set(r.request_type, list);
    }
    return counts
      .filter((c) => byType.has(c.request_type))
      .map((c) => ({ type: c.request_type, label: c.label, requests: byType.get(c.request_type) ?? [] }));
  }, [filteredRequests, counts]);

  async function decide(id: number, action: "approve" | "reject" | "return_for_correction") {
    setBusyId(id);
    setError("");
    try {
      await api.post(`/api/approvals/${id}/decide`, { action, remark: remarks[id] ?? "" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not record the decision");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="grid gap-5 max-w-6xl">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
            Approvals Center
          </h1>
          <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
            Everything pending your decision, across every module.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: "var(--color-ink-faint)" }} />
            <input className="input pl-8 h-8 text-xs w-48" placeholder="Search requests…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid var(--color-line)" }}>
            <button
              className="h-8 px-3 text-xs font-semibold"
              style={{
                background: view === "board" ? "var(--color-primary-tint)" : "var(--color-surface)",
                color: view === "board" ? "var(--color-primary)" : "var(--color-ink-soft)",
              }}
              onClick={() => setView("board")}
            >
              Board
            </button>
            <button
              className="h-8 px-3 text-xs font-semibold"
              style={{
                background: view === "list" ? "var(--color-primary-tint)" : "var(--color-surface)",
                color: view === "list" ? "var(--color-primary)" : "var(--color-ink-soft)",
              }}
              onClick={() => setView("list")}
            >
              List
            </button>
          </div>
        </div>
      </div>

      {error && <div className="card chip-bad">{error}</div>}

      <div className="flex gap-2 overflow-x-auto pb-1">
        <button className={`chip ${filter === null ? "chip-info" : "chip-mute"}`} onClick={() => setFilter(null)}>
          All
        </button>
        {counts.map((c) => (
          <button key={c.request_type} className={`chip ${filter === c.request_type ? "chip-info" : "chip-mute"}`} onClick={() => setFilter(c.request_type)}>
            {c.label} {c.pending_count > 0 && `(${c.pending_count})`}
          </button>
        ))}
      </div>

      {requests.length === 0 && (
        <div className="card py-10 text-center grid gap-1">
          <p className="text-sm font-medium">Nothing pending your decision right now.</p>
          <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
            New requests will show up here as soon as they need you.
          </p>
        </div>
      )}

      {requests.length > 0 && filteredRequests.length === 0 && (
        <div className="card py-8 text-center text-sm" style={{ color: "var(--color-ink-faint)" }}>
          No requests match &ldquo;{query}&rdquo;.
        </div>
      )}

      {view === "board" ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 items-start">
          {columns.map((col) => (
            <div key={col.type} className="grid gap-3 content-start">
              <div className="flex items-center justify-between px-1">
                <h3 className="text-sm font-semibold">{col.label}</h3>
                <span className="chip chip-mute">{col.requests.length}</span>
              </div>
              <div className="grid gap-3">
                {col.requests.map((r) => (
                  <ApprovalCard key={r.id} request={r} busy={busyId === r.id} remark={remarks[r.id] ?? ""} onRemarkChange={(v) => setRemarks({ ...remarks, [r.id]: v })} onDecide={decide} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid gap-3">
          {filteredRequests.map((r) => (
            <ApprovalCard key={r.id} request={r} busy={busyId === r.id} remark={remarks[r.id] ?? ""} onRemarkChange={(v) => setRemarks({ ...remarks, [r.id]: v })} onDecide={decide} showType />
          ))}
        </div>
      )}
    </div>
  );
}

function ApprovalCard({
  request: r,
  busy,
  remark,
  onRemarkChange,
  onDecide,
  showType,
}: {
  request: ApprovalRequest;
  busy: boolean;
  remark: string;
  onRemarkChange: (v: string) => void;
  onDecide: (id: number, action: "approve" | "reject" | "return_for_correction") => void;
  showType?: boolean;
}) {
  return (
    <div className="card grid gap-3">
      <div>
        {showType && <span className="chip chip-info mb-1.5">{r.request_type.replace(/_/g, " ")}</span>}
        <p className="font-semibold text-sm">{r.summary}</p>
        <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
          Requested by {r.requested_by_name ?? "—"} · Level {r.current_level_order}
        </p>
      </div>

      {r.steps.length > 0 && (
        <div className="grid gap-1 text-xs" style={{ color: "var(--color-ink-faint)" }}>
          {r.steps.map((s) => (
            <div key={s.id}>
              {s.approver_name} {s.action.replace(/_/g, " ")} at level {s.level_order}
              {s.remark && ` — "${s.remark}"`}
            </div>
          ))}
        </div>
      )}

      <input className="input h-9 text-sm" placeholder="Remark (optional)" value={remark} onChange={(e) => onRemarkChange(e.target.value)} />

      <div className="flex gap-2">
        <button className="btn btn-primary flex-1" disabled={busy} onClick={() => onDecide(r.id, "approve")}>
          <Check size={16} /> Approve
        </button>
        <button className="btn btn-ghost flex-1" disabled={busy} onClick={() => onDecide(r.id, "return_for_correction")}>
          <Undo2 size={16} /> Return
        </button>
        <button className="btn btn-ghost flex-1" style={{ color: "var(--color-bad)" }} disabled={busy} onClick={() => onDecide(r.id, "reject")}>
          <X size={16} /> Reject
        </button>
      </div>
    </div>
  );
}
