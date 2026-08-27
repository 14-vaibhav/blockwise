"""
Blockwise physics engine.

Implements COEFFICIENTS.md v2. Grid in, temperature delta out.

HARD RULES
  1. No Streamlit import in this file, ever. Return values; do not draw.
  2. Every coefficient carries a STATUS. Three kinds:
       literature_central   - literature-average estimate, real but context-dependent
       engineering_value    - defensible choice inside the literature range
       calibration_parameter- our own tuning knob, no universal basis
     Presenting a calibration parameter as a measured constant is what a
     domain-expert judge catches. Keep the labels visible in the UI.
  3. All values are AIR temperature at ~2 m. Never land surface temperature.
  4. Scope: US, daytime, summer, clear sky, single afternoon snapshot.
  5. MAX_COOLING is an engineering safeguard, not a literature maximum.
     Do not relax it to make a demo number look better.

THE CALCULATION
  1. composition of the current grid
  2. composition of the baseline preset
  3. coefficients applied to the DIFFERENCE, not the absolute
  4. spatial field via convolution, RESCALED so its mean equals the scalar
  5. added to the FortyGuard measured field
  6. clamped

Step 3 is what stops double-counting: planting trees on an already-treed
block does little; planting on asphalt does a lot.
Step 4 is the subtle one: the kernel shapes the picture, the coefficients
set the magnitude. Never let the convolution decide the number.
"""

from collections import namedtuple
from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import convolve

# ---------------------------------------------------------------- geometry
#
# Set by the API probe, 24 Aug 2026:
#   - FortyGuard granularity accepts ONLY 60, 80 or 100 m
#   - a 96 m plot returns zero tiles
#   - spatial spread grows with plot size: Manhattan 0.75 C at 500 m,
#     1.12 at 1 km, 1.58 at 2 km, 1.84 at 3 km
#
# The painting grid is finer than the measurement grid. The baseline is
# interpolated from 100 m tiles onto 40 m cells. SAY SO in the UI: those
# cells are interpolated, not measured.

PLOT_M = 1200
CELL_M = 40
GRID_N = PLOT_M // CELL_M          # 30
CELL_AREA_M2 = CELL_M ** 2         # 1,600
TREES_PER_CELL = 20                # ~9 m spacing across a full cell


# ------------------------------------------------------------ coefficients

Coeff = namedtuple("Coeff", ["central", "low", "high", "status", "confidence"])

LIT = "literature_central"
ENG = "engineering_value"
CAL = "calibration_parameter"


# --- canopy -----------------------------------------------------------------
# -0.30 C per +10 percentage points. Direction well established; magnitude
# depends on climate, scale, baseline canopy, wind, hour, morphology.
# WRI meta-analysis; Krayenhoff et al. 2021. Low anchor Boston 2025
# (-0.07 C per +0.1 fraction). High anchor Calgary 2025 heatwave hotspots.
CANOPY_PER_PP = Coeff(-0.030, -0.010, -0.080, LIT, "medium-high")

# Ziter et al. 2019 (PNAS, Madison WI) observed a marked jump in cooling
# above ~40% canopy at 60-90 m scale.
#
# WARNING: the piecewise form below is a BLOCKWISE APPROXIMATION INSPIRED BY
# that finding. Ziter did not measure these two slopes. Say so in the README.
# Worth building anyway: it is the best moment in the demo and it is grounded
# in a real published non-linearity even though the exact slope is ours.
CANOPY_THRESHOLD_PP = 40.0
CANOPY_PER_PP_ABOVE = Coeff(-0.060, -0.020, -0.150, ENG, "medium")

# --- albedo -----------------------------------------------------------------
# Revised in v2 of COEFFICIENTS.md. The credible range spans a factor of six:
#   Santamouris & Fiorito 2021, 14 studies: ~0.09 C per +0.1 albedo afternoon
#   Santamouris et al. 2018 (Sydney):       ~0.5  C per +0.1
#   Krayenhoff, across climate zones:        0.2-0.9, median 0.6 clear sky
# We model an afternoon snapshot, so the peak value is the one in use.
# The band MUST stay wide and visible - this is not a well-constrained number.
ALBEDO_PER_0P1 = Coeff(-0.60, -0.09, -0.90, ENG, "medium")

# Sanity check for the tests: whole-city cool roof deployment yields only
# 0.4-0.7 C (Atlanta 0.38, Detroit 0.42, Phoenix 0.66). Parcel numbers may
# exceed this, but not by much.

# --- impervious -------------------------------------------------------------
# NOT literature-derived. The literature firmly supports impervious surfaces
# as a major heat driver, but there is no universal linear C-per-percent law.
# This is a tuning knob. Do not cite it as measured.
IMPERVIOUS_PER_PP = Coeff(+0.030, +0.010, +0.050, CAL, "low")

# Impervious and albedo physically overlap - thermal mass vs radiative.
# Cap their combined contribution rather than summing at full strength.
PAVING_CAP_C = 1.5

# --- grass ------------------------------------------------------------------
# Vegetation cooling is well supported; this coefficient is not. Roughly a
# third of the tree value is a reasonable modelling choice - trees give shade
# plus transpiration, grass only transpiration.
GRASS_PER_PP = Coeff(-0.010, -0.005, -0.015, CAL, "low")

# --- water ------------------------------------------------------------------
# Revised DOWN from -0.50 in v1. The most over-claimed intervention in the
# literature. Jacobs et al. 2020 (REALCOOL): typical surrounding afternoon
# air cooling ~0.2 C, max street-level ~0.6 C, max over water ~0.8 C.
# Their conclusion: small urban water bodies are effectively negligible for
# design practice unless combined with shade, fountains or ventilation.
WATER_PER_CELL = Coeff(-0.20, -0.05, -0.60, LIT, "medium")

# Small but real. Model it rather than assuming water always cools.
WATER_NIGHT_WARMING = +0.30

# Distance decay is OUR choice, not a measured universal cutoff.
WATER_DECAY_CELLS = 2

# --- buildings --------------------------------------------------------------
# Weakest part of the model. Buildings simultaneously shade, store heat,
# reduce sky-view factor, alter ventilation and create canyon effects. The
# net effect is geometry- and hour-dependent and NOT additive.
#
# The PRD puts solar geometry and shadow casting out of scope and that
# decision stands - it is the most likely source of day-6 scope creep.
# Naming the limitation is worth more than half-implementing the fix.
BUILDING_PER_PP = Coeff(+0.020, +0.005, +0.040, CAL, "low")

# --- mean radiant temperature ----------------------------------------------
# Reflective paving bounces sunlight into people. Air temperature falls
# slightly while MRT rises - the net effect on a pedestrian can be NEGATIVE.
# King et al. 2026 (Phoenix, MaRTy carts): +2.4 to +3.0 C at midday.
# ASU/City of Phoenix reported 5.8 F (~3.2 C) mid-street at noon.
#
# This is one of the strongest credibility details available. Most teams
# will treat cool pavement as unambiguously good.
MRT_PER_0P1_ALBEDO = +0.45

# --- global cap -------------------------------------------------------------
# ENGINEERING SAFEGUARD, not a literature maximum. Whole-city interventions
# rarely exceed 1-2 C; parcel-scale best cases reach 4-5 C. If the engine
# outputs -7 C, something double-counted and the cap caught it.
MAX_COOLING_C = -4.0


# --------------------------------------------------------------- materials
#
# albedo values stored as (min, default, max) in COEFFICIENTS.md section 2.
# Only the default is used here; the min/max feed the uncertainty band.

MATERIALS = {
    # --- vegetation ---
    "tree_dense": dict(
        label="Tree canopy (dense)", group="Vegetation", colour="#1b5e20",
        canopy=1.00, impervious=0.0, albedo=0.18, trees=TREES_PER_CELL),
    "tree_scattered": dict(
        label="Scattered trees", group="Vegetation", colour="#4caf50",
        canopy=0.40, impervious=0.0, albedo=0.20, trees=8),
    "grass": dict(
        label="Grass / lawn", group="Vegetation", colour="#8bc34a",
        canopy=0.0, impervious=0.0, albedo=0.25, grass=1.0),
    "shrub": dict(
        label="Shrub / meadow", group="Vegetation", colour="#689f38",
        canopy=0.15, impervious=0.0, albedo=0.22, grass=0.85),
    "bare_soil": dict(
        label="Bare soil", group="Vegetation", colour="#a1887f",
        canopy=0.0, impervious=0.10, albedo=0.17),

    # --- water ---
    "water": dict(
        label="Open water", group="Water", colour="#1976d2",
        canopy=0.0, impervious=0.0, albedo=0.06, water=1.0),
    "wetland": dict(
        label="Wetland / rain garden", group="Water", colour="#4dd0e1",
        canopy=0.10, impervious=0.0, albedo=0.15, water=0.5, grass=0.5),

    # --- paving ---
    "asphalt": dict(
        label="Asphalt", group="Paving", colour="#212121",
        canopy=0.0, impervious=1.0, albedo=0.10),
    "concrete": dict(
        label="Concrete", group="Paving", colour="#9e9e9e",
        canopy=0.0, impervious=1.0, albedo=0.30),
    "light_paving": dict(
        label="Light / reflective paving", group="Paving", colour="#e0e0e0",
        canopy=0.0, impervious=1.0, albedo=0.40),
    "permeable": dict(
        label="Permeable paving", group="Paving", colour="#bcaaa4",
        canopy=0.0, impervious=0.35, albedo=0.28),
    "gravel": dict(
        label="Gravel", group="Paving", colour="#d7ccc8",
        canopy=0.0, impervious=0.60, albedo=0.25),
    "parking_treed": dict(
        label="Parking with tree islands", group="Paving", colour="#546e7a",
        canopy=0.30, impervious=0.70, albedo=0.16, trees=6),

    # --- buildings ---
    "building_dark": dict(
        label="Building, dark roof", group="Buildings", colour="#3e2723",
        canopy=0.0, impervious=1.0, albedo=0.12, building=1.0, height_m=8),
    "building_light": dict(
        label="Building, light roof", group="Buildings", colour="#795548",
        canopy=0.0, impervious=1.0, albedo=0.16, building=1.0, height_m=8),
    "building_cool": dict(
        label="Building, cool roof", group="Buildings", colour="#eceff1",
        canopy=0.0, impervious=1.0, albedo=0.75, building=1.0, height_m=8),
    "building_green": dict(
        label="Building, green roof", group="Buildings", colour="#558b2f",
        canopy=0.0, impervious=1.0, albedo=0.20, building=1.0, height_m=8,
        grass=0.8),
    "building_tall": dict(
        label="Tower (20 m+)", group="Buildings", colour="#1a1a1a",
        canopy=0.0, impervious=1.0, albedo=0.14, building=1.0, height_m=24),
}

DEFAULT_MATERIAL = "grass"

_BASE_PROPS = dict(canopy=0.0, impervious=0.0, albedo=0.25, grass=0.0,
                   water=0.0, building=0.0, trees=0, height_m=0.0)


def props(key):
    """Material properties, with unspecified fields defaulted to zero."""
    if key not in MATERIALS:
        raise KeyError(f"unknown material {key!r}")
    return {**_BASE_PROPS, **MATERIALS[key]}


def palette():
    """{group: [(key, label, colour)]} for the UI."""
    out = {}
    for k, v in MATERIALS.items():
        out.setdefault(v["group"], []).append((k, v["label"], v["colour"]))
    return out


# UI caveats. Green roof is a COST result, not a scientific claim - the
# literature does not support "green roofs don't work".
WARNINGS = {
    "light_paving":
        "Cools air slightly but raises radiant heat on pedestrians by ~2.7 C "
        "at midday. Suited to parking and low-footfall streets, not sidewalks.",
    "water":
        "Small water bodies cool weakly by day (~0.2 C typical) and can warm "
        "the area slightly at night.",
    "building_green":
        "Outdoor air-temperature benefit is context-dependent and uncertain. "
        "Cool-roof coating usually achieves similar cooling for less money.",
    "building_tall":
        "Building morphology is the least certain part of this model. Shade, "
        "sky-view factor and canyon effects are not simulated.",
}


# ----------------------------------------------------------------- presets

PRESET_SEED = 20260830

PRESETS = {
    "bare_lot": dict(label="Bare lot / vacant",
                     impervious=0.10, canopy=0.05, building=0.00),
    "parking_lot": dict(label="Parking lot / big-box retail",
                        impervious=0.85, canopy=0.03, building=0.15),
    "low_density": dict(label="Low-density housing",
                        impervious=0.45, canopy=0.25, building=0.20),
    "downtown": dict(label="Dense built-up / downtown",
                     impervious=0.90, canopy=0.08, building=0.55),
    "parkland": dict(label="Open parkland / campus",
                     impervious=0.05, canopy=0.10, building=0.02),
}


def build_preset(key, n=GRID_N):
    """
    Fill a grid so it reads as a real district: buildings as rectangles
    first, then paving, then scattered canopy.

    Fixed seed. The same preset must render identically every run or the
    demo is not reproducible.
    """
    if key not in PRESETS:
        raise KeyError(f"unknown preset {key!r}")
    spec = PRESETS[key]
    rng = np.random.default_rng(PRESET_SEED)

    grid = np.full((n, n), "grass", dtype=object)
    total = n * n

    # buildings as blocks, not noise
    want_building = int(total * spec["building"])
    placed = 0
    guard = 0
    while placed < want_building and guard < 500:
        guard += 1
        h, w = rng.integers(2, 5), rng.integers(2, 6)
        r, c = rng.integers(0, max(1, n - h)), rng.integers(0, max(1, n - w))
        block = grid[r:r + h, c:c + w]
        if (block == "grass").all():
            grid[r:r + h, c:c + w] = "building_dark"
            placed += block.size

    # paving fills the rest of the impervious budget
    want_paved = int(total * spec["impervious"]) - placed
    free = np.argwhere(grid == "grass")
    rng.shuffle(free)
    for r, c in free[:max(0, want_paved)]:
        grid[r, c] = "asphalt"

    # canopy scattered over whatever remains
    want_canopy = int(total * spec["canopy"])
    free = np.argwhere(grid == "grass")
    rng.shuffle(free)
    for r, c in free[:want_canopy]:
        grid[r, c] = "tree_dense"

    return grid


# ------------------------------------------------------------- composition

@dataclass
class Composition:
    canopy_pp: float          # percentage points, 0-100
    impervious_pp: float
    building_pp: float
    grass_pp: float
    mean_albedo: float
    water_cells: int
    tree_count: int


def composition(grid, mask=None):
    """
    Fractional make-up of a grid of material keys.

    mask, when given, restricts the composition to the cells where it is
    True - the cells actually inside a circle/polygon selection, not its
    square bounding grid. Cells outside are excluded entirely, not counted
    as some neutral material, so percentages stay correct.
    """
    cells = grid[mask] if mask is not None else grid.ravel()
    n = cells.size
    acc = dict(canopy=0.0, impervious=0.0, building=0.0,
               grass=0.0, albedo=0.0, water=0.0, trees=0)
    for key in cells:
        p = props(key)
        for f in ("canopy", "impervious", "building", "grass", "albedo", "water"):
            acc[f] += p[f]
        acc["trees"] += p["trees"]
    return Composition(
        canopy_pp=100.0 * acc["canopy"] / n,
        impervious_pp=100.0 * acc["impervious"] / n,
        building_pp=100.0 * acc["building"] / n,
        grass_pp=100.0 * acc["grass"] / n,
        mean_albedo=acc["albedo"] / n,
        water_cells=int(round(acc["water"])),
        tree_count=int(acc["trees"]),
    )


# ------------------------------------------------------------------- delta

def _canopy_cooling(pp, per_pp, per_pp_above):
    """
    Piecewise canopy response. Integrating the two slopes means the delta
    between two canopy levels comes out right automatically, and planting
    on an already-treed block correctly does less.
    """
    below = min(pp, CANOPY_THRESHOLD_PP)
    above = max(0.0, pp - CANOPY_THRESHOLD_PP)
    return below * per_pp + above * per_pp_above


def _band(central, low, high):
    """Order-safe (min, max) - cooling coefficients are negative."""
    return min(central, low, high), max(central, low, high)


def compose_delta(now, base, n_cells=GRID_N * GRID_N):
    """
    Coefficients applied to the DIFFERENCE between current and baseline.

    n_cells is the actual number of cells the compositions were computed
    over (grid.size, or mask.sum() for a circle/polygon selection) - it
    sets how strongly a change in water_cells dilutes across "the plot".
    Defaults to the original calibrated 30x30 grid for callers that don't
    pass it.

    Returns {term: (central, low, high)} in degrees C, plus a special
    "_mrt" entry which is NOT part of the air-temperature total.
    """
    out = {}

    # canopy, piecewise
    vals = []
    for c, ca in ((CANOPY_PER_PP.central, CANOPY_PER_PP_ABOVE.central),
                  (CANOPY_PER_PP.low, CANOPY_PER_PP_ABOVE.low),
                  (CANOPY_PER_PP.high, CANOPY_PER_PP_ABOVE.high)):
        vals.append(_canopy_cooling(now.canopy_pp, c, ca)
                    - _canopy_cooling(base.canopy_pp, c, ca))
    out["canopy"] = (vals[0], *_band(*vals))[:1] + _band(*vals)

    # albedo
    d_alb = (now.mean_albedo - base.mean_albedo) / 0.1
    a = [d_alb * v for v in (ALBEDO_PER_0P1.central,
                             ALBEDO_PER_0P1.low, ALBEDO_PER_0P1.high)]
    out["albedo"] = (a[0], *_band(*a))

    # impervious
    d_imp = now.impervious_pp - base.impervious_pp
    i = [d_imp * v for v in (IMPERVIOUS_PER_PP.central,
                             IMPERVIOUS_PER_PP.low, IMPERVIOUS_PER_PP.high)]
    out["impervious"] = (i[0], *_band(*i))

    # paving cap - impervious and albedo overlap physically
    pav = out["albedo"][0] + out["impervious"][0]
    if abs(pav) > PAVING_CAP_C:
        scale = PAVING_CAP_C / abs(pav)
        for k in ("albedo", "impervious"):
            out[k] = tuple(v * scale for v in out[k])

    # grass
    d_gr = now.grass_pp - base.grass_pp
    g = [d_gr * v for v in (GRASS_PER_PP.central,
                            GRASS_PER_PP.low, GRASS_PER_PP.high)]
    out["grass"] = (g[0], *_band(*g))

    # buildings
    d_bl = now.building_pp - base.building_pp
    b = [d_bl * v for v in (BUILDING_PER_PP.central,
                            BUILDING_PER_PP.low, BUILDING_PER_PP.high)]
    out["building"] = (b[0], *_band(*b))

    # water - per cell, weakly, and only the change
    d_w = now.water_cells - base.water_cells
    frac = d_w / max(1, n_cells) * 10.0     # dilution across the plot
    w = [frac * v for v in (WATER_PER_CELL.central,
                            WATER_PER_CELL.low, WATER_PER_CELL.high)]
    out["water"] = (w[0], *_band(*w))

    # MRT, tracked separately. NOT added to the air-temperature total.
    out["_mrt"] = (d_alb * MRT_PER_0P1_ALBEDO, 0.0, d_alb * MRT_PER_0P1_ALBEDO * 1.3)

    return out


# --------------------------------------------------------------- diffusion
#
# Kernels are ENGINEERING APPROXIMATIONS, not measured constants. At 40 m
# cells a tree's cooling barely reaches its neighbour, so these are much
# tighter than they would be at 3 m.

TREE_KERNEL = np.array([
    [0.05, 0.20, 0.05],
    [0.20, 1.00, 0.20],
    [0.05, 0.20, 0.05],
])

WATER_KERNEL = np.array([
    [0.10, 0.25, 0.40, 0.25, 0.10],
    [0.25, 0.50, 0.70, 0.50, 0.25],
    [0.40, 0.70, 1.00, 0.70, 0.40],
    [0.25, 0.50, 0.70, 0.50, 0.25],
    [0.10, 0.25, 0.40, 0.25, 0.10],
])

LOCAL_KERNEL = np.array([
    [0.05, 0.10, 0.05],
    [0.10, 1.00, 0.10],
    [0.05, 0.10, 0.05],
])


def spatial_field(grid, scalar, mask=None):
    """
    Build a plausible spatial distribution, then RESCALE so its mean equals
    the coefficient-derived scalar.

    The rescale is the whole point. Without it the picture and the number
    drift apart and the readout stops being defensible.

    Works on any grid.shape, not just square - a hand-drawn polygon's
    bounding box need not be square. mask, when given, restricts the
    rescale statistics (mean, spread) to the selected cells, so the empty
    bounding-box corners of a circle/polygon selection don't skew them;
    those cells come back NaN so callers (Plotly heatmaps included) can
    tell "outside the selection" from "inside, near zero".
    """
    rows, cols = grid.shape
    canopy = np.zeros((rows, cols))
    water = np.zeros((rows, cols))
    local = np.zeros((rows, cols))

    for (r, c), key in np.ndenumerate(grid):
        if mask is not None and not mask[r, c]:
            continue
        p = props(key)
        canopy[r, c] = p["canopy"]
        water[r, c] = p["water"]
        local[r, c] = p["albedo"] - 0.25 + p["impervious"] * 0.5

    shape = (convolve(canopy, TREE_KERNEL, mode="nearest") * 1.0
             + convolve(water, WATER_KERNEL, mode="nearest") * 0.6
             + convolve(local, LOCAL_KERNEL, mode="nearest") * 0.4)

    # centre, then rescale to the target mean - using only the selected
    # cells' statistics when masked
    ref = shape[mask] if mask is not None else shape.ravel()
    if np.allclose(ref, ref.mean()):
        out = np.full((rows, cols), scalar)
    else:
        spread = np.abs(ref - ref.mean()).max() or 1.0
        out = (shape - ref.mean()) / spread * abs(scalar) * 0.5 + scalar

    if mask is not None:
        out = np.where(mask, out, np.nan)
    return out


# ------------------------------------------------------------------ result

@dataclass
class Result:
    measured_field: np.ndarray
    delta_field: np.ndarray
    delta_c: float
    delta_low: float
    delta_high: float
    breakdown: dict
    mrt_delta: float
    clamped: bool
    now: Composition = None
    base: Composition = None
    notes: list = field(default_factory=list)

    @property
    def measured_c(self):
        return float(np.nanmean(self.measured_field))

    @property
    def projected_c(self):
        return self.measured_c + self.delta_c

    @property
    def projected_field(self):
        return self.measured_field + self.delta_field

    def readout(self):
        """The three lines the UI shows. Measured and modelled stay separate."""
        return (f"FortyGuard measured   {self.measured_c:6.1f} C\n"
                f"Your changes          {self.delta_c:+6.1f} C  "
                f"(±{(self.delta_high - self.delta_low) / 2:.1f})\n"
                f"{'-' * 34}\n"
                f"Projected             {self.projected_c:6.1f} C")


def evaluate(grid, baseline_grid, measured_field, mask=None):
    """
    Full pipeline. The only function the UI needs to call.

    mask restricts everything - composition, the water dilution term, and
    the spatial field - to the cells actually inside a circle/polygon
    selection, so a hand-drawn area is evaluated as itself, not as its
    square bounding box. Cells outside come back NaN in measured_field/
    delta_field/projected_field, and are excluded from measured_c via
    nanmean. Omit it (the default) to evaluate the whole grid, exactly the
    original behaviour.
    """
    if mask is not None:
        measured_field = np.where(mask, measured_field, np.nan)

    now = composition(grid, mask)
    base = composition(baseline_grid, mask)
    n_cells = int(mask.sum()) if mask is not None else grid.size
    terms = compose_delta(now, base, n_cells)

    mrt = terms.pop("_mrt")[0]

    central = sum(v[0] for v in terms.values())
    low = sum(v[1] for v in terms.values())
    high = sum(v[2] for v in terms.values())

    clamped = False
    if central < MAX_COOLING_C:
        scale = MAX_COOLING_C / central
        central, low, high = MAX_COOLING_C, low * scale, high * scale
        terms = {k: tuple(x * scale for x in v) for k, v in terms.items()}
        clamped = True

    notes = []
    if clamped:
        notes.append("Total cooling hit the -4 C engineering safeguard.")
    if mrt > 0.5:
        notes.append(f"Reflective surfaces raise radiant heat on pedestrians "
                     f"by ~{mrt:.1f} C at midday, even as air temperature falls.")
    if now.water_cells > base.water_cells:
        notes.append("Water bodies may warm the area slightly at night.")

    return Result(
        measured_field=measured_field,
        delta_field=spatial_field(grid, central, mask),
        delta_c=central, delta_low=low, delta_high=high,
        breakdown={k: v[0] for k, v in terms.items()},
        mrt_delta=mrt, clamped=clamped,
        now=now, base=base, notes=notes,
    )


# ------------------------------------------------------------- self-check

if __name__ == "__main__":
    print(f"grid {GRID_N}x{GRID_N}, cell {CELL_M} m, plot {PLOT_M} m, "
          f"{TREES_PER_CELL} trees/cell\n")

    measured = np.full((GRID_N, GRID_N), 34.5)

    base = build_preset("parking_lot")
    c = composition(base)
    print(f"parking lot preset: canopy {c.canopy_pp:.0f}%  "
          f"impervious {c.impervious_pp:.0f}%  "
          f"building {c.building_pp:.0f}%  albedo {c.mean_albedo:.2f}")

    # scenario: convert a third of the asphalt to parking-with-tree-islands
    grid = base.copy()
    asphalt = np.argwhere(grid == "asphalt")
    for r, cc in asphalt[:len(asphalt) // 3]:
        grid[r, cc] = "parking_treed"

    res = evaluate(grid, base, measured)
    print("\n" + res.readout())
    print("\nbreakdown:")
    for k, v in sorted(res.breakdown.items(), key=lambda x: x[1]):
        print(f"  {k:12} {v:+.2f}")
    print(f"\ntrees added: {res.now.tree_count - res.base.tree_count}")
    for n in res.notes:
        print(f"  ! {n}")

    # invariants
    print("\nchecks")
    f = spatial_field(base, -2.5)
    print(f"  field mean == scalar        {abs(f.mean() + 2.5) < 0.01}")
    everything = np.full((GRID_N, GRID_N), "tree_dense", dtype=object)
    everything[:5, :5] = "water"
    r2 = evaluate(everything, build_preset("downtown"), measured)
    print(f"  clamp holds                 {r2.delta_c >= MAX_COOLING_C}")
    print(f"  identical grids give zero   "
          f"{abs(evaluate(base, base, measured).delta_c) < 0.01}")
    print(f"  preset reproducible         "
          f"{(build_preset('downtown') == build_preset('downtown')).all()}")

    # threshold behaviour
    print("\ncanopy threshold (Ziter-inspired, our slopes):")
    for pct in (30, 35, 40, 45, 50, 55):
        g = build_preset("downtown").ravel().copy()
        g[:int(GRID_N * GRID_N * pct / 100)] = "tree_dense"
        d = evaluate(g.reshape(GRID_N, GRID_N),
                     build_preset("downtown"), measured)
        print(f"  {pct:>3}% canopy -> {d.delta_c:+.2f} C")