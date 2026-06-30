import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load .env into process.env so the vite plugin middleware can read
  // ASTRONOMY_API_ID and ASTRONOMY_API_SECRET (non-VITE_ prefixed)
  const env = loadEnv(mode, path.resolve(__dirname), '');
  Object.assign(process.env, env);

  return {
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

          // Endpoint 3: Get stars for the Sky Map
          if (req.url === '/api/sky-map-stars') {
            try {
              const cleanDir = path.resolve(__dirname, '../data/clean/lightcurves');
              const rawDir = path.resolve(__dirname, '../data/raw/lightcurves');
              const primeTargetsPath = path.resolve(__dirname, '../data/clean/prime_targets.csv');
              const availableIds = new Set<string>();

              if (fs.existsSync(cleanDir)) {
                fs.readdirSync(cleanDir).forEach(f => {
                  if (f.startsWith('TIC_') && f.endsWith('.csv')) {
                    availableIds.add(f.replace('TIC_', '').replace('.csv', ''));
                  }
                });
              }
              if (fs.existsSync(rawDir)) {
                fs.readdirSync(rawDir).forEach(f => {
                  if (f.startsWith('TIC_') && f.endsWith('.csv')) {
                    availableIds.add(f.replace('TIC_', '').replace('.csv', ''));
                  }
                });
              }

              // Load coordinates from prime_targets.csv
              const idToCoords = new Map<string, { ra: number; dec: number }>();
              if (fs.existsSync(primeTargetsPath)) {
                const csvContent = fs.readFileSync(primeTargetsPath, 'utf-8');
                const lines = csvContent.split('\n');
                if (lines.length > 0) {
                  const headers = lines[0].split(',').map(h => h.trim());
                  const idIdx = headers.indexOf('ID');
                  const raIdx = headers.indexOf('ra');
                  const decIdx = headers.indexOf('dec');
                  
                  if (idIdx !== -1 && raIdx !== -1 && decIdx !== -1) {
                    for (let i = 1; i < lines.length; i++) {
                      const line = lines[i].trim();
                      if (!line) continue;
                      const parts = line.split(',');
                      if (parts.length > Math.max(idIdx, raIdx, decIdx)) {
                        const idStr = parts[idIdx].trim();
                        const raVal = parseFloat(parts[raIdx]);
                        const decVal = parseFloat(parts[decIdx]);
                        if (idStr && !isNaN(raVal) && !isNaN(decVal)) {
                          idToCoords.set(idStr, { ra: raVal, dec: decVal });
                        }
                      }
                    }
                  }
                }
              }

              // Create response list
              const stars = Array.from(availableIds).map(id => {
                const coords = idToCoords.get(id) || {
                  // Fallback to random coordinates in the southern polar region
                  ra: 0 + Math.random() * 360,
                  dec: -90 + Math.random() * 10
                };

                // Seeded mock logic matching detectSignal
                const digitSum = id.split('').reduce((sum, char) => sum + (parseInt(char, 10) || 0), 0);
                const classifications = ['Exoplanet', 'Binary Star', 'Stellar Blend', 'Starspot'];
                let classification = classifications[digitSum % classifications.length];
                let confidence = 0.65 + (digitSum % 31) / 100;

                // Specific overrides matching detectSignal
                if (id === '451598465') {
                  classification = 'Exoplanet';
                  confidence = 0.945;
                } else if (id === '2054445521') {
                  classification = 'Binary Star';
                  confidence = 0.982;
                } else if (id === '257325189') {
                  classification = 'Stellar Blend';
                  confidence = 0.714;
                } else if (id === '317154919') {
                  classification = 'Starspot';
                  confidence = 0.841;
                } else if (id === '257738202') {
                  classification = 'Exoplanet';
                  confidence = 0.885;
                }

                return {
                  id,
                  ra: coords.ra,
                  dec: coords.dec,
                  classification,
                  confidence
                };
              });

              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify(stars));
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

            console.log(`[tess-data-server] Resolving request for TIC ID: ${ticId}`);
            console.log(`[tess-data-server] Checking paths: Clean: ${cleanPath}, Raw: ${rawPath}`);

            let filePath = '';
            if (fs.existsSync(cleanPath)) {
              filePath = cleanPath;
            } else if (fs.existsSync(rawPath)) {
              filePath = rawPath;
            }

            if (!filePath) {
              if (fs.existsSync(jsonPath)) {
                console.log(`[tess-data-server] Found JSON file: ${jsonPath}`);
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(fs.readFileSync(jsonPath));
                return;
              }
              console.warn(`[tess-data-server] No CSV/JSON files found for TIC ID ${ticId}`);
              res.writeHead(404, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: `TIC ID ${ticId} not found` }));
              return;
            }

            console.log(`[tess-data-server] Reading file content from: ${filePath}`);
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
              
              let fluxIdx = headers.indexOf('flux');
              if (fluxIdx === -1) fluxIdx = headers.indexOf('flux_norm');

              let fluxErrIdx = headers.indexOf('flux_err');
              if (fluxErrIdx === -1) fluxErrIdx = headers.indexOf('flux_err_norm');

              if (timeIdx === -1 || fluxIdx === -1) {
                console.error(`[tess-data-server] Invalid CSV headers: ${lines[0]}`);
                throw new Error("Invalid CSV headers. Missing 'time' or 'flux/flux_norm'.");
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
              console.error(`[tess-data-server] Error reading/parsing file: ${err.message}`);
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: err.message }));
            }
            return;
          }

          next();
        });

        // ---------------------------------------------------------------
        // AstronomyAPI Proxy: POST /api/sky-snapshot
        // Keeps Application Secret server-side — never exposed to client
        // ---------------------------------------------------------------
        server.middlewares.use('/api/sky-snapshot', (req, res, next) => {
          if (req.method !== 'POST') return next();

          let body = '';
          req.on('data', (chunk: Buffer) => { body += chunk.toString(); });
          req.on('end', async () => {
            try {
              const { ticId, ra, dec } = JSON.parse(body || '{}');

              const appId = process.env.ASTRONOMY_API_ID;
              const appSecret = process.env.ASTRONOMY_API_SECRET;

              if (!appId || !appSecret) {
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'credentials_not_configured' }));
                return;
              }

              const credentials = Buffer.from(`${appId}:${appSecret}`).toString('base64');
              const today = new Date().toISOString().split('T')[0];

              // Convert decimal RA degrees → hours (AstronomyAPI expects hours)
              const raHours = (typeof ra === 'number' ? ra : 0) / 15;
              const decNum = typeof dec === 'number' ? dec : -87;

              console.log(`[sky-snapshot] TIC ${ticId} — RA ${raHours.toFixed(4)}h  Dec ${decNum.toFixed(4)}°`);

              const upstream = await fetch(
                'https://api.astronomyapi.com/api/v2/studio/star-chart',
                {
                  method: 'POST',
                  headers: {
                    'Authorization': `Basic ${credentials}`,
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({
                    style: 'navy',
                    observer: { latitude: -87, longitude: 0, date: today },
                    view: {
                      type: 'area',
                      parameters: {
                        position: {
                          equatorial: {
                            rightAscension: raHours,
                            declination: decNum,
                          }
                        },
                        zoom: 3,
                      }
                    }
                  }),
                  signal: AbortSignal.timeout(20_000),
                }
              );

              if (!upstream.ok) {
                const errText = await upstream.text().catch(() => '');
                console.warn(`[sky-snapshot] AstronomyAPI ${upstream.status}:`, errText.slice(0, 200));
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: `upstream_${upstream.status}` }));
                return;
              }

              const data: any = await upstream.json();
              const imageUrl = data?.data?.imageUrl;

              if (!imageUrl) {
                console.warn('[sky-snapshot] No imageUrl in response:', JSON.stringify(data).slice(0, 300));
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'no_image_url' }));
                return;
              }

              console.log(`[sky-snapshot] Success for TIC ${ticId} →`, imageUrl.slice(0, 60) + '…');
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ imageUrl }));

            } catch (err: any) {
              console.error('[sky-snapshot] Error:', err.message);
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: err.message }));
            }
          });
        });
      }
    }
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  }
})
