import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'tess-data-server',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (!req.url) return next();

          // Endpoint 1: Get list of available TIC IDs
          if (req.url === '/api/tic-ids') {
            try {
              const cleanDir = path.resolve(__dirname, '../data/clean/lightcurves');
              const rawDir = path.resolve(__dirname, '../data/raw/lightcurves');
              const files = new Set<string>();

              if (fs.existsSync(cleanDir)) {
                fs.readdirSync(cleanDir).forEach(f => {
                  if (f.startsWith('TIC_') && f.endsWith('.csv')) {
                    files.add(f.replace('TIC_', '').replace('.csv', ''));
                  }
                });
              }
              if (fs.existsSync(rawDir)) {
                fs.readdirSync(rawDir).forEach(f => {
                  if (f.startsWith('TIC_') && f.endsWith('.csv')) {
                    files.add(f.replace('TIC_', '').replace('.csv', ''));
                  }
                });
              }

              const ids = Array.from(files).sort((a, b) => Number(a) - Number(b));
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify(ids));
            } catch (err: any) {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: err.message }));
            }
            return;
          }

          // Endpoint 2: Get light curve data for a TIC ID
          const match = req.url.match(/^\/data\/lightcurves\/(\d+)\.json/);
          if (match) {
            const ticId = match[1];
            const cleanPath = path.resolve(__dirname, '../data/clean/lightcurves', `TIC_${ticId}.csv`);
            const rawPath = path.resolve(__dirname, '../data/raw/lightcurves', `TIC_${ticId}.csv`);
            const jsonPath = path.resolve(__dirname, '../data/lightcurves', `${ticId}.json`);

            let filePath = '';
            if (fs.existsSync(cleanPath)) {
              filePath = cleanPath;
            } else if (fs.existsSync(rawPath)) {
              filePath = rawPath;
            }

            if (!filePath) {
              if (fs.existsSync(jsonPath)) {
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(fs.readFileSync(jsonPath));
                return;
              }
              res.writeHead(404, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: `TIC ID ${ticId} not found` }));
              return;
            }

            try {
              const fileContent = fs.readFileSync(filePath, 'utf-8');
              const lines = fileContent.split('\n');
              if (lines.length === 0) {
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify([]));
                return;
              }

              const headers = lines[0].split(',').map(h => h.trim());
              const timeIdx = headers.indexOf('time');
              const fluxIdx = headers.indexOf('flux');
              const fluxErrIdx = headers.indexOf('flux_err');

              if (timeIdx === -1 || fluxIdx === -1) {
                throw new Error("Invalid CSV headers. Missing 'time' or 'flux'.");
              }

              const data: { time: number; flux: number; flux_err?: number }[] = [];
              for (let i = 1; i < lines.length; i++) {
                const line = lines[i].trim();
                if (!line) continue;
                const parts = line.split(',');
                if (parts.length > Math.max(timeIdx, fluxIdx)) {
                  const t = parseFloat(parts[timeIdx]);
                  const f = parseFloat(parts[fluxIdx]);
                  const e = fluxErrIdx !== -1 ? parseFloat(parts[fluxErrIdx]) : undefined;
                  if (!isNaN(t) && !isNaN(f)) {
                    data.push({
                      time: t,
                      flux: f,
                      ...(e !== undefined && !isNaN(e) ? { flux_err: e } : {})
                    });
                  }
                }
              }

              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify(data));
            } catch (err: any) {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: err.message }));
            }
            return;
          }

          next();
        });
      }
    }
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
