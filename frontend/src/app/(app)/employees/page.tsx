"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { api } from "@/lib/api";

interface Employee {
  id: number;
  employee_code: string;
  full_name: string;
  designation: string;
  division_id: number;
  employment_category: string;
  status: string;
  phone: string;
  personal_email: string;
}

interface Division {
  id: number;
  name: string;
}

const STATUS_CHIP: Record<string, string> = {
  active: "chip-ok",
  on_notice: "chip-warn",
  separated: "chip-mute",
};

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [divisions, setDivisions] = useState<Division[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [divisionFilter, setDivisionFilter] = useState<number | null>(null);

  useEffect(() => {
    api.get<Employee[]>("/api/employees").then(setEmployees).catch(() => {});
    api.get<Division[]>("/api/divisions").then(setDivisions).catch(() => {});
  }, []);

  const divisionName = useMemo(() => {
    const map = new Map(divisions.map((d) => [d.id, d.name]));
    return (id: number) => map.get(id) ?? "—";
  }, [divisions]);

  const counts = useMemo(() => {
    const byStatus: Record<string, number> = {};
    for (const e of employees) byStatus[e.status] = (byStatus[e.status] ?? 0) + 1;
    return byStatus;
  }, [employees]);

  const filtered = employees.filter((e) => {
    const q = query.toLowerCase();
    const matchesQuery =
      e.full_name.toLowerCase().includes(q) ||
      e.employee_code.toLowerCase().includes(q) ||
      e.designation.toLowerCase().includes(q);
    const matchesStatus = !statusFilter || e.status === statusFilter;
    const matchesDivision = !divisionFilter || e.division_id === divisionFilter;
    return matchesQuery && matchesStatus && matchesDivision;
  });

  return (
    <div className="grid gap-5 max-w-6xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
            Employee Directory
          </h1>
          <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
            {employees.length} {employees.length === 1 ? "employee" : "employees"} across {divisions.length} {divisions.length === 1 ? "division" : "divisions"}
          </p>
        </div>
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--color-ink-faint)" }} />
          <input
            className="input pl-9 w-64"
            placeholder="Search name, code, designation…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <SummaryTile label="Active" value={counts.active ?? 0} tone="ok" />
        <SummaryTile label="On notice" value={counts.on_notice ?? 0} tone="warn" />
        <SummaryTile label="Separated" value={counts.separated ?? 0} tone="mute" />
      </div>

      <div className="flex gap-2 flex-wrap">
        <button className={`chip ${statusFilter === null ? "chip-info" : "chip-mute"}`} onClick={() => setStatusFilter(null)}>
          All statuses
        </button>
        {Object.keys(STATUS_CHIP).map((s) => (
          <button key={s} className={`chip ${statusFilter === s ? "chip-info" : "chip-mute"}`} onClick={() => setStatusFilter(s)}>
            {s.replace(/_/g, " ")}
          </button>
        ))}
        <span className="w-px self-stretch" style={{ background: "var(--color-line)" }} />
        <button className={`chip ${divisionFilter === null ? "chip-info" : "chip-mute"}`} onClick={() => setDivisionFilter(null)}>
          All divisions
        </button>
        {divisions.map((d) => (
          <button key={d.id} className={`chip ${divisionFilter === d.id ? "chip-info" : "chip-mute"}`} onClick={() => setDivisionFilter(d.id)}>
            {d.name}
          </button>
        ))}
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
              <th className="pb-2 font-medium">Code</th>
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Designation</th>
              <th className="pb-2 font-medium">Division</th>
              <th className="pb-2 font-medium">Category</th>
              <th className="pb-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => (
              <tr key={e.id} style={{ borderTop: "1px solid var(--color-line)" }}>
                <td className="py-2 font-mono text-xs">{e.employee_code}</td>
                <td className="py-2 font-medium">{e.full_name}</td>
                <td className="py-2">{e.designation || "—"}</td>
                <td className="py-2">{divisionName(e.division_id)}</td>
                <td className="py-2">{e.employment_category.replace(/_/g, " ")}</td>
                <td className="py-2">
                  <span className={`chip ${STATUS_CHIP[e.status] ?? "chip-mute"}`}>{e.status.replace(/_/g, " ")}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-10 text-center grid gap-1">
            <p className="text-sm font-medium">No employees match these filters.</p>
            <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
              Try clearing the search or filters above.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryTile({ label, value, tone }: { label: string; value: number; tone: "ok" | "warn" | "mute" }) {
  const colors = {
    ok: { bg: "var(--color-ok-tint)", fg: "var(--color-ok)" },
    warn: { bg: "var(--color-warn-tint)", fg: "var(--color-warn)" },
    mute: { bg: "var(--color-surface-2)", fg: "var(--color-ink-soft)" },
  }[tone];
  return (
    <div className="card flex items-center justify-between">
      <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
        {label}
      </span>
      <span
        className="text-lg font-bold px-3 py-1 rounded-full"
        style={{ background: colors.bg, color: colors.fg }}
      >
        {value}
      </span>
    </div>
  );
}
