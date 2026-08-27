"""
Blockwise API - HTTP wrapper around the existing pure-Python modules, AND
(once frontend/dist exists) the server for the whole app on one origin.

This file adds NO new physics or data-fetching logic: every endpoint is a
thin translation layer over engine.py / fgdata.py / sandbox.py / osmdata.py,
the same modules app.py and app_studio.py already use. That is deliberate -
the guarantee that the web editor's numbers match the Streamlit app's
numbers comes from calling the exact same functions, not from re-deriving
them. The Streamlit apps are no longer run alongside this one; this process
is the single place the whole thing lives.

To run the real, single-origin app (build once, then just this process):
    cd frontend && npm install && npm run build && cd ..
    uvicorn api:app --port 8000
    open http://localhost:8000

For frontend development with hot reload, `npm run dev` in frontend/ still
works against this same api.py on :8000 (see frontend/vite.config.ts's
proxy) - that two-process setup is a dev convenience only, never what a
user runs.
"""

import math
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import engine as E
import fgdata
import osmdata
import sandbox as S

app = FastAPI(title="Blockwise API")

# Harmless with static-file serving added below (same-origin already, no
# CORS needed for it) - kept only so /api/* is still reachable directly
# (a notebook, curl, etc.) without a browser CORS error.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _clean(arr):
    """numpy array -> nested lists, with NaN/Inf -> None (JSON has no NaN)."""
    a = np.asarray(arr, dtype=float)
    a = np.where(np.isfinite(a), a, np.nan)
    out = a.astype(object)
    out[np.isnan(a)] = None
    return out.tolist()


def _grid_from(rows) -> np.ndarray:
    return np.array(rows, dtype=object)


def _mask_from(rows) -> Optional[np.ndarray]:
    return np.array(rows, dtype=bool) if rows is not None else None


def _field_from(rows) -> np.ndarray:
    """2D list of float | None -> float ndarray, None -> NaN."""
    return np.array(
        [[np.nan if v is None else float(v) for v in row] for row in rows],
        dtype=float,
    )


def _check_material_keys(grid: np.ndarray, field_name: str):
    bad = sorted({str(k) for k in np.unique(grid)} - set(E.MATERIALS))
    if bad:
        raise HTTPException(400, f"{field_name} has unknown material keys: {bad}")


def _check_shapes(*named: tuple[str, np.ndarray]):
    (n0, a0), rest = named[0], named[1:]
    for name, a in rest:
        if a.shape != a0.shape:
            raise HTTPException(
                400, f"{name} shape {a.shape} does not match {n0} shape {a0.shape}")


# ------------------------------------------------------------- materials

@app.get("/api/materials")
def materials():
    """
    The single source of truth for material physics + presentation. The
    frontend never hardcodes a material's color, group or coefficients -
    it reads them from here, same as engine.py is the only place that
    computes temperature.
    """
    mats = {}
    for key, m in E.MATERIALS.items():
        mats[key] = {**m, "warning": E.WARNINGS.get(key)}

    def coeff(c: E.Coeff):
        return {"central": c.central, "low": c.low, "high": c.high,
                "status": c.status, "confidence": c.confidence}

    return {
        "materials": mats,
        "palette": {group: [{"key": k, "label": lbl, "colour": col}
                             for k, lbl, col in items]
                    for group, items in E.palette().items()},
        "default_material": E.DEFAULT_MATERIAL,
        "cell_m": E.CELL_M,
        # Mechanism-level coefficients (not per-material) - each carries the
        # status labels engine.py's hard rule #2 requires stay visible.
        "coefficients": {
            "canopy_per_pp": coeff(E.CANOPY_PER_PP),
            "canopy_per_pp_above_threshold": coeff(E.CANOPY_PER_PP_ABOVE),
            "canopy_threshold_pp": E.CANOPY_THRESHOLD_PP,
            "albedo_per_0p1": coeff(E.ALBEDO_PER_0P1),
            "impervious_per_pp": coeff(E.IMPERVIOUS_PER_PP),
            "grass_per_pp": coeff(E.GRASS_PER_PP),
            "water_per_cell": coeff(E.WATER_PER_CELL),
            "building_per_pp": coeff(E.BUILDING_PER_PP),
            "max_cooling_c": E.MAX_COOLING_C,
        },
    }


@app.get("/api/locations/quick")
def quick_locations():
    return {name: {"lat": lat, "lon": lon}
            for name, (lat, lon) in fgdata.LOCATIONS.items()}


# ------------------------------------------------------------------ geocode

class GeocodeRequest(BaseModel):
    query: str


@app.post("/api/geocode")
def geocode(req: GeocodeRequest):
    hit = fgdata.geocode_us(req.query)
    if hit is None:
        raise HTTPException(404, f'No US match for "{req.query}".')
    lat, lon, display_name = hit
    return {"lat": lat, "lon": lon, "display_name": display_name}


# --------------------------------------------------------------------- site

class SiteRequest(BaseModel):
    location_name: str
    lat: float
    lon: float
    shape: Literal["square", "circle", "polygon"]
    size_m: Optional[float] = Field(default=None, gt=0)
    polygon_ring: Optional[list[list[float]]] = None   # [[lon, lat], ...]
    granularity: Literal[60, 80, 100] = 100
    existing_condition: Literal["blank", "osm"] = "blank"
    date: Optional[str] = None


@app.post("/api/site")
def site(req: SiteRequest):
    date = req.date or fgdata.previous_day()

    if req.shape == "square":
        if not req.size_m:
            raise HTTPException(400, "size_m is required for shape=square")
        aoi = fgdata.square_aoi(req.lat, req.lon, req.size_m)
        shape_label = f"{req.size_m:.0f}m_square"
        grid, mask, cw, ch = S.square_grid(req.size_m)
    elif req.shape == "circle":
        if not req.size_m:
            raise HTTPException(400, "size_m (radius) is required for shape=circle")
        aoi = fgdata.circle_aoi(req.lat, req.lon, req.size_m)
        shape_label = f"{req.size_m:.0f}m_circle"
        grid, mask, cw, ch = S.circle_grid(req.size_m)
    else:
        if not req.polygon_ring or len(req.polygon_ring) < 3:
            raise HTTPException(400, "polygon_ring needs at least 3 points")
        aoi = fgdata.polygon_aoi(req.polygon_ring)
        shape_label = f"polygon_{abs(hash(tuple(map(tuple, req.polygon_ring)))) % 100000}"
        grid, mask, cw, ch = S.polygon_grid(req.polygon_ring)

    if req.existing_condition == "osm" and req.shape != "square":
        raise HTTPException(
            400, "existing_condition=osm is only supported for shape=square "
                 "(osmdata.rasterise assumes a square bounding box)")

    try:
        data = fgdata.get_plot(req.location_name, aoi, shape_label,
                                date=date, granularity=req.granularity)
    except Exception as exc:
        raise HTTPException(502, f"FortyGuard fetch failed: {exc}") from exc

    if not data:
        raise HTTPException(
            404, "FortyGuard has no measurements for this area on this day.")

    rows, cols = grid.shape
    y, x = np.mgrid[0:rows, 0:cols]
    denom = max(1, (rows - 1) + (cols - 1))
    ramp = (x + y) / denom - 0.5
    measured_field = data["peak_c"] + ramp * data.get("peak_spread", 0.0)

    site_stats = None
    baseline_grid = grid.copy()
    if req.existing_condition == "osm":
        try:
            osm_grid, site_stats = osmdata.get_site(
                req.location_name, req.lat, req.lon, size_m=req.size_m)
        except Exception as exc:
            raise HTTPException(502, f"OpenStreetMap fetch failed: {exc}") from exc
        # osmdata rasterises onto its own engine.GRID_N x GRID_N grid;
        # resample onto this request's grid resolution by nearest lookup so
        # the OSM baseline still matches the editable grid's cell count.
        on = osm_grid.shape[0]
        ry = (np.arange(rows) * on // max(1, rows)).clip(0, on - 1)
        rx = (np.arange(cols) * on // max(1, cols)).clip(0, on - 1)
        baseline_grid = osm_grid[np.ix_(ry, rx)]

    return {
        "rows": rows, "cols": cols, "cell_w": cw, "cell_h": ch,
        "grid": baseline_grid.tolist(),
        "baseline_grid": baseline_grid.tolist(),
        "mask": mask.tolist(),
        "measured_field": _clean(measured_field),
        "data": {k: v for k, v in data.items()
                 if k in ("peak_c", "low_c", "daily_mean_c", "n_tiles",
                          "peak_spread", "peak_range", "date")},
        "location_name": data.get("location", req.location_name),
        "site_stats": site_stats,
    }


# --------------------------------------------------------------- simulate

class SimulateRequest(BaseModel):
    grid: list[list[str]]
    baseline_grid: list[list[str]]
    measured_field: list[list[Optional[float]]]
    mask: Optional[list[list[bool]]] = None


@app.post("/api/simulate")
def simulate(req: SimulateRequest):
    grid = _grid_from(req.grid)
    baseline_grid = _grid_from(req.baseline_grid)
    measured_field = _field_from(req.measured_field)
    mask = _mask_from(req.mask)

    _check_shapes(("grid", grid), ("baseline_grid", baseline_grid),
                  ("measured_field", measured_field),
                  *([("mask", mask)] if mask is not None else []))
    _check_material_keys(grid, "grid")
    _check_material_keys(baseline_grid, "baseline_grid")

    result = E.evaluate(grid, baseline_grid, measured_field, mask=mask)

    def comp(c: E.Composition):
        return {"canopy_pp": c.canopy_pp, "impervious_pp": c.impervious_pp,
                "building_pp": c.building_pp, "grass_pp": c.grass_pp,
                "mean_albedo": c.mean_albedo, "water_cells": c.water_cells,
                "tree_count": c.tree_count}

    return {
        "measured_c": result.measured_c,
        "delta_c": result.delta_c,
        "delta_low": result.delta_low,
        "delta_high": result.delta_high,
        "projected_c": result.projected_c,
        "breakdown": result.breakdown,
        "mrt_delta": result.mrt_delta,
        "clamped": result.clamped,
        "notes": result.notes,
        "now": comp(result.now),
        "base": comp(result.base),
        "measured_field": _clean(result.measured_field),
        "delta_field": _clean(result.delta_field),
        "projected_field": _clean(result.projected_field),
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------- static frontend
#
# Mounted LAST and at "/" so every /api/* route above still takes priority.
# html=True serves frontend/dist/index.html for "/" and for any other path
# that isn't a real file in dist/ - the app has no client-side routes beyond
# "/", so that's just the SPA shell, not a router fallback.
_DIST = Path(__file__).parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
