"""
Turns whatever area the user selected on the map (square / circle / hand-
drawn polygon, any size) into an editable grid + mask for engine.py.

Pure geometry, no Streamlit and no engine.py physics - this only decides
which cells exist and which of them fall inside the actual selected shape.
The temperature math itself stays entirely in engine.py.

CELL SCALE: engine.py's coefficients, kernels and canopy threshold are
calibrated around ~40 m cells (see engine.CELL_M). A selection close to the
original 1200 m plot lands on close to a 30x30 grid at ~40 m, matching that
calibration exactly. Far outside that range the grid resolution is clamped
(MIN_N..MAX_N) so cell count never explodes or interactive editing goes
too coarse to be useful - cell size drifts from 40 m accordingly, and the
UI shows the actual resulting cell size rather than hiding it.
"""

import math

import numpy as np

import engine as E

TARGET_CELL_M = E.CELL_M   # 40 - the physics is calibrated around this
MIN_N = 10
MAX_N = 40

M_PER_DEG_LAT = 111_320


def _resolve_n(extent_m):
    n = round(extent_m / TARGET_CELL_M)
    return max(MIN_N, min(MAX_N, n))


def _blank(rows, cols):
    return np.full((rows, cols), E.DEFAULT_MATERIAL, dtype=object)


def square_grid(size_m):
    """size_m x size_m, fully selected - no masking needed."""
    n = _resolve_n(size_m)
    grid = _blank(n, n)
    mask = np.ones((n, n), dtype=bool)
    cell_m = size_m / n
    return grid, mask, cell_m, cell_m


def circle_grid(radius_m):
    """A square bounding grid, masked down to the inscribed circle."""
    side = 2 * radius_m
    n = _resolve_n(side)
    cell_m = side / n
    grid = _blank(n, n)

    centres = (np.arange(n) + 0.5) * cell_m - side / 2
    X, Y = np.meshgrid(centres, centres)
    mask = (X ** 2 + Y ** 2) <= radius_m ** 2

    return grid, mask, cell_m, cell_m


def _inside_polygon(poly_x, poly_y, X, Y):
    """Vectorised crossing-number point-in-polygon test."""
    inside = np.zeros(X.shape, dtype=bool)
    n = len(poly_x)
    j = n - 1
    for i in range(n):
        xi, yi = poly_x[i], poly_y[i]
        xj, yj = poly_x[j], poly_y[j]
        crosses = ((yi > Y) != (yj > Y)) & (
            X < (xj - xi) * (Y - yi) / (yj - yi + 1e-15) + xi)
        inside ^= crosses
        j = i
    return inside


def polygon_grid(lonlat_ring):
    """
    A rectangular bounding grid over a hand-drawn polygon, masked to the
    polygon itself. lonlat_ring: list of [lon, lat] pairs, as returned by
    the map's draw tool. The bounding box need not be square, so this can
    return a non-square grid - engine.py handles that directly.
    """
    lons = [p[0] for p in lonlat_ring]
    lats = [p[1] for p in lonlat_ring]
    lat0 = sum(lats) / len(lats)
    m_per_deg_lon = M_PER_DEG_LAT * math.cos(math.radians(lat0))

    lon0 = sum(lons) / len(lons)
    xs = np.array([(lo - lon0) * m_per_deg_lon for lo in lons])
    ys = np.array([(la - lat0) * M_PER_DEG_LAT for la in lats])

    width_m = float(xs.max() - xs.min())
    height_m = float(ys.max() - ys.min())
    cx, cy = (xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2

    cols = _resolve_n(width_m)
    rows = _resolve_n(height_m)
    cell_w = width_m / cols
    cell_h = height_m / rows

    grid = _blank(rows, cols)

    x_centres = (np.arange(cols) + 0.5) * cell_w - width_m / 2 + cx
    y_centres = (np.arange(rows) + 0.5) * cell_h - height_m / 2 + cy
    X, Y = np.meshgrid(x_centres, y_centres)

    mask = _inside_polygon(xs, ys, X, Y)
    return grid, mask, cell_w, cell_h
