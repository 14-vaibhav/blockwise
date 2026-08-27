import type {
  Field,
  Grid,
  Mask,
  MaterialsResponse,
  SimResult,
  SiteRequest,
  SiteResponse,
} from "../types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function getMaterials(): Promise<MaterialsResponse> {
  return fetch("/api/materials").then((res) => json<MaterialsResponse>(res));
}

export function getQuickLocations(): Promise<Record<string, { lat: number; lon: number }>> {
  return fetch("/api/locations/quick").then((res) => json<Record<string, { lat: number; lon: number }>>(res));
}

export function geocode(query: string): Promise<{ lat: number; lon: number; display_name: string }> {
  return fetch("/api/geocode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  }).then((res) => json<{ lat: number; lon: number; display_name: string }>(res));
}

export function fetchSite(req: SiteRequest): Promise<SiteResponse> {
  return fetch("/api/site", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  }).then((res) => json<SiteResponse>(res));
}

export function simulate(
  grid: Grid,
  baselineGrid: Grid,
  measuredField: Field,
  mask: Mask,
): Promise<SimResult> {
  return fetch("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grid,
      baseline_grid: baselineGrid,
      measured_field: measuredField,
      mask,
    }),
  }).then((res) => json<SimResult>(res));
}
