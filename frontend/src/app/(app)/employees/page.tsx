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

  useEffect(() => {
    api.get<Employee[]>("/api/employees").then(setEmployees).catch(() => {});
    api.get<Division[]>("/api/divisions").then(setDivisions).catch(() => {});
  }, []);

  const divisionName = useMemo(() => {
    const map = new Map(divisions.map((d) => [d.id, d.name]));
    return (id: number) => map.get(id) ?? "—";
  }, [divisions]);

  const filtered = employees.filter((e) => {
    const q = query.toLowerCase();
    return (
      e.full_name.toLowerCase().includes(q) ||
      e.employee_code.toLowerCase().includes(q) ||
      e.designation.toLowerCase().includes(q)
    );
  });

  return (
    <div className="grid gap-5 max-w-5xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
          Employee Directory
        </h1>
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
          <p className="text-sm py-4 text-center" style={{ color: "var(--color-ink-faint)" }}>
            No employees found.
          </p>
        )}
      </div>
    </div>
  );
}
