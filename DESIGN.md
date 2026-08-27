# Blockwise — Design

**FortyGuard Hackathon '26 · Track 01**
Visual language, tokens, and interaction spec for the Streamlit app.

---

## 1. The brief, restated

A tool for city planners and architects to test heat consequences before
building. It answers one question: *what would this district's temperature be
if it were built differently?*

Two facts drive every decision below.

**The audience is planners, not scientists.** They already read drawings. They
do not read dashboards.

**Half the numbers on screen are measurements and half are model output, and
the difference is the whole credibility of the project.** A judge who can't
tell which is which has no reason to trust either.

---

## 2. Direction

### What we did not do

The default for a heat tool is thermal-imaging language: black ground, the
FLIR palette, glowing gradients. It's the first thing anyone reaches for and
it's wrong here — it dramatises heat when the point is to make heat *legible*
and *designable*. It also implies the whole screen is measured data, which is
the one thing we must not imply.

Also avoided: warm cream paper with a serif display and a terracotta accent.
It looks considered and it is currently everywhere.

### What we did

**The planning drawing.** Cool paper, hairline registration rules, a title
block in the corner, everything annotated in monospace. The tool borrows the
planner's own vernacular, which does three things at once: it signals the
audience, it makes "existing / proposed" a native concept rather than a UI
invention, and it gives us a place to put provenance that reads as normal
drawing practice rather than as a disclaimer.

### The one idea

**Measured is ink. Modelled is a redline.**

FortyGuard's measurements are set solid, in a deep teal. Our model's output is
set in annotation violet with a 45° hatch fill — the way a proposed change is
marked over an existing drawing. The hatch is not decoration; it is the visual
grammar for *"this is a claim, not an observation."*

That grammar runs through the whole interface: the title block values, the
scale bar, the contribution chart. A planner reads it without being told.

---

## 3. Tokens

### Colour

| Token | Hex | Role |
|---|---|---|
| `paper` | `#E9EAE5` | Ground. Cool grey-green, like tracing over a plan. |
| `paper2` | `#DFE1DA` | Title block and palette rail. |
| `ink` | `#16181A` | Type, rules, outlines. |
| `ink60` | `#5A5F5C` | Labels, captions, secondary values. |
| `rule` | `#C3C5BD` | Hairlines and table borders. |
| `measured` | `#1B4B52` | **FortyGuard data only.** Never used for model output. |
| `modelled` | `#5E2B54` | **Model output only.** Always hatched when it appears as an area. |
| `amber` | `#9C6B1E` | Caveat flags — radiant heat, night warming, clamp. |

`measured` and `modelled` are reserved. Using either for anything else breaks
the grammar and the honesty guarantee with it.

The thermal view uses its own ramp: `#1B4B52` → `paper` → `#8C2F1E`. Cool end
is the measured teal so the two views share a family.

Material colours live in `engine.MATERIALS`; ground washes in
`plandraw.GROUND` are desaturated versions, so the drawing reads as a plan
rather than a chart.

### Type

| Role | Face | Treatment |
|---|---|---|
| Display | **Archivo** 700 | Wordmark only. `letter-spacing: .16em`, uppercase. |
| Body | **Archivo** 400/500 | Prose in the method panel. |
| Data & labels | **IBM Plex Mono** 400/600 | Every number, every label, every caption. |

Two families, three roles. Archivo is wide and slightly industrial — it does
not read as a default sans. Everything quantitative is mono, because
instruments speak in mono and it makes columns of figures align.

Eyebrow labels: mono, `.6rem`, `.16em` tracking, uppercase, hairline
underneath. They mark sections the way a drawing marks its parts.

### Space and line

No border radius above 2px. Drafting has square corners.
Hairlines are 1px `rule`; structural divisions are 1.5px `ink`; the masthead
and sheet border are 2px and 1.4px `ink` respectively.

---

## 4. Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ BLOCKWISE   District heat sandbox      MANHATTAN · 1200×1200 m   │  masthead
╞══════════════════════════════════════════════════════════════════╡  2px rule
│ SITE           │                            │ TEMPERATURE        │
│  location      │                            │ ┌────┬────┬─────┐  │
│  ○ real site   │     THE PLAN               │ │34.5│−2.1│32.4 │  │
│  ○ preset      │     30 × 30 @ 40 m         │ │meas│mdl │proj │  │
│                │                            │ └────┴────┴─────┘  │
│ MATERIALS      │   [Materials][Temperature] │ ▓▓▓▓▓▓▓▓▓░░░░      │  signature
│  ▣ Tree        │                            │ solid │ hatched    │
│  ▣ Grass       │                            │                    │
│  ▣ Water       │                            │ provenance ×2      │
│  ▣ Asphalt     │                            │                    │
│  ▣ Building    │                            │ CONTRIBUTION       │
│                │                            │  canopy   −1.2     │
│ BRUSH  [──●──] │                            │  albedo   −0.5     │
│                │                            │                    │
│ ⚠ caveat       │  click to place …          │ COMPOSITION        │
│                │                            │  existing │ proposed│
└────────────────┴────────────────────────────┴────────────────────┘
```

Three zones, left to right: **choose**, **draw**, **read**. That is the order
of the task.

The title block sits top-right of the reading column, where a drawing's title
block sits, and holds the same kind of content: what this sheet shows, at what
scale, from what source, revised when.

---

## 5. The plan drawing

`plandraw.py` renders the grid as an architect would draw it, not as a
heatmap.

| Material | How it draws |
|---|---|
| Dense canopy | Three overlapping crowns, ink outline |
| Scattered trees | One crown, smaller radius |
| Parking with islands | Two small crowns, offset diagonally |
| Shrub / wetland | Single small crown |
| Building | Inset block, ink outline, pale roof ridge line |
| Tower | Less inset, darker fill, darker ridge |
| Water | Full cell with a shoreline outline |
| Paving, grass, soil | Ground wash only |

**Performance constraint.** 900 cells makes shape count the binding limit. The
ground wash is a plotly heatmap, not 900 rects — that halved the count and
gives click detection for free. Only things that need to look *drawn* become
shapes. Worst case (downtown preset) is ~1,200; keep it under ~1,500.

The palette rail shows a live SVG miniature of each material rendered by the
same rules, so what you pick is what you get.

---

## 6. Interaction

**Painting.** Click a cell; the brush (1–6) paints a square around it.
Click events come from `st.plotly_chart(on_select="rerun")` — native to
Streamlit 1.38+, so no `streamlit-drawable-canvas` and no pixel-to-cell
mapping to get wrong.

⚠ The chart's `key` must not collide with a `st.session_state` name. `key="grid"`
alongside `st.session_state.grid` returns the numpy array instead of the event.
Use `key="plan_click"`.

**Removing.** There is no eraser mode. Painting *is* removing — put grass or
bare soil over something to take it away. One mechanism, not two.

**Two views.** Materials (the plan) and Temperature (the surface). The toggle
sits above the drawing because it changes the drawing, not the readout.

**Reverting.** "Revert to existing condition" restores the measured baseline.
Never silently resets on any other action.

---

## 7. Copy

Interface voice: plain, active, specific. A control says what happens.

| Not this | This |
|---|---|
| Baseline | Existing condition |
| Modified state | Proposed |
| Submit | *(nothing submits; it's live)* |
| Reset | Revert to existing condition |
| Delta | Modelled change |
| Select material | Click to place light paving |

**Caveats are content, not apology.** They appear where the decision is made —
the radiant-heat warning shows in the palette rail the moment you select
reflective paving, not buried in a help page. They state the trade-off and
stop:

> Cools air slightly but raises radiant heat on pedestrians by ~2.7 °C at
> midday. Suited to parking and low-footfall streets, not sidewalks.

**Provenance is permanent, not a tooltip.** Two lines sit inside the title
block at all times:

> Mean daily peak across 79 tiles, 2024-07-15. Spatial variation 1.12 °C.
> Tiles are 100 m; the 40 m grid is interpolated.

> Existing condition from OpenStreetMap — 412 features, 187 buildings. Roof
> materials and paving type are assumed, not observed.

The second line is doing real work. OSM knows a building is there; it does not
know the roof is dark. Saying so is the same species of honesty as the
LST-versus-air distinction, and it costs one line.

**The scale bar legend** reads *"Modelled — not a measurement."* That is the
thesis of the project rendered as a key.

---

## 8. Quality floor

- Keyboard focus visible on all controls (Streamlit default, not overridden).
- Grid stays square at any window width via `scaleanchor`.
- No animation. Nothing here benefits from motion, and a heat tool that
  animates reads as a toy.
- Sidebar collapses on narrow viewports; the reading column stacks below the
  drawing.
- Everything degrades: no OSM → synthetic preset with a stated fallback;
  no FortyGuard → cached JSON with a stated fallback.

---

## 9. Rules that must not be broken

1. `measured` teal never renders model output. `modelled` violet never renders
   a measurement.
2. Any modelled *area* is hatched. Solid fill means observed.
3. The three title-block values are never combined into one figure.
4. Every displayed figure carries its uncertainty band.
5. Provenance stays on screen. It does not move into a modal, an expander, or
   a footnote.
6. No coefficient value appears in the UI without its status
   (`literature_central` / `engineering_value` / `calibration_parameter`).

---

## 10. Known gaps

**The measured field's shape is synthetic.** Amplitude and spread are real
FortyGuard numbers; the diagonal gradient they're laid onto is invented,
because mapping each tile's lat/lon onto grid cells is unfinished work. Either
finish it or change the caption before submission. Right now the caption says
the grid is interpolated — it does not say the *pattern* is fabricated. That
gap has to close.

**No scale bar or north arrow.** Both are native to the drawing vernacular and
both would add credibility cheaply. Not yet built.

**The optimiser panel has no design.** When it lands it belongs in the reading
column below composition, and its rejections should be typeset as
strikethrough entries in the same ledger as its selections — a plan showing
its own discarded options is more convincing than one that only shows the
answer.
