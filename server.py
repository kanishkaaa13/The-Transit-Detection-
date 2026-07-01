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
    """Proxy endpoint for AstronomyAPI (if you want to add this later)"""
    return jsonify({'error': 'not_implemented'}), 501


@app.route('/api/sky-snapshot', methods=['POST'])
def sky_snapshot():
    """Legacy endpoint for sky snapshot"""
    return jsonify({'error': 'not_implemented'}), 501


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
