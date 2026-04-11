"""ETL — fetch CT.gov data, parse it, put it in the database.

This package is the orchestrator. It imports from `services` (which knows
how to fetch and parse) and `models` (which knows how to persist). The ETL
layer itself just wires them together and manages transactions.

Keep ETL scripts idempotent — running them twice should produce the same
database state, not duplicated rows. Every upsert checks for existing
records by natural key (NCT ID for trials, MeSH ID or term for conditions).
"""
