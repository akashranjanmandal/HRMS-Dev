"use client";

import { useEffect, useState } from "react";
import { Check, X, Undo2 } from "lucide-react";
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

export default function ApprovalsPage() {
  const [requests, setRequests] = useState<ApprovalRequest[]>([]);
  const [counts, setCounts] = useState<ApprovalCount[]>([]);
  const [filter, setFilter] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [remarks, setRemarks] = useState<Record<number, string>>({});

  const load = () => {
    const q = filter ? `?request_type=${filter}` : "";
    api.get<ApprovalRequest[]>(`/api/approvals${q}`).then(setRequests).catch(() => {});
    api.get<ApprovalCount[]>("/api/approvals/counts").then(setCounts).catch(() => {});
  };

  useEffect(load, [filter]);

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
    <div className="grid gap-5 max-w-4xl">
      <div>
        <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
          Approvals Center
        </h1>
        <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
          Everything pending your decision, across every module.
        </p>
      </div>

      {error && <div className="card chip-bad">{error}</div>}

      <div className="flex gap-2 overflow-x-auto pb-1">
        <button
          className={`chip ${filter === null ? "chip-info" : "chip-mute"}`}
          onClick={() => setFilter(null)}
        >
          All
        </button>
        {counts.map((c) => (
          <button
            key={c.request_type}
            className={`chip ${filter === c.request_type ? "chip-info" : "chip-mute"}`}
            onClick={() => setFilter(c.request_type)}
          >
            {c.label} {c.pending_count > 0 && `(${c.pending_count})`}
          </button>
        ))}
      </div>

      {requests.length === 0 && (
        <div className="card text-sm" style={{ color: "var(--color-ink-faint)" }}>
          Nothing pending your decision right now.
        </div>
      )}

      <div className="grid gap-3">
        {requests.map((r) => (
          <div key={r.id} className="card grid gap-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <span className="chip chip-info mb-1.5">{r.request_type.replace(/_/g, " ")}</span>
                <p className="font-semibold">{r.summary}</p>
                <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
                  Requested by {r.requested_by_name ?? "—"} · Level {r.current_level_order}
                </p>
              </div>
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

            <input
              className="input"
              placeholder="Remark (optional)"
              value={remarks[r.id] ?? ""}
              onChange={(e) => setRemarks({ ...remarks, [r.id]: e.target.value })}
            />

            <div className="flex gap-2">
              <button
                className="btn btn-primary flex-1"
                disabled={busyId === r.id}
                onClick={() => decide(r.id, "approve")}
              >
                <Check size={16} /> Approve
              </button>
              <button
                className="btn btn-ghost flex-1"
                disabled={busyId === r.id}
                onClick={() => decide(r.id, "return_for_correction")}
              >
                <Undo2 size={16} /> Return
              </button>
              <button
                className="btn btn-ghost flex-1"
                style={{ color: "var(--color-bad)" }}
                disabled={busyId === r.id}
                onClick={() => decide(r.id, "reject")}
              >
                <X size={16} /> Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
