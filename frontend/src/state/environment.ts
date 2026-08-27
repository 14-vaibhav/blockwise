import type { Field, Grid, Mask, SimResult } from "../types";

export type Tool = "paint" | "erase" | "rect-select" | "rect-fill";
export type ViewMode = "materials" | "temperature";

export interface CellChange {
  r: number;
  c: number;
  from: string;
  to: string;
}
export type Diff = CellChange[];

export interface RectSelection {
  r0: number;
  c0: number;
  r1: number;
  c1: number;
}

export interface EnvironmentState {
  rows: number;
  cols: number;
  mask: Mask;
  baselineGrid: Grid;
  grid: Grid;
  measuredField: Field;
  defaultMaterial: string;
  history: { past: Diff[]; future: Diff[] };
  tool: Tool;
  material: string;
  brush: number;
  selection: RectSelection | null;
  view: ViewMode;
  liveResult: SimResult | null;
  originalResult: SimResult | null;
  appliedResult: SimResult | null;
  appliedGrid: Grid | null;
}

export function initialState(defaultMaterial: string): EnvironmentState {
  return {
    rows: 0,
    cols: 0,
    mask: null,
    baselineGrid: [],
    grid: [],
    measuredField: [],
    defaultMaterial,
    history: { past: [], future: [] },
    tool: "paint",
    material: defaultMaterial,
    brush: 2,
    selection: null,
    view: "materials",
    liveResult: null,
    originalResult: null,
    appliedResult: null,
    appliedGrid: null,
  };
}

export type Action =
  | {
      type: "LOAD_SITE";
      rows: number;
      cols: number;
      mask: Mask;
      baselineGrid: Grid;
      grid: Grid;
      measuredField: Field;
    }
  | { type: "SET_TOOL"; tool: Tool }
  | { type: "SET_MATERIAL"; material: string }
  | { type: "SET_BRUSH"; brush: number }
  | { type: "SET_VIEW"; view: ViewMode }
  | { type: "SET_SELECTION"; selection: RectSelection | null }
  | { type: "APPLY_LIVE"; cells: CellChange[] }
  | { type: "COMMIT"; diff: Diff }
  | { type: "UNDO" }
  | { type: "REDO" }
  | { type: "CLEAR" }
  | { type: "RESET_ENVIRONMENT" }
  | { type: "SET_LIVE_RESULT"; result: SimResult }
  | { type: "SET_ORIGINAL_RESULT"; result: SimResult }
  | { type: "APPLY_CHANGES"; result: SimResult; grid: Grid };

export function cloneGrid(grid: Grid): Grid {
  return grid.map((row) => row.slice());
}

function applyDiffToGrid(grid: Grid, diff: Diff, direction: "to" | "from"): Grid {
  if (diff.length === 0) return grid;
  const next = cloneGrid(grid);
  for (const change of diff) {
    next[change.r][change.c] = direction === "to" ? change.to : change.from;
  }
  return next;
}

/** Brush footprint around (r, c), clamped to the grid and the selection mask. */
export function brushCells(
  state: Pick<EnvironmentState, "grid" | "mask" | "rows" | "cols">,
  r: number,
  c: number,
  brush: number,
  material: string,
): CellChange[] {
  const half = Math.floor((brush - 1) / 2);
  const r0 = Math.max(0, r - half);
  const r1 = Math.min(state.rows, r + Math.ceil((brush - 1) / 2) + 1);
  const c0 = Math.max(0, c - half);
  const c1 = Math.min(state.cols, c + Math.ceil((brush - 1) / 2) + 1);

  const cells: CellChange[] = [];
  for (let rr = r0; rr < r1; rr++) {
    for (let cc = c0; cc < c1; cc++) {
      if (state.mask && !state.mask[rr][cc]) continue;
      const from = state.grid[rr][cc];
      if (from === material) continue;
      cells.push({ r: rr, c: cc, from, to: material });
    }
  }
  return cells;
}

/** Rectangle fill/clear/reset, all built the same way: cells that actually change. */
export function rectCells(
  state: Pick<EnvironmentState, "grid" | "mask">,
  sel: RectSelection,
  material: string,
): CellChange[] {
  const r0 = Math.min(sel.r0, sel.r1);
  const r1 = Math.max(sel.r0, sel.r1);
  const c0 = Math.min(sel.c0, sel.c1);
  const c1 = Math.max(sel.c0, sel.c1);
  const cells: CellChange[] = [];
  for (let r = r0; r <= r1; r++) {
    for (let c = c0; c <= c1; c++) {
      if (state.mask && !state.mask[r][c]) continue;
      const from = state.grid[r][c];
      if (from === material) continue;
      cells.push({ r, c, from, to: material });
    }
  }
  return cells;
}

/** Every cell where `from` and `to` differ, respecting mask. Used both for
 * RESET_ENVIRONMENT (from=current grid, to=baseline) and by GridCanvas to
 * turn a whole drag stroke into one undo entry (from=grid at pointerdown,
 * to=grid at pointerup). */
export function diffGrids(from: Grid, to: Grid, mask: Mask): Diff {
  const cells: Diff = [];
  for (let r = 0; r < from.length; r++) {
    for (let c = 0; c < from[r].length; c++) {
      if (mask && !mask[r][c]) continue;
      if (from[r][c] !== to[r][c]) cells.push({ r, c, from: from[r][c], to: to[r][c] });
    }
  }
  return cells;
}

function diffToTarget(state: Pick<EnvironmentState, "grid" | "mask">, target: Grid): Diff {
  return diffGrids(state.grid, target, state.mask);
}

export function environmentReducer(
  state: EnvironmentState,
  action: Action,
): EnvironmentState {
  switch (action.type) {
    case "LOAD_SITE":
      return {
        ...state,
        rows: action.rows,
        cols: action.cols,
        mask: action.mask,
        baselineGrid: action.baselineGrid,
        grid: action.grid,
        measuredField: action.measuredField,
        history: { past: [], future: [] },
        selection: null,
        liveResult: null,
        originalResult: null,
        appliedResult: null,
      };

    case "SET_TOOL":
      return { ...state, tool: action.tool, selection: null };

    case "SET_MATERIAL":
      return { ...state, material: action.material };

    case "SET_BRUSH":
      return { ...state, brush: action.brush };

    case "SET_VIEW":
      return { ...state, view: action.view };

    case "SET_SELECTION":
      return { ...state, selection: action.selection };

    // Optimistic paint during a drag: updates the grid so it redraws
    // instantly, but does NOT touch history - the stroke commits as one
    // undo entry on pointerup (see COMMIT).
    case "APPLY_LIVE":
      return { ...state, grid: applyDiffToGrid(state.grid, action.cells, "to") };

    case "COMMIT": {
      if (action.diff.length === 0) return state;
      return {
        ...state,
        grid: applyDiffToGrid(state.grid, action.diff, "to"),
        history: { past: [...state.history.past, action.diff], future: [] },
      };
    }

    case "UNDO": {
      const { past, future } = state.history;
      if (past.length === 0) return state;
      const diff = past[past.length - 1];
      return {
        ...state,
        grid: applyDiffToGrid(state.grid, diff, "from"),
        history: { past: past.slice(0, -1), future: [diff, ...future] },
      };
    }

    case "REDO": {
      const { past, future } = state.history;
      if (future.length === 0) return state;
      const diff = future[0];
      return {
        ...state,
        grid: applyDiffToGrid(state.grid, diff, "to"),
        history: { past: [...past, diff], future: future.slice(1) },
      };
    }

    case "CLEAR": {
      const diff = rectCells(
        state,
        { r0: 0, c0: 0, r1: state.rows - 1, c1: state.cols - 1 },
        state.defaultMaterial,
      );
      if (diff.length === 0) return state;
      return {
        ...state,
        grid: applyDiffToGrid(state.grid, diff, "to"),
        history: { past: [...state.history.past, diff], future: [] },
      };
    }

    case "RESET_ENVIRONMENT": {
      const diff = diffToTarget(state, state.baselineGrid);
      if (diff.length === 0) return state;
      return {
        ...state,
        grid: applyDiffToGrid(state.grid, diff, "to"),
        history: { past: [...state.history.past, diff], future: [] },
      };
    }

    case "SET_LIVE_RESULT":
      return { ...state, liveResult: action.result };

    case "SET_ORIGINAL_RESULT":
      return { ...state, originalResult: action.result };

    case "APPLY_CHANGES":
      return { ...state, appliedResult: action.result, appliedGrid: action.grid, view: "temperature" };

    default:
      return state;
  }
}
