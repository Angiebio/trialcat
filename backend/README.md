# backend/

FastAPI application for trialcat.

## Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Pydantic settings from .env
│   ├── db.py                # SQLAlchemy + SQLite connection
│   ├── models/              # SQLAlchemy models
│   ├── routes/              # API route handlers
│   ├── services/            # Business logic (CT.gov client, aggregators)
│   └── schemas/             # Pydantic request/response models
└── tests/                   # pytest suite
```

See [../roadmap.md](../../roadmap.md) for phased build plan.
