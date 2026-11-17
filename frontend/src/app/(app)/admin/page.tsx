"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus, RotateCcw, ShieldOff, ShieldCheck, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api";

interface AppUser {
  id: number;
  email: string;
  role_code: string;
  role_name: string;
  division_id: number | null;
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
}

interface RoleRow {
  id: number;
  code: string;
  name: string;
  description: string;
  is_system: boolean;
  requires_mfa: boolean;
  permissions: string[];
}

interface Division {
  id: number;
  name: string;
}

export default function AdminPage() {
  const [tab, setTab] = useState<"users" | "roles">("users");
  const [users, setUsers] = useState<AppUser[]>([]);
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [divisions, setDivisions] = useState<Division[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [newUser, setNewUser] = useState({ email: "", role_code: "", division_id: "" });
  const [userQuery, setUserQuery] = useState("");

  const load = () => {
    api.get<AppUser[]>("/api/users").then(setUsers).catch(() => {});
    api.get<RoleRow[]>("/api/roles").then(setRoles).catch(() => {});
    api.get<Division[]>("/api/divisions").then(setDivisions).catch(() => {});
  };
  useEffect(load, []);

  const activeCount = useMemo(() => users.filter((u) => u.is_active).length, [users]);
  const mfaRoleCodes = useMemo(() => new Set(roles.filter((r) => r.requires_mfa).map((r) => r.code)), [roles]);
  const mfaUserCount = useMemo(() => users.filter((u) => mfaRoleCodes.has(u.role_code)).length, [users, mfaRoleCodes]);

  const filteredUsers = useMemo(() => {
    const q = userQuery.toLowerCase();
    return users.filter((u) => u.email.toLowerCase().includes(q) || u.role_name.toLowerCase().includes(q));
  }, [users, userQuery]);

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      const created = await api.post<AppUser & { temporary_password: string }>("/api/users", {
        email: newUser.email,
        role_code: newUser.role_code,
        division_id: newUser.division_id ? Number(newUser.division_id) : null,
      });
      setNotice(`Created ${created.email} — temporary password: ${created.temporary_password}`);
      setShowNew(false);
      setNewUser({ email: "", role_code: "", division_id: "" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the user");
    }
  }

  async function toggleActive(u: AppUser) {
    setError("");
    try {
      await api.put(`/api/users/${u.id}/active`, { is_active: !u.is_active });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update the account");
    }
  }

  async function resetPassword(u: AppUser) {
    setError("");
    setNotice("");
    try {
      const res = await api.post<{ temporary_password: string }>(`/api/users/${u.id}/reset-password`);
      setNotice(`New temporary password for ${u.email}: ${res.temporary_password}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reset the password");
    }
  }

  return (
    <div className="grid gap-5 max-w-6xl">
      <div>
        <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
          Administration
        </h1>
        <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
          {users.length} {users.length === 1 ? "user" : "users"} · {roles.length} roles
        </p>
      </div>

      {error && <div className="card chip-bad">{error}</div>}
      {notice && <div className="card chip-ok break-all">{notice}</div>}

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="card flex items-center justify-between">
          <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
            Active users
          </span>
          <span className="text-lg font-bold px-3 py-1 rounded-full" style={{ background: "var(--color-ok-tint)", color: "var(--color-ok)" }}>
            {activeCount}
          </span>
        </div>
        <div className="card flex items-center justify-between">
          <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
            Inactive users
          </span>
          <span className="text-lg font-bold px-3 py-1 rounded-full" style={{ background: "var(--color-surface-2)", color: "var(--color-ink-soft)" }}>
            {users.length - activeCount}
          </span>
        </div>
        <div className="card flex items-center justify-between">
          <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
            MFA-required logins
          </span>
          <span className="text-lg font-bold px-3 py-1 rounded-full" style={{ background: "var(--color-warn-tint)", color: "var(--color-warn)" }}>
            {mfaUserCount}
          </span>
        </div>
      </div>

      <div className="flex gap-2">
        <button className={`chip ${tab === "users" ? "chip-info" : "chip-mute"}`} onClick={() => setTab("users")}>
          Users
        </button>
        <button className={`chip ${tab === "roles" ? "chip-info" : "chip-mute"}`} onClick={() => setTab("roles")}>
          Roles &amp; permissions
        </button>
      </div>

      {tab === "users" && (
        <div className="grid gap-4">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--color-ink-faint)" }} />
              <input className="input pl-9 w-64" placeholder="Search email, role…" value={userQuery} onChange={(e) => setUserQuery(e.target.value)} />
            </div>
            <button className="btn btn-primary" onClick={() => setShowNew((s) => !s)}>
              <Plus size={16} /> New user
            </button>
          </div>

          {showNew && (
            <form onSubmit={createUser} className="card grid gap-3 sm:grid-cols-3">
              <div>
                <label className="label">Email</label>
                <input className="input" type="email" required value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} />
              </div>
              <div>
                <label className="label">Role</label>
                <select className="input" required value={newUser.role_code} onChange={(e) => setNewUser({ ...newUser, role_code: e.target.value })}>
                  <option value="">Select…</option>
                  {roles.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Division (if applicable)</label>
                <select className="input" value={newUser.division_id} onChange={(e) => setNewUser({ ...newUser, division_id: e.target.value })}>
                  <option value="">—</option>
                  {divisions.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-3">
                <button className="btn btn-primary">Create</button>
              </div>
            </form>
          )}

          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
                  <th className="pb-2 font-medium">Email</th>
                  <th className="pb-2 font-medium">Role</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => (
                  <tr key={u.id} style={{ borderTop: "1px solid var(--color-line)" }}>
                    <td className="py-2">{u.email}</td>
                    <td className="py-2">{u.role_name}</td>
                    <td className="py-2">
                      <span className={`chip ${u.is_active ? "chip-ok" : "chip-mute"}`}>{u.is_active ? "active" : "inactive"}</span>
                    </td>
                    <td className="py-2 text-right whitespace-nowrap">
                      <button className="btn btn-ghost h-7 px-2 text-xs" onClick={() => resetPassword(u)}>
                        <RotateCcw size={13} /> Reset password
                      </button>
                      <button className="btn btn-ghost h-7 px-2 text-xs ml-1" onClick={() => toggleActive(u)}>
                        {u.is_active ? (
                          <>
                            <ShieldOff size={13} /> Deactivate
                          </>
                        ) : (
                          <>
                            <ShieldCheck size={13} /> Activate
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredUsers.length === 0 && (
              <p className="text-sm py-6 text-center" style={{ color: "var(--color-ink-faint)" }}>
                {users.length === 0 ? "No users yet." : "No users match this search."}
              </p>
            )}
          </div>
        </div>
      )}

      {tab === "roles" && (
        <div className="grid gap-3">
          {roles.map((r) => (
            <div key={r.id} className="card">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <p className="font-semibold">{r.name}</p>
                  <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
                    {r.description}
                  </p>
                </div>
                <div className="flex gap-1.5">
                  {r.is_system && <span className="chip chip-mute">system role</span>}
                  {r.requires_mfa && <span className="chip chip-warn">MFA required</span>}
                </div>
              </div>
              <div className="flex gap-1 flex-wrap mt-2">
                {r.permissions.slice(0, 12).map((p) => (
                  <span key={p} className="chip chip-mute text-[10px]">
                    {p}
                  </span>
                ))}
                {r.permissions.length > 12 && (
                  <span className="chip chip-mute text-[10px]">+{r.permissions.length - 12} more</span>
                )}
              </div>
            </div>
          ))}
          <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
            The 10 RFP roles are system-defined and not editable here; custom roles (none yet) can have their
            permission set adjusted through the API.
          </p>
        </div>
      )}
    </div>
  );
}
