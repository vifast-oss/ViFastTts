import fs from 'node:fs';
import path from 'node:path';
import { defineConfig } from 'vite';

/**
 * ORT Web tự `import()` các file `.mjs` trong `/ort/`.
 * Vite chặn import module từ `public/`, nên dev server phải trả các file này
 * nguyên bản (không qua transform). Production dùng dist tĩnh nên không cần.
 */
function ortRawAssets() {
  return {
    name: 'vifasttts-ort-raw-assets',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const rawUrl = req.url ?? '';
        const pathname = rawUrl.split('?')[0];
        if (!pathname.startsWith('/ort/')) {
          next();
          return;
        }
        const file = path.join(server.config.publicDir, pathname.slice(1));
        if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {
          next();
          return;
        }
        const ext = path.extname(file).toLowerCase();
        const types = {
          '.mjs': 'text/javascript; charset=utf-8',
          '.js': 'text/javascript; charset=utf-8',
          '.wasm': 'application/wasm',
        };
        res.setHeader('Content-Type', types[ext] ?? 'application/octet-stream');
        res.setHeader('Cache-Control', 'no-cache');
        fs.createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [ortRawAssets()],
});
