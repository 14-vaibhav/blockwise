"""
The plan drawing.

Renders the grid as an architect would draw it rather than as a heatmap:
tree canopies with trunks, buildings as blocks with a roof line, water with a
shoreline, hatched paving. Built from plotly layout shapes so click detection
still works through an invisible heatmap underneath.

Shape count matters. A 30x30 grid is 900 cells; drawing four shapes each would
be 3,600 and Streamlit would crawl. So cells are grouped into runs where
possible and detail drops out below a size threshold.
"""

import numpy as np
import plotly.graph_objects as go

import engine as E

PAPER = "#E9EAE5"
INK = "#16181A"
RULE = "#C3C5BD"

# Ground tone under each material - the drawing's flat wash.
GROUND = {
    "tree_dense": "#CFD9C4", "tree_scattered": "#D6DDCB", "grass": "#DCE2CE",
    "shrub": "#D3DAC6", "bare_soil": "#DED6C8",
    "water": "#C6D5DE", "wetland": "#CBDBD9",
    "asphalt": "#BCBDB8", "concrete": "#D2D3CE", "light_paving": "#E2E3DE",
    "permeable": "#D6D2C8", "gravel": "#DAD6CC", "parking_treed": "#C7CCC2",
    "building_dark": "#B0AAA4", "building_light": "#C3BDB6",
    "building_cool": "#E4E4E2", "building_green": "#BFC9B2",
    "building_tall": "#A29C97",
}

CANOPY = {"tree_dense": "#2F5D31", "tree_scattered": "#4A7A45",
          "parking_treed": "#4A7A45", "shrub": "#6B8A55",
          "building_green": "#5C7A46", "wetland": "#4E8078"}

TREE_R = {"tree_dense": 0.34, "tree_scattered": 0.20,
          "parking_treed": 0.16, "shrub": 0.13, "wetland": 0.10,
          "building_green": 0.0}


def _rect(x0, y0, x1, y1, fill, line=None, width=0.6, layer="below"):
    return dict(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                fillcolor=fill, layer=layer,
                line=dict(color=line or fill, width=width if line else 0))


def _circle(cx, cy, r, fill, line=None, width=0.6):
    return dict(type="circle", x0=cx - r, y0=cy - r, x1=cx + r, y1=cy + r,
                fillcolor=fill, layer="above",
                line=dict(color=line or fill, width=width if line else 0))


_KEYS = list(E.MATERIALS)
_GROUND_SCALE = [[i / max(1, len(_KEYS) - 1), GROUND.get(k, "#D2D3CE")]
                 for i, k in enumerate(_KEYS)]


def plan_figure(grid, height=600, detail=True, paper=PAPER, ink=INK, mask=None):
    """
    A drawn plan of the grid.

    The ground wash is a heatmap rather than 900 rects - that halves the
    shape count. Click detection is a separate invisible Scatter marker per
    cell (see below): Streamlit's on_select doesn't reliably fire on Heatmap
    traces. Only the things that need to look drawn (trees, buildings,
    water) become shapes.

    paper/ink are the sheet's background and line colour - overridable so the
    same drawing re-themes for dark mode. Material colours (GROUND, CANOPY,
    per-material fills) stay constant: a material's true colour shouldn't
    change with the app's theme, only the paper it's drawn on.

    mask, when given, marks which cells are actually inside a circle/polygon
    selection (grid.shape need not be square). Cells outside get no shapes
    and no ground-wash colour - they fade to bare paper, showing the real
    boundary of the selected area rather than its square bounding box.
    """
    rows, cols = grid.shape
    shapes = []

    # 2. buildings: block with a roof line, drawn as a solid mass
    for (r, c), key in np.ndenumerate(grid):
        if mask is not None and not mask[r, c]:
            continue
        if not key.startswith("building"):
            continue
        p = E.MATERIALS[key]
        tall = p.get("height_m", 8) >= 20
        inset = 0.10 if not tall else 0.06
        shapes.append(_rect(c - 0.5 + inset, r - 0.5 + inset,
                            c + 0.5 - inset, r + 0.5 - inset,
                            p["colour"], ink, 0.8, layer="above"))
        if detail:
            # roof ridge - reads as a pitched mass at a glance
            shapes.append(dict(
                type="line", layer="above",
                x0=c - 0.5 + inset, y0=r, x1=c + 0.5 - inset, y1=r,
                line=dict(color=paper if not tall else "#6E6862", width=0.7)))

    # 3. water: shoreline outline over the wash
    for (r, c), key in np.ndenumerate(grid):
        if mask is not None and not mask[r, c]:
            continue
        if key not in ("water", "wetland"):
            continue
        shapes.append(_rect(c - 0.5, r - 0.5, c + 0.5, r + 0.5,
                            E.MATERIALS[key]["colour"], "#0F3D52", 0.7,
                            layer="above"))

    # 4. canopy: circles, with a trunk when there is room to see it
    for (r, c), key in np.ndenumerate(grid):
        if mask is not None and not mask[r, c]:
            continue
        rad = TREE_R.get(key, 0.0)
        if rad <= 0:
            continue
        col = CANOPY.get(key, "#2F5D31")
        if key == "tree_dense":
            # three overlapping crowns reads as a canopy rather than a dot
            for dx, dy, k in ((-0.16, 0.10, 0.62), (0.17, 0.13, 0.55),
                              (0.0, -0.14, 1.0)):
                shapes.append(_circle(c + dx, r + dy, rad * k, col, ink, 0.5))
        elif key == "parking_treed":
            shapes.append(_circle(c - 0.22, r - 0.18, rad, col, ink, 0.5))
            shapes.append(_circle(c + 0.22, r + 0.20, rad, col, ink, 0.5))
        else:
            shapes.append(_circle(c, r, rad, col, ink, 0.5))

    # 5. sheet border
    shapes.append(_rect(-0.5, -0.5, cols - 0.5, rows - 0.5, "rgba(0,0,0,0)",
                        ink, 1.4, layer="above"))

    labels = np.vectorize(lambda k: E.MATERIALS[k]["label"])(grid)
    idx = np.vectorize(_KEYS.index)(grid).astype(float)
    if mask is not None:
        idx[~mask] = np.nan

    fig = go.Figure(go.Heatmap(
        z=idx, zmin=0, zmax=len(_KEYS) - 1,
        colorscale=_GROUND_SCALE, showscale=False, hoverinfo="skip"))

    # Click target: Plotly's click/box-select events are unreliable on
    # Heatmap traces in Streamlit (a longstanding Streamlit + Plotly.js gap -
    # streamlit/streamlit#8760, #8933), so the heatmap above is drawing only.
    # A Scatter trace with one square marker per selectable cell is the
    # combination Streamlit's on_select actually supports, and it also lets
    # each click target be sized to fill its cell rather than a single pixel.
    ys, xs = (np.nonzero(mask) if mask is not None
             else np.mgrid[0:rows, 0:cols].reshape(2, -1))
    cell_px = max(8, (height - 8) / rows * 0.92)
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers",
        marker=dict(size=cell_px, symbol="square", opacity=0.02, color=ink),
        text=labels[ys, xs], hovertemplate="%{text}<extra></extra>",
        hoverinfo="text", showlegend=False))

    fig.update_layout(
        shapes=shapes, height=height, margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor=paper, plot_bgcolor=paper, dragmode=False,
        clickmode="event+select",
        xaxis=dict(visible=False, showgrid=False, range=[-0.6, cols - 0.4],
                   scaleanchor="y", constrain="domain"),
        yaxis=dict(visible=False, showgrid=False, range=[rows - 0.4, -0.6],
                   constrain="domain"),
        font=dict(family="IBM Plex Mono, monospace", color=ink),
    )
    return fig


def thermal_figure(field, height=600, paper=PAPER, ink=INK,
                   cool="#1B4B52", warm="#8C2F1E"):
    """The same plot as a temperature surface."""
    n = field.shape[0]
    fig = go.Figure(go.Heatmap(
        z=field, colorscale=[[0, cool], [0.45, paper], [1, warm]],
        colorbar=dict(title=dict(text="°C", font=dict(size=10)), thickness=10,
                      outlinewidth=1, outlinecolor=ink, tickfont=dict(size=9),
                      len=0.6),
        hovertemplate="%{z:.2f} °C<extra></extra>"))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor=paper, plot_bgcolor=paper, dragmode=False,
        shapes=[_rect(-0.5, -0.5, n - 0.5, n - 0.5, "rgba(0,0,0,0)",
                      ink, 1.4, layer="above")],
        xaxis=dict(visible=False, showgrid=False, scaleanchor="y",
                   constrain="domain"),
        yaxis=dict(visible=False, showgrid=False, autorange="reversed",
                   constrain="domain"),
        font=dict(family="IBM Plex Mono, monospace", color=ink),
    )
    return fig


def swatch_svg(key, size=26, paper=PAPER, ink=INK, rule=RULE):
    """A miniature of how the material draws, for the palette rail."""
    p = E.MATERIALS[key]
    g = GROUND.get(key, "#D2D3CE")
    body = f'<rect width="{size}" height="{size}" fill="{g}"/>'

    if key.startswith("building"):
        i = size * 0.16
        body += (f'<rect x="{i}" y="{i}" width="{size - 2 * i}" '
                 f'height="{size - 2 * i}" fill="{p["colour"]}" '
                 f'stroke="{ink}" stroke-width="1"/>'
                 f'<line x1="{i}" y1="{size / 2}" x2="{size - i}" '
                 f'y2="{size / 2}" stroke="{paper}" stroke-width="1"/>')
    elif key in ("water", "wetland"):
        body += (f'<rect width="{size}" height="{size}" '
                 f'fill="{p["colour"]}" stroke="#0F3D52" stroke-width="1"/>')
    elif TREE_R.get(key, 0) > 0:
        col = CANOPY.get(key, "#2F5D31")
        r = size * TREE_R[key]
        body += (f'<circle cx="{size / 2}" cy="{size / 2}" r="{r}" '
                 f'fill="{col}" stroke="{ink}" stroke-width="0.8"/>')

    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
            f'style="vertical-align:middle;border:1px solid {rule}">'
            f'{body}</svg>')
