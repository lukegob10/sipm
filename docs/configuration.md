# Configuration

This project uses canonical environment variable names (one name per setting).

## Minimal Runtime Variables

Set these for normal deployment:

- `ENV`: `dev`, `uat`, or `prod` (drives `TAConnection(env=...)`).
- `TA_<ENV>_USER`: Oracle username for the selected `ENV`.
- `TA_<ENV>_PASSWORD`: Oracle password for the selected `ENV`.
- `TA_<ENV>_DSN`: Oracle DSN for the selected `ENV` (example: `host:1521/FREEPDB1`).
- `SIPM_SECRET_KEY`: JWT signing key.
- `SIPM_SECURE_COOKIES`: `true` for HTTPS deployments.

## App Startup

- `SIPM_ENV_OVERRIDE` (default: `true`): If `true`, values from `.env` can override existing process env vars.
- `SIPM_DISABLE_STARTUP` (default: `false`): Skip startup init hook.
- `SIPM_DISABLE_THREADPOOL` (default: `false`): Disable AnyIO threadpool (mainly for constrained test/sandbox runs).
- `SIPM_KEEPALIVE_TASK` (default: `false`): Enable keepalive task.

## Database Pooling (TAConnection + SQLAlchemy)

- `SIPM_DB_POOL_SIZE` (default: `5`): Number of persistent pooled DB connections.
- `SIPM_DB_MAX_OVERFLOW` (default: `10`): Extra temporary connections beyond pool size.
- `SIPM_DB_POOL_TIMEOUT_SECONDS` (default: `30`): Wait time for an available pooled connection.
- `SIPM_DB_POOL_RECYCLE_SECONDS` (default: `1800`): Max connection age before recycle.
- `SIPM_DB_POOL_PRE_PING` (default: `true`): Poll/ping connection health before checkout.

## Authentication

- `SIPM_ACCESS_MINUTES` (default: `60`): Access token lifetime in minutes.
- `SIPM_REFRESH_MINUTES` (default: `60`): Refresh token lifetime in minutes.
- `SIPM_RESET_MINUTES` (default: `30`): Password reset token lifetime in minutes.
- `SIPM_COOKIE_SAMESITE` (default: `lax`): Cookie SameSite policy.
- `SIPM_BCRYPT_ROUNDS` (default: `12`): Password hashing cost.
- `DOMAIN_NAME` (default: `citi.com`): Domain used to synthesize user emails from SOEID.

## GenAI Core

- `GENAI_MODEL` (default: `gemini-2.5-flash`): Model name.
- `GENAI_API_KEY`: API key for direct API-key auth mode.
- `GENAI_USE_VERTEXAI` (default: `false`): Enable Vertex mode.
- `GENAI_PROJECT`: Required when `GENAI_USE_VERTEXAI=true`.
- `GENAI_LOCATION` (default: `us-central1`): Vertex location.
- `GENAI_DEBUG` (default: `false`): Debug logging for LLM calls.
- `AI_DEBUG_TRACE` (default: `false`): Trace logging for orchestration/LLM path.

## AI Limits / Performance

- `AI_MAX_STEPS` (default: `30`): Max orchestrator steps.
- `AI_MAX_TOOL_CALLS` (default: `12`): Max tool calls per orchestration.
- `AI_MAX_CONTEXT_CALLS` (default: `4`): Max context calls per orchestration.
- `AI_MODEL_TIMEOUT_SECONDS` (default: `60`): Model call timeout.
- `AI_WALL_TIMEOUT_SECONDS` (default: uses `AI_MODEL_TIMEOUT_SECONDS`): End-to-end wall timeout.
- `AI_TOOL_CACHE_TTL_SECONDS` (default: `0`): Tool cache TTL (`0` disables).
- `AI_DIGEST_WRITE_ENABLED` (default: `true`): Enable digest-table writes.
- `SIPM_SMART_CACHE_ENABLED` (default: `true`): Enable scoped smart cache.
- `SIPM_SMART_CACHE_MAX_ENTRIES` (default: `4096`): Max smart-cache entries.

## Paths / Content

- `SIPM_DOC_STORAGE` (default: `data/external_docs`): Document upload storage root.
- `SIPM_PROMPTS_DIR`: Override prompts directory.
- `SIPM_CONTRACTS_DIR`: Override contracts directory.
- `SIPM_APP_GUIDE_PATH`: Override app guide markdown file.
- `SIPM_TEMPLATES_DIR`: Override templates directory.

## Optional Seeding / Identity Helpers

- `SAMPLE_SEED` (default: `false`): Enable sample data seeding.
- `SIPM_USER_SOEID`: Explicit default user SOEID.

## Test-Only

- `SIPM_TEST_DATABASE_URL`: Database URL used by test fixtures.
- `PYTEST_CURRENT_TEST`: Set by pytest.

No fallback TA variable aliases are used by the local shim; use only `TA_<ENV>_*`.
