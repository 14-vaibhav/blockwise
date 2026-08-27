import L from "leaflet";
import "leaflet-draw";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { useEffect, useRef } from "react";
import type { Shape } from "../types";

// Leaflet's default marker icon uses relative URLs that 404 under a bundler
// (a well-known Leaflet + Vite/webpack issue) - point it at the bundled
// asset URLs instead, once, module-wide.
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const M_PER_DEG_LAT = 111_320;

/** Same metres-per-degree square math as fgdata.square_aoi (Python) - kept
 * in sync so the preview rectangle matches exactly what /api/site queries. */
function squareBounds(lat: number, lon: number, sizeM: number): L.LatLngBoundsExpression {
  const dLat = sizeM / 2 / M_PER_DEG_LAT;
  const dLon = sizeM / 2 / (M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180));
  return [
    [lat - dLat, lon - dLon],
    [lat + dLat, lon + dLon],
  ];
}

interface Props {
  lat: number;
  lon: number;
  shape: Shape;
  sizeM: number;
  label: string;
  onPick: (lat: number, lon: number) => void;
  /** Only used when shape === "polygon": fires with the drawn ring as
   * [lon, lat] pairs, matching fgdata.polygon_aoi / sandbox.polygon_grid. */
  onPolygonDrawn?: (ring: [number, number][]) => void;
}

export default function LocatorMap({ lat, lon, shape, sizeM, label, onPick, onPolygonDrawn }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const overlayRef = useRef<L.Circle | L.Rectangle | null>(null);
  const drawnLayerRef = useRef<L.FeatureGroup | null>(null);
  const drawControlRef = useRef<L.Control.Draw | null>(null);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;
  const onPolygonDrawnRef = useRef(onPolygonDrawn);
  onPolygonDrawnRef.current = onPolygonDrawn;

  // Mount once - the map instance itself is imperative and outlives re-renders.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const map = L.map(container, { attributionControl: true }).setView([lat, lon], 14);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    const marker = L.marker([lat, lon]).addTo(map);
    map.on("click", (e: L.LeafletMouseEvent) => onPickRef.current(e.latlng.lat, e.latlng.lng));

    mapRef.current = map;
    markerRef.current = marker;

    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
      overlayRef.current = null;
      drawnLayerRef.current = null;
      drawControlRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep the pin, AOI overlay, and centering in sync with the current pick/shape/size.
  // Square/circle only - polygon mode draws its own overlay via the Draw plugin below.
  useEffect(() => {
    const map = mapRef.current;
    const marker = markerRef.current;
    if (!map || !marker) return;

    marker.setLatLng([lat, lon]);
    map.setView([lat, lon], map.getZoom());

    if (overlayRef.current) {
      overlayRef.current.remove();
      overlayRef.current = null;
    }
    if (shape === "polygon") return;

    const style = { color: "#5E2B54", weight: 2, fillOpacity: 0.12 };
    overlayRef.current =
      shape === "circle"
        ? L.circle([lat, lon], { radius: sizeM, ...style }).addTo(map)
        : L.rectangle(squareBounds(lat, lon, sizeM), style).addTo(map);
  }, [lat, lon, shape, sizeM]);

  // Polygon mode: swap in Leaflet.draw's polygon tool, matching app.py's
  // folium Draw control (edit-on, only polygon enabled). Torn down again
  // when the user picks a different shape.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || shape !== "polygon") return;

    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    drawnLayerRef.current = drawnItems;

    const drawControl = new L.Control.Draw({
      position: "topleft",
      draw: {
        polygon: { shapeOptions: { color: "#5E2B54", weight: 2, fillOpacity: 0.12 } },
        rectangle: false,
        circle: false,
        circlemarker: false,
        marker: false,
        polyline: false,
      },
      edit: { featureGroup: drawnItems, remove: true },
    });
    map.addControl(drawControl);
    drawControlRef.current = drawControl;

    function emitRing() {
      const layers = drawnItems.getLayers() as L.Polygon[];
      const poly = layers[0];
      if (!poly) return;
      const latlngs = (poly.getLatLngs()[0] as L.LatLng[]) ?? [];
      const ring: [number, number][] = latlngs.map((p) => [p.lng, p.lat]);
      onPolygonDrawnRef.current?.(ring);
    }

    function onCreated(e: L.DrawEvents.Created) {
      drawnItems.clearLayers();
      drawnItems.addLayer(e.layer);
      emitRing();
    }
    function onEdited() {
      emitRing();
    }
    function onDeleted() {
      onPolygonDrawnRef.current?.([]);
    }

    map.on(L.Draw.Event.CREATED, onCreated as L.LeafletEventHandlerFn);
    map.on(L.Draw.Event.EDITED, onEdited);
    map.on(L.Draw.Event.DELETED, onDeleted);

    return () => {
      map.off(L.Draw.Event.CREATED, onCreated as L.LeafletEventHandlerFn);
      map.off(L.Draw.Event.EDITED, onEdited);
      map.off(L.Draw.Event.DELETED, onDeleted);
      map.removeControl(drawControl);
      map.removeLayer(drawnItems);
      drawControlRef.current = null;
      drawnLayerRef.current = null;
    };
  }, [shape]);

  return (
    <div>
      <div
        ref={containerRef}
        style={{ height: 360, width: "100%", border: "1px solid var(--rule)" }}
      />
      <div className="mono" style={{ fontSize: "0.62rem", color: "var(--ink60)", marginTop: "0.25rem" }}>
        {shape === "polygon"
          ? "Draw a polygon on the map (top-left tool) · " + label
          : "Click the map to move the pin · " + label}
      </div>
    </div>
  );
}
