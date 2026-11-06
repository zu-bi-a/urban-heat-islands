// Share cards, drawn in the browser on a 1080×1350 canvas (Instagram/WhatsApp
// portrait) from data already loaded; no server. Card rules (PRD): every card
// carries the date range, "daytime surface temperature (satellite)" and the
// data credits including Mapillary photographers; all context lives inside the
// image because shared images travel without captions; no photos of people or
// homes, and no labels like "slum".

import { people, deg, pct } from './format.js';
import { DECILE_COLOURS } from './palette.js';
import { track } from './track.js';

const W = 1080;
const H = 1350;
const M = 72;
const SERIF = '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif';
const SANS = 'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif';
const C = {
  bg: '#f6f3ee', ink: '#1f1b16', ink2: '#5a5249', ink3: '#8a8178',
  hot: '#be322e', cool: '#2f6f8f', track: '#e6dfd4', band: '#1f1b16', note: '#ece6dc',
};

export function siteUrl() {
  return (import.meta.env.VITE_SITE_URL || window.location.origin).replace(/\/$/, '');
}

// ---------- drawing helpers ----------

function canvas() {
  const el = document.createElement('canvas');
  el.width = W;
  el.height = H;
  const ctx = el.getContext('2d');
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, W, H);
  ctx.textBaseline = 'alphabetic';
  return { el, ctx };
}

function font(ctx, size, { family = SANS, weight = 400 } = {}) {
  ctx.font = `${weight} ${size}px ${family}`;
}

function wrap(ctx, text, maxWidth, maxLines = Infinity) {
  const words = String(text).split(/\s+/);
  const lines = [];
  let line = '';
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = w;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    let last = kept[maxLines - 1];
    while (ctx.measureText(`${last}…`).width > maxWidth && last.length) last = last.slice(0, -1);
    kept[maxLines - 1] = `${last.trimEnd()}…`;
    return kept;
  }
  return lines;
}

/** Draws wrapped text, returns the y below the last line. */
function text(ctx, str, x, y, { size, lineHeight = 1.25, maxWidth = W - 2 * M, maxLines, colour = C.ink, ...f }) {
  font(ctx, size, f);
  ctx.fillStyle = colour;
  const lh = size * lineHeight;
  const lines = wrap(ctx, str, maxWidth, maxLines);
  lines.forEach((l, i) => ctx.fillText(l, x, y + size + i * lh));
  return y + size + (lines.length - 1) * lh + (lh - size);
}

function roundRect(ctx, x, y, w, h, r, fill) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fillStyle = fill;
  ctx.fill();
}

function header(ctx, period) {
  ctx.fillStyle = C.band;
  ctx.fillRect(0, 0, W, 96);
  font(ctx, 26, { weight: 700 });
  ctx.fillStyle = '#fff';
  ctx.letterSpacing = '4px';
  ctx.fillText('DELHI HEAT GAP', M, 59);
  ctx.letterSpacing = '0px';
  font(ctx, 24);
  ctx.fillStyle = '#d9cfc2';
  ctx.textAlign = 'right';
  ctx.fillText(period, W - M, 59);
  ctx.textAlign = 'left';
}

function footer(ctx, { note, credits, cta }) {
  // Laid out bottom-up so the URL is always in the same place.
  font(ctx, 30, { weight: 700 });
  ctx.fillStyle = C.ink;
  const host = siteUrl().replace(/^https?:\/\//, '');
  ctx.fillText(host, M, H - 56);
  font(ctx, 26);
  ctx.fillStyle = C.ink2;
  ctx.textAlign = 'right';
  ctx.fillText(cta, W - M, H - 56);
  ctx.textAlign = 'left';
  ctx.fillStyle = C.track;
  ctx.fillRect(M, H - 110, W - 2 * M, 2);

  font(ctx, 20);
  const creditLines = wrap(ctx, credits, W - 2 * M, 3);
  const creditTop = H - 130 - creditLines.length * 26;
  ctx.fillStyle = C.ink3;
  creditLines.forEach((l, i) => ctx.fillText(l, M, creditTop + 20 + i * 26));

  font(ctx, 24);
  const noteLines = wrap(ctx, note, W - 2 * M - 48, 4);
  const noteH = noteLines.length * 32 + 36;
  const noteTop = creditTop - 24 - noteH;
  roundRect(ctx, M, noteTop, W - 2 * M, noteH, 14, C.note);
  ctx.fillStyle = C.ink2;
  noteLines.forEach((l, i) => ctx.fillText(l, M + 24, noteTop + 18 + 24 + i * 32));
  return noteTop; // content must end above this
}

function watermark(ctx) {
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.rotate(-Math.PI / 7);
  font(ctx, 120, { weight: 800 });
  ctx.fillStyle = 'rgba(190, 50, 46, 0.16)';
  ctx.textAlign = 'center';
  ctx.fillText('SAMPLE DATA', 0, 0);
  ctx.restore();
}

function credits(extra = []) {
  const base = 'Data: Landsat (USGS), VIIRS (NASA), WorldPop (CC-BY 4.0), ESA WorldCover';
  return extra.length ? `${base}. ${extra.join(' ')}` : `${base}. Street photos: Mapillary contributors (CC-BY-SA 4.0).`;
}

function photographers(names) {
  const shown = names.slice(0, 5).join(', ');
  const more = names.length > 5 ? ` and ${names.length - 5} more` : '';
  return `Street photos: Mapillary contributors ${shown}${more} (CC-BY-SA 4.0).`;
}

// ---------- card 1: two streets ----------

export function drawStreetsCard(pair, stats, { sample } = {}) {
  const { el, ctx } = canvas();
  header(ctx, stats.periods?.day ?? '');
  footer(ctx, {
    note: 'Surface, not air: how hot roofs and roads get around 10:30 am. Less shade, more heat is a pattern across many streets, not a verdict on one.',
    credits: credits([photographers([...new Set([...pair.hot.credits, ...pair.cool.credits])])]),
    cta: 'Find your neighbourhood →',
  });

  let y = 140;
  y = text(ctx, 'TWO DELHI STREETS, ONE MORNING', M, y, { size: 26, weight: 700, colour: C.ink2 });
  y = text(ctx, `${pair.diff_c.toFixed(1)} °C apart`, M, y + 10, {
    size: 76, family: SERIF, weight: 600, lineHeight: 1.1, maxLines: 1,
  });
  y = text(ctx, 'Daytime surface temperature (satellite)', M, y + 10, { size: 28, colour: C.ink2 });

  const gap = 48;
  const colW = (W - 2 * M - gap) / 2;
  const top = y + 44;
  [['hot', pair.hot], ['cool', pair.cool]].forEach(([kind, s], i) => {
    const x = M + i * (colW + gap);
    const colour = kind === 'hot' ? C.hot : C.cool;
    ctx.fillStyle = colour;
    ctx.fillRect(x, top, colW, 10);
    let cy = text(ctx, s.name, x, top + 26, { size: 38, family: SERIF, weight: 600, maxWidth: colW, maxLines: 2, lineHeight: 1.15 });
    if (s.area) cy = text(ctx, s.area, x, cy + 4, { size: 24, colour: C.ink3, maxWidth: colW, maxLines: 1 });
    cy = text(ctx, deg(s.lst_day), x, cy + 14, { size: 80, family: SERIF, weight: 600, colour, maxWidth: colW });
    cy += 20;
    for (const [label, key] of [['Trees in view', 'tree_pct'], ['Open sky', 'sky_pct'], ['Buildings', 'building_pct']]) {
      font(ctx, 26);
      ctx.fillStyle = C.ink2;
      ctx.fillText(label, x, cy + 26);
      font(ctx, 26, { weight: 700 });
      ctx.fillStyle = C.ink;
      ctx.textAlign = 'right';
      ctx.fillText(pct(s[key]), x + colW, cy + 26);
      ctx.textAlign = 'left';
      roundRect(ctx, x, cy + 40, colW, 16, 8, C.track);
      roundRect(ctx, x, cy + 40, Math.max(16, (colW * Math.min(100, s[key])) / 100), 16, 8, colour);
      cy += 76;
    }
    text(ctx, `${people(s.people_500m).replace(/^about/, 'About')} people live within 500 m`, x, cy + 4, {
      size: 24, colour: C.ink2, maxWidth: colW, maxLines: 2,
    });
  });
  if (sample) watermark(ctx);
  return el;
}

// ---------- card 2: my neighbourhood ----------

export function drawNeighbourhoodCard(sel, stats, { sample } = {}) {
  const { el, ctx } = canvas();
  header(ctx, stats.periods?.day ?? '');
  footer(ctx, {
    note: 'Daytime surface temperature (satellite): how hot roofs and roads get around 10:30 am, not air temperature. Population is modelled, so numbers are estimates.',
    credits: credits(),
    cta: 'Check your street →',
  });

  const diff = sel.d - stats.median_day_c;
  // Within half a degree of the median is "about typical": don't colour it.
  const colour = Math.abs(diff) < 0.5 ? C.ink : diff > 0 ? C.hot : C.cool;
  let y = 140;
  y = text(ctx, 'MY NEIGHBOURHOOD IN THE HEAT', M, y, { size: 26, weight: 700, colour: C.ink2 });
  y = text(ctx, sel.label, M, y + 10, { size: 64, family: SERIF, weight: 600, lineHeight: 1.1, maxLines: 2 });
  y = text(ctx, deg(sel.d), M, y + 24, { size: 150, family: SERIF, weight: 600, colour, lineHeight: 1 });
  y = text(
    ctx,
    `${Math.abs(diff).toFixed(1)} °C ${diff >= 0 ? 'hotter' : 'cooler'} than the Delhi median (${deg(stats.median_day_c)})`,
    M, y + 16, { size: 32, colour: C.ink, maxLines: 2 },
  );
  y = text(ctx, 'Daytime surface temperature (satellite)', M, y + 6, { size: 26, colour: C.ink3 });

  const dc = Number(sel.dc);
  if (dc > 0) {
    const cellW = (W - 2 * M - 9 * 6) / 10;
    const top = y + 40;
    DECILE_COLOURS.forEach((c, i) => {
      roundRect(ctx, M + i * (cellW + 6), top, cellW, 36, 6, c);
      if (i + 1 === dc) {
        ctx.lineWidth = 5;
        ctx.strokeStyle = C.ink;
        ctx.beginPath();
        ctx.roundRect(M + i * (cellW + 6) - 4, top - 4, cellW + 8, 44, 8);
        ctx.stroke();
      }
    });
    font(ctx, 22);
    ctx.fillStyle = C.ink3;
    ctx.fillText('Coolest tenth', M, top + 70);
    ctx.textAlign = 'right';
    ctx.fillText('Hottest tenth of Delhi', W - M, top + 70);
    ctx.textAlign = 'left';
    y = top + 84;
  }

  const facts = [];
  if (sel.nr != null) facts.push(['Night', `${Number(sel.nr) >= 0 ? '+' : '−'}${Math.abs(Number(sel.nr)).toFixed(1)} °C vs a typical Delhi night`]);
  if (sel.t != null) facts.push(['Tree cover', `${pct(Number(sel.t))} of the area`]);
  if (sel.p != null) facts.push(['People', `${people(Number(sel.p)).replace(/^about/, 'About')} live in this ~0.1 km² hexagon`]);
  y += 30;
  for (const [k, v] of facts) {
    ctx.fillStyle = C.track;
    ctx.fillRect(M, y, W - 2 * M, 2);
    text(ctx, k, M, y + 14, { size: 28, weight: 700, maxWidth: 220 });
    text(ctx, v, M + 240, y + 14, { size: 28, colour: C.ink2, maxWidth: W - 2 * M - 240, maxLines: 2 });
    y += 82;
  }
  if (sample) watermark(ctx);
  return el;
}

// ---------- share or download ----------

export async function shareCanvas(el, { filename, title, text: body, url, event }) {
  const blob = await new Promise((r) => el.toBlob(r, 'image/png'));
  const file = new File([blob], filename, { type: 'image/png' });
  track(event);
  // PRD: the native share sheet on phones, a plain download elsewhere. Some
  // desktop browsers support file sharing too, but a download is what people
  // expect there.
  const touch = window.matchMedia('(pointer: coarse)').matches;
  if (touch && navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title, text: `${body} ${url}` });
      return 'shared';
    } catch (err) {
      if (err.name === 'AbortError') return 'cancelled';
      // Fall through to download if the share sheet failed for another reason.
    }
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  return 'downloaded';
}
