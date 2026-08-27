import type { SimResult } from "../types";

interface Props {
  result: SimResult | null;
  locationName: string;
  plotLabel: string;
  provenance: string;
  loading: boolean;
}

export default function TitleBlock({ result, locationName, plotLabel, provenance, loading }: Props) {
  if (!result) {
    return (
      <div className="titleblock mono">
        <div className="tb-head">Temperature · peak daytime · air at 2 m</div>
        <div style={{ padding: "1rem", color: "var(--ink60)" }}>
          {loading ? "Simulating…" : "Paint something to see the projected temperature."}
        </div>
      </div>
    );
  }

  const band = (result.delta_high - result.delta_low) / 2;
  const span = Math.max(Math.abs(result.delta_c), 0.001);
  const measuredPct = (100 * result.measured_c) / (result.measured_c + span);

  return (
    <div
      className="titleblock mono"
      style={{ border: "1.5px solid var(--ink)", background: "var(--paper2)", width: "100%", boxSizing: "border-box", overflow: "hidden" }}
    >
      <div
        className="tb-head"
        style={{
          fontSize: "0.62rem",
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          padding: "0.4rem 0.8rem",
          borderBottom: "1px solid var(--rule)",
          color: "var(--ink60)",
        }}
      >
        Temperature · peak daytime · air at 2 m — {locationName} · {plotLabel}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)" }}>
        <Cell label="FortyGuard measured" value={`${result.measured_c.toFixed(1)}°C`} color="var(--measured)" />
        <Cell label="Modelled change" value={`${result.delta_c >= 0 ? "+" : ""}${result.delta_c.toFixed(1)}`} band={`±${band.toFixed(1)}`} color="var(--modelled)" />
        <Cell label="Projected" value={`${result.projected_c.toFixed(1)}°C`} color="var(--ink)" last />
      </div>
      <div style={{ padding: "0.7rem 0.8rem 0.9rem", borderTop: "1px solid var(--rule)" }}>
        <div style={{ height: 15, display: "flex", border: "1px solid var(--ink)" }}>
          <div style={{ width: `${measuredPct}%`, background: "var(--measured)" }} />
          <div
            style={{
              width: `${100 - measuredPct}%`,
              borderLeft: "1px solid var(--ink)",
              background:
                "repeating-linear-gradient(45deg, var(--modelled) 0 3px, transparent 3px 6px), var(--paper)",
            }}
          />
        </div>
        <div style={{ display: "flex", gap: "1.4rem", marginTop: "0.45rem", fontSize: "0.58rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--ink60)" }}>
          <span>
            <span className="swatch sw-measured" />
            Measured
          </span>
          <span>
            <span className="swatch sw-modelled" />
            Modelled — not a measurement
          </span>
        </div>
      </div>
      <div style={{ padding: "0.5rem 0.8rem", fontSize: "0.72rem", color: "var(--ink60)", lineHeight: 1.5, borderTop: "1px solid var(--rule)" }}>
        {provenance}
      </div>
      {result.notes.map((note, i) => (
        <div className="flag" key={i}>
          {note}
        </div>
      ))}
    </div>
  );
}

function Cell({ label, value, band, color, last }: { label: string; value: string; band?: string; color: string; last?: boolean }) {
  return (
    <div style={{ minWidth: 0, overflow: "hidden", padding: "0.7rem 0.5rem", borderRight: last ? "none" : "1px solid var(--rule)" }}>
      <span style={{ display: "block", fontSize: "0.55rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--ink60)", marginBottom: "0.3rem" }}>
        {label}
      </span>
      <span style={{ display: "block", fontWeight: 600, fontSize: "1.25rem", lineHeight: 1.1, letterSpacing: "-0.02em", color, overflow: "hidden", textOverflow: "ellipsis" }}>
        {value}
        {band && <span style={{ display: "block", fontSize: "0.65rem", fontWeight: 400, color: "var(--ink60)", marginTop: "0.15rem" }}>{band}</span>}
      </span>
    </div>
  );
}
