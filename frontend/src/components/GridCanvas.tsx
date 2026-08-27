import { useEffect, useRef, useState, type Dispatch } from "react";
import { drawPlan, pickCell } from "../draw/plan";
import { drawThermal } from "../draw/thermal";
import {
  brushCells,
  cloneGrid,
  diffGrids,
  rectCells,
  type Action,
  type EnvironmentState,
  type RectSelection,
} from "../state/environment";
import type { Grid, MaterialDef } from "../types";

interface Props {
  state: EnvironmentState;
  materials: Record<string, MaterialDef>;
  dispatch: Dispatch<Action>;
  paper: string;
  ink: string;
  rule: string;
  thermalCool: string;
  thermalWarm: string;
}

export default function GridCanvas({
  state,
  materials,
  dispatch,
  paper,
  ink,
  rule,
  thermalCool,
  thermalWarm,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<{ r: number; c: number } | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

  const pointerDown = useRef(false);
  const strokeStart = useRef<Grid | null>(null);
  const rectAnchor = useRef<{ r: number; c: number } | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (state.view === "materials") {
      drawPlan(canvas, state.grid, state.mask, materials, paper, ink, rule);
    } else {
      const field = state.liveResult?.projected_field ?? state.measuredField;
      drawThermal(canvas, field, paper, ink, thermalCool, thermalWarm);
    }
  }, [
    state.grid,
    state.mask,
    state.view,
    state.liveResult,
    state.measuredField,
    materials,
    paper,
    ink,
    rule,
    thermalCool,
    thermalWarm,
  ]);

  // Tracks the canvas's CSS size in state (rather than reading canvasRef
  // during render) so the selection marquee can be positioned without
  // touching a ref outside an effect/handler.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setCanvasSize({ width, height });
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  const targetMaterial = state.tool === "erase" ? state.defaultMaterial : state.material;

  function handlePointerDown(e: React.PointerEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas || state.view !== "materials") return;
    const cell = pickCell(canvas, state.rows, state.cols, e.clientX, e.clientY);
    if (!cell) return;
    canvas.setPointerCapture(e.pointerId);
    pointerDown.current = true;

    if (state.tool === "paint" || state.tool === "erase") {
      strokeStart.current = cloneGrid(state.grid);
      const cells = brushCells(state, cell.r, cell.c, state.brush, targetMaterial);
      if (cells.length) dispatch({ type: "APPLY_LIVE", cells });
    } else {
      rectAnchor.current = cell;
      dispatch({ type: "SET_SELECTION", selection: { r0: cell.r, c0: cell.c, r1: cell.r, c1: cell.c } });
    }
  }

  function handlePointerMove(e: React.PointerEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas || state.view !== "materials") return;
    const cell = pickCell(canvas, state.rows, state.cols, e.clientX, e.clientY);
    setHover(cell);
    if (!pointerDown.current || !cell) return;

    if (state.tool === "paint" || state.tool === "erase") {
      const cells = brushCells(state, cell.r, cell.c, state.brush, targetMaterial);
      if (cells.length) dispatch({ type: "APPLY_LIVE", cells });
    } else if (rectAnchor.current) {
      dispatch({
        type: "SET_SELECTION",
        selection: { r0: rectAnchor.current.r, c0: rectAnchor.current.c, r1: cell.r, c1: cell.c },
      });
    }
  }

  function handlePointerUp() {
    if (!pointerDown.current) return;
    pointerDown.current = false;

    if ((state.tool === "paint" || state.tool === "erase") && strokeStart.current) {
      const diff = diffGrids(strokeStart.current, state.grid, state.mask);
      strokeStart.current = null;
      if (diff.length) dispatch({ type: "COMMIT", diff });
    } else if (state.tool === "rect-fill" && state.selection) {
      const diff = rectCells(state, state.selection, targetMaterial);
      dispatch({ type: "COMMIT", diff });
      dispatch({ type: "SET_SELECTION", selection: null });
    }
    rectAnchor.current = null;
  }

  const sel = normaliseSelection(state.selection);
  const hoverMaterial = hover ? state.grid[hover.r]?.[hover.c] : null;
  const hoverLabel = hoverMaterial ? materials[hoverMaterial]?.label ?? hoverMaterial : null;
  const projectedAtHover =
    hover && state.liveResult?.projected_field ? state.liveResult.projected_field[hover.r]?.[hover.c] : null;
  const baselineAtHover =
    hover && state.originalResult?.projected_field ? state.originalResult.projected_field[hover.r]?.[hover.c] : null;

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={() => setHover(null)}
      />
      {sel && state.view === "materials" && canvasSize.width > 0 && (
        <SelectionOverlay rows={state.rows} cols={state.cols} sel={sel} canvasSize={canvasSize} />
      )}
      {hover && hoverLabel && (
        <div className="hover-info mono">
          <div>
            Location: X:{hover.c} Y:{hover.r}
          </div>
          <div>Material: {hoverLabel}</div>
          {projectedAtHover != null && <div>Projected: {projectedAtHover.toFixed(1)} °C</div>}
          {baselineAtHover != null && projectedAtHover != null && (
            <div>Change: {(projectedAtHover - baselineAtHover >= 0 ? "+" : "") + (projectedAtHover - baselineAtHover).toFixed(1)} °C</div>
          )}
        </div>
      )}
    </div>
  );
}

function normaliseSelection(sel: RectSelection | null) {
  if (!sel) return null;
  return {
    r0: Math.min(sel.r0, sel.r1),
    r1: Math.max(sel.r0, sel.r1),
    c0: Math.min(sel.c0, sel.c1),
    c1: Math.max(sel.c0, sel.c1),
  };
}

function SelectionOverlay({
  rows,
  cols,
  sel,
  canvasSize,
}: {
  rows: number;
  cols: number;
  sel: { r0: number; r1: number; c0: number; c1: number };
  canvasSize: { width: number; height: number };
}) {
  const cssW = canvasSize.width;
  const cssH = canvasSize.height;
  const cell = Math.min(cssW / cols, cssH / rows);
  const offX = (cssW - cell * cols) / 2;
  const offY = (cssH - cell * rows) / 2;
  return (
    <div
      style={{
        position: "absolute",
        left: offX + sel.c0 * cell,
        top: offY + sel.r0 * cell,
        width: (sel.c1 - sel.c0 + 1) * cell,
        height: (sel.r1 - sel.r0 + 1) * cell,
        border: "1.5px dashed var(--modelled)",
        background: "rgba(94,43,84,0.08)",
        pointerEvents: "none",
      }}
    />
  );
}
