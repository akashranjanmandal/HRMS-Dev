"use client";

import { useEffect, useState } from "react";
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
    <div className="grid gap-5 max-w-4xl">
      <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
        Performance Appraisal
      </h1>

      {error && <div className="card chip-bad">{error}</div>}

      <div className="card">
        <h3 className="text-base font-semibold mb-3">My appraisals</h3>
        {mine.length === 0 && <p className="text-sm" style={{ color: "var(--color-ink-faint)" }}>No appraisal cycle yet.</p>}
        <div className="grid gap-2">
          {mine.map((r) => (
            <div key={r.id} className="flex items-center justify-between gap-3 py-1.5">
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
      </div>

      {canApprove && (
        <div className="card">
          <h3 className="text-base font-semibold mb-3">Awaiting your review</h3>
          {queue.filter((r) => r.stage !== "self_assessment" && r.stage !== "completed").length === 0 && (
            <p className="text-sm" style={{ color: "var(--color-ink-faint)" }}>Nothing pending.</p>
          )}
          <div className="grid gap-2">
            {queue
              .filter((r) => r.stage === "supervisor_review" || r.stage === "division_head_review")
              .map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-3 py-1.5">
                  <div>
                    <p className="font-medium text-sm">{r.employee_name}</p>
                    <span className={`chip ${STAGE_CHIP[r.stage]}`}>{r.stage.replace(/_/g, " ")}</span>
                  </div>
                  <button
                    className="btn btn-ghost h-8 px-3 text-xs"
                    onClick={() => {
                      setActive(r);
                      setComments("");
                      setRating(4);
                      setSalaryRevision(false);
                    }}
                  >
                    Review
                  </button>
                </div>
              ))}
          </div>
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
