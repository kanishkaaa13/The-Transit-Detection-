from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import csv
from pathlib import Path

app = Flask(__name__)
CORS(app)  # Enable CORS for Vercel frontend

# Base directory for data files
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'


@app.route('/api/tic-ids')
def get_tic_ids():
    """Get list of available TIC IDs from data directory"""
    files = set()
    
    clean_dir = DATA_DIR / 'clean' / 'lightcurves'
    raw_dir = DATA_DIR / 'raw' / 'lightcurves'
    
    for directory in [clean_dir, raw_dir]:
        if directory.exists():
            for f in directory.iterdir():
                if f.name.startswith('TIC_') and f.name.endswith('.csv'):
                    tic_id = f.name.replace('TIC_', '').replace('.csv', '')
                    files.add(tic_id)
    
    ids = sorted(files, key=lambda x: int(x) if x.isdigit() else 0)
    return jsonify(ids)


@app.route('/api/sky-map-stars')
def get_sky_map_stars():
    """Get stars for the Sky Map with coordinates and classifications"""
    available_ids = set()
    
    clean_dir = DATA_DIR / 'clean' / 'lightcurves'
    raw_dir = DATA_DIR / 'raw' / 'lightcurves'
    prime_targets_path = DATA_DIR / 'clean' / 'prime_targets.csv'
    
    for directory in [clean_dir, raw_dir]:
        if directory.exists():
            for f in directory.iterdir():
                if f.name.startswith('TIC_') and f.name.endswith('.csv'):
                    tic_id = f.name.replace('TIC_', '').replace('.csv', '')
                    available_ids.add(tic_id)
    
    # Load coordinates from prime_targets.csv
    id_to_coords = {}
    if prime_targets_path.exists():
        with open(prime_targets_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                id_str = row.get('ID', '').strip()
                ra_val = row.get('ra', '')
                dec_val = row.get('dec', '')
                rad_val = row.get('rad', '1.0')
                
                if id_str and ra_val and dec_val:
                    try:
                        id_to_coords[id_str] = {
                            'ra': float(ra_val),
                            'dec': float(dec_val),
                            'rad': float(rad_val) if rad_val else 1.0
                        }
                    except ValueError:
                        pass
    
    # Create response list with mock classifications
    stars = []
    for star_id in available_ids:
        coords = id_to_coords.get(star_id, {
            'ra': 0 + hash(star_id) % 360,
            'dec': -90 + (hash(star_id) % 10),
            'rad': 1.0
        })
        
        # Mock classification logic (same as Vite config)
        digit_sum = sum(int(c) for c in star_id if c.isdigit())
        classifications = ['Exoplanet', 'Binary Star', 'Stellar Blend', 'Starspot']
        classification = classifications[digit_sum % len(classifications)]
        confidence = 0.65 + (digit_sum % 31) / 100
        
        # Specific overrides
        overrides = {
            '451598465': ('Exoplanet', 0.945),
            '2054445521': ('Binary Star', 0.982),
            '257325189': ('Stellar Blend', 0.714),
            '317154919': ('Starspot', 0.841),
            '257738202': ('Exoplanet', 0.885)
        }
        
        if star_id in overrides:
            classification, confidence = overrides[star_id]
        
        stars.append({
            'id': star_id,
            'ra': coords['ra'],
            'dec': coords['dec'],
            'classification': classification,
            'confidence': confidence,
            'rad': coords.get('rad', 1.0)
        })
    
    return jsonify(stars)


@app.route('/data/lightcurves/<tic_id>.json')
def get_light_curve(tic_id):
    """Get light curve data for a TIC ID"""
    clean_path = DATA_DIR / 'clean' / 'lightcurves' / f'TIC_{tic_id}.csv'
    raw_path = DATA_DIR / 'raw' / 'lightcurves' / f'TIC_{tic_id}.csv'
    json_path = DATA_DIR / 'lightcurves' / f'{tic_id}.json'
    
    file_path = None
    if clean_path.exists():
        file_path = clean_path
    elif raw_path.exists():
        file_path = raw_path
    elif json_path.exists():
        return send_from_directory(json_path.parent, json_path.name, mimetype='application/json')
    else:
        return jsonify({'error': f'TIC ID {tic_id} not found'}), 404
    
    try:
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            data = []
            for row in reader:
                try:
                    time_val = float(row.get('time', 0))
                    flux_val = float(row.get('flux', row.get('flux_norm', 0)))
                    flux_err = row.get('flux_err', row.get('flux_err_norm'))
                    
                    point = {'time': time_val, 'flux': flux_val}
                    if flux_err:
                        try:
                            point['flux_err'] = float(flux_err)
                        except ValueError:
                            pass
                    data.append(point)
                except (ValueError, KeyError):
                    continue
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/model-performance')
def get_model_performance():
    """Serve Stage 4 classifier evaluation metrics."""
    perf_path = BASE_DIR / 'stage4_classifier' / 'model_performance.json'
    if not perf_path.exists():
        return jsonify({'error': 'model_performance.json not found — run stage4_evaluate.py first'}), 404
    import json as _json
    with open(perf_path, 'r') as f:
        return jsonify(_json.load(f))


@app.route('/api/sky-chart')
def get_sky_chart():
    """Proxy endpoint for AstronomyAPI - Mock implementation for prototype."""
    ra = request.args.get('ra', '0.0')
    dec = request.args.get('dec', '-87.0')
    zoom = request.args.get('zoom', '2')
    return jsonify({
        'imageUrl': f'/api/sky-chart-image?ra={ra}&dec={dec}&zoom={zoom}'
    })


@app.route('/api/sky-chart-image')
def get_sky_chart_image():
    """Dynamically generates a styled cosmic starfield mapping coordinates and zoom."""
    import io
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from flask import send_file

    try:
        ra = float(request.args.get('ra', '0.0'))
        dec = float(request.args.get('dec', '-87.0'))
        zoom = int(request.args.get('zoom', '2'))
    except ValueError:
        ra, dec, zoom = 0.0, -87.0, 2

    # Map zoom to FOV
    fov_map = {1: 40.0, 2: 20.0, 3: 10.0, 4: 5.0, 5: 2.5, 6: 1.25}
    fov = fov_map.get(zoom, 10.0)

    # Deterministic random seed based on region coordinates for panning consistency
    seed = int((abs(ra) * 1000 + abs(dec) * 100 + zoom) % (2**31 - 1))
    np.random.seed(seed)

    num_stars = 150
    star_ra = np.random.uniform(ra - fov/2, ra + fov/2, num_stars)
    star_dec = np.random.uniform(dec - fov/2, dec + fov/2, num_stars)
    star_size = np.random.exponential(scale=1.5, size=num_stars) + 0.2
    star_alpha = np.random.uniform(0.2, 0.8, num_stars)

    # Plot Setup (matching dashboard styling colors)
    fig, ax = plt.subplots(figsize=(6, 6), facecolor='#020617')
    ax.set_facecolor('#020617')

    # Draw faint grid lines to look scientific
    ax.grid(True, color='#1e293b', alpha=0.3, linestyle='--')

    # 1. Background stars
    ax.scatter(star_ra, star_dec, s=star_size, color='#94a3b8', alpha=star_alpha, edgecolors='none')

    # 2. Add some colorful bright targets (blue/cyan giants, yellow/amber main sequence, red dwarfs)
    num_targets = 15
    tgt_ra = np.random.uniform(ra - fov/2, ra + fov/2, num_targets)
    tgt_dec = np.random.uniform(dec - fov/2, dec + fov/2, num_targets)
    tgt_size = np.random.uniform(15, 60, tgt_size=num_targets) if hasattr(np, 'random') else np.random.uniform(15, 60, num_targets)
    colors = np.random.choice(['#38bdf8', '#34d399', '#fbbf24', '#f87171'], size=num_targets)
    ax.scatter(tgt_ra, tgt_dec, s=tgt_size, color=colors, alpha=0.6, edgecolors='none')

    # Match sky chart conventions: RA goes right-to-left
    ax.set_xlim(ra + fov/2, ra - fov/2)
    ax.set_ylim(dec - fov/2, dec + fov/2)

    # Clean borders
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)

    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

    # Output to in-memory bytes
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor(), edgecolor='none', pad_inches=0)
    buf.seek(0)
    plt.close(fig)

    return send_file(buf, mimetype='image/png')


@app.route('/api/sky-snapshot', methods=['POST'])
def sky_snapshot():
    """Legacy endpoint for sky snapshot"""
    return jsonify({'imageUrl': '/api/sky-chart-image?ra=0.0&dec=-87.0&zoom=3'})


@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'TESS Transit Detection API',
        'endpoints': [
            '/api/tic-ids',
            '/api/sky-map-stars',
            '/data/lightcurves/<tic_id>.json',
            '/api/sky-chart',
            '/api/sky-snapshot'
        ]
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
