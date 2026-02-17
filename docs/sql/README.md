# Database DDL

Generated DDL files for SIPM.

## Files

- `docs/sql/schema_oracle_ta.sql`: Oracle DDL for TAConnection deployments.
- `docs/sql/migrations/2026-02-14_sow_content_to_clob.sql`: One-time upgrade for existing DBs to widen `TB_TA_PM_SOW_DOCUMENTS.CONTENT` to `CLOB`.
- `docs/sql/migrations/2026-02-14_checklist_title_to_clob.sql`: One-time upgrade for existing DBs to widen `TB_TA_PM_CHECKLIST_ITEMS.TITLE` to `CLOB`.

## Regenerate

From repo root:

```bash
python3 scripts/generate_schema_ddl.py --dialect oracle --ta-mode --output docs/sql/schema_oracle_ta.sql
```

## Notes

- Oracle output uses no schema qualifier and names tables as `TB_TA_PM_*`.
- The `--ta-mode` flag is kept for command compatibility; table naming is now environment-agnostic.
- For TAConnection deployments, use `schema_oracle_ta.sql`.
- If your DB was created before 2026-02-14, run both migration scripts above once to prevent ORA-12899 on long SOW/checklist draft saves.
