// Mirrors api.py's response shapes exactly - this file has no logic of its
// own, only the types the backend actually returns. If a field isn't here,
// the frontend must not invent it.

export interface MaterialDef {
  label: string;
  group: string;
  colour: string;
  canopy: number;
  impervious: number;
  albedo: number;
  grass?: number;
  water?: number;
  building?: number;
  height_m?: number;
  trees?: number;
  warning?: string | null;
}

export interface Coeff {
  central: number;
  low: number;
  high: number;
  status: "literature_central" | "engineering_value" | "calibration_parameter";
  confidence: string;
}

export interface MaterialsResponse {
  materials: Record<string, MaterialDef>;
  palette: Record<string, { key: string; label: string; colour: string }[]>;
  default_material: string;
  cell_m: number;
  coefficients: {
    canopy_per_pp: Coeff;
    canopy_per_pp_above_threshold: Coeff;
    canopy_threshold_pp: number;
    albedo_per_0p1: Coeff;
    impervious_per_pp: Coeff;
    grass_per_pp: Coeff;
    water_per_cell: Coeff;
    building_per_pp: Coeff;
    max_cooling_c: number;
  };
}

export type Grid = string[][];
export type Mask = boolean[][] | null;
export type Field = (number | null)[][];

export type Shape = "square" | "circle" | "polygon";

export interface SiteRequest {
  location_name: string;
  lat: number;
  lon: number;
  shape: Shape;
  size_m?: number;
  polygon_ring?: [number, number][];
  granularity?: 60 | 80 | 100;
  existing_condition?: "blank" | "osm";
  date?: string;
}

export interface SiteResponse {
  rows: number;
  cols: number;
  cell_w: number;
  cell_h: number;
  grid: Grid;
  baseline_grid: Grid;
  mask: boolean[][];
  measured_field: Field;
  data: {
    peak_c: number;
    low_c: number;
    daily_mean_c: number;
    n_tiles: number;
    peak_spread: number;
    peak_range: [number, number];
    date: string;
  };
  location_name: string;
  site_stats: { n_ways: number; n_buildings: number; source: string } | null;
}

export interface Composition {
  canopy_pp: number;
  impervious_pp: number;
  building_pp: number;
  grass_pp: number;
  mean_albedo: number;
  water_cells: number;
  tree_count: number;
}

export interface SimResult {
  measured_c: number;
  delta_c: number;
  delta_low: number;
  delta_high: number;
  projected_c: number;
  breakdown: Record<string, number>;
  mrt_delta: number;
  clamped: boolean;
  notes: string[];
  now: Composition;
  base: Composition;
  measured_field: Field;
  delta_field: Field;
  projected_field: Field;
}
