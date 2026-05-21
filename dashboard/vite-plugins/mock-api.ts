import { existsSync, readFileSync } from 'node:fs';
import { extname, join } from 'node:path';
import type { Plugin } from 'vite';

/**
 * Dev-only middleware that serves `mocks/<path>.json` for `/api/<path>` requests.
 * Replaces the wrangler-pages-dev proxy during `npm run dev` so the frontend can
 * be iterated on without ClickHouse or Workers.
 *
 * Production deploys (Cloudflare Pages) ignore this — the real Workers Functions
 * under `functions/` handle `/api/*` and the JSON files in `public/fallback-data/`
 * remain the prod fallback path.
 */
export function mockApi(mocksDir: string): Plugin {
  return {
    name: 'mylife-mock-api',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (!req.url || !req.url.startsWith('/api/')) return next();

        const urlPath = req.url.split('?')[0].replace(/^\/api\//, '').replace(/\/$/, '');
        const filePath = join(mocksDir, `${urlPath}.json`);

        if (!existsSync(filePath) || extname(filePath) !== '.json') {
          res.statusCode = 404;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ error: `No mock for /api/${urlPath} — add ${filePath}` }));
          return;
        }

        res.statusCode = 200;
        res.setHeader('Content-Type', 'application/json');
        res.setHeader('Cache-Control', 'no-store');
        res.setHeader('X-Data-Source', 'mock');
        res.end(readFileSync(filePath));
      });
    },
  };
}
