"""
Configuration file for the application
"""

import os


class Config:
    """Application configuration"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = True
    
    # Database settings
    DATABASE_PATH = 'database/startup_analysis.db'
    
    # Scraping settings
    REQUEST_TIMEOUT = 15
    MAX_RETRIES = 3
    
    # Feature weights (base values, adjusted dynamically)
    FEATURE_WEIGHTS = {
        'update_gap_score': 0.25,
        'activity_30d_score': 0.20,
        'activity_90d_score': 0.15,
        'frequency_score': 0.15,
        'consistency_score': 0.15,
        'website_depth_score': 0.10,
    }
    
    # Normalization parameters
    NORMALIZATION_PARAMS = {
        'optimal_update_gap': 7,      # days
        'acceptable_update_gap': 30,  # days
        'target_posts_30d': 4,
        'target_posts_90d': 10,
        'optimal_frequency': 7,       # days between posts
        'acceptable_frequency': 30,
        'target_page_count': 20,
    }
