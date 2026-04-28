"""
Flask Application
Main backend API for Startup Health Analysis Dashboard
Phase 1: Website Intelligence
Phase 2: Hiring Intelligence
Phase 3: Social & Engagement Intelligence
Phase 4: Hybrid Dynamic Scoring Engine
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import sys
import threading
import webbrowser
from datetime import datetime

# Add backend modules to path
sys.path.insert(0, os.path.dirname(__file__))

from modules.discovery     import WebsiteDiscovery
from modules.scraper       import WebsiteScraper
from modules.mining        import WebsiteDataMiner
from modules.scoring       import DynamicScoringEngine
from modules.database      import DatabaseManager
from modules.hiring_scraper import HiringScraper
from modules.hiring_mining  import HiringDataMiner
from modules.social_scraper import SocialScraper
from modules.social_mining  import SocialDataMiner
from modules.hybrid_scoring import HybridScoringEngine


app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/static')
CORS(app)

# Initialise modules
discovery      = WebsiteDiscovery()
scraper        = WebsiteScraper()
miner          = WebsiteDataMiner()
scorer         = DynamicScoringEngine()
db             = DatabaseManager()
hiring_scraper = HiringScraper()
hiring_miner   = HiringDataMiner()
social_scraper = SocialScraper()
social_miner   = SocialDataMiner()
hybrid_scorer  = HybridScoringEngine(db=db)   # Phase 4


@app.route('/')
def index():
    """Render main dashboard"""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_startup():
    """
    Main API endpoint – runs all three intelligence pipelines.

    Expected JSON:
        { "startup_name": "...", "website_url": "..." (optional) }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request data'}), 400

        startup_name = (data.get('startup_name') or '').strip()
        website_url  = (data.get('website_url')  or '').strip()
        use_cached   = bool(data.get('use_cached', True))

        if not startup_name:
            return jsonify({'success': False, 'error': 'Startup name is required'}), 400

        # Stable mode: return the latest cached full snapshot for repeat runs.
        if use_cached:
            cached_result = db.get_cached_analysis(startup_name)
            if cached_result:
                return jsonify(cached_result), 200

        result = {
            'startup_name':       startup_name,
            'timestamp':          datetime.utcnow().isoformat(),
            'discovery':          None,
            'validation':         None,
            'scraped_data':       None,
            'features':           None,
            'normalized_features': None,
            'scoring':            None,
            'success':            False
        }

        # ── Step 1: Discover website ──────────────────────────────────────
        if not website_url:
            discovery_result = discovery.discover_website(startup_name)
            result['discovery'] = discovery_result

            if not discovery_result['success']:
                result['error'] = 'Could not discover website automatically'
                db.save_analysis({
                    'startup_name': startup_name,
                    'status':       'failed',
                    'error_message': result['error']
                })
                return jsonify(result), 200

            website_url = discovery_result['website']
        else:
            result['discovery'] = {
                'success': True,
                'website': website_url,
                'method':  'user_provided',
                'message': 'Website URL provided by user'
            }

        # ── Step 2: Validate website ──────────────────────────────────────
        validation_result = discovery.validate_website(website_url)
        result['validation'] = validation_result

        if not validation_result['reachable']:
            result['error'] = f"Website not reachable: {validation_result['message']}"
            db.save_analysis({
                'startup_name':  startup_name,
                'website_url':   website_url,
                'status':        'failed',
                'error_message': result['error']
            })
            return jsonify(result), 200

        # ── Step 3: Scrape website ────────────────────────────────────────
        scraped_data = scraper.scrape_website(website_url)
        result['scraped_data'] = scraped_data

        if not scraped_data.get('success'):
            result['error'] = f"Scraping failed: {scraped_data.get('error')}"
            db.save_analysis({
                'startup_name':  startup_name,
                'website_url':   website_url,
                'status':        'failed',
                'error_message': result['error']
            })
            return jsonify(result), 200

        # ── Step 4: Mine website features ────────────────────────────────
        mined_data = miner.mine_features(scraped_data)
        if not mined_data.get('success'):
            result['error'] = f"Feature mining failed: {mined_data.get('error')}"
            return jsonify(result), 200

        result['features'] = mined_data['features']

        # ── Step 5: Normalize website features ───────────────────────────
        normalized_features = miner.normalize_features(mined_data['features'])
        result['normalized_features'] = normalized_features

        # ── Step 6: Calculate website health score (dynamic thresholds) ───
        recent_analyses = db.get_recent_analyses(limit=200)
        historical_scores = [
            row.get('health_score')
            for row in recent_analyses
            if row.get('health_score') is not None
        ]
        scoring_result = scorer.calculate_health_score(
            normalized_features,
            historical_scores=historical_scores
        )
        result['scoring'] = scoring_result

        # ── Step 7: Hiring intelligence ───────────────────────────────────
        hiring_data   = hiring_scraper.scrape_hiring_data(website_url)
        result['hiring_data'] = hiring_data

        hiring_score    = None
        hiring_features = None
        hiring_normalized = None

        if hiring_data.get('success'):
            hiring_mined    = hiring_miner.mine_hiring_features(hiring_data)
            hiring_features = hiring_mined.get('features', {})
            hiring_normalized = hiring_miner.normalize_hiring_features(hiring_features)
            hiring_score_result = hiring_miner.calculate_hiring_health_score(hiring_normalized)
            hiring_score = hiring_score_result.get('hiring_health_score', hiring_score_result.get('health_score'))
            hiring_score_result['health_score'] = hiring_score

            result['hiring_features']  = hiring_features
            result['hiring_normalized'] = hiring_normalized
            result['hiring_scoring']   = hiring_score_result

            db.save_hiring_data({
                'startup_name':      startup_name,
                'website_url':       website_url,
                'open_positions':    hiring_features.get('open_positions', 0),
                'hiring_pages_found': int(hiring_data.get('hiring_pages_found', 0)),
                'job_listings':      hiring_data.get('job_listings', []),
                'hiring_features':   hiring_features
            })

        # ── Step 8: Social intelligence ───────────────────────────────────
        social_raw = social_scraper.scrape_social_data(website_url)
        result['social_data'] = social_raw

        social_score    = None
        social_features = None
        social_normalized = None  # Phase 4: pre-initialise so Step 10 always has a safe ref

        if social_raw.get('success'):
            social_mined_result = social_miner.mine_social_features(social_raw)

            if social_mined_result.get('success'):
                social_features  = social_mined_result['features']
                social_normalized = social_miner.normalize_social_features(social_features)
                social_score_result = social_miner.calculate_social_health_score(
                    social_normalized,
                    raw_features=social_features
                )
                social_score = social_score_result.get('health_score')

                result['social_features']   = social_features
                result['social_normalized'] = social_normalized
                result['social_scoring']    = social_score_result
                result['social_data']['validated_links'] = social_raw.get('validated_links', {})

                db.save_social_data({
                    'startup_name':    startup_name,
                    'website_url':     website_url,
                    'validated_links': social_raw.get('validated_links', {}),
                    'social_features': social_features,
                    'social_scoring':  social_score_result
                })

        # ── Step 9: Combined health score (website + hiring + social) ─────
        combined_score = scorer.calculate_combined_health_score(
            website_score=scoring_result['health_score'],
            hiring_score=hiring_score,
            social_score=social_score
        )
        result['combined_scoring'] = combined_score

        overall_risk = scorer.get_risk_level(
            combined_score['overall_score'],
            historical_scores=historical_scores
        )
        result['overall_risk_level'] = overall_risk
        result['success']     = True
        result['website_url'] = website_url

        # ── Step 10: Hybrid Dynamic Scoring (Phase 4) ──────────────────────────
        try:
            hybrid_result = hybrid_scorer.score(
                website_norm   = normalized_features,
                hiring_norm    = hiring_normalized or {},
                social_norm    = social_normalized or {},
                startup_name   = startup_name,
                combined_score = combined_score['overall_score'],
            )
            # Add startup / URL context for DB save
            hybrid_result['startup_name']  = startup_name
            hybrid_result['website_url']   = website_url
            hybrid_result['combined_score'] = combined_score['overall_score']

            result['hybrid_scoring'] = hybrid_result

            # Persist hybrid score
            db.save_hybrid_score(hybrid_result)

        except Exception as hybrid_err:
            import traceback, logging
            logging.error("Hybrid scoring error: %s", traceback.format_exc())
            hybrid_result = None
            result['hybrid_scoring'] = {
                'error': str(hybrid_err),
                'hybrid_score': combined_score['overall_score'],
                'cluster_label': 'Unknown',
                'failure_probability': 50.0,
                'scoring_method': 'fallback',
                'signal_breakdown': [],
                'feature_weights': {},
                'feature_vector': {},
                'pca_explained': [],
                'risk_label': overall_risk.replace('_', ' ').title() if overall_risk else 'Unknown',
                'risk_explanation': 'Hybrid scoring unavailable — check server logs.',
                'is_primary_score': False,
            }

        # ── Primary score fields (fully automatic hybrid score) ──────────────
        hs = result['hybrid_scoring']
        primary_score   = hs.get('hybrid_score',          combined_score['overall_score'])
        primary_risk    = hs.get('risk_label',             overall_risk)
        primary_fail    = hs.get('failure_probability',    None)
        primary_method  = hs.get('scoring_method',         'combined')

        result['primary_score']               = round(float(primary_score), 2)
        result['primary_risk_level']          = primary_risk
        result['primary_failure_probability'] = primary_fail
        result['primary_scoring_method']      = primary_method
        result['cached'] = False

        # ── Step 11: Persist to database (hybrid score as canonical) ──────────
        db.save_analysis({
            'startup_name': startup_name,
            'website_url':  website_url,
            'health_score': primary_score,          # ← hybrid score now canonical
            'risk_level':   primary_risk,
            'features':     mined_data['features'],
            'scraped_data': scraped_data,
            'status':       'success'
        })

        # Store full response snapshot for stable repeatability.
        db.save_cached_analysis(startup_name, website_url, result)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Internal server error: {str(e)}'}), 500


# ── History / Query Routes ────────────────────────────────────────────────────

@app.route('/api/history/<startup_name>', methods=['GET'])
def get_history(startup_name):
    """Get analysis history for a startup"""
    try:
        limit = request.args.get('limit', 10, type=int)
        return jsonify({
            'success':      True,
            'startup_name': startup_name,
            'history':      db.get_startup_history(startup_name, limit)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recent', methods=['GET'])
def get_recent():
    """Get recent analyses"""
    try:
        limit = request.args.get('limit', 20, type=int)
        return jsonify({'success': True, 'analyses': db.get_recent_analyses(limit)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get database statistics"""
    try:
        return jsonify({'success': True, 'statistics': db.get_statistics()}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search', methods=['GET'])
def search_startups():
    """Search for startups"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({'success': False, 'error': 'Query parameter required'}), 400
        return jsonify({'success': True, 'query': query, 'results': db.search_startups(query)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/hiring/history/<startup_name>', methods=['GET'])
def get_hiring_history(startup_name):
    """Get hiring intelligence history"""
    try:
        limit = request.args.get('limit', 10, type=int)
        return jsonify({
            'success':        True,
            'startup_name':   startup_name,
            'hiring_history': db.get_hiring_history(startup_name, limit)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/hiring/trends/<startup_name>', methods=['GET'])
def get_hiring_trends(startup_name):
    """Get hiring trend data for visualization"""
    try:
        days = request.args.get('days', 30, type=int)
        return jsonify({
            'success':      True,
            'startup_name': startup_name,
            'trend_data':   db.get_hiring_trend_data(startup_name, days)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/social/history/<startup_name>', methods=['GET'])
def get_social_history(startup_name):
    """Get social intelligence history for a startup (Phase 3)"""
    try:
        limit = request.args.get('limit', 10, type=int)
        return jsonify({
            'success':        True,
            'startup_name':   startup_name,
            'social_history': db.get_social_history(startup_name, limit)
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/social/trends/<startup_name>', methods=['GET'])
def get_social_trends(startup_name):
    """Get social score trend data for visualization (Phase 3)"""
    try:
        days = request.args.get('days', 30, type=int)
        raw  = db.get_social_trend_data(startup_name, days)
        trend_data = [{'timestamp': row[0], 'social_score': row[1]} for row in raw]
        return jsonify({
            'success':      True,
            'startup_name': startup_name,
            'trend_data':   trend_data
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Phase 4: Hybrid Scoring Routes ─────────────────────────────────────────

@app.route('/api/hybrid/history/<startup_name>', methods=['GET'])
def get_hybrid_history(startup_name):
    """Get hybrid scoring history for trend chart (Phase 4)"""
    try:
        limit = request.args.get('limit', 20, type=int)
        history = db.get_hybrid_history(startup_name, limit)
        return jsonify({
            'success':        True,
            'startup_name':   startup_name,
            'hybrid_history': history
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/model/status', methods=['GET'])
def get_model_status():
    """Return Phase 4 model metadata (Phase 4)"""
    try:
        return jsonify({
            'success': True,
            'model_status': hybrid_scorer.get_model_status()
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batch', methods=['POST'])
def batch_analyze():
    """
    Batch analysis endpoint – lightweight version that returns just the
    primary health score + risk for a list of startup names.

    Expected JSON:
        { "startups": ["Stripe", "Notion", "Airbnb"] }
    """
    try:
        data = request.get_json()
        if not data or not isinstance(data.get('startups'), list):
            return jsonify({'success': False, 'error': 'Expected {"startups": [...]}'}), 400

        names = [n.strip() for n in data['startups'] if isinstance(n, str) and n.strip()]
        if not names:
            return jsonify({'success': False, 'error': 'Startup list is empty'}), 400
        if len(names) > 10:
            return jsonify({'success': False, 'error': 'Maximum 10 startups per batch'}), 400

        results = []
        for name in names:
            # Try to find existing history first
            history = db.get_startup_history(name, limit=1)
            if history:
                row = history[0]
                results.append({
                    'startup_name': name,
                    'health_score': row.get('health_score'),
                    'risk_level':   row.get('risk_level'),
                    'website_url':  row.get('website_url'),
                    'timestamp':    row.get('timestamp'),
                    'source':       'cached'
                })
            else:
                results.append({
                    'startup_name': name,
                    'health_score': None,
                    'risk_level':   'Not Analyzed',
                    'website_url':  None,
                    'timestamp':    None,
                    'source':       'not_found'
                })

        return jsonify({'success': True, 'results': results, 'count': len(results)}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Batch error: {str(e)}'}), 500


def _open_browser():
    """Open the dashboard in the default browser after a short delay."""
    import time
    time.sleep(1.8)
    webbrowser.open('http://localhost:5000')


if __name__ == '__main__':
    print("=" * 60)
    print("  Startup Intelligence Dashboard")
    print("  Website + Hiring + Social + Hybrid AI")
    print("=" * 60)
    print("Starting Flask server...")
    print("Dashboard URL: http://localhost:5000")
    print("Press Ctrl+C to stop the server.")
    print("=" * 60)

    # Auto-open browser in background thread
    threading.Thread(target=_open_browser, daemon=True).start()

    app.run(debug=False, host='0.0.0.0', port=5000)
