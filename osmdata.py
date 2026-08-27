"""
Real land cover from OpenStreetMap.

FortyGuard measures temperature, not materials. So the "what is actually here"
half of the digital twin comes from OSM: building footprints, parks, water,
woods, parking and roads, for any location on earth, free and without a key.

Combined with FortyGuard's measured temperature, that gives a genuine twin -
real geometry AND real heat, both observed rather than assumed.

WHAT THIS IS NOT: OSM knows a building exists, not what its roof is made of.
Roof albedo, paving type and tree species are still assumptions. Say so.
"""

import json
import pathlib
import time

import numpy as np
import requests

import engine as E

OVERPASS = "https://overpass-api.de/api/interpreter"
CACHE = pathlib.Path("cache")

# Overpass's usage policy rejects anonymous requests with no User-Agent
# (HTTP 406). A descriptive one identifying the app is required, not optional.
HEADERS = {"User-Agent": "Blockwise/1.0 (FortyGuard hackathon project)"}

# OSM tag -> Blockwise material. Applied in order: land cover first, then
# parking and roads, then buildings on top. Later wins.
LANDUSE = {
    ("natural", "water"): "water",
    ("natural", "wetland"): "wetland",
    ("natural", "wood"): "tree_dense",
    ("natural", "scrub"): "shrub",
    ("natural", "grassland"): "grass",
    ("natural", "sand"): "bare_soil",
    ("landuse", "forest"): "tree_dense",
    ("landuse", "grass"): "grass",
    ("landuse", "meadow"): "shrub",
    ("landuse", "village_green"): "grass",
    ("landuse", "recreation_ground"): "grass",
    ("landuse", "cemetery"): "grass",
    ("landuse", "brownfield"): "bare_soil",
    ("landuse", "construction"): "bare_soil",
    ("landuse", "industrial"): "concrete",
    ("landuse", "retail"): "concrete",
    ("landuse", "commercial"): "concrete",
    ("landuse", "railway"): "gravel",
    ("leisure", "park"): "grass",
    ("leisure", "garden"): "tree_scattered",
    ("leisure", "pitch"): "grass",
    ("leisure", "golf_course"): "grass",
    ("leisure", "playground"): "concrete",
}

QUERY = """
[out:json][timeout:60];
(
  way["building"]({s},{w},{n},{e});
  way["landuse"]({s},{w},{n},{e});
  way["natural"]({s},{w},{n},{e});
  way["leisure"]({s},{w},{n},{e});
  way["amenity"="parking"]({s},{w},{n},{e});
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|service|unclassified)$"]({s},{w},{n},{e});
);
out geom;
"""


def bbox(lat, lon, size_m):
    d_lat = (size_m / 2) / 111_320
    d_lon = (size_m / 2) / (111_320 * np.cos(np.radians(lat)))
    return lat - d_lat, lon - d_lon, lat + d_lat, lon + d_lon


def fetch_osm(lat, lon, size_m):
    s, w, n, e = bbox(lat, lon, size_m)
    q = QUERY.format(s=s, w=w, n=n, e=e)
    r = requests.post(OVERPASS, data={"data": q}, headers=HEADERS, timeout=90)
    r.raise_for_status()
    return r.json().get("elements", [])


def _inside(poly_lon, poly_lat, X, Y):
    """Vectorised crossing-number point-in-polygon. No shapely dependency."""
    inside = np.zeros(X.shape, dtype=bool)
    n = len(poly_lon)
    j = n - 1
    for i in range(n):
        xi, yi = poly_lon[i], poly_lat[i]
        xj, yj = poly_lon[j], poly_lat[j]
        crosses = ((yi > Y) != (yj > Y)) & (
            X < (xj - xi) * (Y - yi) / (yj - yi + 1e-15) + xi)
        inside ^= crosses
        j = i
    return inside


def _material_for(tags):
    if "building" in tags:
        levels = tags.get("building:levels")
        try:
            if levels and float(levels) >= 6:
                return "building_tall", 3
        except ValueError:
            pass
        return "building_dark", 3
    if tags.get("amenity") == "parking":
        return "asphalt", 2
    if "highway" in tags:
        return "asphalt", 2
    for (k, v), mat in LANDUSE.items():
        if tags.get(k) == v:
            return mat, 1
    if "landuse" in tags or "leisure" in tags:
        return "concrete", 1
    return None, 0


def rasterise(elements, lat, lon, size_m, n=E.GRID_N, fill="concrete"):
    """OSM ways -> an n x n array of Blockwise material keys."""
    s, w, north, e = bbox(lat, lon, size_m)

    # cell centres. row 0 is north, so latitude descends with row index.
    lons = w + (np.arange(n) + 0.5) * (e - w) / n
    lats = north - (np.arange(n) + 0.5) * (north - s) / n
    X, Y = np.meshgrid(lons, lats)

    grid = np.full((n, n), fill, dtype=object)
    priority = np.zeros((n, n), dtype=int)

    # metres per degree, for road buffering
    m_per_deg_lon = 111_320 * np.cos(np.radians(lat))
    cell_deg = (e - w) / n

    for el in elements:
        geom = el.get("geometry")
        if not geom or len(geom) < 2:
            continue
        tags = el.get("tags", {})
        mat, pri = _material_for(tags)
        if mat is None:
            continue

        glon = np.array([p["lon"] for p in geom])
        glat = np.array([p["lat"] for p in geom])

        closed = (abs(glon[0] - glon[-1]) < 1e-9
                  and abs(glat[0] - glat[-1]) < 1e-9)

        if closed and len(geom) >= 4:
            hit = _inside(glon, glat, X, Y)
        else:
            # a line, e.g. a road. Mark cells within roughly half a cell.
            lanes = tags.get("lanes")
            try:
                width_m = 3.5 * float(lanes) if lanes else 8.0
            except ValueError:
                width_m = 8.0
            tol = max(width_m / m_per_deg_lon, cell_deg * 0.45)
            hit = np.zeros(X.shape, dtype=bool)
            for k in range(len(glon) - 1):
                # sample along the segment rather than doing true distance
                steps = max(2, int(np.hypot(glon[k + 1] - glon[k],
                                            glat[k + 1] - glat[k]) / tol) + 1)
                for t in np.linspace(0, 1, steps):
                    px = glon[k] + t * (glon[k + 1] - glon[k])
                    py = glat[k] + t * (glat[k + 1] - glat[k])
                    hit |= (np.abs(X - px) < tol) & (np.abs(Y - py) < tol)

        take = hit & (priority <= pri)
        grid[take] = mat
        priority[take] = pri

    return grid


def get_site(location, lat, lon, size_m=E.PLOT_M, use_cache=True):
    """Cached OSM land cover for a named location."""
    CACHE.mkdir(exist_ok=True)
    key = location.replace(", ", "_").replace(" ", "")
    path = CACHE / f"osm_{key}_{size_m}m_{E.GRID_N}.json"

    if use_cache and path.exists():
        saved = json.loads(path.read_text())
        return np.array(saved["grid"], dtype=object), saved["stats"]

    elements = fetch_osm(lat, lon, size_m)
    grid = rasterise(elements, lat, lon, size_m)

    keys, counts = np.unique(grid, return_counts=True)
    stats = {
        "n_ways": len(elements),
        "n_buildings": sum(1 for el in elements
                           if "building" in el.get("tags", {})),
        "mix": {str(k): int(v) for k, v in zip(keys, counts)},
        "source": "OpenStreetMap contributors, ODbL",
    }
    path.write_text(json.dumps({"grid": grid.tolist(), "stats": stats}))
    return grid, stats


if __name__ == "__main__":
    import fgdata

    for name, (lat, lon) in fgdata.LOCATIONS.items():
        t0 = time.time()
        try:
            grid, stats = get_site(name, lat, lon, use_cache=False)
        except Exception as exc:
            print(f"{name:16} FAILED {type(exc).__name__}: {exc}")
            continue
        comp = E.composition(grid)
        top = sorted(stats["mix"].items(), key=lambda x: -x[1])[:4]
        print(f"{name:16} {stats['n_ways']:>4} ways  "
              f"{stats['n_buildings']:>4} buildings  {time.time() - t0:.0f}s")
        print(f"{'':16} canopy {comp.canopy_pp:4.0f}%  "
              f"impervious {comp.impervious_pp:4.0f}%  "
              f"building {comp.building_pp:4.0f}%  albedo {comp.mean_albedo:.2f}")
        print(f"{'':16} {', '.join(f'{k} {v}' for k, v in top)}\n")
        time.sleep(3)      # Overpass is a shared free service. Be polite.
