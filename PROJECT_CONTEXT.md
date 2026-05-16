# PROJECT_CONTEXT.md - Fracttal PRM

> Deep implementation reference for Claude Code sessions.
> Supplements CLAUDE.md - read CLAUDE.md first for project overview, sprint history, and environment setup.
> Last updated: Sprint 3 (RBAC, tenant isolation, field visibility, audit trail delivered)

---

## Table of Contents

1. [API Endpoints](#1-api-endpoints)
2. [Database Schema](#2-database-schema)
3. [Component Structure & Data Flow](#3-component-structure--data-flow)
4. [CI/CD Logic & Skip Rules](#4-cicd-logic--skip-rules)
5. [Error Handling Patterns](#5-error-handling-patterns)
6. [Architectural Decisions](#6-architectural-decisions)

---

## 1. API Endpoints

**Base URL:** `https://fracttal-prm-backend-production.up.railway.app` (live since Sprint 1 closeout)

**Framework:** FastAPI (Python 3.11+)

**CORS:** Configured via `FRONTEND_URL` env var (default: `*`). Must be `*` or explicitly include the Control Centre URL (`https://control-centre-service-production.up.railway.app`). Set `FRONTEND_URL=*` in Railway `fracttal-prm-backend` service variables.

### Public Endpoints

| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| GET | `/` | None | Root info — returns service name + version |
| GET | `/health` | None | Health check — `{status, service, database}`, always 200 (DB unreachable → `database: unreachable`, never 500) |
| POST | `/auth/register` | 10/min per IP | Create user. Body: `{email, password, full_name?}` → 201 `{id, email}`. 409 on duplicate email. |
| POST | `/auth/login` | 10/min per IP | Authenticate. Body: `{email, password}` → 200 `{access_token, token_type, expires_in}`. 401 on bad credentials or inactive account. |
| POST | `/auth/password-reset/request` | None | Always returns 200 `{message: "If that email exists, …"}`. If user exists, generates a UUID reset token with 1h expiry and logs URL to stdout (no email backend yet). |
| POST | `/auth/password-reset/confirm` | None | Body: `{token, new_password}`. 200 on success; 400 if token invalid/used/expired. |

### Bearer-Authenticated Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/logout` | Invalidate caller's token (in-memory blacklist). Returns 200. |
| POST | `/auth/refresh` | Issue a new access token, invalidate the current one. Returns same shape as `/auth/login`. |
| GET | `/auth/me` | Returns `{id, email, role, full_name}` for the authenticated user. |
| GET | `/admin/audit-log` | Paginated audit-log query. Requires `system_admin` (via `require_permission("user_management:read_all")`). Query params: `page`, `page_size` (≤200), `object_type`, `actor_id`, `date_from`, `date_to`. Returns `{total, page, page_size, items}`. |

### JWT Token Spec

- Algorithm: HS256 (signed with `JWT_SECRET` env var)
- Expiry: from `JWT_EXPIRY_HOURS` env var, default 168 (7 days)
- Payload: `{sub: user_id_uuid, email, role, exp}`
- Header: `Authorization: Bearer <token>`
- Logout adds the token to an **in-memory** server-side blacklist — lost on backend restart (see Sprint 3 follow-ups in CLAUDE_HISTORY.md)

> Additional endpoints documented here as sprints deliver them.

---

## 2. Database Schema

### Tables (as of Sprint 3)

| Table | Migration | Purpose |
|---|---|---|
| `users` | `001_create_users_table` | Authenticated users. Columns: `id` (UUID PK), `email` (unique indexed), `hashed_password`, `full_name`, `is_active`, `is_verified`, `role` (string — validated against `UserRole` enum at auth time), `partner_org_id` (UUID, nullable — tenant assignment for partner-side roles), `created_at`, `updated_at`. |
| `password_reset_tokens` | `002_create_password_reset_tokens` | Single-use password reset tokens. Columns: `id` (UUID PK), `token` (unique indexed), `user_id` (FK → users.id), `expires_at`, `used` (bool), `created_at`. 1-hour expiry enforced in handler. |
| `audit_log` | `003_create_audit_log` | Append-only audit trail. Columns: `id` (UUID PK), `timestamp` (indexed), `actor_id` (FK → users.id, indexed), `actor_role`, `action` (dot-notation e.g. `partner_profile.update`), `object_type` (indexed), `object_id` (UUID), `before_state` / `after_state` (JSON), `ip_address`, `notes`. Write via `audit.log_audit_event(...)`; read via `GET /admin/audit-log`. |

**Migration strategy:** Alembic with `alembic upgrade head` as Railway pre-deploy command on `fracttal-prm-backend`.

**Key rules:**
- Every new table requires an Alembic migration — never use SQLAlchemy `create_all()` directly in production
- All migration `upgrade()` functions must be idempotent — use `if_not_exists=True` and existence checks
- When introducing Alembic to an existing database, run `alembic stamp head` first to initialise migration history without running DDL
- Migration files live in `backend/alembic/versions/` — Claude Code reads and modifies them via GitHub Contents API (no local checkout required)
- New migration files committed to the repo are picked up and applied automatically on the next Railway deploy — no manual intervention required

---

## 3. Component Structure & Data Flow

> Populated as frontend components are built.

### Backend (`backend/`)

Flat module layout — all Python source files sit directly in `backend/`. No `src/` subdirectory, no `__init__.py` files. Tests go in `backend/tests/`. Imports are flat: `from models import ...`

**Auth + RBAC dependency pattern (Sprint 3 canonical).** Use these imports for any new router that needs authentication or permission gating:

```python
from auth import get_current_user
from permissions import require_permission, apply_tenant_filter
from field_visibility import filter_sensitive_fields
```

| Need | Use |
|---|---|
| Authenticated route, no permission check | `Depends(get_current_user)` |
| Authenticated + permission required | `Depends(require_permission("resource:action"))` — returns 403 if role lacks permission |
| Partner-tenant scoping on a query | `query = apply_tenant_filter(query, current_user, ModelClass)` — partner roles filtered to own `partner_org_id`, internal roles see all |
| Strip sensitive fields from response | `data = filter_sensitive_fields(model_dict, current_user)` — strips `margin_pct`/`internal_notes`/`cost_price` from partner-side responses |

Permission strings follow `{resource}:{action}` — see `permissions.PERMISSIONS` for the full matrix. Don't duplicate the auth check inside the handler — `require_permission` handles 401 (no token, expired token, unknown role) AND 403 (token valid but role insufficient).

### Frontend (`frontend/src/`)

> Component tree documented here as React components are built.

---

## 4. CI/CD Logic & Skip Rules

### `ci.yml` Job Summary

| Job | Condition | Blocking | What it does |
|-----|-----------|----------|--------------|
| test (3.11, 3.12) | Always | Yes | pytest, skip `tests/e2e/`, upload coverage |
| security | Always | No (`--exit-zero`) | bandit scan on `backend/` |
| sonarcloud | main push only | No (continue-on-error) | Full code analysis |
| playwright | main push only | No (continue-on-error) | E2E against live backend |
| deploy | main push only | No | Railway GraphQL API `serviceInstanceRedeploy` mutation |

### Blocking CI Jobs (will prevent auto-merge)

- `test` matrix jobs (Python 3.11 and 3.12)
- `security` scan (bandit)

### Non-Blocking CI Jobs

- SonarCloud analysis — triggered selectively from Control Centre before TEST/PROD promotion, not on every PR
- Playwright E2E — informational at this stage
- Railway deploy — runs after merge to `main`, not a pre-merge gate

### Railway Deploy (GraphQL API)

Uses `serviceInstanceRedeploy` mutation via `curl` + `jq` — no Railway CLI required (AD-21 pattern from SynPro VSDC):
- Service name: `fracttal-prm-backend` (and `fracttal-prm-frontend` for frontend deploys)
- Railway Project ID: `e5c41b7a-b96c-449d-964f-aba615d4cae0`
- Full API response echoed to CI logs
- Step exits 0 on any error (non-blocking)

**GitHub Secrets required:**

| Secret | Description |
|--------|-------------|
| `PAT_TOKEN` | Personal Access Token (repo + workflow scope) |
| `RAILWAY_TOKEN` | Railway account token |
| `RAILWAY_PROJECT_ID` | `e5c41b7a-b96c-449d-964f-aba615d4cae0` |
| `SONAR_TOKEN` | SonarCloud token (optional until configured) |

### Graceful Skip

If `backend/` or `tests/` directories don't exist yet, test jobs skip without failing. This allows the CI pipeline to be committed before all directories are created.

---

## 5. Error Handling Patterns

### Backend
- Non-2xx responses raise `HTTPException` with appropriate status codes
- All routers are fully self-contained — no cross-directory imports (AD-5)
- Auth dependency: always verify exact function name in `auth.py` before using in any router
- `requirements.txt` is critical — read before writing, never remove packages

### Frontend
- API errors extracted from `error.response.data.detail` for display
- Loading states handled per-component
- JWT token stored in `localStorage` under key `"token"` — consistent across all components

### CORS
- `FRONTEND_URL=*` in Railway — required for Control Centre proxy calls to work
- `allow_credentials` must be `False` when `FRONTEND_URL=*` (CORS spec requirement)
- Bearer token auth (`Authorization: Bearer ...`) works correctly without `allow_credentials=True`

> Additional patterns documented here as they emerge sprint by sprint.

---

## 6. Architectural Decisions

These are conscious design choices — not defaults or accidents. Understanding the *why* prevents future sessions from accidentally reversing them.

---

### AD-1 · Backend uses flat module layout — no packages, no `src/` subdirectory

**Decision:** All Python source files sit directly in `backend/`. No `src/` subdirectory, no `__init__.py` files. Imports are flat: `from models import ...`

**Why:** The backend is a focused FastAPI service. A package hierarchy adds indirection without benefit. The flat layout also matches how Railway's Procfile resolves modules at startup.

**Do not:** Create `src/` subdirectories or `__init__.py` files inside `backend/`.

---

### AD-2 · No git CLI — all GitHub operations use the REST API

**Decision:** Claude Code creates branches, commits files, and opens PRs entirely via the GitHub Contents API and Git Trees API over HTTP. No `git` binary required.

**Why:** Claude Code works anywhere Python and HTTP are available. Base64 encoding handles binary-safe file content. The SHA-based update protocol replaces the need for local refs.

**Consequence:** File updates require the current blob SHA — always fetch the existing SHA before updating a file. The `read_file` step before every `stage_file` is mandatory.

---

### AD-3 · Feature branches are always recreated from `main`, never updated in place

**Decision:** Before creating a branch, delete any existing branch with the same name and recreate it fresh from the latest `main` SHA.

**Why:** Starting fresh from `main` guarantees a clean, minimal diff and eliminates merge conflicts entirely.

**Consequence:** Any work committed to a branch that has not yet been merged to `main` will be lost if Claude Code retriggers for the same ticket. The branch is ephemeral — `main` is the source of truth.

---

### AD-4 · Jira sprints tracked via fix versions, not native Agile sprints

**Decision:** Tickets are assigned to sprints using Jira's `fixVersions` field. Sprint IDs map to Jira versions pre-created before each sprint.

**Why:** Fix versions are simpler to create and query programmatically and don't require board access configuration.

**Consequence:** A dual JQL query is always needed: `fixVersion = {fix_id} OR sprint = {native_id}`. Neither field alone is reliable. Always pre-create the fix version manually and verify before sprint setup.

---

### AD-5 · `backend/` is a self-contained service — no cross-directory imports at runtime

**Decision:** Every Python file in `backend/` must import only from stdlib, pip-installed packages in `backend/requirements.txt`, and other files within `backend/` itself.

**Why:** Railway deploys `backend/` as a standalone service. No other project directories exist on the Railway filesystem at runtime. Cross-directory imports crash the service at startup silently until the first request hits the broken router.

**Do not:** Use `sys.path.insert` to import from parent directories — it does not work in Railway. Inline the logic as local helpers instead.

---

### AD-6 · Jira API calls proxied through the shared SynPro VSDC backend

**Decision:** The Control Centre never calls Jira directly for Fracttal PRM data — all Jira requests go through `/proxy/jira/*` on the shared SynPro VSDC UAT backend (`https://synpro-virtual-dev-team-production.up.railway.app`), with `product_id` identifying the Fracttal PRM product record.

**Why:** Jira's REST API does not set permissive CORS headers, blocking direct browser-to-Jira calls. The shared proxy pattern avoids duplicating proxy infrastructure across products.

**Consequence:** The SynPro VSDC backend must be running and accessible for Fracttal PRM's Control Centre data to load. The Fracttal PRM product record in the SynPro VSDC database must have correct credentials.

**Do not:** Add direct Jira calls to the Control Centre frontend. The proxy pattern is load-bearing.

---

### AD-7 · SonarCloud and Railway deploy are not merge-gate checks

**Decision:** Both run with `continue-on-error: true` in `ci.yml` and are excluded from the auto-merger's blocking check list. Only unit tests (Python 3.11 + 3.12) and bandit security scan are blocking.

**Why:** SonarCloud is triggered selectively from the Control Centre before promoting a build to TEST or PROD — running it on every feature-branch PR would be redundant and costly. Railway deploy only runs after merge to `main`, so it cannot be a pre-merge gate.

**Do not:** Add SonarCloud or Railway deploy as blocking conditions in any merge-readiness logic.

---

## Appendix — Environment Variables

### Required for Backend (Railway `fracttal-prm-backend` service variables)

| Variable | Value | Description |
|----------|-------|-------------|
| `DATABASE_URL` | Auto-provisioned | PostgreSQL connection string |
| `JWT_SECRET` | Generate strong random string | JWT signing secret — never change after first deploy |
| `JWT_EXPIRY_HOURS` | `168` | Token lifetime (7 days) |
| `FRONTEND_URL` | `*` | CORS allowed origins |
| `ANTHROPIC_API_KEY` | From console.anthropic.com | Claude API key |
| `JIRA_BASE_URL` | `https://synproconsulting.atlassian.net` | Jira instance URL |
| `JIRA_EMAIL` | `synproconsulting@gmail.com` | Jira service account email |
| `JIRA_API_TOKEN` | Rotate at id.atlassian.com | Jira API token |
| `JIRA_PROJECT_KEY` | `FPRM` | Jira project key |
| `JIRA_BOARD_ID` | `67` | Jira Agile board ID |

### Required for CI (GitHub Secrets on `Fracttal-PRM` repo)

| Secret | Description |
|--------|-------------|
| `PAT_TOKEN` | Personal Access Token (repo + workflow scope) |
| `RAILWAY_TOKEN` | Railway account token (personal, not project-scoped) |
| `RAILWAY_PROJECT_ID` | `e5c41b7a-b96c-449d-964f-aba615d4cae0` |
| `SONAR_TOKEN` | SonarCloud token (add when SonarCloud is configured) |
