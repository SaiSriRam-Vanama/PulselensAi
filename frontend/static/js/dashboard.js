// ═══════════════════════════════════════════════════════════════════════
//  Startup Health Analysis Dashboard — master JS
//  Phases 1-4 | Navigation | Recent | Compare | Model Status
// ═══════════════════════════════════════════════════════════════════════

'use strict';

/* ─── Chart references ─────────────────────────────────────────────── */
let currentChart          = null;
let contributionChart     = null;
let hiringTrendChart      = null;
let postingFreqChart      = null;
let engagementTrendChart  = null;
let socialRiskPieChart    = null;
let featureImportanceChart = null;
let signalContributionChart = null;
let hybridTrendChartRef   = null;
let compareChartRef       = null;

/* ─── App State ────────────────────────────────────────────────────── */
let currentTab = 'dashboard';
let currentResultTab = 'overview';
let searchDebounceTimer = null;

// ═══════════════════════════════════════════════════════════════════════
//  INITIALISATION
// ═══════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    setupFormHandler();
    loadStatistics();
    // Load recent analyses count for badge
    updateRecentBadge();
    // Check server is reachable
    checkSystemStatus();
});

function checkSystemStatus() {
    fetch('/api/statistics')
        .then(r => {
            const dot  = document.querySelector('.status-dot');
            const text = document.querySelector('.status-text');
            if (r.ok) {
                dot.className  = 'status-dot online';
                text.textContent = 'System Online';
            } else {
                dot.className  = 'status-dot';
                dot.style.background = '#ef4444';
                text.textContent = 'Degraded';
            }
        })
        .catch(() => {
            const dot = document.querySelector('.status-dot');
            if (dot) { dot.style.background = '#ef4444'; }
        });
}

// ═══════════════════════════════════════════════════════════════════════
//  NAVIGATION / TAB SYSTEM
// ═══════════════════════════════════════════════════════════════════════

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    // Deactivate all nav links
    document.querySelectorAll('.nav-link-item').forEach(l => l.classList.remove('active'));
    document.querySelectorAll('.mobile-nav-item').forEach(l => l.classList.remove('active'));

    // Show target tab
    const tabEl = document.getElementById(`tab-${tabName}`);
    if (tabEl) tabEl.classList.add('active');

    // Activate nav link
    const navEl = document.getElementById(`nav-${tabName}`);
    if (navEl) navEl.classList.add('active');
    const mnavEl = document.getElementById(`mnav-${tabName}`);
    if (mnavEl) mnavEl.classList.add('active');

    currentTab = tabName;

    // Load data for the tab
    if (tabName === 'recent')  { loadRecentAnalyses(); }
    if (tabName === 'model')   { loadModelStatus(); }
}

function switchResultTab(tabName) {
    const validTabs = ['overview', 'website', 'hiring', 'social', 'hybrid'];
    if (!validTabs.includes(tabName)) return;

    document.querySelectorAll('.result-tab-content').forEach(t => {
        t.classList.add('d-none');
        t.classList.remove('active');
    });

    document.querySelectorAll('.result-tab-btn').forEach(b => b.classList.remove('active'));

    const target = document.getElementById(`rtab-${tabName}`);
    if (target) {
        target.classList.remove('d-none');
        target.classList.add('active');
    }

    const targetBtn = document.getElementById(`rtab-btn-${tabName}`);
    if (targetBtn) targetBtn.classList.add('active');

    currentResultTab = tabName;
}

function toggleMobileMenu() {
    const drawer  = document.getElementById('mobileMenuDrawer');
    const overlay = document.getElementById('mobileMenuOverlay');
    drawer.classList.toggle('open');
    overlay.classList.toggle('visible');
}

// ═══════════════════════════════════════════════════════════════════════
//  ANALYSIS FORM
// ═══════════════════════════════════════════════════════════════════════

function setupFormHandler() {
    const form = document.getElementById('analysisForm');
    if (form) {
        form.addEventListener('submit', e => {
            e.preventDefault();
            analyzeStartup();
        });
    }
}

async function analyzeStartup() {
    const startupName = (document.getElementById('startupName').value || '').trim();
    const websiteUrl  = (document.getElementById('websiteUrl').value  || '').trim();
    const useCached   = (document.getElementById('useCachedMode') || {}).checked !== false;

    if (!startupName) { showError('Please enter a startup name'); return; }

    showLoading();
    hideResults();
    hideError();

    try {
        const response = await fetch('/api/analyze', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ startup_name: startupName, website_url: websiteUrl || null, use_cached: useCached })
        });

        const data = await response.json();
        hideLoading();

        if (data.success) {
            displayResults(data);
        } else {
            showError(data.error || 'Analysis failed. Could not process this startup.');
        }

        loadStatistics();
        updateRecentBadge();

    } catch (err) {
        hideLoading();
        showError('Network error: ' + err.message);
    }
}

/* ─── Loading State ────────────────────────────────────────────────── */
function showLoading() {
    const btn = document.getElementById('analyzeBtn');
    btn.disabled = true;
    btn.querySelector('.btn-text').textContent = 'Analyzing...';
    btn.querySelector('.spinner-border').classList.remove('d-none');

    document.getElementById('progressSteps').classList.remove('d-none');
    resetProgressSteps();

    const delays = [0, 1200, 2400, 3600, 5000, 6500, 8000, 9500];
    delays.forEach((delay, i) => setTimeout(() => updateProgress(i + 1, 'active'), delay));
}

function hideLoading() {
    const btn = document.getElementById('analyzeBtn');
    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Analyze Now';
    btn.querySelector('.spinner-border').classList.add('d-none');
    for (let i = 1; i <= 8; i++) updateProgress(i, 'completed');
}

function updateProgress(n, status) {
    const el = document.getElementById('step' + n);
    if (el) {
        el.classList.remove('active', 'completed', 'error');
        el.classList.add(status);
    }
}

function resetProgressSteps() {
    for (let i = 1; i <= 8; i++) {
        const el = document.getElementById('step' + i);
        if (el) el.classList.remove('active', 'completed', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════════
//  DISPLAY RESULTS
// ═══════════════════════════════════════════════════════════════════════

function displayResults(data) {
    document.getElementById('welcomeMessage').classList.add('d-none');

    const rc = document.getElementById('resultsContainer');
    rc.classList.remove('d-none');
    rc.classList.add('fade-in');
    switchResultTab('overview');

    // Header
    document.getElementById('resultStartupName').textContent     = data.startup_name;
    document.getElementById('resultWebsiteUrl').href             = data.website_url;
    document.getElementById('resultWebsiteUrlText').textContent  = data.website_url;
    const tsRaw = data.cached ? (data.cache_timestamp || data.timestamp) : data.timestamp;
    const tsText = tsRaw ? new Date(tsRaw).toLocaleString() : new Date().toLocaleString();
    document.getElementById('resultTimestamp').textContent = tsText;

    const modeBadge = document.getElementById('resultDataModeBadge');
    if (modeBadge) {
        if (data.cached) {
            modeBadge.textContent = 'Cached Stable Snapshot';
            modeBadge.className = 'source-badge source-cache';
        } else {
            modeBadge.textContent = 'Live Analysis';
            modeBadge.className = 'source-badge source-live';
        }
    }

    const statusBadge = document.getElementById('resultWebsiteStatus');
    if (data.validation && data.validation.reachable) {
        statusBadge.className = 'status-badge';
        statusBadge.innerHTML = '<i class="bi bi-check-circle-fill"></i> Reachable';
    } else {
        statusBadge.className = 'status-badge danger';
        statusBadge.innerHTML = '<i class="bi bi-x-circle-fill"></i> Not Reachable';
    }

    // Primary hybrid score
    const overallScore = (data.primary_score !== undefined)
        ? data.primary_score
        : (data.combined_scoring ? data.combined_scoring.overall_score : data.scoring.health_score);

    updateHealthScore(overallScore, data.primary_scoring_method);

    // Risk
    const primaryRisk = data.primary_risk_level || data.overall_risk_level || data.scoring.risk_level;
    const primaryFail = data.primary_failure_probability;
    const primaryExpl = (data.hybrid_scoring && !data.hybrid_scoring.error)
        ? data.hybrid_scoring.risk_explanation
        : data.scoring.risk_explanation;

    updateRiskAssessment({ risk_level: primaryRisk, risk_explanation: primaryExpl, failure_probability: primaryFail });

    // Charts
    updateSignalChart((data.scoring && data.scoring.signal_breakdown) || []);
    updateDetailedMetrics(data.features || {});

    if (data.combined_scoring) {
        updateScoreContribution(data.combined_scoring);
    }

    if (data.hiring_data && data.hiring_data.success) {
        updateHiringIntelligence(data);
    } else {
        hideHiringSection();
    }

    if (data.social_data && data.social_data.success) {
        updateSocialIntelligence(data);
    } else {
        hideSocialSection();
    }

    if (data.hybrid_scoring) renderHybridScoring(data.hybrid_scoring, data.startup_name);

    rc.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ─── Health Score ─────────────────────────────────────────────────── */
function updateHealthScore(score, method) {
    const circle = document.getElementById('scoreCircle');
    const val    = document.getElementById('scoreValue');

    val.textContent = score.toFixed(1);
    circle.classList.remove('score-high', 'score-medium', 'score-low');

    if (score >= 75)      circle.classList.add('score-high');
    else if (score >= 50) circle.classList.add('score-medium');
    else                  circle.classList.add('score-low');

    const methodBadge = document.getElementById('scoringMethodBadge');
    if (methodBadge) {
        const map = {
            pca:      { label: '🧠 PCA-Optimized',     cls: 'badge-method-pca' },
            variance: { label: '📊 Variance-Weighted',  cls: 'badge-method-variance' },
            equal:    { label: '⚠️ Bootstrapping…',    cls: 'badge-method-bootstrap' },
            fallback: { label: '⚙️ Fallback Mode',     cls: 'badge-method-fallback' },
        };
        const cfg = map[method] || { label: '🤖 Auto-Computed', cls: 'badge-method-pca' };
        methodBadge.textContent = cfg.label;
        methodBadge.className   = `badge scoring-method-badge ${cfg.cls}`;
    }
}

/* ─── Risk Assessment ──────────────────────────────────────────────── */
function updateRiskAssessment(scoring) {
    document.getElementById('riskLevel').textContent       = scoring.risk_level;
    document.getElementById('riskExplanation').textContent = scoring.risk_explanation;

    const riskAlert = document.getElementById('riskAlert');
    riskAlert.classList.remove('alert-success', 'alert-warning', 'alert-danger');

    const rl = (scoring.risk_level || '').toLowerCase();
    if (rl.includes('low'))        riskAlert.classList.add('alert-success');
    else if (rl.includes('medium')) riskAlert.classList.add('alert-warning');
    else                            riskAlert.classList.add('alert-danger');

    const failEl = document.getElementById('riskFailureProbability');
    if (failEl) {
        if (scoring.failure_probability != null) {
            const fp = scoring.failure_probability;
            const fpColor = fp >= 60 ? '#ef4444' : fp >= 35 ? '#f59e0b' : '#10b981';
            failEl.innerHTML = `Failure Probability: <strong style="color:${fpColor}">${fp.toFixed(1)}%</strong>`;
            failEl.classList.remove('d-none');
        } else {
            failEl.classList.add('d-none');
        }
    }
}

/* ─── Signal Chart ─────────────────────────────────────────────────── */
function updateSignalChart(signalBreakdown) {
    if (!Array.isArray(signalBreakdown) || !signalBreakdown.length) {
        showChartPlaceholder('signalChart', 'No signal breakdown available');
        return;
    }

    const ctx = document.getElementById('signalChart').getContext('2d');
    if (currentChart) currentChart.destroy();

    const labels = signalBreakdown.map(i => i.label);
    const scores = signalBreakdown.map(i => i.score);
    const colors = scores.map(s => s >= 75 ? 'rgba(16,185,129,0.85)' : s >= 50 ? 'rgba(245,158,11,0.85)' : 'rgba(239,68,68,0.85)');
    const borders = scores.map(s => s >= 75 ? 'rgb(5,150,105)'       : s >= 50 ? 'rgb(217,119,6)'       : 'rgb(220,38,38)');

    currentChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ label:'Signal Score', data:scores, backgroundColor:colors, borderColor:borders, borderWidth:2, borderRadius:10, borderSkipped:false }] },
        options: chartBarOptions('Score', 100)
    });
}

/* ─── Detailed Metrics ─────────────────────────────────────────────── */
function updateDetailedMetrics(features) {
    const gap = features.update_gap_days;
    document.getElementById('metricUpdateGap').textContent   = gap === 365 ? 'Unknown' : `${gap}d`;
    document.getElementById('metricPosts30d').textContent    = features.recent_posts_30d || 0;
    document.getElementById('metricPosts90d').textContent    = features.recent_posts_90d || 0;
    const freq = features.avg_posting_frequency_days;
    document.getElementById('metricFrequency').textContent   = freq === 365 ? 'Unknown' : `${freq.toFixed(1)}d`;
    document.getElementById('metricPages').textContent       = features.internal_pages_count || 0;
    document.getElementById('metricConsistency').textContent = ((features.consistency_score || 0) * 100).toFixed(1) + '%';
}

/* ─── Score Contribution ───────────────────────────────────────────── */
function updateScoreContribution(cs) {
    if (!cs || cs.website_score == null) return;

    document.getElementById('websiteScoreDisplay').textContent = cs.website_score.toFixed(1);
    document.getElementById('hiringScoreDisplay').textContent  = cs.hiring_score != null ? cs.hiring_score.toFixed(1)  : 'N/A';
    document.getElementById('socialScoreDisplay').textContent  = cs.social_score  != null ? cs.social_score.toFixed(1)  : 'N/A';

    const ctx = document.getElementById('contributionChart').getContext('2d');
    if (contributionChart) contributionChart.destroy();

    const labels   = ['Website Intelligence'];
    const vals     = [cs.website_contribution];
    const bgs      = ['rgba(99,102,241,0.8)'];
    const bds      = ['rgb(99,102,241)'];

    if (cs.hiring_score != null) { labels.push('Hiring Intelligence'); vals.push(cs.hiring_contribution); bgs.push('rgba(16,185,129,0.8)'); bds.push('rgb(16,185,129)'); }
    if (cs.social_score  != null) { labels.push('Social Intelligence');  vals.push(cs.social_contribution);  bgs.push('rgba(124,58,237,0.8)'); bds.push('rgb(124,58,237)'); }

    contributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: { labels, datasets: [{ data:vals, backgroundColor:bgs, borderColor:bds, borderWidth:2 }] },
        options: chartDoughnutOptions()
    });
}

// ═══════════════════════════════════════════════════════════════════════
//  HIRING INTELLIGENCE
// ═══════════════════════════════════════════════════════════════════════

function updateHiringIntelligence(data) {
    const hf = data.hiring_features || {};
    const hs = data.hiring_scoring  || {};
    const hd = data.hiring_data     || {};
    const openPositions = Number(hf.open_positions != null ? hf.open_positions : hd.open_positions || 0);
    const pagesCount = Number(hd.hiring_pages_found || 0);
    const pages = Array.isArray(hd.hiring_pages) ? hd.hiring_pages : [];
    const healthScore = Number(hs.health_score != null ? hs.health_score : hs.hiring_health_score || 0);

    document.getElementById('hiringCard').classList.remove('d-none');
    document.getElementById('hiringTrendCard').classList.remove('d-none');
    if (openPositions === 0 && pagesCount === 0) {
        document.getElementById('hiringNoData').classList.remove('d-none');
        document.getElementById('hiringDataContent').classList.add('d-none');
    } else {
        document.getElementById('hiringNoData').classList.add('d-none');
        document.getElementById('hiringDataContent').classList.remove('d-none');
    }

    document.getElementById('hiringOpenPositions').textContent = openPositions;
    document.getElementById('hiringHealthScore').textContent   = healthScore.toFixed(1);
    const grRaw = Number(hf.hiring_growth_rate != null ? hf.hiring_growth_rate : hf.growth_rate || 0);
    const grPct = Math.abs(grRaw) <= 1 ? grRaw * 100 : grRaw;
    document.getElementById('hiringGrowthRate').textContent    = grPct > 0 ? '+' + grPct.toFixed(1) + '%' : grPct.toFixed(1) + '%';
    document.getElementById('hiringActivity').textContent      = generateHiringExplanation(hf, hs);
    const pagesDisplay = pages.length || pagesCount;
    document.getElementById('hiringPagesFound').textContent    = `${pagesDisplay} hiring page${pagesDisplay !== 1 ? 's' : ''} found`;

    loadHiringTrendChart(data.startup_name, hf);
}

function hideHiringSection() {
    document.getElementById('hiringCard').classList.remove('d-none');
    document.getElementById('hiringNoData').classList.remove('d-none');
    document.getElementById('hiringDataContent').classList.add('d-none');
    document.getElementById('hiringTrendCard').classList.add('d-none');
}

function generateHiringExplanation(features, scoring) {
    const pos = features.open_positions || 0;
    const hs  = scoring.health_score != null ? scoring.health_score : (scoring.hiring_health_score || 0);
    if (pos === 0) return 'No active job listings found. This may indicate the startup is not actively hiring or hiring pages were not detected.';
    let txt = `The startup has ${pos} open position${pos !== 1 ? 's' : ''}. `;
    if (hs >= 70)      txt += 'Strong hiring activity indicates healthy growth and expansion.';
    else if (hs >= 50) txt += 'Moderate hiring activity suggests steady but cautious growth.';
    else               txt += 'Limited hiring activity may signal cost management or slower growth phase.';
    return txt;
}

function createHiringTrendChartFromSeries(labels, series) {
    const ctx = document.getElementById('hiringTrendChart').getContext('2d');
    if (hiringTrendChart) hiringTrendChart.destroy();

    hiringTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label:'Open Positions', data:series,
                borderColor:'rgb(99,102,241)', backgroundColor:'rgba(99,102,241,0.1)',
                borderWidth:3, fill:true, tension:0.4,
                pointRadius:4, pointHoverRadius:6,
                pointBackgroundColor:'rgb(99,102,241)', pointBorderColor:'#fff', pointBorderWidth:2
            }]
        },
        options: chartLineOptions('Positions')
    });
}

async function loadHiringTrendChart(startupName, fallbackFeatures) {
    if (!startupName) {
        showChartPlaceholder('hiringTrendChart', 'No startup name for hiring history');
        return;
    }

    try {
        const res = await fetch(`/api/hiring/trends/${encodeURIComponent(startupName)}?days=180`);
        const data = await res.json();
        const raw = (data && data.trend_data) || [];

        const points = raw.map(r => {
            if (Array.isArray(r) && r.length >= 2) {
                return { ts: r[0], positions: Number(r[1] || 0) };
            }
            if (r && typeof r === 'object') {
                return { ts: r.scraped_at || r.timestamp, positions: Number(r.open_positions || r.value || 0) };
            }
            return null;
        }).filter(Boolean);

        if (points.length >= 2) {
            const labels = points.map(p => {
                try {
                    return new Date(p.ts).toLocaleDateString('en-US', { month:'short', day:'numeric' });
                } catch (_) {
                    return String(p.ts || '');
                }
            });
            const series = points.map(p => Math.max(0, Math.round(p.positions)));
            createHiringTrendChartFromSeries(labels, series);
            return;
        }

        // Fallback: only current real run exists, so show a single-point chart.
        const currentPositions = Number((fallbackFeatures || {}).open_positions || 0);
        createHiringTrendChartFromSeries(['Current Run'], [currentPositions]);
    } catch (_) {
        showChartPlaceholder('hiringTrendChart', 'Could not load hiring history');
    }
}

// ═══════════════════════════════════════════════════════════════════════
//  PHASE 3 — SOCIAL INTELLIGENCE
// ═══════════════════════════════════════════════════════════════════════

function updateSocialIntelligence(data) {
    const sf = data.social_features  || {};
    const ss = data.social_scoring   || {};
    const sd = data.social_data      || {};

    ['socialCard','postingFreqCard','engagementTrendCard','socialRiskPieCard']
        .forEach(id => document.getElementById(id).classList.remove('d-none'));
    document.getElementById('socialNoData').classList.add('d-none');
    document.getElementById('socialDataContent').classList.remove('d-none');

    renderPlatformBadges(sd.validated_links || {});

    document.getElementById('socialHealthScore').textContent = ss.health_score != null ? ss.health_score.toFixed(1) : 'N/A';

    const fs = ss.feature_scores || {};
    document.getElementById('socialConsistency').textContent = fs.consistency_score != null ? fs.consistency_score.toFixed(1) : '--';

    const dp = sf.activity_drop_pct;
    document.getElementById('socialActivityDrop').textContent = dp != null
        ? (dp > 0 ? '↓' + dp.toFixed(0) + '%' : '↑' + Math.abs(dp).toFixed(0) + '%')
        : '--';

    document.getElementById('socialTotalPosts').textContent = sf.total_posts_scraped || 0;

    const expl = ss.risk_explanation || generateClientSideSocialExplanation(sf, ss);
    document.getElementById('socialExplanationText').textContent = expl;

    createPostingFrequencyChart(sf.per_platform || {});
    createEngagementTrendChart(sd.all_engagement_events || []);
    updateSocialRiskPie(data.combined_scoring || {});
}

function hideSocialSection() {
    document.getElementById('socialCard').classList.remove('d-none');
    document.getElementById('socialNoData').classList.remove('d-none');
    document.getElementById('socialDataContent').classList.add('d-none');
    ['postingFreqCard','engagementTrendCard','socialRiskPieCard']
        .forEach(id => document.getElementById(id).classList.add('d-none'));
}

function renderPlatformBadges(validatedLinks) {
    const c = document.getElementById('socialPlatformBadges');
    const platforms = Object.keys(validatedLinks);
    if (!platforms.length) {
        c.innerHTML = '<span class="text-muted small">No social profiles discovered</span>';
        return;
    }
    const map = {
        linkedin:  { label:'LinkedIn',  cls:'social-badge-linkedin' },
        twitter:   { label:'Twitter/X', cls:'social-badge-twitter' },
        instagram: { label:'Instagram', cls:'social-badge-instagram' },
        facebook:  { label:'Facebook',  cls:'social-badge-facebook' }
    };
    c.innerHTML = platforms.map(p => {
        const cfg = map[p] || { label: p.charAt(0).toUpperCase() + p.slice(1), cls:'social-badge-generic' };
        return `<a href="${validatedLinks[p] || '#'}" target="_blank" class="social-platform-badge ${cfg.cls}">${cfg.label}</a>`;
    }).join('');
}

function createPostingFrequencyChart(perPlatform) {
    const ctx = document.getElementById('postingFreqChart').getContext('2d');
    if (postingFreqChart) postingFreqChart.destroy();

    const platforms = Object.keys(perPlatform);
    if (!platforms.length) { showChartPlaceholder('postingFreqChart', 'No social platforms detected'); return; }

    const postCounts    = platforms.map(p => perPlatform[p].post_count    || 0);
    const avgEngagement = platforms.map(p => perPlatform[p].avg_engagement || 0);
    const pcMap = { linkedin:'#0077b5', twitter:'#1da1f2', instagram:'#e1306c', facebook:'#1877f2' };
    const bgColors = platforms.map(p => (pcMap[p] || '#7c3aed') + 'cc');
    const bdColors = platforms.map(p =>  pcMap[p] || '#7c3aed');

    postingFreqChart = new Chart(ctx, {
        type:'bar',
        data: {
            labels: platforms.map(p => p[0].toUpperCase() + p.slice(1)),
            datasets: [
                { label:'Posts Scraped',  data:postCounts,    backgroundColor:bgColors, borderColor:bdColors, borderWidth:2, borderRadius:8, yAxisID:'y' },
                { label:'Avg Engagement', data:avgEngagement, backgroundColor:'rgba(245,158,11,0.7)', borderColor:'rgb(245,158,11)', borderWidth:2, borderRadius:8, yAxisID:'y1' }
            ]
        },
        options: {
            responsive:true, maintainAspectRatio:true,
            plugins: { legend:{ position:'top' }, tooltip:darkTooltip() },
            scales: {
                y:  { type:'linear', display:true, position:'left',  beginAtZero:true, title:{display:true, text:'Posts', color:'#6b7280'},      grid:{color:'rgba(229,231,235,0.8)'} },
                y1: { type:'linear', display:true, position:'right', beginAtZero:true, title:{display:true, text:'Engagement', color:'#6b7280'}, grid:{drawOnChartArea:false} },
                x:  { grid:{ display:false } }
            },
            animation:{ duration:800, easing:'easeInOutQuart' }
        }
    });
}

function createEngagementTrendChart(allEvents) {
    const ctx = document.getElementById('engagementTrendChart').getContext('2d');
    if (engagementTrendChart) engagementTrendChart.destroy();

    const events = (allEvents || []).filter(e => e.engagement != null);
    if (!events.length) { showChartPlaceholder('engagementTrendChart', 'No engagement data scraped'); return; }

    const slice  = events.slice(-30);
    const labels = slice.map((e, i) => {
        if (e.timestamp) try { return new Date(e.timestamp).toLocaleDateString('en-US', { month:'short', day:'numeric' }); } catch(_){}
        return `#${i + 1}`;
    });
    const values = slice.map(e => e.engagement);
    const movAvg = values.map((_, i) => {
        const w = values.slice(Math.max(0, i - 3), i + 1);
        return w.reduce((a, b) => a + b, 0) / w.length;
    });

    engagementTrendChart = new Chart(ctx, {
        type:'line',
        data: {
            labels,
            datasets: [
                { label:'Engagement Count', data:values, borderColor:'rgba(245,158,11,0.8)', backgroundColor:'rgba(245,158,11,0.1)', borderWidth:2, fill:true, tension:0.3, pointRadius:3 },
                { label:'Trend (4-pt avg)', data:movAvg, borderColor:'rgb(239,68,68)', backgroundColor:'transparent', borderWidth:2, borderDash:[5,5], pointRadius:0, fill:false, tension:0.4 }
            ]
        },
        options: {
            responsive:true, maintainAspectRatio:true,
            plugins: { legend:{ position:'top' }, tooltip:darkTooltip() },
            scales: { y:{ beginAtZero:true, grid:{color:'rgba(229,231,235,0.8)'} }, x:{ grid:{display:false} } },
            animation:{ duration:800 }
        }
    });
}

function updateSocialRiskPie(cs) {
    const ctx = document.getElementById('socialRiskPieChart').getContext('2d');
    if (socialRiskPieChart) socialRiskPieChart.destroy();

    const labels = ['Website Intelligence'];
    const vals   = [cs.website_contribution || 100];
    const bgs    = ['rgba(99,102,241,0.85)'];
    const bds    = ['rgb(99,102,241)'];

    if (cs.hiring_score != null) { labels.push('Hiring Intelligence'); vals.push(cs.hiring_contribution || 0); bgs.push('rgba(139,92,246,0.85)'); bds.push('rgb(139,92,246)'); }
    if (cs.social_score  != null) { labels.push('Social Intelligence');  vals.push(cs.social_contribution  || 0); bgs.push('rgba(236,72,153,0.85)');  bds.push('rgb(236,72,153)');  }

    socialRiskPieChart = new Chart(ctx, {
        type:'pie',
        data: { labels, datasets:[{ data:vals, backgroundColor:bgs, borderColor:bds, borderWidth:2 }] },
        options: {
            responsive:true, maintainAspectRatio:true,
            plugins: {
                legend:{ position:'bottom', labels:{ padding:15, font:{ size:13, weight:'600' } } },
                tooltip:{ ...darkTooltip(), callbacks:{ label: ctx => `${ctx.label}: ${ctx.parsed.toFixed(1)}% of combined score` } }
            },
            animation:{ duration:800 }
        }
    });
}

function generateClientSideSocialExplanation(features, scoring) {
    const pf    = features.platforms_found || [];
    const score = scoring.health_score     || 0;
    if (!pf.length) return 'No social media profiles were discovered for this startup.';
    let txt = `Social presence detected on ${pf.length} platform(s): ${pf.join(', ')}. `;
    if      (score >= 70) txt += 'Social activity signals are strong.';
    else if (score >= 50) txt += 'Moderate social engagement with some inconsistencies.';
    else if (score >= 30) txt += 'Weak social signals — activity appears to be declining.';
    else                  txt += 'Critical: Near-zero social activity detected.';
    return txt;
}

// ═══════════════════════════════════════════════════════════════════════
//  PHASE 4 — HYBRID SCORING ENGINE
// ═══════════════════════════════════════════════════════════════════════

function renderHybridScoring(h, startupName) {
    if (!h) return;

    // Score Arc
    const score = h.hybrid_score || 0;
    document.getElementById('hybridScoreText').textContent = score.toFixed(1);
    const arc = document.getElementById('hybridArcCircle');
    if (arc) {
        const circ   = 326.7;
        const offset = circ - (score / 100) * circ;
        arc.style.transition = 'stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1)';
        setTimeout(() => { arc.style.strokeDashoffset = offset; }, 80);

        const gradStart = score >= 70 ? '#10b981' : score >= 45 ? '#f59e0b' : '#ef4444';
        const gradEnd   = score >= 70 ? '#059669' : score >= 45 ? '#d97706' : '#dc2626';
        const defs = arc.closest('svg').querySelector('linearGradient#hybridGrad');
        if (defs) {
            defs.querySelectorAll('stop')[0].setAttribute('stop-color', gradStart);
            defs.querySelectorAll('stop')[1].setAttribute('stop-color', gradEnd);
        }
    }

    // Cluster Badge
    const clusterBadge = document.getElementById('hybridClusterBadge');
    const clusterLabel = h.cluster_label || 'Unknown';
    const clusterColors = {
        'Healthy':       { bg:'#10b981', txt:'#fff' },
        'Moderate Risk': { bg:'#f59e0b', txt:'#fff' },
        'High Risk':     { bg:'#ef4444', txt:'#fff' },
        'Unknown':       { bg:'#6b7280', txt:'#fff' }
    };
    const cc = clusterColors[clusterLabel] || clusterColors['Unknown'];
    clusterBadge.textContent      = clusterLabel;
    clusterBadge.style.background = cc.bg;
    clusterBadge.style.color      = cc.txt;

    const mLabel = { variance:'📊 Variance-Based', pca:'🧠 PCA-Based', equal:'⚖️ Equal Weights', fallback:'⚠️ Fallback' };
    document.getElementById('hybridScoringMethodBadge').textContent = mLabel[h.scoring_method] || h.scoring_method || 'Auto';

    // Failure Gauge
    const fp = h.failure_probability || 0;
    document.getElementById('failureProbText').textContent = fp.toFixed(1) + '%';
    const failArc = document.getElementById('failureArcPath');
    if (failArc) {
        const full   = 157;
        const offset = full - (fp / 100) * full;
        failArc.style.transition = 'stroke-dashoffset 1.2s ease';
        setTimeout(() => { failArc.style.strokeDashoffset = offset; }, 120);
        failArc.setAttribute('stroke', fp >= 60 ? '#ef4444' : fp >= 35 ? '#f59e0b' : '#10b981');
    }

    const ftag = document.getElementById('failureRiskTag');
    if (fp >= 60)      { ftag.textContent = '⚠️ High Failure Risk';  ftag.style.cssText = 'background:rgba(239,68,68,0.1);color:#ef4444;'; }
    else if (fp >= 35) { ftag.textContent = '🟡 Moderate Risk';       ftag.style.cssText = 'background:rgba(245,158,11,0.1);color:#f59e0b;'; }
    else               { ftag.textContent = '✅ Low Failure Risk';    ftag.style.cssText = 'background:rgba(16,185,129,0.1);color:#10b981;'; }

    const explEl = document.getElementById('hybridExplanationText');
    if (explEl) explEl.textContent = h.risk_explanation || 'No explanation available.';

    const methodEl = document.getElementById('hybridMethodBadge');
    if (methodEl && h.n_training_samples !== undefined) {
        methodEl.textContent = `Automated Model • ${h.n_training_samples} training samples`;
    }

    if (h.feature_weights && Object.keys(h.feature_weights).length > 0) {
        renderFeatureImportanceChart(h.feature_weights, h.feature_vector || {});
    }

    if (h.signal_breakdown && h.signal_breakdown.length > 0) {
        renderSignalContributionChart(h.signal_breakdown);
    }

    if (startupName) loadHybridTrendChart(startupName);
}

function renderFeatureImportanceChart(weights, fvec) {
    const canvas = document.getElementById('featureImportanceChart');
    if (!canvas) return;

    const sorted = Object.entries(weights).sort(([, a], [, b]) => b - a).slice(0, 12);

    const featureLabels = {
        web_update_gap_score:'Website Freshness', web_activity_30d_score:'Recent Activity (30d)',
        web_activity_90d_score:'Medium Activity (90d)', web_frequency_score:'Posting Frequency',
        web_consistency_score:'Content Consistency', web_website_depth_score:'Website Depth',
        hir_open_positions_score:'Open Positions', hir_diversity_score:'Role Diversity',
        hir_seniority_score:'Seniority Mix', hir_tech_ratio_score:'Tech Hiring Ratio',
        hir_hiring_velocity_score:'Hiring Velocity', hir_hiring_health_aggregate:'Hiring Health',
        soc_consistency_score:'Social Consistency', soc_activity_drop_score:'Social Activity',
        soc_engagement_decay_score:'Engagement Trend', soc_entropy_score:'Schedule Regularity',
        soc_platform_reach_score:'Platform Reach',
    };

    const labels  = sorted.map(([k]) => featureLabels[k] || k);
    const wVals   = sorted.map(([, w]) => (w * 100).toFixed(2));
    const sVals   = sorted.map(([k]) => ((fvec[k] || 0) * 100).toFixed(1));
    const bgColors = sorted.map(([k]) => k.startsWith('web_') ? 'rgba(99,102,241,0.8)' : k.startsWith('hir_') ? 'rgba(16,185,129,0.8)' : k.startsWith('soc_') ? 'rgba(124,58,237,0.8)' : 'rgba(107,114,128,0.8)');
    const bdColors = bgColors.map(c => c.replace('0.8)', '1)'));

    if (featureImportanceChart) featureImportanceChart.destroy();
    featureImportanceChart = new Chart(canvas.getContext('2d'), {
        type:'bar',
        data: {
            labels,
            datasets: [
                { label:'Weight (%)', data:wVals, backgroundColor:bgColors, borderColor:bdColors, borderWidth:2, borderRadius:6, borderSkipped:false, yAxisID:'y' },
                { label:'Score (0-100)', data:sVals, backgroundColor:'rgba(245,158,11,0.6)', borderColor:'rgb(245,158,11)', borderWidth:2, borderRadius:6, borderSkipped:false, yAxisID:'y1' }
            ]
        },
        options: {
            indexAxis:'y', responsive:true, maintainAspectRatio:false,
            plugins: { legend:{ position:'top', labels:{ font:{size:12}, padding:16 } }, tooltip:{ ...darkTooltip(), callbacks:{ label: ctx => ctx.dataset.label + ': ' + ctx.parsed.x + (ctx.datasetIndex === 0 ? '%' : '/100') } } },
            scales: {
                y:  { ticks:{ font:{size:11, weight:'600'}, color:'#374151' }, grid:{display:false} },
                x:  { type:'linear', position:'bottom', beginAtZero:true, max:100, display:false },
                y1: { type:'linear', display:false, position:'right', beginAtZero:true, max:100 }
            },
            animation:{ duration:900, easing:'easeInOutQuart' }
        }
    });
}

function renderSignalContributionChart(breakdown) {
    const canvas = document.getElementById('signalContributionChart');
    if (!canvas) return;

    const labels = breakdown.map(s => {
        const label = String(s.label || 'Signal');
        const compact = {
            'Recent Activity (30d)': 'Activity 30d',
            'Medium-term Activity (90d)': 'Activity 90d',
            'Posting Frequency': 'Post Frequency',
            'Content Consistency': 'Consistency',
            'Website Freshness': 'Freshness',
            'Website Depth': 'Web Depth',
            'Open Positions': 'Open Roles',
            'Role Diversity': 'Role Mix',
            'Seniority Mix': 'Seniority',
            'Tech Hiring Ratio': 'Tech Ratio',
            'Hiring Velocity': 'Hiring Speed',
            'Hiring Health': 'Hiring Health',
            'Social Consistency': 'Social Consistency',
            'Social Activity Level': 'Social Activity',
            'Engagement Trend': 'Engagement',
            'Schedule Regularity': 'Regularity',
            'Platform Reach': 'Platform Reach',
        };
        return compact[label] || label;
    });
    const scores   = breakdown.map(s => s.score);
    // Weighted contribution should remain in a 0-100 band for radar scaling.
    const weighted = breakdown.map(s => s.score * s.weight);

    if (signalContributionChart) signalContributionChart.destroy();
    signalContributionChart = new Chart(canvas.getContext('2d'), {
        type:'radar',
        data: {
            labels,
            datasets: [
                { label:'Raw Score (0-100)', data:scores, borderColor:'rgba(99,102,241,1)', backgroundColor:'rgba(99,102,241,0.15)', borderWidth:2, pointBackgroundColor:'rgba(99,102,241,1)', pointRadius:4, fill:true },
                { label:'Weighted Contribution', data:weighted, borderColor:'rgba(16,185,129,1)', backgroundColor:'rgba(16,185,129,0.1)', borderWidth:2, borderDash:[5,3], pointBackgroundColor:'rgba(16,185,129,1)', pointRadius:3, fill:true }
            ]
        },
        options: {
            responsive:true, maintainAspectRatio:false,
            plugins: { legend:{ position:'top', labels:{ font:{size:12}, padding:12 } }, tooltip:{ ...darkTooltip(), callbacks:{ label: ctx => `${ctx.dataset.label}: ${ctx.parsed.r.toFixed(1)}` } } },
            scales: { r:{ beginAtZero:true, max:100, ticks:{ font:{size:10}, color:'#6b7280', stepSize:20, backdropColor:'transparent' }, grid:{color:'rgba(229,231,235,0.6)'}, pointLabels:{font:{size:10, weight:'600'}, color:'#374151'} } },
            animation:{ duration:800 }
        }
    });
}

async function loadHybridTrendChart(startupName) {
    try {
        const res  = await fetch(`/api/hybrid/history/${encodeURIComponent(startupName)}?limit=20`);
        const data = await res.json();

        if (!data.success || !data.hybrid_history || !data.hybrid_history.length) {
            showChartPlaceholder('hybridTrendChart', 'No historical data yet — run the analysis again to build a trend.');
            return;
        }

        const history = data.hybrid_history;
        const labels  = history.map(r => {
            try { return new Date(r.scored_at).toLocaleString('en-US', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }); }
            catch { return r.scored_at; }
        });
        const hybridScores   = history.map(r => r.hybrid_score          || 0);
        const combinedScores = history.map(r => r.combined_score         || 0);
        const failProbs      = history.map(r => r.failure_probability    || 0);

        const canvas = document.getElementById('hybridTrendChart');
        if (!canvas) return;
        if (hybridTrendChartRef) hybridTrendChartRef.destroy();

        hybridTrendChartRef = new Chart(canvas.getContext('2d'), {
            type:'line',
            data: {
                labels,
                datasets: [
                    { label:'Hybrid Score',           data:hybridScores,   borderColor:'rgb(99,102,241)',     backgroundColor:'rgba(99,102,241,0.08)',  borderWidth:3, fill:true, tension:0.4, pointRadius:5, pointHoverRadius:7, pointBackgroundColor:'rgb(99,102,241)', pointBorderColor:'#fff', pointBorderWidth:2, yAxisID:'y' },
                    { label:'Combined Signal Score',  data:combinedScores, borderColor:'rgba(16,185,129,0.9)', backgroundColor:'transparent',            borderWidth:2, borderDash:[6,3], fill:false, tension:0.4, pointRadius:3, pointBackgroundColor:'rgb(16,185,129)', yAxisID:'y' },
                    { label:'Failure Probability (%)', data:failProbs,     borderColor:'rgba(239,68,68,0.8)', backgroundColor:'rgba(239,68,68,0.04)',   borderWidth:2, fill:true, tension:0.4, pointRadius:3, pointBackgroundColor:'rgb(239,68,68)', yAxisID:'y' }
                ]
            },
            options: {
                responsive:true, maintainAspectRatio:false,
                plugins: { legend:{ position:'top', labels:{font:{size:12}, padding:12} }, tooltip:{ ...darkTooltip(), callbacks:{ label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}` } } },
                scales: { y:{ beginAtZero:true, max:100, ticks:{font:{size:11, weight:'600'}, color:'#6b7280'}, grid:{color:'rgba(229,231,235,0.7)'} }, x:{ ticks:{font:{size:10}, color:'#9ca3af', maxRotation:35, minRotation:20}, grid:{display:false} } },
                animation:{ duration:900, easing:'easeInOutQuart' }
            }
        });

        const label = document.getElementById('trendChartLabel');
        if (label) label.textContent = `Showing ${history.length} historical analysis run${history.length > 1 ? 's' : ''}`;

    } catch(err) {
        showChartPlaceholder('hybridTrendChart', 'Could not load trend data.');
    }
}

// ═══════════════════════════════════════════════════════════════════════
//  STATISTICS
// ═══════════════════════════════════════════════════════════════════════

async function loadStatistics() {
    try {
        const res  = await fetch('/api/statistics');
        const data = await res.json();
        if (data.success) displayStatistics(data.statistics);
    } catch(err) {
        console.error('Failed to load statistics:', err);
    }
}

function displayStatistics(stats) {
    document.getElementById('statisticsPanel').innerHTML = `
        <div class="stat-item">
            <span class="stat-value">${stats.total_analyses || 0}</span>
            <span class="stat-label">Total Analyses</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${stats.unique_startups || 0}</span>
            <span class="stat-label">Unique Startups</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${(stats.average_health_score || 0).toFixed(1)}</span>
            <span class="stat-label">Avg Health Score</span>
        </div>
    `;
}

async function updateRecentBadge() {
    try {
        const res  = await fetch('/api/statistics');
        const data = await res.json();
        if (data.success) {
            const badge = document.getElementById('recentCountBadge');
            if (badge) badge.textContent = data.statistics.total_analyses || 0;
        }
    } catch(_) {}
}

// ═══════════════════════════════════════════════════════════════════════
//  RECENT ANALYSES TAB
// ═══════════════════════════════════════════════════════════════════════

async function loadRecentAnalyses() {
    const container = document.getElementById('recentTableContainer');
    container.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-3 text-muted">Loading analyses...</p></div>';

    const query = (document.getElementById('searchInput') || {}).value || '';

    try {
        let url = query.trim().length >= 2
            ? `/api/search?q=${encodeURIComponent(query.trim())}`
            : '/api/recent?limit=50';

        const res  = await fetch(url);
        const data = await res.json();

        let analyses = data.analyses || data.results || [];
        analyses = analyses
            .filter(a => typeof a === 'object' && a !== null)
            .map(a => ({
                ...a,
                timestamp: a.timestamp || a.analysis_timestamp || null,
            }));

        // Update label
        const lbl = document.getElementById('recentCountLabel');
        if (lbl) lbl.textContent = `${analyses.length} result${analyses.length !== 1 ? 's' : ''}`;

        if (!analyses.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="bi bi-inbox"></i>
                    <p>No analyses found${query ? ` for "${query}"` : ''}.</p>
                    <p class="small text-muted">Run an analysis from the Dashboard tab first.</p>
                </div>`;
            return;
        }

        container.innerHTML = `
            <div class="table-responsive">
                <table class="analysis-table">
                    <thead>
                        <tr>
                            <th>Startup</th>
                            <th>Website</th>
                            <th>Health Score</th>
                            <th>Risk Level</th>
                            <th>Date</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${analyses.map(a => {
                            const score = a.health_score ?? '--';
                            const scoreNum = parseFloat(score);
                            const scoreCls = scoreNum >= 75 ? 'high' : scoreNum >= 50 ? 'medium' : 'low';
                            const riskText = a.risk_level || 'Unknown';
                            const riskCls  = riskText.toLowerCase().includes('low') ? 'risk-low' : riskText.toLowerCase().includes('medium') ? 'risk-medium' : 'risk-high';
                            const dateStr  = a.timestamp ? new Date(a.timestamp).toLocaleString('en-US', { month:'short', day:'numeric', year:'numeric', hour:'2-digit', minute:'2-digit' }) : '--';
                            return `
                                <tr>
                                    <td><strong>${escapeHtml(a.startup_name || '')}</strong></td>
                                    <td>
                                        ${a.website_url
                                            ? `<a href="${escapeHtml(a.website_url)}" target="_blank" class="result-url" style="font-size:0.85rem;">${safeHostname(a.website_url)}</a>`
                                            : '<span class="text-muted">—</span>'}
                                    </td>
                                    <td><span class="score-pill ${scoreCls}">${isNaN(scoreNum) ? '--' : scoreNum.toFixed(1)}</span></td>
                                    <td><span class="risk-pill ${riskCls}">${escapeHtml(riskText)}</span></td>
                                    <td style="font-size:0.85rem;color:#64748b;">${dateStr}</td>
                                    <td>
                                        <button class="btn-sm-action" onclick="reAnalyzeFromHistory('${escapeHtml(a.startup_name)}','${escapeHtml(a.website_url || '')}')">
                                            <i class="bi bi-arrow-repeat me-1"></i>Re-analyze
                                        </button>
                                    </td>
                                </tr>`;
                        }).join('')}
                    </tbody>
                </table>
            </div>`;

    } catch(err) {
        container.innerHTML = `<div class="alert alert-danger m-3"><i class="bi bi-exclamation-circle me-2"></i>Failed to load analyses: ${escapeHtml(err.message)}</div>`;
    }
}

function debounceSearch() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(loadRecentAnalyses, 400);
}

function reAnalyzeFromHistory(name, url) {
    switchTab('dashboard');
    setTimeout(() => {
        document.getElementById('startupName').value = name;
        document.getElementById('websiteUrl').value  = url;
    }, 100);
}

// ═══════════════════════════════════════════════════════════════════════
//  COMPARE TAB
// ═══════════════════════════════════════════════════════════════════════

async function compareStartups() {
    const nameA = (document.getElementById('compareA').value || '').trim();
    const nameB = (document.getElementById('compareB').value || '').trim();

    if (!nameA || !nameB) {
        document.getElementById('compareError').classList.remove('d-none');
        document.getElementById('compareErrorMsg').textContent = 'Please enter both startup names.';
        document.getElementById('compareResults').classList.add('d-none');
        return;
    }

    document.getElementById('compareError').classList.add('d-none');
    document.getElementById('compareResults').classList.add('d-none');

    // Show loading
    document.getElementById('compareColA').innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>';
    document.getElementById('compareColB').innerHTML = '<div class="text-center py-4"><div class="spinner-border text-success"></div></div>';
    document.getElementById('compareResults').classList.remove('d-none');

    try {
        const [resA, resB] = await Promise.all([
            fetch(`/api/history/${encodeURIComponent(nameA)}?limit=1`).then(r => r.json()),
            fetch(`/api/history/${encodeURIComponent(nameB)}?limit=1`).then(r => r.json())
        ]);

        const dataA = resA.history?.[0];
        const dataB = resB.history?.[0];

        if (!dataA) {
            document.getElementById('compareColA').innerHTML = noDataCard(nameA);
        } else {
            document.getElementById('compareColA').innerHTML = buildCompareCard(dataA, 'a');
        }

        if (!dataB) {
            document.getElementById('compareColB').innerHTML = noDataCard(nameB);
        } else {
            document.getElementById('compareColB').innerHTML = buildCompareCard(dataB, 'b');
        }

        if (dataA && dataB) renderCompareChart(dataA, dataB);

    } catch(err) {
        document.getElementById('compareError').classList.remove('d-none');
        document.getElementById('compareErrorMsg').textContent = 'Error loading comparison: ' + err.message;
    }
}

function buildCompareCard(d, side) {
    const scoreNum = parseFloat(d.health_score ?? 0);
    const colorClass = side === 'a' ? 'compare-a-color' : 'compare-b-color';
    const headerClass = side === 'a' ? 'compare-card-a' : 'compare-card-b';
    return `
        <div class="compare-card ${headerClass}">
            <div class="compare-card-header">
                <div class="card-header-icon ${side === 'a' ? 'indigo' : 'emerald'}">
                    <i class="bi bi-building"></i>
                </div>
                <div>
                    <strong>${escapeHtml(d.startup_name)}</strong>
                    ${d.website_url ? `<a href="${escapeHtml(d.website_url)}" target="_blank" class="d-block result-url" style="font-size:0.8rem;">${safeHostname(d.website_url)}</a>` : ''}
                </div>
            </div>
            <div class="compare-score-big ${colorClass}">${scoreNum.toFixed(1)}</div>
            <p class="text-center text-muted small mb-2" style="font-size:0.75rem;">AI Health Score</p>
            <div class="compare-metric-row">
                <span class="compare-metric-label">Risk Level</span>
                <span class="compare-metric-val">${escapeHtml(d.risk_level || 'Unknown')}</span>
            </div>
            <div class="compare-metric-row">
                <span class="compare-metric-label">Last Analyzed</span>
                <span class="compare-metric-val" style="font-size:0.8rem;">${(d.timestamp || d.analysis_timestamp) ? new Date(d.timestamp || d.analysis_timestamp).toLocaleDateString() : '--'}</span>
            </div>
            <div class="compare-metric-row">
                <span class="compare-metric-label">Website</span>
                <span class="compare-metric-val" style="color:${d.website_url ? '#10b981' : '#ef4444'};font-size:0.85rem;">
                    ${d.website_url ? '✓ Reachable' : '✗ Not Found'}
                </span>
            </div>
        </div>`;
}

function noDataCard(name) {
    return `
        <div class="compare-card">
            <div class="empty-state py-4">
                <i class="bi bi-question-circle" style="font-size:2.5rem;opacity:0.4;display:block;margin-bottom:0.75rem;"></i>
                <p class="fw-bold">${escapeHtml(name)}</p>
                <p class="text-muted small">No analysis data found. Run an analysis first from the Dashboard tab.</p>
            </div>
        </div>`;
}

function renderCompareChart(dataA, dataB) {
    const canvas = document.getElementById('compareChart');
    if (!canvas) return;
    if (compareChartRef) compareChartRef.destroy();

    compareChartRef = new Chart(canvas.getContext('2d'), {
        type:'bar',
        data: {
            labels: [dataA.startup_name, dataB.startup_name],
            datasets: [{
                label: 'AI Health Score',
                data:  [parseFloat(dataA.health_score ?? 0), parseFloat(dataB.health_score ?? 0)],
                backgroundColor: ['rgba(99,102,241,0.8)', 'rgba(16,185,129,0.8)'],
                borderColor:     ['rgb(99,102,241)',       'rgb(16,185,129)'],
                borderWidth: 3, borderRadius: 12, borderSkipped: false
            }]
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { ...darkTooltip(), callbacks: { label: ctx => `Score: ${ctx.parsed.x.toFixed(1)}/100` } }
            },
            scales: {
                x: { beginAtZero: true, max: 100, grid: { color: 'rgba(229,231,235,0.6)' }, ticks: { font: { size: 12, weight: '600' }, color: '#6b7280' } },
                y: { grid: { display: false }, ticks: { font: { size: 14, weight: '700' }, color: '#374151' } }
            },
            animation: { duration: 900, easing: 'easeInOutQuart' }
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════
//  MODEL STATUS TAB
// ═══════════════════════════════════════════════════════════════════════

async function loadModelStatus() {
    const container = document.getElementById('modelStatusContainer');
    container.innerHTML = `
        <div class="text-center py-5 glass-card">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-3 text-muted">Loading model status...</p>
        </div>`;

    try {
        const res  = await fetch('/api/model/status');
        const data = await res.json();

        if (!data.success) throw new Error(data.error || 'Unknown error');

        const ms = data.model_status || {};
        container.innerHTML = buildModelStatusUI(ms);

    } catch(err) {
        container.innerHTML = `<div class="alert alert-danger glass-card"><i class="bi bi-exclamation-circle me-2"></i>Failed to load model status: ${escapeHtml(err.message)}</div>`;
    }
}

function buildModelStatusUI(ms) {
    const method = ms.scoring_method || 'Unknown';
    const n      = ms.n_training_samples ?? '--';
    const nFeat  = ms.n_features ?? '--';
    const nClusters = ms.n_clusters ?? '--';

    const methodLabels = { pca:'🧠 PCA-Optimized', variance:'📊 Variance-Weighted', equal:'⚖️ Equal Weights', fallback:'⚠️ Fallback' };
    const methodLabel = methodLabels[method] || method;

    const pcaInfo = Array.isArray(ms.pca_explained_variance) && ms.pca_explained_variance.length
        ? ms.pca_explained_variance.map((v, i) => `PC${i+1}: ${(v*100).toFixed(1)}%`).join(' | ')
        : 'N/A';

    const topFeatures = ms.top_features || [];
    const topFeatHtml = topFeatures.length
        ? topFeatures.slice(0, 8).map(([k, w]) => `
            <div class="compare-metric-row">
                <span class="compare-metric-label">${k}</span>
                <span class="compare-metric-val">${(w * 100).toFixed(2)}%</span>
            </div>`).join('')
        : '<div class="text-muted p-3">No feature data available</div>';

    return `
        <div class="model-status-grid">
            <div class="model-stat-card">
                <div class="model-stat-label">Scoring Method</div>
                <div class="model-stat-val" style="font-size:1.2rem;">${methodLabel}</div>
                <div class="model-stat-sub">Active algorithm for this session</div>
            </div>
            <div class="model-stat-card emerald-border">
                <div class="model-stat-label">Training Samples</div>
                <div class="model-stat-val">${n}</div>
                <div class="model-stat-sub">Historical analyses used to train the model</div>
            </div>
            <div class="model-stat-card amber-border">
                <div class="model-stat-label">Feature Dimensions</div>
                <div class="model-stat-val">${nFeat}</div>
                <div class="model-stat-sub">Total signals fed into the hybrid scorer</div>
            </div>
            <div class="model-stat-card violet-border">
                <div class="model-stat-label">KMeans Clusters</div>
                <div class="model-stat-val">${nClusters}</div>
                <div class="model-stat-sub">Risk cluster groups identified</div>
            </div>
        </div>

        <div class="row g-4">
            <div class="col-md-6">
                <div class="glass-card">
                    <div class="glass-card-header">
                        <div class="card-header-icon amber"><i class="bi bi-bar-chart-fill"></i></div>
                        <h5 class="mb-0 text-gradient">Top Feature Weights</h5>
                    </div>
                    <div class="glass-card-body p-0">
                        ${topFeatHtml}
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="glass-card">
                    <div class="glass-card-header">
                        <div class="card-header-icon violet"><i class="bi bi-cpu-fill"></i></div>
                        <h5 class="mb-0 text-gradient">PCA Variance Explained</h5>
                    </div>
                    <div class="glass-card-body">
                        <p class="text-muted small" style="line-height:1.8;">${pcaInfo}</p>
                        <div class="mt-3">
                            <div class="model-stat-label">Cluster Labels</div>
                            <div class="d-flex gap-2 flex-wrap mt-2">
                                <span class="badge" style="background:#10b981;color:#fff;padding:6px 14px;">Healthy</span>
                                <span class="badge" style="background:#f59e0b;color:#fff;padding:6px 14px;">Moderate Risk</span>
                                <span class="badge" style="background:#ef4444;color:#fff;padding:6px 14px;">High Risk</span>
                            </div>
                        </div>
                        <div class="mt-3">
                            <div class="model-stat-label">Phases Active</div>
                            <div class="d-flex gap-2 flex-wrap mt-2">
                                <span class="badge" style="background:rgba(99,102,241,0.15);color:#6366f1;padding:6px 14px;">Phase 1: Website</span>
                                <span class="badge" style="background:rgba(16,185,129,0.15);color:#059669;padding:6px 14px;">Phase 2: Hiring</span>
                                <span class="badge" style="background:rgba(124,58,237,0.15);color:#7c3aed;padding:6px 14px;">Phase 3: Social</span>
                                <span class="badge" style="background:rgba(139,92,246,0.15);color:#8b5cf6;padding:6px 14px;">Phase 4: Hybrid AI</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
}

// ═══════════════════════════════════════════════════════════════════════
//  ERROR / VISIBILITY HELPERS
// ═══════════════════════════════════════════════════════════════════════

function showError(msg) {
    hideResults();
    document.getElementById('welcomeMessage').classList.add('d-none');
    const ec = document.getElementById('errorContainer');
    document.getElementById('errorMessage').textContent = msg;
    ec.classList.remove('d-none');
    ec.classList.add('fade-in');
}

function hideError()   { document.getElementById('errorContainer').classList.add('d-none'); }
function hideResults() { document.getElementById('resultsContainer').classList.add('d-none'); }

// ═══════════════════════════════════════════════════════════════════════
//  CHART OPTION FACTORIES
// ═══════════════════════════════════════════════════════════════════════

function darkTooltip() {
    return {
        backgroundColor: 'rgba(15,23,42,0.95)',
        padding: 12,
        titleFont: { size: 13, weight: 'bold' },
        bodyFont:  { size: 12 },
        cornerRadius: 10,
        borderColor: 'rgba(99,102,241,0.2)',
        borderWidth: 1
    };
}

function chartBarOptions(yLabel, maxY) {
    return {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend:{ display:false }, tooltip:darkTooltip() },
        scales: {
            y: { beginAtZero:true, max:maxY, ticks:{ font:{size:12, weight:'600'}, color:'#6b7280' }, grid:{ color:'rgba(229,231,235,0.8)', drawBorder:false } },
            x: { ticks:{ font:{size:11, weight:'600'}, color:'#4b5563' }, grid:{ display:false, drawBorder:false } }
        },
        animation: { duration:800, easing:'easeInOutQuart' }
    };
}

function chartLineOptions(yLabel) {
    return {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend:{ display:false }, tooltip:{ ...darkTooltip(), callbacks:{ label: ctx => `${yLabel}: ${ctx.parsed.y}` } } },
        scales: {
            y: { beginAtZero:true, ticks:{ stepSize:1, font:{size:12, weight:'600'}, color:'#6b7280' }, grid:{ color:'rgba(229,231,235,0.8)', drawBorder:false } },
            x: { ticks:{ font:{size:11, weight:'600'}, color:'#4b5563', maxRotation:45, minRotation:45 }, grid:{ display:false, drawBorder:false } }
        },
        animation: { duration:800, easing:'easeInOutQuart' }
    };
}

function chartDoughnutOptions() {
    return {
        responsive: true, maintainAspectRatio: false,
        plugins: {
            legend:{ position:'bottom', labels:{ padding:15, font:{size:13, weight:'600'} } },
            tooltip:{ ...darkTooltip(), callbacks:{ label: ctx => `${ctx.label}: ${ctx.parsed.toFixed(1)}%` } }
        }
    };
}

function showChartPlaceholder(canvasId, message) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // Render placeholder at device pixel ratio to avoid blurry stretched text.
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(280, canvas.clientWidth || 600);
    const cssHeight = parseFloat(window.getComputedStyle(canvas).height || '220');
    const height = Math.max(180, Number.isFinite(cssHeight) ? cssHeight : 220);

    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);

    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.font = '600 20px Inter, sans-serif';
    ctx.fillStyle = '#9ca3af';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(message, width / 2, height / 2);
}

// ═══════════════════════════════════════════════════════════════════════
//  UTILITIES
// ═══════════════════════════════════════════════════════════════════════

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function safeHostname(url) {
    try {
        return new URL(url).hostname;
    } catch (_) {
        return String(url || '').replace(/^https?:\/\//i, '').replace(/\/$/, '') || 'invalid-url';
    }
}
