"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { downloadFile, ApiError } from "@/lib/api";

const today = new Date();

export default function ReportsPage() {
  const [error, setError] = useState("");
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [start, setStart] = useState(`${today.getFullYear()}-01-01`);
  const [end, setEnd] = useState(`${today.getFullYear()}-12-31`);

  async function run(path: string) {
    setError("");
    try {
      await downloadFile(path);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not download the report");
    }
  }

  return (
    <div className="grid gap-5 max-w-3xl">
      <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
        Reports
      </h1>
      <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
        Every report downloads as an Excel file.
      </p>

      {error && <div className="card chip-bad">{error}</div>}

      <ReportRow
        title="Employee strength by division"
        description="Active headcount, broken down by division."
        action={() => run("/api/reports/employee-strength/export")}
      />

      <ReportRow title="Contracts expiring (next 30 days)" description="Project/contract staff whose engagement ends soon." action={() => run("/api/reports/contracts-expiring/export?days=30")} />

      <ReportRow title="Asset register summary" description="Counts of assets by status (in store, issued, disposed)." action={() => run("/api/reports/asset-register/export")} />

      <div className="card grid gap-3">
        <div>
          <p className="font-medium text-sm">Attendance summary</p>
          <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
            Present/absent days per employee for one month.
          </p>
        </div>
        <div className="flex gap-2 items-end flex-wrap">
          <input className="input w-28" type="number" value={month} min={1} max={12} onChange={(e) => setMonth(Number(e.target.value))} />
          <input className="input w-28" type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} />
          <button className="btn btn-primary" onClick={() => run(`/api/reports/attendance-summary/export?year=${year}&month=${month}`)}>
            <Download size={16} /> Download
          </button>
        </div>
      </div>

      <div className="card grid gap-3">
        <div>
          <p className="font-medium text-sm">Leave register</p>
          <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
            Every approved leave application for a year.
          </p>
        </div>
        <div className="flex gap-2 items-end flex-wrap">
          <input className="input w-28" type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} />
          <button className="btn btn-primary" onClick={() => run(`/api/reports/leave-register/export?year=${year}`)}>
            <Download size={16} /> Download
          </button>
        </div>
      </div>

      <div className="card grid gap-3">
        <div>
          <p className="font-medium text-sm">Separations</p>
          <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
            Employees who exited within a date range.
          </p>
        </div>
        <div className="flex gap-2 items-end flex-wrap">
          <input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          <input className="input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          <button className="btn btn-primary" onClick={() => run(`/api/reports/separations/export?start=${start}&end=${end}`)}>
            <Download size={16} /> Download
          </button>
        </div>
      </div>
    </div>
  );
}

function ReportRow({ title, description, action }: { title: string; description: string; action: () => void }) {
  return (
    <div className="card flex items-center justify-between gap-3 flex-wrap">
      <div>
        <p className="font-medium text-sm">{title}</p>
        <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
          {description}
        </p>
      </div>
      <button className="btn btn-primary" onClick={action}>
        <Download size={16} /> Download
      </button>
    </div>
  );
}
