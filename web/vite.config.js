import { defineConfig } from 'vite';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

// Link previews (WhatsApp, Instagram) cannot read "#place=…" hashes, so each
// locality gets a tiny page with its own title that forwards into the explorer.
function placePages() {
  const slugify = (s) =>
    s.toLowerCase().normalize('NFKD').replace(/[^\w\s-]/g, '').trim().replace(/[\s_]+/g, '-');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
  return {
    name: 'place-pages',
    apply: 'build',
    closeBundle() {
      const src = resolve(__dirname, 'public/data/places.json');
      if (!existsSync(src)) return;
      const site = (process.env.VITE_SITE_URL || '').replace(/\/$/, '');
      const ogImage = site && existsSync(resolve(__dirname, 'dist/og.png')) ? `${site}/og.png` : '';
      const places = JSON.parse(readFileSync(src, 'utf8'));
      for (const p of places) {
        const slug = slugify(p.name);
        const title = `How hot is ${p.name}? · Delhi Heat Gap`;
        const desc = `See how ${p.name}'s daytime surface heat compares with the rest of Delhi, and why some streets run hotter.`;
        const target = `/#place=${encodeURIComponent(slug)}`;
        const dir = resolve(__dirname, 'dist/p', slug);
        mkdirSync(dir, { recursive: true });
        writeFileSync(
          resolve(dir, 'index.html'),
          `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:type" content="website">
${site ? `<meta property="og:url" content="${site}/p/${slug}/">` : ''}
${ogImage ? `<meta property="og:image" content="${ogImage}">` : ''}
<meta http-equiv="refresh" content="0; url=${target}">
<link rel="canonical" href="${site}/p/${slug}/">
</head><body><p><a href="${target}">${esc(title)}</a></p>
<script>location.replace(${JSON.stringify(target)})</script></body></html>`,
        );
      }
      console.log(`place-pages: wrote ${places.length} pages to dist/p/`);
    },
  };
}

export default defineConfig({
  plugins: [placePages()],
  build: {
    target: 'es2022',
    // MapLibre alone is ~1 MB minified (~300 kB gzipped); that is expected.
    chunkSizeWarningLimit: 1300,
  },
});
