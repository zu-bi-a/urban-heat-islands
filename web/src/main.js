import scrollama from 'scrollama';
import './styles.css';
import { buildChapters } from './chapters.js';
import { createMap, isMobile } from './map.js';
import { createExplorer, parseHash } from './explorer.js';
import { createActions } from './actions.js';
import { escape } from './format.js';
import { track } from './track.js';

const DATA = '/data';

async function loadJSON(name, optional = false) {
  const res = await fetch(`${DATA}/${name}`);
  if (!res.ok) {
    if (optional) return null;
    throw new Error(`${name}: HTTP ${res.status}`);
  }
  return res.json();
}

function renderLegend(el, legend) {
  if (!legend) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const ramp = legend.ramp
    ? `<div class="legend__ramp" style="--ramp:linear-gradient(90deg, ${legend.ramp.join(',')})"></div>
       <div class="legend__ends"><span>${escape(legend.labels[0])}</span><span>${escape(legend.labels[1])}</span></div>`
    : '';
  const swatches = legend.swatches
    ? `<ul class="legend__swatches">${legend.swatches
        .map(([c, label]) => `<li><span style="background:${c}"></span>${escape(label)}</li>`)
        .join('')}</ul>`
    : '';
  el.innerHTML = `<p class="legend__title">${escape(legend.title)}</p>${ramp}${swatches}${
    legend.footnote ? `<p class="legend__foot">${escape(legend.footnote)}</p>` : ''
  }`;
}

function renderStep(ch) {
  const section = document.createElement('section');
  section.className = 'step';
  section.id = `chapter-${ch.id}`;
  section.dataset.step = String(ch.id);
  section.setAttribute('aria-labelledby', `chapter-${ch.id}-title`);
  section.innerHTML = `
    <div class="card">
      <p class="card__kicker"><span class="card__num">${ch.id}</span>${escape(ch.kicker)}</p>
      ${ch.big ? `<p class="card__big">${escape(ch.big)}</p>` : ''}
      <h2 class="card__title" id="chapter-${ch.id}-title">${escape(ch.title)}</h2>
      <p class="card__body">${ch.body}</p>
      ${ch.extra ?? ''}
      ${ch.note ? `<p class="card__note"><span aria-hidden="true">ⓘ</span> ${escape(ch.note)}</p>` : ''}
      ${ch.credit ? `<p class="card__credit">${ch.credit}</p>` : ''}
      ${ch.source ? `<p class="card__credit"><a href="${ch.source.href}" target="_blank" rel="noopener">${escape(ch.source.label)}</a></p>` : ''}
      ${ch.explorer ? '<div class="explorer-slot" id="explorer-slot"></div>' : ''}
      ${ch.actions ? '<div class="actions-slot" id="actions-slot"></div>' : ''}
      ${ch.id === 1 ? '<p class="card__hint" aria-hidden="true">Scroll ↓</p>' : ''}
    </div>`;
  return section;
}

function renderFooter(el, stats) {
  el.innerHTML = `
    <div class="site-footer__inner">
      <h2>About this map</h2>
      <p>Hexagons are about 0.1 km², big enough to show neighbourhoods and small enough to hide individual homes. Heat figures use built-up areas only, leaving out the Yamuna, the ridge forest and farmland.</p>
      <p>Street photos may be a few years old; each comparison shows its capture years. Death and illness figures are not mapped: official and NGO counts differ widely and the data cannot support them by area.</p>
      <h3>Data</h3>
      <ul class="credits">${(stats.credits ?? []).map((c) => `<li>${escape(c)}</li>`).join('')}</ul>
      <p class="site-footer__small">Population: ${escape(stats.versions?.population ?? '')}. Data generated ${escape(stats.generated ?? '')}.</p>
    </div>`;
}

function trackProgress() {
  const bar = document.getElementById('progress-bar');
  const update = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.transform = `scaleX(${max > 0 ? Math.min(1, window.scrollY / max) : 0})`;
  };
  window.addEventListener('scroll', update, { passive: true });
  update();
}

async function main() {
  const status = document.getElementById('map-status');
  let stats, streets, places, wards;
  try {
    [stats, streets, places, wards] = await Promise.all([
      loadJSON('city_stats.json'),
      loadJSON('streets.json', true),
      loadJSON('places.json', true),
      loadJSON('wards.json', true),
    ]);
  } catch (err) {
    status.textContent = 'The data could not be loaded. Please check your connection and reload.';
    console.error(err);
    return;
  }
  const sample = Boolean(stats.sample || streets?.sample);
  if (sample) document.getElementById('sample-banner').hidden = false;
  const link = parseHash();

  const chapters = buildChapters(stats, streets);
  const stepsEl = document.getElementById('steps');
  chapters.forEach((ch) => stepsEl.appendChild(renderStep(ch)));
  renderFooter(document.getElementById('footer'), stats);
  trackProgress();

  const legendEl = document.getElementById('legend');
  const storyMap = createMap('map', { pmtilesUrl: `${DATA}/hexes.pmtiles` });
  storyMap.map.on('error', (e) => console.warn('Map:', e.error?.message ?? e));

  let actions;
  const explorer = createExplorer({
    storyMap,
    stats,
    places: places ?? [],
    wards: wards ?? [],
    slot: document.getElementById('explorer-slot'),
    panelHost: document.querySelector('.story-map'),
    onOpenGuide: () => actions?.openGuide(),
  });
  actions = createActions({
    slot: document.getElementById('actions-slot'),
    stats,
    streets,
    explorer,
    storyMap,
    sample,
  });

  const byId = new Map(chapters.map((c) => [String(c.id), c]));
  const lastId = String(chapters.at(-1).id);
  let active = null;
  const activate = (id) => {
    if (id === active) return;
    active = id;
    const ch = byId.get(id);
    document.querySelectorAll('.step').forEach((s) => s.classList.toggle('is-active', s.dataset.step === id));
    document.body.dataset.chapter = id;
    renderLegend(legendEl, ch.legend);
    storyMap.apply(ch.state);
    explorer.setVisible(Boolean(ch.state.interactive));
    document.dispatchEvent(new CustomEvent('chapter-change', { detail: { id, interactive: Boolean(ch.state.interactive) } }));
    if (id === lastId) track('story_complete');
  };

  // Shared links skip the story and land on "Your neighbourhood", with the
  // story one tap away (PRD story flow).
  if (link) {
    const target = document.getElementById('chapter-6');
    const back = document.createElement('button');
    back.type = 'button';
    back.className = 'link-btn back-to-start';
    back.textContent = '↑ Start the story from the beginning';
    back.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    target.querySelector('.card').prepend(back);
    window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY, behavior: 'instant' });
    track('enter_shared_link');
  }

  const scroller = scrollama();
  scroller
    .setup({ step: '.step', offset: isMobile() ? 0.85 : 0.55 })
    .onStepEnter(({ element }) => activate(element.dataset.step));
  window.addEventListener('resize', () => scroller.resize());

  if (link) {
    activate('6');
    await storyMap.ready;
    explorer.openFromLink(link);
  } else {
    activate(String(chapters[0].id));
  }
}

main();
