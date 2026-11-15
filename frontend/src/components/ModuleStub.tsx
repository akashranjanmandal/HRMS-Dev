export function ModuleStub({ title, note }: { title: string; note?: string }) {
  return (
    <div className="grid gap-1">
      <h3 className="text-2xl" style={{ fontFamily: "var(--font-display)" }}>
        {title}
      </h3>
      <p className="text-sm" style={{ color: "var(--color-ink-soft)" }}>
        {note ?? "Coming soon."}
      </p>
    </div>
  );
}
