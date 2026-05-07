# SIPM

SIPM is a FastAPI backend with a vanilla ES module frontend under `src/main`.

## Run Locally
```bash
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
cd src/main
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/project-manager/`.

Runtime details, environment rules, readiness checks, and operations notes live in `src/main/README.md`.

## Validate
Backend:
```bash
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
cd src/main
pytest -q -s test
```

Frontend:
```bash
npm install
npm run lint:ui
npm run test:ui
npm run test:ui:smoke
```

Repo quality helpers:
```bash
python scripts/check_route_module_test_mapping.py
```

## Review And Operations
- Contribution rules: `CONTRIBUTING.md`
- Canonical Oracle schema: `docs/sql/schema_oracle_ta.sql`
- First-time global admin bootstrap SQL: `docs/sql/first_time_global_admin.sql`

Deployment manifests, ingress, secret injection, log shipping, dashboards, and alert routing are external platform responsibilities.
