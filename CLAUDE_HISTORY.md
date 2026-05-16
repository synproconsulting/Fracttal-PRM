# Fracttal PRM — Sprint History

## Sprint 1 — Project Scaffold & Infrastructure

**Started:** 2026-05-16
**Closed:** 2026-05-16 (single-day intensive; 14-day window 2026-05-16 → 2026-05-30 was the planned envelope)
**Fix Version ID:** `10528`
**Native Sprint ID:** `501`

### Phase 1 epics created

| Key | Summary |
|---|---|
| FPRM-2 | Foundation: Project Scaffold & Infrastructure (Sprint 1 parent epic) |
| FPRM-3 | Foundation: Authentication & Security |
| FPRM-4 | Foundation: RBAC & Permissions |
| FPRM-5 | Foundation: Core Data Model |

### Sprint 1 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-6 | Railway services and environment variables | **In Progress — carried to Sprint 2** | #1 | Docs PR landed (`docs/railway-setup.md`). Manual Railway dashboard work partial: backend service created, PostgreSQL service + `DATABASE_URL` provisioned; frontend service not yet created; not all env vars confirmed set; first backend deploy failed (see FPRM-19) and re-attempt pending after fix landed. |
| FPRM-7 | Scaffold monorepo structure | Done | #2 | `backend/`, `frontend/`, root files. |
| FPRM-8 | CI/CD pipeline | Done | #3 | First true auto-merger run after `PAT_TOKEN` added to GitHub Secrets. |
| FPRM-9 | Health check endpoint | Done | #4 | Clean end-to-end auto-merge — first PR opened with full pipeline already on `main`. |

All nine Sub-tasks under the four Stories are Done.

### Sprint 1 bugs — discovered and fixed in-sprint

| Key | Bug | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-19 | Railway backend build fails on Python 3.13 — pydantic-core wheel incompatibility | Done | #5 | The actual fix is `pydantic==2.7.4` in `backend/requirements.txt` — `pydantic-core 2.18.x` ships a Python 3.13 wheel, so Railpack resolves it without compiling from source. |
| FPRM-20 | CI workflow does not trigger on `fix/**` branches | Done | #5 (bundled) | Added `fix/**` to `on.push.branches` in `.github/workflows/ci.yml`. Self-validating: PR #5 was on a `fix/**` branch and auto-merged through the new trigger config. |

### Known dead config — to remove in Sprint 2

PR #5 also landed `railway.toml` at the repo root with Nixpacks-style syntax (`NIXPACKS_PYTHON_VERSION = "3.11"`). **Railway is using Railpack as its builder, not Nixpacks**, so this file is ignored by the Railway build process. It is harmless dead config — Railpack does not error on unknown files — but should be removed cleanly in Sprint 2 to avoid future confusion. The `pydantic` version bump alone is the working fix.

### What landed on `main` during Sprint 1

- `backend/`
  - `main.py` — FastAPI app with CORS middleware reading `FRONTEND_URL`
  - `database.py` — SQLAlchemy engine, `SessionLocal`, `Base`, `get_db()` generator
  - `requirements.txt` — 11 packages, pinned versions (`pydantic` at 2.7.4)
  - `routers/health.py` — `GET /health` returns 200 with `{status, service, database}`; never 500
  - `tests/test_placeholder.py`, `tests/test_health.py` — health tests use FastAPI `dependency_overrides`
- `frontend/` — Vite + React scaffold (`package.json`, `index.html`, `vite.config.js`, `src/main.jsx`, `src/App.jsx`)
- `.github/workflows/ci.yml` — pytest matrix (Python 3.11 + 3.12, blocking), bandit (`--exit-zero`, non-blocking), SonarCloud (`continue-on-error: true`), Railway deploy on `main` (`continue-on-error: true`), auto-merger using `PAT_TOKEN` and triggered on `feature/**` + `fix/**` pushes
- `docs/railway-setup.md` — manual Railway and GitHub Secrets checklist (FPRM-6)
- `railway.toml` — **dead config** (see "Known dead config" above)
- `README.md`, `.gitignore` at root
- `CLAUDE.md` — seeded with Sprint 1 IDs in the Jira Configuration table (`Sprint 1: 501` / `Sprint 1: 10528`)

### Auto-merger validation chain

| PR | Branch | Merge mechanism | What it proved |
|---|---|---|---|
| #1 | `feature/fprm-6-railway-setup` | Bootstrap (Dev Agent API merge) | Docs landed before CI existed |
| #2 | `feature/fprm-7-monorepo-scaffold` | Bootstrap (Dev Agent API merge) | Scaffold landed before CI existed |
| #3 | `feature/fprm-8-ci-pipeline` | **Auto-merger (after PAT_TOKEN added)** | First true auto-merge; validated the full `test → auto-merge` chain |
| #4 | `feature/fprm-9-health-check` | **Auto-merger** | Clean end-to-end; no human in the loop |
| #5 | `fix/fprm-19-pydantic-py313` | **Auto-merger** (via FPRM-20's trigger fix) | First `fix/**` auto-merge; validated bug-fix flow |

### Bootstrap exceptions (one-time, documented in commit messages)

PR #1 and PR #2 were merged by the Dev Agent calling `PUT /pulls/{n}/merge` because `.github/workflows/ci.yml` did not yet exist on `main` (CI was being delivered by PR #3 in this same sprint). After PR #3 landed, all subsequent PRs were merged by the workflow itself (the rule-based Manager Agent), with no manual intervention.

### GitHub Secrets configured during Sprint 1 (by Johan)

- `PAT_TOKEN` — auto-merger workflow dispatch
- `RAILWAY_TOKEN`, `RAILWAY_PROJECT_ID` — `main`-branch deploy step (non-blocking, currently failing pending FPRM-6 completion)
- `SONAR_TOKEN` — SonarCloud scan (non-blocking, currently failing — see below)

### Known follow-ups for Sprint 2

1. **FPRM-6 carryover** — Railway dashboard:
   - Frontend Railway service `fracttal-prm-frontend` not yet created
   - Backend service env vars (`JWT_SECRET`, `JIRA_*`, etc.) not all confirmed set
   - Backend deploy verification pending — needs re-attempt now that FPRM-19 fix has landed
2. **Remove `railway.toml`** — dead Nixpacks-syntax config; Railway uses Railpack. Small `fix/` PR.
3. **SonarCloud scan failing** — `continue-on-error: true` keeps it non-blocking but the scan never succeeds. Likely needs a `sonar-project.properties` file and a linked SonarCloud project. Optional.
4. **`Live Deployments` table in `CLAUDE.md`** — backend and frontend Railway public URLs not yet recorded. Update when Johan confirms services are live (linked to FPRM-6).
5. **Sprint 1 native sprint closed at end of sprint** — incomplete issues (FPRM-6) moved to backlog by Jira on sprint close. Sprint 2 setup will re-assign FPRM-6 to Sprint 2's fix version and native sprint.

---

## Sprint 2 — Authentication

**Started:** 2026-05-16
**Closed:** 2026-05-16 (single-day intensive)
**Fix Version ID:** `10561`
**Native Sprint ID:** `534`

### Sprint 2 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-22 | User model and database migration | Done | #9 + #10 (FPRM-35 hotfix) | Initial PR landed broken Uuid code due to FPRM-36 race; FPRM-35 patched. Final state on main is correct. |
| FPRM-23 | JWT authentication endpoints | Done | #11 | bcrypt password hashing, HS256 JWT, in-memory blacklist for logout |
| FPRM-24 | Auth middleware and route protection | Done | #12 | slowapi rate limiting (10/min on register + login) via shared ``rate_limiter.py`` |
| FPRM-25 | Password reset flow | Done | #13 | ``PasswordResetToken`` model + migration 002, request/confirm endpoints |

### Sprint 2 housekeeping (Sprint 1 carry-over)

| Key | Item | Status | PR |
|---|---|---|---|
| FPRM-6 | Railway services and environment variables | Done | #7 (Sprint 1 closeout) | All services live, env vars confirmed |
| FPRM-21 | Remove dead railway.toml | Done | #8 | Railpack ignores Nixpacks syntax; file removed cleanly |

### Sprint 2 bugs — discovered and fixed in-sprint

| Key | Bug | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-35 | User model Uuid type fails sqlite compilation - main red | Done | #10 | Used ``sqlalchemy.UUID`` (PG-only alias) instead of ``sqlalchemy.Uuid`` (generic, portable). One-line fix restored main to green and re-enabled all Sprint 1 tests. |
| FPRM-36 | Auto-merger race condition merges PR before real-commit CI completes | Done | #14 | Empty-branch creation triggered a passing CI run on unchanged-main state; auto-merger merged the later real commit. Fix: pass ``sha`` to ``PUT /pulls/n/merge`` so the merge is refused (409) if the head has advanced past the SHA actually tested. |

### What landed on ``main`` during Sprint 2

- ``backend/models.py`` - ``User`` (Uuid pk, email, hashed_password, is_active, is_verified, role, partner_org_id, timestamps) and ``PasswordResetToken`` (token, user_id FK, expires_at, used)
- ``backend/auth.py`` - ``hash_password``, ``verify_password`` (bcrypt via passlib), ``create_access_token`` / ``decode_access_token`` (HS256), ``get_current_user`` dependency, in-memory ``token_blacklist``
- ``backend/rate_limiter.py`` - single shared ``Limiter`` instance with ``get_remote_address`` key
- ``backend/routers/auth_router.py`` - register, login, logout, refresh, me, password-reset/request, password-reset/confirm
- ``backend/alembic.ini`` + ``alembic/env.py`` - Alembic initialised (no ``alembic/__init__.py`` - would shadow installed alembic package)
- ``backend/alembic/versions/001_create_users_table.py``
- ``backend/alembic/versions/002_create_password_reset_tokens.py``
- ``backend/tests/conftest.py`` - autouse fixture creating tables via ``Base.metadata.create_all()`` so unit tests can run on sqlite
- ``backend/tests/test_user_model.py``, ``test_auth.py``, ``test_password_reset.py``
- ``backend/main.py`` - registers ``auth_router``, ``app.state.limiter``, ``RateLimitExceeded`` handler
- ``backend/requirements.txt`` - appended ``passlib[bcrypt]==1.7.4``, ``bcrypt==4.0.1``, ``email-validator==2.1.0`` (no removals)
- ``.github/workflows/ci.yml`` - auto-merger now passes ``sha`` to merge API (FPRM-36 fix)
- ``railway.toml`` REMOVED (FPRM-21 housekeeping)

### Auto-merger lessons

- **Race observed (FPRM-36)**: branch-then-commit pushes caused two CI runs; the first (on unchanged-main state) trivially passed and merged real commits that hadn't been tested
- **Fix landed**: ``ci.yml`` auto-merger now sends ``sha = $GITHUB_SHA`` to ``PUT /pulls/n/merge``; GitHub refuses with 409 if head advanced
- **Dev Agent pattern adopted as defence-in-depth**: branches are now created with the commit pre-attached (blobs → tree → commit → ref points directly at commit). Single push event, single CI run, no race possible from the Dev Agent's side

### Post-Sprint manual step required

The Sprint 2 migrations (``001_create_users_table``, ``002_create_password_reset_tokens``) are in the repo but have not been applied to the live Railway PostgreSQL DB. Options:

1. **Recommended:** update the Railway ``fracttal-prm-backend`` service start command to ``alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT``. Future migrations apply automatically on each deploy.
2. One-off: run ``alembic upgrade head`` from a Railway shell session against the live DB.

Until this runs, ``/auth/register``, ``/auth/login``, and password-reset endpoints will 500 against the live backend (tables don't exist in the live DB yet). Tests in CI use sqlite + create_all so they pass without this step.

### API endpoints active after Sprint 2

| Method | Path | Auth | Rate-limited |
|---|---|---|---|
| GET | ``/`` | No | No |
| GET | ``/health`` | No | No |
| POST | ``/auth/register`` | No | 10/min |
| POST | ``/auth/login`` | No | 10/min |
| POST | ``/auth/logout`` | Bearer | No |
| POST | ``/auth/refresh`` | Bearer | No |
| GET | ``/auth/me`` | Bearer | No |
| POST | ``/auth/password-reset/request`` | No | No |
| POST | ``/auth/password-reset/confirm`` | No | No |

### Known follow-ups for Sprint 3

1. **Alembic upgrade on Railway** - run migrations against live DB before any auth endpoint will work in production (see Post-Sprint manual step above)
2. **Password reset emails** - currently logs reset URL to stdout. A real email backend (SES, SendGrid, etc) will be needed when Sprint 3+ requires it
3. **Token blacklist persistence** - JWT logout blacklist is in-memory only; lost on backend restart. Consider Redis or DB-backed blacklist when multi-instance deploys arrive
4. **SonarCloud scan still failing** - non-blocking; needs ``sonar-project.properties`` and linked SonarCloud project to actually produce useful output

---

## Inter-sprint hotfixes (between Sprint 2 closeout and Sprint 3 start)

Five Python-3.13 / Railpack deploy bugs were filed and fixed between Sprint 2 closeout and Sprint 3 setup. All filed against Sprint 2 fix version (`10561`), no native sprint assigned (Sprint 2 was already closed).

| Key | Bug | PR | Notes |
|---|---|---|---|
| FPRM-37 | pydantic-core wheel missing for Python 3.13 on Railpack — pydantic 2.7.4 insufficient fix | #16 | Bumped `pydantic` 2.7.4 → 2.11.4. FPRM-19's earlier pin to 2.7.4 was based on a wrong assumption about Railpack's wheel index. |
| FPRM-38 | SQLAlchemy 2.0.23 incompatible with Python 3.13 — upgrade required | #18 | `sqlalchemy` 2.0.23 → 2.0.36, `alembic` 1.13.0 → 1.14.0. CLAUDE.md table bundled. |
| FPRM-39 | psycopg2-binary missing libpq.so.5 on Railpack Python 3.13 | #19 | `psycopg2-binary` 2.9.9 → 2.9.10 (2.9.10+ bundles libpq, removes system-library dependency). |
| FPRM-40 | Sprint 1 dependency pins pre-date Python 3.13 — proactive upgrade sweep | #20 | Proactive sweep: `fastapi` 0.115.12, `uvicorn` 0.34.2, `pyjwt` 2.10.1, `httpx` 0.28.1, `pytest` 8.3.5; new `starlette==0.46.2` pin (fastapi 0.115.x requires <0.47). `slowapi` left at 0.1.9 (PyPI latest confirmed). |

PR #17 was a docs-only follow-up to FPRM-37, updating the CLAUDE.md backend dependencies table when Johan asked for the version reference to be kept in sync.

**Lesson:** the original Sprint 1 pinning (Oct/Nov 2023 versions) and FPRM-19's reactive bump to pydantic 2.7.4 were both insufficient for Railway's Python 3.13 runtime. The full sweep in FPRM-40 brought every backend dependency onto a known-good version. Future package additions should be verified against Railway's actual Python version (currently 3.13) before pinning.

---

## Sprint 3 — RBAC & Permissions

**Started:** 2026-05-16
**Closed:** 2026-05-16 (single-day intensive)
**Fix Version ID:** `10562`
**Native Sprint ID:** `535`

### Sprint 3 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-41 | Role definitions and permission matrix | Done | #21 | `UserRole` enum (8 roles); `PERMISSIONS` matrix; `auth.get_current_user` now validates user.role |
| FPRM-42 | RBAC enforcement and tenant isolation | Done | #22 | `require_permission(permission)` dep factory; `get_partner_org_filter`; `apply_tenant_filter` |
| FPRM-43 | Field-level visibility for sensitive fields | Done | #23 | `filter_sensitive_fields(data, user)`; `is_field_visible(field, user)` |
| FPRM-44 | Audit trail foundation | Done | #24 | `AuditLog` model + migration 003; `log_audit_event(...)` utility; `GET /admin/audit-log` endpoint |

All nine Sub-tasks (FPRM-45 → FPRM-53) closed Done.

### What landed on `main` during Sprint 3

- `backend/roles.py` (new) — `UserRole` Enum (8 roles), `PARTNER_ROLES` and `INTERNAL_ROLES` sets
- `backend/permissions.py` (new, then extended in FPRM-42) — `PERMISSIONS` dict (role → permission set), `has_permission`, `require_permission` factory, `get_partner_org_filter`, `apply_tenant_filter`
- `backend/field_visibility.py` (new) — `PARTNER_HIDDEN_FIELDS`, `PARTNER_VISIBLE_SENSITIVE_FIELDS`, `filter_sensitive_fields`, `is_field_visible`
- `backend/audit.py` (new) — `log_audit_event(...)` utility
- `backend/routers/admin_router.py` (new) — `GET /admin/audit-log` (paginated, filterable, requires system_admin via `require_permission("user_management:read_all")`)
- `backend/models.py` (modified) — appends `AuditLog` model, imports `JSON` from sqlalchemy
- `backend/auth.py` (modified) — validates `user.role` against `UserRole` enum (401 on unknown role)
- `backend/main.py` (modified) — registers `admin_router`
- `backend/alembic/versions/003_create_audit_log.py` (new) — creates `audit_log` table + 3 indexes
- `backend/tests/test_roles.py`, `test_rbac.py`, `test_field_visibility.py`, `test_audit.py` (new)

### Deviations from sprint prompt

1. **`require_permission` uses direct `from auth import get_current_user`** instead of the prompt's placeholder pattern. No circular import; chain is `roles → auth → permissions`.
2. **`admin_router` uses canonical `require_permission("user_management:read_all")`** instead of a local `require_system_admin` helper. Only `system_admin` has that permission, so behaviour is identical with fewer abstractions.
3. **`AuditLog` model uses `Uuid(as_uuid=True)`** consistent with `User` and `PasswordResetToken` (the prompt used `sa.Uuid` which would require an additional `import sqlalchemy as sa` in `models.py`).

### API endpoint added (Sprint 3)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/admin/audit-log` | Bearer (system_admin only) | Paginated `?page=N&page_size=N` (page_size ≤ 200); filters: `object_type`, `actor_id`, `date_from`, `date_to` |

### Known follow-ups for Sprint 4

1. **Use `require_permission` and `apply_tenant_filter` in every future router.** PROJECT_CONTEXT.md now documents this as the canonical pattern.
2. **`log_audit_event` should be wired into state-change endpoints** as Sprint 4 builds out deal/quote/partner workflows. Audit utility exists; callers need to be added.
3. **In-memory token blacklist + reset-email backend** still pending (carried from Sprint 2).
4. **SonarCloud configuration** still pending (carried from Sprint 2).

---

## Sprint 4 — Core Data Model (Phase 1 closeout)

**Started:** 2026-05-16
**Closed:** 2026-05-16 (single-day intensive)
**Fix Version ID:** `10563`
**Native Sprint ID:** `536`

### Story key renumbering

The Sprint 4 prompt assumed stories would start at `FPRM-45`. In reality, Sprint 3 sub-tasks already consumed FPRM-45..53, so Sprint 4 stories landed at **FPRM-54..59** and the 13 sub-tasks at **FPRM-60..72**. The Phase B branch names were renumbered accordingly (`feature/fprm-54-partner-org-model` etc.). No work was lost — the renaming was surface-level only.

### Sprint 4 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-54 | Partner Organization and Profile tables | Done | #27 | `partner_organizations` + `partner_profiles` tables, `partners_router` with tenant scoping + audit logging, FK on `users.partner_org_id` |
| FPRM-55 | Partner Documents table | Done | #28 | 10 document types + 4-state review workflow, `proof_of_fiscal_domicile` expiry validation (>90d old rejected) |
| FPRM-56 | Partner Users table and invite system | Done | #29 | `partner_user_invites` table (72h expiry), `partner_users_router`, `POST /auth/accept-invite` public endpoint |
| FPRM-57 | Partner Notes, Tasks and Activities table | Done | #30 | `partner_activities` table, `is_internal` filter applied for partner-side users on GET |
| FPRM-58 | Partner Category and Commission configuration tables | Done | #31 | `partner_category_configs` + `commission_structures` with 3 categories + 24 commission rows seeded from Distributor Agreement |
| FPRM-59 | Phase 1 integration test and PROJECT_CONTEXT update | Done | #32 | End-to-end auth -> partner -> invite -> tenant -> audit flow; PROJECT_CONTEXT Sections 1/2/6 updated; small `auth.get_current_user` UUID-coercion fix bundled for sqlite test compat |

All 13 sub-tasks (FPRM-60..72) closed Done.

### What landed on `main` during Sprint 4

- `backend/models.py` — extended with `ProgramType`, `PartnerCategory`, `PartnerTier`, `PartnerStatus`, `MonthlyFeeStatus`, `DocumentType`, `DocumentStatus`, `InvitedRole`, `ActivityType`, `CommissionType`, `CommissionYear` enums; new models `PartnerOrganization`, `PartnerProfile`, `PartnerDocument`, `PartnerUserInvite`, `PartnerActivity`, `PartnerCategoryConfig`, `CommissionStructure`; `Numeric` added to imports; `User.partner_org_id` upgraded to a real FK
- `backend/auth.py` — `get_current_user` now coerces the JWT `sub` claim with `uuid.UUID(...)` before the SQLAlchemy filter (sqlite needs a UUID object; PG coerces transparently)
- `backend/routers/partners_router.py` (new) — list / get / create / update with tenant scoping + audit logging
- `backend/routers/documents_router.py` (new) — list / upload / review; `proof_of_fiscal_domicile` 90-day age validation
- `backend/routers/partner_users_router.py` (new) — invite / list / patch
- `backend/routers/activities_router.py` (new) — list / create / update with `is_internal` filter for partner-side users
- `backend/routers/config_router.py` (new) — public `GET /config/partner-categories`, `channel_ops_admin`-only writes
- `backend/routers/auth_router.py` (modified) — adds `POST /auth/accept-invite`
- `backend/main.py` (modified) — registers 5 new routers (partners, documents, partner_users, activities, config)
- `backend/alembic/versions/004_create_partner_organizations.py` (new) — creates partner_organizations + partner_profiles + users FK
- `backend/alembic/versions/005_create_partner_documents.py` (new) — creates partner_documents
- `backend/alembic/versions/006_create_partner_user_invites.py` (new) — creates partner_user_invites
- `backend/alembic/versions/007_create_partner_activities.py` (new) — creates partner_activities
- `backend/alembic/versions/008_create_partner_category_and_commission.py` (new) — creates partner_category_configs + commission_structures **and seeds 3 category rows + 24 commission rows**
- `backend/tests/test_partners.py`, `test_documents.py`, `test_partner_users.py`, `test_activities.py`, `test_config.py`, `test_integration_phase1.py` (new) — 56 new tests; full suite ends Sprint 4 at 111/111 green
- `PROJECT_CONTEXT.md` (modified) — Section 1 now lists all 29 Phase 1 endpoints, Section 2 documents all 10 Phase 1 tables, Section 6 adds AD-8 (portable types in models, PG types in migrations), AD-9 (four permission tiers), AD-10 (subtasks inherit sprint/fixVersion from parent)

### API endpoint count

Phase 1 closes with **29 endpoints** live across `/auth/*`, `/admin/*`, `/partners/*`, `/config/*`. Full table maintained in `PROJECT_CONTEXT.md` Section 1.

### Sprint 4 lessons

1. **Jira subtask creates must omit `fixVersions` and `customfield_10020` (sprint).** Jira returns `HTTP 400 — "Issue is a subtask and subtasks cannot be associated to a sprint"`. Subtasks inherit both from their parent. Encoded as AD-10.
2. **`Uuid(as_uuid=True)` columns require a `uuid.UUID` argument when filtering on sqlite.** PostgreSQL coerces strings via the psycopg adapter, so this bug only surfaced when the Phase 1 integration test ran `client.get(...)` against a real sqlite DB via JWT auth. Fix is a one-liner in `auth.get_current_user`. Encoded implicitly in AD-8.
3. **Seed-data migrations using `gen_random_uuid()` and `NOW()` are PG-only by design.** sqlite tests bypass Alembic entirely (conftest's `Base.metadata.create_all`), so the seed-data migration cannot also "seed sqlite for tests" — tests must seed via Python in their own fixtures (test_config.py does exactly this).
4. **Per-test isolated sqlite DB files work better than the shared `test.db`.** Each Sprint 4 test module creates its own `test_partners.db`, `test_documents.db`, etc., so module-scoped engines never collide. The session-scoped conftest fixture still seeds the default `test.db` for legacy tests.

### Known follow-ups for Sprint 5

1. **Alembic migrations 004..008 must be applied to Railway PostgreSQL** before any Sprint 4 endpoint will function in production. The recommended Sprint 2 fix (Railway start command = `alembic upgrade head && uvicorn ...`) should now be applying these automatically on each deploy — verify after first Sprint 5 deploy.
2. **`partner_profiles` is created but has no router yet.** A `partner_profile` CRUD router is queued for Sprint 5 alongside the partner registration flow.
3. **Document file uploads only store metadata.** Actual file storage (S3 / Railway Volume / similar) is queued for Sprint 5+ when partner onboarding ships.
4. **Invite acceptance does not send email.** The invite token is currently returned in the API response — production will need an email backend, queued for Sprint 5+.
5. **Carry-forward:** in-memory token blacklist, reset-email backend, SonarCloud configuration — all still pending from earlier sprints.

---

## Sprint 5 — Partner Registration & Onboarding (Phase 2 kick-off)

**Started:** 2026-05-16
**Closed:** 2026-05-16 (single-day intensive)
**Fix Version ID:** `10564`
**Native Sprint ID:** `537`
**Phase 2 epic:** FPRM-74 — Partner Registration & Onboarding

### Sprint 5 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-75 | PartnerApplication backend model and API | Done | #35 | Two new tables + six endpoints + draft-token pattern; `audit_log.actor_id` made nullable in same migration. 16 new tests. |
| FPRM-76 | Registration form: Company and Contact sections | Done | #36 | Multi-step scaffold + `/register` route + Steps 1-2 + draft creation + debounced auto-save + resume via URL token. Added `react-router-dom@^6.22.0`. |
| FPRM-77 | Registration form: Business and Experience sections | Done | #37 | Steps 3-5; fetches `/config/partner-categories` for checkbox catalog; Yes/No conditional fields for Reseller Experience and Technical Capabilities. |
| FPRM-78 | Registration form: Goals, References, Documents and Submit | Done | #38 | Steps 6-10 + document upload (PDF/JPG/PNG ≤10MB, metadata-only persistence) + Review & Submit + terms checkbox + `RegisterConfirmation.jsx`. |
| FPRM-79 | Internal application review queue | Done | #39 | `ApplicationQueue.jsx` at `/internal/applications` behind `ProtectedRoute`; status filter, search, status badges. |
| FPRM-80 | Sprint 5 docs and PROJECT_CONTEXT update | Done | (this PR) | Sections 1/2/3 updated, AD-11 added, CLAUDE_HISTORY entry added. |

All 7 sub-tasks (FPRM-81..87) closed Done.

### What landed on `main` during Sprint 5

- `backend/models.py` — `ApplicationStatus` enum + `PartnerApplication` + `PartnerApplicationDocument` models; `AuditLog.actor_id` flipped to `nullable=True`
- `backend/audit.py` — `log_audit_event` accepts `actor=None` and records `actor_role="anonymous"` in that case
- `backend/alembic/versions/009_create_partner_applications.py` — creates both new tables, the `application_status` enum, draft-token unique constraint, status/draft_token indexes, FKs to `users.id` and `partner_organizations.id`, and alters `audit_log.actor_id` to nullable
- `backend/permissions.py` — `partner_application:read_all` granted to `channel_manager`, `channel_ops_admin`, `system_admin`; `partner_application:update_all` granted to `channel_ops_admin`, `system_admin` (used by Sprint 6 review workflow)
- `backend/routers/applications_router.py` (new) — six endpoints: public draft create / get / patch / submit / documents, plus internal paginated list with `?status=` filter. Public endpoints validate the draft token on every call and return 410 on expired drafts.
- `backend/main.py` — registers `applications_router`
- `backend/tests/test_applications.py` (new) — 16 tests covering draft creation, field update, draft_token validation, submit validation, duplicate-submit guard, document metadata, internal list + status filter, RBAC denial for partner role; full suite ends Sprint 5 at **130/130 green**
- `frontend/package.json` — appended `react-router-dom@^6.22.0`
- `frontend/src/main.jsx` — wraps `App` in `<BrowserRouter>`
- `frontend/src/App.jsx` — `<Routes>` for `/`, `/register`, `/register/confirmation`, `/internal/applications` (the last guarded by `ProtectedRoute`)
- `frontend/src/pages/RegisterPartner.jsx` (new) — 10-step public partner application form
- `frontend/src/pages/RegisterConfirmation.jsx` (new) — post-submit thank-you page with application reference number
- `frontend/src/pages/ApplicationQueue.jsx` (new) — internal review queue with status filter and search
- `frontend/src/components/ProtectedRoute.jsx` (new) — JWT auth guard
- `PROJECT_CONTEXT.md` — Section 1 lists the six new endpoints; Section 2 documents `partner_applications` + `partner_application_documents` and the audit_log nullability change; Section 3 now contains a Frontend component tree; Section 6 introduces **AD-11 — Draft token pattern**

### API endpoint count

Phase 2 kicks off with 6 new endpoints across `/applications/*`. Phase 1's 29 endpoints remain unchanged; total now **35 endpoints** live.

### Sprint 5 lessons

1. **Public-endpoint audit needs nullable `actor_id`.** The original Sprint 3 audit_log made `actor_id` NOT NULL with a FK to `users.id`, which prevented logging events triggered by unauthenticated actors. Migration 009 relaxed this to nullable and `audit.log_audit_event` was extended to accept `actor=None` with `actor_role="anonymous"`. Captured in AD-11.
2. **Optional auth on a single FastAPI endpoint requires a custom dependency.** `Depends(get_current_user)` always requires a Bearer token. To let `GET /applications/{id}` accept either `?draft_token=` OR a JWT, the router reads the `Authorization` header manually via `Header(default=None)` and re-decodes the token using the existing `decode_access_token` helper. Documented inline in `applications_router.py`.
3. **Frontend routing added in Sprint 5.** The Sprint 1 scaffold shipped a single static `<App/>` component. Sprint 5 introduced `react-router-dom` and a `<Routes>` tree. All future frontend features should add their pages under `frontend/src/pages/` and register a `<Route>` in `App.jsx`.
4. **Jira issue type for sub-tasks is `Sub-task` (hyphenated).** This project's issue scheme exposes both `Subtask` and `Sub-task` in the API listing, but only `Sub-task` is valid for the FPRM project; using `Subtask` returns `HTTP 400 — "Specify a valid issue type"`. Confirmed during Phase A6.

### Known follow-ups for Sprint 6

1. **Application review detail page** (`/internal/applications/{id}`) — the queue page already routes to it, but the page itself is queued for Sprint 6 along with the review workflow (approve/reject, info-required, convert to `partner_organization`).
2. **File storage backend** — `POST /applications/{id}/documents` records metadata only; actual file persistence (S3 / Railway Volume / similar) is still pending.
3. **Confirmation/notification email** — submit currently has no email backend. Applicants only see the in-app confirmation page. Email integration carries forward from earlier sprints.
4. **Alembic migration 009 must run on Railway PostgreSQL** before any `/applications/*` endpoint will work in production. The Sprint 2 Railway start command (`alembic upgrade head && uvicorn ...`) should be applying it automatically — verify after first Sprint 5 deploy.
5. **Carry-forward:** in-memory token blacklist, reset-email backend, SonarCloud configuration — all still pending from earlier sprints.
