import { useState } from "react";
import { geocode } from "../api/client";
import type { Shape } from "../types";
import LocatorMap from "./LocatorMap";

export interface SiteParams {
  locationName: string;
  lat: number;
  lon: number;
  shape: Shape;
  sizeM: number;
  polygonRing: [number, number][] | null;
  granularity: 60 | 80 | 100;
  existingCondition: "blank" | "osm";
}

interface Props {
  quickLocations: Record<string, { lat: number; lon: number }>;
  loading: boolean;
  onFetch: (params: SiteParams) => void;
}

// Manhattan - same fallback fgdata.py / app_studio.py already default to,
// used only until the user picks something or quickLocations has loaded.
const FALLBACK = { lat: 40.758, lon: -73.9855 };

const SHAPE_LABEL: Record<Shape, string> = {
  square: "Square",
  circle: "Circle",
  polygon: "Polygon (draw on map)",
};

export default function LocationPicker({ quickLocations, loading, onFetch }: Props) {
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [shape, setShape] = useState<Shape>("square");
  const [sizeM, setSizeM] = useState(1000);
  const [granularity, setGranularity] = useState<60 | 80 | 100>(100);
  const [existingCondition, setExistingCondition] = useState<"blank" | "osm">("blank");
  const [picked, setPicked] = useState<{ name: string; lat: number; lon: number } | null>(null);
  const [polygonRing, setPolygonRing] = useState<[number, number][] | null>(null);

  const mapCenter = picked ?? { name: "", ...(Object.values(quickLocations)[0] ?? FALLBACK) };
  const ready = shape === "polygon" ? !!picked && !!polygonRing && polygonRing.length >= 3 : !!picked;

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setError(null);
    try {
      const hit = await geocode(query);
      setPicked({ name: hit.display_name, lat: hit.lat, lon: hit.lon });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    }
  }

  function changeShape(s: Shape) {
    setShape(s);
    setPolygonRing(null);
  }

  function fetchWith(name: string, lat: number, lon: number) {
    onFetch({
      locationName: name,
      lat,
      lon,
      shape,
      sizeM,
      polygonRing: shape === "polygon" ? polygonRing : null,
      granularity,
      existingCondition,
    });
  }

  return (
    <div>
      <div className="eyebrow" style={{ marginTop: 0 }}>
        Site — anywhere in the USA
      </div>

      <form onSubmit={handleSearch} style={{ display: "flex", gap: "0.35rem", marginBottom: "0.5rem" }}>
        <input
          className="mono"
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Type a location — e.g. Austin, TX · 90210 · 123 Main St, Denver CO"
          style={{ flex: 1, padding: "0.55rem 0.6rem", fontSize: "0.85rem", border: "1.5px solid var(--ink)", background: "var(--paper)", color: "var(--ink)" }}
        />
        <button
          type="submit"
          style={{ padding: "0.55rem 0.8rem", fontSize: "0.85rem", border: "1.5px solid var(--ink)", background: "var(--ink)", color: "var(--paper)" }}
        >
          Search
        </button>
      </form>
      {error && <div className="flag">{error}</div>}

      <div style={{ display: "flex", gap: "0.3rem", marginBottom: "0.6rem" }}>
        {Object.entries(quickLocations).map(([name, { lat, lon }]) => (
          <button
            key={name}
            style={{ flex: 1, padding: "0.3rem", border: "1px solid var(--rule)", background: "var(--paper)" }}
            onClick={() => setPicked({ name, lat, lon })}
          >
            {name.split(",")[0]}
          </button>
        ))}
      </div>

      <div style={{ marginBottom: "0.6rem" }}>
        <LocatorMap
          lat={mapCenter.lat}
          lon={mapCenter.lon}
          shape={shape}
          sizeM={sizeM}
          label={picked ? picked.name : "pick a location below"}
          onPick={(lat, lon) => setPicked({ name: `${lat.toFixed(4)}, ${lon.toFixed(4)}`, lat, lon })}
          onPolygonDrawn={(ring) => setPolygonRing(ring.length >= 3 ? ring : null)}
        />
      </div>

      {picked && (
        <div className="mono" style={{ fontSize: "0.72rem", color: "var(--ink60)", marginBottom: "0.5rem" }}>
          Showing <b style={{ color: "var(--ink)" }}>{picked.name}</b>
        </div>
      )}

      <div className="eyebrow">Shape &amp; size</div>
      <div style={{ display: "flex", gap: "0.3rem", marginBottom: "0.4rem" }}>
        {(["square", "circle", "polygon"] as Shape[]).map((s) => (
          <button
            key={s}
            style={{
              flex: 1,
              padding: "0.3rem",
              fontSize: "0.72rem",
              border: "1px solid var(--rule)",
              background: shape === s ? "var(--ink)" : "var(--paper)",
              color: shape === s ? "var(--paper)" : "var(--ink)",
            }}
            onClick={() => changeShape(s)}
          >
            {SHAPE_LABEL[s]}
          </button>
        ))}
      </div>
      {shape !== "polygon" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.5rem" }}>
          <input
            type="range"
            min={200}
            max={5000}
            step={100}
            value={sizeM}
            onChange={(e) => setSizeM(Number(e.target.value))}
            style={{ flex: 1 }}
          />
          <span className="mono" style={{ fontSize: "0.7rem", width: "4.5em" }}>
            {sizeM} m
          </span>
        </div>
      ) : (
        <div className="mono" style={{ fontSize: "0.68rem", color: "var(--ink60)", marginBottom: "0.5rem" }}>
          Draw a polygon on the map above (top-left tool){polygonRing ? ` — ${polygonRing.length} points` : ""}.
        </div>
      )}

      <div className="eyebrow">Granularity (m)</div>
      <div style={{ display: "flex", gap: "0.3rem", marginBottom: "0.5rem" }}>
        {([60, 80, 100] as const).map((g) => (
          <button
            key={g}
            title="FortyGuard's tile size — the real-world measurement resolution, only allows these three values."
            style={{
              flex: 1,
              padding: "0.3rem",
              border: "1px solid var(--rule)",
              background: granularity === g ? "var(--ink)" : "var(--paper)",
              color: granularity === g ? "var(--paper)" : "var(--ink)",
            }}
            onClick={() => setGranularity(g)}
          >
            {g} m
          </button>
        ))}
      </div>

      <div className="eyebrow">Existing condition</div>
      <div style={{ display: "flex", gap: "0.3rem", marginBottom: "0.6rem" }}>
        <button
          style={{
            flex: 1,
            padding: "0.3rem",
            border: "1px solid var(--rule)",
            background: existingCondition === "blank" ? "var(--ink)" : "var(--paper)",
            color: existingCondition === "blank" ? "var(--paper)" : "var(--ink)",
          }}
          onClick={() => setExistingCondition("blank")}
        >
          Blank canvas
        </button>
        <button
          disabled={shape !== "square"}
          title={shape !== "square" ? "OpenStreetMap baseline is only available for a square area" : undefined}
          style={{
            flex: 1,
            padding: "0.3rem",
            border: "1px solid var(--rule)",
            background: existingCondition === "osm" ? "var(--ink)" : "var(--paper)",
            color: existingCondition === "osm" ? "var(--paper)" : "var(--ink)",
            opacity: shape !== "square" ? 0.5 : 1,
          }}
          onClick={() => setExistingCondition("osm")}
        >
          Real (OpenStreetMap)
        </button>
      </div>

      <button
        disabled={loading || !ready}
        onClick={() => picked && fetchWith(picked.name, picked.lat, picked.lon)}
        style={{
          width: "100%",
          padding: "0.6rem",
          fontSize: "0.9rem",
          fontWeight: 600,
          border: "1px solid var(--ink)",
          background: "var(--ink)",
          color: "var(--paper)",
          opacity: loading || !ready ? 0.4 : 1,
          cursor: loading || !ready ? "not-allowed" : "pointer",
        }}
      >
        {loading ? "Generating heatmap…" : "Generate Heatmap"}
      </button>
      {!picked && (
        <div className="mono" style={{ fontSize: "0.68rem", color: "var(--ink60)", marginTop: "0.3rem" }}>
          Pick a location first — search above, click a quick location, or click the map.
        </div>
      )}
      {shape === "polygon" && picked && !polygonRing && (
        <div className="mono" style={{ fontSize: "0.68rem", color: "var(--ink60)", marginTop: "0.3rem" }}>
          Draw a polygon on the map first.
        </div>
      )}
    </div>
  );
}
