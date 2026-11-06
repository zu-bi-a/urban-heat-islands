// Fills the methods page with the live numbers, so it never drifts from the map.

import './styles.css';
import { people, escape } from './format.js';
import { ARTHA_URL } from './links.js';

const $ = (s) => document.querySelector(s);

async function main() {
  $('#artha-link').href = ARTHA_URL;
  const repo = import.meta.env.VITE_REPO_URL;
  if (repo) {
    $('#repo-link').href = repo;
    $('#repo').hidden = false;
  }

  const [stats, streets] = await Promise.all([
    fetch('/data/city_stats.json').then((r) => r.json()),
    fetch('/data/streets.json').then((r) => (r.ok ? r.json() : null)).catch(() => null),
  ]);
  if (stats.sample || streets?.sample) $('#sample-banner').hidden = false;

  document.querySelectorAll('[data-stat]').forEach((el) => {
    const v = stats[el.dataset.stat];
    if (v == null) return;
    el.textContent = `: ${'people' in el.dataset ? people(v) : `${v} ${el.dataset.unit}`}`;
  });
  document.querySelectorAll('[data-period]').forEach((el) => (el.textContent = stats.periods?.[el.dataset.period] ?? ''));
  document.querySelectorAll('[data-version]').forEach((el) => (el.textContent = stats.versions?.[el.dataset.version] ?? ''));

  const b = stats.decile_breaks_c ?? [];
  $('#breaks').textContent = b.length ? `${b.map((x) => `${x} °C`).join(', ')}` : 'not available';

  const hs = (stats.hotspots ?? []).filter((h) => h.decile != null);
  $('#hotspots').textContent = hs.length
    ? `In this version: ${hs.map((h) => `${h.name} decile ${h.decile}`).join(', ')} (10 = hottest).`
    : '';

  $('#credits-list').innerHTML = (stats.credits ?? []).map((c) => `<li>${escape(c)}</li>`).join('');
  if (streets?.credits?.length) {
    $('#photographers').textContent = `Mapillary photographers whose photos were used: ${streets.credits.join(', ')}. Images derived from their photos are shared under CC-BY-SA 4.0.`;
  }
  $('#generated').textContent = `Data generated ${stats.generated}. ${stats.versions?.population ?? ''}.`;
}

main();
