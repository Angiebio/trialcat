# 🐈 trialcat

**Clinical trial enrollment intelligence, visualized.**

An interactive world map that surfaces real aggregate enrollment patterns from public clinical trial registries. Filter by geography, therapeutic area, intervention type, phase, and time period to see how trials actually enroll — median patient counts, time-to-enroll, common endpoints, and eligibility criteria trends across cohorts.

Built because clinical trial benchmarking data is locked up in expensive consulting reports or buried in registries that won't give you an API. trialcat makes it accessible to sponsors, investigators, regulatory professionals, and patients.

[trialcat.ai](https://trialcat.ai) *(launching soon)*

---

## Status

🚧 **Early development.** See [roadmap.md](../roadmap.md) for the full phase plan.

---

## What It Does

- **Interactive map** — click a country (or US state) to see aggregate trial data
- **Powerful filters** — therapeutic area, intervention type (drug/biologic/device/behavioral), device class, phase, time period
- **Enrollment stats** — low/median/high patient enrollment per month, average time-to-enroll
- **Natural language insights** *(coming)* — common primary endpoints, typical inclusion/exclusion patterns, cross-region comparisons
- **Free forever for core data**, with optional email signup for deeper analysis

---

## Data Sources

| Source | Status | Notes |
|---|---|---|
| [ClinicalTrials.gov](https://clinicaltrials.gov) | ✅ MVP | Free public API, ~400K+ trials |
| [ISRCTN](https://www.isrctn.com/) | 🔜 v2 | Limited REST API |
| [ANZCTR](https://www.anzctr.org.au/) | 🔜 v2 | Australia/NZ registry |
| [WHO ICTRP](https://www.who.int/ictrp) | 🔜 v2 | Weekly XML downloads |
| [EU CTR / CTIS](https://euclinicaltrials.eu/) | 🔜 v2 | Bulk export ETL |

---

## Tech Stack

- **Backend**: FastAPI (Python 3.12+), SQLite (MVP) → Postgres (if needed)
- **Frontend**: Vanilla HTML/JS + Leaflet.js + OpenStreetMap tiles
- **Container**: Docker + docker-compose
- **Hosting**: Fly.io
- **Rate limiting**: SlowAPI
- **AI features**: OpenAI `gpt-4o-mini` + `text-embedding-3-small`

---

## Local Development

```bash
# Clone
git clone https://github.com/Angiebio/trialcat.git
cd trialcat

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Run with Docker
docker-compose up

# Open http://localhost:8000
```

---

## Contributing

Contributions are welcome — especially from regulatory professionals who know their regional registries best. Open an issue to discuss before starting significant work. PRs should target the `main` branch with clear descriptions.

If you work in clinical trials and want to help shape what the tool shows, open a GitHub Discussion or email angie at therealcat dot ai.

---

## License

MIT. See [LICENSE](LICENSE).

---

## About

trialcat is a project of **[The Real Cat AI Labs](https://therealcat.ai)**, a 501(c)(3) nonprofit dedicated to morally-aligned AI research and education. Proceeds from donations support research on machine cognition and human-AI interaction.

Built with 🔥 by Angie (human) and Flame (AI).
