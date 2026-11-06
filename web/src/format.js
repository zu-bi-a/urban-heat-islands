// Number formatting for story text. Population is modelled, so it is always
// rounded and introduced with "about" (see PRD, Ethics).

// International grouping, to sit consistently next to "million".
const nf = new Intl.NumberFormat('en-GB');

export function people(n) {
  if (n == null) return '—';
  if (n >= 1e6) return `about ${(n / 1e6).toFixed(1).replace(/\.0$/, '')} million`;
  if (n >= 1e4) return `about ${nf.format(Math.round(n / 1e4) * 1e4)}`;
  if (n >= 1e3) return `about ${nf.format(Math.round(n / 1e3) * 1e3)}`;
  return `about ${nf.format(Math.round(n / 100) * 100)}`;
}

export function deg(c, digits = 1) {
  return c == null ? '—' : `${c.toFixed(digits)} °C`;
}

export function pct(p) {
  return p == null ? '—' : `${Math.round(p)}%`;
}

export function km(a, b) {
  const r = Math.PI / 180;
  const h =
    Math.sin(((b.lat - a.lat) * r) / 2) ** 2 +
    Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(((b.lng - a.lng) * r) / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}

export function escape(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}
