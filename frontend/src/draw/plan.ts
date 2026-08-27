// Ported from plandraw.py's plan_figure: draws the grid as an architect's
// plan rather than a heatmap. Ground tone per material, then buildings /
// water / canopy as distinct shapes on top - kept in one place so the
// materials view always matches plandraw.py's Streamlit rendering rules.
import type { Grid, Mask, MaterialDef } from "../types";

export const GROUND: Record<string, string> = {
  tree_dense: "#CFD9C4",
  tree_scattered: "#D6DDCB",
  grass: "#DCE2CE",
  shrub: "#D3DAC6",
  bare_soil: "#DED6C8",
  water: "#C6D5DE",
  wetland: "#CBDBD9",
  asphalt: "#BCBDB8",
  concrete: "#D2D3CE",
  light_paving: "#E2E3DE",
  permeable: "#D6D2C8",
  gravel: "#DAD6CC",
  parking_treed: "#C7CCC2",
  building_dark: "#B0AAA4",
  building_light: "#C3BDB6",
  building_cool: "#E4E4E2",
  building_green: "#BFC9B2",
  building_tall: "#A29C97",
};

export const CANOPY: Record<string, string> = {
  tree_dense: "#2F5D31",
  tree_scattered: "#4A7A45",
  parking_treed: "#4A7A45",
  shrub: "#6B8A55",
  building_green: "#5C7A46",
  wetland: "#4E8078",
};

export const TREE_R: Record<string, number> = {
  tree_dense: 0.34,
  tree_scattered: 0.2,
  parking_treed: 0.16,
  shrub: 0.13,
  wetland: 0.1,
  building_green: 0,
};

/** Draws one cell's ground wash + any drawn shapes into a cellSize x cellSize box. */
export function drawCell(
  ctx: CanvasRenderingContext2D,
  material: string,
  materials: Record<string, MaterialDef>,
  x: number,
  y: number,
  cellSize: number,
  ink: string,
  paper: string,
) {
  const cx = x + cellSize / 2;
  const cy = y + cellSize / 2;

  ctx.fillStyle = GROUND[material] ?? "#D2D3CE";
  ctx.fillRect(x, y, cellSize, cellSize);

  if (material.startsWith("building")) {
    const def = materials[material];
    const tall = (def?.height_m ?? 8) >= 20;
    const inset = (tall ? 0.06 : 0.1) * cellSize;
    ctx.fillStyle = def?.colour ?? "#3e2723";
    ctx.strokeStyle = ink;
    ctx.lineWidth = 0.8;
    ctx.fillRect(x + inset, y + inset, cellSize - 2 * inset, cellSize - 2 * inset);
    ctx.strokeRect(x + inset, y + inset, cellSize - 2 * inset, cellSize - 2 * inset);
    ctx.strokeStyle = tall ? "#6E6862" : paper;
    ctx.lineWidth = 0.7;
    ctx.beginPath();
    ctx.moveTo(x + inset, cy);
    ctx.lineTo(x + cellSize - inset, cy);
    ctx.stroke();
    return;
  }

  if (material === "water" || material === "wetland") {
    const def = materials[material];
    ctx.fillStyle = def?.colour ?? "#1976d2";
    ctx.fillRect(x, y, cellSize, cellSize);
    ctx.strokeStyle = "#0F3D52";
    ctx.lineWidth = 0.7;
    ctx.strokeRect(x, y, cellSize, cellSize);
  }

  const rad = (TREE_R[material] ?? 0) * cellSize;
  if (rad > 0) {
    const col = CANOPY[material] ?? "#2F5D31";
    ctx.fillStyle = col;
    ctx.strokeStyle = ink;
    ctx.lineWidth = 0.5;
    const crown = (dx: number, dy: number, k: number) => {
      ctx.beginPath();
      ctx.arc(cx + dx * cellSize, cy + dy * cellSize, rad * k, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    };
    if (material === "tree_dense") {
      crown(-0.16, 0.1, 0.62);
      crown(0.17, 0.13, 0.55);
      crown(0, -0.14, 1.0);
    } else if (material === "parking_treed") {
      crown(-0.22, -0.18, 1.0);
      crown(0.22, 0.2, 1.0);
    } else {
      crown(0, 0, 1.0);
    }
  }
}

export function drawPlan(
  canvas: HTMLCanvasElement,
  grid: Grid,
  mask: Mask,
  materials: Record<string, MaterialDef>,
  paper: string,
  ink: string,
  rule: string,
) {
  const rows = grid.length;
  const cols = rows > 0 ? grid[0].length : 0;
  const ctx = canvas.getContext("2d");
  if (!ctx || rows === 0 || cols === 0) return;

  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth;
  const cssH = canvas.clientHeight;
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const cell = Math.min(cssW / cols, cssH / rows);
  const offX = (cssW - cell * cols) / 2;
  const offY = (cssH - cell * rows) / 2;

  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, cssW, cssH);

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (mask && !mask[r][c]) continue;
      drawCell(ctx, grid[r][c], materials, offX + c * cell, offY + r * cell, cell, ink, paper);
    }
  }

  // Hairline registration rules between every cell (DESIGN.md's "planning
  // drawing" vernacular) - without these, a freshly-loaded all-one-material
  // grid is indistinguishable from empty space. Drawn per masked cell rather
  // than as full-width/height lines so a circle/polygon selection's real
  // boundary shows, not its square bounding box.
  ctx.strokeStyle = rule;
  ctx.lineWidth = 0.6;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (mask && !mask[r][c]) continue;
      ctx.strokeRect(offX + c * cell, offY + r * cell, cell, cell);
    }
  }

  ctx.strokeStyle = ink;
  ctx.lineWidth = 1.4;
  ctx.strokeRect(offX, offY, cell * cols, cell * rows);

  return { cell, offX, offY };
}

/** Screen (x, y) within the canvas -> grid (row, col), or null if outside. */
export function pickCell(
  canvas: HTMLCanvasElement,
  rows: number,
  cols: number,
  clientX: number,
  clientY: number,
): { r: number; c: number } | null {
  const rect = canvas.getBoundingClientRect();
  const cssW = rect.width;
  const cssH = rect.height;
  const cell = Math.min(cssW / cols, cssH / rows);
  const offX = (cssW - cell * cols) / 2;
  const offY = (cssH - cell * rows) / 2;
  const x = clientX - rect.left - offX;
  const y = clientY - rect.top - offY;
  const c = Math.floor(x / cell);
  const r = Math.floor(y / cell);
  if (r < 0 || r >= rows || c < 0 || c >= cols) return null;
  return { r, c };
}
