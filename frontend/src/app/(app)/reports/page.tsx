"use client";

import { useState } from "react";
import { Download, Eye, X } from "lucide-react";
import { api, downloadFile, ApiError } from "@/lib/api";

const today = new Date();

interface PreviewState {
  title: string;
  columns: string[];
  rows: Record<string, unknown>[];
}

export default function ReportsPage() {
  const [error, setError] = useState("");
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [start, setStart] = useState(`${today.getFullYear()}-01-01`);
  const [end, setEnd] = useState(`${today.getFullYear()}-12-31`);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  async function run(path: string) {
    setError("");
    try {
      await downloadFile(path);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not download the report");
    }
  }

  async function show(title: string, path: string) {
    setError("");
    setLoadingPreview(true);
    try {
      const rows = await api.get<Record<string, unknown>[]>(path);
      const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
      setPreview({ title, columns, rows });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the preview");
    } finally {
      setLoadingPreview(false);
    }
  }

  return (
    <div className="grid gap-5 max-w-5xl">
      <div>
        <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
          Reports
        </h1>
        <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
          Preview a report in-browser, or download it as an Excel file.
        </p>
      </div>

      {error && <div className="card chip-bad">{error}</div>}

      <div className="grid gap-3 sm:grid-cols-2">
        <ReportRow
          title="Employee strength by division"
          description="Active headcount, broken down by division."
          onPreview={() => show("Employee strength by division", "/api/reports/employee-strength/preview")}
          onDownload={() => run("/api/reports/employee-strength/export")}
        />

        <ReportRow
          title="Asset register summary"
          description="Counts of assets by status (in store, issued, disposed)."
          onPreview={() => show("Asset register summary", "/api/reports/asset-register/preview")}
          onDownload={() => run("/api/reports/asset-register/export")}
        />

        <ReportRow
          title="Contracts expiring (next 30 days)"
          description="Project/contract staff whose engagement ends soon."
          onPreview={() => show("Contracts expiring", "/api/reports/contracts-expiring/preview?days=30")}
          onDownload={() => run("/api/reports/contracts-expiring/export?days=30")}
        />
      </div>

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
          <button className="btn btn-ghost" onClick={() => show("Attendance summary", `/api/reports/attendance-summary/preview?year=${year}&month=${month}`)}>
            <Eye size={16} /> Preview
          </button>
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
          <button className="btn btn-ghost" onClick={() => show("Leave register", `/api/reports/leave-register/preview?year=${year}`)}>
            <Eye size={16} /> Preview
          </button>
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
          <button className="btn btn-ghost" onClick={() => show("Separations", `/api/reports/separations/preview?start=${start}&end=${end}`)}>
            <Eye size={16} /> Preview
          </button>
          <button className="btn btn-primary" onClick={() => run(`/api/reports/separations/export?start=${start}&end=${end}`)}>
            <Download size={16} /> Download
          </button>
        </div>
      </div>

      {loadingPreview && <div className="card text-sm">Loading preview…</div>}

      {preview && (
        <div className="fixed inset-0 grid place-items-center p-4 z-50" style={{ background: "rgb(0 0 0 / 0.4)" }}>
          <div className="card grid gap-3 w-full max-w-3xl max-h-[80vh] overflow-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold">{preview.title}</h3>
              <button className="btn btn-ghost h-8 w-8 p-0" onClick={() => setPreview(null)}>
                <X size={16} />
              </button>
            </div>
            {preview.rows.length === 0 ? (
              <p className="text-sm py-6 text-center" style={{ color: "var(--color-ink-faint)" }}>
                No rows for this report.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
                      {preview.columns.map((c) => (
                        <th key={c} className="pb-2 font-medium">
                          {c.replace(/_/g, " ")}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, i) => (
                      <tr key={i} style={{ borderTop: "1px solid var(--color-line)" }}>
                        {preview.columns.map((c) => (
                          <td key={c} className="py-2">
                            {String(row[c] ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ReportRow({
  title,
  description,
  onPreview,
  onDownload,
}: {
  title: string;
  description: string;
  onPreview: () => void;
  onDownload: () => void;
}) {
  return (
    <div className="card grid gap-3">
      <div>
        <p className="font-medium text-sm">{title}</p>
        <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
          {description}
        </p>
      </div>
      <div className="flex gap-2">
        <button className="btn btn-ghost flex-1" onClick={onPreview}>
          <Eye size={16} /> Preview
        </button>
        <button className="btn btn-primary flex-1" onClick={onDownload}>
          <Download size={16} /> Download
        </button>
      </div>
    </div>
  );
}
