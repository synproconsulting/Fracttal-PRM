# PROJECT_CONTEXT.md - Fracttal PRM

> Deep implementation reference for Claude Code sessions.
> Supplements CLAUDE.md - read CLAUDE.md first for project overview, sprint history, and environment setup.
> Last updated: Sprint 5 (Partner registration & onboarding — public application form, draft token pattern, internal review queue)

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
| POST | `/auth/register` | 10/min per IP | Create user with role `partner_user` (hardcoded — external users cannot self-elevate). Body: `{email, password, full_name?}` → 201 `{id, email}`. 409 on duplicate email. |
| POST | `/auth/login` | 10/min per IP | Authenticate. Body: `{email, password}` → 200 `{access_token, token_type, expires_in}`. 401 on bad credentials or inactive account. |
| POST | `/auth/password-reset/request` | None | Always returns 200 `{message: "If that email exists, …"}`. If user exists, generates a UUID reset token with 1h expiry and logs URL to stdout (no email backend yet). |
| POST | `/auth/password-reset/confirm` | None | Body: `{token, new_password}`. 200 on success; 400 if token invalid/used/expired. |
| POST | `/auth/accept-invite` | None | Body: `{token, password, full_name?}` → 201 `{access_token, token_type, expires_in, user}`. Creates a User with role + partner_org_id from the invite, marks invite accepted_at. 404 unknown token, 400 expired/already-accepted, 409 email-already-registered. |
| GET | `/config/partner-categories` | None | List active partner categories — public so the registration form can render. Returns `{items: [{id, code, display_name, deal_reg_sla_hours, max_discount_pct, monthly_fee_usd, ...}]}`. |
| POST | `/applications` | None | Create a draft partner application. Body: `{applicant_email, ...optional fields}` → 201 `{id, draft_token}`. The returned token (30-day expiry) authorises subsequent PATCH/submit/document calls — see AD-11. |
| GET | `/applications/{id}` | None / Bearer | Fetch an application. Public via `?draft_token=...`; internal users with `partner_application:read_all` (channel_manager+) can access any application via JWT. 401 if neither is supplied. |
| PATCH | `/applications/{id}` | None | Public draft update via `?draft_token=...`. Only writable fields are mutated. 400 if status ∉ {draft, info_required}; 403 on bad token; 410 if draft expired. |
| POST | `/applications/{id}/submit` | None | Public submit via `?draft_token=...`. Validates `legal_name`, `applicant_email`, `applicant_name`, `terms_accepted`. On success sets `status=submitted` and `submitted_at=now`. Audit logged as `partner_application.submitted` with `actor=None`. |
| POST | `/applications/{id}/documents` | None | Public document metadata upload via `?draft_token=...`. Body: `{document_type, document_name, file_path, file_size_bytes?, mime_type?}`. Actual file storage is pending — only metadata is persisted today. |

### Bearer-Authenticated Endpoints

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| POST | `/auth/logout` | any | Invalidate caller's token (in-memory blacklist). Returns 200. |
| POST | `/auth/refresh` | any | Issue a new access token, invalidate the current one. Returns same shape as `/auth/login`. |
| GET | `/auth/me` | any | Returns `{id, email, role, full_name}` for the authenticated user. |
| GET | `/admin/audit-log` | `user_management:read_all` (system_admin) | Paginated audit-log query. Query params: `page`, `page_size` (≤200), `object_type`, `actor_id`, `date_from`, `date_to`. Returns `{total, page, page_size, items}`. |
| GET | `/partners` | `partner_organization:read_all` (internal) | List partner organizations. Query: `skip`, `limit` (≤200). Returns `{total, skip, limit, items}`. |
| GET | `/partners/{id}` | any (tenant-scoped) | Get one partner. Partner-side users 403 unless the id matches their own `partner_org_id`. |
| POST | `/partners` | `partner_organization:create` (channel_ops_admin, system_admin) | Create partner. Required: `legal_name`, `program_type`, `partner_category`. Audit logged. |
| PATCH | `/partners/{id}` | channel_ops_admin / system_admin (any) or partner_admin (own only) | Update partner. `id` and `created_at` are immutable. Audit logged. |
| GET | `/partners/{id}/documents` | any (tenant-scoped) | List documents for the partner. |
| POST | `/partners/{id}/documents` | any (tenant-scoped) | Upload document metadata. Required: `document_type`, `document_name`, `file_path`. `proof_of_fiscal_domicile` rejected if `expiry_date < today - 90d`. Audit logged as `partner_document.upload`. |
| PATCH | `/partners/{id}/documents/{doc_id}` | internal roles only | Review/update status, review_notes, expiry_date. Status change is logged as `partner_document.status_change`. |
| POST | `/partners/{id}/users/invite` | partner_admin (own) / channel_ops_admin / system_admin | Generate a 72h invite token. Body: `{email, invited_role}` where invited_role ∈ {`partner_user`, `partner_admin`}. Audit `partner_user.invite_sent`. |
| GET | `/partners/{id}/users` | any (tenant-scoped) | List users where `partner_org_id == {id}`. |
| PATCH | `/partners/{id}/users/{user_id}` | partner_admin (own) / channel_ops_admin / system_admin | Disable/enable (`is_active`), role change (`partner_user` ↔ `partner_admin`), update `full_name`. Each change audited (`partner_user.disabled` / `partner_user.enabled` / `partner_user.role_changed`). |
| GET | `/partners/{id}/activities` | any (tenant-scoped, internal-filtered) | List activities. Partner-side users only see `is_internal=False`. |
| POST | `/partners/{id}/activities` | internal roles only (channel_manager+) | Create activity. Required: `activity_type`, `title`. `is_internal` defaults True. Audit `partner_activity.create`. |
| PATCH | `/partners/{id}/activities/{activity_id}` | creator OR channel_ops_admin / system_admin | Update activity. Audit `partner_activity.update`. |
| POST | `/config/partner-categories` | `system_config:update_all` (channel_ops_admin, system_admin) | Create a new partner category. |
| GET | `/config/commission-structures` | internal roles only | List all commission structures across categories. |
| PATCH | `/config/commission-structures/{id}` | `system_config:update_all` | Update commission_pct / subpartner_uplift_pct / applies_to_upsell / notes. Audit logged. |
| GET | `/applications` | `partner_application:read_all` (channel_manager, channel_ops_admin, system_admin) | Paginated application list. Query: `status` (comma-separated to filter multiple), `skip`, `limit` (≤200). Returns `{total, skip, limit, items}` ordered by `submitted_at` desc. |

### JWT Token Spec

- Algorithm: HS256 (signed with `JWT_SECRET` env var)
- Expiry: from `JWT_EXPIRY_HOURS` env var, default 168 (7 days)
- Payload: `{sub: user_id_uuid, email, role, exp}`
- Header: `Authorization: Bearer <token>`
- Logout adds the token to an **in-memory** server-side blacklist — lost on backend restart (see Sprint 3 follow-ups in CLAUDE_HISTORY.md)

> Additional endpoints documented here as sprints deliver them.

---

## 2. Database Schema

### Tables (as of Sprint 5)

| Table | Migration | Purpose |
|---|---|---|
| `users` | `001_create_users_table` (+ FK added in `004`) | Authenticated users. Columns: `id` (UUID PK), `email` (unique indexed), `hashed_password`, `full_name`, `is_active`, `is_verified`, `role` (string — validated against `UserRole` enum at auth time), `partner_org_id` (UUID, nullable, FK → partner_organizations.id), `created_at`, `updated_at`. FK constraint `fk_users_partner_org_id` added in migration 004. |
| `password_reset_tokens` | `002_create_password_reset_tokens` | Single-use password reset tokens. Columns: `id` (UUID PK), `token` (unique indexed), `user_id` (FK → users.id), `expires_at`, `used` (bool), `created_at`. 1-hour expiry enforced in handler. |
| `audit_log` | `003_create_audit_log` (+ `009` makes `actor_id` nullable) | Append-only audit trail. Columns: `id` (UUID PK), `timestamp` (indexed), `actor_id` (FK → users.id, **nullable since 009 for anonymous events**), `actor_role` (`"anonymous"` when actor is None), `action` (dot-notation e.g. `partner_profile.update`), `object_type` (indexed), `object_id` (UUID), `before_state` / `after_state` (JSON), `ip_address`, `notes`. Write via `audit.log_audit_event(...)`; read via `GET /admin/audit-log`. |
| `partner_organizations` | `004_create_partner_organizations` | Central partner record. Columns: `id` (UUID PK), `legal_name` (not null), `dba_name`, `website`, `hq_address` (JSONB), `phone`, `email`, `program_type` (ENUM distributor/subpartner), `partner_category` (ENUM master/promotor/reseller), `parent_partner_id` (FK self-ref, nullable), `tier` (ENUM registered/silver/gold, nullable), `territory`/`industries`/`authorized_offerings`/`delivery_capabilities` (JSONB), `status` (ENUM applicant/active/suspended/inactive/terminated), `monthly_fee_status` (ENUM current/overdue/waived), `contract_start_date`, `contract_end_date`, `auto_renew` (bool default true), `certification_expiry_date`, `hubspot_company_id`, `created_at`, `updated_at`. |
| `partner_profiles` | `004_create_partner_organizations` | Onboarding questionnaire. Columns: `id`, `partner_org_id` (FK unique), `year_established`, `employee_count`, `annual_revenue`, `shareholders` (JSONB), `cmms_experience` + `cmms_experience_description`, `other_software_products`, `sales_marketing_strategy`, `technical_support_team` + `technical_support_description`, `implementation_services` + `implementation_description`, `partnership_goals`, `market_growth_plan`, `additional_info`, `profile_completeness_pct` (default 0), `updated_at`. |
| `partner_documents` | `005_create_partner_documents` | Legal/compliance documents. Columns: `id`, `partner_org_id` (FK), `document_type` (ENUM: id_legal_representative, power_of_attorney, articles_of_incorporation, beneficial_owners_list, fiscal_id, proof_of_fiscal_domicile, bank_certificate, nda, insurance, other), `document_name`, `file_path`, `file_size_bytes`, `mime_type`, `uploaded_by_user_id` (FK users), `uploaded_at`, `expiry_date`, `status` (ENUM pending_review/approved/rejected/expired, default pending_review), `review_notes`, `reviewed_by_user_id` (FK users, nullable), `reviewed_at`. Indexed on `partner_org_id`. |
| `partner_user_invites` | `006_create_partner_user_invites` | 72-hour invite tokens. Columns: `id`, `partner_org_id` (FK), `email`, `invited_role` (ENUM partner_user/partner_admin), `token` (unique indexed), `invited_by_user_id` (FK users), `expires_at`, `accepted_at` (nullable), `created_at`. |
| `partner_activities` | `007_create_partner_activities` | Notes / tasks / calls / meetings / emails / status-change events. Columns: `id`, `partner_org_id` (FK indexed), `activity_type` (ENUM), `title`, `body`, `due_date`, `completed_at`, `created_by_user_id` (FK users), `assigned_to_user_id` (FK users, nullable), `is_internal` (bool, default true), `created_at`. |
| `partner_category_configs` | `008_create_partner_category_and_commission` | Configurable partner tiers. Columns: `id`, `code` (unique indexed), `display_name`, `description`, `deal_reg_sla_hours`, `max_discount_pct` (numeric), `monthly_fee_usd` (numeric default 200), `is_active`, `created_at`, `updated_at`. **Seeded with 3 rows: master/promotor/reseller** (SLA 48/72/96h, discount cap 40/30/20%). |
| `commission_structures` | `008_create_partner_category_and_commission` | Commission lookup per (category, type, year). Columns: `id`, `partner_category_code` (FK → partner_category_configs.code), `commission_type` (ENUM autonomous_sell/indirect_sell/direct_sell/co_sell_shared), `year` (ENUM year_1/year_2_plus), `commission_pct` (numeric), `subpartner_uplift_pct` (numeric default 10.0), `applies_to_upsell` (bool default true), `notes`. **Seeded with 24 rows** per Fracttal Distributor Agreement: autonomous_sell Y1=50% Y2+=30%, indirect_sell 30%/30%, direct_sell 10%/10%, co_sell_shared 25%/25%; subpartner uplift +10% applies only to Y1. |
| `partner_applications` | `009_create_partner_applications` | Public partner-application drafts and submitted applications. Columns: `id` (UUID PK), `status` (ENUM `application_status`: draft/submitted/in_review/info_required/approved/rejected, default draft), `applicant_email` (not null), `applicant_name`, `applicant_phone`, `applicant_title`, `legal_name`, `dba_name`, `website`, `hq_address` (JSONB), `phone`, `requested_categories` / `territory` / `industries` (JSONB arrays), `year_established`, `employee_count`, `annual_revenue`, `shareholders` (JSONB), `other_software_products`, `cmms_experience` (bool) + `cmms_experience_description`, `sales_marketing_strategy`, `technical_support_team` (bool) + `technical_support_description`, `implementation_services` (bool) + `implementation_description`, `partnership_goals`, `market_growth_plan`, `additional_info`, `references` (JSONB array), `terms_accepted` (bool default false) + `terms_accepted_at`, `draft_token` (unique, indexed) + `draft_expires_at` (30-day TTL), `submitted_at`, `reviewer_id` (FK users, nullable — populated in Sprint 6), `review_notes`, `reviewed_at`, `partner_org_id` (FK partner_organizations, nullable — populated on approval), `created_at`, `updated_at`. |
| `partner_application_documents` | `009_create_partner_applications` | Supporting documents uploaded with an application. Columns: `id` (UUID PK), `application_id` (FK partner_applications, indexed), `document_type` (string — free-form for the public form), `document_name`, `file_path`, `file_size_bytes`, `mime_type`, `uploaded_at`. Only metadata is recorded today — actual file storage backend is pending. |

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

Vite + React 18, with `react-router-dom@^6` for client-side routing (introduced in Sprint 5).

```
frontend/src/
├── main.jsx                         # ReactDOM root, wraps <App/> in <BrowserRouter>
├── App.jsx                          # Top-level <Routes> with /, /register, /register/confirmation, /internal/applications
├── components/
│   └── ProtectedRoute.jsx           # JWT auth guard - decodes localStorage 'token', redirects to /login if missing/invalid or role not in allowed list
└── pages/
    ├── RegisterPartner.jsx          # Public 10-step partner application form (Sprint 5)
    ├── RegisterConfirmation.jsx     # Post-submit thank-you page (?ref=<application_id>)
    └── ApplicationQueue.jsx         # Internal queue for channel_manager+ (table with status filter + search)
```

**Public registration flow (`RegisterPartner.jsx`).** Steps 1-10 walk through Company → Contact → Business → Reseller Experience → Technical Capabilities → Partnership Goals → References → Additional Info → Documents → Review & Submit. On Step 1 completion the form calls `POST /applications` to mint `{id, draft_token}` which is cached in component state and `localStorage` under `fprm_draft_{id}`. Every field change debounces a `PATCH /applications/{id}?draft_token=...` after 2 seconds. The Save & Continue Later panel surfaces a bookmarkable URL containing the draft token; revisiting that URL pulls the draft back in via `GET /applications/{id}?draft_token=...`. Step 10's Submit button POSTs to `/applications/{id}/submit?draft_token=...`, clears the localStorage cache, and navigates to `/register/confirmation?ref={id}`.

**Internal queue (`ApplicationQueue.jsx`).** Requires JWT with role in {`channel_manager`, `channel_ops_admin`, `system_admin`} (enforced by `ProtectedRoute`). Lists applications via `GET /applications` with optional `?status=` filter; client-side search across company name, applicant name, email. Status badge colours: submitted=blue, in_review=yellow, info_required=orange, approved=green, rejected=red. Row click routes to `/internal/applications/{id}` (review detail page lands Sprint 6).

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

### AD-8 · `models.py` uses portable SQLAlchemy types; migrations use PostgreSQL-native types

**Decision:** All Column definitions in `backend/models.py` use generic SQLAlchemy types (`Uuid`, `JSON`) rather than PostgreSQL-dialect types (`UUID`, `JSONB`). Alembic migration files, on the other hand, use `postgresql.UUID(as_uuid=True)` and `postgresql.JSONB` since the target is always PostgreSQL on Railway.

**Why:** CI tests run against a fresh sqlite database created via `Base.metadata.create_all(...)`. Dialect-specific column types crash on sqlite (the original FPRM-35 incident in Sprint 2). Migration files only ever run against PostgreSQL via `alembic upgrade head` on Railway, so they can use the native, more efficient types.

**Do not:** Import from `sqlalchemy.dialects.postgresql` inside `models.py`. If a feature genuinely needs JSONB-specific operators, gate it on the engine type at runtime rather than baking dialect-specific types into the model definition.

---

### AD-9 · Public + tenant-scoped + internal-only permission tiers

**Decision:** Every new endpoint falls into one of four tiers:

| Tier | Pattern | Examples |
|---|---|---|
| Public | No auth dependency | `GET /health`, `POST /auth/register`, `GET /config/partner-categories` |
| Authenticated, tenant-scoped | `Depends(get_current_user)` + manual `partner_org_id` check for partner roles | `GET /partners/{id}`, `GET /partners/{id}/documents`, `GET /partners/{id}/activities` |
| Permission-required | `Depends(require_permission("resource:action"))` | `POST /partners`, `GET /admin/audit-log` |
| Internal-only | `Depends(get_current_user)` + manual `INTERNAL_ROLES` check OR a permission only internal roles hold | `PATCH /partners/{id}/documents/{doc_id}`, `GET /config/commission-structures` |

**Why:** Most endpoints have a mixed permission story — for example, partner_admin can update their *own* org but not others. A single declarative permission string doesn't capture "own org only" — that requires an explicit comparison against `current_user.partner_org_id` in the handler. The `require_permission(...)` dependency handles purely-role-based gates; tenant scoping always lives in the handler.

**Do not:** Try to fold tenant scoping into `require_permission`. Keep `require_permission` for role-based 403s; check tenant identity in handler bodies.

---

### AD-10 · Sub-tasks inherit fix-version and native sprint from their parent — never set explicitly on Sub-task issues

**Decision:** When creating Sub-tasks via the Jira REST API, do not include `fixVersions` or `customfield_10020` (sprint) fields in the payload. Jira rejects subtask creates that set these fields directly.

**Why:** Jira treats subtasks as fully owned by their parent — sprint and fix-version assignment cascade automatically. Setting them on the subtask returns `HTTP 400 — "Issue is a subtask and subtasks cannot be associated to a sprint"`.

**Consequence:** Subtask JQL queries by sprint still work — Jira surfaces the parent's sprint membership on the subtask. The `fixVersion = X OR sprint = Y` dual-query from AD-4 catches subtasks correctly.

---

### AD-11 · Draft token pattern — per-application secret for unauthenticated access

**Decision:** Public partner-application endpoints authenticate via a per-application `draft_token` query parameter rather than a JWT. The token is minted at `POST /applications` (returned alongside the new application id), stored as a unique column on `partner_applications`, and required on every subsequent `PATCH /applications/{id}`, `POST /applications/{id}/submit`, and `POST /applications/{id}/documents` call. `GET /applications/{id}` accepts either `?draft_token=` (public) or a Bearer JWT with `partner_application:read_all` (internal). The token has a 30-day TTL enforced by `draft_expires_at`; an expired token returns 410.

**Why:** Applicants are external prospects who don't yet have user accounts — we cannot require authentication before a partner record exists, and we don't want to require account creation just to start a draft. A per-application secret threaded through the URL is simple, bookmarkable (so applicants can resume later), and limits blast radius if leaked (it only authorises that one application).

**Consequence:** Routers handling these endpoints must validate the token against the database record on every call — never trust the application id alone. The `audit_log.actor_id` column is now nullable (migration 009) because `partner_application.submitted` events have no authenticated actor; `audit.log_audit_event` records `actor_role="anonymous"` in that case.

**Do not:** Reuse draft tokens for any other resource. Never extend the public surface to mutating endpoints that affect anything outside the single application identified by `{id}`.

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
