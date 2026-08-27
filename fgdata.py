"""
FortyGuard data access.

Pick a location and a plot size, get back the temperatures for that plot.

What the API gives us, established by probing:
  - async: POST /v1/heatmap returns an activity_id, GET /v1/status/{id}
    returns the data
  - auth is the api-key header
  - polygon_aoi must be a FeatureCollection, filter_type 3 for a single day
  - granularity is metres and accepts ONLY 60, 80 or 100
  - each tile carries average / min / max temperature, in Celsius
  - a 96 m plot returns zero tiles; you need a few hundred metres minimum

Which number to build on: max_temperature. Every coefficient in engine.py is
a peak-afternoon value, so the baseline has to be the daytime peak, not the
24-hour mean. The mean also turned out to be nearly identical everywhere,
which makes it useless as a baseline anyway.
"""

import json
import math
import os
import pathlib
import re
import time
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["FORTYGUARD_API_KEY"]
BASE = "https://api.fortyguard.com/v1"
HEADERS = {"api-key": API_KEY, "Content-Type": "application/json"}

GRANULARITY = 100          # metres. allowed: 60, 80, 100
CACHE = pathlib.Path("cache")

# Curated quick-pick examples, pre-cached for a fast first load. Not the only
# selectable locations - geocode_us() below resolves any US place name.
LOCATIONS = {
    "Manhattan, NY": (40.7580, -73.9855),
    "Ashburn, VA":   (39.0438, -77.4874),
    "Phoenix, AZ":   (33.4484, -112.0740),
}

# Nominatim (OpenStreetMap) - free, no key, restricted to the US to match the
# engine's scope (engine.py: "Scope: US, daytime, summer, clear sky").
GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
GEOCODE_HEADERS = {"User-Agent": "Blockwise/1.0 (FortyGuard hackathon project)"}


def geocode_us(query):
    """
    Free-text place name -> (lat, lon, display_name), restricted to the USA.
    None if nothing matched. Raises on a network/HTTP failure.
    """
    query = query.strip()
    if not query:
        return None
    r = requests.get(GEOCODE_URL, params={
        "q": query, "format": "json", "countrycodes": "us", "limit": 1,
    }, headers=GEOCODE_HEADERS, timeout=20)
    r.raise_for_status()
    hits = r.json()
    if not hits:
        return None
    hit = hits[0]
    return float(hit["lat"]), float(hit["lon"]), hit["display_name"]


def previous_day():
    """
    FortyGuard is queried for a single day (filter_type 3). Default to
    yesterday relative to the server's local date - "today" is still an
    incomplete day, so it is never a meaningful single-day snapshot.
    """
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def square_aoi(lat, lon, size_m):
    """Square GeoJSON FeatureCollection centred on lat/lon, side = size_m."""
    dla = (size_m / 2) / 111_320
    dlo = (size_m / 2) / (111_320 * math.cos(math.radians(lat)))
    ring = [[lon - dlo, lat - dla], [lon + dlo, lat - dla],
            [lon + dlo, lat + dla], [lon - dlo, lat + dla],
            [lon - dlo, lat - dla]]
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {},
         "geometry": {"type": "Polygon", "coordinates": [ring]}}]}


# kept for compatibility - "square" was the only shape before circle/polygon.
build_aoi = square_aoi


def circle_aoi(lat, lon, radius_m, n=48):
    """
    Circle GeoJSON FeatureCollection centred on lat/lon, approximated as an
    n-sided polygon - FortyGuard's polygon_aoi has no native circle type.
    """
    dla = radius_m / 111_320
    dlo = radius_m / (111_320 * math.cos(math.radians(lat)))
    ring = [[lon + dlo * math.cos(2 * math.pi * i / n),
             lat + dla * math.sin(2 * math.pi * i / n)] for i in range(n)]
    ring.append(ring[0])
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {},
         "geometry": {"type": "Polygon", "coordinates": [ring]}}]}


def polygon_aoi(lonlat_ring):
    """GeoJSON FeatureCollection from an explicit [lon, lat] ring, e.g. one
    drawn by hand on a map. Closed automatically if not already."""
    ring = [list(pt) for pt in lonlat_ring]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {},
         "geometry": {"type": "Polygon", "coordinates": [ring]}}]}


def fetch_tiles(aoi, date=None, granularity=GRANULARITY):
    """Submit a heatmap job, poll until complete. Returns the tile list."""
    date = date or previous_day()

    r = requests.post(f"{BASE}/heatmap", headers=HEADERS, json={
        "polygon_aoi": aoi,
        "date_time": {"start_date": date, "filter_type": 3},
        "granularity": granularity,
    }, timeout=60)
    r.raise_for_status()
    aid = r.json()["data"]["activity_id"]

    for _ in range(60):
        d = requests.get(f"{BASE}/status/{aid}",
                         headers=HEADERS, timeout=60).json().get("data", {})
        status = d.get("status")
        if status == "Completed":
            return d["result"]["map_data"]["features"]
        if status in ("Failed", "Error"):
            raise RuntimeError(f"job failed: {str(d)[:200]}")
        time.sleep(3)
    raise TimeoutError(f"activity {aid} did not complete in 180s")


def summarise(tiles):
    """Tiles -> the numbers the app displays."""
    if not tiles:
        return None
    mx = [t["properties"]["max_temperature"] for t in tiles]
    mn = [t["properties"]["min_temperature"] for t in tiles]
    av = [t["properties"]["average_temperature"] for t in tiles]
    return {
        "n_tiles": len(tiles),
        "peak_c": sum(mx) / len(mx),          # the baseline engine.py modifies
        "low_c": sum(mn) / len(mn),
        "daily_mean_c": sum(av) / len(av),
        # spatial variation across the plot. Watch this: if it is ever much
        # above ~1 C, there is a real measured field here and the thermal
        # view can show it rather than only showing the model's output.
        "peak_spread": max(mx) - min(mx),
        "peak_range": [min(mx), max(mx)],
    }


def get_plot(location, aoi, shape_label, date=None, use_cache=True,
             granularity=GRANULARITY):
    """
    Cache first, network second. shape_label identifies the AOI for the
    cache filename (e.g. "1000m_square", "600m_circle", "polygon_a1b2c3") -
    a live call is an async job polled every 3s, up to ~2 minutes.
    """
    CACHE.mkdir(exist_ok=True)
    date = date or previous_day()
    key = re.sub(r"[^A-Za-z0-9]+", "_", location).strip("_")
    path = CACHE / f"{key}_{shape_label}_g{granularity}_{date}.json"

    if use_cache and path.exists():
        return json.loads(path.read_text())

    tiles = fetch_tiles(aoi, date, granularity)
    out = summarise(tiles)
    if out:
        out["location"] = location
        out["shape_label"] = shape_label
        out["date"] = date
        path.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    print(f"granularity {GRANULARITY} m\n")
    print(f"{'location':16} {'size':>6} {'tiles':>6} {'peak':>7} "
          f"{'low':>7} {'spread':>7}")
    print("-" * 56)

    for loc in LOCATIONS:
        lat, lon = LOCATIONS[loc]
        for size in (500, 1000, 2000, 3000):
            cached = (CACHE / f"{loc.replace(', ', '_').replace(' ', '')}"
                              f"_{size}m_square_g{GRANULARITY}_2024-07-15.json").exists()
            try:
                d = get_plot(loc, square_aoi(lat, lon, size), f"{size}m_square",
                            date="2024-07-15")
            except Exception as e:
                print(f"{loc:16} {size:>5}m  ERROR {type(e).__name__} "
                      f"- waiting 60s for rate limit")
                time.sleep(60)
                continue
            if not d:
                print(f"{loc:16} {size:>5}m  0 tiles")
                continue
            print(f"{loc:16} {size:>5}m {d['n_tiles']:>6} "
                  f"{d['peak_c']:>6.1f}C {d['low_c']:>6.1f}C "
                  f"{d['peak_spread']:>6.2f}")
            if not cached:
                time.sleep(20)

    print("\nRun again - cached results return instantly.")