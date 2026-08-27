import type { SimResult } from "../types";

export default function CompositionTable({ result }: { result: SimResult | null }) {
  if (!result) return null;
  const { now, base } = result;
  const rows: [string, string, string][] = [
    ["Canopy", `${base.canopy_pp.toFixed(0)}%`, `${now.canopy_pp.toFixed(0)}%`],
    ["Impervious", `${base.impervious_pp.toFixed(0)}%`, `${now.impervious_pp.toFixed(0)}%`],
    ["Building", `${base.building_pp.toFixed(0)}%`, `${now.building_pp.toFixed(0)}%`],
    ["Mean albedo", base.mean_albedo.toFixed(2), now.mean_albedo.toFixed(2)],
    ["Trees", base.tree_count.toLocaleString(), now.tree_count.toLocaleString()],
  ];
  return (
    <div>
      <div className="eyebrow">Composition</div>
      <table className="mono" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.72rem", border: "1px solid var(--rule)" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--rule)" }}>
            <th style={{ textAlign: "left", padding: "0.3rem 0.5rem" }} />
            <th style={{ textAlign: "right", padding: "0.3rem 0.5rem", fontSize: "0.55rem", color: "var(--ink60)" }}>EXISTING</th>
            <th style={{ textAlign: "right", padding: "0.3rem 0.5rem", fontSize: "0.55rem", color: "var(--ink60)" }}>PROPOSED</th>
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
        </tbody>
      </table>
    </div>
  );
}
