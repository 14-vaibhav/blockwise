// Ported from plandraw.py's thermal_figure: the same cool -> paper -> warm
// ramp, so the temperature view matches the Streamlit app's rendering.
import type { Field } from "../types";

function lerp(a: [number, number, number], b: [number, number, number], t: number) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t] as const;
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function thermalColor(t: number, cool: string, paper: string, warm: string): string {
  const c = hexToRgb(cool);
  const p = hexToRgb(paper);
  const w = hexToRgb(warm);
  const [r, g, b] = t <= 0.45 ? lerp(c, p, t / 0.45) : lerp(p, w, (t - 0.45) / 0.55);
  return `rgb(${r | 0}, ${g | 0}, ${b | 0})`;
}

export function drawThermal(
  canvas: HTMLCanvasElement,
  field: Field,
  paper: string,
  ink: string,
  cool: string,
  warm: string,
) {
  const rows = field.length;
  const cols = rows > 0 ? field[0].length : 0;
  const ctx = canvas.getContext("2d");
  if (!ctx || rows === 0 || cols === 0) return null;

  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth;
  const cssH = canvas.clientHeight;
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const values = field.flat().filter((v): v is number => v !== null);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const span = max - min || 1;

  const cell = Math.min(cssW / cols, cssH / rows);
  const offX = (cssW - cell * cols) / 2;
  const offY = (cssH - cell * rows) / 2;

  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, cssW, cssH);

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = field[r][c];
      if (v === null) continue;
      ctx.fillStyle = thermalColor((v - min) / span, cool, paper, warm);
      ctx.fillRect(offX + c * cell, offY + r * cell, cell, cell);
    }
  }

  ctx.strokeStyle = ink;
  ctx.lineWidth = 1.4;
  ctx.strokeRect(offX, offY, cell * cols, cell * rows);

  return { cell, offX, offY, min, max };
}
