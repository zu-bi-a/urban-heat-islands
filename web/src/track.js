// Privacy-friendly event counting for the PRD success metrics (story
// completion, shares, own-area lookups). Events go to GoatCounter when
// VITE_GOATCOUNTER_CODE is set at build time: no cookies, nothing stored about
// the reader, only anonymous totals. Each event is counted once per page view.

const sent = new Set();

export function track(name) {
  if (import.meta.env.DEV) console.debug('[track]', name);
  if (sent.has(name)) return;
  sent.add(name);
  window.goatcounter?.count?.({ path: `event/${name}`, title: name, event: true });
}
