import type { Dispatch } from "react";
import type { Action, EnvironmentState, Tool } from "../state/environment";
import { rectCells } from "../state/environment";

interface Props {
  state: EnvironmentState;
  dispatch: Dispatch<Action>;
  onApply: () => void;
  applying: boolean;
}

const TOOLS: { tool: Tool; label: string }[] = [
  { tool: "paint", label: "Paint" },
  { tool: "erase", label: "Erase" },
  { tool: "rect-select", label: "Select" },
  { tool: "rect-fill", label: "Rectangle fill" },
];

function tbtn(active: boolean): React.CSSProperties {
  return {
    padding: "0.35rem 0.6rem",
    border: "1px solid var(--rule)",
    borderRadius: "2px",
    background: active ? "var(--ink)" : "var(--paper)",
    color: active ? "var(--paper)" : "var(--ink)",
  };
}

export default function Toolbar({ state, dispatch, onApply, applying }: Props) {
  const hasSelection = !!state.selection;

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", alignItems: "center", padding: "0.5rem 0" }}>
      {TOOLS.map(({ tool, label }) => (
        <button key={tool} style={tbtn(state.tool === tool)} onClick={() => dispatch({ type: "SET_TOOL", tool })}>
          {label}
        </button>
      ))}

      <span className="mono" style={{ fontSize: "0.68rem", color: "var(--ink60)", marginLeft: "0.4rem" }}>
        Brush
      </span>
      <input
        type="range"
        min={1}
        max={6}
        value={state.brush}
        onChange={(e) => dispatch({ type: "SET_BRUSH", brush: Number(e.target.value) })}
      />
      <span className="mono" style={{ fontSize: "0.68rem", width: "1.2em" }}>
        {state.brush}
      </span>

      <span style={{ width: "1px", height: "1.4rem", background: "var(--rule)", margin: "0 0.3rem" }} />

      {state.tool === "rect-select" && (
        <>
          <button
            style={tbtn(false)}
            disabled={!hasSelection}
            onClick={() => {
              if (!state.selection) return;
              const diff = rectCells(state, state.selection, state.material);
              dispatch({ type: "COMMIT", diff });
              dispatch({ type: "SET_SELECTION", selection: null });
            }}
          >
            Fill selection
          </button>
          <button
            style={tbtn(false)}
            disabled={!hasSelection}
            onClick={() => {
              if (!state.selection) return;
              const diff = rectCells(state, state.selection, state.defaultMaterial);
              dispatch({ type: "COMMIT", diff });
              dispatch({ type: "SET_SELECTION", selection: null });
            }}
          >
            Clear selection
          </button>
        </>
      )}

      <button style={tbtn(false)} disabled={state.history.past.length === 0} onClick={() => dispatch({ type: "UNDO" })}>
        ↶ Undo
      </button>
      <button style={tbtn(false)} disabled={state.history.future.length === 0} onClick={() => dispatch({ type: "REDO" })}>
        ↷ Redo
      </button>

      <span style={{ width: "1px", height: "1.4rem", background: "var(--rule)", margin: "0 0.3rem" }} />

      <button style={tbtn(false)} onClick={() => dispatch({ type: "CLEAR" })}>
        Clear to blank
      </button>
      <button
        style={tbtn(false)}
        onClick={() => {
          if (confirm("Restore the entire area to its existing condition? This can be undone.")) {
            dispatch({ type: "RESET_ENVIRONMENT" });
          }
        }}
      >
        Reset environment
      </button>

      <span style={{ flex: 1 }} />

      <button
        style={{ ...tbtn(true), padding: "0.4rem 0.9rem" }}
        onClick={onApply}
        disabled={applying}
      >
        {applying ? "Simulating…" : "Apply Changes & Generate Heatmap"}
      </button>
    </div>
  );
}
