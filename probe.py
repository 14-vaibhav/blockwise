"""
At what area size does FortyGuard's data actually vary in space?

What we know:
  - 60 m is the smallest granularity the API accepts
  - a 96 m area returns zero tiles
  - at 500-800 m the tiles are near-identical: Central Park's edge gave
    0.00 spread across 179 tiles, so all of them fell inside one underlying
    data cell
  - Manhattan at 500 m gave 0.75 C, which means it straddled a boundary
    between two cells

So the tiles are interpolation, not measurement, and the real cells are
much bigger. This finds how big.

What we are looking for: spread that GROWS with area size. If 5 km shows
2-3 C, that is the scale Blockwise should work at. If everything stays
near zero, FortyGuard gives us a number rather than a field, and the
baseline becomes a scalar.
"""

import math
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

H = {"api-key": os.environ["FORTYGUARD_API_KEY"],
     "Content-Type": "application/json"}
DATE = "2024-07-15"


def aoi(lat, lon, size_m):
    dla = (size_m / 2) / 111_320
    dlo = (size_m / 2) / (111_320 * math.cos(math.radians(lat)))
    ring = [[lon - dlo, lat - dla], [lon + dlo, lat - dla],
            [lon + dlo, lat + dla], [lon - dlo, lat + dla],
            [lon - dlo, lat - dla]]
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {},
         "geometry": {"type": "Polygon", "coordinates": [ring]}}]}


def fetch(lat, lon, size_m, gran=60, date=DATE):
    r = requests.post("https://api.fortyguard.com/v1/heatmap", headers=H, json={
        "polygon_aoi": aoi(lat, lon, size_m),
        "date_time": {"start_date": date, "filter_type": 3},
        "granularity": gran,
    }, timeout=60)
    if r.status_code != 200:
        return None, f"submit {r.status_code}: {r.text[:150]}"
    aid = r.json()["data"]["activity_id"]

    for _ in range(60):
        d = requests.get(f"https://api.fortyguard.com/v1/status/{aid}",
                         headers=H, timeout=60).json().get("data", {})
        if d.get("status") == "Completed":
            return d["result"]["map_data"]["features"], None
        if d.get("status") in ("Failed", "Error"):
            return None, str(d)[:150]
        time.sleep(3)
    return None, "timeout"


def distinct_values(feats, key="max_temperature"):
    """
    How many DIFFERENT temperatures came back, rounded to 0.01.

    This is the real measure. 179 tiles holding 1 distinct value means the
    whole area sits inside one data cell. 179 tiles holding 40 distinct
    values means we have a field.
    """
    return sorted({round(f["properties"][key], 2) for f in feats})


def report(label, lat, lon, size_m, gran=60):
    t0 = time.time()
    feats, err = fetch(lat, lon, size_m, gran)
    took = time.time() - t0

    if err:
        print(f"{label:22} ERROR  {err}")
        return
    if not feats:
        print(f"{label:22} 0 tiles")
        return

    mx = [f["properties"]["max_temperature"] for f in feats]
    vals = distinct_values(feats)

    print(f"{label:22} {len(feats):>5} tiles  "
          f"{len(vals):>4} distinct  "
          f"spread {max(mx) - min(mx):5.2f} C  "
          f"({min(mx):.1f}-{max(mx):.1f})  {took:.0f}s")


print("=" * 78)
print("SIZE SWEEP - Manhattan. Does spread grow with area?")
print("=" * 78)
for size in [500, 1000, 2000, 5000, 10000]:
    report(f"Manhattan {size}m", 40.7580, -73.9855, size)

print()
print("=" * 78)
print("Same sweep, Phoenix. Confirms it is not a Manhattan quirk.")
print("=" * 78)
for size in [2000, 5000, 10000]:
    report(f"Phoenix {size}m", 33.4484, -112.0740, size)

print()
print("=" * 78)
print("Coarser granularity at 10 km - different data product, or same?")
print("=" * 78)
for g in [120, 250, 500]:
    report(f"Manhattan g={g}", 40.7580, -73.9855, 10000, gran=g)

print()
print("=" * 78)
print("Full 422 text - what granularity values are actually allowed?")
print("=" * 78)
r = requests.post("https://api.fortyguard.com/v1/heatmap", headers=H, json={
    "polygon_aoi": aoi(40.7580, -73.9855, 2000),
    "date_time": {"start_date": DATE, "filter_type": 3},
    "granularity": 7,
}, timeout=30)
print(r.text)

print()
print("READ IT LIKE THIS:")
print("  'distinct' is the column that matters, not 'tiles'.")
print("  Tiles are interpolation. Distinct values are real data cells.")
print("  Find the smallest size where distinct is comfortably above ~20.")
print("  That is the scale Blockwise works at.")