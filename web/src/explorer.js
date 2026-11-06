// Chapter 6: find your neighbourhood by search, location or tap, and see how
// it compares with the city. The selected hex is kept in the URL hash so it can
// be shared; shared links open straight here (PRD story flow).

import { people, deg, pct, km, escape } from './format.js';
import { THIN_COVERAGE, isMobile } from './map.js';
import { DECILE_COLOURS } from './palette.js';
import { track } from './track.js';

const DELHI_BBOX = { w: 76.84, s: 28.4, e: 77.35, n: 28.885 };

export function slugify(s) {
  return s.toLowerCase().normalize('NFKD').replace(/[^\w\s-]/g, '').trim().replace(/[\s_]+/g, '-');
}

function signed(c) {
  return `${c > 0 ? '+' : c < 0 ? '−' : '±'}${Math.abs(c).toFixed(1)} °C`;
}

/** Parse "#n=<hex>&ll=lat,lng" or "#place=<slug>". Plain anchors return null. */
export function parseHash(hash = window.location.hash) {
  const q = new URLSearchParams(hash.replace(/^#/, ''));
  if (q.has('n') && q.has('ll')) {
    const [lat, lng] = q.get('ll').split(',').map(Number);
    if (Number.isFinite(lat) && Number.isFinite(lng)) return { h: q.get('n'), lat, lng };
  }
  if (q.has('place')) return { place: q.get('place') };
  return null;
}

export function createExplorer({ storyMap, stats, places, wards, slot, panelHost, onOpenGuide }) {
  const items = [
    ...places.map((p) => ({ label: p.name, sub: 'Locality', lat: p.lat, lng: p.lng, slug: slugify(p.name) })),
    ...wards.map((w) => ({ label: w.name, sub: `Ward ${w.no}`, lat: w.lat, lng: w.lng, slug: `ward-${w.no}` })),
  ];
  const wardByNo = new Map(wards.map((w) => [w.no, w]));
  const listeners = new Set();
  let selected = null;

  // ---------- search UI (inside the chapter 6 card) ----------
  slot.innerHTML = `
    <div class="search">
      <label class="search__label" for="search-input">Search a locality${wards.length ? ' or ward' : ''}</label>
      <div class="search__row">
        <input id="search-input" class="search__input" type="search" autocomplete="off" spellcheck="false"
          placeholder="e.g. ${escape(places[0]?.name ?? 'Rohini')}" role="combobox" aria-expanded="false"
          aria-controls="search-list" aria-autocomplete="list" />
        <button type="button" class="btn btn--ghost search__locate" id="locate-btn" aria-label="Use my location">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="3.5" fill="currentColor"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" stroke-width="2"/></svg>
        </button>
      </div>
      <ul class="search__list" id="search-list" role="listbox" hidden></ul>
      <p class="search__hint" id="search-hint">Or tap any hexagon on the map.</p>
    </div>`;

  const input = slot.querySelector('#search-input');
  const list = slot.querySelector('#search-list');
  const hint = slot.querySelector('#search-hint');
  let matches = [];
  let cursor = -1;

  function renderList() {
    list.hidden = matches.length === 0;
    input.setAttribute('aria-expanded', String(!list.hidden));
    list.innerHTML = matches
      .map((m, i) => `<li role="option" id="opt-${i}" aria-selected="${i === cursor}" data-i="${i}">
          <span>${escape(m.label)}</span><small>${escape(m.sub)}</small></li>`)
      .join('');
    if (cursor >= 0) input.setAttribute('aria-activedescendant', `opt-${cursor}`);
    else input.removeAttribute('aria-activedescendant');
  }

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    cursor = -1;
    matches = q.length < 2 ? [] : items
      .filter((it) => it.label.toLowerCase().includes(q))
      .sort((a, b) => a.label.toLowerCase().indexOf(q) - b.label.toLowerCase().indexOf(q))
      .slice(0, 8);
    renderList();
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!matches.length) return;
      e.preventDefault();
      cursor = (cursor + (e.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length;
      renderList();
    } else if (e.key === 'Enter' && matches.length) {
      e.preventDefault();
      choose(matches[Math.max(cursor, 0)]);
    } else if (e.key === 'Escape') {
      matches = [];
      renderList();
    }
  });
  list.addEventListener('mousedown', (e) => e.preventDefault()); // keep focus for click
  list.addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (li) choose(matches[Number(li.dataset.i)]);
  });
  input.addEventListener('blur', () => setTimeout(() => { matches = []; renderList(); }, 100));

  async function choose(item) {
    input.value = item.label;
    matches = [];
    renderList();
    input.blur();
    track('explore_search');
    await goTo({ lat: item.lat, lng: item.lng }, item.sub === 'Locality' ? item.label : `${item.sub} · ${item.label}`);
  }

  slot.querySelector('#locate-btn').addEventListener('click', () => {
    if (!navigator.geolocation) {
      hint.textContent = 'Your browser cannot share its location. Try searching instead.';
      return;
    }
    hint.textContent = 'Finding you…';
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        const p = { lat: coords.latitude, lng: coords.longitude };
        if (p.lng < DELHI_BBOX.w || p.lng > DELHI_BBOX.e || p.lat < DELHI_BBOX.s || p.lat > DELHI_BBOX.n) {
          hint.textContent = 'You seem to be outside Delhi. Search for a locality instead.';
          return;
        }
        hint.textContent = 'Or tap any hexagon on the map.';
        track('explore_locate');
        await goTo(p, null);
      },
      () => (hint.textContent = 'Location was not shared. Search or tap the map instead.'),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 },
    );
  });

  // ---------- selection ----------
  async function goTo(point, label) {
    await storyMap.flyToPoint(point, 13.5);
    const f = await storyMap.featureAt([point.lng, point.lat]);
    if (f) setSelected(f, label);
    else hint.textContent = 'That spot is outside the mapped area. Try a nearby locality.';
  }

  storyMap.onHexClick((f) => {
    track('explore_tap');
    setSelected(f, null);
  });

  function nameFor(f) {
    const ward = f.w != null ? wardByNo.get(Number(f.w)) : null;
    let best = null;
    for (const p of places) {
      const d = km(f.centre, p);
      if (!best || d < best.d) best = { p, d };
    }
    const near = best && best.d < 2.5 ? best.p.name : null;
    if (near) return best.d < 0.6 ? near : `Near ${near}`;
    if (ward) return `Ward ${ward.no} · ${ward.name}`;
    return 'This neighbourhood';
  }

  function setSelected(f, label) {
    selected = { ...f, label: label ?? nameFor(f) };
    storyMap.select(f.h);
    const { lat, lng } = f.centre;
    history.replaceState(null, '', `#n=${f.h}&ll=${lat.toFixed(5)},${lng.toFixed(5)}`);
    renderPanel();
    clearCard();
    listeners.forEach((fn) => fn(selected));
  }

  // On phones the panel is a bottom sheet; scroll the chapter card up so the
  // two do not overlap.
  function clearCard() {
    if (!isMobile() || panel.hidden) return;
    requestAnimationFrame(() => {
      const card = slot.closest('.card').getBoundingClientRect();
      const overlap = card.bottom - panel.getBoundingClientRect().top + 12;
      if (overlap > 0 && card.top > 0) window.scrollBy({ top: Math.min(overlap, card.top), behavior: 'smooth' });
    });
  }

  // ---------- details panel (over the map) ----------
  const panel = document.createElement('section');
  panel.className = 'hex-panel';
  panel.setAttribute('aria-live', 'polite');
  panel.hidden = true;
  panelHost.appendChild(panel);

  function rankLine(dc) {
    if (dc === 10) return 'In Delhi’s hottest tenth of neighbourhoods';
    if (dc === 1) return 'In Delhi’s coolest tenth of neighbourhoods';
    return `Hotter than about ${(dc - 1) * 10}% of built-up Delhi`;
  }

  function renderPanel() {
    const s = selected;
    if (!s) {
      panel.hidden = true;
      return;
    }
    const built = Number(s.dc) > 0;
    const diff = s.d - stats.median_day_c;
    const thin = built && Number(s.mc ?? 0) < THIN_COVERAGE;
    panel.hidden = false;
    panel.innerHTML = `
      <button type="button" class="hex-panel__close" aria-label="Close">×</button>
      <p class="hex-panel__kicker">Daytime surface temperature</p>
      <h3 class="hex-panel__title">${escape(s.label)}</h3>
      <div class="hex-panel__head">
        <span class="hex-panel__temp">${deg(s.d)}</span>
        <span class="hex-panel__diff ${Math.abs(diff) < 0.5 ? '' : diff > 0 ? 'is-hot' : 'is-cool'}">${signed(diff)} vs Delhi median</span>
      </div>
      <p class="hex-panel__rank">${built ? rankLine(Number(s.dc)) : 'Mostly river, forest, farmland or open ground, so not ranked.'}</p>
      ${built ? decileStrip(Number(s.dc)) : ''}
      <dl class="hex-panel__facts">
        ${s.nr != null ? `<div><dt>Night</dt><dd>${signed(Number(s.nr))} vs a typical Delhi night</dd></div>` : ''}
        ${s.t != null ? `<div><dt>Tree cover</dt><dd>${pct(Number(s.t))} of the area</dd></div>` : ''}
        ${s.p != null ? `<div><dt>People</dt><dd>${people(Number(s.p)).replace(/^about/, 'About')} live in this hexagon (~0.1 km²)</dd></div>` : ''}
      </dl>
      ${thin ? `<p class="hex-panel__thin">Few street photos here. <button type="button" class="link-btn" data-guide>Add yours</button></p>` : ''}
      <div class="hex-panel__actions">
        <button type="button" class="btn btn--primary" data-share-hex>Share this neighbourhood</button>
      </div>`;
    panel.querySelector('.hex-panel__close').addEventListener('click', clear);
    panel.querySelector('[data-guide]')?.addEventListener('click', onOpenGuide);
    panel.querySelector('[data-share-hex]').addEventListener('click', () =>
      panel.dispatchEvent(new CustomEvent('share-hex', { bubbles: true, detail: selected })),
    );
  }

  function clear() {
    selected = null;
    storyMap.select(null);
    history.replaceState(null, '', window.location.pathname + window.location.search);
    renderPanel();
    listeners.forEach((fn) => fn(null));
  }

  function setVisible(on) {
    panel.classList.toggle('is-visible', on);
  }

  // ---------- deep links ----------
  async function openFromLink(link) {
    if (link.place) {
      const it = items.find((i) => i.slug === link.place);
      if (it) await goTo(it, it.sub === 'Locality' ? it.label : `${it.sub} · ${it.label}`);
      return;
    }
    await goTo({ lat: link.lat, lng: link.lng }, null);
  }

  return {
    openFromLink,
    setVisible,
    getSelected: () => selected,
    onChange: (fn) => listeners.add(fn),
    focusSearch: () => input.focus({ preventScroll: true }),
  };
}

function decileStrip(dc) {
  const cells = DECILE_COLOURS.map((c, i) =>
    `<span class="decile__cell${i + 1 === dc ? ' is-here' : ''}" style="background:${c}"></span>`).join('');
  return `<div class="decile" role="img" aria-label="Decile ${dc} of 10, where 10 is hottest">
    ${cells}<span class="decile__ends"><span>Coolest</span><span>Hottest</span></span></div>`;
}
