# Remove Reverse Proxy Authentication Plan

## Branch

`remove-reverse-proxy-auth`

## Objective

Reverse out the unstable company reverse-proxy authentication path and return SIPM to local application-managed authentication for the production hotfix. The target state is the pre-reverse-proxy behavior from the commit before `80f6ead` (`reverse proxy setup`): users authenticate against the SIPM `users` table with bcrypt password hashes, JWT access/refresh cookies, account lockout, and the existing temporary-password reset flow.

SSO should remain out of scope for this branch. The goal is a safe rollback to known local auth behavior that can ship quickly, then revisit SSO separately.

## Current State

The repo already retains most local-auth primitives:

- `src/main/backend/app/models/identity.py` has `users.password_hash`, `failed_attempts`, `locked_until`, `temp_password_hash`, `temp_password_expires_at`, `force_password_reset`, and `password_changed_at`.
- `src/main/backend/app/auth/auth.py` has bcrypt hashing/verification, JWT creation/validation, cookie handling, token TTL configuration, and local self-registration controls.
- `src/main/backend/app/routes/auth.py` still has `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/reset-password`, `/auth/logout`, and `/auth/me`, but local routes are disabled whenever proxy auth is enabled.
- `src/main/backend/app/services/password_reset.py` supports admin-issued temporary passwords and user completion through `/auth/reset-password`.
- `src/main/backend/app/routes/users.py` exposes admin password reset request endpoints.
- The reverse-proxy-specific path was introduced in `80f6ead` through `src/main/backend/app/auth/proxy_auth.py`, route guards, startup/readiness validation, frontend portal messaging, and tests.

## Implementation Strategy

Use the pre-`80f6ead` local-auth behavior as the baseline, but do not blindly revert the whole commit. Preserve unrelated hardening added after that commit, including structured request logging, frontend bundle checks, DB warmup/keepwarm behavior, security headers, API token/service-account functionality, and production readiness changes.

## Backend Work

1. Remove reverse-proxy auth as an active authentication mechanism.

   - Stop importing `proxy_auth_enabled`, `proxy_identity_from_request`, `provision_proxy_user`, and `portal_auth_disabled_exception` in `src/main/backend/app/routes/auth.py`.
   - Remove `_ensure_local_auth_routes_enabled()` and calls from `/register`, `/login`, and `/reset-password`.
   - Keep local routes always available, controlled only by `SIPM_ALLOW_SELF_REGISTER` where registration is concerned.
   - Remove proxy auto-provisioning behavior from auth flow if it exists outside `routes/auth.py`.

2. Remove proxy validation from startup/readiness.

   - Stop importing `validate_proxy_auth_configuration` and `maybe_inject_dev_proxy_headers` in `src/main/backend/main.py`.
   - Remove the `proxy_auth` readiness check.
   - Remove ASGI middleware or scope mutation that injects dev proxy headers, if present.
   - Keep `validate_auth_configuration()` as the local-auth readiness gate.

3. Decide what to do with `src/main/backend/app/auth/proxy_auth.py`.

   - Preferred for a clean hotfix: delete it if no imports remain.
   - Acceptable fallback: leave it unused for one release if deletion creates avoidable test churn, but add a follow-up cleanup issue.

4. Preserve local session behavior.

   - `/auth/login` should normalize SOEID, verify bcrypt password hash, enforce inactive-user rejection, enforce lockout after `MAX_FAILED_ATTEMPTS`, clear failed attempts on success, set `last_login_at`, issue access/refresh cookies, and set active-space cookie.
   - `/auth/refresh` should validate refresh JWT, reject inactive/missing/locked users, reject revoked sessions via `ensure_token_not_revoked`, and reissue cookies.
   - `/auth/logout` should clear auth and active-space cookies.
   - `/auth/reset-password` should accept SOEID, temporary password, new password, and confirmation, then clear active cookies after password update.

5. Confirm admin user management still supports local auth.

   - Keep admin-created users backed by `password_hash`.
   - Keep `/users/{user_id}/password-reset-request` and `/users/by-soeid/{soeid}/password-reset-request` for issuing temporary passwords.
   - Confirm service-account users cannot break interactive login expectations.

## Frontend Work

1. Restore local login/register/reset UI from the pre-`80f6ead` implementation.

   - Restore `performLogin()` and `performRegister()` in `src/main/ui/js/shell/session.js`.
   - Restore auth tab handling with `setAuthMode("login")`, `setAuthMode("register")`, and the reset-password navigation.
   - Restore login form submit behavior calling `/auth/login`.
   - Restore register form submit behavior calling `/auth/register`.
   - Restore reset form behavior calling `/auth/reset-password`.
   - Restore local session-expired messaging: users should be prompted to sign in again, not to access the company portal.

2. Restore login/register/reset markup if it was simplified for portal auth.

   - Review `src/main/ui/index.html` against `80f6ead^`.
   - Reintroduce fields for SOEID, display name, password, temporary password, new password, and confirmation where needed.
   - Keep current CSS and shell layout improvements unless they conflict with local auth UX.

3. Keep authenticated app behavior unchanged.

   - Continue using cookie-based credentials with `fetch(..., credentials: "include")`.
   - Continue refreshing sessions through `/auth/refresh`.
   - Continue passing `X-Space-Id` during refresh and API calls.

## Configuration Work

1. Remove reverse-proxy env requirements and examples.

   - Delete or deprecate `SIPM_PROXY_AUTH_ENABLED`.
   - Delete or deprecate `SIPM_PROXY_AUTH_SOEID_HEADER`.
   - Delete or deprecate `SIPM_PROXY_AUTH_NAME_HEADER`.
   - Delete or deprecate `SIPM_PROXY_AUTH_DEV_MOCK_ENABLED`.
   - Delete or deprecate `SIPM_PROXY_AUTH_DEV_MOCK_SOEID`.
   - Delete or deprecate `SIPM_PROXY_AUTH_DEV_MOCK_NAME`.

2. Confirm required local-auth env for prod.

   - `ENV=prod` or equivalent.
   - `SIPM_SECRET_KEY` set to a strong non-default value.
   - `SIPM_SECURE_COOKIES=true`.
   - `SIPM_COOKIE_SAMESITE` set intentionally, likely `strict` unless cross-site deployment requires `none` with secure cookies.
   - `SIPM_ACCESS_MINUTES`, `SIPM_REFRESH_MINUTES` or `SIPM_REFRESH_DAYS`, and reset TTLs set to production values.
   - `SIPM_ALLOW_SELF_REGISTER=false` unless explicitly approved.

## Database Work

No schema migration is expected for the rollback because the `users` table already contains the local-auth columns. Validate prod data before release:

- Confirm every interactive user has a non-empty `password_hash`.
- Confirm initial admin access exists before disabling proxy auth.
- Confirm any proxy-provisioned users either already have usable local passwords or receive admin-issued temporary passwords.
- Confirm `external_id` can remain populated harmlessly; do not remove it during the hotfix unless there is a concrete collision or security issue.

## User Screen Scope

Build or verify an admin-facing user screen that supports local-auth operations:

- List users with SOEID, display name, email, role, active status, service-account flag, team tag, capacity, and last login.
- Create a local user with SOEID, display name, and temporary password flow rather than exposing a shared default password.
- Edit display name, team tag, capacity, active status, and role where permitted.
- Trigger password reset request and display the one-time temporary password once.
- Lock/unlock or clear failed login attempts if not already exposed.
- Deactivate users without deleting audit history.
- Clearly separate interactive users from service accounts.

## Login Screen Scope

Restore a first-class local login screen:

- SOEID field.
- Password field.
- Submit action against `/auth/login`.
- Error handling for invalid credentials, inactive user, locked account, password reset required, and expired session.
- Link to reset-password screen for temporary-password completion.
- Optional register tab only when self-registration is enabled or acceptable for the environment.

## Password Reset Scope

Use the existing admin-issued temporary password flow for the production rollback:

- Admin requests reset through user screen.
- Backend generates a temporary password, stores only its bcrypt hash, sets `force_password_reset=true`, clears lockout state, and invalidates existing sessions by updating `password_changed_at`.
- User visits `/reset-password`.
- User enters SOEID, temporary password, new password, and confirmation.
- Backend verifies temporary password and expiry, updates `password_hash`, clears temp password fields, clears force-reset flag, and clears auth cookies.
- User signs in with the new password.

Out of scope for the hotfix:

- Email delivery for reset links.
- Self-service forgotten-password without admin involvement.
- SSO or reverse-proxy header trust.

## Test Plan

1. Backend unit/API tests.

   - Local login succeeds with valid SOEID/password.
   - Login fails with invalid password and increments failed attempts.
   - Account locks after configured failed attempts.
   - Inactive users cannot log in.
   - Forced-reset users cannot refresh or continue normal session.
   - Refresh reissues cookies and preserves active-space context.
   - Logout clears auth cookies.
   - Admin reset issues a temp password and stores only a hash.
   - Reset with temp password updates the password and clears force-reset state.
   - Reverse-proxy env flags no longer disable local auth.

2. Frontend unit tests.

   - Login form calls `/auth/login` with SOEID/password.
   - Register form calls `/auth/register` only when enabled in UI.
   - Reset form calls `/auth/reset-password` with the expected payload.
   - Session-expired messaging references signing in again, not the company portal.

3. E2E smoke tests.

   - Fresh unauthenticated user sees login UI.
   - User can log in, navigate authenticated routes, refresh session, and log out.
   - Admin can issue reset and user can complete reset.
   - App works under `APP_CONTEXT_PATH=/project-manager`.

4. Release validation.

   - Run backend tests from `src/main/test`.
   - Run frontend unit tests.
   - Run auth E2E smoke if browser dependencies are available.
   - Run startup/readiness locally with production-like auth env and proxy env unset.

## Release Plan

1. Merge rollback branch into the production release branch.
2. Set production env to local-auth mode by removing proxy auth env vars and confirming local-auth secrets.
3. Pre-provision or reset passwords for required users before cutover.
4. Deploy to a non-prod environment that matches the production context path.
5. Validate login, refresh, logout, reset, admin reset, and user-management operations.
6. Deploy to production.
7. Keep reverse-proxy/SSO follow-up work on a separate branch after production stabilizes.

## Risks

- Users auto-provisioned by proxy may not know a local password; mitigate with admin-issued temporary passwords before cutover.
- If `SIPM_SECRET_KEY` changes unexpectedly, existing JWT cookies become invalid; acceptable during rollback but should be communicated.
- Self-registration must stay disabled in production unless explicitly approved.
- Leaving unused proxy code can confuse future maintenance; delete it if test impact is manageable.
- Browser tests may still encode portal-auth copy; update them with the UI changes.

## Acceptance Criteria

- Proxy headers are no longer required for authentication.
- Local `/auth/login`, `/auth/register`, `/auth/refresh`, `/auth/reset-password`, `/auth/logout`, and `/auth/me` behave consistently with the pre-`80f6ead` local-auth implementation.
- Production readiness no longer fails due to proxy-auth configuration.
- Login, reset-password, and user-management screens support the local auth workflow.
- Backend, frontend, and auth E2E tests cover the restored local-auth path.
- The only planned SSO work remaining is explicitly deferred to a future branch.
