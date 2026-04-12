# 🐈 trialcat

**Clinical trial enrollment intelligence, visualized.**

[![MIT License](https://img.shields.io/badge/License-MIT-4a0873.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-5bb545.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-4a0873.svg)](https://fastapi.tiangolo.com/)

An interactive world map that surfaces real aggregate enrollment patterns from ClinicalTrials.gov. Filter by geography, therapeutic area, intervention type, phase, and time period — then click any country or US state to see enrollment statistics: trial counts, total patients enrolled, low/median/high enrollment rates per month, and average time-to-enroll.

**Built because clinical trial benchmarking data is locked up in expensive consulting reports or buried in registries that won't give you an API.** trialcat makes it accessible — for free, forever — to sponsors, CROs, investigators, regulatory professionals, and patients.

🔗 **[trialcat.ai](https://trialcat.ai)** *(launching soon)* · 📋 **[Terms & Disclaimer](https://trialcat.ai/terms)**

> **Disclaimer:** trialcat is for research and educational purposes only. Enrollment rates are approximate. Not intended for clinical, regulatory, or investment decision-making. [Full terms →](https://trialcat.ai/terms)

---

## Screenshots

<p align="center">
  <em>World choropleth with enrollment stats popup (30 cardiovascular Phase 3 trials loaded)</em>
</p>

```
┌─────────────────────────────────────────────────────────────────┐
│ 🐈 Trial Cat          Clinical trial enrollment intelligence    │
├──────────┬──────────────────────────────────────────────────────┤
│ Filters  │                                                      │
│          │              🗺️  Interactive World Map                │
│ Area  ▼  │                                                      │
│ Phase ▼  │         Click any country → enrollment popup         │
│ Status▼  │         Click US → "View by state" drill-down        │
│ Type  ▼  │                                                      │
│ Date  📅 │    ┌──────────────────────────┐                      │
│          │    │ United States (US)       │                      │
│ [Apply]  │    │ Trials: 13              │                      │
│ [Reset]  │    │ Enrolled: 1,241,776     │                      │
│          │    │ Rate: 0.4–127.9 pts/mo  │                      │
│ 30 trials│    │ Median: 14.0 pts/mo     │                      │
│ 45 ctries│    │ [View by state→][CSV ↓] │                      │
│          │    └──────────────────────────┘                      │
└──────────┴──────────────────────────────────────────────────────┘
```

---

## Features

### 🗺️ Interactive Map
- **World choropleth** colored by trial count (green gradient, purple borders for countries with data)
- **Hover** any country → tooltip with name and trial count
- **Click** any country → popup with enrollment stats (total trials, total enrolled, low/median/high enrollment rate, avg duration)
- **US state drill-down** → click US, then "View by state" → zooms to US with state-level choropleth and per-state popups
- **"← Back to world"** button to return from state view

### 🔍 Filters
- Therapeutic area (Cardiovascular, Oncology, Neurology, Ophthalmology, ...)
- Phase (Phase 1–4, Early Phase 1, N/A)
- Overall status (Recruiting, Completed, Terminated, ...)
- Intervention type (Drug, Device, Biological, Behavioral, ...)
- Date range (trial start date from/to)
- All filters apply to every view: world map, US state map, stats popups

### 📊 Export
- **CSV download** from any popup — one click, zero backend overhead
- Includes all stats, applied filters, branded footer with source attribution
- Disclaimer embedded in every export: *"For research and educational purposes only"*

### 📋 Data Pipeline
- Pulls from **ClinicalTrials.gov API v2** (free, public, ~400K+ trials)
- ETL normalizes: ISO country codes, USPS state codes, MeSH therapeutic areas, enrollment rate approximation
- Fault-tolerant batch loading: one bad trial doesn't kill a 10K load
- CLI: `python -m app.etl.refresh --condition=cardiovascular --phase=PHASE3 --limit=500`

---

## Data Sources

| Source | Status | Coverage |
|---|---|---|
| [ClinicalTrials.gov](https://clinicaltrials.gov) | ✅ Live | ~400K+ trials, free public API |
| [ISRCTN](https://www.isrctn.com/) | 🔜 v2 | UK/international, limited REST API |
| [ANZCTR](https://www.anzctr.org.au/) | 🔜 v2 | Australia/New Zealand |
| [WHO ICTRP](https://www.who.int/ictrp) | 🔜 v2 | Aggregates ~20 national registries (weekly XML) |
| [EU CTR / CTIS](https://euclinicaltrials.eu/) | 🔜 v2 | EU clinical trials (bulk export ETL) |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | FastAPI (Python 3.12+) | Async, typed, auto OpenAPI docs |
| **Database** | SQLite (MVP) | Zero config, file-based, handles 500K+ trials fine |
| **Frontend** | Vanilla HTML/JS + Leaflet.js | No build step, no framework, fast iteration |
| **Map tiles** | OpenStreetMap | Free, no API key |
| **Geo data** | Natural Earth 110m + US Census | Country boundaries (257KB) + US states (86KB) |
| **Container** | Docker + docker-compose | Dev and prod parity |
| **Hosting** | Fly.io | Auto-HTTPS, sleep-on-idle, ~$5/mo |
| **Rate limiting** | SlowAPI *(Phase 6)* | IP-based, 1 detailed request/day free tier |
| **AI features** | OpenAI gpt-4o-mini *(Phase 7)* | Endpoint clustering, criteria NL analysis |

---

## Quick Start

### Option A: Python directly (fastest for development)

```bash
# Clone
git clone https://github.com/Angiebio/trialcat.git
cd trialcat

# Set up environment
cp .env.example .env
# Edit .env if you want AI features (OpenAI key) — not required for core map

# Install dependencies
cd backend
pip install -r requirements.txt

# Load some trial data
python -m app.etl.refresh --condition=cardiovascular --phase=PHASE3 --limit=100

# Start the server
python -m uvicorn app.main:app --reload

# Open http://localhost:8000
```

### Option B: Docker

```bash
git clone https://github.com/Angiebio/trialcat.git
cd trialcat
cp .env.example .env
docker-compose up

# Open http://localhost:8000
```

### ETL Examples

```bash
# Load 500 cardiovascular Phase 3 trials
python -m app.etl.refresh --condition=cardiovascular --phase=PHASE3 --limit=500

# Load completed oncology trials
python -m app.etl.refresh --condition=cancer --phase=PHASE3 --status=COMPLETED --limit=200

# Load trials by sponsor
python -m app.etl.refresh --sponsor="Pfizer" --limit=300

# Dry run (fetch but don't write to DB)
python -m app.etl.refresh --condition=diabetes --limit=10 --dry-run
```

---

## API Endpoints

All endpoints return JSON. Full OpenAPI docs at `/docs` when running in development mode.

| Endpoint | Purpose | Example |
|---|---|---|
| `GET /api/filters` | Dropdown values for all filter fields | `/api/filters` |
| `GET /api/aggregate` | Choropleth data (per-country or per-state counts) | `/api/aggregate?by=country&phase=PHASE3` |
| `GET /api/stats` | Summary stats for a filter cohort (popup data) | `/api/stats?country_code=US&therapeutic_area=Cardiovascular` |
| `GET /api/trials` | Paginated trial list | `/api/trials?phase=PHASE3&page=1&page_size=20` |
| `GET /health` | Liveness probe | `/health` |
| `GET /api/version` | Deployment version info | `/api/version` |

### Filter Parameters (shared across aggregate, stats, trials)

| Parameter | Type | Example |
|---|---|---|
| `country_code` | ISO alpha-2 | `US`, `DE`, `JP` |
| `state_code` | USPS 2-letter | `CA`, `NY`, `TX` (only when country_code=US) |
| `therapeutic_area` | string | `Cardiovascular`, `Oncology`, `Neurology` |
| `phase` | enum | `PHASE1`, `PHASE2`, `PHASE3`, `PHASE4` |
| `status` | enum | `RECRUITING`, `COMPLETED`, `TERMINATED` |
| `study_type` | enum | `INTERVENTIONAL`, `OBSERVATIONAL` |
| `intervention_type` | enum | `DRUG`, `DEVICE`, `BIOLOGICAL`, `BEHAVIORAL` |
| `start_date` | date | `2025-01-01` (trial start date lower bound) |
| `end_date` | date | `2026-12-31` (trial start date upper bound) |

---

## Project Structure

```
trialcat/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point + route registration
│   │   ├── config.py            # Pydantic settings from .env
│   │   ├── db.py                # SQLAlchemy engine + session management
│   │   ├── models/              # SQLAlchemy models (Trial, Location, Intervention, ...)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routes/              # API endpoint handlers
│   │   ├── services/            # Business logic (CT.gov client, parser, stats, geo)
│   │   └── etl/                 # ETL pipeline (loader, refresh CLI)
│   ├── tests/                   # pytest suite (87 tests)
│   │   ├── fixtures/            # Real CT.gov sample data for testing
│   │   ├── test_parser.py       # Parser unit + integration tests
│   │   ├── test_loader.py       # ETL loader tests (incl. fault tolerance)
│   │   ├── test_geo.py          # Country + US state normalization tests
│   │   └── test_api.py          # Full endpoint tests via TestClient
│   └── requirements.txt
├── frontend/
│   ├── templates/
│   │   ├── index.html           # Main map page
│   │   └── terms.html           # Terms of Use & Disclaimer
│   └── static/
│       ├── css/main.css         # TRCL brand system (colors, layout)
│       ├── js/map.js            # Leaflet map + choropleth + drill-down + CSV export
│       ├── geo/                 # Country + US state GeoJSON boundaries
│       └── img/                 # Trial Cat logos + favicon
├── data/                        # SQLite database (gitignored, regenerable)
├── Dockerfile                   # Production container
├── docker-compose.yml           # Local dev with hot-reload
├── .env.example                 # Environment template
└── LICENSE                      # MIT
```

---

## Tests

```bash
cd backend
python -m pytest tests/ -v
```

**87 tests** covering:
- Date parsing, phase ranking, device class regex, therapeutic area mapping
- Full trial parsing against 6 real CT.gov fixture trials
- ETL loader: roundtrip, idempotency, fault tolerance, condition dedup
- Country + US state normalization (50 states + DC + territories)
- All 4 API endpoints via FastAPI TestClient with in-memory SQLite

---

## Important Caveats

> **Enrollment rates are approximate.** They are computed from protocol start dates and primary completion dates, which is not the same as the actual enrollment period. For trials with long primary endpoints (e.g., 12-month follow-up), this overestimates duration and underestimates the true monthly rate. The UI labels these as "approximate" and shows sample sizes so users can judge reliability. See the [Terms & Disclaimer](https://trialcat.ai/terms) for the full list of data limitations.

> **Therapeutic area classification is heuristic.** Derived from MeSH ancestor hierarchy with a priority-ordered mapping (specialty areas like Ophthalmology beat general categories like Cardiovascular when a trial has both in its ancestry). Not every trial maps cleanly.

> **Device class is a hint, not authoritative.** Parsed heuristically from intervention description text. Authoritative device classification data comes from the FDA's 510(k)/PMA database, which is a separate data source planned for v2.

---

## Contributing

Contributions are welcome — especially from regulatory professionals who know their regional registries, enrollment patterns, or data quality issues better than we do.

**How to contribute:**
1. Open an issue to discuss your idea before starting significant work
2. Fork the repo, create a branch, make your changes
3. Ensure `python -m pytest tests/` passes
4. Submit a PR against `main` with a clear description

**Especially welcome:**
- Country/registry-specific expertise (EU CTR, PMDA, ANVISA, etc.)
- Therapeutic area classification improvements
- Accessibility improvements for the map UI
- Translations (English only for now)

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| 0. Project setup | ✅ | Repo, domain (trialcat.ai), structure |
| 1. FastAPI skeleton | ✅ | Hello world + Docker + Dockerfile |
| 2. Data pipeline | ✅ | CT.gov ETL: schema, parser, loader, 42 tests |
| 2.5 Retrospective | ✅ | Honest rate naming, CLI, US states, fault tolerance, brand |
| 3. Backend API | ✅ | /api/filters, /aggregate, /stats, /trials — 87 tests |
| 4. Frontend map | ✅ | Leaflet choropleth, US drill-down, CSV export, Terms page |
| **5. Deployment** | 🔜 | Fly.io, custom domain, HTTPS |
| **6. Rate limiting** | 🔜 | SlowAPI, donate button, mailing list |
| **7. NL features** | 🔜 | Endpoint clustering, criteria comparison, AI-driven insights |
| 8. More registries | 📋 | ISRCTN, WHO ICTRP, EU CTR batch ETL |
| 9. Polish & launch | 📋 | Blog post, social, soft launch |

---

## License

[MIT](LICENSE). Use it, fork it, build on it.

The data trialcat presents is sourced from [ClinicalTrials.gov](https://clinicaltrials.gov), which is public domain. This tool is not affiliated with, endorsed by, or sponsored by NIH, NLM, or the U.S. government.

---

## About

**trialcat** is a project of **[The Real Cat AI Labs, Inc.](https://therealcat.ai)** (therealcat.ai), a Massachusetts 501(c)(3) nonprofit dedicated to research and education on machine cognition and human-AI interaction.

Built in partnership with **[Northeastern University School of Professional Studies Regulatory Affairs Graduate Program](https://graduate.northeastern.edu/programs/ms-regulatory-affairs-cps/master-of-science-in-regulatory-affairs-online/)**.

Built with 🔥 by Angie (human) and Flame (AI). Building Structurally Unprofitable AI since 2023.
