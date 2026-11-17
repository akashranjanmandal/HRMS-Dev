"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, Plus, PlayCircle, Search } from "lucide-react";
import { api, ApiError, downloadFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface PayrollRun {
  id: number;
  month: number;
  year: number;
  status: string;
  payslip_count: number;
  total_net: number;
}

interface Payslip {
  id: number;
  employee_name: string;
  division_name: string | null;
  loss_of_pay_days: number;
  gross: number;
  net: number;
}

interface PayrollRunDetail extends PayrollRun {
  payslips: Payslip[];
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function PayrollPage() {
  const { hasPermission } = useAuth();
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [selected, setSelected] = useState<PayrollRunDetail | null>(null);
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(false);
  const today = new Date();
  const [newRun, setNewRun] = useState({ month: today.getMonth() + 1, year: today.getFullYear() });
  const [payslipQuery, setPayslipQuery] = useState("");

  const canCreate = hasPermission("payroll:create");
  const canApprove = hasPermission("payroll:approve");
  const canExport = hasPermission("payroll:export");

  const load = () => {
    api.get<PayrollRun[]>("/api/payroll").then(setRuns).catch(() => {});
  };
  useEffect(load, []);

  const totalNetPaid = useMemo(() => runs.reduce((sum, r) => sum + r.total_net, 0), [runs]);
  const finalisedCount = useMemo(() => runs.filter((r) => r.status === "finalised").length, [runs]);

  const filteredPayslips = useMemo(() => {
    if (!selected) return [];
    const q = payslipQuery.toLowerCase();
    return selected.payslips.filter((p) => p.employee_name.toLowerCase().includes(q) || (p.division_name ?? "").toLowerCase().includes(q));
  }, [selected, payslipQuery]);

  async function openRun(id: number) {
    try {
      const detail = await api.get<PayrollRunDetail>(`/api/payroll/${id}`);
      setSelected(detail);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the run");
    }
  }

  async function createRun(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const detail = await api.post<PayrollRunDetail>("/api/payroll", newRun);
      setShowNew(false);
      load();
      setSelected(detail);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the run");
    }
  }

  async function finalise(id: number) {
    setError("");
    try {
      await api.post(`/api/payroll/${id}/finalise`);
      load();
      openRun(id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not finalise the run");
    }
  }

  return (
    <div className="grid gap-5 max-w-6xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
            Payroll
          </h1>
          <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
            {runs.length} {runs.length === 1 ? "run" : "runs"} on record
          </p>
        </div>
        {canCreate && (
          <button className="btn btn-primary" onClick={() => setShowNew((s) => !s)}>
            <Plus size={16} /> New run
          </button>
        )}
      </div>

      {error && <div className="card chip-bad">{error}</div>}

      {runs.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="card flex items-center justify-between">
            <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
              Total net paid
            </span>
            <span className="text-lg font-bold" style={{ color: "var(--color-primary)" }}>
              ₹{totalNetPaid.toLocaleString()}
            </span>
          </div>
          <div className="card flex items-center justify-between">
            <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
              Finalised runs
            </span>
            <span className="text-lg font-bold px-3 py-1 rounded-full" style={{ background: "var(--color-ok-tint)", color: "var(--color-ok)" }}>
              {finalisedCount}
            </span>
          </div>
          <div className="card flex items-center justify-between">
            <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
              Draft runs
            </span>
            <span className="text-lg font-bold px-3 py-1 rounded-full" style={{ background: "var(--color-surface-2)", color: "var(--color-ink-soft)" }}>
              {runs.length - finalisedCount}
            </span>
          </div>
        </div>
      )}

      {showNew && (
        <form onSubmit={createRun} className="card grid gap-3 sm:grid-cols-[auto_auto_auto]">
          <div>
            <label className="label">Month</label>
            <select className="input" value={newRun.month} onChange={(e) => setNewRun({ ...newRun, month: Number(e.target.value) })}>
              {MONTHS.map((m, i) => (
                <option key={m} value={i + 1}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Year</label>
            <input
              className="input"
              type="number"
              value={newRun.year}
              onChange={(e) => setNewRun({ ...newRun, year: Number(e.target.value) })}
            />
          </div>
          <button className="btn btn-primary self-end">Generate</button>
        </form>
      )}

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        <div className="card grid gap-1 content-start">
          <h3 className="text-base font-semibold mb-2">Runs</h3>
          {runs.map((r) => (
            <button
              key={r.id}
              onClick={() => openRun(r.id)}
              className="flex items-center justify-between px-2.5 py-2 text-sm text-left"
              style={{
                borderRadius: "var(--radius-sm)",
                background: selected?.id === r.id ? "var(--color-primary-tint)" : "transparent",
              }}
            >
              <span>
                {MONTHS[r.month - 1]} {r.year}
              </span>
              <span className={`chip ${r.status === "finalised" ? "chip-ok" : "chip-mute"}`}>{r.status}</span>
            </button>
          ))}
          {runs.length === 0 && (
            <p className="text-sm py-6 text-center" style={{ color: "var(--color-ink-faint)" }}>
              No runs yet — generate one to get started.
            </p>
          )}
        </div>

        <div className="card">
          {!selected ? (
            <div className="py-10 text-center grid gap-1">
              <p className="text-sm font-medium">Select a run to see its payslips.</p>
              <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
                Pick one from the list on the left.
              </p>
            </div>
          ) : (
            <div className="grid gap-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <h3 className="text-base font-semibold">
                    {MONTHS[selected.month - 1]} {selected.year}
                  </h3>
                  <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
                    {selected.payslip_count} payslips · ₹{selected.total_net.toLocaleString()} net
                  </p>
                </div>
                <div className="flex gap-2 items-center">
                  <div className="relative">
                    <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: "var(--color-ink-faint)" }} />
                    <input
                      className="input pl-8 h-8 text-xs w-40"
                      placeholder="Search payslips…"
                      value={payslipQuery}
                      onChange={(e) => setPayslipQuery(e.target.value)}
                    />
                  </div>
                  {canApprove && selected.status === "draft" && (
                    <button className="btn btn-ghost" onClick={() => finalise(selected.id)}>
                      <PlayCircle size={16} /> Finalise
                    </button>
                  )}
                  {canExport && (
                    <>
                      <button className="btn btn-ghost" onClick={() => downloadFile(`/api/payroll/${selected.id}/export/bank-file`)}>
                        <Download size={16} /> Bank file
                      </button>
                      <button className="btn btn-ghost" onClick={() => downloadFile(`/api/payroll/${selected.id}/export/payroll-report`)}>
                        <Download size={16} /> Report
                      </button>
                    </>
                  )}
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
                      <th className="pb-2 font-medium">Employee</th>
                      <th className="pb-2 font-medium">Division</th>
                      <th className="pb-2 font-medium">LOP days</th>
                      <th className="pb-2 font-medium">Gross</th>
                      <th className="pb-2 font-medium">Net</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPayslips.map((p) => (
                      <tr key={p.id} style={{ borderTop: "1px solid var(--color-line)" }}>
                        <td className="py-2">{p.employee_name}</td>
                        <td className="py-2">{p.division_name ?? "—"}</td>
                        <td className="py-2">{p.loss_of_pay_days}</td>
                        <td className="py-2">₹{p.gross.toLocaleString()}</td>
                        <td className="py-2 font-semibold">₹{p.net.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
