"""
Data Mining Module
Mines behavioral patterns from scraped website data
Extracts and normalizes features for scoring
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter


class WebsiteDataMiner:
    """Mines and processes website data to extract meaningful features"""
    
    def __init__(self):
        pass
    
    def mine_features(self, scraped_data):
        """
        Mine features from scraped website data
        
        Args:
            scraped_data (dict): Raw scraped data
            
        Returns:
            dict: Mined features with normalized values
        """
        if not scraped_data.get('success'):
            return {
                'success': False,
                'error': scraped_data.get('error', 'Unknown error')
            }
        
        # Extract raw features
        raw_features = {
            'last_modified': scraped_data.get('last_modified'),
            'internal_pages': scraped_data.get('internal_pages', 0),
            'blog_dates': scraped_data.get('blog_dates', []),
        }
        
        # Calculate derived features
        features = {}
        
        # Feature 1: Website Update Gap (days since last modified)
        features['update_gap_days'] = self._calculate_update_gap(
            raw_features['last_modified']
        )
        
        # Feature 2: Content Activity Score (based on blog dates)
        activity_metrics = self._calculate_content_activity(
            raw_features['blog_dates']
        )
        features['recent_posts_30d'] = activity_metrics['recent_posts_30d']
        features['recent_posts_90d'] = activity_metrics['recent_posts_90d']
        features['total_posts_found'] = activity_metrics['total_posts']
        features['avg_posting_frequency_days'] = activity_metrics['avg_frequency']
        
        # Feature 3: Website Size/Depth
        features['internal_pages_count'] = raw_features['internal_pages']
        
        # Feature 4: Activity Consistency Score
        features['consistency_score'] = self._calculate_consistency(
            raw_features['blog_dates']
        )
        
        return {
            'success': True,
            'features': features,
            'raw_data': raw_features
        }
    
    def _calculate_update_gap(self, last_modified):
        """Calculate days since last website modification"""
        if not last_modified:
            return 365  # Assume 1 year if not available (conservative)
        
        try:
            # Parse ISO format date
            last_mod_date = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
            
            # Remove timezone info for comparison
            if last_mod_date.tzinfo:
                last_mod_date = last_mod_date.replace(tzinfo=None)
            
            now = datetime.now()
            gap = (now - last_mod_date).days
            
            return max(0, gap)  # Ensure non-negative
            
        except:
            return 365  # Default to 1 year if parsing fails
    
    def _calculate_content_activity(self, blog_dates):
        """Calculate content activity metrics from blog dates"""
        if not blog_dates or len(blog_dates) == 0:
            return {
                'recent_posts_30d': 0,
                'recent_posts_90d': 0,
                'total_posts': 0,
                'avg_frequency': 365  # No activity assumption
            }
        
        now = datetime.now()
        dates = []
        
        # Parse all dates
        for date_str in blog_dates:
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                dates.append(dt)
            except:
                continue
        
        if len(dates) == 0:
            return {
                'recent_posts_30d': 0,
                'recent_posts_90d': 0,
                'total_posts': 0,
                'avg_frequency': 365
            }
        
        # Sort dates (most recent first)
        dates.sort(reverse=True)
        
        # Count recent posts
        recent_30d = sum(1 for dt in dates if (now - dt).days <= 30)
        recent_90d = sum(1 for dt in dates if (now - dt).days <= 90)
        
        # Calculate average posting frequency
        if len(dates) >= 2:
            # Calculate gaps between consecutive posts
            gaps = []
            for i in range(len(dates) - 1):
                gap = (dates[i] - dates[i + 1]).days
                if gap > 0:  # Valid gap
                    gaps.append(gap)
            
            if gaps:
                avg_frequency = np.mean(gaps)
            else:
                avg_frequency = 365
        else:
            avg_frequency = 365
        
        return {
            'recent_posts_30d': recent_30d,
            'recent_posts_90d': recent_90d,
            'total_posts': len(dates),
            'avg_frequency': avg_frequency
        }
    
    def _calculate_consistency(self, blog_dates):
        """
        Calculate posting consistency score
        Higher score = more consistent posting schedule
        """
        if not blog_dates or len(blog_dates) < 3:
            return 0.0  # Not enough data for consistency
        
        now = datetime.now()
        dates = []
        
        # Parse dates
        for date_str in blog_dates:
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                dates.append(dt)
            except:
                continue
        
        if len(dates) < 3:
            return 0.0
        
        # Sort dates
        dates.sort(reverse=True)
        
        # Calculate gaps between posts
        gaps = []
        for i in range(len(dates) - 1):
            gap = (dates[i] - dates[i + 1]).days
            if gap > 0:
                gaps.append(gap)
        
        if len(gaps) < 2:
            return 0.0
        
        # Consistency = inverse of coefficient of variation
        # Lower variation = higher consistency
        mean_gap = np.mean(gaps)
        std_gap = np.std(gaps)
        
        if mean_gap == 0:
            return 0.0
        
        cv = std_gap / mean_gap  # Coefficient of variation
        
        # Convert to 0-1 score (lower CV = higher score)
        # Use exponential decay: consistency = exp(-cv)
        consistency = np.exp(-cv)
        
        return round(consistency, 4)
    
    def normalize_features(self, features):
        """
        Normalize all features to 0-1 scale
        
        Args:
            features (dict): Raw feature values
            
        Returns:
            dict: Normalized features
        """
        normalized = {}
        
        # Normalize update gap (inverse: smaller gap = better)
        # Use sigmoid-like function
        update_gap = features.get('update_gap_days', 365)
        normalized['update_gap_score'] = self._inverse_sigmoid_norm(
            update_gap,
            optimal=7,    # 1 week is optimal
            acceptable=30  # 1 month is acceptable
        )
        
        # Normalize recent activity (30 days)
        recent_30d = features.get('recent_posts_30d', 0)
        normalized['activity_30d_score'] = self._sigmoid_norm(
            recent_30d,
            target=4,  # 4 posts in 30 days is good
            scale=2
        )
        
        # Normalize recent activity (90 days)
        recent_90d = features.get('recent_posts_90d', 0)
        normalized['activity_90d_score'] = self._sigmoid_norm(
            recent_90d,
            target=10,  # 10 posts in 90 days is good
            scale=3
        )
        
        # Normalize average posting frequency
        avg_freq = features.get('avg_posting_frequency_days', 365)
        normalized['frequency_score'] = self._inverse_sigmoid_norm(
            avg_freq,
            optimal=7,     # Weekly posts optimal
            acceptable=30  # Monthly posts acceptable
        )
        
        # Normalize internal pages
        pages = features.get('internal_pages_count', 0)
        normalized['website_depth_score'] = self._sigmoid_norm(
            pages,
            target=20,  # 20 pages is decent
            scale=10
        )
        
        # Consistency score is already 0-1
        normalized['consistency_score'] = features.get('consistency_score', 0.0)
        
        return normalized
    
    def _sigmoid_norm(self, value, target, scale):
        """
        Normalize using sigmoid function (for 'more is better')
        
        Args:
            value: Current value
            target: Target value (0.5 point)
            scale: Scaling factor
        """
        return 1 / (1 + np.exp(-(value - target) / scale))
    
    def _inverse_sigmoid_norm(self, value, optimal, acceptable):
        """
        Inverse normalization (for 'less is better')
        
        Args:
            value: Current value
            optimal: Optimal value (gets score ~1.0)
            acceptable: Acceptable value (gets score ~0.5)
        """
        if value <= optimal:
            return 1.0
        
        # Use exponential decay after optimal point
        decay_rate = -np.log(0.5) / (acceptable - optimal)
        score = np.exp(-decay_rate * (value - optimal))
        
        return max(0.0, min(1.0, score))
