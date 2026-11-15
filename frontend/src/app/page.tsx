"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function RootPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? "/dashboard" : "/login");
  }, [loading, user, router]);

  return (
    <div className="min-h-screen grid place-items-center" style={{ background: "var(--color-bg)" }}>
      <span className="text-sm" style={{ color: "var(--color-ink-faint)" }}>
        Loading…
      </span>
    </div>
  );
}
