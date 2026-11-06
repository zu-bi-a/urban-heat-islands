// Chapter 7: one main action (share the two-street card) and lighter ones
// below it. Each costs under 30 seconds and needs no account (PRD, End actions).

import { drawStreetsCard, drawNeighbourhoodCard, shareCanvas, siteUrl } from './sharecard.js';
import { slugify } from './explorer.js';
import { track } from './track.js';

export function createActions({ slot, stats, streets, explorer, storyMap, sample }) {
  const pair = streets?.pairs?.[0];

  slot.innerHTML = `
    ${pair ? `
      <div class="share-main">
        <button type="button" class="share-main__preview" data-share-streets aria-label="Share the two-street card">
          <img alt="" id="card-preview" width="216" height="270" />
        </button>
        <div>
          <button type="button" class="btn btn--primary" data-share-streets>Share “Two streets”</button>
          <p class="share-main__hint">An image sized for WhatsApp and Instagram. Sources and credits are printed on it.</p>
        </div>
      </div>` : ''}
    <ul class="actions">
      <li>
        <button type="button" class="action" data-share-mine>
          <strong>Share my neighbourhood</strong>
          <span id="mine-hint">Pick an area in step 6 first.</span>
        </button>
      </li>
      <li>
        <button type="button" class="action" data-guide aria-haspopup="dialog">
          <strong>Fill the photo gap</strong>
          <span>Record your street with the free Mapillary app.</span>
        </button>
      </li>
    </ul>
    <p class="status-line" role="status" id="share-status"></p>`;

  const status = slot.querySelector('#share-status');
  const say = (msg) => {
    status.textContent = msg;
    setTimeout(() => (status.textContent === msg ? (status.textContent = '') : null), 5000);
  };
  const result = (r) => r === 'downloaded' && say('Image saved. Post it anywhere you like.');

  // ---- two streets ----
  if (pair) {
    const preview = slot.querySelector('#card-preview');
    // Draw the preview lazily, when the reader is near the end of the story.
    new IntersectionObserver((entries, obs) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      preview.src = drawStreetsCard(pair, stats, { sample }).toDataURL('image/png');
      obs.disconnect();
    }, { rootMargin: '400px' }).observe(slot);

    slot.querySelectorAll('[data-share-streets]').forEach((b) =>
      b.addEventListener('click', async () => {
        const el = drawStreetsCard(pair, stats, { sample });
        result(await shareCanvas(el, {
          filename: 'delhi-heat-gap-two-streets.png',
          title: 'Two Delhi streets, one morning',
          text: `Two Delhi streets, ${pair.diff_c.toFixed(1)} °C apart at the surface. Why?`,
          url: siteUrl(),
          event: 'share_streets',
        }));
      }),
    );
  }

  // ---- my neighbourhood ----
  const mineHint = slot.querySelector('#mine-hint');
  explorer.onChange((sel) => {
    mineHint.textContent = sel ? sel.label : 'Pick an area in step 6 first.';
  });

  async function shareMine(sel) {
    const el = drawNeighbourhoodCard(sel, stats, { sample });
    const link = `${siteUrl()}/#n=${sel.h}&ll=${sel.centre.lat.toFixed(5)},${sel.centre.lng.toFixed(5)}`;
    result(await shareCanvas(el, {
      filename: `delhi-heat-gap-${slugify(sel.label) || 'neighbourhood'}.png`,
      title: `${sel.label} in the heat`,
      text: `How hot does ${sel.label} get compared with the rest of Delhi?`,
      url: link,
      event: 'share_neighbourhood',
    }));
  }

  slot.querySelector('[data-share-mine]').addEventListener('click', () => {
    const sel = explorer.getSelected();
    if (sel) return shareMine(sel);
    document.getElementById('chapter-6').scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(() => explorer.focusSearch(), 700);
  });
  document.addEventListener('share-hex', (e) => shareMine(e.detail));

  // ---- photo gap guide ----
  const guide = buildGuide(storyMap);
  slot.querySelector('[data-guide]').addEventListener('click', guide.open);
  return { openGuide: guide.open };
}

function buildGuide(storyMap) {
  const dlg = document.createElement('dialog');
  dlg.className = 'guide';
  dlg.setAttribute('aria-labelledby', 'guide-title');
  dlg.innerHTML = `
    <form method="dialog" class="guide__inner">
      <button class="guide__close" value="close" aria-label="Close">×</button>
      <h2 id="guide-title">Fill the photo gap</h2>
      <p>Street photos show <em>why</em> a street runs hot: shade, open sky, hard roofs. Many Delhi streets have none yet.</p>
      <ol>
        <li>Install the free <strong>Mapillary</strong> app from your app store.</li>
        <li>Mount your phone facing forward, on a two-wheeler or held while walking.</li>
        <li>Record in daylight. Point along the road, not into homes. Mapillary blurs faces and number plates.</li>
        <li>Upload. Photos are public under CC-BY-SA, credited to you, and feed the next update of this map.</li>
      </ol>
      <label class="toggle">
        <input type="checkbox" id="coverage-toggle" />
        <span>Show areas with few street photos (blue) on the map</span>
      </label>
      <p class="guide__foot"><a href="https://www.mapillary.com/" target="_blank" rel="noopener">mapillary.com</a></p>
    </form>`;
  document.body.appendChild(dlg);

  const toggle = dlg.querySelector('#coverage-toggle');
  toggle.addEventListener('change', () => {
    storyMap.setOverlay(toggle.checked ? 'coverage' : null);
    if (toggle.checked) track('coverage_overlay');
  });
  // Scrolling back into the story clears overlays; keep the checkbox honest.
  document.addEventListener('chapter-change', (e) => {
    if (!e.detail.interactive) toggle.checked = false;
  });

  return {
    open: () => {
      track('photo_guide');
      dlg.showModal();
    },
  };
}
