"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Step = "credentials" | "otp";

export default function LoginPage() {
  const router = useRouter();
  const { login, verifyOtp } = useAuth();

  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleCredentials(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { mfaRequired } = await login(email, password);
      if (mfaRequired) {
        setStep("otp");
      } else {
        router.replace("/dashboard");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  }

  async function handleOtp(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await verifyOtp(email, code);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not verify the code");
    } finally {
      setBusy(false);
    }
  }

  const maskedEmail = email.includes("@")
    ? email[0] + "•••••" + email.slice(email.indexOf("@"))
    : email;

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{ background: "var(--color-bg)" }}
    >
      <div
        className="w-full max-w-4xl grid md:grid-cols-2 overflow-hidden"
        style={{
          border: "1px solid var(--color-line)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-aaranyak)",
        }}
      >
        {/* Brand panel */}
        <div
          className="hidden md:flex flex-col justify-between p-10 relative overflow-hidden"
          style={{ background: "var(--color-primary)", color: "var(--color-primary-ink)" }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-lg grid place-items-center font-bold"
              style={{
                background: "var(--color-primary-ink)",
                color: "var(--color-primary)",
                fontFamily: "var(--font-display)",
              }}
            >
              A
            </div>
            <span className="font-semibold" style={{ fontFamily: "var(--font-display)" }}>
              Aaranyak HRMS
            </span>
          </div>
          <div>
            <h3
              className="text-3xl leading-tight max-w-[14ch]"
              style={{ fontFamily: "var(--font-display)" }}
            >
              People, places and projects in one place
            </h3>
            <p className="mt-3 max-w-[40ch] opacity-85 text-sm">
              Attendance, leave, approvals and staff records for every
              division and field site.
            </p>
          </div>
          <svg
            className="absolute -right-10 -bottom-16 w-[420px] opacity-20"
            viewBox="0 0 400 300"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M20 260 C 80 180, 160 220, 220 150 S 340 80, 390 40" />
            <path d="M20 290 C 90 210, 170 250, 240 180 S 350 110, 400 80" />
            <path d="M40 300 C 110 240, 190 280, 260 210 S 360 150, 410 120" />
          </svg>
        </div>

        {/* Form panel */}
        <div className="flex flex-col justify-center p-10 gap-4" style={{ background: "var(--color-surface)" }}>
          {step === "credentials" ? (
            <form onSubmit={handleCredentials} className="grid gap-4">
              <span
                className="text-xs font-semibold uppercase"
                style={{ color: "var(--color-accent)", fontFamily: "var(--font-mono)", letterSpacing: "0.06em" }}
              >
                Step 1 of 2
              </span>
              <h4 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
                Sign in
              </h4>

              <div>
                <label className="label" htmlFor="email">
                  Work email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="username"
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@aaranyak.org"
                />
              </div>

              <div>
                <label className="label" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  className="input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              {error && (
                <p className="text-sm" style={{ color: "var(--color-bad)" }}>
                  {error}
                </p>
              )}

              <button type="submit" className="btn btn-primary btn-lg" disabled={busy}>
                {busy ? "Signing in…" : "Continue"}
              </button>
              <span className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
                Forgot your password? Ask HR for a temporary one.
              </span>
            </form>
          ) : (
            <form onSubmit={handleOtp} className="grid gap-4">
              <span
                className="text-xs font-semibold uppercase"
                style={{ color: "var(--color-accent)", fontFamily: "var(--font-mono)", letterSpacing: "0.06em" }}
              >
                Step 2 of 2
              </span>
              <h4 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
                Enter the code
              </h4>
              <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
                We sent a 6-digit code to {maskedEmail}. It expires in 10 minutes.
              </p>

              <div>
                <label className="label" htmlFor="otp">
                  One-time code
                </label>
                <input
                  id="otp"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  required
                  className="input text-center tracking-[0.5em]"
                  style={{ fontFamily: "var(--font-mono)", fontSize: "22px" }}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  autoFocus
                />
              </div>

              {error && (
                <p className="text-sm" style={{ color: "var(--color-bad)" }}>
                  {error}
                </p>
              )}

              <button type="submit" className="btn btn-primary btn-lg" disabled={busy}>
                {busy ? "Verifying…" : "Verify and sign in"}
              </button>
              <button
                type="button"
                className="text-sm text-left"
                style={{ color: "var(--color-ink-soft)" }}
                onClick={() => {
                  setStep("credentials");
                  setCode("");
                  setError(null);
                }}
              >
                Use a different account
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
