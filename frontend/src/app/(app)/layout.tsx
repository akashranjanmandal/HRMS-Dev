"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { NAV_ITEMS } from "@/components/nav";

const APPROVE_CODES = [
  "recruitment:approve",
  "onboarding:approve",
  "attendance:approve",
  "leave:approve",
  "appraisal:approve",
  "asset:approve",
  "payroll:approve",
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, hasPermission, hasAnyPermission, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="min-h-screen grid place-items-center" style={{ background: "var(--color-bg)" }}>
        <span className="text-sm" style={{ color: "var(--color-ink-faint)" }}>
          Loading…
        </span>
      </div>
    );
  }

  const visible = NAV_ITEMS.filter((item) => {
    if (item.href === "/approvals") return hasAnyPermission(...APPROVE_CODES);
    if (!item.permission) return true;
    return hasPermission(item.permission);
  });
  const mobileItems = visible.filter((i) => i.mobile).slice(0, 5);
  const initials = user.email.slice(0, 2).toUpperCase();

  return (
    <div className="min-h-screen md:grid md:grid-cols-[220px_1fr]" style={{ background: "var(--color-bg)" }}>
      {/* Desktop sidebar */}
      <aside
        className="hidden md:flex md:flex-col gap-4 p-3"
        style={{ background: "var(--color-surface)", borderRight: "1px solid var(--color-line)" }}
      >
        <div className="flex items-center gap-2.5 px-2">
          <div
            className="w-[30px] h-[30px] rounded-lg grid place-items-center font-bold text-[15px]"
            style={{
              background: "var(--color-primary)",
              color: "var(--color-primary-ink)",
              fontFamily: "var(--font-display)",
            }}
          >
            A
          </div>
          <div>
            <b className="block text-[17px]" style={{ fontFamily: "var(--font-display)" }}>
              Aaranyak
            </b>
            <small className="block -mt-0.5 text-[11px]" style={{ color: "var(--color-ink-faint)" }}>
              HRMS
            </small>
          </div>
        </div>

        <nav className="grid gap-0.5 content-start flex-1">
          {visible.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-2.5 px-2.5 py-2 text-sm font-medium"
                style={{
                  borderRadius: "var(--radius-sm)",
                  background: active ? "var(--color-primary-tint)" : "transparent",
                  color: active ? "var(--color-primary)" : "var(--color-ink-soft)",
                  fontWeight: active ? 600 : 500,
                }}
              >
                <Icon size={17} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div
          className="flex items-center gap-2.5 px-2 pt-2.5 text-sm"
          style={{ borderTop: "1px solid var(--color-line)" }}
        >
          <div
            className="w-8 h-8 rounded-full grid place-items-center text-xs font-bold flex-none"
            style={{ background: "var(--color-primary-tint)", color: "var(--color-primary)" }}
          >
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <b className="block truncate">{user.email}</b>
            <span className="block text-[11px]" style={{ color: "var(--color-ink-faint)" }}>
              {user.role_name}
            </span>
          </div>
          <button
            onClick={() => logout()}
            title="Sign out"
            className="w-8 h-8 rounded-full grid place-items-center flex-none"
            style={{ color: "var(--color-ink-soft)" }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <div className="flex flex-col min-h-screen">
        {/* Top bar */}
        <header
          className="flex items-center gap-3 px-4 md:px-6 h-[60px] flex-none"
          style={{ background: "var(--color-surface)", borderBottom: "1px solid var(--color-line)" }}
        >
          <span className="md:hidden font-semibold" style={{ fontFamily: "var(--font-display)" }}>
            Aaranyak HRMS
          </span>
          <span
            className="hidden md:inline-flex items-center gap-2 h-[34px] px-3 text-sm rounded-full"
            style={{ border: "1px solid var(--color-line)" }}
          >
            {user.role_name}
          </span>
          <div className="flex-1" />
          <button
            className="w-[34px] h-[34px] rounded-full grid place-items-center relative"
            style={{ color: "var(--color-ink-soft)" }}
            title="Notifications"
          >
            <Bell size={18} />
          </button>
          <button
            onClick={() => logout()}
            className="md:hidden w-[34px] h-[34px] rounded-full grid place-items-center"
            style={{ color: "var(--color-ink-soft)" }}
            title="Sign out"
          >
            <LogOut size={18} />
          </button>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 md:p-6 pb-20 md:pb-6">{children}</main>

        {/* Mobile bottom tab bar */}
        <nav
          className="md:hidden fixed bottom-0 left-0 right-0 grid"
          style={{
            gridTemplateColumns: `repeat(${mobileItems.length || 1}, 1fr)`,
            background: "var(--color-surface)",
            borderTop: "1px solid var(--color-line)",
          }}
        >
          {mobileItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex flex-col items-center justify-center gap-0.5 py-2 text-[10.5px] font-semibold"
                style={{ color: active ? "var(--color-primary)" : "var(--color-ink-faint)" }}
              >
                <Icon size={21} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
