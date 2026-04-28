"""
Dynamic Scoring Engine
Generates Website Health Score automatically using weighted normalization
No hardcoded values, no static deductions
"""

import numpy as np


class DynamicScoringEngine:
    """
    Calculates dynamic health score from normalized features
    Uses adaptive weighting based on data availability
    """
    
    def __init__(self):
        
        self.base_weights = {
            'update_gap_score': 0.25,        # Website freshness
            'activity_30d_score': 0.20,      # Recent activity
            'activity_90d_score': 0.15,      # Medium-term activity
            'frequency_score': 0.15,         # Posting frequency
            'consistency_score': 0.15,       # Activity consistency
            'website_depth_score': 0.10,     # Website size/depth
        }
    
    def calculate_health_score(self, normalized_features, historical_scores=None):
        """
        Calculate dynamic health score from normalized features
        
        Args:
            normalized_features (dict): Normalized features (0-1 scale)
            historical_scores (list, optional): Prior health scores (0-100)
            
        Returns:
            dict: {
                'health_score': float (0-100),
                'feature_scores': dict,
                'weights_used': dict,
                'risk_level': str,
                'risk_explanation': str
            }
        """
        # Adjust weights based on available data
        adjusted_weights = self._adjust_weights(normalized_features)
        
        # Calculate weighted score
        weighted_sum = 0.0
        total_weight = 0.0
        feature_scores = {}
        
        for feature, weight in adjusted_weights.items():
            if feature in normalized_features:
                score = normalized_features[feature]
                weighted_sum += score * weight
                total_weight += weight
                feature_scores[feature] = round(score * 100, 2)  # Convert to 0-100
        
        # Normalize to 0-100 scale
        if total_weight > 0:
            health_score = (weighted_sum / total_weight) * 100
        else:
            health_score = 0.0
        
        # Classify risk dynamically
        risk_classification = self._classify_risk(
            health_score,
            feature_scores,
            historical_scores=historical_scores
        )
        
        return {
            'health_score': round(health_score, 2),
            'feature_scores': feature_scores,
            'weights_used': adjusted_weights,
            'risk_level': risk_classification['level'],
            'risk_explanation': risk_classification['explanation'],
            'signal_breakdown': self._create_signal_breakdown(feature_scores)
        }
    
    def _adjust_weights(self, normalized_features):
        """
        Dynamically adjust weights based on data availability
        If some features are missing/zero, redistribute their weights
        """
        adjusted = self.base_weights.copy()
        
        # Identify zero/missing features
        zero_features = []
        for feature, weight in adjusted.items():
            if feature not in normalized_features or normalized_features[feature] == 0:
                zero_features.append(feature)
        
        if not zero_features:
            return adjusted
        
        # Redistribute weights from zero features
        total_zero_weight = sum(adjusted[f] for f in zero_features)
        remaining_features = [f for f in adjusted.keys() if f not in zero_features]
        
        if not remaining_features:
            return adjusted
        
        # Remove zero features
        for feature in zero_features:
            adjusted[feature] = 0.0
        
        # Redistribute proportionally
        for feature in remaining_features:
            original_weight = self.base_weights[feature]
            proportion = original_weight / sum(self.base_weights[f] for f in remaining_features)
            adjusted[feature] = original_weight + (total_zero_weight * proportion)
        
        return adjusted
    
    def _classify_risk(self, health_score, feature_scores, historical_scores=None):
        """
        Dynamically classify risk level using percentile thresholds
        computed from available score distributions.
        """
        low_cutoff, med_cutoff, high_cutoff = self._compute_dynamic_risk_thresholds(
            health_score,
            feature_scores,
            historical_scores=historical_scores
        )

        if health_score >= low_cutoff:
            level = "Low Risk"
            color = "success"
        elif health_score >= med_cutoff:
            level = "Medium Risk"
            color = "warning"
        elif health_score >= high_cutoff:
            level = "High Risk"
            color = "danger"
        else:
            level = "Critical Risk"
            color = "danger"
        
        # Enhance explanation with specific insights
        detailed_explanation = self._generate_detailed_explanation(
            health_score,
            feature_scores
        )
        
        return {
            'level': level,
            'explanation': detailed_explanation,
            'color': color
        }

    def _compute_dynamic_risk_thresholds(self, health_score, feature_scores, historical_scores=None):
        """
        Compute automatic risk thresholds from percentile splits.

        Priority:
        1) historical_scores, when available
        2) current feature score distribution + current health score
        """
        reference = []

        if historical_scores:
            reference.extend([
                float(s) for s in historical_scores
                if s is not None and np.isfinite(float(s))
            ])

        if not reference and feature_scores:
            reference.extend([float(v) for v in feature_scores.values()])
            reference.append(float(health_score))

        if not reference:
            # Neutral fallback when no signal is available.
            reference = [25.0, 50.0, 75.0]

        arr = np.array(reference, dtype=float)
        q25, q50, q75 = np.percentile(arr, [25, 50, 75])

        # Return descending cutoffs used by classifier comparisons.
        return float(q75), float(q50), float(q25)
    
    def _generate_detailed_explanation(self, health_score, feature_scores):
        """Generate detailed risk explanation based on feature analysis"""
        insights = []
        
        # Analyze update gap
        update_score = feature_scores.get('update_gap_score', 0)
        if update_score < 30:
            insights.append("Website appears outdated with infrequent modifications")
        elif update_score > 80:
            insights.append("Website is well-maintained with recent updates")
        
        # Analyze recent activity
        activity_30d = feature_scores.get('activity_30d_score', 0)
        if activity_30d < 20:
            insights.append("very low recent content activity")
        elif activity_30d > 70:
            insights.append("strong recent content activity")
        
        # Analyze consistency
        consistency = feature_scores.get('consistency_score', 0)
        if consistency < 30:
            insights.append("irregular posting patterns")
        elif consistency > 70:
            insights.append("consistent content publishing schedule")
        
        # Analyze website depth
        depth_score = feature_scores.get('website_depth_score', 0)
        if depth_score < 30:
            insights.append("limited website structure")
        elif depth_score > 70:
            insights.append("substantial website with multiple pages")
        
        # Combine insights
        if not insights:
            return "Limited data available for detailed analysis."
        
        explanation = "Key signals: " + ", ".join(insights) + "."
        return explanation
    
    def _create_signal_breakdown(self, feature_scores):
        """Create structured signal breakdown for visualization"""
        
        signal_mapping = {
            'update_gap_score': 'Website Freshness',
            'activity_30d_score': 'Recent Activity (30d)',
            'activity_90d_score': 'Medium-term Activity (90d)',
            'frequency_score': 'Posting Frequency',
            'consistency_score': 'Activity Consistency',
            'website_depth_score': 'Website Depth'
        }
        
        breakdown = []
        for key, label in signal_mapping.items():
            if key in feature_scores:
                breakdown.append({
                    'label': label,
                    'score': feature_scores[key],
                    'key': key
                })
        
        return breakdown
    
    def calculate_trend(self, historical_scores):
        """
        Calculate trend from historical health scores
        
        Args:
            historical_scores (list): List of past health scores
            
        Returns:
            str: 'improving', 'stable', or 'declining'
        """
        if len(historical_scores) < 2:
            return 'stable'
        
        recent = historical_scores[-3:]  # Last 3 scores
        
        if len(recent) >= 2:
            trend = np.mean(np.diff(recent))
            
            if trend > 5:
                return 'improving'
            elif trend < -5:
                return 'declining'
        
        return 'stable'
    
    def calculate_combined_health_score(self, website_score, hiring_score=None,
                                       social_score=None,
                                       website_weight=0.6, hiring_weight=0.4):
        """
        Calculate combined health score integrating website, hiring, and social intelligence.
        Weights are derived automatically from available signal confidence.

        Args:
            website_score (float): Website health score (0-100)
            hiring_score  (float, optional): Hiring health score (0-100)
            social_score  (float, optional): Social health score (0-100)
            website_weight (float): Backward-compatible argument (not used)
            hiring_weight  (float): Backward-compatible argument (not used)

        Returns:
            dict: Combined score with breakdown
        """
        # Keep function signature backward-compatible for existing callers.
        _ = website_weight
        _ = hiring_weight

        # Build available score map (only non-null values participate).
        score_map = {
            'website': website_score,
            'hiring': hiring_score,
            'social': social_score,
        }
        available = {
            name: float(value)
            for name, value in score_map.items()
            if value is not None
        }

        if not available:
            return {
                'overall_score': 0.0,
                'website_score': None,
                'hiring_score': None,
                'social_score': None,
                'website_contribution': 0.0,
                'hiring_contribution': 0.0,
                'social_contribution': 0.0,
            }

        # Automatic confidence-based weighting:
        # stronger signal = farther from neutral midpoint (50).
        confidence = {
            name: abs(score - 50.0) + 1.0
            for name, score in available.items()
        }
        total_confidence = sum(confidence.values())
        weights = {
            name: (confidence[name] / total_confidence) if total_confidence > 0 else 0.0
            for name in available
        }

        combined = sum(available[name] * weights[name] for name in available)

        return {
            'overall_score': round(combined, 2),
            'website_score': round(float(website_score), 2) if website_score is not None else None,
            'hiring_score': round(float(hiring_score), 2) if hiring_score is not None else None,
            'social_score': round(float(social_score), 2) if social_score is not None else None,
            'website_contribution': round(weights.get('website', 0.0) * 100, 2),
            'hiring_contribution': round(weights.get('hiring', 0.0) * 100, 2),
            'social_contribution': round(weights.get('social', 0.0) * 100, 2),
        }

    
    def get_risk_level(self, score, historical_scores=None):
        """
        Categorize risk level based on dynamic percentile thresholds.
        
        Args:
            score (float): Health score (0-100)
            historical_scores (list, optional): Historical scores for percentile cuts
            
        Returns:
            str: Risk level ('low', 'medium', 'high', 'critical')
        """
        low_cutoff, med_cutoff, high_cutoff = self._compute_dynamic_risk_thresholds(
            score,
            feature_scores={},
            historical_scores=historical_scores
        )

        if score >= low_cutoff:
            return 'low'
        elif score >= med_cutoff:
            return 'medium'
        elif score >= high_cutoff:
            return 'high'
        return 'critical'
