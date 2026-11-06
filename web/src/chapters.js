// The seven chapters. Each is one map state plus at most ~40 words of text.
// Every number is filled from city_stats.json / streets.json, never typed in.
// Limitation notes are part of the story text, not footnotes (PRD, Ethics).

import { people, deg, pct, km, escape } from './format.js';
import { DECILE_COLOURS, NIGHT_STOPS, HOT, MUTED } from './palette.js';

// IMD, via PTI: 35.2 °C minimum on 19 June 2024, the warmest night in 12-14
// years (outlets differ; pre-1969 records are unanalysed, so not "on record").
const RECORD_NIGHT_SOURCE =
  'https://theprint.in/india/delhi-records-warmest-night-in-14-years-at-35-2-degrees-celsius-spike-in-heatstroke-casualties/2138688/';

function dayLegend(stats) {
  const b = stats.decile_breaks_c ?? [];
  return {
    title: 'Daytime surface temperature',
    ramp: DECILE_COLOURS,
    labels: [b[0] != null ? `< ${Math.round(b[0])} °C` : 'Cooler',
             b[8] != null ? `> ${Math.round(b[8])} °C` : 'Hotter'],
    footnote: `Coolest to hottest tenth of neighbourhoods. Satellite, ${stats.periods?.day ?? ''}`,
  };
}

function bars(pair) {
  const rows = [
    ['Trees in view', 'tree_pct'],
    ['Open sky', 'sky_pct'],
    ['Buildings', 'building_pct'],
  ];
  const side = (s, kind) => `
    <div class="compare__col compare__col--${kind}">
      <p class="compare__name">${escape(s.name)}</p>
      <p class="compare__temp">${deg(s.lst_day)}</p>
      ${rows.map(([label, key]) => `
        <div class="bar" role="img" aria-label="${label}: ${pct(s[key])}">
          <span class="bar__label">${label}</span>
          <span class="bar__track"><span class="bar__fill" style="--w:${Math.min(100, s[key])}%"></span></span>
          <span class="bar__value">${pct(s[key])}</span>
        </div>`).join('')}
      <p class="compare__people">${people(s.people_500m)} people live within 500 m</p>
    </div>`;
  return `<div class="compare">${side(pair.hot, 'hot')}${side(pair.cool, 'cool')}</div>`;
}

function photoCredit(pair, streets) {
  const n = pair.hot.n_images + pair.cool.n_images;
  const years = [...pair.hot.years, ...pair.cool.years];
  const names = [...new Set([...pair.hot.credits, ...pair.cool.credits])];
  const shown = names.slice(0, 4).map(escape).join(', ') + (names.length > 4 ? ` and ${names.length - 4} more` : '');
  return `Bars average ${n} street photos (${Math.min(...years)}–${Math.max(...years)}) by Mapillary contributors ${shown}. ${escape(streets.licence ?? '')}`;
}

export function buildChapters(stats, streets) {
  const pair = streets?.pairs?.[0];
  const hasNight = stats.median_night_c != null;

  const chapters = [
    {
      id: 1,
      kicker: '19 June 2024',
      title: 'The hottest night',
      big: '35.2 °C',
      body: `Delhi’s temperature never fell below 35.2 °C that night, its warmest in more than a decade. But the heat was not shared equally. Some streets carry far more of it than others.`,
      source: { label: 'Source: IMD, via PTI (ThePrint)', href: RECORD_NIGHT_SOURCE },
      state: { look: 'teaser', camera: 'delhi' },
    },
    {
      id: 2,
      kicker: 'The heat gap',
      title: 'One city, many temperatures',
      big: `${stats.heat_gap_c?.toFixed(1)} °C`,
      body: `On pre-monsoon mornings, the hottest tenth of Delhi’s neighbourhoods reaches about ${deg(stats.hot10_median_c, 0)} at the surface. The coolest tenth stays near ${deg(stats.cool10_median_c, 0)}. Same city, same sun.`,
      note: 'Surface is not air. This is how hot roofs and roads get around 10:30 am, not the air you breathe or the heat inside a room at night.',
      legend: dayLegend(stats),
      state: { look: 'day', camera: 'delhi' },
    },
    {
      id: 3,
      kicker: 'After dark',
      title: 'The city does not cool down',
      body: hasNight
        ? `At night, dense neighbourhoods with few trees hold on to the day’s heat. Red areas stay warmer than Delhi’s typical night; blue areas cool off faster.`
        : `Night-time satellite data has not been processed yet for this version.`,
      note: 'Night data is coarse. Each reading covers about 1 km, so this shows broad patterns, not single streets.',
      legend: hasNight && {
        title: 'Night surface temperature vs typical Delhi night',
        ramp: NIGHT_STOPS.map(([, c]) => c),
        labels: ['Cools faster', 'Stays warmer'],
        footnote: `Satellite, ~1:30 am, ${stats.periods?.night ?? ''}`,
      },
      state: { look: hasNight ? 'night' : 'day', camera: 'delhi' },
    },
    {
      id: 4,
      kicker: 'Who lives in the heat',
      title: `${people(stats.people_in_heat).replace('about ', 'About ')} people`,
      body: `live in Delhi’s hottest tenth of neighbourhoods. Among them are ${people(stats.children_u5_in_heat)} children under five and ${people(stats.older_65_in_heat)} adults over 65, the people heat harms first.`,
      note: 'Population is modelled from satellite data and older census counts, not counted door to door. Treat these as estimates.',
      legend: {
        title: 'Neighbourhoods',
        swatches: [[HOT, 'Hottest tenth'], [MUTED, 'Everywhere else']],
      },
      state: { look: 'people', camera: 'delhi' },
    },
  ];

  if (pair) {
    const dist = km(pair.hot, pair.cool);
    chapters.push({
      id: 5,
      kicker: 'Why some streets run hotter',
      title: 'Two streets, one afternoon',
      body: `${escape(pair.hot.name)} runs ${deg(pair.diff_c)} hotter at the surface than ${escape(pair.cool.name)}, ${dist.toFixed(0)} km away. Trees fill ${pct(pair.cool.tree_pct)} of the street view on one, ${pct(pair.hot.tree_pct)} on the other.`,
      extra: bars(pair),
      note: 'Less shade, more heat is a pattern across many streets, not a verdict on any one street.',
      credit: photoCredit(pair, streets),
      state: { look: 'streets', camera: { points: [pair.hot, pair.cool] }, pair },
    });
  }

  chapters.push(
    {
      id: 6,
      kicker: 'Your turn',
      title: 'Your neighbourhood',
      body: `Find where you live. Search, use your location or tap a hexagon to see how it compares with the Delhi median of ${deg(stats.median_day_c, 0)}.`,
      legend: dayLegend(stats),
      state: { look: 'explore', camera: 'delhi', interactive: true },
      explorer: true,
    },
    {
      id: 7,
      kicker: 'Share and act',
      title: 'Pass it on',
      body: `Heat gaps close when people see them. Share the two-street comparison, or add photos of your own street so the next update can see it too.`,
      state: { look: 'explore', camera: 'delhi', interactive: true },
      actions: true,
    },
  );
  return chapters;
}
