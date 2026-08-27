import type { Dispatch } from "react";
import type { Action, EnvironmentState } from "../state/environment";
import type { MaterialsResponse } from "../types";

interface Props {
  materialsResp: MaterialsResponse;
  state: EnvironmentState;
  dispatch: Dispatch<Action>;
}

export default function MaterialPalette({ materialsResp, state, dispatch }: Props) {
  const warning = materialsResp.materials[state.material]?.warning;

  return (
    <div>
      <div className="eyebrow">Materials</div>
      {Object.entries(materialsResp.palette).map(([group, items]) => (
        <div key={group} style={{ marginBottom: "0.6rem" }}>
          <div
            className="mono"
            style={{
              fontSize: "0.55rem",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--ink60)",
              margin: "0.5rem 0 0.3rem",
            }}
          >
            {group}
          </div>
          {items.map(({ key, label, colour }) => {
            const active = state.material === key && state.tool !== "erase";
            return (
              <button
                key={key}
                onClick={() => {
                  dispatch({ type: "SET_MATERIAL", material: key });
                  if (state.tool === "erase") dispatch({ type: "SET_TOOL", tool: "paint" });
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  width: "100%",
                  textAlign: "left",
                  padding: "0.3rem 0.5rem",
                  marginBottom: "2px",
                  border: "1px solid var(--rule)",
                  borderLeft: `6px solid ${colour}`,
                  borderRadius: "2px",
                  background: active ? "var(--ink)" : "var(--paper)",
                  color: active ? "var(--paper)" : "var(--ink)",
                }}
              >
                <span>{active ? "●" : "○"}</span>
                <span>{label}</span>
              </button>
            );
          })}
        </div>
      ))}
      {warning && state.tool !== "erase" && <div className="flag">{warning}</div>}
    </div>
  );
}
