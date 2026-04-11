# data/

Runtime data directory. Most contents are gitignored because they're regenerable from the CT.gov API.

## Structure

```
data/
├── trialcat.db        # SQLite database (gitignored)
├── raw/               # Raw API responses cache (gitignored)
└── seed/              # Small sample data for tests (committed)
```

To rebuild the database from scratch:

```bash
python -m backend.app.etl.refresh_all
```
