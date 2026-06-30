/**
 * build-lightcurve-json.mjs
 *
 * Pre-build script: converts TIC_*.csv light curve files into compact JSON
 * and copies them into  dashboard/public/data/lightcurves/<ticId>.json
 * Also generates:
 *   public/data/tic-ids.json        — replaces /api/tic-ids
 *   public/data/sky-map-stars.json  — replaces /api/sky-map-stars
 * so that Vercel (static hosting) can serve them without any server middleware.
 *
 * Run:  node scripts/build-lightcurve-json.mjs
 * Or via npm scripts:  npm run build  (wired as "prebuild")
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Paths relative to the dashboard/ folder
const DASHBOARD_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT      = path.resolve(DASHBOARD_ROOT, '..');

const CLEAN_DIR  = path.join(REPO_ROOT, 'data', 'clean', 'lightcurves');
const RAW_DIR    = path.join(REPO_ROOT, 'data', 'raw',   'lightcurves');
const OUTPUT_DIR = path.join(DASHBOARD_ROOT, 'public', 'data', 'lightcurves');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Parse a CSV buffer into [{time, flux, flux_err?}, …], filtering NaN rows. */
function parseCsv(content) {
  const lines = content.split('\n');
  if (lines.length === 0) return [];

  const headers = lines[0].split(',').map(h => h.trim());

  const timeIdx    = headers.indexOf('time');
  let   fluxIdx    = headers.indexOf('flux');
  if (fluxIdx    === -1) fluxIdx    = headers.indexOf('flux_norm');
  let   fluxErrIdx = headers.indexOf('flux_err');
  if (fluxErrIdx === -1) fluxErrIdx = headers.indexOf('flux_err_norm');

  if (timeIdx === -1 || fluxIdx === -1) {
    throw new Error(`Invalid headers: ${lines[0]}`);
  }

  const data = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const parts = line.split(',');
    if (parts.length <= Math.max(timeIdx, fluxIdx)) continue;

    const t = parseFloat(parts[timeIdx]);
    const f = parseFloat(parts[fluxIdx]);
    if (!Number.isFinite(t) || !Number.isFinite(f)) continue;

    const point = { time: t, flux: f };
    if (fluxErrIdx !== -1) {
      const e = parseFloat(parts[fluxErrIdx]);
      if (Number.isFinite(e)) point.flux_err = e;
    }
    data.push(point);
  }
  return data;
}

/** Collect all unique TIC IDs from a directory of TIC_*.csv files. */
function collectIds(dir) {
  if (!fs.existsSync(dir)) return new Set();
  return new Set(
    fs.readdirSync(dir)
      .filter(f => f.startsWith('TIC_') && f.endsWith('.csv'))
      .map(f => f.replace('TIC_', '').replace('.csv', ''))
  );
}

/** Build sky-map-stars data from prime_targets.csv + classification overrides. */
function buildSkyMapStars(allIds) {
  const primeTargetsPath = path.join(REPO_ROOT, 'data', 'clean', 'prime_targets.csv');
  const idToCoords = new Map();

  if (fs.existsSync(primeTargetsPath)) {
    const lines = fs.readFileSync(primeTargetsPath, 'utf-8').split('\n');
    if (lines.length > 0) {
      const headers = lines[0].split(',').map(h => h.trim());
      const idIdx  = headers.indexOf('ID');
      const raIdx  = headers.indexOf('ra');
      const decIdx = headers.indexOf('dec');

      if (idIdx !== -1 && raIdx !== -1 && decIdx !== -1) {
        for (let i = 1; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line) continue;
          const parts = line.split(',');
          if (parts.length > Math.max(idIdx, raIdx, decIdx)) {
            const idStr  = parts[idIdx].trim();
            const raVal  = parseFloat(parts[raIdx]);
            const decVal = parseFloat(parts[decIdx]);
            if (idStr && !isNaN(raVal) && !isNaN(decVal)) {
              idToCoords.set(idStr, { ra: raVal, dec: decVal });
            }
          }
        }
      }
    }
  }

  // Classification overrides — mirrors vite.config.ts and server.py
  const overrides = {
    '451598465':  ['Exoplanet',      0.945],
    '2054445521': ['Binary Star',    0.982],
    '257325189':  ['Stellar Blend',  0.714],
    '317154919':  ['Starspot',       0.841],
    '257738202':  ['Exoplanet',      0.885],
  };
  const classifications = ['Exoplanet', 'Binary Star', 'Stellar Blend', 'Starspot'];

  return [...allIds].map(id => {
    const coords = idToCoords.get(id) || {
      ra:  (id.split('').reduce((s, c) => s + (parseInt(c, 10) || 0), 0) * 137.5) % 360,
      dec: -90 + (id.split('').reduce((s, c) => s + (parseInt(c, 10) || 0), 0) % 10),
    };

    const digitSum = id.split('').reduce((s, c) => s + (parseInt(c, 10) || 0), 0);
    let classification = classifications[digitSum % classifications.length];
    let confidence     = 0.65 + (digitSum % 31) / 100;

    if (overrides[id]) {
      [classification, confidence] = overrides[id];
    }

    return { id, ra: coords.ra, dec: coords.dec, classification, confidence };
  });
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const cleanIds = collectIds(CLEAN_DIR);
const rawIds   = collectIds(RAW_DIR);
const allIds   = new Set([...cleanIds, ...rawIds]);

console.log(`\n🚀  build-lightcurve-json — found ${allIds.size} TIC IDs\n`);

// Ensure output directories exist
fs.mkdirSync(OUTPUT_DIR, { recursive: true });
fs.mkdirSync(path.join(DASHBOARD_ROOT, 'public', 'data'), { recursive: true });

// ── 1. tic-ids.json ─────────────────────────────────────────────────────────
const sortedIds = [...allIds].sort((a, b) => Number(a) - Number(b));
fs.writeFileSync(
  path.join(DASHBOARD_ROOT, 'public', 'data', 'tic-ids.json'),
  JSON.stringify(sortedIds)
);
console.log(`  ✓  tic-ids.json — ${sortedIds.length} IDs`);

// ── 2. sky-map-stars.json ────────────────────────────────────────────────────
const stars = buildSkyMapStars(allIds);
fs.writeFileSync(
  path.join(DASHBOARD_ROOT, 'public', 'data', 'sky-map-stars.json'),
  JSON.stringify(stars)
);
console.log(`  ✓  sky-map-stars.json — ${stars.length} stars\n`);

// ── 3. Individual lightcurve JSON files ─────────────────────────────────────
let ok = 0, skipped = 0, failed = 0;

for (const ticId of sortedIds) {
  const outPath = path.join(OUTPUT_DIR, `${ticId}.json`);

  // Choose source file (clean preferred over raw)
  const cleanPath = path.join(CLEAN_DIR, `TIC_${ticId}.csv`);
  const rawPath   = path.join(RAW_DIR,   `TIC_${ticId}.csv`);
  const srcPath   = fs.existsSync(cleanPath) ? cleanPath : rawPath;

  try {
    const content = fs.readFileSync(srcPath, 'utf-8');
    const data    = parseCsv(content);

    if (data.length === 0) {
      console.warn(`  ⚠  TIC ${ticId}: parsed 0 valid rows — skipping`);
      skipped++;
      continue;
    }

    // Sort by time (matches dev-server behaviour)
    data.sort((a, b) => a.time - b.time);

    fs.writeFileSync(outPath, JSON.stringify(data));
    console.log(`  ✓  TIC ${ticId}: ${data.length} points → ${path.relative(DASHBOARD_ROOT, outPath)}`);
    ok++;
  } catch (err) {
    console.error(`  ✗  TIC ${ticId}: ${err.message}`);
    failed++;
  }
}

console.log(`\n✅  Done — ${ok} converted, ${skipped} skipped, ${failed} failed\n`);
if (failed > 0) process.exit(1);
