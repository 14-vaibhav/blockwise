"""
Blockwise - step 1, with area controls and an editable sandbox.

Type any US location or click the map to set a centre point, pick a shape
(square / circle / hand-drawn polygon) and size, pick FortyGuard's tile
granularity, and see its measured heat for the most recent complete day
(FortyGuard is a single-day query - "today" is still incomplete, so the
default is always yesterday).

Once fetched, the exact area you selected becomes an editable grid: paint
buildings, greenery, water, paving onto a blank canvas and watch the
projected temperature change - every number in that readout comes from
engine.py, the same physics model used everywhere else in this project.
Nothing about the temperature math lives in this file.

The fuller dark-mode / OSM-existing-condition design lives in app_studio.py
for later.
"""

import math

import folium
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

import engine as E
import fgdata
import plandraw
import sandbox as S

st.set_page_config(page_title="Blockwise", layout="wide")

st.title("Blockwise")
st.caption("Enter any location in the USA, or click the map, to see "
          "FortyGuard's measured peak-afternoon temperature there - then "
          "paint the area to test what changes would do to it.")

# ------------------------------------------------------------------- state

if "center" not in st.session_state:
    st.session_state.center = {"name": None, "lat": 40.7580, "lon": -73.9855}
    st.session_state.location_error = None
    st.session_state.drawn_ring = None     # [[lon, lat], ...] from the map
    st.session_state.material = "tree_dense"
    st.session_state.brush = 2
    st.session_state.sandbox = None        # built after the first fetch
    st.session_state.click_seq = 0         # bumped to retire a stale click


@st.cache_data(show_spinner="Finding location...")
def geocode(query):
    return fgdata.geocode_us(query)


@st.cache_data(show_spinner="Fetching FortyGuard measurements... "
                            "(a new area can take up to 2 minutes)")
def fetch(location_name, aoi, shape_label, granularity, date):
    return fgdata.get_plot(location_name, aoi, shape_label,
                           date=date, granularity=granularity)


# ----------------------------------------------------------- sandbox rail

with st.sidebar:
    if not st.session_state.sandbox or "grid" not in st.session_state.sandbox:
        st.caption("Fetch a heatmap first - the sandbox to paint on "
                  "appears here once you have.")
    else:
        st.markdown("#### Paint the area")

        for group, items in E.palette().items():
            st.caption(group)
            for key, label, _ in items:
                on = st.session_state.material == key
                sw, btn = st.columns([1, 6], gap="small")
                with sw:
                    st.markdown(plandraw.swatch_svg(key, 22), unsafe_allow_html=True)
                with btn:
                    if st.button(("● " if on else "○ ") + label,
                                 key=f"mat_{key}", width="stretch"):
                        st.session_state.material = key
                        st.rerun()

        st.session_state.brush = st.slider("Brush size (cells)", 1, 6,
                                           st.session_state.brush)

        if st.button("Clear canvas", width="stretch"):
            sb = st.session_state.sandbox
            sb["grid"] = sb["baseline_grid"].copy()
            st.session_state.click_seq += 1   # retire any pending click too
            st.rerun()

        warn = E.WARNINGS.get(st.session_state.material)
        if warn:
            st.warning(warn, icon="⚠️")


# --------------------------------------------------------------- controls

with st.form("locate", clear_on_submit=False):
    c1, c2 = st.columns([5, 1])
    with c1:
        query = st.text_input(
            "Location", label_visibility="collapsed",
            placeholder="e.g. Austin, TX  ·  90210  ·  123 Main St, Denver CO")
    with c2:
        locate = st.form_submit_button("Locate", width="stretch")

if locate and query.strip():
    hit = geocode(query)
    if hit is None:
        st.session_state.location_error = f'No US match for "{query}".'
    else:
        lat, lon, display_name = hit
        st.session_state.center = {"name": display_name, "lat": lat, "lon": lon}
        st.session_state.location_error = None
        st.session_state.drawn_ring = None
        st.rerun()

if st.session_state.location_error:
    st.error(st.session_state.location_error)

o1, o2, o3 = st.columns(3)
with o1:
    shape = st.radio("Shape", ["Square", "Circle", "Polygon (draw on map)"],
                     horizontal=False)
with o2:
    if shape != "Polygon (draw on map)":
        size_m = st.slider("Side length (m)" if shape == "Square" else
                           "Radius (m)", 200, 5000, 1000, step=100)
    else:
        size_m = None
        st.caption("Draw a shape on the map using the polygon tool "
                  "(top-left of the map).")
with o3:
    granularity = st.selectbox("Granularity (m)", [60, 80, 100], index=2,
                               help="FortyGuard's tile size - the real-world "
                                    "measurement resolution, only allows "
                                    "these three values.")

date = fgdata.previous_day()
st.caption(f"Data date: **{date}** (most recent complete day - FortyGuard "
          "is queried for a single day at a time).")

# ------------------------------------------------------------------- map

center = st.session_state.center
m = folium.Map(location=[center["lat"], center["lon"]], zoom_start=14,
               control_scale=True)
folium.Marker([center["lat"], center["lon"]],
             tooltip=center["name"] or "Click map to move").add_to(m)

if shape == "Square":
    dla = (size_m / 2) / 111_320
    dlo = (size_m / 2) / (111_320 * math.cos(math.radians(center["lat"])))
    folium.Rectangle(
        bounds=[[center["lat"] - dla, center["lon"] - dlo],
               [center["lat"] + dla, center["lon"] + dlo]],
        color="#5E2B54", weight=2, fill=True, fill_opacity=0.12,
    ).add_to(m)
elif shape == "Circle":
    folium.Circle(
        location=[center["lat"], center["lon"]], radius=size_m,
        color="#5E2B54", weight=2, fill=True, fill_opacity=0.12,
    ).add_to(m)
else:
    Draw(export=False, draw_options={
        "polygon": {"shapeOptions": {"color": "#5E2B54"}},
        "rectangle": False, "circle": False, "circlemarker": False,
        "marker": False, "polyline": False,
    }, edit_options={"edit": True}).add_to(m)
    if st.session_state.drawn_ring:
        folium.Polygon(
            locations=[[lat, lon] for lon, lat in st.session_state.drawn_ring],
            color="#5E2B54", weight=2, fill=True, fill_opacity=0.12,
        ).add_to(m)

map_state = st_folium(m, height=420, width=None, key="picker",
                      returned_objects=["last_clicked", "last_active_drawing"])

if shape != "Polygon (draw on map)":
    clicked = map_state.get("last_clicked")
    if clicked and (round(clicked["lat"], 6) != round(center["lat"], 6)
                    or round(clicked["lng"], 6) != round(center["lon"], 6)):
        st.session_state.center = {"name": None, "lat": clicked["lat"],
                                   "lon": clicked["lng"]}
        st.rerun()
else:
    drawing = map_state.get("last_active_drawing")
    if drawing and drawing["geometry"]["type"] == "Polygon":
        ring = drawing["geometry"]["coordinates"][0]
        if ring != st.session_state.drawn_ring:
            st.session_state.drawn_ring = ring
            st.rerun()

# ------------------------------------------------------------------ fetch

go_clicked = st.button("Show heatmap", type="primary", width="stretch")

if go_clicked:
    location_name = center["name"] or f"{center['lat']:.4f}, {center['lon']:.4f}"
    if shape == "Square":
        aoi = fgdata.square_aoi(center["lat"], center["lon"], size_m)
        shape_label = f"{size_m}m_square"
    elif shape == "Circle":
        aoi = fgdata.circle_aoi(center["lat"], center["lon"], size_m)
        shape_label = f"{size_m}m_circle"
    elif not st.session_state.drawn_ring:
        aoi = None
        st.error("Draw a polygon on the map first.")
    else:
        aoi = fgdata.polygon_aoi(st.session_state.drawn_ring)
        shape_label = ("polygon_"
                       f"{abs(hash(tuple(map(tuple, st.session_state.drawn_ring)))) % 100000}")

    if aoi is not None:
        data = fetch(location_name, aoi, shape_label, granularity, date)

        sandbox_entry = {"location_name": location_name, "data": data}
        if data:
            # Build the editable grid to match the EXACT area just measured -
            # same shape, same size, same drawn ring - so the sandbox is
            # never a bounding-box approximation of what was selected.
            if shape == "Square":
                grid, mask, cw, ch = S.square_grid(size_m)
            elif shape == "Circle":
                grid, mask, cw, ch = S.circle_grid(size_m)
            else:
                grid, mask, cw, ch = S.polygon_grid(st.session_state.drawn_ring)

            y, x = np.mgrid[0:grid.shape[0], 0:grid.shape[1]]
            denom = max(1, (grid.shape[0] - 1) + (grid.shape[1] - 1))
            ramp = (x + y) / denom - 0.5
            measured_field_raw = data["peak_c"] + ramp * data.get("peak_spread", 0.0)

            sandbox_entry.update(
                grid=grid, baseline_grid=grid.copy(), mask=mask,
                cell_w=cw, cell_h=ch, measured_field_raw=measured_field_raw,
            )
        st.session_state.sandbox = sandbox_entry
        st.session_state.click_seq += 1   # new grid - drop any pending click
        st.rerun()

# --------------------------------------------------------------- result

sb = st.session_state.sandbox

if sb is None:
    st.info('Set a location and area above, then press "Show heatmap".')
elif not sb["data"]:
    st.warning("FortyGuard has no measurements for this area on this day.")
else:
    data, location_name = sb["data"], sb["location_name"]
    st.subheader(location_name)

    c1, c2, c3 = st.columns(3)
    c1.metric("Peak temperature", f"{data['peak_c']:.1f} °C")
    c2.metric("Tiles measured", data["n_tiles"])
    c3.metric("Spatial variation", f"{data['peak_spread']:.2f} °C")

    st.caption(
        f"Mean daily peak across {data['n_tiles']} FortyGuard tiles, "
        f"{data['date']}. Spatial variation {data['peak_spread']:.2f} °C. "
        f"Tiles are {granularity} m."
    )

    # ---------------------------------------------------------- sandbox

    rows, cols = sb["grid"].shape
    result = E.evaluate(sb["grid"], sb["baseline_grid"],
                        sb["measured_field_raw"], mask=sb["mask"])

    if abs(sb["cell_w"] - sb["cell_h"]) < 0.5:
        cell_desc = f"~{sb['cell_w']:.0f} m"
    else:
        cell_desc = f"~{sb['cell_w']:.0f} x {sb['cell_h']:.0f} m"

    st.markdown("---")
    st.markdown("#### Sandbox - paint the area to test the temperature effect")
    st.caption(
        f"Editable grid: {rows}×{cols} cells, {cell_desc} each, interpolated "
        f"from FortyGuard's measurement - not individually measured at cell "
        f"scale. Cells outside your selected shape (a circle or polygon can "
        f"be smaller than its square grid) are shown blank and excluded "
        f"from every calculation."
    )

    view = st.radio("view", ["Materials", "Temperature"], horizontal=True,
                    label_visibility="collapsed")

    if view == "Materials":
        mat = st.session_state.material
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:.5rem;'
            f'padding:.4rem .6rem;margin-bottom:.4rem;background:#DFE1DA;'
            f'border:1px solid #C3C5BD;border-radius:3px;'
            f'font-family:\'IBM Plex Mono\',monospace;font-size:.85rem;">'
            f'{plandraw.swatch_svg(mat, 20)}'
            f'<span>Now painting <b>{E.MATERIALS[mat]["label"]}</b> '
            f'&middot; brush {st.session_state.brush} cell'
            f'{"s" if st.session_state.brush != 1 else ""} '
            f'&middot; click the canvas below to place it '
            f'(pick a different material or brush size in the sidebar)</span>'
            f'</div>', unsafe_allow_html=True)
        fig = plandraw.plan_figure(sb["grid"], height=560, mask=sb["mask"])
    else:
        fig = plandraw.thermal_figure(result.projected_field, height=560)

    ev = st.plotly_chart(fig, width="stretch", on_select="rerun",
                         key=f"sandbox_click_{st.session_state.click_seq}",
                         selection_mode=("points",))

    sel = getattr(ev, "selection", None) or (
        ev.get("selection") if isinstance(ev, dict) else None)
    pts = (sel or {}).get("points", [])
    if pts:
        r, c = int(round(pts[0]["y"])), int(round(pts[0]["x"]))
        b = st.session_state.brush - 1
        r0, r1 = max(0, r - b // 2), min(rows, r + b // 2 + 1)
        c0, c1 = max(0, c - b // 2), min(cols, c + b // 2 + 1)
        sub = sb["grid"][r0:r1, c0:c1]
        sub_mask = sb["mask"][r0:r1, c0:c1]
        sub[sub_mask] = st.session_state.material
        # A plotly selection sticks around in session_state until a new
        # frontend event overwrites it - the chart's key must change so the
        # next render gets a clean widget instead of replaying this same
        # click (and rerun()ing) forever.
        st.session_state.click_seq += 1
        st.rerun()

    m1, m2, m3 = st.columns(3)
    m1.metric("Measured", f"{result.measured_c:.1f} °C")
    band = (result.delta_high - result.delta_low) / 2
    m2.metric("Your changes", f"{result.delta_c:+.1f} °C", delta=f"±{band:.1f}",
              delta_color="off")
    m3.metric("Projected", f"{result.projected_c:.1f} °C")

    for note in result.notes:
        st.info(note, icon="ℹ️")

    terms = {k: v for k, v in result.breakdown.items() if abs(v) > 0.005}
    if terms:
        st.caption("Contribution by mechanism")
        order = sorted(terms.items(), key=lambda x: x[1])
        bar = go.Figure(go.Bar(
            x=[v for _, v in order], y=[k for k, _ in order], orientation="h",
            marker_color=["#1976d2" if v < 0 else "#c62828" for _, v in order],
            text=[f"{v:+.2f}" for _, v in order], textposition="auto",
        )).update_layout(height=34 * len(order) + 40,
                         margin=dict(l=0, r=0, t=0, b=0),
                         xaxis_title="°C", showlegend=False)
        st.plotly_chart(bar, width="stretch")
    else:
        st.caption("No changes yet - paint something on the canvas above.")

    now, base = result.now, result.base
    st.caption("Composition")
    st.dataframe({
        "": ["Canopy", "Impervious", "Building", "Mean albedo", "Trees"],
        "Blank canvas": [f"{base.canopy_pp:.0f}%", f"{base.impervious_pp:.0f}%",
                         f"{base.building_pp:.0f}%", f"{base.mean_albedo:.2f}",
                         f"{base.tree_count:,}"],
        "Your design": [f"{now.canopy_pp:.0f}%", f"{now.impervious_pp:.0f}%",
                        f"{now.building_pp:.0f}%", f"{now.mean_albedo:.2f}",
                        f"{now.tree_count:,}"],
    }, hide_index=True, width="stretch")

    with st.expander("How these numbers are made"):
        st.markdown("""
Every coefficient is **air temperature at 2 m**, not land surface
temperature. Surface effects run roughly 2x larger; quoting them would
make this tool wildly over-optimistic.

Coefficients carry a status:

- **literature_central** — literature-average estimate. Real, but climate-
  and scale-dependent. *Canopy, cool pavement, water.*
- **engineering_value** — a defensible choice inside the published range.
  *Albedo: credible estimates span 0.09 to 0.6 °C per +0.1, a factor of six.*
- **calibration_parameter** — our own tuning knob, no universal basis.
  *Impervious, grass, building density.*

The 40% canopy threshold is inspired by Ziter et al. 2019 (PNAS, Madison WI),
which found a marked jump in cooling above roughly that level. The two slopes
either side are **ours**, not theirs.

Total cooling is capped at −4 °C as an engineering safeguard, not a
literature maximum. Building morphology is the least certain part of the
model; shade, sky-view factor and street-canyon effects are not simulated.
        """)
