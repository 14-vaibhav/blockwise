"""
api.py is a thin wrapper - these tests exist to prove it stays thin. The
one that matters most is test_simulate_matches_engine_directly: it proves
the HTTP layer can never drift from engine.py's actual physics, which is
the guarantee the whole Part 2 editor depends on.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

import api
import engine as E
import fgdata

client = TestClient(api.app)


# ------------------------------------------------------------- materials

def test_materials_matches_engine_verbatim():
    body = client.get("/api/materials").json()
    assert set(body["materials"]) == set(E.MATERIALS)
    for key, mat in E.MATERIALS.items():
        for field in ("label", "group", "colour", "canopy", "impervious", "albedo"):
            assert body["materials"][key][field] == mat[field]
    assert body["default_material"] == E.DEFAULT_MATERIAL
    assert body["coefficients"]["max_cooling_c"] == E.MAX_COOLING_C


def test_quick_locations_matches_fgdata():
    body = client.get("/api/locations/quick").json()
    assert set(body) == set(fgdata.LOCATIONS)
    for name, (lat, lon) in fgdata.LOCATIONS.items():
        assert body[name] == {"lat": lat, "lon": lon}


# ------------------------------------------------------------------ geocode

def test_geocode_no_match_is_404(monkeypatch):
    monkeypatch.setattr(fgdata, "geocode_us", lambda q: None)
    r = client.post("/api/geocode", json={"query": "Nowhere At All"})
    assert r.status_code == 404


def test_geocode_hit_passes_through(monkeypatch):
    monkeypatch.setattr(fgdata, "geocode_us", lambda q: (1.0, 2.0, "Somewhere, US"))
    r = client.post("/api/geocode", json={"query": "Somewhere"})
    assert r.status_code == 200
    assert r.json() == {"lat": 1.0, "lon": 2.0, "display_name": "Somewhere, US"}


# --------------------------------------------------------------------- site

def test_site_square_uses_cache_and_matches_sandbox_shape():
    # Manhattan, NY / 1000m / g100 / 2024-07-15 is pre-cached in cache/ -
    # this must not hit the network.
    lat, lon = fgdata.LOCATIONS["Manhattan, NY"]
    r = client.post("/api/site", json={
        "location_name": "Manhattan, NY", "lat": lat, "lon": lon,
        "shape": "square", "size_m": 1000, "granularity": 100,
        "date": "2024-07-15",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == body["cols"] == len(body["grid"])
    assert len(body["mask"]) == body["rows"]
    assert body["data"]["n_tiles"] > 0
    assert all(v == E.DEFAULT_MATERIAL for row in body["grid"] for v in row)


def test_site_polygon_needs_three_points():
    lat, lon = fgdata.LOCATIONS["Manhattan, NY"]
    r = client.post("/api/site", json={
        "location_name": "Manhattan, NY", "lat": lat, "lon": lon,
        "shape": "polygon", "polygon_ring": [[lon, lat], [lon + 0.001, lat]],
    })
    assert r.status_code == 400


def test_site_osm_baseline_rejected_for_non_square():
    lat, lon = fgdata.LOCATIONS["Manhattan, NY"]
    r = client.post("/api/site", json={
        "location_name": "Manhattan, NY", "lat": lat, "lon": lon,
        "shape": "circle", "size_m": 500, "existing_condition": "osm",
    })
    assert r.status_code == 400


# ----------------------------------------------------------------- simulate

def _sample_grid(n=10):
    grid = np.full((n, n), "grass", dtype=object)
    grid[2:5, 2:5] = "asphalt"
    baseline = np.full((n, n), "grass", dtype=object)
    measured = np.full((n, n), 34.5)
    return grid, baseline, measured


def test_simulate_matches_engine_directly():
    grid, baseline, measured = _sample_grid()
    expected = E.evaluate(grid, baseline, measured)

    r = client.post("/api/simulate", json={
        "grid": grid.tolist(), "baseline_grid": baseline.tolist(),
        "measured_field": measured.tolist(), "mask": None,
    })
    assert r.status_code == 200
    body = r.json()

    assert body["delta_c"] == pytest.approx(expected.delta_c)
    assert body["delta_low"] == pytest.approx(expected.delta_low)
    assert body["delta_high"] == pytest.approx(expected.delta_high)
    assert body["measured_c"] == pytest.approx(expected.measured_c)
    assert body["projected_c"] == pytest.approx(expected.projected_c)
    assert body["clamped"] == expected.clamped
    for k, v in expected.breakdown.items():
        assert body["breakdown"][k] == pytest.approx(v)
    assert body["now"]["canopy_pp"] == pytest.approx(expected.now.canopy_pp)
    assert body["base"]["impervious_pp"] == pytest.approx(expected.base.impervious_pp)
    np.testing.assert_allclose(
        np.array(body["projected_field"]), expected.projected_field)


def test_simulate_with_mask_matches_engine_directly():
    grid, baseline, measured = _sample_grid()
    mask = np.ones((10, 10), dtype=bool)
    mask[0, :] = False   # exclude the top row, like a circle/polygon selection
    expected = E.evaluate(grid, baseline, measured, mask=mask)

    r = client.post("/api/simulate", json={
        "grid": grid.tolist(), "baseline_grid": baseline.tolist(),
        "measured_field": measured.tolist(), "mask": mask.tolist(),
    })
    body = r.json()
    assert body["delta_c"] == pytest.approx(expected.delta_c)
    # excluded cells come back as null (JSON has no NaN), not a number
    assert body["projected_field"][0][0] is None


def test_simulate_rejects_unknown_material():
    grid, baseline, measured = _sample_grid()
    grid[0, 0] = "lava"
    r = client.post("/api/simulate", json={
        "grid": grid.tolist(), "baseline_grid": baseline.tolist(),
        "measured_field": measured.tolist(), "mask": None,
    })
    assert r.status_code == 400


def test_simulate_rejects_mismatched_shapes():
    grid, baseline, measured = _sample_grid()
    r = client.post("/api/simulate", json={
        "grid": grid.tolist(), "baseline_grid": baseline[:5].tolist(),
        "measured_field": measured.tolist(), "mask": None,
    })
    assert r.status_code == 400


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}
