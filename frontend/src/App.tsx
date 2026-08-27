import { useEffect, useReducer, useRef, useState } from "react";
import { fetchSite, getMaterials, getQuickLocations, simulate } from "./api/client";
import AnalysisPanel from "./components/AnalysisPanel";
import CompositionTable from "./components/CompositionTable";
import ContributionChart from "./components/ContributionChart";
import GridCanvas from "./components/GridCanvas";
import LocationPicker, { type SiteParams } from "./components/LocationPicker";
import MaterialPalette from "./components/MaterialPalette";
import TitleBlock from "./components/TitleBlock";
import Toolbar from "./components/Toolbar";
import { environmentReducer, initialState } from "./state/environment";
import type { MaterialsResponse, SiteResponse } from "./types";

export default function App() {
  const [materialsResp, setMaterialsResp] = useState<MaterialsResponse | null>(null);
  const [quickLocations, setQuickLocations] = useState<Record<string, { lat: number; lon: number }>>({});
  const [state, dispatch] = useReducer(environmentReducer, initialState("grass"));
  const [siteMeta, setSiteMeta] = useState<SiteResponse["data"] | null>(null);
  const [locationName, setLocationName] = useState("");
  const [plotLabel, setPlotLabel] = useState("");
  const [siteLoading, setSiteLoading] = useState(false);
  const [siteError, setSiteError] = useState<string | null>(null);
  const [simLoading, setSimLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [dark, setDark] = useState(false);

  const simRequestId = useRef(0);
  const loadedGridRef = useRef<unknown>(null);
  const lastSiteParamsRef = useRef<SiteParams | null>(null);

  useEffect(() => {
    getMaterials().then(setMaterialsResp).catch((e) => setSiteError(String(e)));
    getQuickLocations().then(setQuickLocations).catch(() => {});
  }, []);

  async function handleFetchSite(params: SiteParams) {
    lastSiteParamsRef.current = params;
    setSiteLoading(true);
    setSiteError(null);
    try {
      const resp = await fetchSite({
        location_name: params.locationName,
        lat: params.lat,
        lon: params.lon,
        shape: params.shape,
        size_m: params.sizeM,
        polygon_ring: params.polygonRing ?? undefined,
        granularity: params.granularity,
        existing_condition: params.existingCondition,
      });
      dispatch({
        type: "LOAD_SITE",
        rows: resp.rows,
        cols: resp.cols,
        mask: resp.mask,
        baselineGrid: resp.baseline_grid,
        grid: resp.grid,
        measuredField: resp.measured_field,
      });
      setSiteMeta(resp.data);
      setLocationName(resp.location_name);
      if (params.shape === "polygon") {
        setPlotLabel(`${resp.rows}×${resp.cols} cells, ~${resp.cell_w.toFixed(0)} m, polygon`);
      } else {
        const extent = params.shape === "circle" ? params.sizeM * 2 : params.sizeM;
        setPlotLabel(`${extent}×${extent} m ${params.shape}`);
      }

      // Deterministic, captured exactly once at load - this is the fixed
      // "before" side of the analysis panel's comparison, independent of
      // the debounced re-simulate effect below.
      const initial = await simulate(resp.grid, resp.baseline_grid, resp.measured_field, resp.mask);
      loadedGridRef.current = resp.grid;
      dispatch({ type: "SET_LIVE_RESULT", result: initial });
      dispatch({ type: "SET_ORIGINAL_RESULT", result: initial });
    } catch (err) {
      setSiteError(err instanceof Error ? err.message : "Failed to load site.");
    } finally {
      setSiteLoading(false);
    }
  }

  // Single source of truth for "the grid changed, so re-simulate": fires on
  // every state.grid change regardless of *why* it changed (a paint stroke,
  // a rectangle fill, undo, redo, clear, reset-environment - the reducer
  // replaces the grid array on all of them). This is deliberately NOT wired
  // per-action - an earlier version called simulate() manually from
  // GridCanvas's pointer handlers only, which meant Undo/Redo/Clear/Reset
  // (dispatched from the Toolbar) never refreshed the title block. Debounced
  // so a paint drag coalesces into one call after motion pauses instead of
  // one request per pointermove.
  useEffect(() => {
    if (state.rows === 0) return;
    if (state.grid === loadedGridRef.current) return;
    const id = ++simRequestId.current;
    setSimLoading(true);
    const handle = setTimeout(() => {
      simulate(state.grid, state.baselineGrid, state.measuredField, state.mask)
        .then((result) => {
          if (id === simRequestId.current) dispatch({ type: "SET_LIVE_RESULT", result });
        })
        .catch(() => {
          // transient network hiccup - the next grid change retries
        })
        .finally(() => {
          if (id === simRequestId.current) setSimLoading(false);
        });
    }, 120);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.grid]);

  async function handleApply() {
    setApplying(true);
    try {
      const result = await simulate(state.grid, state.baselineGrid, state.measuredField, state.mask);
      dispatch({ type: "SET_LIVE_RESULT", result });
      dispatch({ type: "APPLY_CHANGES", result, grid: state.grid });
    } catch (err) {
      setSiteError(err instanceof Error ? err.message : "Simulation failed.");
    } finally {
      setApplying(false);
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod || e.key.toLowerCase() !== "z") return;
      e.preventDefault();
      dispatch({ type: e.shiftKey ? "REDO" : "UNDO" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!materialsResp) {
    return (
      <div className="mono" style={{ padding: "2rem" }}>
        Loading…
      </div>
    );
  }

  const provenance = siteMeta
    ? `Mean daily peak across ${siteMeta.n_tiles} FortyGuard tiles, ${siteMeta.date}. Spatial variation ${siteMeta.peak_spread.toFixed(2)} °C. Simulation estimates below are modelled, not measured.`
    : "No site loaded yet.";

  return (
    <div data-theme={dark ? "dark" : "light"} style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div
        className="mono"
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          borderBottom: "2px solid var(--ink)",
          padding: "0.7rem 1rem",
        }}
      >
        <div>
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.3rem", letterSpacing: "0.16em", textTransform: "uppercase" }}>
            Blockwise
          </span>
          <span style={{ marginLeft: "1rem", fontSize: "0.68rem", color: "var(--ink60)" }}>
            Interactive material editor
          </span>
        </div>
        <button style={{ border: "1px solid var(--rule)", padding: "0.3rem 0.6rem" }} onClick={() => setDark((d) => !d)}>
          {dark ? "Light" : "Dark"} mode
        </button>
      </div>

      {siteError && (
        <div className="flag" style={{ margin: "0.5rem 1rem", display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <span>Unable to generate heatmap. Reason: {siteError}</span>
          {lastSiteParamsRef.current && (
            <button
              className="mono"
              style={{ padding: "0.2rem 0.5rem", border: "1px solid currentColor", background: "transparent", color: "inherit", flexShrink: 0 }}
              onClick={() => lastSiteParamsRef.current && handleFetchSite(lastSiteParamsRef.current)}
            >
              Retry
            </button>
          )}
        </div>
      )}

      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "260px 1fr 340px", gap: "1rem", padding: "1rem", minHeight: 0 }}>
        <aside style={{ overflowY: "auto", overflowX: "hidden", minWidth: 0 }}>
          <LocationPicker quickLocations={quickLocations} loading={siteLoading} onFetch={handleFetchSite} />
          {state.rows > 0 && (
            <>
              <Toolbar state={state} dispatch={dispatch} onApply={handleApply} applying={applying} />
              <MaterialPalette materialsResp={materialsResp} state={state} dispatch={dispatch} />
            </>
          )}
        </aside>

        <main style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          {state.rows > 0 ? (
            <>
              <div style={{ display: "flex", gap: "0.4rem", marginBottom: "0.4rem" }}>
                {(["materials", "temperature"] as const).map((v) => (
                  <button
                    key={v}
                    className="mono"
                    style={{
                      padding: "0.3rem 0.7rem",
                      border: "1px solid var(--rule)",
                      background: state.view === v ? "var(--ink)" : "var(--paper)",
                      color: state.view === v ? "var(--paper)" : "var(--ink)",
                      textTransform: "capitalize",
                    }}
                    onClick={() => dispatch({ type: "SET_VIEW", view: v })}
                  >
                    {v}
                  </button>
                ))}
                <span className="mono" style={{ fontSize: "0.65rem", color: "var(--ink60)", alignSelf: "center", marginLeft: "0.5rem" }}>
                  {state.view === "materials"
                    ? `${state.tool === "erase" ? "Erasing" : `Painting ${materialsResp.materials[state.material]?.label}`} · brush ${state.brush}`
                    : "Modelled temperature — not a measurement"}
                </span>
              </div>
              <div style={{ flex: 1, minHeight: 0, overflow: "hidden", border: "1px solid var(--rule)" }}>
                <GridCanvas
                  state={state}
                  materials={materialsResp.materials}
                  dispatch={dispatch}
                  paper={dark ? "#15191D" : "#E9EAE5"}
                  ink={dark ? "#ECEDE7" : "#16181A"}
                  rule={dark ? "#343B41" : "#C3C5BD"}
                  thermalCool={dark ? "#3E93A0" : "#1B4B52"}
                  thermalWarm={dark ? "#D97A54" : "#8C2F1E"}
                />
              </div>
            </>
          ) : (
            <div className="mono" style={{ color: "var(--ink60)", padding: "2rem" }}>
              Pick a location on the left, then "Show heatmap".
            </div>
          )}
        </main>

        <aside style={{ overflowY: "auto", overflowX: "hidden", minWidth: 0 }}>
          <TitleBlock result={state.liveResult} locationName={locationName} plotLabel={plotLabel} provenance={provenance} loading={simLoading} />
          <div style={{ marginTop: "0.8rem" }}>
            <ContributionChart result={state.liveResult} />
          </div>
          <div style={{ marginTop: "0.8rem" }}>
            <CompositionTable result={state.liveResult} />
          </div>
          <div style={{ marginTop: "0.8rem" }}>
            <AnalysisPanel state={state} />
          </div>
        </aside>
      </div>
    </div>
  );
}
