// Privacy-friendly event counting (PRD success metrics). Wired to Cloudflare
// Web Analytics in Phase 5; nothing about the reader is stored.

export function track(name) {
  if (import.meta.env.DEV) console.debug('[track]', name);
}
