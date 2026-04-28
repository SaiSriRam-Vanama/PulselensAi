"""
Database Module
Manages SQLite database for storing analysis history
"""

import sqlite3
import json
from datetime import datetime
import os


class DatabaseManager:
    """Manages database operations for startup analysis history"""
    
    def __init__(self, db_path='database/startup_analysis.db'):
        self.db_path = db_path
        self._initialize_database()
    
    def _initialize_database(self):
        """Create database tables if they don't exist"""
        # Ensure database directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create analysis history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                startup_name TEXT NOT NULL,
                website_url TEXT,
                health_score REAL,
                risk_level TEXT,
                features_json TEXT,
                scraped_data_json TEXT,
                analysis_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                error_message TEXT
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_startup_name 
            ON analysis_history(startup_name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON analysis_history(analysis_timestamp DESC)
        ''')
        
        # Create hiring history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hiring_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                startup_name TEXT NOT NULL,
                website_url TEXT,
                open_positions INTEGER,
                hiring_pages_found INTEGER,
                job_listings_json TEXT,
                hiring_features_json TEXT,
                scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                analysis_id INTEGER,
                FOREIGN KEY (analysis_id) REFERENCES analysis_history(id)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_hiring_startup 
            ON hiring_history(startup_name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_hiring_timestamp 
            ON hiring_history(scraped_at DESC)
        ''')
        
        # ── Phase 3: Social Intelligence History ──────────────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS social_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                startup_name TEXT NOT NULL,
                website_url TEXT,
                platforms_json TEXT,
                social_features_json TEXT,
                social_score REAL,
                risk_level TEXT,
                scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                analysis_id INTEGER,
                FOREIGN KEY (analysis_id) REFERENCES analysis_history(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_social_startup
            ON social_history(startup_name)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_social_timestamp
            ON social_history(scraped_at DESC)
        ''')

        # ── Phase 4: Hybrid Dynamic Scoring ───────────────────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hybrid_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                startup_name TEXT NOT NULL,
                website_url TEXT,
                hybrid_score REAL,
                cluster_id INTEGER,
                cluster_label TEXT,
                failure_probability REAL,
                scoring_method TEXT,
                feature_weights_json TEXT,
                feature_vector_json TEXT,
                pca_explained_json TEXT,
                combined_score REAL,
                analysis_id INTEGER,
                scored_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analysis_history(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_hybrid_startup
            ON hybrid_scores(startup_name)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_hybrid_timestamp
            ON hybrid_scores(scored_at DESC)
        ''')

        # ── Stable analysis cache (full response snapshot) ───────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_result_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                startup_name TEXT NOT NULL,
                startup_key TEXT NOT NULL,
                website_url TEXT,
                response_json TEXT NOT NULL,
                cached_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cache_startup_key
            ON analysis_result_cache(startup_key)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_cache_timestamp
            ON analysis_result_cache(cached_at DESC)
        ''')

        conn.commit()
        conn.close()
    
    def save_analysis(self, analysis_data):
        """
        Save analysis results to database
        
        Args:
            analysis_data (dict): Complete analysis data
            
        Returns:
            int: ID of saved record
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO analysis_history 
            (startup_name, website_url, health_score, risk_level, 
             features_json, scraped_data_json, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analysis_data.get('startup_name'),
            analysis_data.get('website_url'),
            analysis_data.get('health_score'),
            analysis_data.get('risk_level'),
            json.dumps(analysis_data.get('features', {})),
            json.dumps(analysis_data.get('scraped_data', {})),
            analysis_data.get('status', 'success'),
            analysis_data.get('error_message')
        ))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return record_id
    
    def get_startup_history(self, startup_name, limit=10):
        """
        Get analysis history for a specific startup
        
        Args:
            startup_name (str): Startup name
            limit (int): Maximum number of records
            
        Returns:
            list: List of analysis records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM analysis_history 
            WHERE startup_name = ?
            ORDER BY analysis_timestamp DESC
            LIMIT ?
        ''', (startup_name, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to list of dicts
        history = []
        for row in rows:
            record = dict(row)
            record['timestamp'] = record.get('analysis_timestamp')
            # Parse JSON fields
            record['features'] = json.loads(record['features_json']) if record['features_json'] else {}
            record['scraped_data'] = json.loads(record['scraped_data_json']) if record['scraped_data_json'] else {}
            history.append(record)
        
        return history
    
    def get_recent_analyses(self, limit=20):
        """
        Get most recent analyses across all startups
        
        Args:
            limit (int): Maximum number of records
            
        Returns:
            list: List of recent analysis records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, startup_name, website_url, health_score, 
                   risk_level, analysis_timestamp, analysis_timestamp AS timestamp, status
            FROM analysis_history 
            ORDER BY analysis_timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_startup_trend(self, startup_name, days=30):
        """
        Get health score trend for a startup over time
        
        Args:
            startup_name (str): Startup name
            days (int): Number of days to look back
            
        Returns:
            list: List of (timestamp, health_score) tuples
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT analysis_timestamp, health_score 
            FROM analysis_history 
            WHERE startup_name = ?
            AND analysis_timestamp >= datetime('now', '-' || ? || ' days')
            AND status = 'success'
            ORDER BY analysis_timestamp ASC
        ''', (startup_name, days))
        
        rows = cursor.fetchall()
        conn.close()
        
        return rows
    
    def search_startups(self, query):
        """
        Search recent analyses by startup name.
        
        Args:
            query (str): Search query
            
        Returns:
            list: List of matching analysis records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, startup_name, website_url, health_score,
                   risk_level, analysis_timestamp, analysis_timestamp AS timestamp, status
            FROM analysis_history 
            WHERE startup_name LIKE ?
            ORDER BY analysis_timestamp DESC
            LIMIT 50
        ''', (f'%{query}%',))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_statistics(self):
        """
        Get database statistics
        
        Returns:
            dict: Statistics about stored analyses
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total analyses
        cursor.execute('SELECT COUNT(*) FROM analysis_history')
        total = cursor.fetchone()[0]
        
        # Unique startups
        cursor.execute('SELECT COUNT(DISTINCT startup_name) FROM analysis_history')
        unique_startups = cursor.fetchone()[0]
        
        # Average health score
        cursor.execute('''
            SELECT AVG(health_score) 
            FROM analysis_history 
            WHERE status = 'success' AND health_score IS NOT NULL
        ''')
        avg_score = cursor.fetchone()[0] or 0
        
        # Risk distribution
        cursor.execute('''
            SELECT risk_level, COUNT(*) 
            FROM analysis_history 
            WHERE status = 'success'
            GROUP BY risk_level
        ''')
        risk_dist = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            'total_analyses': total,
            'unique_startups': unique_startups,
            'average_health_score': round(avg_score, 2) if avg_score else 0,
            'risk_distribution': risk_dist
        }
    
    def save_hiring_data(self, hiring_data, analysis_id=None):
        """
        Save hiring intelligence data to database
        
        Args:
            hiring_data (dict): Hiring data from scraper and miner
            analysis_id (int): Optional ID of parent analysis record
            
        Returns:
            int: ID of saved hiring record
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO hiring_history 
            (startup_name, website_url, open_positions, hiring_pages_found, 
             job_listings_json, hiring_features_json, analysis_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            hiring_data.get('startup_name'),
            hiring_data.get('website_url'),
            hiring_data.get('open_positions', 0),
            hiring_data.get('hiring_pages_found', 0),
            json.dumps(hiring_data.get('job_listings', [])),
            json.dumps(hiring_data.get('hiring_features', {})),
            analysis_id
        ))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return record_id
    
    def get_hiring_history(self, startup_name, limit=10):
        """
        Get hiring history for a specific startup
        
        Args:
            startup_name (str): Startup name
            limit (int): Maximum number of records
            
        Returns:
            list: List of hiring records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM hiring_history 
            WHERE startup_name = ?
            ORDER BY scraped_at DESC
            LIMIT ?
        ''', (startup_name, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to list of dicts
        history = []
        for row in rows:
            record = dict(row)
            # Parse JSON fields
            record['job_listings'] = json.loads(record['job_listings_json']) if record['job_listings_json'] else []
            record['hiring_features'] = json.loads(record['hiring_features_json']) if record['hiring_features_json'] else {}
            history.append(record)
        
        return history
    
    def get_hiring_trend_data(self, startup_name, days=30):
        """
        Get hiring trend over time for visualization
        
        Args:
            startup_name (str): Startup name
            days (int): Number of days to look back
            
        Returns:
            list: List of (timestamp, open_positions) tuples
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT scraped_at, open_positions 
            FROM hiring_history 
            WHERE startup_name = ?
            AND scraped_at >= datetime('now', '-' || ? || ' days')
            ORDER BY scraped_at ASC
        ''', (startup_name, days))
        
        rows = cursor.fetchall()
        conn.close()
        
        return rows

    # ── Phase 3: Social Intelligence DB Methods ──────────────────────────

    def save_social_data(self, social_data, analysis_id=None):
        """
        Save social intelligence data to social_history table.

        Args:
            social_data  (dict): Social scraping + mining results
            analysis_id  (int):  Optional FK to analysis_history

        Returns:
            int: ID of saved record
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        platforms = social_data.get('validated_links', {})
        features  = social_data.get('social_features', {})
        scoring   = social_data.get('social_scoring', {})

        cursor.execute('''
            INSERT INTO social_history
            (startup_name, website_url, platforms_json, social_features_json,
             social_score, risk_level, analysis_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            social_data.get('startup_name'),
            social_data.get('website_url'),
            json.dumps(platforms),
            json.dumps(features),
            scoring.get('health_score'),
            scoring.get('risk_level'),
            analysis_id
        ))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id

    def get_social_history(self, startup_name, limit=10):
        """
        Get social history for a specific startup.

        Returns:
            list: List of social records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM social_history
            WHERE startup_name = ?
            ORDER BY scraped_at DESC
            LIMIT ?
        ''', (startup_name, limit))

        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            record = dict(row)
            record['platforms']       = json.loads(record['platforms_json'])       if record['platforms_json']       else {}
            record['social_features'] = json.loads(record['social_features_json']) if record['social_features_json'] else {}
            history.append(record)

        return history

    def get_social_trend_data(self, startup_name, days=30):
        """
        Get social score over time for visualization.

        Returns:
            list: List of (scraped_at, social_score) tuples
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT scraped_at, social_score
            FROM social_history
            WHERE startup_name = ?
              AND scraped_at >= datetime('now', '-' || ? || ' days')
            ORDER BY scraped_at ASC
        ''', (startup_name, days))

        rows = cursor.fetchall()
        conn.close()
        return rows

    # ── Phase 4: Hybrid Scoring DB Methods ──────────────────────────────────

    def save_hybrid_score(self, data, analysis_id=None):
        """
        Persist one hybrid scoring result to the hybrid_scores table.

        Args:
            data (dict): Output of HybridScoringEngine.score()
            analysis_id (int): Optional FK to analysis_history

        Returns:
            int: ID of saved record
        """
        import json
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO hybrid_scores
            (startup_name, website_url, hybrid_score, cluster_id, cluster_label,
             failure_probability, scoring_method, feature_weights_json,
             feature_vector_json, pca_explained_json, combined_score, analysis_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('startup_name'),
            data.get('website_url'),
            data.get('hybrid_score'),
            data.get('cluster_id'),
            data.get('cluster_label'),
            data.get('failure_probability'),
            data.get('scoring_method'),
            json.dumps(data.get('feature_weights', {})),
            json.dumps(data.get('feature_vector', {})),
            json.dumps(data.get('pca_explained', [])),
            data.get('combined_score'),
            analysis_id,
        ))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id

    def get_hybrid_history(self, startup_name, limit=20):
        """
        Get hybrid scoring history for a startup (for trend chart).

        Returns:
            list of dicts with keys: scored_at, hybrid_score, cluster_label,
                                     failure_probability, combined_score
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT scored_at, hybrid_score, cluster_label,
                   failure_probability, combined_score, scoring_method
            FROM hybrid_scores
            WHERE startup_name = ?
            ORDER BY scored_at ASC
            LIMIT ?
        ''', (startup_name, limit))

        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_all_feature_vectors(self):
        """
        Retrieve latest (feature_vector_json, combined_score) per startup
        for model retraining. Using only the newest vector per startup avoids
        repeated runs of the same company from skewing the model over time.

        Returns:
            list of (feature_vector_json: str, combined_score: float)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT hs.feature_vector_json, hs.combined_score
            FROM hybrid_scores hs
            INNER JOIN (
                SELECT startup_name, MAX(scored_at) AS max_scored_at
                FROM hybrid_scores
                GROUP BY startup_name
            ) latest
            ON hs.startup_name = latest.startup_name
            AND hs.scored_at = latest.max_scored_at
            WHERE feature_vector_json IS NOT NULL
              AND combined_score IS NOT NULL
            ORDER BY scored_at ASC
        ''')

        rows = cursor.fetchall()
        conn.close()
        return rows

    # ── Stable cached full analysis methods ───────────────────────────────

    @staticmethod
    def _startup_key(startup_name):
        return (startup_name or '').strip().lower()

    def get_cached_analysis(self, startup_name):
        """
        Return the latest cached full analysis response for a startup.

        Returns:
            dict | None
        """
        key = self._startup_key(startup_name)
        if not key:
            return None

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT response_json, cached_at
            FROM analysis_result_cache
            WHERE startup_key = ?
            ORDER BY cached_at DESC
            LIMIT 1
        ''', (key,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        try:
            payload = json.loads(row['response_json'])
        except Exception:
            return None

        payload['cached'] = True
        payload['cache_timestamp'] = row['cached_at']
        return payload

    def save_cached_analysis(self, startup_name, website_url, response_payload):
        """
        Persist one full response payload as a cache snapshot.
        """
        key = self._startup_key(startup_name)
        if not key:
            return None

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO analysis_result_cache
            (startup_name, startup_key, website_url, response_json)
            VALUES (?, ?, ?, ?)
        ''', (
            startup_name,
            key,
            website_url,
            json.dumps(response_payload),
        ))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id
