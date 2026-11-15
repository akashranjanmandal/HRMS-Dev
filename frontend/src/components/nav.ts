import {
  LayoutDashboard,
  BadgeCheck,
  Users,
  Clock,
  CalendarDays,
  UserPlus,
  Star,
  Package,
  Wallet,
  FileBarChart,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

/** One source of truth for every top-level module link, shared by the
 * desktop sidebar and the mobile bottom tab bar. `permission` gates
 * visibility via useAuth().hasPermission(); omit it for links every
 * signed-in user should see. */
export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  permission?: string;
  /** Shown on the mobile bottom tab bar (max 5 recommended). */
  mobile?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, mobile: true },
  // Approvals has no single permission code of its own — it's a view onto
  // whichever *:approve codes the signed-in role holds (see
  // backend/app/core/permissions.py). Gate on any one of them.
  { href: "/approvals", label: "Approvals", icon: BadgeCheck, mobile: true },
  { href: "/employees", label: "Employees", icon: Users, permission: "employee:view" },
  { href: "/attendance", label: "Attendance", icon: Clock, permission: "attendance:view", mobile: true },
  { href: "/leave", label: "Leave", icon: CalendarDays, permission: "leave:view", mobile: true },
  { href: "/recruitment", label: "Recruitment", icon: UserPlus, permission: "recruitment:view" },
  { href: "/appraisal", label: "Appraisal", icon: Star, permission: "appraisal:view" },
  { href: "/assets", label: "Assets", icon: Package, permission: "asset:view" },
  { href: "/payroll", label: "Payroll", icon: Wallet, permission: "payroll:view", mobile: true },
  { href: "/reports", label: "Reports", icon: FileBarChart, permission: "report:view" },
  { href: "/admin", label: "Admin", icon: ShieldCheck, permission: "user:view" },
];
