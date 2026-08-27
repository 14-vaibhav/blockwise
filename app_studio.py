"""
Blockwise - district heat sandbox.

VISUAL LANGUAGE: the planning drawing. Cool paper, hairline rules, a title
block, monospace annotation. The tool is for planners, so it borrows the
planner's vernacular rather than the thermographer's.

THE RULE THIS DESIGN ENCODES: measured and modelled never blend. FortyGuard's
measurements are solid ink. Our model's output is annotation violet with a
hatch fill - a redline over an existing drawing. A reader can tell at a glance
which part is data and which part is a claim.
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import engine as E
import fgdata
import osmdata
import plandraw

st.set_page_config(page_title="Blockwise", layout="wide",
                   initial_sidebar_state="expanded")

# ------------------------------------------------------------------- state
#
# Set before the style block below, since it needs st.session_state.material
# and .dark to already exist to build the selected-material highlight and
# pick a token set.

if "material" not in st.session_state:
    st.session_state.material = "tree_dense"
    st.session_state.brush = 2
    st.session_state.site = None
    st.session_state.dark = False
    st.session_state.location = {"name": "Manhattan, NY",
                                 "lat": 40.7580, "lon": -73.9855}
    st.session_state.location_error = None

# ------------------------------------------------------------------ tokens
#
# Two full token sets rather than a CSS media query: the toggle must be
# explicit and reliable regardless of the viewer's OS/browser theme, which
# is what made the original fixed-light design unreadable for some users.

_LIGHT = dict(
    PAPER="#E9EAE5", PAPER_2="#DFE1DA", INK="#16181A", INK_60="#5A5F5C",
    RULE="#C3C5BD", MEASURED="#1B4B52", MODELLED="#5E2B54", AMBER="#9C6B1E",
    THERMAL_COOL="#1B4B52", THERMAL_WARM="#8C2F1E",
)
_DARK = dict(
    PAPER="#15191D", PAPER_2="#1E2329", INK="#ECEDE7", INK_60="#9AA39C",
    RULE="#343B41", MEASURED="#5FD3DE", MODELLED="#E39BD6", AMBER="#E6AE4D",
    THERMAL_COOL="#3E93A0", THERMAL_WARM="#D97A54",
)
_T = _DARK if st.session_state.dark else _LIGHT

PAPER = _T["PAPER"]
PAPER_2 = _T["PAPER_2"]
INK = _T["INK"]
INK_60 = _T["INK_60"]
RULE = _T["RULE"]
MEASURED = _T["MEASURED"]      # FortyGuard data - solid, factual
MODELLED = _T["MODELLED"]      # our model - annotation violet, hatched
AMBER = _T["AMBER"]            # radiant-heat warning

# Left-border colour per material, plus a solid highlight on whichever
# material button is currently selected. Targets Streamlit's auto-generated
# `.st-key-<key>` class - this is CSS-only styling, not a DOM wrapper, since
# st.markdown() and st.button() calls render as sibling elements rather than
# nesting, so wrapping a button in markdown HTML tags does not work.
_mat_css = "\n".join(
    f'.st-key-mat_{k} button {{ border-left: 6px solid {v["colour"]} !important; }}'
    for k, v in E.MATERIALS.items()
)
_mat_css += (
    f'\n.st-key-mat_{st.session_state.material} button {{'
    f' background: {INK} !important; color: {PAPER} !important; }}'
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {{
  --paper: {PAPER}; --paper2: {PAPER_2}; --ink: {INK}; --ink60: {INK_60};
  --rule: {RULE}; --measured: {MEASURED}; --modelled: {MODELLED};
  --amber: {AMBER};
}}

.stApp {{ background: var(--paper); }}
html, body, [class*="css"] {{ font-family: 'Archivo', sans-serif; color: var(--ink); }}

#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1500px; }}

.masthead {{
  display: flex; align-items: baseline; justify-content: space-between;
  border-bottom: 2px solid var(--ink); padding-bottom: .5rem; margin-bottom: 1.4rem;
}}
.masthead .wordmark {{
  font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 1.55rem;
  letter-spacing: .16em; text-transform: uppercase;
}}
.masthead .strap {{
  font-family: 'IBM Plex Mono', monospace; font-size: .68rem; letter-spacing: .13em;
  text-transform: uppercase; color: var(--ink60);
}}

.titleblock {{ border: 1.5px solid var(--ink); background: var(--paper2); margin-top: .4rem; }}
.tb-head {{
  font-family: 'IBM Plex Mono', monospace; font-size: .62rem; letter-spacing: .16em;
  text-transform: uppercase; padding: .4rem .8rem; border-bottom: 1px solid var(--rule);
  color: var(--ink60);
}}
.tb-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; }}
.tb-cell {{ padding: .85rem .8rem; border-right: 1px solid var(--rule); }}
.tb-cell:last-child {{ border-right: none; }}
.tb-label {{
  display: block; font-family: 'IBM Plex Mono', monospace; font-size: .58rem;
  letter-spacing: .13em; text-transform: uppercase; color: var(--ink60);
  margin-bottom: .35rem;
}}
.tb-value {{
  font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 1.95rem;
  line-height: 1; letter-spacing: -.02em;
}}
.tb-value .u {{ font-size: .8rem; font-weight: 400; margin-left: .15rem; color: var(--ink60); }}
.v-measured {{ color: var(--measured); }}
.v-modelled {{ color: var(--modelled); }}
.v-projected {{ color: var(--ink); }}
.tb-band {{
  font-family: 'IBM Plex Mono', monospace; font-size: .7rem; color: var(--ink60);
  margin-left: .3rem;
}}

/* signature: solid measured bar, hatched modelled delta */
.scale {{ padding: .7rem .8rem .9rem; border-top: 1px solid var(--rule); }}
.scale-track {{ height: 15px; display: flex; border: 1px solid var(--ink); }}
.scale-measured {{ background: var(--measured); }}
.scale-modelled {{
  background: repeating-linear-gradient(45deg,
    var(--modelled) 0 3px, transparent 3px 6px), var(--paper);
  border-left: 1px solid var(--ink);
}}
.scale-key {{
  display: flex; gap: 1.4rem; margin-top: .45rem;
  font-family: 'IBM Plex Mono', monospace; font-size: .58rem;
  letter-spacing: .1em; text-transform: uppercase; color: var(--ink60);
}}
.swatch {{ display: inline-block; width: 22px; height: 8px; margin-right: .35rem;
  border: 1px solid var(--ink); vertical-align: middle; }}
.sw-m {{ background: var(--measured); }}
.sw-d {{ background: repeating-linear-gradient(45deg,
  var(--modelled) 0 3px, transparent 3px 6px), var(--paper); }}

.ann {{ font-family: 'IBM Plex Mono', monospace; font-size: .72rem;
  padding: .5rem .8rem; border-top: 1px solid var(--rule); color: var(--ink60);
  line-height: 1.5; }}
.ann b {{ color: var(--ink); font-weight: 600; }}
.flag {{ border-left: 3px solid var(--amber); background: rgba(156,107,30,.08);
  padding: .5rem .7rem; margin: .5rem 0; font-family: 'IBM Plex Mono', monospace;
  font-size: .7rem; line-height: 1.45; }}

.eyebrow {{
  font-family: 'IBM Plex Mono', monospace; font-size: .6rem; letter-spacing: .16em;
  text-transform: uppercase; color: var(--ink60);
  border-bottom: 1px solid var(--rule); padding-bottom: .3rem; margin: 1.3rem 0 .6rem;
}}

section[data-testid="stSidebar"] {{ background: var(--paper2); border-right: 1.5px solid var(--ink); }}
section[data-testid="stSidebar"] .stButton button {{
  font-family: 'IBM Plex Mono', monospace; font-size: .72rem; text-align: left;
  justify-content: flex-start; border-radius: 2px; border: 1px solid var(--rule);
  background: var(--paper); color: var(--ink); padding: .3rem .6rem;
  min-height: 0; height: 30px;
}}
section[data-testid="stSidebar"] .stButton button:hover {{
  border-color: var(--ink); background: #fff;
}}
{_mat_css}

.stRadio label p {{ font-family: 'IBM Plex Mono', monospace; font-size: .72rem; }}

/* native widget chrome - re-themed so dark mode has no light-theme leftovers */
:root {{ color-scheme: {"dark" if st.session_state.dark else "light"}; }}
[data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background: var(--paper); }}
[data-testid="stWidgetLabel"] p, .stMarkdown p {{ color: var(--ink); }}

div[data-testid="stTextInput"] input,
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"] {{
  background: var(--paper) !important; color: var(--ink) !important;
  border-color: var(--rule) !important;
  font-family: 'IBM Plex Mono', monospace !important; font-size: .78rem !important;
}}
div[data-baseweb="popover"] [role="listbox"],
div[data-baseweb="menu"] {{
  background: var(--paper2) !important; color: var(--ink) !important;
}}
div[data-baseweb="popover"] li, div[data-baseweb="menu"] li {{
  color: var(--ink) !important;
}}
div[data-baseweb="popover"] li:hover, div[data-baseweb="menu"] li:hover {{
  background: var(--rule) !important;
}}

div[data-testid="stSlider"] [data-baseweb="slider"] div {{ background: var(--rule); }}
div[data-testid="stSlider"] [role="slider"] {{
  background: var(--ink) !important; border-color: var(--ink) !important;
}}
div[data-testid="stSliderTickBarMin"], div[data-testid="stSliderTickBarMax"],
div[data-testid="stTickBarMin"], div[data-testid="stTickBarMax"] {{ color: var(--ink60) !important; }}

div[data-testid="stForm"] {{ border: 1px solid var(--rule); border-radius: 2px;
  padding: .6rem .6rem .2rem; background: var(--paper); }}

div[data-testid="stExpander"] {{ border: 1px solid var(--rule); background: var(--paper2); }}
div[data-testid="stExpander"] summary {{ color: var(--ink); font-family: 'IBM Plex Mono', monospace; }}

label[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p,
label[data-baseweb="checkbox"] div {{ color: var(--ink) !important; }}

div[data-testid="stTable"], div[data-testid="stDataFrame"] {{ color: var(--ink); }}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------- palette rail

@st.cache_data(show_spinner="Reading OpenStreetMap land cover...")
def site_grid(location_name, lat, lon):
    """What is actually on the ground, from OSM. Falls back to a preset."""
    try:
        return osmdata.get_site(location_name, lat, lon), None
    except Exception as exc:
        return (E.build_preset("downtown"), {"n_ways": 0}), str(exc)


@st.cache_data(show_spinner="Finding location...")
def geocode(query):
    return fgdata.geocode_us(query)


with st.sidebar:
    st.session_state.dark = st.toggle("Dark mode", value=st.session_state.dark)

    st.markdown('<div class="eyebrow" style="margin-top:0">'
                'Site &mdash; anywhere in the USA</div>', unsafe_allow_html=True)

    qcols = st.columns(len(fgdata.LOCATIONS))
    for i, name in enumerate(fgdata.LOCATIONS):
        if qcols[i].button(name.split(",")[0], key=f"quick_{i}", width="stretch"):
            lat, lon = fgdata.LOCATIONS[name]
            st.session_state.location = {"name": name, "lat": lat, "lon": lon}
            st.session_state.location_error = None
            st.rerun()

    with st.form("loc_search", clear_on_submit=False):
        query = st.text_input("Search", placeholder="City, state - e.g. Austin, TX",
                              label_visibility="collapsed")
        submitted = st.form_submit_button("Search this location", width="stretch")
    if submitted and query.strip():
        hit = geocode(query)
        if hit is None:
            st.session_state.location_error = f'No US match for "{query}".'
        else:
            lat, lon, display_name = hit
            st.session_state.location = {"name": display_name, "lat": lat, "lon": lon}
            st.session_state.location_error = None
            st.rerun()
    if st.session_state.location_error:
        st.markdown(f'<div class="flag">{st.session_state.location_error}</div>',
                    unsafe_allow_html=True)

    st.markdown(
        f'<div class="ann" style="border-top:none;padding:.2rem 0 .1rem">'
        f'Showing <b>{st.session_state.location["name"]}</b></div>',
        unsafe_allow_html=True)

    source = st.radio(
        "Existing condition", ["Real site (OpenStreetMap)", "Synthetic preset"],
        label_visibility="collapsed")

    preset = None
    if source == "Synthetic preset":
        preset = st.selectbox(
            "Preset", list(E.PRESETS),
            format_func=lambda k: E.PRESETS[k]["label"],
            label_visibility="collapsed")

    st.markdown('<div class="eyebrow">Materials</div>', unsafe_allow_html=True)
    for group, items in E.palette().items():
        st.markdown(
            f'<div style="font-family:IBM Plex Mono,monospace;font-size:.55rem;'
            f'letter-spacing:.14em;text-transform:uppercase;color:{INK_60};'
            f'margin:.6rem 0 .25rem">{group}</div>', unsafe_allow_html=True)
        for key, label, _ in items:
            on = st.session_state.material == key
            sw, btn = st.columns([1, 6], gap="small")
            with sw:
                st.markdown(plandraw.swatch_svg(key, 24, paper=PAPER, ink=INK,
                                                rule=RULE),
                            unsafe_allow_html=True)
            with btn:
                if st.button(("● " if on else "○ ") + label,
                             key=f"mat_{key}", width="stretch"):
                    st.session_state.material = key
                    st.rerun()

    st.markdown('<div class="eyebrow">Brush</div>', unsafe_allow_html=True)
    st.session_state.brush = st.slider(
        "cells", 1, 6, st.session_state.brush, label_visibility="collapsed")

    st.markdown('<div class="eyebrow">Edit site</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="ann" style="border-top:none;padding:0 0 .5rem">'
        f'Clear removes every material - the site\'s real buildings included -'
        f' down to open ground, so you can build up a scenario from scratch. '
        f'The existing-condition reading used for the temperature comparison '
        f'stays fixed either way.</div>', unsafe_allow_html=True)
    ec1, ec2 = st.columns(2, gap="small")
    with ec1:
        if st.button("Clear to blank", width="stretch"):
            st.session_state.grid = np.full((E.GRID_N, E.GRID_N),
                                            E.DEFAULT_MATERIAL, dtype=object)
            st.rerun()
    with ec2:
        if st.button("Revert to existing", width="stretch"):
            st.session_state.grid = st.session_state.baseline_grid.copy()
            st.rerun()

    warn = E.WARNINGS.get(st.session_state.material)
    if warn:
        st.markdown(f'<div class="flag">{warn}</div>', unsafe_allow_html=True)


# ------------------------------------------------- resolve existing condition

loc = st.session_state.location
location_name, lat, lon = loc["name"], loc["lat"], loc["lon"]

if source == "Synthetic preset":
    site_key = f"preset:{preset}"
    base_grid, site_stats, site_err = E.build_preset(preset), None, None
else:
    site_key = f"osm:{location_name}"
    (base_grid, site_stats), site_err = site_grid(location_name, lat, lon)

if st.session_state.site != site_key:
    st.session_state.site = site_key
    st.session_state.baseline_grid = base_grid.copy()
    st.session_state.grid = base_grid.copy()
    st.rerun()


# --------------------------------------------------------------- basemap

@st.cache_data(show_spinner="Reading FortyGuard measurements... "
                            "(a new location can take up to 2 minutes)")
def baseline_field(location_name, lat, lon):
    data = fgdata.get_plot(location_name, lat, lon, 1000, date="2024-07-15")
    if not data:
        return np.full((E.GRID_N, E.GRID_N), 34.5), None
    y, x = np.mgrid[0:E.GRID_N, 0:E.GRID_N]
    ramp = (x + y) / (2 * (E.GRID_N - 1)) - 0.5
    return data["peak_c"] + ramp * data.get("peak_spread", 0.0), data


measured, meta = baseline_field(location_name, lat, lon)
result = E.evaluate(st.session_state.grid, st.session_state.baseline_grid,
                    measured)


# --------------------------------------------------------------- masthead

st.markdown(f"""
<div class="masthead">
  <div>
    <span class="wordmark">Blockwise</span>
    <span class="strap" style="margin-left:1rem">District heat sandbox</span>
  </div>
  <div class="strap">
    {location_name} &nbsp;&middot;&nbsp; {E.PLOT_M}&times;{E.PLOT_M} m
    &nbsp;&middot;&nbsp; {E.GRID_N}&times;{E.GRID_N} cells @ {E.CELL_M} m
  </div>
</div>
""", unsafe_allow_html=True)


plan, block = st.columns([3, 2], gap="large")

# ------------------------------------------------------------------- plan

with plan:
    view = st.radio("view", ["Materials", "Temperature"], horizontal=True,
                    label_visibility="collapsed")

    if view == "Materials":
        fig = plandraw.plan_figure(st.session_state.grid, height=580,
                                   paper=PAPER, ink=INK)
    else:
        fig = plandraw.thermal_figure(result.projected_field, height=580,
                                      paper=PAPER, ink=INK,
                                      cool=_T["THERMAL_COOL"],
                                      warm=_T["THERMAL_WARM"])

    ev = st.plotly_chart(fig, width="stretch", on_select="rerun",
                         key="plan_click", selection_mode=("points",))

    st.markdown(
        f'<div style="font-family:IBM Plex Mono,monospace;font-size:.62rem;'
        f'letter-spacing:.1em;text-transform:uppercase;color:{INK_60};'
        f'margin-top:-.4rem">Click to place '
        f'{E.MATERIALS[st.session_state.material]["label"].lower()}'
        f' &nbsp;&middot;&nbsp; brush {st.session_state.brush}</div>',
        unsafe_allow_html=True)

    sel = getattr(ev, "selection", None) or (
        ev.get("selection") if isinstance(ev, dict) else None)
    pts = (sel or {}).get("points", [])
    if pts:
        r, c = int(round(pts[0]["y"])), int(round(pts[0]["x"]))
        b = st.session_state.brush - 1
        st.session_state.grid[
            max(0, r - b // 2):min(E.GRID_N, r + b // 2 + 1),
            max(0, c - b // 2):min(E.GRID_N, c + b // 2 + 1)
        ] = st.session_state.material
        st.rerun()


# ------------------------------------------------------------ title block

with block:
    band = (result.delta_high - result.delta_low) / 2
    span = max(abs(result.delta_c), 0.001)
    m_pct = 100 * result.measured_c / (result.measured_c + span)

    if meta:
        prov = (f"Mean daily peak across <b>{meta['n_tiles']}</b> tiles, "
                f"{meta['date']}. Spatial variation "
                f"<b>{meta['peak_spread']:.2f} °C</b>. Tiles are 100 m; the "
                f"{E.CELL_M} m grid is interpolated.")
    else:
        prov = "No measurement available - using a placeholder baseline."

    if site_err:
        site_prov = (f"OpenStreetMap unavailable ({site_err[:60]}). Showing a "
                     f"synthetic preset instead.")
    elif site_stats:
        site_prov = (f"Existing condition from <b>OpenStreetMap</b> - "
                     f"{site_stats['n_ways']} features, "
                     f"{site_stats['n_buildings']} buildings. Roof materials "
                     f"and paving type are assumed, not observed.")
    else:
        site_prov = "Existing condition is a <b>synthetic preset</b>, not a real site."

    st.markdown(f"""
<div class="titleblock">
  <div class="tb-head">Temperature &middot; peak daytime &middot; air at 2 m</div>
  <div class="tb-grid">
    <div class="tb-cell">
      <span class="tb-label">FortyGuard measured</span>
      <span class="tb-value v-measured">{result.measured_c:.1f}<span class="u">°C</span></span>
    </div>
    <div class="tb-cell">
      <span class="tb-label">Modelled change</span>
      <span class="tb-value v-modelled">{result.delta_c:+.1f}</span><span class="tb-band">&plusmn;{band:.1f}</span>
    </div>
    <div class="tb-cell">
      <span class="tb-label">Projected</span>
      <span class="tb-value v-projected">{result.projected_c:.1f}<span class="u">°C</span></span>
    </div>
  </div>
  <div class="scale">
    <div class="scale-track">
      <div class="scale-measured" style="width:{m_pct:.1f}%"></div>
      <div class="scale-modelled" style="width:{100 - m_pct:.1f}%"></div>
    </div>
    <div class="scale-key">
      <span><span class="swatch sw-m"></span>Measured</span>
      <span><span class="swatch sw-d"></span>Modelled &mdash; not a measurement</span>
    </div>
  </div>
  <div class="ann">{prov}</div>
  <div class="ann">{site_prov}</div>
</div>
""", unsafe_allow_html=True)

    for note in result.notes:
        st.markdown(f'<div class="flag">{note}</div>', unsafe_allow_html=True)

    terms = {k: v for k, v in result.breakdown.items() if abs(v) > 0.005}
    if terms:
        st.markdown('<div class="eyebrow">Contribution by mechanism</div>',
                    unsafe_allow_html=True)
        order = sorted(terms.items(), key=lambda x: x[1])
        st.plotly_chart(go.Figure(go.Bar(
            x=[v for _, v in order], y=[k for k, _ in order], orientation="h",
            marker=dict(color=MODELLED, line=dict(color=INK, width=1)),
            text=[f"{v:+.2f}" for _, v in order], textposition="outside",
            textfont=dict(family="IBM Plex Mono, monospace", size=10),
        )).update_layout(
            height=34 * len(order) + 40, margin=dict(l=0, r=34, t=0, b=20),
            paper_bgcolor=PAPER, plot_bgcolor=PAPER, showlegend=False,
            font=dict(family="IBM Plex Mono, monospace", size=10, color=INK),
            xaxis=dict(title="", zerolinecolor=INK, gridcolor=RULE),
            yaxis=dict(title=""),
        ), width="stretch")

    n, b0 = result.now, result.base
    st.markdown('<div class="eyebrow">Site composition</div>',
                unsafe_allow_html=True)
    rows = [("Canopy", f"{b0.canopy_pp:.0f}%", f"{n.canopy_pp:.0f}%"),
            ("Impervious", f"{b0.impervious_pp:.0f}%", f"{n.impervious_pp:.0f}%"),
            ("Building", f"{b0.building_pp:.0f}%", f"{n.building_pp:.0f}%"),
            ("Mean albedo", f"{b0.mean_albedo:.2f}", f"{n.mean_albedo:.2f}"),
            ("Trees", f"{b0.tree_count:,}", f"{n.tree_count:,}")]
    body = "".join(
        f'<tr><td style="padding:.28rem .5rem;color:{INK_60}">{a}</td>'
        f'<td style="padding:.28rem .5rem;text-align:right;color:{INK_60}">{b}</td>'
        f'<td style="padding:.28rem .5rem;text-align:right;font-weight:600">{c}</td>'
        f'</tr>' for a, b, c in rows)
    hdr = ("padding:.3rem .5rem;text-align:right;font-size:.55rem;"
           f"letter-spacing:.12em;color:{INK_60};font-weight:500")
    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;'
        f'font-family:IBM Plex Mono,monospace;font-size:.72rem;'
        f'border:1px solid {RULE}">'
        f'<tr style="border-bottom:1px solid {RULE}">'
        f'<th style="{hdr};text-align:left"></th>'
        f'<th style="{hdr}">EXISTING</th>'
        f'<th style="{hdr}">PROPOSED</th></tr>{body}</table>',
        unsafe_allow_html=True)

    with st.expander("Method and limits"):
        st.markdown("""
Every coefficient is **air temperature at 2 m**, not land surface temperature.
Surface effects run roughly twice as large; quoting them would make this tool
badly over-optimistic.

Coefficients carry a status:

**literature_central** — a literature-average estimate, real but climate- and
scale-dependent. *Canopy, cool pavement, water.*

**engineering_value** — a defensible choice inside the published range.
*Albedo: credible estimates span 0.09 to 0.6 °C per +0.1, a factor of six.*

**calibration_parameter** — our own tuning knob, no universal basis.
*Impervious, grass, building density.*

The 40% canopy threshold follows Ziter et al. 2019 (PNAS, Madison WI), which
found a marked jump in cooling above roughly that level. The two slopes either
side of it are ours, not theirs.

Cooling is capped at −4 °C as an engineering safeguard, not a literature
maximum. Building morphology is the least certain part of the model — shade,
sky-view factor and street-canyon effects are not simulated.
        """)
