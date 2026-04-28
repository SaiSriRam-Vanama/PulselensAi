"""
Social Intelligence Data Mining Module
Phase 3 – Social & Engagement Intelligence Layer

Mines posting consistency, activity drop %, engagement decay rate,
and social entropy index from raw social scraper output.
All scoring is fully dynamic — no hardcoded class labels or dummy values.
"""

import math
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta


class SocialDataMiner:
    """
    Mines raw social scraper data into normalised engagement signals
    and a dynamic Social Health Score.
    """

    def __init__(self):
        # Base weights — redistributed if data is missing
        self.base_weights = {
            'consistency_score':      0.30,   # regularity of posts
            'activity_drop_score':    0.25,   # recent vs prior activity
            'engagement_decay_score': 0.20,   # trend of engagement counts
            'entropy_score':          0.15,   # irregularity penalty
            'platform_reach_score':   0.10,   # number of validated platforms
        }

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def mine_social_features(self, social_data):
        """
        Convert raw social_scraper output into numeric features.

        Args:
            social_data (dict): Output of SocialScraper.scrape_social_data()

        Returns:
            dict: { 'success': bool, 'features': dict, 'platform_summary': dict }
        """
        if not social_data or not social_data.get('success'):
            return {
                'success': False,
                'error': social_data.get('error', 'No social data available'),
                'features': self._zero_features(),
                'platform_summary': {}
            }

        all_timestamps = social_data.get('all_post_timestamps', [])
        all_engagement = social_data.get('all_engagement_events', [])
        validated_links = social_data.get('validated_links', {})
        platform_data   = social_data.get('platform_data', {})

        timestamps_dt = self._parse_timestamps(all_timestamps)

        features = {}

        # 1 – Posting Consistency (lower CoV of gaps = more consistent)
        features['posting_consistency'] = self._calc_posting_consistency(timestamps_dt)

        # 2 – Activity Drop % (recent 30 d vs. prior 30 d)
        features['activity_drop_pct'] = self._calc_activity_drop(timestamps_dt)

        # 3 – Engagement Decay Rate (linear regression slope)
        features['engagement_decay_rate'] = self._calc_engagement_decay(all_engagement)

        # 4 – Social Entropy Index (Shannon entropy of weekday distribution)
        features['social_entropy_index'] = self._calc_social_entropy(timestamps_dt)

        # 5 – Platform Reach (how many validated platforms)
        features['platforms_count'] = len(validated_links)
        features['platforms_found'] = list(validated_links.keys())

        # 6 – Per-platform post counts for chart rendering
        per_platform = {}
        for platform, pdata in platform_data.items():
            ts_list = self._parse_timestamps(pdata.get('recent_post_timestamps', []))
            eng_list = pdata.get('engagement_events', [])
            per_platform[platform] = {
                'url': pdata.get('url', ''),
                'reachable': pdata.get('reachable', False),
                'post_count': len(ts_list),
                'recent_timestamps': pdata.get('recent_post_timestamps', [])[:20],
                'avg_engagement': self._safe_mean(
                    [e['engagement'] for e in eng_list if e.get('engagement') is not None]
                )
            }
        features['per_platform'] = per_platform

        # 7 – Total posts scraped
        features['total_posts_scraped'] = len(timestamps_dt)

        return {
            'success': True,
            'features': features,
            'platform_summary': per_platform
        }

    def normalize_social_features(self, features):
        """
        Normalize social features to [0, 1] scale.

        Args:
            features (dict): Raw mined features from mine_social_features()

        Returns:
            dict: Normalised feature scores keyed by score name
        """
        norm = {}

        # 1 – Posting consistency (0 = chaotic, 1 = perfectly regular)
        #     consistency value is already [0, 1]
        raw_consistency = features.get('posting_consistency', 0.0)
        norm['consistency_score'] = float(np.clip(raw_consistency, 0.0, 1.0))

        # 2 – Activity drop (drop_pct can be negative = decline)
        #     +100% drop → score 0;  0% drop → score 1; improvement > 0 → bonus capped at 1
        drop_pct = features.get('activity_drop_pct', 0.0)
        norm['activity_drop_score'] = self._normalize_activity_drop(drop_pct)

        # 3 – Engagement decay rate (negative slope = decay)
        #     strong positive slope → 1; strong negative slope → 0
        decay_rate = features.get('engagement_decay_rate', 0.0)
        norm['engagement_decay_score'] = self._normalize_decay_rate(decay_rate)

        # 4 – Social entropy (0 = uniform/predictable, 1 = log(7) = maximum chaos)
        #     lower entropy is better; invert and rescale
        entropy = features.get('social_entropy_index', 0.0)
        norm['entropy_score'] = self._normalize_entropy(entropy)

        # 5 – Platform reach (0=none, 1=4+ platforms)
        platforms_count = features.get('platforms_count', 0)
        norm['platform_reach_score'] = min(platforms_count / 4.0, 1.0)

        return norm

    def calculate_social_health_score(self, normalized_features, raw_features=None):
        """
        Compute a dynamic Social Health Score (0-100) from normalized signals.

        Args:
            normalized_features (dict): Output of normalize_social_features()
            raw_features (dict):        Optional raw features for explanation generation

        Returns:
            dict: health_score, risk_level, risk_explanation, signal_breakdown, weights_used
        """
        adjusted_weights = self._adjust_weights(normalized_features)

        weighted_sum  = 0.0
        total_weight  = 0.0
        feature_scores = {}

        for feature, weight in adjusted_weights.items():
            if feature in normalized_features:
                score = normalized_features[feature]
                weighted_sum  += score * weight
                total_weight  += weight
                feature_scores[feature] = round(score * 100, 2)

        social_health_score = (weighted_sum / total_weight * 100) if total_weight > 0 else 0.0
        social_health_score = round(social_health_score, 2)

        risk_info = self._classify_social_risk(social_health_score, feature_scores)

        explanation = self.generate_social_explanation(
            raw_features or {},
            social_health_score,
            feature_scores
        )

        return {
            'health_score':    social_health_score,
            'risk_level':      risk_info['level'],
            'risk_explanation': explanation,
            'risk_color':      risk_info['color'],
            'feature_scores':  feature_scores,
            'weights_used':    adjusted_weights,
            'signal_breakdown': self._build_signal_breakdown(feature_scores)
        }

    def generate_social_explanation(self, raw_features, score, feature_scores=None):
        """
        Auto-generate a natural-language explanation of social health.

        Args:
            raw_features   (dict): raw mined features
            score          (float): social health score (0-100)
            feature_scores (dict): normalised scores per feature (0-100)

        Returns:
            str: Human-readable explanation
        """
        feature_scores = feature_scores or {}
        insights = []

        # Platform presence
        platforms = raw_features.get('platforms_found', [])
        if platforms:
            insights.append(f"Active on {len(platforms)} platform(s): {', '.join(p.capitalize() for p in platforms)}")
        else:
            insights.append("No validated social media profiles discovered")

        # Posting consistency
        cs = feature_scores.get('consistency_score', 0)
        if cs >= 70:
            insights.append("posts are published on a consistent, predictable schedule")
        elif cs >= 40:
            insights.append("posting schedule is moderately irregular")
        else:
            insights.append("posting activity is highly sporadic or infrequent")

        # Activity drop
        drop_pct = raw_features.get('activity_drop_pct', 0.0)
        ads = feature_scores.get('activity_drop_score', 50)
        if drop_pct > 30:
            insights.append(f"recent activity has dropped by ~{drop_pct:.0f}% compared to the prior period (significant decline)")
        elif drop_pct > 0:
            insights.append(f"slight activity decline of ~{drop_pct:.0f}% in the recent period")
        elif drop_pct < -10:
            insights.append(f"activity has increased by ~{abs(drop_pct):.0f}% recently (positive trend)")
        else:
            insights.append("activity level is stable across recent periods")

        # Engagement decay
        eds = feature_scores.get('engagement_decay_score', 50)
        if eds >= 70:
            insights.append("engagement signals (likes/comments) are growing or stable")
        elif eds >= 40:
            insights.append("engagement is showing mild decay")
        else:
            insights.append("engagement counts are declining — audience interaction is weakening")

        # Entropy
        ent = feature_scores.get('entropy_score', 50)
        if ent < 30:
            insights.append("highly irregular posting patterns suggest operational stress")

        # Score summary
        if score >= 75:
            headline = "Strong social presence."
        elif score >= 50:
            headline = "Moderate social activity."
        elif score >= 30:
            headline = "Weak social signals detected."
        else:
            headline = "Critical social inactivity."

        return f"{headline} {'; '.join(insights)}."

    # ──────────────────────────────────────────────────────────────
    # Feature Calculation Helpers
    # ──────────────────────────────────────────────────────────────

    def _calc_posting_consistency(self, timestamps_dt):
        """
        Returns a consistency score [0, 1].
        1 = perfectly regular intervals, 0 = completely chaotic or no posts.
        Uses inverse of Coefficient of Variation of inter-post gaps.
        """
        if len(timestamps_dt) < 2:
            return 0.0

        sorted_ts = sorted(timestamps_dt)
        gaps = []
        for i in range(1, len(sorted_ts)):
            delta = (sorted_ts[i] - sorted_ts[i - 1]).total_seconds() / 3600  # hours
            if delta > 0:
                gaps.append(delta)

        if not gaps:
            return 0.0

        mean_gap = np.mean(gaps)
        std_gap  = np.std(gaps)

        if mean_gap == 0:
            return 0.0

        cov = std_gap / mean_gap   # coefficient of variation
        # Map CoV to [0,1]: CoV=0 → 1.0, CoV≥3 → ~0.05
        consistency = 1.0 / (1.0 + cov)
        return round(float(consistency), 4)

    def _calc_activity_drop(self, timestamps_dt):
        """
        Returns drop percentage (positive = decline, negative = growth).
        Compares post count in the most recent 30 days vs. the prior 30 days.
        All comparisons use UTC-aware datetimes.
        """
        if not timestamps_dt:
            return 0.0

        aware_now = datetime.now(timezone.utc)

        # Ensure every timestamp is UTC-aware
        def make_aware(dt):
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        aware_ts = [make_aware(dt) for dt in timestamps_dt]

        recent_30d  = [dt for dt in aware_ts if (aware_now - dt).days <= 30]
        prior_30_60 = [dt for dt in aware_ts if 30 < (aware_now - dt).days <= 60]

        prior_count  = len(prior_30_60)
        recent_count = len(recent_30d)

        if prior_count == 0 and recent_count == 0:
            return 0.0
        if prior_count == 0:
            return -100.0  # new/growing activity

        drop_pct = ((prior_count - recent_count) / prior_count) * 100
        return round(drop_pct, 2)

    def _calc_engagement_decay(self, engagement_events):
        """
        Returns the linear regression slope of engagement over time.
        Negative slope = decay; positive = growth.
        """
        if len(engagement_events) < 3:
            return 0.0

        values = []
        for ev in engagement_events:
            eng = ev.get('engagement')
            if eng is not None:
                values.append(float(eng))

        if len(values) < 3:
            return 0.0

        x = np.arange(len(values), dtype=float)
        y = np.array(values)

        # Linear fit
        coeffs = np.polyfit(x, y, 1)
        slope  = coeffs[0]  # engagements per post (positive = growing)
        return round(float(slope), 4)

    def _calc_social_entropy(self, timestamps_dt):
        """
        Computes Shannon entropy of post-weekday distribution.
        Range [0, log(7)]: 0 = all posts on 1 day, log(7) ≈ 1.946 = perfectly spread.
        Higher entropy → more irregular schedule.
        """
        if len(timestamps_dt) < 3:
            return 0.0

        def make_aware(dt):
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

        weekdays = [make_aware(dt).weekday() for dt in timestamps_dt]
        from collections import Counter
        counts = Counter(weekdays)
        total  = len(weekdays)

        probs = [cnt / total for cnt in counts.values()]
        entropy = -sum(p * math.log(p) for p in probs if p > 0)
        return round(entropy, 4)

    # ──────────────────────────────────────────────────────────────
    # Normalisation Helpers
    # ──────────────────────────────────────────────────────────────

    def _normalize_activity_drop(self, drop_pct):
        """
        drop_pct: +100 (total decline) → 0.0
                  0    (no change)     → 1.0
                  -100 (doubled)       → 1.0 (capped)
        """
        if drop_pct >= 100:
            return 0.0
        if drop_pct <= -100:
            return 1.0
        # Linear mapping: [-100, 100] → [1.0, 0.0]
        return round(float((100 - drop_pct) / 200), 4)

    def _normalize_decay_rate(self, slope):
        """
        slope > 0 (growth) → towards 1.0
        slope < 0 (decay)  → towards 0.0
        Uses sigmoid: 1 / (1 + e^(−slope/10))
        """
        # Clamp to avoid overflow
        clamped = max(-200.0, min(200.0, slope))
        sigmoid = 1.0 / (1.0 + math.exp(-clamped / 10.0))
        return round(float(sigmoid), 4)

    def _normalize_entropy(self, entropy):
        """
        entropy=0 (uniform posting on single day) → regular → score 1.0
        entropy=log(7)≈1.946 (all 7 days equal)  → very irregular → 0.0

        Invert: score = 1 - (entropy / max_entropy)
        Paradox: uniform spread is actually GOOD for global reach but BAD for consistent cadence.
        We treat HIGH ENTROPY as slightly irregular — penalise only >80% of max.
        """
        max_entropy = math.log(7)  # ≈ 1.946
        if max_entropy == 0:
            return 1.0
        # Penalise only the top 50%: remap [0, max] → [1.0, 0.0]
        normalized = 1.0 - (entropy / max_entropy)
        return round(float(np.clip(normalized, 0.0, 1.0)), 4)

    # ──────────────────────────────────────────────────────────────
    # Scoring Helpers
    # ──────────────────────────────────────────────────────────────

    def _adjust_weights(self, normalized_features):
        """
        Redistribute weight from missing/zero features to present ones.
        """
        adjusted = self.base_weights.copy()

        zero_features = [
            f for f, w in adjusted.items()
            if f not in normalized_features or normalized_features.get(f, 0) == 0
        ]

        if not zero_features:
            return adjusted

        total_zero_weight = sum(adjusted[f] for f in zero_features)
        remaining = [f for f in adjusted if f not in zero_features]

        for f in zero_features:
            adjusted[f] = 0.0

        if remaining:
            total_remaining_base = sum(self.base_weights[f] for f in remaining)
            for f in remaining:
                proportion = self.base_weights[f] / total_remaining_base
                adjusted[f] = self.base_weights[f] + total_zero_weight * proportion

        return adjusted

    def _classify_social_risk(self, score, feature_scores):
        if score >= 74:
            return {'level': 'Low Risk',      'color': 'success'}
        elif score >= 50:
            return {'level': 'Medium Risk',   'color': 'warning'}
        elif score >= 28:
            return {'level': 'High Risk',     'color': 'danger'}
        else:
            return {'level': 'Critical Risk', 'color': 'danger'}

    def _build_signal_breakdown(self, feature_scores):
        label_map = {
            'consistency_score':      'Posting Consistency',
            'activity_drop_score':    'Activity Level',
            'engagement_decay_score': 'Engagement Trend',
            'entropy_score':          'Schedule Regularity',
            'platform_reach_score':   'Platform Reach',
        }
        return [
            {'label': label_map[k], 'score': v, 'key': k}
            for k, v in feature_scores.items()
            if k in label_map
        ]

    # ──────────────────────────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────────────────────────

    def _parse_timestamps(self, raw_list):
        """Convert ISO string timestamps to timezone-AWARE UTC datetime objects."""
        result = []
        for ts in (raw_list or []):
            if not ts:
                continue
            try:
                s = str(ts).strip()
                # Replace Z with +00:00 for fromisoformat compatibility
                s = s.replace('Z', '+00:00')
                dt = datetime.fromisoformat(s)
                # If naive (no tzinfo), assume UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                result.append(dt)
            except Exception:
                continue
        return result

    def _safe_mean(self, values):
        if not values:
            return 0.0
        return round(float(np.mean(values)), 2)

    def _zero_features(self):
        return {
            'posting_consistency':   0.0,
            'activity_drop_pct':     0.0,
            'engagement_decay_rate': 0.0,
            'social_entropy_index':  0.0,
            'platforms_count':       0,
            'platforms_found':       [],
            'per_platform':          {},
            'total_posts_scraped':   0,
        }
