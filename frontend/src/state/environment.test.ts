import { describe, expect, it } from "vitest";
import {
  brushCells,
  environmentReducer,
  initialState,
  rectCells,
  type EnvironmentState,
} from "./environment";

function loaded(n = 4): EnvironmentState {
  const grid = Array.from({ length: n }, () => Array(n).fill("grass"));
  const baseline = grid.map((row) => row.slice());
  const mask = Array.from({ length: n }, () => Array(n).fill(true));
  const measuredField = Array.from({ length: n }, () => Array(n).fill(30));
  return environmentReducer(initialState("grass"), {
    type: "LOAD_SITE",
    rows: n,
    cols: n,
    mask,
    baselineGrid: baseline,
    grid,
    measuredField,
  });
}

describe("brushCells", () => {
  it("paints a square footprint clamped to the grid", () => {
    const state = loaded(4);
    const cells = brushCells(state, 0, 0, 3, "tree_dense");
    // brush 3 centred on (0,0) clamped to the top-left corner -> a 2x2 block
    const coords = cells.map((c) => `${c.r},${c.c}`).sort();
    expect(coords).toEqual(["0,0", "0,1", "1,0", "1,1"]);
    expect(cells.every((c) => c.to === "tree_dense" && c.from === "grass")).toBe(true);
  });

  it("skips cells outside the mask", () => {
    const state = loaded(3);
    state.mask![1][1] = false;
    const cells = brushCells(state, 1, 1, 1, "water");
    expect(cells).toEqual([]);
  });

  it("skips cells already at the target material", () => {
    const state = loaded(3);
    const cells = brushCells(state, 1, 1, 1, "grass");
    expect(cells).toEqual([]);
  });
});

describe("rectCells", () => {
  it("normalises reversed corners and fills the rectangle", () => {
    const state = loaded(4);
    const cells = rectCells(state, { r0: 2, c0: 2, r1: 0, c1: 0 }, "asphalt");
    expect(cells).toHaveLength(9); // 3x3 block from (0,0) to (2,2)
  });
});

describe("environmentReducer paint/erase via COMMIT", () => {
  it("commits a diff, updates the grid, and records history", () => {
    let state = loaded(3);
    const diff = brushCells(state, 1, 1, 1, "tree_dense");
    state = environmentReducer(state, { type: "COMMIT", diff });
    expect(state.grid[1][1]).toBe("tree_dense");
    expect(state.history.past).toHaveLength(1);
    expect(state.history.future).toHaveLength(0);
  });

  it("erase (paint default material) reverts a cell", () => {
    let state = loaded(3);
    state = environmentReducer(state, {
      type: "COMMIT",
      diff: brushCells(state, 0, 0, 1, "water"),
    });
    expect(state.grid[0][0]).toBe("water");
    state = environmentReducer(state, {
      type: "COMMIT",
      diff: brushCells(state, 0, 0, 1, state.defaultMaterial),
    });
    expect(state.grid[0][0]).toBe("grass");
  });

  it("an empty diff (no-op paint) does not push history", () => {
    let state = loaded(3);
    state = environmentReducer(state, { type: "COMMIT", diff: [] });
    expect(state.history.past).toHaveLength(0);
  });
});

describe("environmentReducer rectangle fill", () => {
  it("fills a rectangle as a single history entry", () => {
    let state = loaded(4);
    const diff = rectCells(state, { r0: 0, c0: 0, r1: 1, c1: 1 }, "concrete");
    state = environmentReducer(state, { type: "COMMIT", diff });
    expect(state.grid[0][0]).toBe("concrete");
    expect(state.grid[1][1]).toBe("concrete");
    expect(state.grid[2][2]).toBe("grass");
    expect(state.history.past).toHaveLength(1);
  });
});

describe("environmentReducer clear / reset", () => {
  it("CLEAR paints every masked cell to the default material", () => {
    let state = loaded(3);
    state = environmentReducer(state, {
      type: "COMMIT",
      diff: rectCells(state, { r0: 0, c0: 0, r1: 2, c1: 2 }, "asphalt"),
    });
    state = environmentReducer(state, { type: "CLEAR" });
    expect(state.grid.flat().every((m) => m === "grass")).toBe(true);
  });

  it("RESET_ENVIRONMENT restores the baseline grid exactly", () => {
    let state = loaded(3);
    state.baselineGrid[1][1] = "building_dark"; // simulate a real (OSM) baseline
    state = environmentReducer(state, {
      type: "COMMIT",
      diff: brushCells(state, 0, 0, 1, "water"),
    });
    state = environmentReducer(state, { type: "RESET_ENVIRONMENT" });
    expect(state.grid).toEqual(state.baselineGrid);
  });
});

describe("environmentReducer undo/redo", () => {
  it("undo reverses the last commit, redo reapplies it", () => {
    let state = loaded(3);
    state = environmentReducer(state, {
      type: "COMMIT",
      diff: brushCells(state, 1, 1, 1, "tree_dense"),
    });
    state = environmentReducer(state, { type: "UNDO" });
    expect(state.grid[1][1]).toBe("grass");
    expect(state.history.past).toHaveLength(0);
    expect(state.history.future).toHaveLength(1);

    state = environmentReducer(state, { type: "REDO" });
    expect(state.grid[1][1]).toBe("tree_dense");
    expect(state.history.past).toHaveLength(1);
    expect(state.history.future).toHaveLength(0);
  });

  it("undo/redo on empty stacks is a no-op", () => {
    const state = loaded(3);
    expect(environmentReducer(state, { type: "UNDO" })).toBe(state);
    expect(environmentReducer(state, { type: "REDO" })).toBe(state);
  });

  it("a new commit after an undo clears the redo stack", () => {
    let state = loaded(3);
    state = environmentReducer(state, {
      type: "COMMIT",
      diff: brushCells(state, 0, 0, 1, "tree_dense"),
    });
    state = environmentReducer(state, { type: "UNDO" });
    state = environmentReducer(state, {
      type: "COMMIT",
      diff: brushCells(state, 2, 2, 1, "water"),
    });
    expect(state.history.future).toHaveLength(0);
    expect(state.grid[0][0]).toBe("grass");
    expect(state.grid[2][2]).toBe("water");
  });
});
