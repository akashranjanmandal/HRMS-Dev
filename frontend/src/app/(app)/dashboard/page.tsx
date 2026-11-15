"use client";

import { useEffect, useState } from "react";
import { Users, CalendarClock, Box, FileWarning } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface DashboardSummary {
  active_employees: number;
  pending_leave_applications: number;
  assets_issued: number;
  contracts_expiring_30_days: number;
  employee_strength_by_division: { division: string; active_employees: number }[];
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<DashboardSummary>("/api/reports/dashboard")
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load the dashboard"));
  }, []);

  return (
    <div className="grid gap-5 max-w-5xl">
      <div>
        <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
          Welcome, {user?.role_name}
        </h1>
        <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
          A quick look at where things stand today.
        </p>
      </div>

      {error && <div className="card chip-bad">{error}</div>}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={Users} label="Active employees" value={data.active_employees} />
            <StatCard icon={CalendarClock} label="Pending leave applications" value={data.pending_leave_applications} tone="warn" />
            <StatCard icon={Box} label="Assets issued" value={data.assets_issued} />
            <StatCard icon={FileWarning} label="Contracts expiring (30 days)" value={data.contracts_expiring_30_days} tone={data.contracts_expiring_30_days > 0 ? "warn" : undefined} />
          </div>

          {data.employee_strength_by_division.length > 0 && (
            <div className="card">
              <h3 className="text-base font-semibold mb-3">Employee strength by division</h3>
              <div className="grid gap-2">
                {data.employee_strength_by_division.map((row) => (
                  <div key={row.division} className="flex items-center gap-3">
                    <span className="w-40 text-sm truncate" style={{ color: "var(--color-ink-soft)" }}>
                      {row.division}
                    </span>
                    <div className="flex-1 h-2 rounded-full" style={{ background: "var(--color-surface-2)" }}>
                      <div
                        className="h-2 rounded-full"
                        style={{
                          background: "var(--color-primary)",
                          width: `${Math.min(100, row.active_employees * 10)}%`,
                        }}
                      />
                    </div>
                    <span className="w-8 text-sm text-right font-semibold">{row.active_employees}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Users;
  label: string;
  value: number;
  tone?: "warn";
}) {
  return (
    <div className="card flex items-center gap-3">
      <div
        className="w-10 h-10 rounded-lg grid place-items-center flex-none"
        style={{
          background: tone === "warn" ? "var(--color-warn-tint)" : "var(--color-primary-tint)",
          color: tone === "warn" ? "var(--color-warn)" : "var(--color-primary)",
        }}
      >
        <Icon size={18} />
      </div>
      <div>
        <div className="text-2xl font-bold leading-tight">{value}</div>
        <div className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
          {label}
        </div>
      </div>
    </div>
  );
}
