"use client";

import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Vacancy {
  id: number;
  title: string;
  division_id: number;
  positions_open: number;
  status: string;
  terms_of_reference: string;
}

interface Division {
  id: number;
  name: string;
}

interface Candidate {
  id: number;
  vacancy_id: number;
  full_name: string;
  email: string;
  phone: string;
  stage: string;
}

const STAGES = ["applied", "shortlisted", "interviewed", "selected", "rejected"];

const VACANCY_CHIP: Record<string, string> = {
  draft: "chip-mute",
  pending_approval: "chip-warn",
  published: "chip-ok",
  closed: "chip-bad",
};

const STAGE_CHIP: Record<string, string> = {
  applied: "chip-mute",
  shortlisted: "chip-info",
  interviewed: "chip-warn",
  selected: "chip-ok",
  rejected: "chip-bad",
};

export default function RecruitmentPage() {
  const { hasPermission } = useAuth();
  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [divisions, setDivisions] = useState<Division[]>([]);
  const [selected, setSelected] = useState<Vacancy | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [newVacancy, setNewVacancy] = useState({ title: "", division_id: "", positions_open: 1, terms_of_reference: "" });

  const canCreate = hasPermission("recruitment:create");
  const canApprove = hasPermission("recruitment:approve");

  const load = () => {
    api.get<Vacancy[]>("/api/vacancies").then(setVacancies).catch(() => {});
    api.get<Division[]>("/api/divisions").then(setDivisions).catch(() => {});
  };
  useEffect(load, []);

  async function openVacancy(v: Vacancy) {
    setSelected(v);
    try {
      setCandidates(await api.get<Candidate[]>(`/api/vacancies/${v.id}/candidates`));
    } catch {
      setCandidates([]);
    }
  }

  async function createVacancy(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/api/vacancies", {
        title: newVacancy.title,
        division_id: Number(newVacancy.division_id),
        positions_open: newVacancy.positions_open,
        terms_of_reference: newVacancy.terms_of_reference,
      });
      setShowNew(false);
      setNewVacancy({ title: "", division_id: "", positions_open: 1, terms_of_reference: "" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the vacancy");
    }
  }

  async function submitForApproval(v: Vacancy) {
    setError("");
    try {
      await api.post(`/api/vacancies/${v.id}/submit`);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit for approval");
    }
  }

  async function moveStage(c: Candidate, stage: string) {
    setError("");
    try {
      await api.put(`/api/candidates/${c.id}/stage`, { stage });
      if (selected) openVacancy(selected);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update the candidate's stage");
    }
  }

  async function select(c: Candidate) {
    setError("");
    try {
      await api.post(`/api/candidates/${c.id}/select`, {});
      if (selected) openVacancy(selected);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not select this candidate");
    }
  }

  return (
    <div className="grid gap-5 max-w-5xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
          Recruitment
        </h1>
        {canCreate && (
          <button className="btn btn-primary" onClick={() => setShowNew((s) => !s)}>
            <Plus size={16} /> New vacancy
          </button>
        )}
      </div>

      {error && <div className="card chip-bad">{error}</div>}

      {showNew && (
        <form onSubmit={createVacancy} className="card grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label">Title</label>
            <input className="input" required value={newVacancy.title} onChange={(e) => setNewVacancy({ ...newVacancy, title: e.target.value })} />
          </div>
          <div>
            <label className="label">Division</label>
            <select className="input" required value={newVacancy.division_id} onChange={(e) => setNewVacancy({ ...newVacancy, division_id: e.target.value })}>
              <option value="">Select…</option>
              {divisions.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Positions open</label>
            <input
              className="input"
              type="number"
              min={1}
              value={newVacancy.positions_open}
              onChange={(e) => setNewVacancy({ ...newVacancy, positions_open: Number(e.target.value) })}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Terms of reference</label>
            <textarea
              className="input"
              style={{ height: 90, paddingTop: 10 }}
              value={newVacancy.terms_of_reference}
              onChange={(e) => setNewVacancy({ ...newVacancy, terms_of_reference: e.target.value })}
            />
          </div>
          <div className="sm:col-span-2">
            <button className="btn btn-primary">Create (draft)</button>
          </div>
        </form>
      )}

      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <div className="card grid gap-1 content-start">
          <h3 className="text-base font-semibold mb-2">Vacancies</h3>
          {vacancies.map((v) => (
            <button
              key={v.id}
              onClick={() => openVacancy(v)}
              className="flex items-center justify-between gap-2 px-2.5 py-2 text-sm text-left"
              style={{
                borderRadius: "var(--radius-sm)",
                background: selected?.id === v.id ? "var(--color-primary-tint)" : "transparent",
              }}
            >
              <span className="truncate">{v.title}</span>
              <span className={`chip ${VACANCY_CHIP[v.status] ?? "chip-mute"}`}>{v.status.replace(/_/g, " ")}</span>
            </button>
          ))}
          {vacancies.length === 0 && <p className="text-sm" style={{ color: "var(--color-ink-faint)" }}>No vacancies yet.</p>}
        </div>

        <div className="card">
          {!selected ? (
            <p className="text-sm" style={{ color: "var(--color-ink-faint)" }}>
              Select a vacancy to see candidates.
            </p>
          ) : (
            <div className="grid gap-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <h3 className="text-base font-semibold">{selected.title}</h3>
                  <span className={`chip ${VACANCY_CHIP[selected.status] ?? "chip-mute"}`}>{selected.status.replace(/_/g, " ")}</span>
                </div>
                {canCreate && selected.status === "draft" && (
                  <button className="btn btn-ghost" onClick={() => submitForApproval(selected)}>
                    Submit for approval
                  </button>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
                      <th className="pb-2 font-medium">Candidate</th>
                      <th className="pb-2 font-medium">Contact</th>
                      <th className="pb-2 font-medium">Stage</th>
                      <th className="pb-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c) => (
                      <tr key={c.id} style={{ borderTop: "1px solid var(--color-line)" }}>
                        <td className="py-2 font-medium">{c.full_name}</td>
                        <td className="py-2 text-xs" style={{ color: "var(--color-ink-faint)" }}>
                          {c.email}
                        </td>
                        <td className="py-2">
                          <span className={`chip ${STAGE_CHIP[c.stage] ?? "chip-mute"}`}>{c.stage}</span>
                        </td>
                        <td className="py-2 text-right">
                          {canApprove && c.stage !== "selected" && c.stage !== "rejected" && (
                            <div className="flex gap-1 justify-end flex-wrap">
                              {STAGES.filter((s) => s !== c.stage && s !== "selected").map((s) => (
                                <button key={s} className="btn btn-ghost h-7 px-2 text-xs" onClick={() => moveStage(c, s)}>
                                  {s}
                                </button>
                              ))}
                              <button className="btn btn-primary h-7 px-2 text-xs" onClick={() => select(c)}>
                                Select
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {candidates.length === 0 && (
                  <p className="text-sm py-3" style={{ color: "var(--color-ink-faint)" }}>
                    No candidates have applied yet.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
