import type { SimResult } from "../types";

export default function ContributionChart({ result }: { result: SimResult | null }) {
  if (!result) return null;
  const terms = Object.entries(result.breakdown).filter(([, v]) => Math.abs(v) > 0.005);
  if (terms.length === 0) {
    return (
      <div className="mono" style={{ fontSize: "0.72rem", color: "var(--ink60)" }}>
        No changes yet — paint something on the canvas.
      </div>
    );
  }
  terms.sort((a, b) => a[1] - b[1]);
  const max = Math.max(...terms.map(([, v]) => Math.abs(v)), 0.01);

  return (
    <div>
      <div className="eyebrow">Contribution by mechanism</div>
      {terms.map(([term, v]) => (
        <div key={term} className="mono" style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.68rem", margin: "0.2rem 0" }}>
          <span style={{ width: "6.5em", color: "var(--ink60)" }}>{term}</span>
          <span style={{ flex: 1, display: "flex", justifyContent: v < 0 ? "flex-end" : "flex-start" }}>
            <span
              style={{
                width: `${(Math.abs(v) / max) * 100}%`,
                minWidth: 2,
                height: 10,
                background: "var(--modelled)",
              }}
            />
          </span>
          <span style={{ width: "3.5em", textAlign: "right" }}>{v >= 0 ? "+" : ""}{v.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}
