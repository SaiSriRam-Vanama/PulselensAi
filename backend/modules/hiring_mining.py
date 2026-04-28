"""
Hiring Intelligence Data Mining Module
Mines hiring patterns and calculates hiring health metrics
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta


class HiringDataMiner:
    """Mines hiring data to extract meaningful features and trends"""
    
    def __init__(self):
        pass
    
    def mine_hiring_features(self, current_hiring_data, historical_hiring_data=None):
        """
        Mine features from hiring data
        
        Args:
            current_hiring_data (dict): Current scraped hiring data
            historical_hiring_data (list): List of past hiring data records
            
        Returns:
            dict: Mined hiring features
        """
        if not current_hiring_data.get('success'):
            return {
                'success': False,
                'error': current_hiring_data.get('error', 'No hiring data')
            }
        
        features = {}
        
        # Feature 1: Current open positions
        features['open_positions'] = current_hiring_data.get('open_positions', 0)
        
        # Feature 2: Hiring pages discovered
        features['hiring_pages_found'] = current_hiring_data.get('hiring_pages_found', 0)
        
        # Feature 3: Job diversity (number of unique categories)
        job_listings = current_hiring_data.get('job_listings', [])
        categories = set()
        for job in job_listings:
            if job.get('category'):
                categories.add(job['category'])
        features['job_categories'] = len(categories)
        
        # Feature 4: Calculate hiring trends if historical data available
        if historical_hiring_data and len(historical_hiring_data) > 0:
            trend_metrics = self._calculate_hiring_trends(
                current_hiring_data,
                historical_hiring_data
            )
            features.update(trend_metrics)
        else:
            # No historical data - set neutral values
            features['hiring_growth_rate'] = 0.0
            features['hiring_volatility'] = 0.0
            features['hiring_trend'] = 'stable'
            features['historical_data_available'] = False
        
        # Feature 5: Hiring intensity (positions per hiring page)
        if features['hiring_pages_found'] > 0:
            features['hiring_intensity'] = features['open_positions'] / features['hiring_pages_found']
        else:
            features['hiring_intensity'] = 0.0
        
        return {
            'success': True,
            'features': features,
            'job_listings': job_listings
        }
    
    def _calculate_hiring_trends(self, current_data, historical_data):
        """Calculate hiring growth rate and volatility from historical data"""
        trends = {}
        
        # Extract position counts from historical data
        historical_counts = []
        for record in historical_data[-10:]:  # Last 10 records
            count = record.get('open_positions', 0)
            historical_counts.append(count)
        
        current_count = current_data.get('open_positions', 0)
        
        if len(historical_counts) == 0:
            return {
                'hiring_growth_rate': 0.0,
                'hiring_volatility': 0.0,
                'hiring_trend': 'stable',
                'historical_data_available': False
            }
        
        # Calculate growth rate (change from most recent to current)
        most_recent = historical_counts[-1] if historical_counts else 0
        
        if most_recent > 0:
            growth_rate = ((current_count - most_recent) / most_recent) * 100
        elif current_count > 0:
            growth_rate = 100.0  # New hiring activity
        else:
            growth_rate = 0.0
        
        trends['hiring_growth_rate'] = round(growth_rate, 2)
        
        # Calculate volatility (standard deviation of changes)
        all_counts = historical_counts + [current_count]
        
        if len(all_counts) >= 2:
            changes = np.diff(all_counts)
            volatility = np.std(changes) if len(changes) > 0 else 0.0
            trends['hiring_volatility'] = round(float(volatility), 2)
        else:
            trends['hiring_volatility'] = 0.0
        
        # Determine trend direction
        if growth_rate > 10:
            trends['hiring_trend'] = 'growing'
        elif growth_rate < -10:
            trends['hiring_trend'] = 'declining'
        else:
            trends['hiring_trend'] = 'stable'
        
        trends['historical_data_available'] = True
        trends['historical_records_analyzed'] = len(historical_counts)
        
        return trends
    
    def normalize_hiring_features(self, features):
        """
        Normalize hiring features to 0-1 scale
        
        Args:
            features (dict): Raw hiring features
            
        Returns:
            dict: Normalized hiring features
        """
        normalized = {}
        
        # Normalize open positions (more is better)
        open_positions = features.get('open_positions', 0)
        normalized['open_positions_score'] = self._normalize_positions(open_positions)
        
        # Normalize hiring pages (more indicates serious hiring effort)
        hiring_pages = features.get('hiring_pages_found', 0)
        normalized['hiring_effort_score'] = self._normalize_hiring_effort(hiring_pages)
        
        # Normalize growth rate (positive growth is good)
        growth_rate = features.get('hiring_growth_rate', 0)
        normalized['growth_score'] = self._normalize_growth_rate(growth_rate)
        
        # Normalize volatility (lower volatility is better - indicates stability)
        volatility = features.get('hiring_volatility', 0)
        normalized['stability_score'] = self._normalize_volatility(volatility)
        
        # Normalize job diversity
        categories = features.get('job_categories', 0)
        normalized['diversity_score'] = self._normalize_diversity(categories)
        
        # Normalize hiring intensity
        intensity = features.get('hiring_intensity', 0)
        normalized['intensity_score'] = self._normalize_intensity(intensity)
        
        return normalized
    
    def _normalize_positions(self, count):
        """Normalize open positions count (0 to 50+ positions)"""
        if count <= 0:
            return 0.0
        elif count >= 50:
            return 1.0
        else:
            # Sigmoid-like normalization
            return 1 / (1 + np.exp(-(count - 15) / 8))
    
    def _normalize_hiring_effort(self, pages):
        """Normalize number of hiring pages"""
        if pages <= 0:
            return 0.0
        elif pages >= 5:
            return 1.0
        else:
            return pages / 5.0
    
    def _normalize_growth_rate(self, growth_rate):
        """
        Normalize hiring growth rate
        Positive growth is good, but excessive growth might indicate instability
        """
        if growth_rate < -50:
            return 0.0  # Severe decline
        elif growth_rate < 0:
            return 0.5 + (growth_rate / 100)  # Moderate decline
        elif growth_rate <= 50:
            return 0.5 + (growth_rate / 100)  # Healthy growth
        else:
            # Very high growth - diminishing returns
            return 1.0 - (1 / (1 + np.exp(-(growth_rate - 100) / 30)))
    
    def _normalize_volatility(self, volatility):
        """
        Normalize hiring volatility (lower is better)
        High volatility indicates unstable hiring practices
        """
        if volatility <= 0:
            return 1.0
        elif volatility >= 20:
            return 0.0
        else:
            # Inverse exponential decay
            return np.exp(-volatility / 10)
    
    def _normalize_diversity(self, categories):
        """Normalize job category diversity"""
        if categories <= 0:
            return 0.0
        elif categories >= 8:
            return 1.0
        else:
            return categories / 8.0
    
    def _normalize_intensity(self, intensity):
        """Normalize hiring intensity (jobs per page)"""
        if intensity <= 0:
            return 0.0
        elif intensity >= 10:
            return 1.0
        else:
            return intensity / 10.0
    
    def calculate_hiring_health_score(self, normalized_features, historical_available=False):
        """
        Calculate overall hiring health score
        
        Args:
            normalized_features (dict): Normalized hiring features
            historical_available (bool): Whether historical data is available
            
        Returns:
            dict: Hiring health score and breakdown
        """
        # Define weights (adjusted if no historical data)
        if historical_available:
            weights = {
                'open_positions_score': 0.25,
                'hiring_effort_score': 0.15,
                'growth_score': 0.25,
                'stability_score': 0.20,
                'diversity_score': 0.10,
                'intensity_score': 0.05
            }
        else:
            # Without historical data, rely more on current state
            weights = {
                'open_positions_score': 0.40,
                'hiring_effort_score': 0.25,
                'diversity_score': 0.20,
                'intensity_score': 0.15,
                'growth_score': 0.0,
                'stability_score': 0.0
            }
        
        # Calculate weighted score
        total_score = 0.0
        total_weight = 0.0
        breakdown = {}
        
        for feature, weight in weights.items():
            if feature in normalized_features and weight > 0:
                score = normalized_features[feature]
                total_score += score * weight
                total_weight += weight
                breakdown[feature] = {
                    'score': round(score * 100, 2),
                    'weight': weight
                }
        
        # Normalize to 0-100
        if total_weight > 0:
            hiring_health_score = (total_score / total_weight) * 100
        else:
            hiring_health_score = 0.0
        
        # Classify hiring risk
        risk_classification = self._classify_hiring_risk(
            hiring_health_score,
            normalized_features
        )
        
        return {
            'hiring_health_score': round(hiring_health_score, 2),
            'risk_level': risk_classification['level'],
            'risk_explanation': risk_classification['explanation'],
            'feature_breakdown': breakdown,
            'weights_used': weights
        }
    
    def _classify_hiring_risk(self, score, features):
        """Classify hiring risk based on score and features"""
        if score >= 70:
            level = "Low Risk"
            explanation = "Strong hiring signals with active recruitment and healthy growth patterns."
        elif score >= 50:
            level = "Medium Risk"
            explanation = "Moderate hiring activity with some positive indicators but limited scale or growth."
        elif score >= 30:
            level = "High Risk"
            explanation = "Weak hiring signals indicating limited recruitment activity or declining hiring trends."
        else:
            level = "Critical Risk"
            explanation = "Minimal to no hiring activity, suggesting possible financial constraints or operational challenges."
        
        return {
            'level': level,
            'explanation': explanation
        }
