"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface LeaveType {
  id: number;
  name: string;
  annual_entitlement_days: number;
  requires_approval: boolean;
}

interface LeaveBalance {
  leave_type_id: number;
  leave_type_name: string;
  year: number;
  opening_balance_days: number;
  used_days: number;
  available_days: number;
}

interface LeaveApplication {
  id: number;
  employee_name: string;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: string;
  created_at: string;
}

const STATUS_CHIP: Record<string, string> = {
  pending: "chip-warn",
  approved: "chip-ok",
  rejected: "chip-bad",
  returned: "chip-bad",
  cancelled: "chip-mute",
};

export default function LeavePage() {
  const { hasPermission } = useAuth();
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [mine, setMine] = useState<LeaveApplication[]>([]);
  const [team, setTeam] = useState<LeaveApplication[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({ leave_type_id: "", start_date: "", end_date: "", reason: "" });

  const canApprove = hasPermission("leave:approve");

  const load = () => {
    api.get<LeaveType[]>("/api/leave/types").then(setTypes).catch(() => {});
    api.get<LeaveBalance[]>("/api/leave/balances").then(setBalances).catch(() => {});
    api.get<LeaveApplication[]>("/api/leave/mine").then(setMine).catch(() => {});
    if (canApprove) {
      api.get<LeaveApplication[]>("/api/leave").then(setTeam).catch(() => {});
    }
  };

  useEffect(load, [canApprove]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);
    try {
      await api.post("/api/leave", {
        leave_type_id: Number(form.leave_type_id),
        start_date: form.start_date,
        end_date: form.end_date,
        reason: form.reason,
      });
      setSuccess("Leave application submitted.");
      setForm({ leave_type_id: "", start_date: "", end_date: "", reason: "" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit the application");
    } finally {
      setSubmitting(false);
    }
  }

  async function cancel(id: number) {
    try {
      await api.post(`/api/leave/${id}/cancel`);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not cancel");
    }
  }

  return (
    <div className="grid gap-5 max-w-5xl">
      <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
        Leave
      </h1>

      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <form onSubmit={submit} className="card grid gap-3 content-start">
          <h3 className="text-base font-semibold">Apply for leave</h3>
          {error && <div className="chip chip-bad">{error}</div>}
          {success && <div className="chip chip-ok">{success}</div>}

          <div>
            <label className="label">Leave type</label>
            <select
              className="input"
              required
              value={form.leave_type_id}
              onChange={(e) => setForm({ ...form, leave_type_id: e.target.value })}
            >
              <option value="">Select…</option>
              {types.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="label">Start date</label>
              <input
                type="date"
                className="input"
                required
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              />
            </div>
            <div>
              <label className="label">End date</label>
              <input
                type="date"
                className="input"
                required
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
            </div>
          </div>
          <div>
            <label className="label">Reason</label>
            <textarea
              className="input"
              style={{ height: 80, paddingTop: 10 }}
              value={form.reason}
              onChange={(e) => setForm({ ...form, reason: e.target.value })}
            />
          </div>
          <button className="btn btn-primary" disabled={submitting}>
            {submitting ? "Submitting…" : "Submit application"}
          </button>

          {balances.length > 0 && (
            <div className="grid gap-1.5 pt-2" style={{ borderTop: "1px solid var(--color-line)" }}>
              <h4 className="text-xs font-semibold uppercase tracking-wide pt-2" style={{ color: "var(--color-ink-faint)" }}>
                Balances
              </h4>
              {balances.map((b) => (
                <div key={b.leave_type_id} className="flex justify-between text-sm">
                  <span>{b.leave_type_name}</span>
                  <span className="font-semibold">{b.available_days} days</span>
                </div>
              ))}
            </div>
          )}
        </form>

        <div className="grid gap-4">
          <div className="card">
            <h3 className="text-base font-semibold mb-3">My applications</h3>
            <ApplicationTable rows={mine} onCancel={cancel} />
          </div>

          {canApprove && (
            <div className="card">
              <h3 className="text-base font-semibold mb-3">Team applications</h3>
              <ApplicationTable rows={team} showEmployee />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ApplicationTable({
  rows,
  showEmployee,
  onCancel,
}: {
  rows: LeaveApplication[];
  showEmployee?: boolean;
  onCancel?: (id: number) => void;
}) {
  if (rows.length === 0) {
    return <p className="text-sm" style={{ color: "var(--color-ink-faint)" }}>No applications yet.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
            {showEmployee && <th className="pb-2 font-medium">Employee</th>}
            <th className="pb-2 font-medium">Type</th>
            <th className="pb-2 font-medium">Dates</th>
            <th className="pb-2 font-medium">Days</th>
            <th className="pb-2 font-medium">Status</th>
            {onCancel && <th className="pb-2 font-medium"></th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} style={{ borderTop: "1px solid var(--color-line)" }}>
              {showEmployee && <td className="py-2">{r.employee_name}</td>}
              <td className="py-2">{r.leave_type_name}</td>
              <td className="py-2">
                {r.start_date} → {r.end_date}
              </td>
              <td className="py-2">{r.days}</td>
              <td className="py-2">
                <span className={`chip ${STATUS_CHIP[r.status] ?? "chip-mute"}`}>{r.status}</span>
              </td>
              {onCancel && (
                <td className="py-2 text-right">
                  {r.status === "pending" && (
                    <button className="btn btn-ghost h-7 px-2 text-xs" onClick={() => onCancel(r.id)}>
                      Cancel
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
