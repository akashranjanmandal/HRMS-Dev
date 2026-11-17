"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface AppraisalReview {
  id: number;
  cycle_name: string;
  employee_id: number;
  employee_name: string;
  stage: string;
  self_assessment_text: string;
  self_rating: number | null;
  supervisor_comments: string;
  supervisor_rating: number | null;
  division_head_comments: string;
  division_head_rating: number | null;
  salary_revision_recommended: boolean;
}

const STAGE_CHIP: Record<string, string> = {
  self_assessment: "chip-warn",
  supervisor_review: "chip-info",
  division_head_review: "chip-info",
  completed: "chip-ok",
};

export default function AppraisalPage() {
  const { hasPermission } = useAuth();
  const [mine, setMine] = useState<AppraisalReview[]>([]);
  const [queue, setQueue] = useState<AppraisalReview[]>([]);
  const [error, setError] = useState("");
  const [active, setActive] = useState<AppraisalReview | null>(null);
  const [selfText, setSelfText] = useState("");
  const [selfRating, setSelfRating] = useState(4);
  const [comments, setComments] = useState("");
  const [rating, setRating] = useState(4);
  const [salaryRevision, setSalaryRevision] = useState(false);

  const canApprove = hasPermission("appraisal:approve");

  const load = () => {
    api.get<AppraisalReview[]>("/api/appraisal/mine").then(setMine).catch(() => {});
    if (canApprove) {
      api.get<AppraisalReview[]>("/api/appraisal").then(setQueue).catch(() => {});
    }
  };
  useEffect(load, [canApprove]);

  const stageCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const r of queue) counts[r.stage] = (counts[r.stage] ?? 0) + 1;
    return counts;
  }, [queue]);

  async function submitSelfAssessment(review: AppraisalReview) {
    setError("");
    try {
      await api.post(`/api/appraisal/reviews/${review.id}/self-assessment`, {
        self_assessment_text: selfText,
        self_rating: selfRating,
        ratings: [],
      });
      setActive(null);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit your self-assessment");
    }
  }

  async function submitSupervisorReview(review: AppraisalReview) {
    setError("");
    try {
      await api.post(`/api/appraisal/reviews/${review.id}/supervisor-review`, {
        supervisor_comments: comments,
        supervisor_rating: rating,
      });
      setActive(null);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit the supervisor review");
    }
  }

  async function submitDivisionHeadReview(review: AppraisalReview) {
    setError("");
    try {
      await api.post(`/api/appraisal/reviews/${review.id}/division-head-review`, {
        division_head_comments: comments,
        division_head_rating: rating,
        salary_revision_recommended: salaryRevision,
      });
      setActive(null);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit the Division Head review");
    }
  }

  return (
    <div className="grid gap-5 max-w-5xl">
      <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
        Performance Appraisal
      </h1>

      {error && <div className="card chip-bad">{error}</div>}

      {canApprove && queue.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <AppraisalStatTile label="Self-assessment" value={stageCounts.self_assessment ?? 0} tone="warn" />
          <AppraisalStatTile label="Supervisor review" value={stageCounts.supervisor_review ?? 0} tone="info" />
          <AppraisalStatTile label="Division Head review" value={stageCounts.division_head_review ?? 0} tone="info" />
          <AppraisalStatTile label="Completed" value={stageCounts.completed ?? 0} tone="ok" />
        </div>
      )}

      <div className="card">
        <h3 className="text-base font-semibold mb-3">My appraisals</h3>
        {mine.length === 0 ? (
          <div className="py-8 text-center grid gap-1">
            <p className="text-sm font-medium">No appraisal cycle yet.</p>
            <p className="text-xs" style={{ color: "var(--color-ink-faint)" }}>
              You&apos;ll see your review here once HR opens a cycle.
            </p>
          </div>
        ) : (
          <div className="grid gap-2">
            {mine.map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-3 py-1.5" style={{ borderTop: "1px solid var(--color-line)" }}>
                <div>
                  <p className="font-medium text-sm">{r.cycle_name}</p>
                  <span className={`chip ${STAGE_CHIP[r.stage]}`}>{r.stage.replace(/_/g, " ")}</span>
                </div>
                {r.stage === "self_assessment" && (
                  <button
                    className="btn btn-ghost h-8 px-3 text-xs"
                    onClick={() => {
                      setActive(r);
                      setSelfText("");
                      setSelfRating(4);
                    }}
                  >
                    Complete self-assessment
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {canApprove && (
        <div className="card">
          <h3 className="text-base font-semibold mb-3">Team overview</h3>
          {queue.length === 0 ? (
            <p className="text-sm py-6 text-center" style={{ color: "var(--color-ink-faint)" }}>
              No reviews in your scope yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
                    <th className="pb-2 font-medium">Employee</th>
                    <th className="pb-2 font-medium">Cycle</th>
                    <th className="pb-2 font-medium">Stage</th>
                    <th className="pb-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {queue.map((r) => (
                    <tr key={r.id} style={{ borderTop: "1px solid var(--color-line)" }}>
                      <td className="py-2 font-medium">{r.employee_name}</td>
                      <td className="py-2">{r.cycle_name}</td>
                      <td className="py-2">
                        <span className={`chip ${STAGE_CHIP[r.stage]}`}>{r.stage.replace(/_/g, " ")}</span>
                      </td>
                      <td className="py-2 text-right">
                        {(r.stage === "supervisor_review" || r.stage === "division_head_review") && (
                          <button
                            className="btn btn-ghost h-7 px-2 text-xs"
                            onClick={() => {
                              setActive(r);
                              setComments("");
                              setRating(4);
                              setSalaryRevision(false);
                            }}
                          >
                            Review
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {active && active.stage === "self_assessment" && (
        <Modal title="Self-assessment" onClose={() => setActive(null)}>
          <textarea
            className="input"
            style={{ height: 100, paddingTop: 10 }}
            placeholder="How did this period go?"
            value={selfText}
            onChange={(e) => setSelfText(e.target.value)}
          />
          <RatingPicker value={selfRating} onChange={setSelfRating} />
          <button className="btn btn-primary" onClick={() => submitSelfAssessment(active)}>
            Submit
          </button>
        </Modal>
      )}

      {active && active.stage === "supervisor_review" && (
        <Modal title={`Supervisor review — ${active.employee_name}`} onClose={() => setActive(null)}>
          <p className="text-sm italic" style={{ color: "var(--color-ink-soft)" }}>
            &ldquo;{active.self_assessment_text}&rdquo; (self-rating: {active.self_rating})
          </p>
          <textarea className="input" style={{ height: 80, paddingTop: 10 }} value={comments} onChange={(e) => setComments(e.target.value)} />
          <RatingPicker value={rating} onChange={setRating} />
          <button className="btn btn-primary" onClick={() => submitSupervisorReview(active)}>
            Submit
          </button>
        </Modal>
      )}

      {active && active.stage === "division_head_review" && (
        <Modal title={`Division Head review — ${active.employee_name}`} onClose={() => setActive(null)}>
          <p className="text-sm italic" style={{ color: "var(--color-ink-soft)" }}>
            Supervisor: &ldquo;{active.supervisor_comments}&rdquo; (rating: {active.supervisor_rating})
          </p>
          <textarea className="input" style={{ height: 80, paddingTop: 10 }} value={comments} onChange={(e) => setComments(e.target.value)} />
          <RatingPicker value={rating} onChange={setRating} />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={salaryRevision} onChange={(e) => setSalaryRevision(e.target.checked)} />
            Recommend a salary revision
          </label>
          <button className="btn btn-primary" onClick={() => submitDivisionHeadReview(active)}>
            Complete appraisal
          </button>
        </Modal>
      )}
    </div>
  );
}

function RatingPicker({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex gap-1.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className="w-9 h-9 rounded-lg text-sm font-semibold"
          style={{
            background: value === n ? "var(--color-primary)" : "var(--color-surface-2)",
            color: value === n ? "var(--color-primary-ink)" : "var(--color-ink-soft)",
          }}
          onClick={() => onChange(n)}
        >
          {n}
        </button>
      ))}
    </div>
  );
}

function AppraisalStatTile({ label, value, tone }: { label: string; value: number; tone: "ok" | "warn" | "info" }) {
  const colors = {
    ok: { bg: "var(--color-ok-tint)", fg: "var(--color-ok)" },
    warn: { bg: "var(--color-warn-tint)", fg: "var(--color-warn)" },
    info: { bg: "var(--color-primary-tint)", fg: "var(--color-primary)" },
  }[tone];
  return (
    <div className="card flex items-center justify-between">
      <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
        {label}
      </span>
      <span className="text-lg font-bold px-3 py-1 rounded-full" style={{ background: colors.bg, color: colors.fg }}>
        {value}
      </span>
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 grid place-items-center p-4 z-50" style={{ background: "rgb(0 0 0 / 0.4)" }}>
      <div className="card grid gap-3 w-full max-w-md">
        <h3 className="text-base font-semibold">{title}</h3>
        {children}
        <button className="btn btn-ghost" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
