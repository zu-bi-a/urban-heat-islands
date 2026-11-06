import { defineConfig, loadEnv } from 'vite';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const DATA = resolve(__dirname, 'public/data');

// Refuse to build a deployable site from synthetic data. Local builds of the
// sample can opt in with ALLOW_SAMPLE=1 (npm run build:sample).
function sampleGuard() {
  return {
    name: 'sample-guard',
    apply: 'build',
    buildStart() {
      const flagged = ['city_stats.json', 'streets.json'].filter((f) => {
        const p = resolve(DATA, f);
        return existsSync(p) && JSON.parse(readFileSync(p, 'utf8')).sample === true;
      });
      if (!flagged.length) return;
      const msg = `${flagged.join(' and ')} contain SAMPLE data.`;
      if (process.env.ALLOW_SAMPLE === '1') this.warn(`${msg} Building anyway (ALLOW_SAMPLE=1); do not deploy this.`);
      else this.error(`${msg} Run the real pipeline first, or use \`npm run build:sample\` for a local test build.`);
    },
  };
}

// Absolute preview-image tags and optional analytics, injected at build time.
function headTags(env) {
  const site = (env.VITE_SITE_URL || '').replace(/\/$/, '');
  return {
    name: 'head-tags',
    transformIndexHtml: {
      order: 'post',
      handler(html, ctx) {
        const tags = [];
        if (site) {
          const page = ctx.path === '/index.html' ? '/' : ctx.path;
          tags.push({ tag: 'meta', attrs: { property: 'og:url', content: `${site}${page}` }, injectTo: 'head' });
          tags.push({ tag: 'meta', attrs: { property: 'og:image', content: `${site}/og.png` }, injectTo: 'head' });
          tags.push({ tag: 'meta', attrs: { name: 'twitter:card', content: 'summary_large_image' }, injectTo: 'head' });
          tags.push({ tag: 'link', attrs: { rel: 'canonical', href: `${site}${page}` }, injectTo: 'head' });
        }
        if (ctx.server) return { html, tags }; // no analytics in dev
        if (env.VITE_CF_BEACON_TOKEN) {
          tags.push({
            tag: 'script',
            attrs: {
              defer: true,
              src: 'https://static.cloudflareinsights.com/beacon.min.js',
              'data-cf-beacon': JSON.stringify({ token: env.VITE_CF_BEACON_TOKEN }),
            },
            injectTo: 'body',
          });
        }
        if (env.VITE_GOATCOUNTER_CODE) {
          tags.push({
            tag: 'script',
            attrs: {
              async: true,
              src: 'https://gc.zgo.at/count.js',
              'data-goatcounter': `https://${env.VITE_GOATCOUNTER_CODE}.goatcounter.com/count`,
            },
            injectTo: 'body',
          });
        }
        return { html, tags };
      },
    },
  };
}

// Link previews (WhatsApp, Instagram) cannot read "#place=…" hashes, so each
// locality gets a tiny page with its own title that forwards into the explorer.
function placePages(env) {
  const slugify = (s) =>
    s.toLowerCase().normalize('NFKD').replace(/[^\w\s-]/g, '').trim().replace(/[\s_]+/g, '-');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
  return {
    name: 'place-pages',
    apply: 'build',
    closeBundle() {
      const src = resolve(DATA, 'places.json');
      if (!existsSync(src)) return;
      const site = (env.VITE_SITE_URL || '').replace(/\/$/, '');
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
${site ? `<meta property="og:url" content="${site}/p/${slug}/">\n<link rel="canonical" href="${site}/p/${slug}/">` : ''}
${ogImage ? `<meta property="og:image" content="${ogImage}">\n<meta name="twitter:card" content="summary_large_image">` : ''}
<meta http-equiv="refresh" content="0; url=${target}">
</head><body><p><a href="${target}">${esc(title)}</a></p>
<script>location.replace(${JSON.stringify(target)})</script></body></html>`,
        );
      }
      console.log(`place-pages: wrote ${places.length} pages to dist/p/`);
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, 'VITE_');
  return {
    plugins: [sampleGuard(), headTags(env), placePages(env)],
    build: {
      target: 'es2022',
      // MapLibre alone is ~1 MB minified (~300 kB gzipped); that is expected.
      chunkSizeWarningLimit: 1300,
      rolldownOptions: {
        input: {
          main: resolve(__dirname, 'index.html'),
          methods: resolve(__dirname, 'methods.html'),
        },
      },
    },
  };
});
