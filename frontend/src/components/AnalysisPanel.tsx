import { diffGrids } from "../state/environment";
import type { EnvironmentState } from "../state/environment";
import type { Field } from "../types";

function stats(field: Field) {
  const values = field.flat().filter((v): v is number => v !== null);
  if (values.length === 0) return null;
  const sum = values.reduce((a, b) => a + b, 0);
  return { avg: sum / values.length, max: Math.max(...values), min: Math.min(...values) };
}

function bucket(delta: number): { label: string; color: string } {
  if (delta <= -3) return { label: "Strong cooling", color: "#1B4B52" };
  if (delta <= -1) return { label: "Cooling", color: "#3E93A0" };
  if (delta < 1) return { label: "No significant change", color: "var(--ink60)" };
  if (delta < 3) return { label: "Warming", color: "#B36A3E" };
  return { label: "Strong warming", color: "#8C2F1E" };
}

export default function AnalysisPanel({ state }: { state: EnvironmentState }) {
  const original = state.originalResult;
  const applied = state.appliedResult;

  if (!original || !applied || !state.appliedGrid) {
    return (
      <div className="mono" style={{ color: "var(--ink60)", fontSize: "0.75rem", padding: "0.5rem 0" }}>
        Paint some changes, then "Apply Changes & Generate Heatmap" to compare against the
        original reading.
      </div>
    );
  }

  const before = stats(original.projected_field);
  const after = stats(applied.projected_field);
  const affected = diffGrids(state.baselineGrid, state.appliedGrid, state.mask).length;
  const overall = bucket(applied.delta_c - original.delta_c);

  const rows: [string, string, string][] = before && after
    ? [
        ["Average temperature", `${before.avg.toFixed(1)}°C`, `${after.avg.toFixed(1)}°C`],
        ["Maximum temperature", `${before.max.toFixed(1)}°C`, `${after.max.toFixed(1)}°C`],
        ["Minimum temperature", `${before.min.toFixed(1)}°C`, `${after.min.toFixed(1)}°C`],
      ]
    : [];

  return (
    <div className="mono" style={{ fontSize: "0.75rem" }}>
      <div className="eyebrow">Before / after</div>
      <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid var(--rule)" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--rule)" }}>
            <th style={{ textAlign: "left", padding: "0.3rem 0.5rem", fontSize: "0.6rem", color: "var(--ink60)" }} />
            <th style={{ textAlign: "right", padding: "0.3rem 0.5rem", fontSize: "0.6rem", color: "var(--ink60)" }}>
              ORIGINAL
            </th>
            <th style={{ textAlign: "right", padding: "0.3rem 0.5rem", fontSize: "0.6rem", color: "var(--ink60)" }}>
              MODIFIED
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, a, b]) => (
            <tr key={label}>
              <td style={{ padding: "0.28rem 0.5rem", color: "var(--ink60)" }}>{label}</td>
              <td style={{ padding: "0.28rem 0.5rem", textAlign: "right" }}>{a}</td>
              <td style={{ padding: "0.28rem 0.5rem", textAlign: "right", fontWeight: 600 }}>{b}</td>
            </tr>
          ))}
          <tr>
            <td style={{ padding: "0.28rem 0.5rem", color: "var(--ink60)" }}>Temperature difference</td>
            <td colSpan={2} style={{ padding: "0.28rem 0.5rem", textAlign: "right", fontWeight: 600 }}>
              {(applied.delta_c - original.delta_c).toFixed(1)}°C
            </td>
          </tr>
          <tr>
            <td style={{ padding: "0.28rem 0.5rem", color: "var(--ink60)" }}>Affected cells</td>
            <td colSpan={2} style={{ padding: "0.28rem 0.5rem", textAlign: "right", fontWeight: 600 }}>
              {affected}
            </td>
          </tr>
        </tbody>
      </table>

      <div style={{ marginTop: "0.5rem", padding: "0.4rem 0.6rem", borderLeft: `3px solid ${overall.color}`, background: "rgba(0,0,0,0.03)" }}>
        {overall.label} ({applied.delta_c >= original.delta_c ? "+" : ""}
        {(applied.delta_c - original.delta_c).toFixed(1)}°C modelled)
      </div>

      <div style={{ marginTop: "0.6rem", fontSize: "0.65rem", color: "var(--ink60)" }}>
        Both readings are simulation estimates from the same coefficients as the title block
        above — not independent measurements. See "Method and limits" for what each coefficient's
        status means.
      </div>
    </div>
  );
}
