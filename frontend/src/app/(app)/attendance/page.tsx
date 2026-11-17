"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Camera, MapPin, LogIn, LogOut, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface AttendanceRecord {
  id: number;
  employee_name: string;
  work_date: string;
  site_name: string | null;
  check_in_at: string | null;
  check_out_at: string | null;
  source: string;
  status: string;
  field_duty_reason: string;
  is_within_geofence: boolean;
}

const STATUS_CHIP: Record<string, string> = {
  present: "chip-ok",
  absent: "chip-bad",
  on_leave: "chip-info",
  pending_approval: "chip-warn",
};

function getLocation(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not available on this device"));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 15000 });
  });
}

export default function AttendancePage() {
  const { hasPermission } = useAuth();
  const [today, setToday] = useState<AttendanceRecord | null>(null);
  const [history, setHistory] = useState<AttendanceRecord[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [fieldDutyReason, setFieldDutyReason] = useState("");
  const [showCamera, setShowCamera] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const canRegister = hasPermission("attendance:create");
  const canApprove = hasPermission("attendance:approve");

  const [register, setRegister] = useState<AttendanceRecord[]>([]);
  const [registerQuery, setRegisterQuery] = useState("");
  const [registerDate, setRegisterDate] = useState(() => new Date().toISOString().slice(0, 10));

  const load = () => {
    api.get<AttendanceRecord | null>("/api/attendance/today").then(setToday).catch(() => {});
    api.get<AttendanceRecord[]>("/api/attendance/mine").then(setHistory).catch(() => {});
  };

  useEffect(load, []);

  useEffect(() => {
    if (!canApprove) return;
    api.get<AttendanceRecord[]>(`/api/attendance/register?for_date=${registerDate}`).then(setRegister).catch(() => {});
  }, [canApprove, registerDate]);

  const registerCounts = useMemo(() => {
    const byStatus: Record<string, number> = {};
    for (const r of register) byStatus[r.status] = (byStatus[r.status] ?? 0) + 1;
    return byStatus;
  }, [register]);

  const filteredRegister = useMemo(() => {
    const q = registerQuery.toLowerCase();
    return register.filter((r) => r.employee_name.toLowerCase().includes(q));
  }, [register, registerQuery]);

  const monthPresentDays = useMemo(() => history.filter((r) => r.status === "present").length, [history]);

  async function openCamera() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
      streamRef.current = stream;
      setShowCamera(true);
      setTimeout(() => {
        if (videoRef.current) videoRef.current.srcObject = stream;
      }, 50);
    } catch {
      setError("Could not access the camera. Check your browser permissions.");
    }
  }

  function closeCamera() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setShowCamera(false);
  }

  async function captureAndCheckIn() {
    if (!videoRef.current) return;
    setBusy(true);
    setError("");
    try {
      const canvas = document.createElement("canvas");
      canvas.width = videoRef.current.videoWidth || 480;
      canvas.height = videoRef.current.videoHeight || 640;
      const ctx = canvas.getContext("2d");
      ctx?.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
      const selfieBase64 = canvas.toDataURL("image/jpeg", 0.85);

      const pos = await getLocation();
      await api.post("/api/attendance/check-in", {
        lat: pos.coords.latitude,
        lng: pos.coords.longitude,
        accuracy_m: pos.coords.accuracy,
        selfie_base64: selfieBase64,
        field_duty_reason: fieldDutyReason,
      });
      closeCamera();
      setFieldDutyReason("");
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not check in — try again");
    } finally {
      setBusy(false);
    }
  }

  async function checkOut() {
    setBusy(true);
    setError("");
    try {
      const pos = await getLocation();
      await api.post("/api/attendance/check-out", { lat: pos.coords.latitude, lng: pos.coords.longitude });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not check out");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5 max-w-6xl">
      <h1 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
        Attendance
      </h1>

      {error && <div className="card chip-bad">{error}</div>}

      {canRegister && history.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="card flex items-center justify-between">
            <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
              Present (last 90 days)
            </span>
            <span className="text-lg font-bold px-3 py-1 rounded-full" style={{ background: "var(--color-ok-tint)", color: "var(--color-ok)" }}>
              {monthPresentDays}
            </span>
          </div>
          <div className="card flex items-center justify-between">
            <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
              Total records
            </span>
            <span className="text-lg font-bold px-3 py-1 rounded-full" style={{ background: "var(--color-surface-2)", color: "var(--color-ink-soft)" }}>
              {history.length}
            </span>
          </div>
          <div className="card flex items-center justify-between">
            <span className="text-sm font-medium" style={{ color: "var(--color-ink-soft)" }}>
              Pending approval
            </span>
            <span
              className="text-lg font-bold px-3 py-1 rounded-full"
              style={{ background: "var(--color-warn-tint)", color: "var(--color-warn)" }}
            >
              {history.filter((r) => r.status === "pending_approval").length}
            </span>
          </div>
        </div>
      )}

      {canRegister && (
        <div className="card grid gap-3">
          <h3 className="text-base font-semibold">Today</h3>

          {today ? (
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`chip ${STATUS_CHIP[today.status] ?? "chip-mute"}`}>{today.status.replace(/_/g, " ")}</span>
              <span className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
                Checked in {today.check_in_at ? new Date(today.check_in_at).toLocaleTimeString() : "—"}
                {today.check_out_at && ` · Checked out ${new Date(today.check_out_at).toLocaleTimeString()}`}
              </span>
              {today.site_name && <span className="chip chip-mute">{today.site_name}</span>}
            </div>
          ) : (
            <p className="text-sm" style={{ color: "var(--color-ink-faint)" }}>
              You haven&apos;t checked in today.
            </p>
          )}

          {!showCamera && (
            <div className="flex gap-2 flex-wrap">
              {!today?.check_in_at && (
                <button className="btn btn-primary" onClick={openCamera}>
                  <LogIn size={16} /> Check in
                </button>
              )}
              {today?.check_in_at && !today?.check_out_at && (
                <button className="btn btn-primary" onClick={checkOut} disabled={busy}>
                  <LogOut size={16} /> {busy ? "Checking out…" : "Check out"}
                </button>
              )}
            </div>
          )}

          {showCamera && (
            <div className="grid gap-3">
              <input
                className="input"
                placeholder="If you're outside the office/site boundary, say why (field duty)"
                value={fieldDutyReason}
                onChange={(e) => setFieldDutyReason(e.target.value)}
              />
              <video ref={videoRef} autoPlay playsInline className="rounded-lg w-full max-w-sm" style={{ border: "1px solid var(--color-line)" }} />
              <div className="flex gap-2">
                <button className="btn btn-primary" onClick={captureAndCheckIn} disabled={busy}>
                  <Camera size={16} /> {busy ? "Checking in…" : "Capture selfie & check in"}
                </button>
                <button className="btn btn-ghost" onClick={closeCamera}>
                  Cancel
                </button>
              </div>
              <p className="text-xs flex items-center gap-1" style={{ color: "var(--color-ink-faint)" }}>
                <MapPin size={12} /> Your location is checked against the site boundary automatically.
              </p>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h3 className="text-base font-semibold mb-3">History</h3>
        {history.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-ink-faint)" }}>No attendance records yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
                  <th className="pb-2 font-medium">Date</th>
                  <th className="pb-2 font-medium">Site</th>
                  <th className="pb-2 font-medium">In / Out</th>
                  <th className="pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map((r) => (
                  <tr key={r.id} style={{ borderTop: "1px solid var(--color-line)" }}>
                    <td className="py-2">{r.work_date}</td>
                    <td className="py-2">{r.site_name ?? "—"}</td>
                    <td className="py-2">
                      {r.check_in_at ? new Date(r.check_in_at).toLocaleTimeString() : "—"}
                      {" / "}
                      {r.check_out_at ? new Date(r.check_out_at).toLocaleTimeString() : "—"}
                    </td>
                    <td className="py-2">
                      <span className={`chip ${STATUS_CHIP[r.status] ?? "chip-mute"}`}>{r.status.replace(/_/g, " ")}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {canApprove && (
        <div className="card">
          <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
            <h3 className="text-base font-semibold">Team register</h3>
            <div className="flex items-center gap-2">
              <input type="date" className="input h-8 text-xs w-36" value={registerDate} onChange={(e) => setRegisterDate(e.target.value)} />
              <div className="relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: "var(--color-ink-faint)" }} />
                <input
                  className="input pl-8 h-8 text-xs w-48"
                  placeholder="Search employee…"
                  value={registerQuery}
                  onChange={(e) => setRegisterQuery(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="flex gap-2 flex-wrap mb-3">
            <span className="chip chip-ok">{registerCounts.present ?? 0} present</span>
            <span className="chip chip-bad">{registerCounts.absent ?? 0} absent</span>
            <span className="chip chip-info">{registerCounts.on_leave ?? 0} on leave</span>
            <span className="chip chip-warn">{registerCounts.pending_approval ?? 0} pending</span>
          </div>

          {filteredRegister.length === 0 ? (
            <p className="text-sm py-6 text-center" style={{ color: "var(--color-ink-faint)" }}>
              No attendance records for this date.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--color-ink-faint)" }} className="text-left">
                    <th className="pb-2 font-medium">Employee</th>
                    <th className="pb-2 font-medium">Site</th>
                    <th className="pb-2 font-medium">In / Out</th>
                    <th className="pb-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRegister.map((r) => (
                    <tr key={r.id} style={{ borderTop: "1px solid var(--color-line)" }}>
                      <td className="py-2 font-medium">{r.employee_name}</td>
                      <td className="py-2">{r.site_name ?? "—"}</td>
                      <td className="py-2">
                        {r.check_in_at ? new Date(r.check_in_at).toLocaleTimeString() : "—"}
                        {" / "}
                        {r.check_out_at ? new Date(r.check_out_at).toLocaleTimeString() : "—"}
                      </td>
                      <td className="py-2">
                        <span className={`chip ${STATUS_CHIP[r.status] ?? "chip-mute"}`}>{r.status.replace(/_/g, " ")}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
