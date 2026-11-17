"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Users, CalendarClock, Box, FileWarning, UserCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface AttendanceByDivision {
  division: string;
  present: number;
  field_duty: number;
  on_leave: number;
  total_active: number;
}

interface DashboardSummary {
  active_employees: number;
  pending_leave_applications: number;
  assets_issued: number;
  contracts_expiring_30_days: number;
  checked_in_today: number;
  employee_strength_by_division: { division: string; active_employees: number }[];
  attendance_by_division: AttendanceByDivision[];
}

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
  requested_by_name: string | null;
  summary: string;
  current_level_order: number;
  created_at: string;
  steps: ApprovalStep[];
}

export default function DashboardPage() {
  const { user, hasAnyPermission } = useAuth();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRequest[] | null>(null);
  const [error, setError] = useState("");

  const canSeeApprovals = hasAnyPermission(
    "recruitment:approve",
    "onboarding:approve",
    "attendance:approve",
    "leave:approve",
    "appraisal:approve",
    "asset:approve",
    "payroll:approve"
  );

  useEffect(() => {
    api
      .get<DashboardSummary>("/api/reports/dashboard")
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load the dashboard"));

    if (canSeeApprovals) {
      api
        .get<ApprovalRequest[]>("/api/approvals")
        .then((rows) => setApprovals(rows.slice(0, 5)))
        .catch(() => setApprovals([]));
    } else {
      setApprovals([]);
    }
  }, [canSeeApprovals]);

  const maxDivisionStrength = Math.max(
    1,
    ...(data?.employee_strength_by_division.map((r) => r.active_employees) ?? [0])
  );

  return (
    <div className="grid gap-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
            Welcome, {user?.role_name}
          </h1>
          <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
            A quick look at where things stand today.
          </p>
        </div>
      </div>

      {error && <div className="card chip-bad">{error}</div>}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard
              icon={Users}
              label="Active employees"
              value={data.active_employees}
              href="/employees"
            />
            <StatCard
              icon={UserCheck}
              label="Checked in today"
              value={data.checked_in_today}
              sub={
                data.active_employees > 0
                  ? `${Math.round((data.checked_in_today / data.active_employees) * 100)}% of active staff`
                  : undefined
              }
              href="/attendance"
            />
            <StatCard
              icon={CalendarClock}
              label="Pending leave applications"
              value={data.pending_leave_applications}
              tone="warn"
              href="/leave"
            />
            <StatCard icon={Box} label="Assets issued" value={data.assets_issued} href="/assets" />
            <StatCard
              icon={FileWarning}
              label="Contracts expiring (30 days)"
              value={data.contracts_expiring_30_days}
              tone={data.contracts_expiring_30_days > 0 ? "warn" : undefined}
              href="/employees"
            />
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.15fr_1fr]">
            <div className="card">
              <h3 className="text-base font-semibold mb-3">Attendance by division</h3>
              {data.attendance_by_division.length > 0 ? (
                <>
                  <div className="grid gap-2.5">
                    {data.attendance_by_division.map((row) => {
                      const total = Math.max(1, row.total_active);
                      return (
                        <div key={row.division} className="flex items-center gap-3">
                          <span
                            className="w-36 text-sm truncate flex-none"
                            style={{ color: "var(--color-ink-soft)" }}
                          >
                            {row.division}
                          </span>
                          <div
                            className="flex-1 h-2.5 rounded-full overflow-hidden flex"
                            style={{ background: "var(--color-surface-2)" }}
                          >
                            <div
                              className="h-full"
                              style={{ background: "var(--color-primary)", width: `${(row.present / total) * 100}%` }}
                            />
                            <div
                              className="h-full"
                              style={{ background: "var(--color-accent)", width: `${(row.field_duty / total) * 100}%` }}
                            />
                            <div
                              className="h-full"
                              style={{
                                background: "var(--color-ink-faint)",
                                opacity: 0.45,
                                width: `${(row.on_leave / total) * 100}%`,
                              }}
                            />
                          </div>
                          <span
                            className="w-16 text-sm text-right flex-none"
                            style={{ color: "var(--color-ink-faint)" }}
                          >
                            {row.present + row.field_duty} / {row.total_active}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex gap-4 mt-4 text-xs" style={{ color: "var(--color-ink-soft)" }}>
                    <Legend color="var(--color-primary)" label="At site" />
                    <Legend color="var(--color-accent)" label="Field duty" />
                    <Legend color="var(--color-ink-faint)" opacity={0.45} label="On leave" />
                  </div>
                </>
              ) : data.employee_strength_by_division.length > 0 ? (
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
                            width: `${(row.active_employees / maxDivisionStrength) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="w-8 text-sm text-right font-semibold">{row.active_employees}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState text="No division-level data is visible for your role." />
              )}
            </div>

            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-base font-semibold">Waiting for you</h3>
                {canSeeApprovals && (
                  <Link
                    href="/approvals"
                    className="text-sm font-medium"
                    style={{ color: "var(--color-primary)" }}
                  >
                    Open Approvals
                  </Link>
                )}
              </div>

              {!canSeeApprovals ? (
                <EmptyState text="You don't have any approvals routed to you." />
              ) : approvals === null ? (
                <p className="text-sm" style={{ color: "var(--color-ink-faint)" }}>
                  Loading…
                </p>
              ) : approvals.length === 0 ? (
                <EmptyState text="Nothing pending your decision right now." />
              ) : (
                <div className="grid gap-3">
                  {approvals.map((a) => (
                    <Link
                      key={a.id}
                      href="/approvals"
                      className="flex items-center justify-between gap-3 pb-3 last:pb-0"
                      style={{ borderBottom: "1px solid var(--color-line)" }}
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-semibold truncate">{a.requested_by_name ?? "—"}</p>
                        <p className="text-xs truncate" style={{ color: "var(--color-ink-faint)" }}>
                          {a.summary}
                        </p>
                      </div>
                      <span className="chip chip-warn flex-none">Level {a.current_level_order}</span>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Legend({ color, opacity, label }: { color: string; opacity?: number; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <i
        className="inline-block w-2.5 h-2.5 rounded-sm"
        style={{ background: color, opacity: opacity ?? 1 }}
      />
      {label}
    </span>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <p className="text-sm py-6 text-center" style={{ color: "var(--color-ink-faint)" }}>
      {text}
    </p>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  tone,
  href,
}: {
  icon: typeof Users;
  label: string;
  value: number;
  sub?: string;
  tone?: "warn";
  href?: string;
}) {
  const content = (
    <div className="card flex items-center gap-3 h-full">
      <div
        className="w-10 h-10 rounded-lg grid place-items-center flex-none"
        style={{
          background: tone === "warn" ? "var(--color-warn-tint)" : "var(--color-primary-tint)",
          color: tone === "warn" ? "var(--color-warn)" : "var(--color-primary)",
        }}
      >
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold leading-tight">{value}</div>
        <div className="text-xs truncate" style={{ color: "var(--color-ink-faint)" }}>
          {label}
        </div>
        {sub && (
          <div className="text-xs truncate" style={{ color: "var(--color-ink-faint)" }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  );

  if (!href) return content;
  return (
    <Link href={href} className="block transition-opacity hover:opacity-80">
      {content}
    </Link>
  );
}
