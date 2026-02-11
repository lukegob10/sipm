# Database DDL

Generated DDL files for SIPM.

## Files

- `docs/sql/schema_oracle_ta.sql`: Oracle DDL for TAConnection deployments.
- `docs/sql/schema_sqlite.sql`: SQLite DDL for local/non-TA environments.

## Regenerate

From repo root:

```bash
python3 scripts/generate_schema_ddl.py --dialect oracle --ta-mode --output docs/sql/schema_oracle_ta.sql
python3 scripts/generate_schema_ddl.py --dialect sqlite --output docs/sql/schema_sqlite.sql
```

## Notes

- Oracle output uses no schema qualifier and names tables as `TB_TA_PM_*`.
- The `--ta-mode` flag is kept for command compatibility; table naming is now environment-agnostic.
- For TAConnection deployments, use `schema_oracle_ta.sql`.
