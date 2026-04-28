# Running Commands

## Quick Start (Recommended)
```
start.bat
```
> Double-click `start.bat` — it auto-installs deps, starts Flask, and opens the browser.

## Manual Start
```
cd backend
pip install -r requirements.txt
python app.py
```

## Dashboard URL
http://localhost:5000

## API Endpoints
| Method | URL | Description |
|--------|-----|-------------|
| POST | /api/analyze | Full 4-phase analysis |
| GET  | /api/recent?limit=N | Recent analyses |
| GET  | /api/statistics | System statistics |
| GET  | /api/search?q=name | Search startups |
| GET  | /api/history/<name> | Startup analysis history |
| GET  | /api/hybrid/history/<name> | Hybrid score trend |
| GET  | /api/model/status | Phase 4 model metadata |
| POST | /api/batch | Batch lookup (cached results) |