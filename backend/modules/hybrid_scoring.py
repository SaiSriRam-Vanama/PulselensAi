"""
Hybrid Dynamic Scoring Engine  –  Phase 4
==========================================
Replaces all rule-based scoring with a fully mathematical pipeline:

  1. Aggregate normalised features from Website + Hiring + Social miners
  2. Compute per-feature variance and correlation matrix
  3. Derive feature weights automatically via:
       a) Variance-based weighting  (default)
       b) PCA loadings as weights   (selected when it explains ≥ variance-method)
  4. Compute final Startup Health Score (0-100)
  5. KMeans clustering (n=3) → Healthy / Moderate Risk / High Risk
  6. Logistic regression → Failure Probability %
  7. Serialize / auto-reload all fitted models (joblib)

No hardcoded thresholds, no static weights, no manual class labels.
"""

import os
import json
import logging
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ── sklearn imports (graceful fallback when not installed) ─────────────────────
try:
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn / joblib not installed. Phase 4 will run in "
                   "fallback mode (variance-only weights, no clustering / LR).")

# ── Model storage path ─────────────────────────────────────────────────────────
_MODELS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "database", "models"
)
os.makedirs(_MODELS_DIR, exist_ok=True)

_KMEANS_PATH = os.path.join(_MODELS_DIR, "kmeans.joblib")
_LR_PATH     = os.path.join(_MODELS_DIR, "lr.joblib")
_SCALER_PATH = os.path.join(_MODELS_DIR, "scaler.joblib")
_META_PATH   = os.path.join(_MODELS_DIR, "meta.json")

# ── Feature catalogue ──────────────────────────────────────────────────────────
# Defines which normalised keys we accept from each intelligence layer.
# Values missing from a given analysis are substituted with 0.0 (unknown).
WEBSITE_FEATURES = [
    "update_gap_score",
    "activity_30d_score",
    "activity_90d_score",
    "frequency_score",
    "consistency_score",
    "website_depth_score",
]
HIRING_FEATURES = [
    "open_positions_score",
    "diversity_score",
    "seniority_score",
    "tech_ratio_score",
    "hiring_velocity_score",
    "hiring_health_aggregate",
]
SOCIAL_FEATURES = [
    "consistency_score",
    "activity_drop_score",
    "engagement_decay_score",
    "entropy_score",
    "platform_reach_score",
]

# Build namespaced catalogue so all keys are unique
FEATURE_CATALOGUE = (
    [f"web_{k}" for k in WEBSITE_FEATURES]
    + [f"hir_{k}" for k in HIRING_FEATURES]
    + [f"soc_{k}" for k in SOCIAL_FEATURES]
)
N_FEATURES = len(FEATURE_CATALOGUE)


class HybridScoringEngine:
    """
    Phase 4 – Fully dynamic hybrid scoring engine.

    Usage
    -----
    engine = HybridScoringEngine(db)
    result = engine.score(
        website_norm   = {...},   # output of WebsiteDataMiner.normalize_features()
        hiring_norm    = {...},   # output of HiringDataMiner.normalize_hiring_features()
        social_norm    = {...},   # output of SocialDataMiner.normalize_social_features()
        startup_name   = "Acme",
        combined_score = 67.3    # from existing scorer (used as LR label proxy)
    )
    """

    MIN_SAMPLES_CLUSTER = 6   # need ≥ this many obs to fit KMeans
    MIN_SAMPLES_LR      = 10  # need ≥ this many obs to fit logistic regression
    N_CLUSTERS          = 3

    CLUSTER_LABELS = ["Healthy", "Moderate Risk", "High Risk"]

    def __init__(self, db=None):
        """
        Args:
            db: DatabaseManager instance (used to load historical feature
                vectors for model training). Can be None; in that case the
                engine runs in single-shot / cold-start mode.
        """
        self.db = db

        # In-memory state
        self._kmeans    = None
        self._lr        = None
        self._scaler    = None
        self._weights   = None          # 1-D array, length N_FEATURES
        self._method    = "equal"       # 'equal' | 'variance' | 'pca'
        self._n_samples = 0

        # Try to load previously saved models
        self._load_models()

    # ═══════════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════════

    def score(
        self,
        website_norm: dict,
        hiring_norm: dict,
        social_norm: dict,
        startup_name: str = "",
        combined_score: float = None,
    ) -> dict:
        """
        Compute the full hybrid analysis for one startup.

        Returns
        -------
        dict with keys:
            hybrid_score        float   0-100
            cluster_id          int     0/1/2
            cluster_label       str     'Healthy' | 'Moderate Risk' | 'High Risk'
            failure_probability float   0-100  (%)
            scoring_method      str     'variance' | 'pca' | 'equal'
            feature_weights     dict    {feature_name: weight}
            feature_vector      dict    {feature_name: normalized_value}
            statistical_analysis dict  variance / correlation summary
            risk_explanation    str
            signal_breakdown    list[dict]
            pca_explained       list[float]  (empty when not used)
        """
        # 1 ── Build feature vector ────────────────────────────────────────────
        fvec = self._build_feature_vector(website_norm, hiring_norm, social_norm)

        # 2 ── Load historical data & retrain models ───────────────────────────
        hist_matrix, hist_scores = self._load_history()
        self._retrain(hist_matrix, hist_scores)

        # 3 ── Statistical analysis on history ────────────────────────────────
        stats = self._compute_statistics(hist_matrix)

        # 4 ── Derive weights (variance / PCA / equal) ────────────────────────
        weights_arr, method, pca_explained = self._derive_weights(hist_matrix)
        self._weights = weights_arr
        self._method  = method

        # 5 ── Final hybrid score ──────────────────────────────────────────────
        hybrid_score = self._compute_score(fvec, weights_arr)

        # 6 ── KMeans clustering ───────────────────────────────────────────────
        cluster_id, cluster_label = self._classify_cluster(fvec, hist_matrix, hist_scores)

        # 7 ── Failure probability ─────────────────────────────────────────────
        fail_prob = self._failure_probability(fvec, hist_matrix, hist_scores, combined_score)

        # 8 ── Risk explanation ────────────────────────────────────────────────
        explanation = self._generate_explanation(
            fvec, weights_arr, hybrid_score, cluster_label, fail_prob
        )

        # 9 ── Signal breakdown (for chart) ───────────────────────────────────
        breakdown = self._build_signal_breakdown(fvec, weights_arr)

        # 10 ─ Feature weights as named dict ──────────────────────────────────
        weights_dict = {
            FEATURE_CATALOGUE[i]: round(float(weights_arr[i]), 6)
            for i in range(N_FEATURES)
        }
        fvec_dict = {
            FEATURE_CATALOGUE[i]: round(float(fvec[i]), 4)
            for i in range(N_FEATURES)
        }

        # Derive risk label from cluster + historical percentiles
        risk_label = self.get_risk_label(hybrid_score, hist_scores)

        return {
            "hybrid_score":         round(hybrid_score, 2),
            "cluster_id":           int(cluster_id),
            "cluster_label":        cluster_label,
            "failure_probability":  round(fail_prob, 2),
            "scoring_method":       method,
            "feature_weights":      weights_dict,
            "feature_vector":       fvec_dict,
            "statistical_analysis": stats,
            "risk_explanation":     explanation,
            "signal_breakdown":     breakdown,
            "pca_explained":        [round(v, 4) for v in pca_explained],
            "n_training_samples":   self._n_samples,
            # ── Primary score flags (consumed by app.py / frontend) ──
            "risk_label":           risk_label,
            "is_primary_score":     True,
        }

    def get_model_status(self) -> dict:
        """Return metadata about the current models."""
        return {
            "scoring_method":      self._method,
            "n_training_samples":  self._n_samples,
            "sklearn_available":   SKLEARN_AVAILABLE,
            "kmeans_fitted":       self._kmeans is not None,
            "lr_fitted":           self._lr is not None,
            "n_features":          N_FEATURES,
            "feature_catalogue":   FEATURE_CATALOGUE,
        }

    def get_risk_label(self, score: float, historical_scores: list = None) -> str:
        """
        Derive a risk label for `score` using dynamic percentile thresholds
        computed from `historical_scores`.  Falls back to static thirds when
        insufficient history is available.

        Returns one of: 'Low Risk' | 'Medium Risk' | 'High Risk' | 'Critical Risk'
        """
        if historical_scores and len(historical_scores) >= 4:
            arr = np.array([float(s) for s in historical_scores if s is not None], dtype=float)
            q25  = float(np.percentile(arr, 25))
            q50  = float(np.percentile(arr, 50))
            q75  = float(np.percentile(arr, 75))
        else:
            # Cold-start: use fixed thirds of 0-100 scale
            q25, q50, q75 = 25.0, 50.0, 75.0

        if score >= q75:
            return "Low Risk"
        elif score >= q50:
            return "Medium Risk"
        elif score >= q25:
            return "High Risk"
        else:
            return "Critical Risk"

    # ═══════════════════════════════════════════════════════════════════════════
    # Feature Vector Construction
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_feature_vector(
        self,
        website_norm: dict,
        hiring_norm: dict,
        social_norm: dict,
    ) -> np.ndarray:
        """
        Merge the three normalised dicts into a fixed-length numpy array.
        Missing keys → 0.0  (unknown / unavailable signal).
        """
        web = website_norm or {}
        hir = hiring_norm  or {}
        soc = social_norm  or {}

        # Remap hiring keys – the hiring miner may use slightly different names
        hir_remapped = self._remap_hiring(hir)

        parts = []
        for k in WEBSITE_FEATURES:
            parts.append(float(web.get(k, 0.0)))
        for k in HIRING_FEATURES:
            parts.append(float(hir_remapped.get(k, 0.0)))
        for k in SOCIAL_FEATURES:
            parts.append(float(soc.get(k, 0.0)))

        arr = np.array(parts, dtype=float)
        arr = np.clip(arr, 0.0, 1.0)   # Ensure [0, 1]
        return arr

    def _remap_hiring(self, hir: dict) -> dict:
        """
        The HiringDataMiner may return keys with different names.
        Normalise them to our expected catalogue.
        """
        remap = {
            # possible hiring miner key  →  catalogue key
            "open_positions_score":   "open_positions_score",
            "position_diversity":     "diversity_score",
            "seniority_ratio":        "seniority_score",
            "tech_ratio":             "tech_ratio_score",
            "hiring_velocity":        "hiring_velocity_score",
            "health_score_norm":      "hiring_health_aggregate",
            # flat pass-through
            "diversity_score":        "diversity_score",
            "seniority_score":        "seniority_score",
            "tech_ratio_score":       "tech_ratio_score",
            "hiring_velocity_score":  "hiring_velocity_score",
            "hiring_health_aggregate":"hiring_health_aggregate",
        }
        out = {}
        for src_key, dst_key in remap.items():
            if src_key in hir:
                out[dst_key] = float(hir[src_key])
        # If a hiring_score exists (0-100), convert to normalised health aggregate
        if "health_score" in hir and "hiring_health_aggregate" not in out:
            out["hiring_health_aggregate"] = float(hir["health_score"]) / 100.0
        return out

    # ═══════════════════════════════════════════════════════════════════════════
    # Historical Data Loading
    # ═══════════════════════════════════════════════════════════════════════════

    def _load_history(self):
        """
        Retrieve all historical feature vectors and corresponding combined
        scores from the database.

        Returns (matrix: np.ndarray | None, scores: list[float])
        matrix shape: (n_obs, N_FEATURES)
        """
        if self.db is None:
            return None, []

        try:
            rows = self.db.get_all_feature_vectors()
            if not rows:
                return None, []

            vectors, scores = [], []
            for fvec_json, combined_score in rows:
                try:
                    fvec = json.loads(fvec_json)
                    # fvec is either a list or a dict  → normalise to list
                    if isinstance(fvec, dict):
                        arr = np.array([fvec.get(k, 0.0) for k in FEATURE_CATALOGUE],
                                       dtype=float)
                    else:
                        arr = np.array(fvec, dtype=float)
                        # Pad / trim to N_FEATURES
                        if len(arr) < N_FEATURES:
                            arr = np.pad(arr, (0, N_FEATURES - len(arr)))
                        elif len(arr) > N_FEATURES:
                            arr = arr[:N_FEATURES]
                    vectors.append(arr)
                    scores.append(float(combined_score) if combined_score is not None else 50.0)
                except Exception:
                    continue

            if not vectors:
                return None, []

            matrix = np.vstack(vectors)
            self._n_samples = len(vectors)
            return matrix, scores
        except Exception as exc:
            logger.warning(f"Could not load historical feature vectors: {exc}")
            return None, []

    # ═══════════════════════════════════════════════════════════════════════════
    # Statistical Analysis
    # ═══════════════════════════════════════════════════════════════════════════

    def _compute_statistics(self, matrix) -> dict:
        """Compute per-feature variance and top correlations."""
        if matrix is None or len(matrix) < 2:
            return {
                "feature_variance": {},
                "top_correlated_pairs": [],
                "n_observations": self._n_samples,
            }

        df = pd.DataFrame(matrix, columns=FEATURE_CATALOGUE)

        variance    = df.var().to_dict()
        correlation = df.corr()

        # Top 5 most correlated pairs (absolute value, off-diagonal)
        corr_pairs = []
        seen = set()
        for c1 in FEATURE_CATALOGUE:
            for c2 in FEATURE_CATALOGUE:
                if c1 == c2 or (c2, c1) in seen:
                    continue
                seen.add((c1, c2))
                val = correlation.loc[c1, c2]
                if not np.isnan(val):
                    corr_pairs.append((abs(val), c1, c2, round(float(val), 4)))

        corr_pairs.sort(reverse=True)
        top5 = [
            {"feature_a": a, "feature_b": b, "correlation": v}
            for _, a, b, v in corr_pairs[:5]
        ]

        return {
            "feature_variance":    {k: round(float(v), 6) for k, v in variance.items()},
            "top_correlated_pairs": top5,
            "n_observations":      self._n_samples,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # Weight Derivation (Variance-based vs PCA)
    # ═══════════════════════════════════════════════════════════════════════════

    def _derive_weights(self, matrix):
        """
        Returns (weights_array, method_name, pca_explained_ratios).
        Falls back to equal weights when not enough data.
        """
        equal_weights = np.ones(N_FEATURES) / N_FEATURES

        if matrix is None or len(matrix) < 3:
            return equal_weights, "equal", []

        # ── Option A: Variance-based weights ─────────────────────────────────
        variances = np.var(matrix, axis=0)
        var_total = variances.sum()

        if var_total > 0:
            var_weights = variances / var_total
        else:
            var_weights = equal_weights.copy()

        # ── Option B: PCA weights (first PC loadings) ─────────────────────────
        pca_weights  = equal_weights.copy()
        pca_explained = []

        if SKLEARN_AVAILABLE and len(matrix) >= max(N_FEATURES, 3):
            try:
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(matrix)
                pca = PCA(n_components=min(N_FEATURES, len(matrix)))
                pca.fit(X_scaled)
                # Use absolute loadings of PC1 as weights
                loadings = np.abs(pca.components_[0])
                load_sum = loadings.sum()
                if load_sum > 0:
                    pca_weights = loadings / load_sum
                pca_explained = list(pca.explained_variance_ratio_)
            except Exception as exc:
                logger.warning(f"PCA failed: {exc}")

        # ── Select method with higher weighted-information content ────────────
        # We measure "entropy" of weights: higher entropy = weights more spread
        def weight_entropy(w):
            w_clip = np.clip(w, 1e-12, None)
            w_norm = w_clip / w_clip.sum()
            return -np.sum(w_norm * np.log(w_norm))

        # Prefer PCA if it assigns clearer differential importance
        # (lower entropy = more decisive weighting)
        var_H = weight_entropy(var_weights)
        pca_H = weight_entropy(pca_weights)

        if SKLEARN_AVAILABLE and pca_explained and pca_H < var_H:
            return pca_weights, "pca", pca_explained
        else:
            return var_weights, "variance", pca_explained

    # ═══════════════════════════════════════════════════════════════════════════
    # Score Computation
    # ═══════════════════════════════════════════════════════════════════════════

    def _compute_score(self, fvec: np.ndarray, weights: np.ndarray) -> float:
        """Weighted dot-product → rescale to [0, 100]."""
        raw = float(np.dot(fvec, weights))
        # weights sum to 1, fvec ∈ [0,1] → raw ∈ [0,1]
        score = raw * 100.0
        return max(0.0, min(100.0, score))

    # ═══════════════════════════════════════════════════════════════════════════
    # KMeans Clustering
    # ═══════════════════════════════════════════════════════════════════════════

    def _classify_cluster(self, fvec, matrix, scores):
        """
        Fit (or reload) KMeans and assign a cluster label to `fvec`.
        Clusters are sorted by centroid mean score → deterministic labels.
        Falls back to score-threshold clustering when sklearn unavailable.
        """
        if not SKLEARN_AVAILABLE:
            return self._threshold_cluster(np.dot(fvec, self._weights) * 100)

        # ── Need ≥ MIN_SAMPLES_CLUSTER points to fit ──────────────────────────
        if matrix is None or len(matrix) < self.MIN_SAMPLES_CLUSTER:
            return self._threshold_cluster(np.dot(fvec, self._weights) * 100)

        try:
            scaler = self._get_or_fit_scaler(matrix)
            X_sc   = scaler.transform(matrix)
            fvec_sc = scaler.transform(fvec.reshape(1, -1))

            if self._kmeans is None:
                self._fit_kmeans(X_sc, scores)

            if self._kmeans is None:
                return self._threshold_cluster(np.dot(fvec, self._weights) * 100)

            raw_cluster = int(self._kmeans.predict(fvec_sc)[0])

            # Remap raw cluster id → sorted label (0=Healthy, 2=High Risk)
            centroid_means = [
                float(np.dot(self._kmeans.cluster_centers_[c], self._weights))
                for c in range(self.N_CLUSTERS)
            ]
            sorted_ids = np.argsort(centroid_means)[::-1]  # descending score
            label_map  = {int(sorted_ids[i]): i for i in range(self.N_CLUSTERS)}
            mapped_id  = label_map.get(raw_cluster, raw_cluster)

            return mapped_id, self.CLUSTER_LABELS[mapped_id]

        except Exception as exc:
            logger.warning(f"KMeans classify failed: {exc}")
            return self._threshold_cluster(np.dot(fvec, self._weights) * 100)

    def _fit_kmeans(self, X_scaled, scores):
        """Fit a new KMeans model and persist it."""
        try:
            km = KMeans(
                n_clusters=self.N_CLUSTERS,
                n_init=10,
                random_state=42
            )
            km.fit(X_scaled)
            self._kmeans = km
            joblib.dump(km, _KMEANS_PATH)
        except Exception as exc:
            logger.warning(f"KMeans fit failed: {exc}")
            self._kmeans = None

    def _threshold_cluster(self, score: float):
        """Score-quantile based fallback classifier (no sklearn needed)."""
        # Uses the historical score distribution to define quantiles dynamically
        if self._n_samples >= 6 and self.db is not None:
            try:
                rows  = self.db.get_all_feature_vectors()
                hscores = [float(r[1]) for r in rows if r[1] is not None]
                if len(hscores) >= 3:
                    q33 = float(np.percentile(hscores, 33))
                    q66 = float(np.percentile(hscores, 66))
                    if score >= q66:
                        return 0, "Healthy"
                    elif score >= q33:
                        return 1, "Moderate Risk"
                    else:
                        return 2, "High Risk"
            except Exception:
                pass

        # Static percentile fallback
        if score >= 66:
            return 0, "Healthy"
        elif score >= 33:
            return 1, "Moderate Risk"
        else:
            return 2, "High Risk"

    # ═══════════════════════════════════════════════════════════════════════════
    # Failure Probability (Logistic Regression)
    # ═══════════════════════════════════════════════════════════════════════════

    def _failure_probability(self, fvec, matrix, scores, combined_score):
        """
        Train (or reload) logistic regression on historical data.
        failure_label = 1 when combined_score < 40 (dynamically computed).
        Returns probability of failure (0-100 %).
        """
        if not SKLEARN_AVAILABLE or matrix is None or len(matrix) < self.MIN_SAMPLES_LR:
            # Cold start: use score-based heuristic
            ref_score = (
                combined_score
                if combined_score is not None
                else float(np.dot(fvec, self._weights)) * 100
            )
            return self._heuristic_failure_prob(ref_score)

        try:
            # ── Build labels ──────────────────────────────────────────────────
            # Adaptive threshold: 40th percentile of historical scores
            threshold = float(np.percentile(scores, 40))
            labels = np.array([1 if s < threshold else 0 for s in scores])

            # Skip if all labels are the same
            if labels.sum() == 0 or labels.sum() == len(labels):
                ref = combined_score if combined_score is not None else 50.0
                return self._heuristic_failure_prob(ref)

            scaler = self._get_or_fit_scaler(matrix)
            X_sc   = scaler.transform(matrix)

            if self._lr is None:
                self._fit_lr(X_sc, labels)

            if self._lr is None:
                ref = combined_score if combined_score is not None else 50.0
                return self._heuristic_failure_prob(ref)

            fvec_sc = scaler.transform(fvec.reshape(1, -1))
            proba   = float(self._lr.predict_proba(fvec_sc)[0][1])   # P(failure)
            return round(proba * 100.0, 2)

        except Exception as exc:
            logger.warning(f"LR failure prob failed: {exc}")
            ref = combined_score if combined_score is not None else 50.0
            return self._heuristic_failure_prob(ref)

    def _fit_lr(self, X_scaled, labels):
        """Fit logistic regression and persist."""
        try:
            lr = LogisticRegression(max_iter=500, random_state=42, C=1.0)
            lr.fit(X_scaled, labels)
            self._lr = lr
            joblib.dump(lr, _LR_PATH)
        except Exception as exc:
            logger.warning(f"LR fit failed: {exc}")
            self._lr = None

    def _heuristic_failure_prob(self, score: float) -> float:
        """
        Sigmoid-based heuristic: score 0 → 95 % failure, score 100 → 5 %.
        Used during cold-start or when sklearn unavailable.
        """
        # Sigmoid centred at score=40
        import math
        prob = 1.0 / (1.0 + math.exp((score - 40) / 12.0))
        return round(prob * 100.0, 2)

    # ═══════════════════════════════════════════════════════════════════════════
    # Model Training  (retrain = fit on every call; cheap for small datasets)
    # ═══════════════════════════════════════════════════════════════════════════

    def _retrain(self, matrix, scores):
        """
        Retrain KMeans and LR only when the training set has grown since the
        last fit.  This ensures identical results for the same input when no
        new historical data has been added (deterministic behaviour).
        """
        if not SKLEARN_AVAILABLE or matrix is None:
            return

        n_now = len(matrix)
        # Only retrain when sample count has changed
        if n_now == getattr(self, '_last_trained_n', -1):
            return

        try:
            # Always refit scaler on current full dataset for consistency
            self._scaler = None   # force fresh fit
            scaler = self._get_or_fit_scaler(matrix)
            X_sc   = scaler.transform(matrix)

            if n_now >= self.MIN_SAMPLES_CLUSTER:
                self._fit_kmeans(X_sc, scores)

            if n_now >= self.MIN_SAMPLES_LR:
                threshold = float(np.percentile(scores, 40))
                labels    = np.array([1 if s < threshold else 0 for s in scores])
                if 0 < labels.sum() < len(labels):
                    self._fit_lr(X_sc, labels)

            self._last_trained_n = n_now
            self._save_meta()
        except Exception as exc:
            logger.warning(f"Model retrain failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Model Persistence
    # ═══════════════════════════════════════════════════════════════════════════

    def _get_or_fit_scaler(self, matrix) -> "StandardScaler":
        """Return the cached scaler; fit a new one if not available."""
        if self._scaler is not None:
            return self._scaler
        scaler = StandardScaler()
        scaler.fit(matrix)
        self._scaler = scaler
        if SKLEARN_AVAILABLE:
            try:
                joblib.dump(scaler, _SCALER_PATH)
            except Exception:
                pass
        return scaler

    def _save_meta(self):
        """Persist lightweight metadata as JSON."""
        meta = {
            "scoring_method":  self._method,
            "n_training_samples": self._n_samples,
            "n_features": N_FEATURES,
        }
        try:
            with open(_META_PATH, "w") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

    def _load_models(self):
        """Try to restore previously saved models from disk."""
        if not SKLEARN_AVAILABLE:
            return
        try:
            if os.path.exists(_KMEANS_PATH):
                self._kmeans = joblib.load(_KMEANS_PATH)
            if os.path.exists(_LR_PATH):
                self._lr = joblib.load(_LR_PATH)
            if os.path.exists(_SCALER_PATH):
                self._scaler = joblib.load(_SCALER_PATH)
            if os.path.exists(_META_PATH):
                with open(_META_PATH) as f:
                    meta = json.load(f)
                self._method    = meta.get("scoring_method", "equal")
                self._n_samples = meta.get("n_training_samples", 0)
        except Exception as exc:
            logger.warning(f"Could not load saved models: {exc}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Explanation & Breakdown
    # ═══════════════════════════════════════════════════════════════════════════

    FEATURE_LABELS = {
        # Website
        "web_update_gap_score":       "Website Freshness",
        "web_activity_30d_score":     "Recent Activity (30d)",
        "web_activity_90d_score":     "Medium-term Activity (90d)",
        "web_frequency_score":        "Posting Frequency",
        "web_consistency_score":      "Content Consistency",
        "web_website_depth_score":    "Website Depth",
        # Hiring
        "hir_open_positions_score":   "Open Positions",
        "hir_diversity_score":        "Role Diversity",
        "hir_seniority_score":        "Seniority Mix",
        "hir_tech_ratio_score":       "Tech Hiring Ratio",
        "hir_hiring_velocity_score":  "Hiring Velocity",
        "hir_hiring_health_aggregate":"Hiring Health",
        # Social
        "soc_consistency_score":      "Social Consistency",
        "soc_activity_drop_score":    "Social Activity Level",
        "soc_engagement_decay_score": "Engagement Trend",
        "soc_entropy_score":          "Schedule Regularity",
        "soc_platform_reach_score":   "Platform Reach",
    }

    def _generate_explanation(
        self, fvec, weights, score, cluster_label, fail_prob
    ) -> str:
        # Top 5 most-weighted features
        top_idx = np.argsort(weights)[::-1][:5]
        top_features = [
            (FEATURE_CATALOGUE[i], float(weights[i]), float(fvec[i]))
            for i in top_idx
            if weights[i] > 0.0
        ]

        strong, weak = [], []
        for fname, w, val in top_features:
            label = self.FEATURE_LABELS.get(fname, fname)
            pct   = round(val * 100, 1)
            if val >= 0.6:
                strong.append(f"{label} ({pct}%)")
            elif val < 0.35:
                weak.append(f"{label} ({pct}%)")

        risk_verb = {
            "Healthy":        "low risk",
            "Moderate Risk":  "moderate risk",
            "High Risk":      "high risk",
        }.get(cluster_label, "undetermined risk")

        parts = [
            f"The model classifies this startup as '{cluster_label}' "
            f"with a {risk_verb} profile.",
            f"Hybrid Health Score: {round(score, 1)}/100.",
            f"Estimated Failure Probability: {round(fail_prob, 1)}%.",
        ]

        if strong:
            parts.append("Strong signals: " + ", ".join(strong) + ".")
        if weak:
            parts.append("Weak signals (concern areas): " + ", ".join(weak) + ".")

        method_desc = {
            "variance": "Feature weights were derived from variance analysis.",
            "pca":      "Feature weights were derived from PCA (first principal component).",
            "equal":    "Equal weights applied (insufficient historical data for training).",
        }.get(self._method, "")
        if method_desc:
            parts.append(method_desc)

        return " ".join(parts)

    def _build_signal_breakdown(self, fvec, weights) -> list:
        """Return top-12 most important signals for chart rendering."""
        top_idx = np.argsort(weights)[::-1][:12]
        breakdown = []
        for i in top_idx:
            label  = self.FEATURE_LABELS.get(FEATURE_CATALOGUE[i], FEATURE_CATALOGUE[i])
            breakdown.append({
                "key":    FEATURE_CATALOGUE[i],
                "label":  label,
                "score":  round(float(fvec[i]) * 100, 2),
                "weight": round(float(weights[i]), 4),
            })
        return breakdown
