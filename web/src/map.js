import { Map, Marker, AttributionControl, NavigationControl, LngLatBounds, addProtocol, setWorkerUrl } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
// MapLibre 6 looks for its worker next to its own module, which no longer
// exists after bundling. Point it at an emitted copy instead.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import { Protocol } from 'pmtiles';
import { DECILE_COLOURS, NOT_BUILT, NIGHT_STOPS, HOT, MUTED } from './palette.js';

const BASEMAP = 'https://tiles.openfreemap.org/styles/positron';
const DELHI = [[76.84, 28.4], [77.35, 28.885]];
const HEX_SOURCE = 'hexes';
const HEX_LAYER = 'hexes';

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

const decileFill = [
  'match', ['get', 'dc'],
  ...DECILE_COLOURS.flatMap((c, i) => [i + 1, c]),
  NOT_BUILT,
];

const nightFill = [
  'case', ['==', ['typeof', ['get', 'nr']], 'number'],
  ['interpolate', ['linear'], ['get', 'nr'], ...NIGHT_STOPS.flat()],
  NOT_BUILT,
];

// Built-up hexes with fewer recent street photos than this are "thin coverage".
export const THIN_COVERAGE = 5;

function thinCoverage() {
  return ['all', ['>', ['get', 'dc'], 0], ['<', ['coalesce', ['get', 'mc'], 0], THIN_COVERAGE]];
}

// One entry per map "look". Chapters pick a look plus a camera.
const LOOKS = {
  teaser: { fill: decileFill, opacity: ['case', ['>', ['get', 'dc'], 0], 0.5, 0.12], outline: false },
  day: { fill: decileFill, opacity: ['case', ['>', ['get', 'dc'], 0], 0.85, 0.25], outline: false },
  night: { fill: nightFill, opacity: 0.8, outline: false },
  people: {
    fill: ['case', ['==', ['get', 'dc'], 10], HOT, MUTED],
    opacity: ['case', ['==', ['get', 'dc'], 10], 0.9, 0.35],
    outline: true,
  },
  streets: { fill: decileFill, opacity: ['case', ['>', ['get', 'dc'], 0], 0.55, 0.15], outline: false },
  explore: { fill: decileFill, opacity: ['case', ['>', ['get', 'dc'], 0], 0.8, 0.25], outline: false },
  // Built-up hexes with fewer than THIN_COVERAGE recent street photos.
  coverage: {
    fill: ['case', thinCoverage(), '#2f6f8f', MUTED],
    opacity: ['case', thinCoverage(), 0.75, 0.3],
    outline: false,
  },
};

export function isMobile() {
  return window.matchMedia('(max-width: 899px)').matches;
}

function padding() {
  const h = window.innerHeight;
  // On phones the legend sits on top and cards enter from the bottom.
  return isMobile()
    ? { top: 110, right: 16, bottom: Math.round(h * 0.25), left: 16 }
    : { top: 48, right: 48, bottom: 48, left: 48 };
}

export function createMap(container, { pmtilesUrl }) {
  setWorkerUrl(new URL(workerUrl, window.location.href).href);
  const protocol = new Protocol();
  addProtocol('pmtiles', protocol.tile);

  const map = new Map({
    container,
    style: BASEMAP,
    bounds: DELHI,
    fitBoundsOptions: { padding: padding() },
    attributionControl: false,
    // The page scrolls; the map must not steal the wheel or one-finger drags.
    scrollZoom: false,
    dragPan: false,
    dragRotate: false,
    touchZoomRotate: false,
    touchPitch: false,
    doubleClickZoom: false,
    keyboard: false,
    maxBounds: [[76.3, 28.0], [77.9, 29.3]],
    minZoom: 8,
    maxZoom: 15,
  });
  map.addControl(new AttributionControl({ compact: true }), 'bottom-right');
  // The compact attribution opens itself on first load and covers the map on
  // phones. Start it collapsed; full credits are in the page footer.
  map.once('load', () => {
    map.getContainer().querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show');
  });
  const nav = new NavigationControl({ showCompass: false });

  let current = { look: null, interactive: false };
  let markers = [];
  const ready = new Promise((resolve) => {
    map.on('load', () => {
      const firstLabel = map.getStyle().layers.find((l) => l.type === 'symbol')?.id;
      map.addSource(HEX_SOURCE, {
        type: 'vector',
        url: `pmtiles://${new URL(pmtilesUrl, window.location.href).href}`,
        attribution: 'Landsat (USGS) · VIIRS (NASA) · WorldPop · ESA WorldCover · Mapillary',
      });
      map.addLayer(
        {
          id: HEX_LAYER,
          type: 'fill',
          source: HEX_SOURCE,
          'source-layer': 'hexes',
          paint: { 'fill-color': decileFill, 'fill-opacity': 0, 'fill-opacity-transition': { duration: 600 } },
        },
        firstLabel,
      );
      map.addLayer(
        {
          id: `${HEX_LAYER}-outline`,
          type: 'line',
          source: HEX_SOURCE,
          'source-layer': 'hexes',
          filter: ['==', ['get', 'dc'], 10],
          paint: { 'line-color': '#5e0f1d', 'line-width': 0.6, 'line-opacity': 0 },
        },
        firstLabel,
      );
      map.addLayer({
        id: `${HEX_LAYER}-selected`,
        type: 'line',
        source: HEX_SOURCE,
        'source-layer': 'hexes',
        filter: ['==', ['get', 'h'], ''],
        paint: { 'line-color': '#1f1b16', 'line-width': 3 },
      });
      resolve();
    });
  });

  function setLook(name) {
    const look = LOOKS[name];
    map.setPaintProperty(HEX_LAYER, 'fill-color', look.fill);
    map.setPaintProperty(HEX_LAYER, 'fill-opacity', look.opacity);
    map.setPaintProperty(`${HEX_LAYER}-outline`, 'line-opacity', look.outline ? 0.7 : 0);
  }

  function setInteractive(on) {
    if (on === current.interactive) return;
    const handlers = ['dragPan', 'touchZoomRotate', 'doubleClickZoom', 'keyboard'];
    handlers.forEach((h) => (on ? map[h].enable() : map[h].disable()));
    if (on) {
      map.touchZoomRotate.disableRotation();
      map.addControl(nav, 'top-right');
    } else if (map.hasControl(nav)) {
      map.removeControl(nav);
    }
    map.getCanvas().style.cursor = on ? 'pointer' : '';
    current.interactive = on;
  }

  function camera(target) {
    const opts = { padding: padding(), duration: reducedMotion.matches ? 0 : 1600, essential: false };
    if (target === 'delhi') {
      map.fitBounds(DELHI, opts);
    } else if (target?.points) {
      const b = new LngLatBounds();
      target.points.forEach((p) => b.extend([p.lng, p.lat]));
      // Street labels hang below and to either side of their dots; leave room.
      const p = opts.padding;
      const padded = { ...p, left: p.left + 70, right: p.right + 70, bottom: p.bottom + 30 };
      map.fitBounds(b, { ...opts, padding: padded, maxZoom: target.maxZoom ?? 13 });
    }
  }

  function showStreets(pair) {
    markers.forEach((m) => m.remove());
    markers = [];
    if (!pair) return;
    for (const [kind, s] of [['hot', pair.hot], ['cool', pair.cool]]) {
      const el = document.createElement('div');
      el.className = `street-marker street-marker--${kind}`;
      el.innerHTML = `<span class="street-marker__dot"></span><span class="street-marker__label"></span>`;
      el.querySelector('.street-marker__label').textContent = s.name;
      // anchor top + offset puts the dot's centre on the street; the label hangs below it.
      markers.push(new Marker({ element: el, anchor: 'top', offset: [0, -7] }).setLngLat([s.lng, s.lat]).addTo(map));
    }
  }

  // ---- explorer helpers ----

  let overrideLook = null; // e.g. the thin-coverage overlay, toggled by the reader

  function showLook(name) {
    if (name === current.applied) return;
    setLook(name);
    current.applied = name;
  }

  function setOverlay(name) {
    overrideLook = name;
    showLook(name ?? current.look);
  }

  function select(h) {
    map.setFilter(`${HEX_LAYER}-selected`, ['==', ['get', 'h'], h ?? '']);
  }

  /** The hex feature drawn at a lng/lat, once the map has settled there. */
  async function featureAt(lngLat) {
    await ready;
    if (!map.loaded() || !map.areTilesLoaded()) await new Promise((r) => map.once('idle', r));
    const [f] = map.queryRenderedFeatures(map.project(lngLat), { layers: [HEX_LAYER] });
    return f ? { ...f.properties, centre: centroid(f.geometry) } : null;
  }

  function onHexClick(fn) {
    map.on('click', HEX_LAYER, (e) => {
      if (!current.interactive) return;
      const f = e.features?.[0];
      if (f) fn({ ...f.properties, centre: centroid(f.geometry) });
    });
  }

  function flyToPoint({ lat, lng }, zoom = 13) {
    current.lastCamera = null;
    current.explored = true;
    const opts = { center: [lng, lat], zoom, padding: padding() };
    reducedMotion.matches ? map.jumpTo(opts) : map.flyTo({ ...opts, duration: 1400 });
    return new Promise((r) => map.once('moveend', r));
  }

  async function apply(state) {
    await ready;
    if (!state.interactive) overrideLook = null; // overlays belong to the explorer only
    current.look = state.look;
    showLook(overrideLook ?? state.look);
    showStreets(state.pair);
    setInteractive(Boolean(state.interactive));
    // Interactive chapters keep whatever view the reader has moved to.
    if (state.interactive && current.explored) return;
    current.lastCamera = state.camera;
    camera(state.camera);
  }

  map.on('dragstart', () => (current.explored = current.interactive));
  map.on('zoomstart', (e) => e.originalEvent && (current.explored = current.interactive));

  // Keep the story framing correct after rotation or window resizes.
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!current.interactive && current.lastCamera) camera(current.lastCamera);
    }, 200);
  });

  return { map, ready, apply, select, featureAt, onHexClick, flyToPoint, setOverlay };
}

function centroid(geometry) {
  const ring = geometry.type === 'Polygon' ? geometry.coordinates[0] : geometry.coordinates[0][0];
  const pts = ring.slice(0, -1);
  const lng = pts.reduce((s, p) => s + p[0], 0) / pts.length;
  const lat = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  return { lat, lng };
}
