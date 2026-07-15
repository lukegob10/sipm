# Agent Human-Delegated Review Security Boundary

## Decision

Human-delegated approval and rejection use a 10-minute delegated bearer token issued from an existing authenticated SIPM human session. They do not use the automation service account, a statement in a prompt, or a service-account API token. No database change is required.

## Principal Separation

- Automation service accounts may discover, read, validate, submit, poll, cancel their own requests, and never approve or reject.
- Human delegates authenticate with a delegated token tied to an active, non-revoked human login session.
- The user must hold the required role in the explicitly supplied `X-Space-Id` space.
- Normal cookie-based review remains available through the existing interactive endpoints.

## Confirmation Binding

Delegated review uses separate `delegated-approve` and `delegated-reject` endpoints. The body must repeat:

- The exact change-request ID being confirmed.
- The `updated_at` value observed when the immutable diff was retrieved.

The server rejects ID mismatches, changed request versions, non-pending requests, cross-space access, and service-account credentials. Approval then revalidates optimistic concurrency and applies the patch atomically as the human user.

## Credential Lifecycle

The cookie-authenticated `POST /api/agent/delegated-session` endpoint issues a signed token with type `delegated`, a 10-minute lifetime, and the existing auth-session ID. Delegated routes validate token type, active user, password revocation, session revocation, and session idle/absolute limits. The agent therefore does not rely on ambient browser cookies after issuance.

## Replay And Confused-Deputy Controls

- A confirmation is bound to one request ID and version.
- Terminal requests cannot be reviewed again.
- Space membership is checked at review time.
- Audit rows identify the human reviewer and affected work items.
- Service-account self-approval remains impossible even if it knows the confirmation fields.

## Residual Risk

Human access tokens are not consent grants specific to one change request, so callers must protect them as full session credentials. Confirmation fields bind each review action to one request and version. If the product later requires one-time consent grants, that requires a separate security design and likely a database change through the database change gate.
