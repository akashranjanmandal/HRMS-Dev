"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface SearchResultItem {
  kind: "employee" | "approval_request" | "asset";
  id: number;
  title: string;
  subtitle: string;
  url: string;
}

const KIND_LABEL: Record<string, string> = {
  employee: "People",
  approval_request: "Requests",
  asset: "Assets",
};

export function GlobalSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    const handle = setTimeout(() => {
      api
        .get<{ results: SearchResultItem[] }>(`/api/search?q=${encodeURIComponent(query.trim())}`)
        .then((res) => setResults(res.results))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [query]);

  const grouped = results.reduce<Record<string, SearchResultItem[]>>((acc, r) => {
    (acc[r.kind] ??= []).push(r);
    return acc;
  }, {});

  function go(r: SearchResultItem) {
    setOpen(false);
    setQuery("");
    router.push(r.url);
  }

  return (
    <div ref={containerRef} className="relative flex-1 max-w-sm">
      <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--color-ink-faint)" }} />
      <input
        className="input pl-9 h-9 text-sm"
        placeholder="Search people, requests, assets…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {loading && (
        <Loader2 size={14} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin" style={{ color: "var(--color-ink-faint)" }} />
      )}

      {open && query.trim().length >= 2 && (
        <div
          className="absolute left-0 right-0 mt-1.5 rounded-lg shadow-lg overflow-hidden z-50"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-line)", boxShadow: "var(--shadow-aaranyak)" }}
        >
          {results.length === 0 && !loading && (
            <p className="text-sm py-4 px-3 text-center" style={{ color: "var(--color-ink-faint)" }}>
              No matches for &ldquo;{query}&rdquo;.
            </p>
          )}
          <div className="max-h-80 overflow-y-auto">
            {Object.entries(grouped).map(([kind, items]) => (
              <div key={kind}>
                <div
                  className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide"
                  style={{ color: "var(--color-ink-faint)", background: "var(--color-surface-2)" }}
                >
                  {KIND_LABEL[kind] ?? kind}
                </div>
                {items.map((r) => (
                  <button
                    key={`${r.kind}-${r.id}`}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-surface-2)]"
                    onClick={() => go(r)}
                  >
                    <div className="font-medium truncate">{r.title}</div>
                    <div className="text-xs truncate" style={{ color: "var(--color-ink-faint)" }}>
                      {r.subtitle}
                    </div>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
