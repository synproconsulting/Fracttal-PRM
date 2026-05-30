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

5. **Carry-forward:** in-memory token blacklist, SonarCloud configuration — Sprint 6 partly closes the email-backend gap (lifecycle notifications now use SMTP with dev-mode stdout fallback; password-reset emails still pending an SMTP wire-up in a later sprint).

---

## Sprint 6 — Internal Review Workflow & Approval (Phase 2)

**Started:** 2026-05-16
**Closed:** 2026-05-16 (single-day intensive)
**Fix Version ID:** `10565`
**Native Sprint ID:** `538`
**Phase 2 epic:** FPRM-74 — Partner Registration & Onboarding

### Sprint 6 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-90 | Application review detail page | Done | #42 | Adds approve/reject/request-info/timeline endpoints + `rejection_reason`/`info_request_message` columns (migration 010) + `ApplicationReview.jsx` page with action panel, modals, sticky timeline. Required a follow-up commit to fix one test that overrode `get_current_user` but called an endpoint that reads the Authorization header directly. |
| FPRM-91 | Applicant info-required response flow | Done | #43 | New `PartnerApplicationMessage` model + migration 011, `GET`/`POST /applications/{id}/messages` (public via draft_token OR internal Bearer), `ApplicationResume.jsx` page. Same header-vs-dependency gotcha as Story 1 — fixed by minting a real JWT in the test. |
| FPRM-92 | Partner provisioning on approval | Done | #44 | New `backend/provisioning.py`: idempotent `provision_partner_from_application` creates `PartnerOrganization` + `PartnerProfile` + `PartnerUserInvite`, links `application.partner_org_id`. Router already imported it lazily from Story 1; this PR makes the import succeed. No migration — `partner_org_id` was added in Sprint 5 migration 009. |
| FPRM-93 | Email notifications for application lifecycle | Done | #45 | New `backend/notifications.py` — `send_email` wraps `smtplib` with dev-mode stdout fallback and never raises. Five lifecycle templates wired into submit / approve / reject / request-info via `try/except`. Railway env vars listed in PR description for ops. |
| FPRM-94 | Sprint 6 docs and PROJECT_CONTEXT update | Done | (this PR) | Sections 1, 2, 3 updated; AD-12 (provisioning) and AD-13 (email fallback) added. |

All 9 sub-tasks (FPRM-95..FPRM-103) closed Done.

### Sprint 6 bugs — discovered and tracked

| Key | Bug | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-88 | CLAUDE.md missing pre-sprint git hygiene hard rules | Done | #41 | Pre-implementation fix landed before any Phase A work. Adds an explicit Hard Rule covering `git fetch / reset --hard / clean -fd --exclude=Documentation/` so the canonical local `Documentation/` folder (RUNBOOK.md, sprint prompts, partner contracts, requirements) survives the pre-sprint reset. |
| FPRM-89 | actor_id stores string 'None' on anonymous audit events | To Do | — | Logged only, intentionally not fixed in Sprint 6. Cosmetic only — anonymous audit rows are otherwise correct. Carries to a future sprint. |

### What landed on `main` during Sprint 6

- `backend/models.py` — adds `rejection_reason` and `info_request_message` columns to `PartnerApplication`; new `PartnerApplicationMessage` model + `ApplicationMessageSender` enum
- `backend/routers/applications_router.py` — four new review action endpoints (approve/reject/request-info/timeline), GET+POST messages, all wired to audit log and email notifications (try/except wrapped)
- `backend/provisioning.py` (new) — `provision_partner_from_application` utility
- `backend/notifications.py` (new) — `send_email` + 5 lifecycle templates, dev-mode stdout fallback
- `backend/alembic/versions/010_application_review_columns.py` (new) — adds rejection_reason + info_request_message
- `backend/alembic/versions/011_create_partner_application_messages.py` (new) — adds partner_application_messages table
- `backend/tests/test_application_review.py` (new) — 9 cases
- `backend/tests/test_application_messages.py` (new) — 5 cases
- `backend/tests/test_provisioning.py` (new) — 7 cases
- `backend/tests/test_notifications.py` (new) — 7 cases
- `frontend/src/pages/ApplicationReview.jsx` (new) — internal review detail page
- `frontend/src/pages/ApplicationResume.jsx` (new) — applicant resume page
- `frontend/src/App.jsx` — registers `/internal/applications/:id` (behind `ProtectedRoute`) and public `/resume-application`
- `PROJECT_CONTEXT.md` — Sections 1, 2, 3 updated; AD-12 (provisioning), AD-13 (email pattern) added
- `CLAUDE.md` — pre-sprint git hygiene rules added (FPRM-88)
- `CLAUDE_HISTORY.md` — this Sprint 6 entry

### API endpoint count

Sprint 6 adds 6 new endpoints (`/approve`, `/reject`, `/request-info`, `/timeline`, GET+POST `/messages`). The total surface area is now **41 endpoints**.

### Sprint 6 lessons

1. **Endpoints that bypass `Depends(get_current_user)` cannot be tested via `app.dependency_overrides[get_current_user]`.** The optional-auth pattern in `applications_router._user_from_bearer` reads the Authorization header directly so it can handle either a draft_token OR a Bearer JWT, but that means dependency overrides do not apply. Test the internal path either by minting a real JWT with `auth.create_access_token` and sending it via `headers={"Authorization": ...}` (PR #43 fix), or by exercising the public draft_token path (PR #42 fix).
2. **Notification calls in lifecycle endpoints must be try/except wrapped.** A buggy email template or an SMTP outage must never break the application's submit or review flow. AD-13 makes this a project-wide rule.
3. **Provisioning belongs in its own module, imported lazily by the router.** Concentrating the "approved application → active partner" sequence in one function makes it testable without a router and avoids drift if future endpoints also create partners. AD-12 captures the rule.
4. **The pre-sprint git hygiene block in CLAUDE.md must exclude `Documentation/`** (FPRM-88). A bare `git clean -fd` deletes the prompt currently being executed.

### Known follow-ups for Sprint 7

1. **Alembic migrations 010 and 011 must run on Railway PostgreSQL** before any Sprint 6 endpoint will work in production. The Sprint 2 Railway start command (`alembic upgrade head && uvicorn ...`) should apply them automatically — verify after first Sprint 6 deploy.
2. **SMTP env vars must be set on Railway** for real emails to send. Without them the backend logs notifications to stdout (no crash). Required vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `CHANNEL_OPS_EMAIL`, `FRONTEND_URL`.
3. **FPRM-89 (`actor_id == "None"`)** still open — cosmetic fix to coerce the str("None") path in the audit logger.
4. **Application review page** does not yet persist the internal-only reviewer notes; those live in component state. A `reviewer_notes` PATCH endpoint is queued for a later sprint.
5. **Carry-forward:** in-memory token blacklist, password-reset email backend, SonarCloud configuration.



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

---

## Sprint 7 — Partner Portal Shell & Activation (Phase 2 closeout)

**Started:** 2026-05-16
**Closed:** 2026-05-16 (single-day intensive)
**Fix Version ID:** `10566`
**Native Sprint ID:** `539`
**Phase 2 epic:** FPRM-74 — Partner Registration & Onboarding (now complete)

### Sprint 7 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-105 | Partner portal shell and navigation | Done | #47 | `PartnerPortalLayout`, `Login`, `AcceptInvite`, `PartnerHome`. Nested `/portal/*` routes guarded by `ProtectedRoute(partner_user, partner_admin)`. Role-based redirect on login. Token stored in `localStorage['token']`. |
| FPRM-106 | Partner profile page | Done | #48 | New `partner_profiles_router` with `GET+PATCH /partner-profiles/{partner_org_id}`, `calculate_profile_completeness` helper, audit logging, activation recalc stub. Frontend page adapts to `/portal/profile` (self-service) and `/internal/partners/:id/profile` (channel team). Bundles **FPRM-119** JWT fix. |
| FPRM-107 | Activation checklist | Done | #49 | New `PartnerActivationChecklist` model + migration 012 + `backend/activation.py` with `recalculate_activation`. `GET+POST /partners/{id}/activation*` endpoints. Provisioning extended to create the all-False row. `ActivationChecklist.jsx` widget integrated into `PartnerHome`. Encodes AD-14. |
| FPRM-108 | Partner documents portal page | Done | #50 | No new endpoints (Sprint 4 router already had them). `PATCH /partners/{id}/documents/{doc_id}` now calls `recalculate_activation` when status flips to `approved`. New `PartnerDocuments.jsx` with partner upload + internal approve/reject (with reject-notes modal). |
| FPRM-109 | Sprint 7 docs and Phase 2 closeout | Done | (this PR) | PROJECT_CONTEXT.md endpoints / table / component tree / AD-14 / AD-15. CLAUDE.md `Current state` line refreshed (was still on Sprint 5), Sprint 4–7 IDs added, AD-8..AD-15 summaries added to the at-a-glance list. CLAUDE_HISTORY.md gains this entry + the Phase 2 complete marker + Phase 3 readiness note. Documentation/RUNBOOK.md (local, not in git) gains the Phase 2 happy-path validation section. |

All 9 sub-tasks (FPRM-110..FPRM-118) closed Done.

### Sprint 7 bugs — discovered and fixed in-sprint

| Key | Bug | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-119 | JWT payload and `/auth/me` omit `partner_org_id` — partner portal breaks on refresh | Done | #48 (bundled with FPRM-106) | Discovered while wiring Story 1's `PartnerPortalLayout`. The Sprint 6 default `create_access_token({sub, email, role})` lost `partner_org_id`, so `PartnerPortalLayout` decoded the JWT and got `undefined`. Fix: `_token_payload(user)` helper in `auth_router.py`, used by login/refresh/accept-invite; `/auth/me` returns it too. Old tokens still validate — the claim is just absent and the frontend falls back to `/auth/me`. |
| FPRM-104 | Endpoints using `_user_from_bearer` cannot be tested via `dependency_overrides` | To Do | — | Tech debt ticket filed at Phase A; parked Low. Affected endpoints (timeline, messages) still work with real JWTs in tests. Carries to a later sprint when the affected routers are next touched. |

### What landed on `main` during Sprint 7

- `backend/models.py` — adds `PartnerActivationChecklist` (Uuid PK, unique `partner_org_id` FK, six bool flags + `activated_at` + `updated_at`)
- `backend/alembic/versions/012_create_partner_activation_checklists.py` — creates the new table with Postgres-native types and a unique constraint on `partner_org_id`
- `backend/activation.py` (new) — `recalculate_activation(db, partner_org_id)` is the single source of truth (AD-14)
- `backend/provisioning.py` — `provision_partner_from_application` now creates the all-False checklist row alongside the org/profile/invite
- `backend/routers/partner_profiles_router.py` (new) — `GET+PATCH /partner-profiles/{partner_org_id}` keyed by org id (1:1 with profiles, ergonomic for the frontend), audit logged as `partner_profile.update`
- `backend/routers/partners_router.py` — adds `GET /partners/{id}/activation` (auto-initialises checklist on first read) and `POST /partners/{id}/activation/recalculate` (internal-only). `PATCH /partners/{id}` now calls recalc when `contract_start_date` changes
- `backend/routers/documents_router.py` — `PATCH` calls `recalculate_activation` when status flips to `approved` (no recalc on rejection)
- `backend/routers/auth_router.py` — `_token_payload(user)` shared helper threads `partner_org_id` through JWT at login/refresh/accept-invite; `GET /auth/me` returns `partner_org_id` (FPRM-119)
- `backend/main.py` — registers `partner_profiles_router`
- `backend/tests/test_partner_profiles.py` (new) — 13 cases (completeness helper, GET tenant matrix, PATCH update/recalc/forbidden/audit/unknown-fields)
- `backend/tests/test_auth_partner_org_id.py` (new) — 4 cases proving JWT and `/auth/me` carry `partner_org_id`
- `backend/tests/test_activation.py` (new) — 15 cases (10 recalc unit tests, 5 endpoint tests)
- `backend/tests/test_documents_activation.py` (new) — 3 cases verifying document approval triggers checklist recalc
- `backend/tests/test_provisioning.py` — extended with `test_provisioning_creates_activation_checklist` and an assertion in the approve-endpoint test
- `frontend/src/layouts/PartnerPortalLayout.jsx` (new) — authenticated partner shell
- `frontend/src/pages/Login.jsx`, `AcceptInvite.jsx`, `PartnerHome.jsx`, `PartnerProfile.jsx`, `PartnerDocuments.jsx` (all new)
- `frontend/src/components/ActivationChecklist.jsx` (new)
- `frontend/src/App.jsx` — adds `/login`, `/accept-invite`, nested `/portal/{home,profile,documents}`, `/internal/partners/:id/{profile,documents}`
- `PROJECT_CONTEXT.md` — Section 1 adds Sprint 7 endpoints; Section 2 documents `partner_activation_checklists` + nullable refresh of `/auth/me`; Section 3 frontend tree adds the new layout + components + pages; Section 6 introduces AD-14 (activation recalc) and AD-15 (role-based route guards)
- `CLAUDE.md` — `Current state` line refreshed, Sprint 4–7 IDs added to the configuration table, AD-8..AD-15 summaries added to the at-a-glance list, tech debt section updated (adds FPRM-89, FPRM-104, SMTP env var pending)
- `CLAUDE_HISTORY.md` — this Sprint 7 entry + Phase 2 complete marker + Phase 3 readiness note

### API endpoint count

Sprint 7 adds 4 new endpoints (`GET+PATCH /partner-profiles/{id}`, `GET+POST /partners/{id}/activation*`). The total surface area is now **45 endpoints**.

### Sprint 7 lessons

1. **JWT payload must include `partner_org_id` from day one of any portal that reads it client-side.** The Sprint 6 default `create_access_token({sub, email, role})` omitted it, leaving Story 1's `PartnerPortalLayout` reading `undefined`. The fix bundled into Story 2 (FPRM-119) is small but the discovery was costly. Future stories that introduce new partner-side or org-aware claims should add them to the JWT helper, not to individual endpoints.
2. **Activation recalc belongs in a single function, called from every place that touches the inputs.** Spreading the rules across the three call sites (profile update, document approval, contract date change) would have invited drift — by Sprint 10's training integration, half of them would have forgotten the recalc. Encoded as AD-14.
3. **PartnerProfile endpoints key by `partner_org_id`, not the profile's own UUID.** The 1:1 relationship makes the org id the natural key, the frontend already has it from the JWT, and the internal `/internal/partners/:id/profile` route shares the same `:id` shape as the org-level routes. Documented in `partner_profiles_router.py`.
4. **`Story 2 → Story 3` lazy import handoff worked cleanly.** Story 2's PATCH `partner-profiles/{id}` wrapped the `from activation import recalculate_activation` call in `try/except`, so the endpoint shipped before `activation.py` existed and started recalculating as soon as Story 3 (PR #49) merged. The Sprint 6 pattern (AD-12 provisioning lazy import) ports cleanly to other call sites.
5. **Cross-story App.jsx changes need to land routes incrementally.** Story 1 registered only `/portal/home`; Story 2 added `/portal/profile`; Story 4 added `/portal/documents`. Registering all five routes in Story 1 would have broken the Vite build until the matching page files existed (CI is backend-only and would not have caught it, but Railway's frontend build would have failed on the first merge). The incremental approach kept every PR independently mergeable.

### Phase 2 — complete

| Sprint | Theme | Stories | Points | Key delivery |
|---|---|---|---|---|
| 5 | Partner Registration | 6 | 18 | Public application form + `partner_applications` table + draft-token pattern (AD-11) |
| 6 | Internal Review Workflow | 5 | 18 | Approve/reject/info-required + message thread + partner provisioning (AD-12) + email lifecycle (AD-13) |
| 7 | Portal Shell + Activation | 5 | 16 | Authenticated partner portal + profile/documents/activation pages + activation gate (AD-14) + role-based routing (AD-15) |
| **Total** | **Phase 2** | **16** | **52** | Partner onboarding end-to-end: application → approval → invite → portal → activation |

### Phase 3 readiness note

Sprint 8 begins **Deal Registration** (Phase 3). Pre-implementation notes:

1. **New tables required:**
   - `deal_registrations` — `id`, `partner_org_id` (FK to `partner_organizations.id` — provisioned by Sprint 6's `provision_partner_from_application`), customer info, deal size, requested commission type, conflict-check fields, status, created/submitted timestamps
   - `conflict_check_results` — referenced by `deal_registrations` for the auto-conflict check (similar deal already registered by another partner?)
   - `deal_collaboration_threads` (proposed) — internal review + partner clarification thread on a deal; conceptually parallel to `partner_application_messages` from Sprint 6
2. **Activation gate.** Deal-registration endpoints (`POST /deal-registrations`) must check `partner_activation_checklists.activation_complete = True` for the submitting `partner_org_id` before accepting the request. Return 412 Precondition Failed (or similar) with a pointer to the partner's activation checklist if not yet activated.
3. **Commission lookup ties to `commission_structures`.** Sprint 4 / FPRM-58 seeded 24 commission rows. Deal registration should resolve the applicable row from `(partner_category_code, commission_type, year)` at submission time and snapshot the percentage on the deal record (so later commission table changes do not retroactively alter the deal).
4. **Frontend.** The disabled `Register a Deal` tile on `PartnerHome` becomes live. New routes under `/portal/deals/*`. Internal queue under `/internal/deals` — likely a parallel of `ApplicationQueue` from Sprint 5.

### Known follow-ups for Sprint 8

1. **Phase 3 ticket set must be created in a planning session before Sprint 8 starts.**
2. **`FPRM-89` (`actor_id == "None"`)** still parked Low. Carry to Phase 3 or fix when next touching `audit.py`.
3. **`FPRM-104` (`_user_from_bearer` testability)** still parked Low. Affected endpoints (timeline, messages) carry forward.
4. **SMTP env vars on Railway** — set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `CHANNEL_OPS_EMAIL`, `FRONTEND_URL` on `fracttal-prm-backend` to switch lifecycle notifications from stdout-only to real email. No code change.
5. **Phase 2 happy-path validation** — run `Documentation/RUNBOOK.md` § 11 (added in this PR) end-to-end against production before opening Sprint 8.
6. **Carry-forward:** in-memory token blacklist, password-reset email backend, SonarCloud configuration.

---

## Sprint 8 — UI Polish + Deal Registration Foundation (Phase 3 kick-off)

**Started:** 2026-05-17
**Closed:** 2026-05-17 (single-day intensive)
**Fix Version ID:** `10599`
**Native Sprint ID:** `572`
**Phase 3 epic:** FPRM-121 — Deal Registration

### Sprint 8 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-122 | UI polish — apply Fracttal One design language to portal components | Done | #53 | New `frontend/src/styles/tokens.css` (Inter + #1A6EBB + utility classes for buttons/cards/badges/tables/modals/floating-label inputs/portal shell/tiles/progress/checklist). PartnerPortalLayout, Login, AcceptInvite, PartnerHome, PartnerProfile, PartnerDocuments, ActivationChecklist all restyled. Sidebar nav adds Register a Deal / My Pipeline (live) and Commissions/Training/Assets/Support (disabled). Dashboard "Register a Deal" tile unlocked and routes to `/portal/deals/new` (page lands in Story 4). |
| FPRM-125 | DealRegistration backend model and migration | Done | #54 | `DealRegistration` model in `models.py` (Uuid PK + FK to `partner_organizations`/`commission_structures`/`users`, status string defaulting to draft, conflict_status defaulting to not_checked, commission snapshot fields, audit/lifecycle timestamps, composite index on `(partner_org_id, status)`). Migration 013 with `gen_random_uuid()` + `now()` Postgres-native defaults. 8 new model tests. |
| FPRM-128 | Deal registration submission API | Done | #55 | New `routers/deal_registrations_router.py` with `POST/GET/PATCH/DELETE /deal-registrations` + `POST /deal-registrations/{id}/submit`. Activation gate on create returns `412 {detail, activation_url}` when checklist incomplete or missing. Tenant isolation (partner_admin own only, internal roles see all). Commission snapshot on submit resolves `(partner_category_code, commission_type, year_1)`; missing match leaves snapshot null. 13 router tests. |
| FPRM-131 | Deal registration form — partner portal frontend | Done | #56 | `DealRegistrationForm.jsx` two-section floating-label form at `/portal/deals/new` and `/portal/deals/:id/edit`, Save-as-draft + Submit. `DealList.jsx` partner pipeline at `/portal/deals` with status badges, USD formatting, empty state, and toast on successful submit. App.jsx wires three new routes nested under PartnerPortalLayout. |
| FPRM-134 | Internal deal queue | Done | #57 | Added 4 internal endpoints to `deal_registrations_router.py`: `GET /internal/deals`, `POST /internal/deals/{id}/start-review`, `POST /internal/deals/{id}/approve`, `POST /internal/deals/{id}/reject` — review roles only, approve/reject require `review_notes`. Frontend `DealQueue.jsx` at `/internal/deals` with filter tabs, status badges, per-row context actions, review modal. 8 new endpoint tests. |

All 10 sub-tasks (FPRM-123/124, 126/127, 129/130, 132/133, 135/136) closed Done.

### Sprint 8 bugs

None — Sprint 8 ran clean with no in-sprint bug tickets.

### What landed on `main` during Sprint 8

- `frontend/src/styles/tokens.css` (new) — Fracttal One design system
- `frontend/src/main.jsx` — imports `tokens.css`
- `frontend/src/layouts/PartnerPortalLayout.jsx` — restyled with `.fp-shell`, icon + label sidebar, top breadcrumb + actions header
- `frontend/src/pages/Login.jsx`, `AcceptInvite.jsx`, `PartnerHome.jsx`, `PartnerProfile.jsx`, `PartnerDocuments.jsx`, `components/ActivationChecklist.jsx` — restyled
- `frontend/src/pages/DealRegistrationForm.jsx` (new)
- `frontend/src/pages/DealList.jsx` (new)
- `frontend/src/pages/DealQueue.jsx` (new)
- `frontend/src/App.jsx` — adds `/portal/deals`, `/portal/deals/new`, `/portal/deals/:id/edit`, `/internal/deals`
- `backend/models.py` — adds `DealRegistration` model (and `Float`, `Index` to imports)
- `backend/alembic/versions/013_create_deal_registrations.py` (new)
- `backend/routers/deal_registrations_router.py` (new) — partner-facing CRUD + submit + internal review endpoints
- `backend/main.py` — registers `deal_registrations_router`
- `backend/tests/test_deal_registration_model.py` (new) — 8 model tests
- `backend/tests/test_deal_registrations.py` (new) — 26 router tests (18 partner-facing + 8 internal review)
- `PROJECT_CONTEXT.md` — Section 1 endpoints + Section 2 schema + Section 3 frontend tree updated
- `CLAUDE.md` — Current state line refreshed, Sprint 8 IDs added
- `CLAUDE_HISTORY.md` — this entry

### API endpoint count

Sprint 8 adds **10 new endpoints** across `/deal-registrations/*` and `/internal/deals/*`. Total surface area is now **55 endpoints**.

### Sprint 8 test count

Backend ends Sprint 8 at **228 tests passing** (Sprint 7 baseline 194 + 34 new model & router tests).

### Sprint 8 lessons

1. **Fracttal One tokens are a one-time investment that pays off immediately.** Story 1 landed before any deal-registration UI so Stories 4 and 5 could compose new pages purely from utility classes (`.fp-card`, `.fp-btn--primary`, `.fp-field`, `.fp-table`, `.fp-modal`) — no inline styling needed. Future internal pages (Sprint 9 deal detail, Sprint 10 commission rates) can do the same. The CSS-custom-property approach also lets the whole palette flip cheaply if branding changes.
2. **Activation gate belongs on `create`, not `submit`.** Forcing the gate at draft creation prevents partners from accumulating unsubmitted drafts before they are active. Once active, drafts flow freely and only the standard tenant + status guards apply. The 412 response shape (`{detail, activation_url}`) lets the frontend show a deep-link banner without parsing the error text.
3. **Commission snapshot is best-effort, not load-bearing.** The form's commission_type vocabulary (`reseller`, `referral`) does not match `commission_structures.commission_type` enum values (`autonomous_sell` etc) by design — Sprint 10 will surface available rates to partners and Sprint 11 will rationalise the vocabulary. For Sprint 8, a missing match silently leaves `commission_rate_snapshot` null and `_snapshot_commission` never raises, so a malformed deal cannot block submission.
4. **Single router file, no prefix, full paths — the `/internal/deals/*` and `/deal-registrations/*` endpoints live in the same `deal_registrations_router.py`.** Using `APIRouter(tags=...)` without a `prefix` lets each handler declare its full path. This was simpler than spinning up a second router file just to host the four internal endpoints, and tests can exercise both surfaces against the same `db_session` fixture.
5. **Lazy import of `recalculate_activation` is the right escape hatch.** Story 1's UI changes shipped before Story 3 even had the chance to look at `activation.py`. The `try: from activation import ...` pattern in `partner_profiles_router` (from Sprint 7) keeps stories independently mergeable even when call sites and helpers land in different PRs. Sprint 8 didn't need this pattern, but it remains the canonical hand-off shape (encoded in AD-12 / AD-14).
6. **Internal endpoints should not share the partner activation gate.** `GET /internal/deals` and `POST /internal/deals/{id}/{start-review,approve,reject}` deliberately bypass the activation check — internal users review *any* partner's deal regardless of that partner's activation state. The gate is partner-scoped (own-org create only), not a global pre-condition.

### Known follow-ups for Sprint 9

1. **Sprint 9 (Deal Review Workflow & Collaboration Thread)** is next. Phase 3 Jira tickets doc has the full sprint-9 spec (FPRM_Phase3_Jira_Tickets.md): `DealMessage` model + thread API, `DealDetail` page (partner + internal), info_required resubmit flow. New tables: `deal_messages` (migration 014).
2. **`FPRM-89` (`actor_id == "None"`)** still parked Low.
3. **`FPRM-104` (`_user_from_bearer` testability)** still parked Low.
4. **SMTP env vars on Railway** — still not set; lifecycle notifications still fall back to stdout. No code change required. Confirmed during Sprint 8 closeout that this is harmless for the deal-registration path because Sprint 8 introduces no new email side-effects.
5. **Phase 3A happy-path validation** — Sprint 9 closeout (FPRM-129 in the Phase 3 ticket doc) will add a `RUNBOOK.md` § for the full submit → start-review → request-info → resubmit → approve flow. Sprint 8 closeout does not yet add a RUNBOOK section because the Phase 3 review flow lands incrementally over Sprints 8 and 9.
6. **Carry-forward:** in-memory token blacklist, password-reset email backend, SonarCloud configuration.

### Inter-sprint hotfixes (Sprint 8 closeout → Sprint 9 start)

| Key | Bug | PR | Notes |
|---|---|---|---|
| FPRM-137 | `partner_documents` missing `rejection_reason` + `info_request_message` columns (model included them, DB did not) | #59 | Migration 014 adds the two TEXT columns; idempotent. |
| FPRM-138 | `commission_structures.commission_type` PG enum rejects deal-submitted values like "reseller" with 500 (InvalidTextRepresentation) | #60 | Migration 015 converts the column to VARCHAR + drops the enum. Aligns with `deal_registrations.commission_type` being plain string. Pattern is now codified — any future broadening of a Postgres enum used as a join target should convert to VARCHAR rather than ALTER TYPE add values. |

---

## Sprint 9 — Deal Review Workflow + Collaboration Thread + Admin Configurability

**Started:** 2026-05-17
**Closed:** 2026-05-17 (single-day intensive)
**Fix Version ID:** `10632`
**Native Sprint ID:** `605`
**Phase 3 epic:** FPRM-121 — Deal Registration

### Sprint 9 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-139 | Deal collaboration thread model and API | Done | #61 | `DealMessage` model + migration 016 (`deal_messages`, FK to `deal_registrations`/`users`, index on `(deal_id, created_at)`); `GET/POST /deal-registrations/{id}/messages`; `POST /internal/deals/{id}/request-info` posts the reviewer note inline; existing submit already accepted `info_required → submitted`. 13 new tests. |
| FPRM-140 | Deal detail page — partner portal | Done | #62 | `DealDetail.jsx` at `/portal/deals/:id`; read-only fields, status banners, collab thread, info_required → message + resubmit. `DealList.jsx` deal name now links to detail; draft state shows "Edit draft" → existing form. |
| FPRM-141 | Deal detail page — internal review | Done | #63 | `InternalDealDetail.jsx` at `/internal/deals/:id`; commission snapshot + conflict status (read-only) + always-on thread + status-sensitive Quick Actions (Start Review / Request Info / Approve / Reject). `DealQueue.jsx` inline approve/reject modals removed; rows link to detail; Start Review kept inline. |
| FPRM-142 | Sprint 9 docs and Phase 3A closeout | Done | (this PR) | PROJECT_CONTEXT.md (Sections 1, 2, 3) updated; CLAUDE.md `Current state` + sprint IDs table; CLAUDE_HISTORY.md gains this entry; RUNBOOK.md gains §12 Phase 3A happy-path validation. |
| FPRM-143 | Deal Queue shows truncated UUID instead of partner org legal name | Done (Bug) | #64 | `_serialize_with_org()` + `_bulk_org_names()` add `partner_legal_name` to single-deal + list responses. Bulk lookup avoids N+1. 3 new tests. |
| FPRM-144 | Document types admin-configurable | Done | #65 | `DocumentTypeConfig` model + migration 017 (table + seed of 10 original values + ENUM→VARCHAR conversion). `GET /config/document-types` (public), `POST/PATCH /config/document-types/{id}` (system_admin / channel_ops_admin). `documents_router.upload_document` validates against the DB table with a legacy-enum fallback for migration safety. 9 new tests. |
| FPRM-145 | `baseline_training_complete` has no set endpoint — activation checklist stuck | Done | #66 | `POST /partners/{id}/activation/training-complete` and `training-reset` (channel_manager / channel_ops_admin / system_admin only). `activation.recalculate_activation` now (a) preserves whatever the endpoints set, and (b) **includes the flag in the `activation_complete` gate**. Migration 018 backfills `baseline_training_complete=true` for partners currently `activation_complete=true` so the gate change does not deactivate anyone. Existing activation/document tests updated. 8 new endpoint tests. |

All 10 subtasks (FPRM-146..FPRM-155) closed Done.

### What landed on `main` during Sprint 9

- `backend/models.py` — adds `DealMessage`, `DocumentTypeConfig`. `PartnerDocument.document_type` now plain String (was PG enum) — see migration 017.
- `backend/routers/deal_registrations_router.py` — `GET/POST /deal-registrations/{id}/messages`, `POST /internal/deals/{id}/request-info`, `_serialize_with_org` / `_bulk_org_names` for `partner_legal_name`.
- `backend/routers/config_router.py` — three new document-type endpoints.
- `backend/routers/documents_router.py` — upload validates against `document_types` table (legacy-enum fallback if table empty).
- `backend/routers/partners_router.py` — `_set_training` helper + `POST /partners/{id}/activation/training-complete | training-reset`.
- `backend/activation.py` — preserves `baseline_training_complete`; gate now includes it.
- `backend/alembic/versions/016_create_deal_messages.py` (new).
- `backend/alembic/versions/017_create_document_types_config.py` (new) — creates table + seed + ENUM→VARCHAR conversion.
- `backend/alembic/versions/018_backfill_baseline_training.py` (new) — one-line UPDATE.
- `backend/tests/test_deal_messages.py` (13 cases), `test_deal_partner_legal_name.py` (3 cases), `test_document_types_config.py` (9 cases), `test_training_complete.py` (8 cases). `test_activation.py` + `test_documents_activation.py` updated for new gate.
- `frontend/src/pages/DealDetail.jsx` (new), `InternalDealDetail.jsx` (new).
- `frontend/src/pages/DealList.jsx`, `DealQueue.jsx` — link to detail, simplified row actions.
- `frontend/src/App.jsx` — `/portal/deals/:id` + `/internal/deals/:id` routes.
- `PROJECT_CONTEXT.md` — Sections 1, 2, 3 updated.
- `CLAUDE.md` — Current state line refreshed; Sprint 9 IDs added.
- `CLAUDE_HISTORY.md` — this entry.
- `RUNBOOK.md` — §12 Phase 3A happy-path validation added.

### API endpoint count

Sprint 9 adds **8 new endpoints**:
- `GET /deal-registrations/{id}/messages`
- `POST /deal-registrations/{id}/messages`
- `POST /internal/deals/{id}/request-info`
- `GET /config/document-types`
- `POST /config/document-types`
- `PATCH /config/document-types/{id}`
- `POST /partners/{id}/activation/training-complete`
- `POST /partners/{id}/activation/training-reset`

Total surface area is now **63 endpoints**.

### Sprint 9 test count

Backend ends Sprint 9 at **261 tests passing** (Sprint 8 baseline 228 + 33 new across deal_messages, deal_partner_legal_name, document_types_config, training_complete — plus updated activation/documents_activation tests).

### Sprint 9 lessons

1. **Backfill migrations are mandatory when gate logic tightens.** FPRM-145 added `baseline_training_complete` to the activation gate. Without migration 018, the next recalc against any currently-active partner would have flipped them back to `activation_complete=False`. Pattern: when an activation rule changes from "ignored" to "required", always backfill the prerequisite state for entities currently passing the gate. Cheap one-line `UPDATE … WHERE` statements prevent silent regressions in production data.
2. **Enum → VARCHAR conversions follow a stable recipe.** FPRM-138 migration 015 introduced the pattern (commission_type). FPRM-144 migration 017 repeated it (document_type) without re-discovery. The recipe: `ALTER COLUMN … TYPE VARCHAR USING …::text` then `DROP TYPE`. Anywhere a PG enum is used as a *join target* with a value-source that might broaden (form field, admin config table), prefer VARCHAR from the start. Codified.
3. **N+1 avoidance in serialisers is cheap when done up-front.** `_bulk_org_names` does one IN-query for the whole page; trivially small. Adding `partner_legal_name` row-by-row would have been a hidden N+1 for the deal queue. The price of "one query per page" is paid before the first regression. Pattern is reusable for any list endpoint that needs to join one related-name field.
4. **Frontend graceful fallbacks insulate against PR ordering.** Story 3 (`InternalDealDetail.jsx`) was merged before Addendum A (`partner_legal_name` backend). The frontend reads `deal.partner_legal_name || deal.partner_org_id` — when the field was missing the page still rendered with the UUID; after Addendum A landed, the same code instantly upgraded. No coordination across PRs was needed.
5. **Existing routers absorb new endpoints best.** All three thread + request-info endpoints + the `partner_legal_name` join landed inside the existing `deal_registrations_router.py`. Creating a `deal_messages_router.py` would have meant a new file, new `app.include_router`, and split test fixtures. AD-style observation: when new endpoints share dependency + tenant guards with an existing router, keep them co-located.

### Known follow-ups for Sprint 10

1. **Sprint 10 (Conflict Checking + Commission Visibility — Phase 3 closeout)** is next. New backend module `conflict_checker.py` wires into `POST /deal-registrations/{id}/submit`. Conflict override button replaces the `{/* TODO Sprint 10 */}` comment in `InternalDealDetail.jsx`. Commission rate visibility for partners (new portal view of `commission_structures`).
2. **`FPRM-89` (`actor_id == "None"`)** still parked Low.
3. **`FPRM-104` (`_user_from_bearer` testability)** still parked Low.
4. **SMTP env vars on Railway** — still not set; lifecycle notifications still fall back to stdout. No code change required.
5. **Phase 3A happy-path validation** — RUNBOOK.md §12 must be run against production before Sprint 10 begins. Validates submit → start-review → request-info → resubmit → approve end-to-end.
6. **Carry-forward:** in-memory token blacklist, password-reset email backend, SonarCloud configuration.

---

## Sprint 10 — Conflict Checking + Commission Visibility (Phase 3 closeout)

**Started:** 2026-05-18
**Closed:** 2026-05-18 (single-day intensive)
**Fix Version ID:** `10665`
**Native Sprint ID:** `638`
**Phase 3 epic:** FPRM-121 — Deal Registration (Phase 3)

### Sprint 10 stories — outcome

| Key | Type | Story | Status | PR | Notes |
|---|---|---|---|---|---|
| FPRM-156 | Bug | `documents_uploaded` flag never flips despite approved documents | Done | #69 | `activation.recalculate_activation` simplified — gate now flips True when the partner has at least one approved `PartnerDocument`. The earlier "fiscal_id AND id_legal_representative" rule was incompatible with FPRM-144's admin-configurable document_types. Existing `test_activation.py` / `test_documents_activation.py` updated; added `test_documents_uploaded_regression_single_approved`. Phase 3A production validation run end-to-end against test partner `b223c3b0-…6f076811e518` — see results table below. |
| FPRM-157 | Story | Automatic conflict checking on deal submission | Done | #70 | New `backend/conflict_checker.py` standalone utility — no FastAPI session creation, returns a `ConflictResult` dataclass. Wired into `POST /deal-registrations/{id}/submit` after the status flip (best-effort, try/except wrapped). New `POST /internal/deals/{id}/override-conflict` — channel_manager + system_admin only (channel_ops_admin explicitly excluded). 14 new tests using StaticPool in-memory sqlite. |
| FPRM-158 | Story | Commission rate visibility in partner portal | Done | #71 | New `GET /partners/{id}/commission-rates` endpoint with own-org tenant guard for partner_admin. New `CommissionRates.jsx` page at `/portal/commissions` inside `PartnerPortalLayout` (Commissions nav item enabled). `DealRegistrationForm.jsx`: commission_type dropdown vocabulary aligned with `commission_structures` enum (autonomous_sell/indirect_sell/direct_sell/co_sell_shared) — earlier reseller/referral values could not match any row. Helper text below the dropdown shows "Applicable rate (Year 1): X%" or "Rate not on file…" or silently omits on fetch failure. 6 new endpoint tests. |
| FPRM-159 | Story | Conflict status display — frontend | Done | #72 | Replaces the `{/* TODO Sprint 10: conflict override */}` placeholder in `InternalDealDetail.jsx`. Conflict badges: `not_checked` (grey "Not Checked" + helper text), `clear` (green "Clear ✅"), `conflict_detected` (red "Conflict Detected ⚠️" + notes + Override button). `ConflictOverrideModal` requires `override_notes` (min. 10 chars), POSTs to override-conflict endpoint, surfaces a transient "Conflict overridden" toast. `DealDetail.jsx` verified to expose no conflict fields to partners. |
| FPRM-160 | Story | Sprint 10 docs and Phase 3 closeout | Done | (this PR) | PROJECT_CONTEXT.md (Sections 1, 2, 3) updated; CLAUDE.md current-state + sprint IDs table; CLAUDE_HISTORY.md gains this entry + Phase 3 summary + Phase 4 readiness note; RUNBOOK.md gains §13 Phase 3 full happy-path validation. |

All 11 subtasks (FPRM-161..FPRM-171) closed Done.

### What landed on `main` during Sprint 10

- `backend/conflict_checker.py` (new) — standalone utility with `ConflictResult` dataclass and `check_deal_conflict(db, deal_id)`.
- `backend/activation.py` — `documents_uploaded` rule simplified to "≥1 approved document"; legacy `REQUIRED_DOCUMENT_TYPES` constant removed.
- `backend/routers/deal_registrations_router.py` — submit endpoint runs conflict check after status flip; `POST /internal/deals/{id}/override-conflict` (channel_manager + system_admin only).
- `backend/routers/partners_router.py` — `GET /{partner_id}/commission-rates` (partner_admin own-org or internal).
- `backend/tests/test_conflict_checker.py` (new, 14 cases), `test_commission_rates.py` (new, 6 cases). `test_activation.py` and `test_documents_activation.py` updated for the simpler `documents_uploaded` rule.
- `frontend/src/pages/CommissionRates.jsx` (new).
- `frontend/src/pages/DealRegistrationForm.jsx` — commission_type vocabulary aligned + rate preview helper text.
- `frontend/src/pages/InternalDealDetail.jsx` — conflict badge spec'd labels + Override Conflict button + `ConflictOverrideModal` + toast.
- `frontend/src/layouts/PartnerPortalLayout.jsx` — Commissions nav item enabled.
- `frontend/src/App.jsx` — `/portal/commissions` route inside the partner layout.
- `PROJECT_CONTEXT.md` — Sections 1, 2, 3 updated.
- `CLAUDE.md` — Current state line refreshed; Sprint 10 IDs added.
- `CLAUDE_HISTORY.md` — this entry + Phase 3 complete marker + Phase 4 readiness note.
- `RUNBOOK.md` — §13 Phase 3 full happy-path validation added.

### Phase 3A validation results (production, after FPRM-156 deploy)

Test partner: `b223c3b0-623e-405c-b056-6f076811e518`. Validation date: 2026-05-18.

| Step | Status | Detail |
|---|---|---|
| admin login | OK | system_admin token obtained |
| recalculate after deploy | OK | `documents_uploaded=True`, `activation_complete=True`, `activated_at=2026-05-18T13:30:42Z` |
| partner_admin invite | OK | new email `s10val+…@phase3atest.com` |
| accept invite | OK | partner_admin JWT minted |
| create deal | OK | status=draft |
| submit deal | OK | status=submitted, `commission_rate_snapshot=50.0` |
| start-review | OK | status=under_review |
| request-info | OK | status=info_required |
| partner message | OK | message posted by partner_admin |
| resubmit | OK | status=submitted |
| start-review (2nd) | OK | status=under_review |
| approve | OK | status=approved |

End-to-end Phase 3A chain green. Conflict checker integration tested via unit + integration tests (deal submit records `conflict_status=clear` and `conflict_status=conflict_detected`).

### API endpoint count

Sprint 10 adds **2 new endpoints**:
- `GET /partners/{id}/commission-rates`
- `POST /internal/deals/{id}/override-conflict`

Total surface area is now **65 endpoints**.

### Sprint 10 test count

Backend ends Sprint 10 at **283 tests passing** (Sprint 9 baseline 261 + 22 new across conflict_checker (14) and commission_rates (6) plus 2 updated activation tests).

### Sprint 10 lessons

1. **A rule made strict-by-list dies when the list becomes pluggable.** The `documents_uploaded` gate hardcoded `{fiscal_id, id_legal_representative}`. After FPRM-144 made document_types admin-configurable, a partner whose required set was, say, `{nda, fiscal_id, articles_of_incorporation}` could never activate — a fact only the Phase 3A production validation caught. Pattern: when migrating a constraint from "fixed list" to "admin-configurable list", search for downstream guards that reference the old fixed values *in the same PR* — not the next sprint.
2. **Conflict checker as a standalone utility paid off.** `backend/conflict_checker.py` has no FastAPI dependency, no session creation, no audit-log call. It returned a dataclass; the router persisted three columns. That isolation made the 8 unit tests trivial and the integration tests minimal. Same shape as `activation.py` (AD-14) — keep recalculators / checkers in dedicated modules, never inline in routers.
3. **TestClient + in-memory SQLite needs StaticPool.** First pass with bare `:memory:` saw `OperationalError` on TestClient requests because each HTTP request opened a fresh connection to a fresh database. `poolclass=StaticPool` keeps every connection on the same in-memory DB. Codified — any future cross-row-query test module should follow `test_conflict_checker.py` / `test_commission_rates.py`.
4. **Form vocabularies that drift from backend vocabularies are silent bugs.** The deal form's commission_type dropdown shipped with `reseller`/`referral` while the seeded `commission_structures` rows used `autonomous_sell` etc. The form-side mismatch was harmless until FPRM-158 needed to *match* the user's pick against the rates table — at which point every selection returned "Rate not on file". Fix was a one-line vocabulary alignment. Lesson: when a database table is the source of truth for a dropdown, derive the dropdown from it (or at least pin the values to the same enum) rather than re-typing them client-side.
5. **Best-effort wrapping is mandatory once a write does more than one thing.** The submit endpoint persists status, snapshots commission, AND now runs the conflict checker. Any one failing must not roll back the others. `try/except` around the checker call (and the existing pattern around `recalculate_activation`) keeps the primary mutation atomic and the side effects optional. AD-13 / AD-14 generalised to: every secondary write triggered from a router belongs inside a try/except.

### Phase 3 — Complete

| Sprint | Theme | Stories | Points | Key delivery |
|---|---|---|---|---|
| 8 | UI Polish + Deal Registration Foundation | 5 | 18 | DealRegistration model + API + form + queue; Fracttal One restyle |
| 9 | Collaboration Thread + Admin Configurability | 7 | 22 | DealMessage model + thread API; DealDetail + InternalDealDetail; configurable doc types; training-complete endpoint |
| 10 | Conflict Checking + Commission Visibility | 5 | 18 | conflict_checker.py; commission rate visibility; conflict override UI; Phase 3A validation complete |
| **Total** | **Phase 3** | **17** | **58** | Deal registration end-to-end: submit → conflict check → review → approve |

Phase 3 surface area:
- DB tables added: `deal_registrations`, `deal_messages`, `document_types` (+ enum→VARCHAR conversion of `partner_documents.document_type`), `partner_activation_checklists` (Sprint 7 carried over, training-complete migration 018 in Sprint 9).
- API endpoints added across Phase 3: 65 − 38 (Sprint 7 closeout count) = **27 new endpoints** spanning deal CRUD, internal review queue, collaboration thread, document-type config, training, commission-rates, conflict override.
- Frontend pages added: `DealRegistrationForm`, `DealList`, `DealQueue`, `DealDetail`, `InternalDealDetail`, `CommissionRates`.

### Phase 4 readiness note

Phase 4 begins **Reporting & Analytics**. Pre-implementation notes:

1. **All deal data is queryable via existing endpoints — no schema changes needed for Phase 4 start.** `deal_registrations` already carries every field a dashboard tile needs (status, partner_org_id, commission_rate_snapshot, conflict_status, submitted_at, reviewed_at). Aggregation will be query-side, not schema-side.
2. **Phase 4 opening stories MUST include both home dashboards.** Modelled on the SynPro VSDC home portal design (summary tiles, KPIs, links to all key modules):
   - **Internal admin home dashboard** — summary tiles (partners by status, deals by status, applications awaiting review, conflicts pending override), KPIs (avg approval time, deals approved this month, total commission $ pipeline), quick-links to partner pipeline / deal queue / applications / commission overview.
   - **Partner admin home dashboard** — same design language, partner-scoped (own deals pipeline, own profile completeness, own activation checklist if not yet complete, own commission rates link, training / documents quick-links).
3. **Carry-forward Sprint 10 → Sprint 11+:**
   - `FPRM-89` — `actor_id == "None"` (cosmetic, parked Low).
   - `FPRM-104` — `_user_from_bearer` testability tech-debt (parked Low).
   - **SMTP env vars not yet set on Railway** — lifecycle emails fall back to stdout. No code change; ops follow-up.
   - **JWT logout blacklist is in-memory only** (multi-instance unsafe).
   - **Password-reset email backend** still logs to stdout.
   - **SonarCloud** still needs a `sonar-project.properties` + linked project.
4. **Spec generation:** `FPRM_Phase4_Jira_Tickets.md` is the planning artefact to be generated in a planning session before Sprint 11.



## Sprint 11 — Internal Shell, Dashboards & Quick Wins (Phase 4 kick-off)

**Started:** 2026-05-18
**Closed:** 2026-05-18 (single-day intensive)
**Fix Version ID:** `10698`
**Native Sprint ID:** `671`
**Phase 4 epic:** FPRM-175 — Admin Foundation & Reporting

### Sprint 11 ticket-key map

The Phase 4 planning doc predicted FPRM-175..FPRM-189 for the new stories, but Jira auto-assigns sequentially and the epic took the first available key (FPRM-175). The actual map is therefore offset by one across stories and starts at FPRM-176 for the first story:

| Planned | Actual | Type | Title |
|---|---|---|---|
| FPRM-E8 | FPRM-175 | Epic | Admin Foundation & Reporting |
| FPRM-175 | FPRM-176 | Story | Internal admin navigation shell (InternalLayout) |
| FPRM-176 | FPRM-179 | Story | Internal admin home dashboard (InternalHome) |
| FPRM-177 | FPRM-183 | Story | Partner admin home dashboard (enhanced PartnerHome) |
| FPRM-178 | FPRM-186 | Story | Forgot password UI + cancel info request |

Subtasks: FPRM-177/178 (under 176), FPRM-180/181/182 (under 179), FPRM-184/185 (under 183), FPRM-187/188/189 (under 186).

Carry-forward bugs reassigned to Sprint 11 (not recreated): FPRM-89, FPRM-104.

### Sprint 11 stories — outcome

| Key | Type | Story | Status | PR | Notes |
|---|---|---|---|---|---|
| FPRM-89 | Bug | actor_id stores "None" instead of SQL null | Done | #78 | Root cause was the serializer at `backend/routers/admin_router.py:48` (`str(item.actor_id)` → `"None"` when actor_id is NULL), not `audit.py`. `audit.py` has always passed Python `None` correctly since FPRM-44/FPRM-75. Fix mirrors the existing `object_id` pattern on the next line. Added 2 tests: one for `log_audit_event` with `actor=None` (sanity), and one TestClient test asserting the API returns JSON null. |
| FPRM-104 | Bug | _user_from_bearer testability debt | Done | #79 | Added `get_optional_bearer_user` FastAPI dependency in `auth.py` — reads the Authorization header, decodes the JWT, returns `Optional[User]`, never raises. Removed `_user_from_bearer` from `applications_router.py` and migrated all four dual-auth endpoints (`GET /applications/{id}`, `GET /applications/{id}/timeline`, `GET /applications/{id}/messages`, `POST /applications/{id}/messages`). New `test_bearer_dependency.py` proves `app.dependency_overrides[get_optional_bearer_user]` controls auth on every migrated path, including the draft_token fallback. |
| FPRM-176 | Story | Internal admin navigation shell (InternalLayout) | Done | #80 | New `frontend/src/layouts/InternalLayout.jsx` with Fracttal-branded sidebar, role-aware nav (per-item `roles` filter), mobile hamburger, role badge in the header. `App.jsx` consolidated all 7 `/internal/*` routes under one `ProtectedRoute roles={INTERNAL_ROLES} → InternalLayout` nested route. Disabled items (Partners / Users / Program Config / Reports) render as greyed "soon" placeholders. `/internal/home` placeholder route added (real dashboard in FPRM-179). |
| FPRM-179 | Story | Internal admin home dashboard (InternalHome) | Done | #81 | New router `backend/routers/dashboard_router.py` with `GET /internal/dashboard/summary` — system_admin/channel_ops_admin/channel_manager only. Returns applications / deals / partners / conflicts roll-up read from existing tables (no migrations). New `frontend/src/pages/InternalHome.jsx` — KPI tile grid (4 tiles), pipeline-this-month strip (3), partner health strip (3), quick-action buttons. Login `destinationForRole` repointed internal roles to `/internal/home`. Shape-contract test locks the response shape the frontend depends on. |
| FPRM-183 | Story | Partner admin home dashboard (enhanced PartnerHome) | Done | #82 | New endpoint `GET /partners/{id}/dashboard/summary` added to `partners_router.py` — partner_admin own-org only. Returns deals counts by status, activation `items_complete / items_total` (4 hard-coded flags), and document counts (pending/approved/rejected). `PartnerHome.jsx` upgraded with KPI tiles, activation progress widget retaining `ActivationChecklist`, and a Recent Deals panel (last 5 from `/deal-registrations?limit=5`) with status badges + "Register a Deal" CTA. |
| FPRM-186 | Story | Forgot password UI + cancel info request | Done | #83 | New public pages `ForgotPassword.jsx` (`/forgot-password`) and `ResetPassword.jsx` (`/reset-password`) wired to existing Sprint 2 endpoints `POST /auth/password-reset/request` and `POST /auth/password-reset/confirm`. Login.jsx gains "Forgot password?" link + reset-success toast. New endpoints `POST /applications/{id}/cancel-info-request` (info_required → in_review) and `POST /internal/deals/{deal_id}/cancel-info-request` (info_required → under_review, posts a system message to the thread). New buttons on `ApplicationReview.jsx` and `InternalDealDetail.jsx` (visible only when `status === 'info_required'`) with confirm-style modals. 13 new tests. |

All 10 subtasks (FPRM-177, 178, 180, 181, 182, 184, 185, 187, 188, 189) closed Done.

### What landed on `main` during Sprint 11

- `backend/routers/admin_router.py` — null-safe `actor_id` serializer (FPRM-89).
- `backend/auth.py` — new `get_optional_bearer_user` FastAPI dependency (FPRM-104).
- `backend/routers/applications_router.py` — migrated 4 dual-auth endpoints to the new dependency, removed `_user_from_bearer` (FPRM-104); added `POST /applications/{id}/cancel-info-request` (FPRM-186).
- `backend/routers/dashboard_router.py` (new) — `GET /internal/dashboard/summary` (FPRM-179).
- `backend/routers/partners_router.py` — added `GET /partners/{id}/dashboard/summary` (FPRM-183).
- `backend/routers/deal_registrations_router.py` — added `POST /internal/deals/{deal_id}/cancel-info-request` (FPRM-186).
- `backend/main.py` — registered `dashboard_router`.
- `backend/tests/` — new files `test_bearer_dependency.py` (8), `test_dashboard.py` (13), `test_partner_dashboard.py` (10), `test_cancel_info_request.py` (13); existing `test_audit.py` gains 2 new cases.
- `frontend/src/layouts/InternalLayout.jsx` (new) and `frontend/src/App.jsx` re-wrapping (FPRM-176).
- `frontend/src/pages/InternalHome.jsx` (new) (FPRM-179).
- `frontend/src/pages/Login.jsx` — internal-role redirect repointed to `/internal/home`, "Forgot password?" link, reset-success toast (FPRM-179 + FPRM-186).
- `frontend/src/pages/PartnerHome.jsx` — KPI tiles + activation widget + recent deals panel (FPRM-183).
- `frontend/src/pages/ForgotPassword.jsx`, `ResetPassword.jsx` (new) (FPRM-186).
- `frontend/src/pages/ApplicationReview.jsx`, `InternalDealDetail.jsx` — Cancel Info Request buttons + confirm modals (FPRM-186).
- `CLAUDE.md` — Current state line + Sprint 11 IDs added; FPRM-89 and FPRM-104 removed from Known Issues; new `info_request_message` debt item added.
- `CLAUDE_HISTORY.md` — this entry.
- `RUNBOOK.md` — §14 Phase 4 Sprint 11 happy-path validation added.

### API endpoint count

Sprint 11 adds **4 new endpoints**:
- `GET /internal/dashboard/summary`
- `GET /partners/{id}/dashboard/summary`
- `POST /applications/{id}/cancel-info-request`
- `POST /internal/deals/{deal_id}/cancel-info-request`

Total surface area is now **69 endpoints** (Sprint 10 baseline 65 + 4).

### Sprint 11 test count

Backend ends Sprint 11 at **332 tests passing** (Sprint 10 baseline 283 + 49 new across `test_audit.py` (+2), `test_bearer_dependency.py` (+8), `test_dashboard.py` (+13), `test_partner_dashboard.py` (+10), `test_cancel_info_request.py` (+13) + 3 historical tests added between Sprint 10 close and Sprint 11 start by FPRM-172/173/174).

### Sprint 11 lessons

1. **The Jira issue-key counter is shared across all issuetypes, including Epics.** The Phase 4 doc planned FPRM-175 = first story, but creating the epic first burnt that key — the InternalLayout story landed as FPRM-176. Predicted ticket-key tables in planning docs should be read as "ordering / themes," never as ground truth — always confirm the actual keys post-creation and record them. The actual map is captured in the ticket-key map table above.
2. **A bug's "stated" location is not always its real location.** FPRM-89's acceptance criteria called out `audit.py` for the `actor_id == "None"` issue, but `audit.py` had been correct since Sprint 2 — the visible "None" was being introduced by the serializer in `admin_router.py:48`. The cheap signal here was reading the file the AC named *and the file that produces the visible symptom*. If you only read the AC's file you would have shipped a no-op fix and called it done.
3. **Phantom attributes haunt SQLAlchemy models.** `PartnerApplication.info_request_message` is set as an in-memory attribute by the request-info endpoint but is not a Column, so SQLAlchemy does not error on `app.info_request_message = "..."`, does not persist it, AND raises `AttributeError` on read if the attribute was never assigned. The Sprint 11 cancel endpoint had to use `getattr(..., None)` to be safe. Pattern: when reading an attribute that may have been set by a sibling endpoint, never assume — always `getattr` or check `hasattr`. Discoverable only because the test fixture happened to construct rows without setting it; production rows from the request-info path would have the attribute on them.
4. **Aggregate-count tests pollute each other under module-scoped engines.** Both `test_dashboard.py` and `test_partner_dashboard.py` run multi-row count queries, so module-scoped SQLite engines (used elsewhere in the suite) leaked rows between tests and inflated counts. Per-test cleanup (`for table in reversed(Base.metadata.sorted_tables): db.execute(table.delete())` in the `db_session` fixture teardown) is the right shape for any test module that asserts aggregate state — `test_bearer_dependency.py` doesn't need it because it tests per-row behaviour.
5. **Two backend dashboard endpoints, two role guards.** `GET /internal/dashboard/summary` requires `system_admin` / `channel_ops_admin` / `channel_manager` (internal roll-up). `GET /partners/{id}/dashboard/summary` requires `partner_admin` of the same org — explicitly rejects system_admin too, because internal users have their own dashboard. Keeping these as separate endpoints with separate role checks (rather than one polymorphic endpoint that branches on caller role) made the 23 new tests trivial to express and read.
6. **Nested route + single ProtectedRoute beats N copies.** Pre-FPRM-176 every `/internal/*` route was wrapped in its own `<ProtectedRoute roles=[...]>`. The new InternalLayout pattern (parent ProtectedRoute on `/internal`, Outlet inside the layout) cut ~50 lines from App.jsx, eliminated the risk of a route being added without its guard, and gave us a single place to redirect partner roles back to `/portal/home`. PartnerPortalLayout was already on this pattern from Sprint 7 — internal lagged.

## Sprint 12 — Internal User Management + Partners List (Phase 4 continues)

**Started:** 2026-05-18
**Closed:** 2026-05-18 (single-day intensive)
**Fix Version ID:** `10731`
**Native Sprint ID:** `704`
**Phase 4 epic:** FPRM-175 — Admin Foundation & Reporting

### Sprint 12 ticket-key map

The planning prompt predicted FPRM-189..FPRM-192 for the four stories, but **bugs were created before stories** in Phase A so the bugs consumed those keys and the stories landed five higher. The actual map:

| Planned | Actual | Type     | Title |
|---------|--------|----------|-------|
| BUG-A   | FPRM-190 | Bug      | GET /partners/{id}/dashboard/summary returns 403 for system_admin |
| BUG-B   | FPRM-191 | Bug      | GET /applications?status=under_review returns 500 — enum mismatch |
| BUG-C   | FPRM-192 | Bug      | Application status enum inconsistency — in_review vs under_review |
| BUG-D   | FPRM-193 | Bug      | conflict_detected string leaking into InternalHome UI display |
| FPRM-189 | FPRM-194 | Story    | Internal user management backend |
| FPRM-190 | FPRM-198 | Story    | Internal user management UI + role permission matrix |
| FPRM-191 | FPRM-202 | Story    | Partner user management — internal admin view |
| FPRM-192 | FPRM-205 | Story    | Internal partners list page |

Subtasks landed at FPRM-195..197 (under 194), FPRM-199..201 (under 198), FPRM-203..204 (under 202), FPRM-206..207 (under 205).

### Sprint 12 stories — outcome

| Key | Type  | Story | Status | PR | Notes |
|-----|-------|-------|--------|----|-------|
| FPRM-190 | Bug   | dashboard/summary 403 for system_admin | Done | #86 | `partners_router.get_partner_dashboard_summary` now accepts `system_admin` / `channel_ops_admin` / `channel_manager` for any org; `partner_admin` still scoped to own org. The Sprint 11 test that asserted internal-role → 403 was replaced with three `*_can_view_any_org` tests. |
| FPRM-191 + FPRM-192 | Bug | ApplicationStatus enum alignment | Done | #87 | Renamed `ApplicationStatus.in_review` → `under_review` to match the deal-side vocabulary. Postgres migration 019 uses `ALTER TYPE ... RENAME VALUE` (atomic, no data-rewrite). All `ApplicationStatus.in_review` references updated across routers + tests; frontend `ApplicationQueue` / `ApplicationReview` filter strings updated. Bonus: the `?status=` filter on `GET /applications` now validates against the enum and returns 422 on unknown values instead of letting them bubble to 500. |
| FPRM-193 | Bug   | conflict_detected UI leak | Done | #88 | Replaced the hardcoded `'Unresolved conflict_detected'` sub-label in InternalHome.jsx with `'Unresolved conflicts'`. InternalDealDetail.jsx already had a proper CONFLICT_LABEL map — only this one tile slipped. |
| FPRM-194 | Story | Internal user management backend | Done | #89 | New `backend/routers/internal_users_router.py` with `/internal/users` GET (paginated + role/is_active filters), GET `/{id}`, POST `/invite` (random unguessable password + 7-day `PasswordResetToken` + welcome email via `notifications.send_email`), PATCH `/{id}/role` (blocks self-modification + demoting the last active system_admin), POST `/disable`, POST `/reactivate`. Audit events for every state change. `User` gains `last_login_at` (migration 020) populated by the `auth_router.login` happy path. 18 unit tests. |
| FPRM-198 | Story | Internal user management UI + role permission matrix | Done | #90 | `frontend/src/pages/InternalUsers.jsx` at `/internal/users` (system_admin only). Filter bar + user table with role-coloured badges (purple system_admin, blue channel_ops_admin, teal channel_manager, green sales_rep, orange sales_ops, yellow finance_approver), per-row Change Role / Disable / Reactivate, modal-driven invite. Static **Role permission matrix** rendered below the table. `Users` nav item in InternalLayout flipped from `Coming soon` to live. |
| FPRM-202 | Story | Partner user management — internal admin view | Done | #91 | New `backend/routers/internal_partner_users_router.py` (kept distinct from the pre-existing per-tenant `partner_users_router.py` to keep tenant-scoped and cross-tenant surfaces clearly separated). Endpoints under `/internal/partner-users` for `system_admin` + `channel_ops_admin`. New page `PartnerUserManagement.jsx` at `/internal/partner-users`; new **Partner Users** nav item added between Partners and Deals. 11 unit tests. |
| FPRM-205 | Story | Internal partners list page | Done | #92 | New `backend/routers/internal_partners_router.py` exposing `GET /internal/partners` (search/status/tier/category filters + page/page_size pagination + activation join). New page `InternalPartnerList.jsx` at `/internal/partners` with debounced search, filter row, status badges, activation indicator. **Partners** nav item in InternalLayout flipped from `Coming soon` to live. 7 unit tests. |

All 10 Sub-tasks (FPRM-195..197, 199..201, 203..204, 206..207) closed Done.

### What landed on `main` during Sprint 12

- `backend/models.py` — `User.last_login_at` (DateTime, nullable); `ApplicationStatus.in_review` renamed to `under_review`.
- `backend/alembic/versions/019_rename_application_in_review_to_under_review.py` — Postgres-only `ALTER TYPE ... RENAME VALUE`.
- `backend/alembic/versions/020_add_last_login_at_to_users.py` — adds the column.
- `backend/routers/auth_router.py` — stamps `user.last_login_at` on the login happy path.
- `backend/routers/applications_router.py` — every `ApplicationStatus.in_review` reference flipped to `under_review`; `cancel-info-request` now transitions to `under_review`; `?status=` filter validates against the enum (422 on unknown) instead of letting Postgres throw a 500.
- `backend/routers/dashboard_router.py` — pending_review count picks up the renamed value.
- `backend/routers/partners_router.py` — `get_partner_dashboard_summary` role guard widened (FPRM-190).
- `backend/routers/internal_users_router.py` (new) — internal user CRUD + invite + role/disable/reactivate.
- `backend/routers/internal_partner_users_router.py` (new) — cross-org partner-user admin.
- `backend/routers/internal_partners_router.py` (new) — `GET /internal/partners` with filters + pagination.
- `backend/main.py` — registers the three new routers.
- `backend/tests/test_internal_users.py` (new, 18); `test_internal_partner_users.py` (new, 11); `test_internal_partners.py` (new, 7); plus the new `test_internal_list_status_under_review_returns_200` and `test_internal_list_invalid_status_returns_422` in `test_applications.py`; assertions updated in `test_cancel_info_request.py` and `test_dashboard.py` for the renamed enum; `test_partner_dashboard.py` flipped the internal-role test to assert `200` instead of `403`.
- `frontend/src/pages/InternalUsers.jsx` (new) (FPRM-198).
- `frontend/src/pages/PartnerUserManagement.jsx` (new) (FPRM-202).
- `frontend/src/pages/InternalPartnerList.jsx` (new) (FPRM-205).
- `frontend/src/pages/InternalHome.jsx` — `'Unresolved conflict_detected'` → `'Unresolved conflicts'` (FPRM-193).
- `frontend/src/pages/ApplicationQueue.jsx`, `ApplicationReview.jsx` — `in_review` → `under_review` in colour map, label map, status filter dropdown.
- `frontend/src/layouts/InternalLayout.jsx` — Users + Partners nav items enabled; new Partner Users item; breadcrumb map updated.
- `frontend/src/App.jsx` — three new nested routes (`/internal/users`, `/internal/partner-users`, `/internal/partners`) each with its role-specific ProtectedRoute.
- `CLAUDE.md` — Current state line + Sprint 12 IDs + 372-tests count.
- `CLAUDE_HISTORY.md` — this entry.

### API endpoint count

Sprint 12 adds **12 new endpoints**:

- `GET /internal/users`
- `GET /internal/users/{user_id}`
- `POST /internal/users/invite`
- `PATCH /internal/users/{user_id}/role`
- `POST /internal/users/{user_id}/disable`
- `POST /internal/users/{user_id}/reactivate`
- `GET /internal/partner-users`
- `PATCH /internal/partner-users/{user_id}/role`
- `POST /internal/partner-users/{user_id}/disable`
- `POST /internal/partner-users/{user_id}/reactivate`
- `POST /internal/partner-users/invite`
- `GET /internal/partners`

Total surface area is now **81 endpoints** (Sprint 11 baseline 69 + 12).

### Sprint 12 test count

Backend ends Sprint 12 at **372 tests passing** (Sprint 11 baseline 332 + 40 new across `test_internal_users.py` (+18), `test_internal_partner_users.py` (+11), `test_internal_partners.py` (+7), `test_applications.py` (+2), and the three `*_can_view_any_org` tests added to `test_partner_dashboard.py` replacing the single `*_403_for_internal_role` test = net +2).

### Sprint 12 lessons

1. **Create stories before bugs when you care about predictable ticket keys.** The Phase A script in this sprint created the four bug tickets first (FPRM-190..193), so the four stories landed at FPRM-194/198/202/205 instead of the planned FPRM-189..192. The sprint still closed cleanly because the PRs reference `<STORY_X_KEY>` not hardcoded numbers, but anyone scanning the sprint prompt looking for FPRM-189 in the merged history will be confused. Pattern: if the prompt mentions specific ticket numbers, do stories first.
2. **The Sprint 11 partner-dashboard role guard was over-restrictive — and the existing test enforced the over-restriction.** Fixing FPRM-190 required not just widening the role check but also deleting `test_summary_403_for_internal_role` and adding the inverse `*_can_view_any_org` tests. Sprint 11 lesson #5 specifically called out that "system_admin → 403" was intentional; Sprint 12 reversed that decision. The takeaway isn't that Sprint 11 was wrong, it's that role-guard decisions are product decisions that age — record the *rationale* in the test name (`test_summary_403_for_internal_role_use_internal_dashboard_instead` would have been a better Sprint 11 name) so the next reviewer knows whether to defend the constraint or relax it.
3. **Atlassian's `/rest/api/3/search` was removed.** The closeout script hit `410 Gone`. The new shape is `POST /rest/api/3/search/jql` with the JQL in the request body. Any future sprint helper that uses the search API needs the new endpoint; the helper module in `.sprint12/helpers.py` does not export this call yet — the verify_and_close script implements it inline. Worth promoting to `jira_search_jql(jql, fields=[...])` in `helpers.py` next time we touch it.
4. **`Edit` can silently fail when a file has been read by a different tool earlier in the conversation.** During this sprint a `models.py` edit for the enum rename reported success but the file remained unchanged; the second invocation worked. After every backend edit during a fix-multiple-files PR, grep for the post-state to confirm the change actually landed — don't trust the success message alone when you're stacking many edits.
5. **The auto-merger 405 race fires on real PRs and burns 10+ minutes of background polling.** RUNBOOK §7 documents the symptom; PR #91 hit it during this sprint after the blocking checks went green but the `Auto Merge PR` step returned `failure`. The workaround (`PUT /pulls/{n}/merge` via API with `merge_method=squash`) merged in ~200ms. The `push_fprm205.py` script now wraps the wait-loop in a try/except so a timeout falls back to the manual merge automatically. Backporting this guard to a shared helper would save the next sprint the same diagnostic round-trip.
6. **`internal_partner_users_router.py` next to `partner_users_router.py` is intentional, not duplication.** The existing per-tenant `/partners/{partner_id}/users/*` surface is for partner_admins managing their own org; the new cross-tenant `/internal/partner-users/*` surface is for internal admins seeing all orgs at once. Two routers with similar names but distinct prefixes, role guards, and audit verbs (`partner_user.*` vs `internal_user.*`) keeps the surface searchable — when a future bug report says "I disabled a partner user as system_admin," you grep `internal/partner-users` and find the exact router in one hit.

## Sprint 13 — Program Configuration UI (Phase 4 continues)

**Started:** 2026-05-19
**Closed:** 2026-05-19 (single-day intensive)
**Fix Version ID:** `10732`
**Native Sprint ID:** `705`
**Phase 4 epic:** FPRM-175 — Admin Foundation & Reporting

### Sprint 13 bugs fixed

| Key | Bug | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-208 | No ability to disable or suspend a partner organisation | Done | #94 | New `PATCH /internal/partners/{id}/status` (system_admin + channel_ops_admin) accepting `active`/`suspended`/`terminated`/`inactive` with explicit 400 on the `applicant` value (only the partner-application approval flow may set that). Audit event `partner_org.status_changed` records the old→new transition in notes. Frontend: Suspend / Reactivate row action on `InternalPartnerList.jsx`, matching status badge + button on the internal `PartnerProfile.jsx` view, plus a confirmation modal and bottom-right success toast. 9 new tests in `test_partner_status.py`. |

### Sprint 13 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-209 | Approval workflow configuration backend | Done | #95 | New `ApprovalWorkflowStep` model + migration 021 with 2 seed rows (Channel Ops Review for `partner_application`, Channel Manager Review for `deal_registration`). New `program_config_router.py` exposing GET / POST / PATCH / DELETE on `/internal/config/approval-steps`. GET = any internal role, POST/PATCH = channel_ops_admin + system_admin, DELETE = system_admin only (soft-delete). 10 new tests. Multi-step enforcement deferred to Phase 5. |
| FPRM-213 | Activation checklist + partner tier configuration backend | Done | #96 | Three new models: `PartnerTierConfig` (table `partner_tiers` — named with `Config` suffix to avoid clashing with the still-in-use `PartnerTier` enum; the enum is retained until Phase 5 wires up dynamic tier assignment), `PartnerTierEligibilityRule`, `ActivationChecklistConfig`. Migration 022 seeds 3 tiers (Registered/Silver/Gold) and 6 default activation criteria mirroring the four mandatory flags in `activation.py` plus two optional placeholders (`contract_signed`, `training_advanced_complete`). Extends `program_config_router.py` with tier CRUD (with duplicate-name 409), eligibility-rule add/delete (system_admin-only delete), and activation-criteria CRUD with soft-delete. 12 additional tests (22 total in the file). |
| FPRM-217 | Program configuration UI | Done | #97 | New `frontend/src/pages/ProgramConfig.jsx` — three tabs (Approval Workflow / Partner Tiers / Activation Checklist) wired to the `/internal/config/*` endpoints. Approval Workflow: two panels (one per workflow_type) with up/down reorder (swap step_order values), inline rename on blur, role select, active toggle, delete, and add-step form. Partner Tiers: tier cards sorted by rank with active/inactive badges, edit modal, per-tier eligibility-rule list with add-rule modal (4 rule types: min_deals_approved / min_revenue / required_certification / min_win_rate). Activation Checklist: filterable table with inline Required/Active toggles, soft-delete, add-criterion modal with optional category/tier scoping. `Program Config` nav item in `InternalLayout` flipped from `Coming soon` to live (system_admin + channel_ops_admin only). |

All 9 Sub-tasks (FPRM-210/211/212 under 209, FPRM-214/215/216 under 213, FPRM-218/219/220 under 217) closed Done.

### What landed on `main` during Sprint 13

- `backend/models.py` — `from sqlalchemy.orm import relationship` (new dependency), `ApprovalWorkflowStep`, `PartnerTierConfig` (with `eligibility_rules` relationship), `PartnerTierEligibilityRule`, `ActivationChecklistConfig`.
- `backend/alembic/versions/021_create_approval_workflow_steps.py` — table + index + 2 seed rows.
- `backend/alembic/versions/022_create_tier_and_checklist_config.py` — three tables (with FK + cascade on eligibility rules) + 3 tier seeds + 6 activation-criteria seeds.
- `backend/routers/program_config_router.py` (new) — full CRUD for approval steps, tiers, eligibility rules, activation criteria; three role guards (`require_internal`, `require_config_writer`, `require_system_admin`).
- `backend/routers/internal_partners_router.py` — adds `PATCH /internal/partners/{id}/status` plus the `STATUS_ADMIN_ROLES` guard and a `_serialize_org` helper; module docstring updated for FPRM-208.
- `backend/main.py` — registers `program_config_router`.
- `backend/tests/test_partner_status.py` (new, 9) — partner status PATCH endpoint coverage.
- `backend/tests/test_program_config.py` (new, 22) — approval step (10) + tier/eligibility/activation criteria (12) coverage.
- `frontend/src/pages/ProgramConfig.jsx` (new) — three-tab program config page.
- `frontend/src/pages/InternalPartnerList.jsx` — Suspend / Reactivate row actions + confirmation modal + success toast.
- `frontend/src/pages/PartnerProfile.jsx` — status badge in header + Change Status button (internal admin view only) + matching modal + toast.
- `frontend/src/layouts/InternalLayout.jsx` — `Program Config` nav item `enabled: false` → `enabled: true`.
- `frontend/src/App.jsx` — new `/internal/config` route with `system_admin` + `channel_ops_admin` `ProtectedRoute` guard.
- `CLAUDE.md` — Current state line updated; Sprint 13 IDs added.
- `CLAUDE_HISTORY.md` — this entry.

### API endpoint count

Sprint 13 adds **14 new endpoints**:

- `PATCH /internal/partners/{id}/status` (FPRM-208)
- `GET / POST / PATCH / DELETE /internal/config/approval-steps[/{id}]` (4 endpoints, FPRM-209)
- `GET / POST / PATCH /internal/config/tiers[/{id}]` (3 endpoints, FPRM-213)
- `POST / DELETE /internal/config/tiers/{tier_id}/eligibility-rules[/{rule_id}]` (2 endpoints, FPRM-213)
- `GET / POST / PATCH / DELETE /internal/config/activation-criteria[/{id}]` (4 endpoints, FPRM-213)

Total surface area is now **95 endpoints** (Sprint 12 baseline 81 + 14).

### Sprint 13 test count

Backend ends Sprint 13 at **403 tests passing** (Sprint 12 baseline 372 + 31 new across `test_partner_status.py` (+9) and `test_program_config.py` (+22)).

### Notable notes

- **`activation.py` is unchanged.** `recalculate_activation` still enforces the four hard-coded flags (`profile_complete`, `documents_uploaded`, `terms_signed`, `baseline_training_complete`). Dynamic enforcement that reads from `activation_checklist_config` is deferred to Phase 5.
- **Multi-step approval enforcement is deferred to Phase 5.** Steps are configurable via API and UI; the existing single-reviewer flow in `applications_router` and `deal_registrations_router` is unchanged.
- **`PartnerTier` enum vs `PartnerTierConfig` model.** The new model intentionally takes a different class name (`PartnerTierConfig`) so it can coexist with the existing `PartnerTier` enum that `partner_organizations.tier` still references. The table name is `partner_tiers` because Phase 5 will migrate the foreign-key relationship and retire the enum. Two callers in `internal_partners_router.py` still validate filters against the enum — those keep working unchanged.

### Sprint 13 lessons

1. **Class-name clashes with pre-existing enums are easy to miss.** The Sprint 13 prompt named the new model `PartnerTier`, which would have shadowed the existing enum of the same name. `Grep PartnerTier` before adding a new model called PartnerTier is cheap; resolving the clash mid-PR is not. Pattern: skim `models.py` plus `grep -r ClassName backend/` for every new top-level class.
2. **Tests don't run Alembic migrations — fixtures must mirror seed data.** Migration 021/022 use `op.execute("INSERT INTO ... VALUES (gen_random_uuid(), ...)")`. The CI test suite creates schema via `Base.metadata.create_all` and never runs migrations, so the seed inserts never appear. Tests that rely on "the seed rows exist" must reconstruct them in a fixture (here: `seeded_workflow_steps`, `seeded_tiers`, `seeded_activation_criteria`). Skipping this gives green tests locally and an empty table in CI.
3. **Bash tool persists cwd across calls.** A `cd backend && pytest` in one Bash invocation left subsequent invocations rooted in `backend/` until a new explicit `cd "/c/Johan/..."` reset it. Two consecutive `cd backend && ...` calls fail the second one because `backend/backend/` doesn't exist. Pattern: prefer absolute paths in every Bash invocation and treat the persistent cwd as a footgun.
4. **AD-2 (no-git-CLI) implies the GitHub Trees API for multi-file commits.** Git CLI commits require a `user.email`/`user.name` config, which the hard rules forbid touching. The Trees API path (create blobs → create tree → create commit → update ref) is the canonical commit pipeline. Promoting the inline Python helpers used this sprint to `.sprint13/gh_helper.py` made all four PRs trivial — keeping a similar helper around (somewhere persistent, since `.sprintXX/` gets wiped by pre-flight `git clean`) would save the next sprint the re-write.
5. **The auto-merger merged all four PRs in ~32 seconds each.** PR #94, #95, #96, #97 all merged on the first CI run with no flakes. The Sprint 12 lesson #5 about the 405 race didn't recur — either the underlying race was fixed during the FPRM-205 merge or this sprint just got lucky.

### Known follow-ups for Sprint 14

1. **Sprint 14 is the final Phase 4 sprint — Reporting & Analytics.** Planned stories: internal reporting backend (5 pts), internal reporting dashboard UI (6 pts), partner pipeline view (5 pts), Phase 4 closeout docs (4 pts).
2. SMTP env vars still not set on the `fracttal-prm-backend` Railway service — lifecycle / invite emails still fall back to stdout in production. Manual ops follow-up.
3. **Dynamic activation enforcement** (consuming `activation_checklist_config` in `activation.py`) — Phase 5.
4. **Multi-step approval enforcement** (routing through `approval_workflow_steps` in `applications_router` / `deal_registrations_router`) — Phase 5.
5. **Retire the `PartnerTier` enum** in favour of the `PartnerTierConfig` table — Phase 5.

## Sprint 14 — Reporting & Analytics (Phase 4 closeout)

**Started:** 2026-05-19
**Closed:** 2026-05-19 (single-day intensive)
**Fix Version ID:** `10733`
**Native Sprint ID:** `706`
**Phase 4 epic:** FPRM-175 — Admin Foundation & Reporting

### Sprint 14 ticket-key map

Stories were created in execution order with no bugs to consume keys first, so the actual map matches the planning prompt offsets:

| Planned | Actual | Type     | Title |
|---------|--------|----------|-------|
| —       | FPRM-221 | Story    | Internal reporting backend (5 pts) |
| —       | FPRM-225 | Story    | Internal reporting dashboard UI (6 pts) |
| —       | FPRM-229 | Story    | Partner pipeline view (5 pts) |
| —       | FPRM-233 | Story    | Sprint 14 docs and Phase 4 closeout (4 pts) |

Subtasks: FPRM-222/223/224 (under 221), FPRM-226/227/228 (under 225), FPRM-230/231/232 (under 229), FPRM-234/235/236/237 (under 233).

### Sprint 14 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-221 | Internal reporting backend | Done | #99 | New `backend/routers/reports_router.py` exposing five endpoints under `/internal/reports`: `/pipeline`, `/cycle-times`, `/conflicts`, `/partner-activity`, `/pipeline/export`. All aggregations are computed at query time from existing tables — no new migrations (head remains 022). Role gating: `system_admin` / `channel_ops_admin` / `channel_manager` / `sales_ops` for reads; CSV export additionally allows `finance_approver`. 18 new tests in `test_reports.py` covering empty DB, pipeline counts, date/category filters, cycle-time averaging and slowest-5 ordering, conflict rate math, CSV header + content-type, and role guards. |
| FPRM-225 | Internal reporting dashboard UI | Done | #100 | New `frontend/src/pages/InternalReports.jsx` at `/internal/reports` consuming the new endpoints. Three sections: **Pipeline Overview** (5 summary tiles, stacked bar chart of top-10 partners, donut by category, sortable Top Partners table), **Cycle Times** (avg-days badge, monthly line chart pivoted from `by_category_and_month`, slowest-5 table), **Conflict Report** (rate badge with threshold colouring red>10%/amber>5%/green, unresolved table). Filter bar with preset date ranges (Last 30 / 90 / This Year / All Time), category dropdown, tier dropdown — re-fetches pipeline + conflicts on every change. CSV export uses fetch + Blob URL + anchor click (not `window.location.href`, since Authorization header is required). recharts added to `frontend/package.json` (^2.12.7). Shimmer loading skeletons, inline error banners with Retry, empty states, mobile-responsive layout. `Reports` nav item in `InternalLayout` flipped from `Coming soon` to live; `App.jsx` wires the new route with role-aware ProtectedRoute. |
| FPRM-229 | Partner pipeline view | Done | #101 | Appended `GET /partners/{id}/pipeline` to `backend/routers/partners_router.py` — partner_admin only, tenant-scoped to own org, returns deals grouped into the six pipeline-status keys (`draft`, `submitted`, `under_review`, `info_required`, `approved`, `rejected`). Supports optional `status` / `from_date` / `to_date` filters. 7 new tests in `test_pipeline.py` cover happy path, cross-org block, system_admin block (partner_admin only), grouping, filters, 404. `DealList.jsx` rewritten with a List/Pipeline view toggle synced to `?view=` query param, filter bar with status + date inputs, pipeline summary strip (Total Deals / Total Value / Approved Value / Info Required), and a read-only Kanban view with 6 columns each with a coloured left border and a per-column total. `PartnerHome.jsx` gains a "My pipeline" widget (4 tiles + `View Pipeline →` link to `/portal/deals?view=pipeline`). |
| FPRM-233 | Sprint 14 docs + Phase 4 closeout | Done | #102 | Updated all four canonical docs: `CLAUDE.md` (current state Sprint 14 / Phase 4 complete, Sprint 14 sprint IDs, tech-debt refresh adding the four Phase-5 carry items), `CLAUDE_HISTORY.md` (this entry + Phase 4 complete marker + Phase 5 readiness notes), `PROJECT_CONTEXT.md` (Sprint 14 API endpoints in Section 1, AD-16 and AD-17 added in Section 6), `RUNBOOK.md` (§12 Phase 4 happy-path validation appended). |

All 13 Sub-tasks (FPRM-222/223/224, 226/227/228, 230/231/232, 234/235/236/237) closed Done.

### What landed on `main` during Sprint 14

- `backend/routers/reports_router.py` (new) — five report endpoints (FPRM-221).
- `backend/routers/partners_router.py` — appended `GET /partners/{id}/pipeline` (FPRM-229).
- `backend/main.py` — registers `reports_router`.
- `backend/tests/test_reports.py` (new, 18); `backend/tests/test_pipeline.py` (new, 7).
- `frontend/package.json` — added `recharts: ^2.12.7`.
- `frontend/src/pages/InternalReports.jsx` (new) (FPRM-225).
- `frontend/src/pages/DealList.jsx` — List/Pipeline view toggle, filter bar, summary strip, kanban view (FPRM-229).
- `frontend/src/pages/PartnerHome.jsx` — pipeline summary widget + View Pipeline link (FPRM-229).
- `frontend/src/layouts/InternalLayout.jsx` — `Reports` nav `enabled: false` → `true` (FPRM-225).
- `frontend/src/App.jsx` — `/internal/reports` route added with role-aware ProtectedRoute (FPRM-225).
- `CLAUDE.md`, `CLAUDE_HISTORY.md`, `PROJECT_CONTEXT.md`, `RUNBOOK.md` — Phase 4 closeout updates.

### API endpoint count

Sprint 14 adds **6 new endpoints**:
- `GET /internal/reports/pipeline`
- `GET /internal/reports/cycle-times`
- `GET /internal/reports/conflicts`
- `GET /internal/reports/partner-activity`
- `GET /internal/reports/pipeline/export`
- `GET /partners/{id}/pipeline`

Total surface area is now **101 endpoints** (Sprint 13 baseline 95 + 6).

### Sprint 14 test count

Backend ends Sprint 14 at **428 tests passing** (Sprint 13 baseline 403 + 25 new across `test_reports.py` (+18) and `test_pipeline.py` (+7)).

### Sprint 14 lessons

1. **The `conflict_detected` field is a string status value, not a boolean column.** The Sprint 14 prompt referenced `conflict_detected` as a column on `DealRegistration`. The actual schema (since Sprint 10 / FPRM-157) has `conflict_status` storing one of `"clear"` / `"conflict_detected"` / `"not_checked"`. Reading the model up front prevented a backend-test-only failure — the existing `dashboard_router.py` (Sprint 11 / FPRM-179) already had the correct filter pattern that the new reports_router could mirror.
2. **`recharts` was prescribed but missing from `package.json`.** The prompt told me to "confirm recharts is present — do NOT add any other charting library." The package was not yet installed. Adding the prescribed library was clearly intended; the rule was about not introducing a *different* library (e.g. Chart.js, ECharts). Reading prompts strictly enough to catch this kind of nuance saves a back-and-forth.
3. **CSV export requires fetch + Blob, not `window.location.href`.** Native browser navigation cannot send an `Authorization: Bearer` header, so a direct anchor link to `/internal/reports/pipeline/export` would 401. The fetch+Blob+createObjectURL+anchor.click pattern is the right answer — promoted to AD-16 in PROJECT_CONTEXT.md so future authenticated-download endpoints don't reinvent it.
4. **All four PRs merged on first CI green in <60s each.** No flakes, no race, no manual-merge fallback. The auto-merger reliability has been consistent for the last two sprints — Sprint 12's 405-race lesson appears to have been a transient issue.

### Phase 4 — complete

| Sprint | Theme | Stories | Points | Key delivery |
|---|---|---|---|---|
| 11 | Admin Shell & Dashboards | 4 stories + 2 bug fixes | 20 | InternalLayout, InternalHome, enhanced PartnerHome, forgot password, FPRM-89/104 fixed |
| 12 | User Management | 4 stories + 4 bug fixes | 20 | Internal user CRUD, partner user management, internal partners list, enum/dashboard bugs |
| 13 | Program Configuration | 3 stories + 1 bug fix | 22 | ApprovalWorkflowStep, PartnerTier, ActivationChecklistConfig, ProgramConfig.jsx 3-tab UI |
| 14 | Reporting & Analytics | 4 stories | 20 | reports_router, InternalReports.jsx, partner pipeline Kanban, Phase 4 docs |
| **Total** | **Phase 4** | **15 stories, 7 bugs** | **82** | Admin foundation, user management, program configuration, reporting — complete |

### Phase 5 readiness notes

1. **Quoting module (FR-QUOTE).** Top priority. Johan has detailed design inputs from the partnership programme; use those as the primary source.
2. **HubSpot integration (FR-HS).** High priority. Johan has detailed design inputs; use those as the primary source.
3. **Dynamic activation enforcement.** Wire `backend/activation.py` `recalculate_activation` to read criteria from `activation_checklist_config` rather than the four hard-coded flags. The data model is already in place from Sprint 13.
4. **Multi-step approval enforcement.** Thread `approval_workflow_steps` through `applications_router.approve_application` and `deal_registrations_router.approve_deal` so configured workflow steps are required instead of the existing single-reviewer flow.
5. **Retire the `PartnerTier` enum.** Convert `partner_organizations.tier` from the enum to a foreign key into `partner_tiers`. Migration drops the enum once all callers are flipped.
6. **SMTP env vars on Railway.** Set `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `EMAIL_FROM` / `CHANNEL_OPS_EMAIL` on the `fracttal-prm-backend` service — no code change required, just dashboard ops.
7. **Persist `info_request_message` as a real column.** Currently an in-memory attribute; a migration would unblock historical reporting of past info requests on applications.
8. **JWT logout blacklist → Redis (or DB).** The in-memory blacklist is lost on backend restart and is not safe for multi-instance deploys. Move to a shared store before scaling out.
9. **Password reset email backend.** Reset URLs are still logged to stdout via `print`. Adopt the AD-13 SMTP+stdout-fallback pattern used by lifecycle notifications.
10. **Multi-role users.** `User.role` is a single string. If a Phase 5 requirement needs e.g. `sales_rep + partner_admin` on the same user, redesign as a join table.


## Sprint 15 — Quoting Module Foundation (Phase 5 begins)

**Started:** 2026-05-19
**Closed:** 2026-05-19 (single-day intensive)
**Fix Version ID:** `10766`
**Native Sprint ID:** `739`
**Phase 5 epic:** FPRM-238 — Quoting Module & Enforcement

### Sprint 15 ticket-key map

Phase 5 Epic (FPRM-238) was created first, so the first story is one off the planning-prompt offsets:

| Planned | Actual | Type     | Title |
|---------|--------|----------|-------|
| FPRM-238 | FPRM-238 | Epic | Quoting Module & Enforcement (Phase 5) |
| FPRM-239 | FPRM-239 | Story | Quote data model and Alembic migrations (6 pts) |
| —       | FPRM-240 | Sub-task | Add pricing catalogue models + migration 023 with seed data (3 pts) |
| —       | FPRM-241 | Sub-task | Add quote header, version, and line-item models + migration 024 (2 pts) |
| —       | FPRM-242 | Sub-task | Write unit tests for new models and seed data (1 pt) |
| FPRM-240 | FPRM-243 | Story | Quote calculation engine (6 pts) |
| —       | FPRM-244 | Sub-task | Implement `calculate_quote` and dataclasses (3 pts) |
| —       | FPRM-245 | Sub-task | Write 20+ unit tests for the engine (3 pts) |
| FPRM-242 | FPRM-246 | Story | Quote CRUD API (6 pts) |
| —       | FPRM-247 | Sub-task | Create `quotes_router.py` (3 pts) |
| —       | FPRM-248 | Sub-task | Add version management + status endpoints (2 pts) |
| —       | FPRM-249 | Sub-task | Write unit tests for quotes API (1 pt) |
| FPRM-244 | FPRM-250 | Story | Sprint 15 docs update (3 pts) |
| —       | FPRM-251/252/253 | Sub-tasks | Update PROJECT_CONTEXT.md + CLAUDE.md / CLAUDE_HISTORY.md / Close Sprint 15 |

### Sprint 15 stories — outcome

| Key | Story | Status | PR | Notes |
|---|---|---|---|---|
| FPRM-239 | Quote data model and Alembic migrations | Done | #103 | Added six new SQLAlchemy models (`FeaturePlanPrice`, `VolumeDiscountTier`, `AddonCatalogItem`, `Quote`, `QuoteVersion`, `QuoteLineItem`) and two Alembic migrations: 023 creates the three pricing-catalogue tables and seeds them from the Fracttal Pricing and Quotation Specification (3 plans + 6 volume tiers + 21 add-ons via idempotent `WHERE NOT EXISTS` inserts); 024 creates the three quote tables with FK constraints, the unique `(quote_id, version_number)` constraint, and the required indexes. `models.py` imports patched to add `Decimal` and `UniqueConstraint`. 9 model tests in `test_quote_models.py` verifying seed data and FK enforcement (uses `PRAGMA foreign_keys = ON` per AD-8 — sqlite needs it explicitly enabled to honour FK constraints in tests). |
| FPRM-243 | Quote calculation engine | Done | #104 | New `backend/quote_engine.py` — pure module, no FastAPI imports, importable standalone (AD-18). `calculate_quote(db, feature_plan, feature_plan_discount_pct, qty_transactional, qty_limited_tech_quoted, selected_addon_keys)` returns a `QuoteCalculationResult` dataclass with ordered `QuoteLineItemData` rows + grand totals. Implements all 7 spec rules: free Limited Technician allocation (suppressed when discount > 0); volume-banded user lines (1 line per non-zero band); Feature Plan discount affects ONLY the Feature Pack; add-on validation per plan (Enterprise raises if any add-on passed; Starter/Professional rejects add-ons marked unavailable for that plan); `Decimal` quantised to 2 places throughout. 21 unit tests in `test_quote_engine.py` covering all four worked spec examples exactly (Examples 1-4) plus boundary cases (band edges 10/11, 501+ users, 100% discount, multiple add-ons, line-order sequentiality). Spec Example 2's stated after-discount total (15399.60) appears to have an arithmetic error; the engine computes the mathematically correct 15039.60. |
| FPRM-246 | Quote CRUD API | Done | #105 | New `backend/routers/quotes_router.py` with 10 endpoints (see PROJECT_CONTEXT §1). Wraps `quote_engine.calculate_quote` per AD-18 — no inline pricing arithmetic in the router. Tenant scoping: partner_admin can only quote on own org's deals; internal review roles unrestricted. Write roles (channel_manager + channel_ops_admin + system_admin) for new versions / activate / status transitions; soft-delete restricted to channel_ops_admin + system_admin and rejects deleting the currently active version. Engine `ValueError` -> HTTP 422 (e.g. Enterprise + add-on, unknown add-on key, invalid plan). Status state machine: `draft -> sent`, `sent -> {accepted, expired}`; other transitions 422. Registered in `main.py` between `reports_router` and the end of the list. 18 API tests in `test_quotes_api.py` covering create / list / read / version add+activate / RBAC cross-org block / status state machine / soft-delete + activate-deleted / audit log emission / pricing catalogue endpoints / Enterprise-add-on rejection. |
| FPRM-250 | Sprint 15 docs update | Done | (this PR) | All canonical docs updated: PROJECT_CONTEXT.md (§1 adds 10 new endpoints; §2 adds 6 new tables + 2 migrations; §6 adds AD-18); CLAUDE.md (current state, Sprint 15 IDs); CLAUDE_HISTORY.md (this entry). |

All 9 Sub-tasks (FPRM-240..242, 244-245, 247-249, 251-253) closed Done.

### Sprint 15 bugs — discovered and fixed mid-sprint

| Key | Bug | Fixed in PR | Notes |
|---|---|---|---|
| — | Missing `UniqueConstraint` import in `models.py` | #103 (fix commit) | First test run failed `NameError`; the planned edit to add the import wasn't matching the existing multi-line import block. Fix-commit patched the import; no separate Jira ticket since the bug only existed inside the unmerged PR. |
| — | `seed_pricing` duplicated rows across tests on a module-scoped engine | #103 (fix commit) | First test run failed `UNIQUE constraint failed: addon_catalog_items.addon_key`. Replaced the per-test fixture with a teardown that truncates the quote/pricing tables in dependency order (matches the pattern from `test_dashboard.py` / `test_partner_dashboard.py`). |
| — | `Quote` constructor rejected a stray `grand_total_after_discount` kwarg | #103 (fix commit) | Copy-paste error in `test_quote_requires_deal_id` (the field belongs on `QuoteVersion`). Dropped the kwarg. |
| — | `Decimal` serialised as float, not string, in test assertion | #105 (fix commit) | FastAPI `jsonable_encoder` converts `Numeric` -> `float`; test asserted `== "16608.00"`. Fix: assert numeric equality via `float()`. The actual API behaviour is unchanged. |

### What landed on `main` during Sprint 15

- `backend/models.py` — adds `Decimal` + `UniqueConstraint` imports and six new models: `FeaturePlanPrice`, `VolumeDiscountTier`, `AddonCatalogItem`, `Quote`, `QuoteVersion`, `QuoteLineItem`.
- `backend/alembic/versions/023_create_pricing_catalogue.py` (new) — 3 pricing tables + 30 seeded rows.
- `backend/alembic/versions/024_create_quotes.py` (new) — 3 quote tables + FKs + unique constraint + indexes.
- `backend/quote_engine.py` (new) — standalone pricing calculation module (AD-18).
- `backend/routers/quotes_router.py` (new) — 10 quote endpoints.
- `backend/main.py` — registers `quotes_router`.
- `backend/tests/test_quote_models.py` (new, 9 cases).
- `backend/tests/test_quote_engine.py` (new, 21 cases).
- `backend/tests/test_quotes_api.py` (new, 18 cases).
- `CLAUDE.md`, `CLAUDE_HISTORY.md`, `PROJECT_CONTEXT.md` — Sprint 15 closeout updates.

### API endpoint count

Sprint 15 adds **10 new endpoints**:
- `POST /deals/{deal_id}/quotes`
- `GET /deals/{deal_id}/quotes`
- `GET /quotes/{quote_id}`
- `POST /quotes/{quote_id}/versions`
- `PATCH /quotes/{quote_id}/active-version`
- `PATCH /quotes/{quote_id}/status`
- `GET /quotes/{quote_id}/versions`
- `DELETE /quotes/{quote_id}/versions/{version_number}`
- `GET /internal/config/pricing/plans`
- `GET /internal/config/pricing/addons`

Total surface area is now **111 endpoints** (Sprint 14 baseline 101 + 10).

### Sprint 15 test count

Backend ends Sprint 15 at **~474 tests passing** (Sprint 14 baseline 428 + 9 + 21 + 18). A precise post-merge count is asserted in the closeout report after `pytest backend/tests/ -v` against the merged `main`.

### Sprint 15 lessons

1. **Multi-line Python imports need an exact replacement target.** The initial `models.py` patch tried to insert `UniqueConstraint` by matching `    Uuid,\n)`. The match did not fire (likely a CRLF / formatting subtlety), so the import block reached CI without the new symbol and the test loader broke at `NameError: name 'UniqueConstraint' is not defined`. Lesson: validate the patched file content by re-reading it from GitHub before pushing, not just by checking that the string "UniqueConstraint" appears *somewhere* in the file — the model definitions referenced it too, producing a false-positive presence check.
2. **Module-scoped engines need per-test cleanup when tests seed data.** The test seed helper inserted the 21 add-ons under a UNIQUE `addon_key`; on the second test the same module-level engine triggered `UNIQUE constraint failed`. Existing tests like `test_partner_dashboard.py` already had a `db_session` fixture that truncates all tables on teardown — copying that pattern resolved it. Future stories that introduce seeded test data should adopt the truncate-on-teardown pattern from day one.
3. **`jsonable_encoder` converts `Decimal` -> `float`.** Currency values like `Decimal("16608.00")` serialise as `16608.0` (no string preservation). Tests that assert against the raw response value must compare numerically (`float(val) == 16608.00`) rather than string-equality, or the router must explicitly stringify Decimals before returning. Keeping the engine in `Decimal` and the wire format in `float` is the path of least resistance for Phase 5; if currency precision becomes load-bearing for downstream consumers, revisit at that time.
4. **Spec Example 2 grand-total has an arithmetic error.** Stated `15399.60`; correct is `15039.60` (5619.60 + 4500 + 2400 + 2520). Trust the rules, not the stated totals — the engine math reconciles to the four corrected totals exactly. Flagging here so the next sprint that touches the spec doesn't try to make the engine match a wrong number.

### Phase 5 progress

| Sprint | Theme | Stories | Points | Status |
|---|---|---|---|---|
| 15 | Quoting Module Foundation (data model + engine + API) | 4 | 21 | **Done** |
| 16 | Quoting Module Frontend + PDF + CSV export gaps | 4 | 21 | Pending |
| 17 | Dynamic activation enforcement + Multi-step approval | 3 | 20 | Pending |
| 18 | Quote scenarios + Multi-currency display + Phase 5 closeout | 4 | 20 | Pending |
| **Total** | **Phase 5** | **15 stories** | **82** | **1 of 4 sprints complete** |


## Sprint 16 — Quoting UX, PDF Generation, CSV Export (Phase 5 Sprint 2 of 4)

**Started:** 2026-05-19
**Closed:** 2026-05-19 (single-day intensive)
**Fix Version ID:** `10767`
**Native Sprint ID:** `740`
**Phase 5 epic:** FPRM-238 — Quoting Module & Enforcement

### Sprint 16 stories — outcome

| Key | Story | Pts | Status | PR | Notes |
|---|---|---|---|---|---|
| FPRM-254 | Quote form and list UI (internal + portal) | 7 | Done | #107 | QuoteForm.jsx (3-section form with live preview), QuoteDetail.jsx (version browser + line items + status), Quotes tab on InternalDealDetail, read-only PortalQuoteSection on DealDetail.jsx |
| FPRM-258 | PDF quote generation and storage | 7 | Done | #108 | Migration 025 adds 3 columns; reportlab==4.2.2; POST generate-pdf + GET /pdf endpoints; 11 unit tests; frontend buttons already wired in Story 1 |
| FPRM-262 | CSV export on list views (gap closure) | 4 | Done | #109 | New backend/csv_export.py helper; 7 endpoints get `?export=csv`; 7 frontend pages get Export CSV button (fetch+Blob, AD-20) |
| FPRM-265 | Sprint 16 docs update | 3 | Done | #<this PR> | This entry + CLAUDE.md + PROJECT_CONTEXT.md (AD-19, AD-20, migration 025) |

All 11 sub-tasks closed Done.

### What landed on `main` during Sprint 16

- `frontend/src/pages/QuoteForm.jsx` (new) — quote create + new-version form with sticky live-preview panel
- `frontend/src/pages/QuoteDetail.jsx` (new) — version browser, line-item table, status management, PDF generate/download
- `frontend/src/pages/InternalDealDetail.jsx` (extended) — new `QuotesSection` with list table + New Quote / View / Add Version modals
- `frontend/src/pages/DealDetail.jsx` (extended) — read-only `PortalQuoteSection` on the partner portal deal detail (serves `/portal/deals/:id`)
- `backend/alembic/versions/025_add_pdf_to_quote_versions.py` (new) — `pdf_artifact_data` Text, `pdf_generated_at`, `pdf_filename` on quote_versions
- `backend/requirements.txt` — appended `reportlab==4.2.2` (universal py3-none-any wheel; runs on Python 3.13)
- `backend/models.py` (extended) — three new columns on `QuoteVersion`
- `backend/routers/quotes_router.py` (extended) — `POST /quotes/{id}/versions/{n}/generate-pdf`, `GET /quotes/{id}/versions/{n}/pdf`, with the inline `generate_quote_pdf` reportlab renderer
- `backend/tests/test_quote_pdf.py` (new) — 11 tests
- `backend/csv_export.py` (new) — shared `csv_response(filename_base, header, rows)` helper
- `backend/routers/deal_registrations_router.py`, `documents_router.py`, `internal_partners_router.py`, `internal_partner_users_router.py`, `applications_router.py`, `internal_users_router.py` (extended) — each list endpoint gets `?export=csv` branch
- `backend/tests/test_csv_exports.py` (new) — 7 smoke tests, one per endpoint
- 7 frontend list pages get an Export CSV button using fetch + Blob (DealList.jsx portal, DealQueue.jsx, PartnerDocuments.jsx, InternalPartnerList.jsx, PartnerUserManagement.jsx, ApplicationQueue.jsx, InternalUsers.jsx)
- PROJECT_CONTEXT.md — AD-19 (PDF base64 storage) + AD-20 (fetch+Blob for authenticated downloads); migration 025 noted in Section 2

### API endpoints added

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/quotes/{id}/versions/{n}/generate-pdf` | Internal write roles | Renders + stores PDF base64 |
| GET  | `/quotes/{id}/versions/{n}/pdf`          | partner_admin own + internal | Streams application/pdf |

7 endpoints extended with optional `?export=csv` query parameter (no surface count change).

Total API surface ends Sprint 16 at ~113 endpoints + 7 endpoints with CSV extension.

### Test count

| Source | Count |
|---|---|
| Sprint 15 baseline | 476 |
| Story 2 PDF tests | +11 |
| Story 3 CSV tests | +7 |
| **Sprint 16 total** | **~494** |

### Sprint 16 lessons

1. **GitHub Contents API returns CRLF line endings for files originally stored with them on Windows.** When generating modified files programmatically via Python on Windows, `read_text` + `write_text` round-trips translate `\r\n` -> `\n` -> `\r\n` -> `\n\n` (each step duplicates), producing files with extra blank lines. Fix: explicitly normalize `\r\n` -> `\n` after reading and write with `newline=""`. Discovered mid-Sprint while building Story 3 string replacements; Story 1 files were pushed with the doubled blank lines (cosmetic-only, valid JSX).
2. **Story 1 already wired the PDF buttons.** Writing the QuoteDetail.jsx component to include both Generate and Download buttons up-front meant Sprint 16's Subtask 3 of Story 2 (frontend wiring) collapsed into a no-op once Story 2's backend merged. Recorded by transitioning the subtasks to Done without a separate PR.
3. **reportlab==4.2.2** is a universal `py3-none-any` wheel — no Python 3.13 wheel needed, the universal wheel works fine. PyPI metadata says `<4,>=3.7` which the universal wheel honours on 3.13.

### Known follow-ups for Sprint 17

1. Dynamic activation enforcement — wire `recalculate_activation` to read from the `activation_checklist_config` table.
2. Multi-step approval enforcement — enforce `approval_workflow_steps` sequence for applications and deal registrations.
3. PartnerTier enum vs PartnerTierConfig table — migrate FK and retire enum.


## Sprint 17 — Dynamic Activation & Multi-Step Approval Enforcement (Phase 5 Sprint 3 of 4)

**Started:** 2026-05-20
**Closed:** 2026-05-20 (single-day intensive)
**Fix Version ID:** `10768`
**Native Sprint ID:** `741`
**Phase 5 epic:** FPRM-238 — Quoting Module & Enforcement

### Sprint 17 stories — outcome

| Key | Story | Pts | Status | PR | Notes |
|---|---|---|---|---|---|
| FPRM-270 | Dynamic activation enforcement | 8 | Done | #112 | `backend/activation.py` rewritten — `recalculate_activation` (signature frozen) now reads required criteria from `activation_checklist_config` with NULL-as-wildcard for category/tier scoping; falls back to the hardcoded four-flag rule when no rows match. New `CRITERION_KEY_MAP` translates criterion keys to checklist fields; unknown keys auto-satisfied (forward-compat). New endpoint `GET /partners/{id}/activation/criteria` returns `{required_criteria, activation_complete, config_source}`. `ActivationChecklist.jsx` + `PartnerHome.jsx` switched to the new endpoint. 22 new tests (15 engine + 7 endpoint) all green; 17 existing `test_activation.py` tests still green (regression guard). |
| FPRM-274 | Multi-step approval enforcement | 8 | Done | #113 | New `ApprovalStepRecord` model (polymorphic `object_id`, indexes on `object_id` and `(workflow_type, object_id)`) + migration 026. New `backend/approval_helpers.py` (`get_approval_step_context`, `build_approval_progress`, `record_step_action`) shared between `applications_router` and `deal_registrations_router` to avoid duplication. Step-gating in both approve endpoints — caller role must match the current step's `required_role`, intermediate-step approvals stamp a step record without changing status, final step runs the existing approval flow. Reject endpoints stamp a `rejected` step record before flipping status. `approval_progress` added to `GET /applications/{id}` and `GET /deal-registrations/{id}`. Frontend: `ApplicationReview.jsx` + `InternalDealDetail.jsx` show the step indicator and disable the Approve button on role mismatch. 18 new tests covering fallback (no-steps), single-step correct/wrong role, two-step intermediate/final, can't-skip-step, audit-log ordering, deal flow parity. |
| FPRM-279 | Sprint 17 docs update | 4 | Done | #<this PR> | This entry + CLAUDE.md (current state, Sprint 17 IDs, removed deferred items) + PROJECT_CONTEXT.md (new endpoint, migration 026, AD-21 + AD-22). |

All 10 sub-tasks (FPRM-271..273, 275..278, 280..282) closed Done.

### What landed on `main` during Sprint 17

- `backend/activation.py` — rewritten for dynamic enforcement with fallback; `CRITERION_KEY_MAP`, `HARDCODED_REQUIRED_KEYS`, `resolve_required_criteria` exposed for the router to reuse
- `backend/routers/partners_router.py` — new `GET /partners/{id}/activation/criteria` endpoint
- `backend/tests/test_activation_dynamic.py` (new, 22 tests) — fallback path, dynamic path, category/tier scoping (match/mismatch/null-wildcard), partial criteria, alias handling, endpoint RBAC
- `frontend/src/components/ActivationChecklist.jsx` — fetches `/activation/criteria`, renders dynamic items with a `KEY_ACTIONS` map for per-criterion CTA/hint
- `frontend/src/pages/PartnerHome.jsx` — progress widget sourced from criteria endpoint (falls back to dashboard summary)
- `backend/models.py` — adds `ApprovalStepRecord`
- `backend/alembic/versions/026_create_approval_step_records.py` (new)
- `backend/approval_helpers.py` (new) — shared multi-step helpers
- `backend/routers/applications_router.py` — step-gating on approve, step record on reject, `approval_progress` on GET
- `backend/routers/deal_registrations_router.py` — same pattern on deal approve/reject + GET
- `backend/tests/test_approval_enforcement.py` (new, 18 tests)
- `frontend/src/pages/ApplicationReview.jsx` — Approval Workflow card + role-gated Approve button
- `frontend/src/pages/InternalDealDetail.jsx` — same indicator + role-gated Approve in the under_review action panel
- `PROJECT_CONTEXT.md` — Section 1 adds the criteria endpoint; Section 2 adds `approval_step_records` migration row; Section 6 adds AD-21 (dynamic activation) and AD-22 (multi-step approval)
- `CLAUDE.md` — Sprint 17 IDs (native 741, fix version 10768), updated current-state paragraph, two deferred items removed from Known Issues

### API endpoints added

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/partners/{partner_org_id}/activation/criteria` | partner_admin (own) / internal | Returns resolved criteria + per-item met state + `config_source` |

`approval_progress` field added to existing `GET /applications/{id}` and `GET /deal-registrations/{id}` responses — does not change the endpoint surface count.

Total API surface ends Sprint 17 at **~114 endpoints** (Sprint 16 baseline 113 + 1) + 7 endpoints with the `?export=csv` extension.

### Migrations added

- `026_create_approval_step_records` — creates the `approval_step_records` table, FK on `actor_id` → `users.id`, indexes on `object_id` and `(workflow_type, object_id)`. Idempotent (checks for existing table before creating).

Alembic head advances **025 → 026**.

### Test count

| Source | Count |
|---|---|
| Sprint 16 baseline | ~494 |
| Story 1 activation tests | +22 |
| Story 2 approval tests | +18 |
| **Sprint 17 total** | **535** |

(A precise post-merge count is asserted in the Phase C closeout report after `pytest backend/tests/ -v` against merged `main`.)

### Sprint 17 lessons

1. **`recalculate_activation`'s return type is "checklist row" not "bool", and every caller relies on it.** The prompt's pseudocode returned `bool`, but the function in the codebase (since Sprint 7 / AD-14) has always returned the persisted `PartnerActivationChecklist`. Several callers reassign `checklist = recalculate_activation(...)` — changing the return type would have been a silent breakage. Preserving it kept zero churn on `partner_profiles_router`, `documents_router`, `partners_router`, `provisioning.py`. Reading every caller before touching a "frozen signature" function is the only way to confirm what "frozen" actually means.
2. **CRLF line endings on Windows break naive `Edit` calls on multi-line anchors.** When `models.py` was written with `\r\n` line endings, the harness's `Edit` tool refused to match an anchor that included blank lines because the byte representation differed from the Read view. The reliable workaround was a one-shot Python script that reads the file as bytes, locates the anchor with explicit `\r\n` sequences, and writes the result back as bytes. Applies whenever inserting whole classes/blocks into a CRLF-encoded file.
3. **Multi-step approval and dynamic activation are *enabled by config*, not by code.** The fallback paths are not "future-proofing" — they are the production-correct behaviour for every existing partner and every existing deal. Tests must explicitly cover both the dynamic path AND the fallback path; one is not the other's degenerate case.
4. **Tests that call dual-auth endpoints (`get_optional_bearer_user`) need a separate override.** The `_override` helper only overrode `get_current_user`, which is what `approve`/`reject` use — but `GET /applications/{id}` uses `get_optional_bearer_user`. The first test fixture cut produced a 401 on the GET test. Overriding both dependencies in the helper made the rest of the suite green and is the right pattern for any future test that touches both endpoint flavours.
5. **Polymorphic `object_id` without a FK constraint is the simplest portable cross-workflow audit pattern.** `ApprovalStepRecord.object_id` references either `partner_applications.id` or `deal_registrations.id`. A union-typed FK would require PostgreSQL-specific check constraints or triggers; a separate table per workflow type would force shared logic into two places. Plain UUID column + composite index `(workflow_type, object_id)` is what `audit_log` already uses for the same reason.

### Known follow-ups for Sprint 18

1. **Quote scenario management** — Good/Better/Best comparison UI on top of the existing `scenario_label` field on `QuoteVersion`.
2. **Multi-currency display** — `quotes.currency_code` exists; surface it in the quote UI and on PDFs (no FX conversion in Phase 5).
3. **Internal quote dashboard** — `/internal/quotes` cross-deal quote list with filters and CSV export.
4. **Partner quote history** — `/portal/quotes` for partner-facing visibility into all quote versions across their deals.
5. **PartnerTier enum vs PartnerTierConfig table** — Phase 5 still has this last legacy enum to retire; will land before Phase 5 closeout.
6. **Phase 5 docs + closeout** — Sprint 18 closes Phase 5; CLAUDE_HISTORY Phase 5 complete marker, RUNBOOK validation.

### Phase 5 progress (updated)

| Sprint | Theme | Stories | Points | Status |
|---|---|---|---|---|
| 15 | Quoting Module Foundation (data model + engine + API) | 4 | 21 | Done |
| 16 | Quoting Module Frontend + PDF + CSV export gaps | 4 | 21 | Done |
| 17 | Dynamic activation enforcement + Multi-step approval | 3 | 20 | **Done** |
| 18 | Quote scenarios + Multi-currency display + Phase 5 closeout | 4 | 20 | Pending |
| **Total** | **Phase 5** | **15 stories** | **82** | **3 of 4 sprints complete** |

## Sprint 18 — Quote Scenarios, Multi-Currency Display & Phase 5 Closeout (Phase 5 Sprint 4 of 4)

**Started:** 2026-05-19
**Closed:** 2026-05-19 (single-day intensive)
**Fix Version ID:** `10769`
**Native Sprint ID:** `742`
**Phase 5 epic:** FPRM-238 — Quoting Module & Enforcement

### Sprint 18 stories — outcome

| Key | Story | Pts | Status | PR | Notes |
|---|---|---|---|---|---|
| FPRM-283 | Quote scenario management (Good/Better/Best) | 6 | Done | #115 + #116 | Backend `PATCH /quotes/{id}/active-scenario` + `GET /quotes/{id}/scenarios` (10 tests). Frontend: conditional scenario comparison panel in `QuoteDetail.jsx`, scenario-label hint in `QuoteForm.jsx` new-version mode (greys out already-created labels), recommended-scenario badge + read-only scenario tabs in `DealDetail.jsx` PortalQuoteSection. AD-24 codifies the active_scenario / active_version decoupling. |
| FPRM-287 | Multi-currency display and internal quote dashboard | 6 | Done | #117 (+ 2 fix commits) | `GET /internal/quotes` with status / partner_org_id / feature_plan / search filters, pagination, system-wide summary (counts + pipeline_total, expired excluded). 6 tests in `test_internal_quotes.py`. New `InternalQuotes.jsx` at `/internal/quotes` linked from the InternalLayout sidebar between Deals and Users. Shared `frontend/src/utils/currency.js` adopted by QuoteForm / QuoteDetail / DealDetail / InternalQuotes / PortalQuotes; PDF generator's existing `CURRENCY_SYMBOL` map already covers the same nine currencies. AD-23 codifies multi-currency display semantics. |
| FPRM-291 | Partner quote history and deal quote summary | 5 | Done | #118 | `GET /partners/{id}/quotes` (partner own-org only; internal users 403'd with a hint to use `/internal/quotes`). 5 tests in `test_partner_quotes.py`. New `PortalQuotes.jsx` at `/portal/quotes` linked from PartnerPortalLayout between Commissions and the disabled Training item. New `DealHeaderQuoteBadge` in `InternalDealDetail.jsx` page header surfaces the most relevant quote (accepted > sent > draft > expired) with status + version + grand total. |
| FPRM-294 | Phase 5 docs and closeout | 3 | Done | #<this PR> | This entry + Phase 5 complete marker + PROJECT_CONTEXT.md Section 1 (4 new endpoints) + Section 3 (InternalQuotes/PortalQuotes/QuoteForm/QuoteDetail entries) + Section 6 (AD-23 / AD-24) + CLAUDE.md (current-state paragraph, Sprint 18 IDs, tech-debt refresh) + RUNBOOK.md §16 (Phase 5 validation). |

All 10 sub-tasks (FPRM-284..286, 288..290, 292..293, 295..298) closed Done.

### Sprint 18 bugs — discovered and fixed mid-PR

| Discovery | Fixed in | Notes |
|---|---|---|
| `NameError: name 'PartnerOrganization' is not defined` in the `/internal/quotes` endpoint | Push-forward commit on PR #117 | The existing `quotes_router.py` already imported `PartnerOrganization` aliased as `_PartnerOrg` (for the PDF renderer in Sprint 16). My scripted patch conditional checked the wrong thing and skipped the top-level import addition. Fix: add the unaliased import to the top-of-file `from models import (...)` block. |
| `NameError: name 'and_' is not defined` in the same endpoint | Second push-forward commit on PR #117 | Same root cause — script conditional skipped the sqlalchemy import line addition. Fix: `from sqlalchemy import and_, or_` at the top of `quotes_router.py`. |
| Anchor mismatch in `InternalDealDetail.jsx` | Story 3 script retry | The file has CRLF line endings (Sprint 16 closure left this on the file). LF-based string anchors fail to match. Updated the apply helper to detect `\r\n` in target content and auto-convert anchor whitespace. Same lesson as Sprint 17 Lesson #2 — promoted to permanent Sprint helper. |

### What landed on `main` during Sprint 18

- `backend/routers/quotes_router.py` — appended four new endpoints (`PATCH /active-scenario`, `GET /scenarios`, `GET /internal/quotes`, `GET /partners/{id}/quotes`). Top-level imports gained `PartnerOrganization` and `from sqlalchemy import and_, or_`. No new dependencies.
- `backend/tests/test_quote_scenarios.py` (new, 10 tests)
- `backend/tests/test_internal_quotes.py` (new, 6 tests)
- `backend/tests/test_partner_quotes.py` (new, 5 tests)
- `frontend/src/utils/currency.js` (new) — shared `formatCurrency(amount, currencyCode)` + `CURRENCY_SYMBOL` map
- `frontend/src/pages/QuoteDetail.jsx` — scenario comparison panel + scenario fetch + `handleSelectScenario` (PATCHes /active-scenario then /active-version); migrated to shared currency util
- `frontend/src/pages/QuoteForm.jsx` — scenario-label dropdown greys out already-created labels in new-version mode; migrated to shared currency util
- `frontend/src/pages/DealDetail.jsx` (portal `/portal/deals/:id`) — recommended-scenario badge + read-only scenario tabs when multiple exist; migrated to shared currency util
- `frontend/src/pages/InternalQuotes.jsx` (new) — `/internal/quotes` dashboard
- `frontend/src/pages/PortalQuotes.jsx` (new) — `/portal/quotes` partner quote history
- `frontend/src/pages/InternalDealDetail.jsx` — `DealHeaderQuoteBadge` appended at module scope and rendered in the page header next to status/commission chips
- `frontend/src/App.jsx` — new `/internal/quotes` and `/portal/quotes` routes
- `frontend/src/layouts/InternalLayout.jsx` — Quotes nav item between Deals and Users (new IconDoc), breadcrumb entry
- `frontend/src/layouts/PartnerPortalLayout.jsx` — My Quotes nav item between Commissions and Training (using existing IconDoc), breadcrumb entry
- `PROJECT_CONTEXT.md` — Section 1 (4 new endpoints), Section 3 (4 file entries), Section 6 (AD-23 + AD-24)
- `CLAUDE.md` — current-state paragraph, Sprint 18 IDs, tech-debt refresh
- `RUNBOOK.md` — new §16 Phase 5 happy-path validation
- `CLAUDE_HISTORY.md` — this Sprint 18 entry + Phase 5 complete marker

### API endpoints added (Sprint 18)

| Method | Path | Auth | Notes |
|---|---|---|---|
| PATCH | `/quotes/{id}/active-scenario` | Internal write roles | Re-point `active_scenario`; 422 if label has no non-deleted version |
| GET | `/quotes/{id}/scenarios` | tenant-scoped | Latest non-deleted version per scenario_label, canonical order |
| GET | `/internal/quotes` | Internal write roles | Cross-deal dashboard + system summary |
| GET | `/partners/{id}/quotes` | partner_admin / partner_user (own org) | Partner-facing quote history; internal 403 |

Total API surface ends Sprint 18 at **~118 endpoints** (Sprint 17 baseline 114 + 4) + 7 endpoints with the `?export=csv` extension.

### Migrations added

None. Alembic head remains **026** (Sprint 17). All Sprint 18 schema requirements were already in place via migrations 023–026 (`active_scenario` / `scenario_label` columns shipped in Sprint 15 / migration 024).

### Test count

| Source | Count |
|---|---|
| Sprint 17 baseline | 535 |
| Story 1 scenario tests | +10 |
| Story 2 internal quotes tests | +6 |
| Story 3 partner quotes tests | +5 |
| **Sprint 18 total** | **~556** |

(A precise post-merge count is asserted in the Phase C closeout report after `pytest backend/tests/ -v` against merged `main`.)

### Sprint 18 lessons

1. **Scripted edits that gate import additions on a substring check can be fooled by aliased imports.** Story 2 had `from models import PartnerOrganization as _PartnerOrg` inside the PDF section, so the `if "PartnerOrganization" not in router:` check returned False and the top-of-file import was never added. Two fix-forward commits caught it. Lesson: gate import additions on the literal *line being added*, not a substring that could already appear in an alias or comment elsewhere in the file.
2. **CRLF line endings on Windows-authored files break LF-only anchor matching.** Same lesson as Sprint 17 Lesson #2, now permanently codified in the Sprint 18 helper: `apply()` detects `\r\n` in the file content and converts the anchor on the fly. `InternalDealDetail.jsx` was the canonical example — Sprint 16's script left it CRLF-encoded.
3. **`utils/currency.js` finally exists.** Three pages had been duplicating the same `formatCurrency` + `CURRENCY_SYMBOL` for two sprints. Sprint 18's extraction took a few minutes but removed the maintenance hazard — any new currency only needs to be added once. The PDF generator's own `CURRENCY_SYMBOL` constant stays inside `quotes_router.py` because the PDF renderer is server-side and can't import from `frontend/src/utils/`.
4. **Closing the Phase 5 epic at sprint close requires manual transition.** Story 4's last sub-task explicitly transitions `FPRM-238` to Done in Jira — the rule-based auto-merger only touches ticket transitions on PR merge, not on the epic at phase close. Captured here so the same step is run for the Phase 6 closeout.

---

## ✅ PHASE 5 COMPLETE — Quoting Module & Enforcement

**Sprints:** 15–18 | **Total points:** 82 | **PR range:** #103–#118

| Sprint | Points | Key Delivery |
|--------|--------|--------------|
| Sprint 15 | 21 | Pricing catalogue (migrations 023–024, 30 seeded rows), `quote_engine.py` (AD-18), Quote CRUD API (10 endpoints) |
| Sprint 16 | 21 | `QuoteForm`/`QuoteDetail` UI, PDF generation (migration 025, reportlab, base64 storage AD-19), CSV export on 7 list views (AD-20) |
| Sprint 17 | 20 | Dynamic activation enforcement (AD-21), multi-step approval enforcement (migration 026, AD-22) |
| Sprint 18 | 20 | Scenario management (AD-24), multi-currency display (AD-23), `/internal/quotes` dashboard, `/portal/quotes`, deal-header quote badge |

**Phase 5 API surface added:** ~17 new endpoints (10 in S15 + 2 in S16 + 1 in S17 + 4 in S18) + 7 endpoints extended with `?export=csv`.
**Migrations added:** 023 (pricing catalogue + seeds), 024 (quotes tables), 025 (PDF columns), 026 (approval_step_records).
**Test count:** 535 (entering Sprint 17) → ~556 (Phase 5 complete).
**Phase 4 deferrals retired:** Dynamic activation enforcement ✅ | Multi-step approval enforcement ✅
**Phase 5 ADs added:** AD-18 (quote engine), AD-19 (PDF base64 storage), AD-20 (fetch+Blob downloads), AD-21 (dynamic activation), AD-22 (multi-step approval), AD-23 (multi-currency display), AD-24 (quote scenario selection).

### Phase 6 readiness

Phase 6 scope (in priority order):
1. **HubSpot integration (FR-HS).** Detailed design inputs already documented. Likely the largest Phase 6 epic.
2. **Implementation services pricing quote.** Sister module to the Phase 5 software pricing engine, but services-side (per-day / per-engagement rates).
3. **Training catalogue (FR-TRN).** First-class training program records linked to partner certification + activation.
4. **`PartnerTier` enum retirement.** Final FK migration to `partner_tiers` table.
5. **Sweep deprecation warnings.** `datetime.utcnow()` → `datetime.now(timezone.utc)` before Python 3.14.

Migration head entering Phase 6: **026**
Last Jira ticket entering Phase 6: **FPRM-298**
Test baseline entering Phase 6: **~556 passing**
Phase 5 epic status: **FPRM-238 — Done**

---

## Sprint 19 — Pricing Catalogue Admin (Phase 6 Sprint 1 of 4)

**Started:** 2026-05-20
**Closed:** 2026-05-20 (single-day intensive)
**Fix Version ID:** `10802`
**Native Sprint ID:** `775`
**Phase 6 epic:** **FPRM-299** — Pricing Admin, Services Quote & Partner Enablement

Sprint 19 made the Sprint 15 pricing catalogue admin-maintainable. Every row in `feature_plan_prices`, `volume_discount_tiers`, and `addon_catalog_items` — previously seed-only via migration 023 — is now a data operation behind a new admin CRUD API + Program Config UI. AD-25 codifies the convention that pricing changes are never new Alembic migrations.

### Sprint 19 stories — outcome

| Key | Story | Pts | Status | PR | Notes |
|---|---|---|---|---|---|
| FPRM-300 | Pricing catalogue backend — admin CRUD API | 6 | Done | #124 | New `backend/routers/pricing_admin_router.py` with 9 write endpoints. Existing GETs for plans + addons gained `?include_inactive=true` (admin-only). Soft-delete pattern. Last-active-row guard on plan prices. Range-overlap validation on volume tiers; gap-aware DELETE with `?force=true` override. Case-insensitive unique addon_key. Audit events under `pricing.*` action prefix. 18 unit tests in `test_pricing_admin.py`. |
| FPRM-304 | Pricing catalogue admin UI — Program Config integration | 8 | Done | #125 | New "Pricing" tab on `/internal/program-config` with three sub-sections (Feature Plan Prices / Volume Discount Tiers / Add-on Catalogue). Inline edit + soft-delete + add forms. Status badges per plan price row (Active / Scheduled / Inactive). View-history + show-inactive toggles. Reactivate flow. Persistent amber warning banner: "Price changes take effect immediately for all new quotes. Existing quote versions are not affected." Role-gated: channel_ops_admin / system_admin can edit; system_admin only for deactivation. Auto-generated addon_key on new add-ons. |
| FPRM-308 | Pricing catalogue audit trail and effective-date management | 4 | Done | #126 | Backend: `/admin/audit-log` gains `?action_prefix=pricing` and `?export=csv` (AD-20 pattern). `quote_engine.calculate_quote` filters `effective_from <= date.today()` so scheduled future-dated rows are stored but inert. +5 unit tests. Frontend: new `PricingHistoryPanel` collapsible at the bottom of the Pricing tab (system_admin only — `/admin/audit-log` requires `user_management:read_all`) groups events by date with a discreet `Export CSV` button. New preview impact widget in plan-price EditRow showing a 5T + 5L compact preview plus an amber change-impact banner when any field differs from the original. AD-25 codifies the pricing-as-data pattern. |
| FPRM-311 | Sprint 19 docs and closeout | 3 | Done | #<this PR> | This entry + Phase 6 sprint summary table + PROJECT_CONTEXT.md Section 1 (13 new / extended endpoints) + AD-25 + CLAUDE.md (current-state paragraph, Sprint 19 IDs, AD-25 reference). |

All 11 sub-tasks (FPRM-301..303, 305..307, 309..310, 312..314) closed Done.

### What landed on `main` during Sprint 19

- `backend/routers/pricing_admin_router.py` (new) — 9 write endpoints + 1 GET for volume tiers
- `backend/routers/quotes_router.py` — `?include_inactive=true` on the two existing pricing GETs
- `backend/routers/admin_router.py` — `?action_prefix` filter and `?export=csv` on `/admin/audit-log`
- `backend/quote_engine.py` — added `from datetime import date`; engine now filters `effective_from <= date.today()`
- `backend/tests/test_pricing_admin.py` (new, 23 tests total: 18 CRUD + 5 audit/effective-date)
- `backend/main.py` — registered `pricing_admin_router`
- `frontend/src/pages/ProgramConfig.jsx` — new `pricing` tab + three sub-sections + `PricingHistoryPanel` + preview impact widget
- `PROJECT_CONTEXT.md` — Section 1 (13 new/extended endpoints), Section 6 (AD-25)
- `CLAUDE.md` — current-state paragraph, Sprint 19 fix/native IDs, AD-25 reference

### API endpoints added (Sprint 19)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/internal/config/pricing/plans` | channel_ops_admin / system_admin | Create FeaturePlanPrice |
| PATCH | `/internal/config/pricing/plans/{plan_price_id}` | channel_ops_admin / system_admin | Update prices, effective_from, is_active |
| DELETE | `/internal/config/pricing/plans/{plan_price_id}` | system_admin only | Soft delete; last-active-row guard |
| GET | `/internal/config/pricing/volume-tiers` | any internal | New read endpoint |
| POST | `/internal/config/pricing/volume-tiers` | channel_ops_admin / system_admin | Create with overlap check |
| PATCH | `/internal/config/pricing/volume-tiers/{tier_id}` | channel_ops_admin / system_admin | Update with overlap re-check |
| DELETE | `/internal/config/pricing/volume-tiers/{tier_id}` | system_admin only | Soft delete with gap warning + `?force=true` |
| POST | `/internal/config/pricing/addons` | channel_ops_admin / system_admin | Unique addon_key (case-insensitive) |
| PATCH | `/internal/config/pricing/addons/{addon_id}` | channel_ops_admin / system_admin | Update display / price / availability |
| DELETE | `/internal/config/pricing/addons/{addon_id}` | system_admin only | Soft delete |

Extended endpoints:

| Method | Path | Change |
|---|---|---|
| GET | `/internal/config/pricing/plans` | + `?include_inactive=true` (admin-only) |
| GET | `/internal/config/pricing/addons` | + `?include_inactive=true` (admin-only) |
| GET | `/admin/audit-log` | + `?action_prefix=pricing` and `?export=csv` |

Total API surface ends Sprint 19 at **~127 endpoints** (Sprint 18 baseline 118 + 9 new write endpoints) + 8 endpoints with the `?export=csv` extension (Sprint 18 baseline 7 + `/admin/audit-log`).

### Migrations added

None. Alembic head remains **026** (Sprint 17). All pricing tables shipped in migration 023 (Sprint 15). AD-25 codifies the convention that pricing changes are data operations, not migrations.

### Test count

| Source | Count |
|---|---|
| Sprint 18 + post-phase fixes baseline | 556 |
| Story 1 pricing admin CRUD tests | +18 |
| Story 3 audit + effective-date tests | +5 |
| **Sprint 19 total** | **579** |

(A precise post-merge count is asserted in the Phase C closeout report after `pytest backend/tests/ -v` against merged `main`.)

### Sprint 19 lessons

1. **Auditing `action` ≠ `object_type`.** The audit log column is `action` (dot-notation like `pricing.plan_price_created`), not `event_type` as the prompt's pseudocode suggested. The existing `object_type` filter does an exact-match on the model name (`feature_plan_price`). Reading `audit.py` + `admin_router.py` *before* writing made the right design jump: add a new `action_prefix` query param that filters `AuditLog.action LIKE 'pricing.%'` instead of overloading the existing `object_type` filter. Lesson: confirm column names + existing filter semantics first; the prompt's pseudocode is a sketch, not a spec.
2. **Scheduled rows mean the engine needs a `<= today` filter.** Sprint 15 ordered by `effective_from DESC` and took the first row — which would immediately apply any future-dated row, breaking the "Scheduled" badge concept. Adding `FeaturePlanPrice.effective_from <= date.today()` to the engine query is the smallest change that makes the badge meaningful. Existing tests (all using 2024-01-01 seed dates) are unaffected.
3. **/admin/audit-log permission gating constrains who can see the history panel.** `user_management:read_all` is system_admin-only, so the frontend `PricingHistoryPanel` is shown only to system_admin. Channel_ops_admin can still edit pricing — they just can't view the change history in the UI. Loosening the permission was tempting but out of scope for Sprint 19; the design note is captured here so a future sprint can decide whether to widen it.
4. **calculate_quote signature is `qty_transactional` / `qty_limited_tech_quoted`, not `qty_transactional_users` / `qty_limited_tech_users`.** The Story 3 effective-date tests initially passed the API-layer field names and got `TypeError`. The router (`quotes_router.py`) re-maps the field names; the engine uses its own. When writing engine-level tests, read the signature, don't infer it from the API.
5. **No migration is a feature, not an omission.** Sprint 19 ships purely as API + UI changes — Alembic head stays at 026 throughout. AD-25 codifies this as the standing convention: pricing is data, not schema. The same will apply to any future admin-config sprint that operates on already-existing tables.

### Phase 6 progress (running)

| Sprint | Theme | Stories | Points | Status |
|---|---|---|---|---|
| 19 | Pricing catalogue admin (CRUD API + UI + audit trail) | 4 | 21 | **Done** |
| 20 | Deal enhancements (Section A + B SPICED form, internal create, addon category/sort) | 5 | 22 | **Done** |
| 21 | TBD | TBD | TBD | Pending |
| 22 | TBD | TBD | TBD | Pending |

(Sprint 20 was reframed from "Implementation services pricing quote" to "Deal enhancements" mid-Phase 6 — services quote deferred again pending business design input.)

---

## Sprint 20 — Deal Enhancements (Phase 6 Sprint 2 of 4)

**Started:** 2026-05-20
**Closed:** 2026-05-20 (single-day intensive)
**Fix Version ID:** `10835`
**Native Sprint ID:** `808`
**Phase 6 epic:** **FPRM-299** — Pricing Admin, Services Quote & Partner Enablement

Sprint 20 was reframed from the originally-planned "Implementation Services Pricing Quote" (deferred again pending business design input) into a **Deal Enhancements** sprint addressing two UI-testing-discovered gaps and one catalogue scalability problem: (1) the deal registration form was missing the full DEAL INFORMATION specification (Section A additional prospect/engagement fields + Section B Current State and Needs Assessment using the SPICED framework); (2) only partners could create deal registrations — channel managers had no way to capture an opportunity identified during a partner call; (3) the add-on catalogue had grown to 68 items with no organisation, making the Pricing tab and quote-form selector unwieldy.

### Sprint 20 stories — outcome

| Key | Story | Pts | Status | PR | Notes |
|---|---|---|---|---|---|
| FPRM-315 | Deal schema extension — Section A + Section B SPICED + `created_on_behalf_of` | 5 | Done | #129 | Migration 027 adds 36 columns to `deal_registrations`. Section A (9): engagement_date, prospect_phone, compiled_by, prospect_contact_name/position, prospect_website, industry_sector, company_size, feature_plan_preference. Section B Current Systems (5): current_system/old_system/inventory_stores/work_orders_prs/monitoring_system. Section B Feature Requirements (15): 13 need_* booleans + integration_with + languages_required free-text. Section B SPICED narratives (6 Text): about_client, pain, impact, critical_event, decision, next_steps. Story 3's `created_on_behalf_of` (Boolean NOT NULL default False, `server_default='false'` for Postgres backfill) consolidated into the same migration. 7 model-level tests cover Section A round-trip, Section B current systems, feature requirements with True/False/null mix, SPICED narratives, no-regression default-null, on-behalf flag, and a schema-presence smoke test. |
| FPRM-316 | Deal form update — full Section A + Section B in portal and internal view | 6 | Done | #130 | Backend `CREATABLE_FIELDS` extended with 35 new keys (`created_on_behalf_of` deliberately excluded — server-only). New `_coerce_dates` helper parses ISO date strings for `estimated_close_date` and `engagement_date`, fixing a latent Postgres/SQLite parity issue. Partner portal `DealRegistrationForm.jsx` gains two new sections: "Additional prospect details" (Section A) and "Current State and Needs Assessment (SPICED)" (Section B with About-the-Client textarea, Current Systems table of 5 dropdowns, Features Required checkbox grid with conditional integration_with / languages_required follow-ups, and SPICED narrative textareas). `compiled_by` pre-populates with the logged-in user's email on a new draft. Internal `InternalDealDetail.jsx` gets a new collapsible `DealInformationSection` showing all Section A + B read-only with ✅/❌/— for the booleans. 6 API-level tests cover Section A round-trip, Section B PATCH, no-regression bare create, `feature_plan_preference` returned on GET, three-state boolean handling, and `created_on_behalf_of` whitelist lockdown. **Spec deviation**: the Phase 6 doc claimed `qty_transactional_users` and `qty_limited_tech_users` already lived on `deal_registrations`, but they're on `quote_versions` — those fields were **omitted** from the partner deal form to honour the user's "two migrations in Sprint 20" constraint. User counts continue to be set at quote time. |
| FPRM-317 | Internal deal creation — channel managers create deals on behalf of partners | 4 | Done | #131 | New `_resolve_create_partner` helper in `deal_registrations_router.py` consolidates auth for POST: partner_admin uses JWT (existing path, activation-gated); channel_manager / channel_ops_admin / system_admin must supply `partner_org_id` in body (validated against `PartnerStatus.active`); activation gate **skipped** on the internal path; `created_on_behalf_of` set True; distinct `deal_registration.created_internal` audit action. Frontend: "+ New Deal" primary button on `DealQueue.jsx` opens a focused `NewDealModal` (Partner Org selector loading from `/internal/partners?status=active` + Section A core fields + opening SPICED textareas). After save, channel manager is navigated to the deal detail page. Grey "Created by Channel Manager" badge on `InternalDealDetail.jsx` header when `created_on_behalf_of=True`. 7 API-level tests cover the happy path, missing `partner_org_id` (422), nonexistent partner (404), suspended partner (422), partner_admin no-regression, audit event presence, and partner_user 403. **Spec deviation**: the modal does not embed the full `DealRegistrationForm.jsx` page — extracting that 500-line page into a reusable presentational component was beyond the 4-point scope. Modal captures essentials; partner completes remaining Section B fields. |
| FPRM-318 | Add-on catalogue category and sort order | 4 | Done | #132 | Migration 028 adds `category` (String, nullable) and `sort_order` (Integer, NOT NULL, default 0 via `server_default='0'`) to `addon_catalog_items`. `_serialise_addon` returns both new fields. PATCH accepts `category` (empty string clears to null) and `sort_order` (negatives clamped to 0; non-int → 422). GET `/internal/config/pricing/addons` accepts `?category=` filter (`__null__` matches uncategorised); orders by `(category, sort_order, display_name)`. Per AD-25 the taxonomy itself is admin-maintainable data — migration only creates the columns. Pricing admin tab adds category filter dropdown + inline-editable Category and Sort columns; create flow does POST then follow-up PATCH so admins get one-click create-with-organisation. Quote-form add-on selector groups by category with uppercase section headers; uncategorised items in a final "Other" group. 5 backend tests cover defaults, PATCH set/clear, category filter, negative clamp + invalid 422, and `__null__` filter. |
| FPRM-319 | Sprint 20 docs and closeout | 3 | Done | #<this PR> | This entry + Sprint 20 row in Phase 6 progress table + PROJECT_CONTEXT.md endpoint additions + CLAUDE.md (current-state paragraph, Sprint 20 IDs, refreshed tech-debt entries: services-quote deferral note, full-form-reuse polish backlog, empty category taxonomy follow-up). |

All 12 sub-tasks (FPRM-320..328 implementation, FPRM-329..331 docs/closeout) closed Done.

### What landed on `main` during Sprint 20

- `backend/models.py` — 36 new columns on `DealRegistration`; 2 new columns on `AddonCatalogItem`
- `backend/alembic/versions/027_extend_deal_registrations.py` (new) — Section A + B + `created_on_behalf_of`
- `backend/alembic/versions/028_addon_category_sort_order.py` (new) — addon `category` and `sort_order`
- `backend/routers/deal_registrations_router.py` — `CREATABLE_FIELDS` extended; `_coerce_dates` helper; `_resolve_create_partner` helper; POST refactored for dual partner/internal paths; new `deal_registration.created_internal` audit action
- `backend/routers/pricing_admin_router.py` — `_serialise_addon` extended; PATCH accepts category/sort_order
- `backend/routers/quotes_router.py` — GET addons accepts `?category=` filter, returns new fields, orders by `(category, sort_order, display_name)`
- `backend/tests/test_deal_registration_model.py` — +7 model tests
- `backend/tests/test_deal_registrations.py` — +6 Section A/B API tests + +7 internal create tests
- `backend/tests/test_pricing_admin.py` — +5 addon category/sort tests
- `frontend/src/pages/DealRegistrationForm.jsx` — Section A additional details + Section B SPICED sections; `compiled_by` JWT pre-fill
- `frontend/src/pages/InternalDealDetail.jsx` — collapsible `DealInformationSection` + on-behalf badge
- `frontend/src/pages/DealQueue.jsx` — "+ New Deal" button + `NewDealModal` with Partner Org selector
- `frontend/src/pages/ProgramConfig.jsx` — `AddonCatalogueSection` gains Category filter dropdown + Category and Sort columns + inline edit + add-row support
- `frontend/src/pages/QuoteForm.jsx` — `groupedAddons` memo groups selector by category with section headers

### API endpoints — Sprint 20 changes

| Method | Path | Change |
|---|---|---|
| POST | `/deal-registrations` | Now accepts channel_manager / channel_ops_admin / system_admin with `partner_org_id` in body (FPRM-317). Activation gate skipped for internal-create path. Sets `created_on_behalf_of=True` and logs `deal_registration.created_internal`. Existing partner_admin path unchanged. |
| POST | `/deal-registrations` (partner_admin) | Body whitelist extended with 35 new Section A + B keys (FPRM-316). `created_on_behalf_of` deliberately excluded. |
| PATCH | `/deal-registrations/{id}` | Same body whitelist extension (FPRM-316). Date-string coercion via `_coerce_dates`. |
| GET | `/deal-registrations/{id}` | Returns all 36 new Section A + B columns + `created_on_behalf_of` (via existing `_serialize` which auto-walks `__table__.columns`). |
| GET | `/internal/config/pricing/addons` | + `?category=` filter (`__null__` for uncategorised). Response now includes `category` and `sort_order`. Ordering: `(category, sort_order, display_name)`. (FPRM-318) |
| PATCH | `/internal/config/pricing/addons/{id}` | Body now accepts `category` (empty string clears to null) and `sort_order` (negatives clamped, non-int → 422). (FPRM-318) |

No new endpoints — Sprint 20 extends existing ones. Total API surface unchanged at ~127.

### Migrations added

| Revision | File | Purpose |
|---|---|---|
| 027 | `027_extend_deal_registrations.py` | 36 new columns on `deal_registrations` (Section A + B SPICED + `created_on_behalf_of`) |
| 028 | `028_addon_category_sort_order.py` | `category` (nullable) + `sort_order` (NOT NULL default 0) on `addon_catalog_items` |

Alembic head bumps from 026 → **028**.

### Test count

| Source | Count |
|---|---|
| Sprint 19 baseline | 579 |
| Story 1 deal schema model tests | +7 |
| Story 2 deal API Section A/B tests | +6 |
| Story 3 internal-create tests | +7 |
| Story 4 addon category/sort tests | +5 |
| **Sprint 20 total** | **604** |

### Sprint 20 lessons

1. **The spec's "already exists" notes are not always correct.** The Phase 6 doc claimed `qty_transactional_users` / `qty_limited_tech_users` already lived on `deal_registrations` — they're on `quote_versions`. Cross-check field-location claims against `models.py` before writing form fields that depend on them. Story 2 omitted those two fields rather than violate the user's "two migrations in Sprint 20" constraint.
2. **SQLite tests catch Postgres/SQLite-divergent ORM behaviour the production runtime hides.** The existing `estimated_close_date` field had been accepting ISO date strings in Postgres for months — when Story 2 added the first API test that POSTed a date string, SQLite errored with "Date type only accepts Python date objects". The `_coerce_dates` helper fixes both the new and the pre-existing field. Lesson: if a column type needs coercion, do it server-side at the boundary regardless of which DB driver currently masks it.
3. **Whitelist-based POST/PATCH bodies need explicit exclusion notes.** `created_on_behalf_of` was deliberately left out of `CREATABLE_FIELDS` so partners can't toggle it via PATCH. Without a comment, a future hand could "fix" the omission and silently break the FPRM-317 server-only invariant. The lockdown test guards behaviour; the comment in `CREATABLE_FIELDS` explains intent.
4. **Modal "reuse the full form" is often a 3-point ask hidden in a 2-point subtask.** The spec said embed the partner-side `DealRegistrationForm.jsx` in the internal modal. That 500-line page has page-routing assumptions, save-vs-submit logic, and JWT-bound state — refactoring it into a reusable presentational component is real work. Story 3 chose a focused modal capturing essentials instead, documented the tradeoff in the PR, and added the full-reuse refactor to tech debt. Bounded scope > unbounded fidelity.
5. **Migrations stay sequential; admin data does not.** Story 4 added migration 028 for `addon_catalog_items` columns but did **not** seed categories — those flow through the pricing admin API per AD-25. The migration is the smallest possible thing that unblocks the UI; the taxonomy itself is admin-maintained data. Empty taxonomies show as "Other" in the quote form, which is acceptable until ops populates them.

---

## Post-Sprint 20 UX & Workflow Fixes (PRs #128–#163)

**Closed:** 2026-05-22
**Migration head:** 028 → **033**
**Tests:** 604 → **711**
**Last PR merged in this session:** **#167**
**No Jira ticket** — driven by direct browser testing of the Sprint 20 deliverables; the user opted to run polish as an unticketed session and reconcile docs in a follow-up sweep (this entry).

### Why this session existed

Sprint 20 closed clean on Alembic 028, but live partner-portal and internal-queue smoke tests surfaced a long tail of UX gaps and workflow holes: the deal form needed restructure for the SPICED assessment to be usable, list views had no sortable columns, the quote lifecycle was missing terminal states (cancelled / lost / withdrawn / won) and a retract path, commission rates needed an admin tab, pipeline values were drifting from the actual quoted state, and deal headers had stale single-quote assumptions. Rather than packaging into a new sprint, the user worked through the punch list directly with Claude Code, opening one PR at a time, each merged via the standard auto-merger before the next.

### Key deliverables

- **Deal form restructure** — Section A and Section B SPICED assessment laid out with a dedicated partner contact-information section; combobox for current systems fields (replacing free-form text); evenly split feature checkboxes.
- **Internal deal creation by channel managers** — the partner-only `POST /deal-registrations` path opened to channel_manager / channel_ops_admin / system_admin (migration 027 had already added `created_on_behalf_of`; this session wired the UI's "New Deal" modal into the same partner pool).
- **Add-on catalogue seeded** — 47 new add-on rows added via the AD-25 admin API (no migration).
- **Migration 029** — license qty columns (`qty_transactional_users` / `qty_limited_tech_users`) finally land on `deal_registrations`. Was a Sprint 20 spec deviation; now corrected.
- **Migration 030** — `customer_contact_position` hotfix (column missed under certain SQLite test paths in 029).
- **Sortable columns** — `SortableTh` shared component (`frontend/src/components/SortableTh.jsx`) added and adopted across all 9 list views.
- **Commission Rates admin tab** — new tab in Program Config powered by the new `/internal/config/commission-rates` endpoints; migration 031 adds `is_active` + timestamps to `commission_structures`. Per AD-25 commission catalogue entries are now admin-maintained.
- **Conflict check rerun button** — `POST /internal/deals/{id}/conflict-check` exposed on `InternalDealDetail.jsx` so reviewers can re-run the checker after data changes without retransitioning the deal.
- **Pipeline toggle + extended terminal statuses** — `quotes.include_in_pipeline` toggle (migration 032) plus deal terminal statuses `cancelled` / `lost` / `withdrawn` / `won`. The per-deal `pipeline_total` now reads `include_in_pipeline` exclusively.
- **Quote document attachment + acceptance gate** — new `quote_documents` table (migration 033) and `POST/GET/GET(download)/DELETE /quotes/{id}/documents` endpoints. `PATCH /quotes/{id}/status` rejects `sent → accepted` unless a non-deleted `signed_acceptance` document exists.
- **Deal Won with cascade quote cancellation** — `POST /internal/deals/{id}/won` requires at least one accepted quote on the deal and cascade-cancels every other non-terminal quote version on the same deal (audit per quote).
- **system_admin approval break-glass bypass** — multi-step approval enforcement (AD-22) now treats system_admin as satisfying any `required_role`, unblocking emergency reviews without a Jira-ticketed workflow edit.
- **Quote version lock on terminal states** — `accepted` / `expired` / `cancelled` quotes hide Add Version / Set as Active controls.
- **Quote retract** — `accepted → sent` transition added to `PATCH /quotes/{id}/status`, **system_admin only** (the rest of the state machine unchanged).
- **Portal pipeline values corrected** — `My Pipeline` summary cards and Kanban columns now reflect `pipeline_total` (sum of include_in_pipeline quotes) not `estimated_deal_value`.
- **Deal header redesigned** — multi-quote model surfaces a Pipeline Value badge + Quote Accepted chip instead of the old single-quote summary.
- **Deep link** — `/internal/quotes` row links open the quote modal directly on `/internal/deals/:id?openQuote=:quote_id`.
- **Channel manager test user** — `cmtest@test.com / TestPass123!` (role `channel_manager`) created for ongoing validation; recorded in `RUNBOOK.md` §2.

### Migrations added

| Revision | File | Purpose |
|---|---|---|
| 029 | `029_add_license_qty_to_deal_registrations.py` | `qty_transactional_users` / `qty_limited_tech_users` columns on `deal_registrations` (closes Sprint 20 spec deviation) |
| 030 | `030_add_customer_contact_position.py` | `customer_contact_position` column hotfix (idempotent — covers SQLite test paths missed by 029) |
| 031 | `031_extend_commission_structures.py` | `is_active` + `created_at` + `updated_at` on `commission_structures` (unblocks Commission Rates admin tab) |
| 032 | `032_pipeline_toggle_and_quote_composition.py` | `quotes.include_in_pipeline` + `quote_versions.includes_software` / `includes_services` |
| 033 | `033_create_quote_documents.py` | New `quote_documents` table (acceptance-gate substrate) |

Alembic head bumps from 028 → **033**.

### Frontend design standards codified

This session also produced a multi-page design consistency audit (`InternalQuotes.jsx` chosen as the reference template). Seven new ADs (**AD-26 through AD-32**) and a new **PROJECT_CONTEXT.md Section 7** lock the layout grammar: filter-bar layout, tinted status badges, `fp-table` standard, input/select styling, Export CSV placement, the summary-cards rule, and the `fp-card` wrapper convention. The corresponding code changes (standardising the seven non-conformant pages — InternalPartnerList, PartnerUserManagement, InternalUsers, ApplicationQueue, PortalQuotes, DealList, PartnerDocuments) ship as a second PR after this docs sync merges, per the user's "one PR at a time" rule.

### Test count

| Source | Count |
|---|---|
| Sprint 20 baseline | 604 |
| Post-Sprint 20 net additions across PRs #128–#167 | +107 |
| **Post-Sprint 20 total** | **711** |

### Lessons

1. **Unticketed sessions need a docs-sync follow-up.** Skipping Jira during a polish run is fine when the user is driving the punch list interactively, but the canonical project docs (CLAUDE.md / PROJECT_CONTEXT.md / CLAUDE_HISTORY.md / RUNBOOK.md) still need a single reconciliation PR at the end. This entry is that PR.
2. **"Migration 028 only adds columns" is a load-bearing AD-25 corollary.** When the user added 47 new add-ons during this session, no migration was required — those are admin data per AD-25. The pattern keeps recurring; the migrations 029–033 in this session all touch *schema*, not catalogue rows, which is the correct distinction to maintain going forward.
3. **The retract path is a system_admin-only operation by design.** Opening `accepted → sent` to channel_manager would invite accidental retract from partners-facing approvals. Keeping it system_admin-only matches the AD-22 break-glass spirit — high-blast-radius reversals stay narrow.
4. **The acceptance gate belongs at the router, not the database.** A CHECK constraint on `quote_documents` would require knowing about quote status (cross-table) and would be hard to bypass for legitimate operational cases (e.g. importing a pre-signed acceptance from a paper contract via a backfill). Router-level enforcement keeps the rule visible alongside the transition code and easy to instrument.
5. **Design audits work best as one read pass, one PR for docs, one PR for code.** The Section 7 + AD-26..32 docs land first so the standards are recorded and reviewable; the code changes that bring the seven non-conformant pages into compliance land as a separate, mechanical PR. The split keeps reviewers focused: "are the standards correct?" vs "does the code conform?"

---

## Frontend Fix Session — 2026-05-26 (PRs #169–#173)

**Date:** 2026-05-26
**Migration head:** 033 (unchanged)
**Tests:** 723 (711 prior + 8 new in PR #175 + 4 new in PR #178)
**Last PR merged:** #178

### Context

Pre-Sprint-21 UI testing session. Browser testing of the post-Sprint-20 deliverables identified 17 issues across portal and internal pages. This session addressed the frontend design standardisation items, nav reorder, and architectural decisions. Fix PR B (date filter bug, draft quote editability, Approved→Accepted label) follows as the next PR.

### What landed on `main` in this session

| PR | Branch type | Change |
|---|---|---|
| #169 | docs | AD-33 added to PROJECT_CONTEXT.md Section 6 and CLAUDE.md — centralised document repository: `partner_documents` as single source of truth, `document_references` join table, `quote_documents` retired in Sprint 21. SOC II / ISO 27001 tenant isolation boundary defined. |
| #170 | fix | `docs/**` added to ci.yml push trigger branches — docs branch PRs now run full pytest matrix + bandit and are eligible for auto-merger. Fixes the manual-merge issue encountered on PR #169. |
| #171 | fix | Frontend design standardisation pass A: `DealQueue.jsx` (AD-26 fp-card filter bar + free-text search); `DealList.jsx` (SortableTh all list columns + free-text search); `PartnerDocuments.jsx` (free-text search + SortableTh Name/Expires); `ApplicationQueue.jsx` (fp-table + fp-card); `InternalQuotes.jsx` (Export CSV placeholder per AD-30); `PartnerPortalLayout.jsx` (My Quotes nav item moved above Commissions). |
| #172 | fix | `PortalQuotes.jsx` fully rebuilt to match `InternalQuotes.jsx` design: 7 summary cards (Total, Draft, Sent, Accepted, Won, Active Pipeline Value, Closed Won); full filter bar (status + plan + search + pipeline toggle); SortableTh on all 8 columns; Partner column removed; `isReadOnly={true}` QuoteDetail modal. TODO Sprint 21: `GET /partners/{id}/quotes` missing `deal_status` field. |
| #173 | fix | `DealList.jsx` list view rebuilt to match `InternalQuotes.jsx` layout: 6 summary cards above filter bar (Total Deals, Total Est Value, Pipeline Value, Approved Pipeline, Won, Info Required); broken date pickers removed; clean filter bar (status + search + buttons); SortableTh on all 6 columns; "Accepted" label for `approved` status. Two new Hard Rules added to `CLAUDE.md`. `PROMPT_TEMPLATE.md` created as new canonical document. |
| #174 | fix | Fix PR B1: draft quote version lock corrected (draft/sent no longer locked); PortalQuotes.jsx QuoteDetail renders as modal overlay not inline; Approved→Accepted label rename completed across DealQueue.jsx, InternalDealDetail.jsx, DealDetail.jsx, PartnerHome.jsx, InternalReports.jsx. |
| #175 | fix | Fix PR B2: backend date filter bug — from_date/to_date params now applied as submitted_at filters in GET /partners/{id}/pipeline and GET /deal-registrations. End-of-day handling for to_date. 422 on malformed date strings. New tests added to test_pipeline.py and test_deal_registrations.py. |
| #176 | fix | Fix PR C: DealQueue.jsx rebuilt to match portal/deals layout — summary cards (Total Deals, Total Est Value, Pipeline Value, Accepted Pipeline, Won $, Info Required), date filter inputs re-added (from_date/to_date wired to PR #175 backend fix), fp-table + SortableTh all columns, Actions column removed, deal name as link, title "Deals". DealList.jsx: Won card changed from count to sum of pipeline_total; "Approved Pipeline" → "Accepted Pipeline" label; filter dropdown "Approved" → "Accepted". InternalHome.jsx: "Approved This Month" → "Accepted This Month". |
| #177 | fix | Fix PR D: DealQueue.jsx full-width layout corrected (matches InternalQuotes.jsx container structure); from_date/to_date params correctly wired in DealQueue.jsx fetch call; date filter inputs re-added to DealList.jsx (portal/deals) wired to GET /partners/{id}/pipeline which supports date filters since PR #175. |
| #178 | fix | Fix PR E: GET /internal/deals now supports from_date/to_date query params applied as submitted_at filters (same pattern as PR #175). End-of-day handling on to_date. 422 on malformed date strings. +4 tests in test_deal_registrations.py. |

### Architectural decisions recorded

- **AD-33** — Centralised document repository (`partner_documents` single source of truth, `document_references` join table, `quote_documents` retired Sprint 21). Full entry in PROJECT_CONTEXT.md Section 6.

### Process improvements introduced

- **CI trigger extended** — `docs/**` branches now run full CI and auto-merge (PR #170).
- **Two new Hard Rules in CLAUDE.md** — post-flight sync mandatory at end of every session; canonical docs must travel in the same PR as the code change that caused them.
- **PROMPT_TEMPLATE.md created** — new canonical document in repo root defining the mandatory structure for every Claude Code prompt. Governs Claude chat as prompt author; complements CLAUDE.md which governs Claude Code as Dev Agent.

### Remaining UI testing items

All UI testing items from the pre-Sprint-21 session resolved. Export CSV for internal/quotes deferred to Sprint 21 (requires GET /internal/quotes/export backend endpoint). Ready for Sprint 21 planning.

### Test count

723 (711 prior + 8 added in PR #175 + 4 added in PR #178)

---

## Sprint 21 — Centralised Document Repository (Phase 6, AD-33)

**Started:** 2026-05-27
**Closed:** 2026-05-27
**Phase 6 Epic:** FPRM-299
**Migration head:** 033 → **036**
**Tests:** 723 → **738**

### Why this sprint

Two systems were holding partner-scoped file bytes side-by-side: `partner_documents`
for compliance / legal / NDA docs, and `quote_documents` (added in migration 033)
for quote acceptance evidence. Each had its own endpoints, its own upload
ceremony, its own tenant-isolation checks. Duplicate stores invite duplicate bugs,
and the `quote_documents` path lacked the `partner_org_id` boundary that
`partner_documents` enforces -- a future deal-attachment feature would have made
the divergence worse. Sprint 21 collapses both into one repository, codified as
AD-33 in PROJECT_CONTEXT.md Section 6.

### What landed on `main` (single PR)

| Layer | File | Change |
|---|---|---|
| Migration 034 | `backend/alembic/versions/034_extend_partner_documents.py` | Add `file_data` Text nullable; relax `file_path` to nullable. Idempotent column-existence checks. |
| Migration 035 | `backend/alembic/versions/035_create_document_references.py` | Create `document_references` table with `(entity_type, entity_id)` and `document_id` indexes; FK to `partner_documents.id` ON DELETE CASCADE. |
| Migration 036 | `backend/alembic/versions/036_backfill_drop_quote_documents.py` | Backfill every `quote_documents` row into `partner_documents` (status `approved`) plus a `document_references` row (`entity_type='quote'`); drop `quote_documents` table. Postgres uses an explicit cast to `document_status` enum, generic dialects pass the string through (kept for sqlite test paths). |
| Model | `backend/models.py` | `PartnerDocument`: `file_data` Text nullable + `file_path` nullable. New `DocumentReference` model. `QuoteDocument` removed. |
| Backend router | `backend/routers/documents_router.py` | Rewritten as the central documents API. New endpoints: single-doc metadata, download, delete, plus 3 references endpoints. `file_data` excluded from every metadata response via a centralised column allow-list. Upload accepts both `file_data` (new) and `file_path` (legacy compat). 10 MB cap on both declared and decoded size. |
| Backend router | `backend/routers/quotes_router.py` | Acceptance gate switched from `QuoteDocument.quote_id` lookup to a join through `DocumentReference` + `PartnerDocument` requiring `status='approved'`. 4 legacy `/quotes/{quote_id}/documents` endpoints retired (upload, list, download, delete). New `GET /quotes/{quote_id}/attached-documents` exposes the join result for the QuoteDetail UI. New `GET /internal/quotes/export` CSV endpoint (closes Sprint 16 TODO). `GET /partners/{id}/quotes` payload + CSV now include `deal_status` (closes the PR #172 TODO). |
| Tests | `backend/tests/test_partner_documents_api.py` (new) | 17 cases covering upload/download/list/patch/delete/references + tenant isolation + 10 MB cap + the no-`file_data` leak guarantee. |
| Tests | `backend/tests/test_migration_034_035.py` (new) | Model-level guarantees for migrations 034 + 035 plus an importability guard on each of 034/035/036 so a syntax error fails CI even though Postgres-specific casts can't run against sqlite. |
| Tests updated | `backend/tests/test_deal_won_cascade.py`, `test_pipeline_toggle_and_terminal_statuses.py`, `test_internal_quotes.py`, `test_partner_quotes.py` | Acceptance-document helpers rewritten to seed `PartnerDocument` + `DocumentReference` directly. CSV header assertion updated for new `Deal Status` column. |
| Tests removed | `backend/tests/test_quote_documents.py` | Endpoints retired; functionality now covered by `test_partner_documents_api.py`. |
| Frontend | `frontend/src/pages/PartnerDocuments.jsx` | Upload modal now reads files as base64 client-side and posts `file_data`. New Download column wired to `/partners/{id}/documents/{doc_id}/download` via fetch+Blob (AD-20). |
| Frontend | `frontend/src/pages/QuoteDetail.jsx` | Document section rewired: `loadDocuments` calls the new `/quotes/{id}/attached-documents`; attach is now a two-step upload + create-reference flow against the partner_documents store; detach removes the document_references row only (the underlying file survives for other links). Download uses the centralised download endpoint. |
| Frontend | `frontend/src/pages/InternalQuotes.jsx` | Export CSV button enabled, wired to `/internal/quotes/export` via fetch+Blob with filter params (AD-20 / AD-30). |
| Docs | `CLAUDE.md`, `PROJECT_CONTEXT.md`, `RUNBOOK.md`, `CLAUDE_HISTORY.md` | Sprint 21 entry, AD-33 surfaced in CLAUDE.md highlights, current-state paragraph rewritten, known-issue note added about the rotated Jira token. |

### New API endpoints (net +5)

Added (10):

- `POST /partners/{partner_id}/documents` (extended to accept `file_data`)
- `GET /partners/{partner_id}/documents` (extended -- `?status=` filter)
- `GET /partners/{partner_id}/documents/{doc_id}` (new -- single-doc metadata)
- `GET /partners/{partner_id}/documents/{doc_id}/download` (new)
- `DELETE /partners/{partner_id}/documents/{doc_id}` (new)
- `GET /partners/{partner_id}/documents/{doc_id}/references` (new)
- `POST /partners/{partner_id}/documents/{doc_id}/references` (new)
- `DELETE /partners/{partner_id}/documents/{doc_id}/references/{ref_id}` (new)
- `GET /quotes/{quote_id}/attached-documents` (new)
- `GET /internal/quotes/export` (new)

Retired (4): `POST` / `GET` / `GET .../download` / `DELETE` on `/quotes/{quote_id}/documents/...`

### Lessons

1. **One table, one boundary.** The pre-Sprint-21 `quote_documents` path enforced
   tenant isolation indirectly (via a `quote.partner_org_id` join). Moving the
   bytes into `partner_documents` puts the boundary on the row itself and lets a
   single helper (`_load_doc_or_404`) enforce it. Anything that crosses table
   boundaries to compute "may this caller see this row?" is fragile -- collapse
   it where you can.
2. **A migration that drops a table needs the model and the router gone in the
   same commit.** Half-deletes (e.g. migration drops `quote_documents` but the
   ORM still imports `QuoteDocument`) break service startup. The fix is to treat
   the migration + model removal + router removal + test cleanup as one atomic
   landing. Sprint 21's single-PR approach makes this enforceable.
3. **Tests that mark quotes accepted via the API need a helper that abstracts
   the gate, not a duplicated upload snippet.** Four test files had near-
   identical `_attach_acceptance_doc` helpers calling the now-retired endpoint;
   one missed update would have rotted silently. The Sprint 21 rewrite seeds
   the document + reference directly through the session, which is both faster
   and decoupled from the upload API's evolution.
4. **The Jira token rots silently between sessions.** The Sprint 21 prompt's
   Phase A (fix version + native sprint + 5 stories) couldn't run because
   `JIRA_API_TOKEN` returns 401. The hard rule was satisfied by the PR-level
   structure (one PR, all changes traceable through the diff), but future
   sprints should pre-flight the token in the prompt and fail fast if it's
   rejected -- recorded as a known issue in CLAUDE.md.

---

## Sprint 21 Hotfix -- Post-Sprint-21 Bug Fixes

**Started:** 2026-05-27
**Closed:** 2026-05-27
**Fix Version:** Sprint 21 (10868) -- same sprint, no new fix version
**Native Sprint:** 841
**Tests:** 738 → **740**

### Why this hotfix

UI testing on the Sprint 21 PR after merge surfaced five bugs that fell into
two distinct buckets. The first three are interlocked: the quote acceptance
gate was silently rejecting status transitions even though documents were
visibly attached, and the quote modal lacked a path to reuse an existing
partner document (only Upload New worked). The remaining two are smaller:
the internal `/internal/partners/:id/documents` page was constrained to a
narrow column instead of the full-width layout the rest of the internal
pages use, and the `deal_status` field added in Sprint 21 was not actually
returned by `GET /internal/quotes` or rendered as a column in either the
internal or portal quotes table.

### Bugs fixed

| Key | Bug | Root cause |
|---|---|---|
| FPRM-353 | Mark as Accepted does not change quote status even with documents attached | The acceptance gate joined `document_references` → `partner_documents` and filtered on `PartnerDocument.status == 'approved'`. Documents uploaded via the QuoteDetail modal arrive with the default `status='pending_review'` and there is no UI path to flip them to approved. The button enabled (because the document_type matched), the click PATCHed status, the backend returned 422 with a "proof must be attached" detail, and the user saw an error that contradicted the visible attachment. Fix: drop the `status='approved'` filter from the gate -- the attachment via `document_references` IS the affirmative evidence act; the status field on `partner_documents` is for the KYC review workflow, not quote acceptance. |
| FPRM-354 | Cannot open/edit existing draft quote to attach a document | Investigation showed the modal already opened for drafts (no status gate on the View button) and the document section already showed the "+ Attach Document" button. The actual gap was the single-path Upload New flow -- the user expected to ALSO be able to reuse an existing partner document without re-uploading. Subsumed into FPRM-355. |
| FPRM-355 | Quote document section still shows old direct-upload form -- picker and upload flow not rendering | The Sprint 21 implementation only built the Upload New path. Added a two-tab UI inside the same panel: Upload New (default, original flow) and Pick Existing (lists `GET /partners/{id}/documents`, excludes already-attached docs, attach button POSTs a single reference). |
| FPRM-356 | Internal partner documents page does not fit to full page width | `internalMode` wrapped content in `<div className="fp-page">`. The `fp-page` class constrained width whereas every other internal page (DealQueue, DealList, InternalQuotes) uses a plain `<div>` and inherits the full content slot from `InternalLayout`. Fix: drop the class. |
| FPRM-357 | deal_status column missing from internal and portal quotes list UI | Sprint 21 added `deal_status` to `GET /partners/{id}/quotes` but not to `GET /internal/quotes`; and neither the internal nor portal quotes tables rendered the field. Fix: include `deal_status` in the internal-quotes response, plus a `DealStatusBadge` (tinted, AD-27 palette) and new column in both InternalQuotes.jsx and PortalQuotes.jsx. |

### Files changed

| Layer | File | Change |
|---|---|---|
| Backend | `backend/routers/quotes_router.py` | Acceptance gate filter `PartnerDocument.status == DocumentStatus.approved` removed (FPRM-353). `DocumentStatus` import dropped (no longer referenced). `deal_status` added to `GET /internal/quotes` item payload (FPRM-357). |
| Tests | `backend/tests/test_pipeline_toggle_and_terminal_statuses.py` | New `test_accept_quote_with_pending_review_document_succeeds` regression test (FPRM-353). |
| Tests | `backend/tests/test_internal_quotes.py` | New `test_internal_quotes_list_includes_deal_status` (FPRM-357). |
| Frontend | `frontend/src/pages/QuoteDetail.jsx` | Document section gains a tab switcher (Upload New / Pick Existing); new `loadPickList` fetches `/partners/{id}/documents` minus already-attached; new `handleAttachExistingDocument` POSTs a reference only (FPRM-354 / FPRM-355). |
| Frontend | `frontend/src/pages/PartnerDocuments.jsx` | `internalMode` returns a plain `<div>` instead of `<div className="fp-page">` so the page uses full width (FPRM-356). |
| Frontend | `frontend/src/pages/InternalQuotes.jsx` | New `DealStatusBadge` (tinted, AD-27 palette); new Deal Status column between Status and Pipeline; colspan adjusted (FPRM-357). |
| Frontend | `frontend/src/pages/PortalQuotes.jsx` | Same Deal Status column + badge as InternalQuotes (FPRM-357). |

### UX decision recorded

Document attachment from a quote must offer two paths in a single panel:

1. **Upload New** -- creates a `partner_documents` record AND a
   `document_references` row in one operation; the user never leaves the
   quote modal.
2. **Pick Existing** -- selects from existing partner documents, creates a
   `document_references` row only.

This supersedes the Sprint 21 single-path implementation. The acceptance gate
in `PATCH /quotes/{id}/status` now treats the mere presence of an attachment
as sufficient evidence -- it no longer requires `PartnerDocument.status` to
be `'approved'`. The status field on `partner_documents` remains the
substrate for the KYC / compliance review workflow (`documents_router.py`
PATCH endpoint) but is decoupled from the quote acceptance gate.

### Lessons

1. **A gate that depends on two independent state machines silently fails
   when one is off.** The acceptance gate required both "document attached"
   (via `document_references`) AND "document approved" (via
   `partner_documents.status`). The QuoteDetail upload flow only created the
   first; flipping the second required a trip to the Documents page and an
   internal review action that channel managers normally don't perform on
   evidence they uploaded themselves. The fix is the cleaner gate: one
   condition, the attachment itself.
2. **A column added to one of two list endpoints needs to be added to
   both.** Sprint 21 carry-forward fix added `deal_status` to
   `GET /partners/{id}/quotes` (closing the PR #172 TODO) but missed
   `GET /internal/quotes`. The UI then had no column to read regardless.
   Future similar fixes: audit every consumer endpoint when adding a field
   to one of them.
3. **`fp-page` was a layout footgun.** No other internal page uses it. The
   class survived from an earlier layout iteration. Worth a wider audit:
   any class that exists but is used by exactly one page is either
   load-bearing (rename it to advertise that) or vestigial (delete it).

---

## Sprint 22 -- Document Repository v2 (Phase 6)

**Started:** 2026-05-27
**Closed:** 2026-05-27
**Fix Version ID:** 10901
**Native Sprint ID:** 874
**Phase 6 Epic:** FPRM-299

**Stories:** 6 | **Subtasks:** 18 | **Points:** 25
**Migration head:** 036 -> **038**
**Tests:** 740 -> **765** (+25 new Sprint 22 cases)
**New AD:** AD-34 (partner_documents.file_data deprecation)

### Why this sprint

Sprint 21 collapsed the file-storage layer into a single `partner_documents`
store but left three rough edges that the post-sprint UI testing surfaced:
documents could not be versioned (any "upload again" was a brand-new file),
preview required a download round trip, and the approval workflow was hard-
coded in Python instead of admin-maintainable. Sprint 22 closes all three
plus the smaller items deferred from the hotfix: partner self-service delete
and surfacing the uploader's name in list views.

### What landed on `main` (single PR)

| Layer | File | Change |
|---|---|---|
| Migration 037 | `037_document_versions.py` | Create `document_versions` (id, document_id FK CASCADE, version_number, file_data Text, file_size_bytes, mime_type, uploaded_by FK SET NULL, uploaded_at, notes, is_current); UNIQUE(document_id, version_number); ix_doc_versions_document; Postgres partial index ix_doc_versions_current. Add `current_version_number` (Integer nullable) and `version_count` (Integer NOT NULL DEFAULT 1) to `partner_documents`. Backfill every existing row with non-null `file_data` into a v1 `document_versions` row with `is_current=true`. Idempotent column/table checks. |
| Migration 038 | `038_document_type_rules.py` | Create `document_type_rules` (id, document_type UNIQUE, requires_approval, auto_approve, description, created_at, updated_at). Seed rows: `quote_acceptance` (auto-approve, no manual approval) and `contract` (requires approval). Postgres uses `ON CONFLICT DO NOTHING`; sqlite path uses NOT EXISTS sub-select. |
| Models | `backend/models.py` | New `DocumentVersion` model with `versions` relationship on `PartnerDocument`. New `DocumentTypeRule` model. `PartnerDocument.file_data` flagged DEPRECATED in the column comment (AD-34) -- column retained, never written by new code. New columns `current_version_number`, `version_count`. |
| Backend router | `backend/routers/documents_router.py` | Upload endpoint now writes the file bytes to a v1 `document_versions` row (NEVER to `partner_documents.file_data`) and looks up `document_type_rules` for the `auto_approve` shortcut. Download / preview endpoints resolve via `document_versions where is_current=true` and fall back to `partner_documents.file_data` for legacy rows. New endpoints: POST/GET `/partners/{id}/documents/{doc_id}/versions`, GET `/partners/{id}/documents/{doc_id}/versions/{vid}/download`, POST `/partners/{id}/documents/{doc_id}/versions/{vid}/revert` (internal only), GET `/partners/{id}/documents/{doc_id}/preview` (inline disposition for PDF/image, attachment otherwise). New separate router `rules_router` registered at `/admin/document-type-rules` (GET/POST/PATCH/DELETE; 409 on delete-in-use). Upload accepts any document_type that matches an admin rule, in addition to the legacy DocumentType enum + DocumentTypeConfig table. `uploaded_by_name` joined into list responses. Partner-admin delete (Sprint 22 / FPRM-370) is now a soft-delete with a `document_references` 409 reference check. |
| Backend router | `backend/routers/quotes_router.py` | Acceptance gate now consults `DocumentTypeRule.requires_approval` for the `quote_acceptance` type. The seed row has `requires_approval=false`, so the FPRM-353 hotfix behaviour is preserved by default; admins flipping the rule to true reinstates the `PartnerDocument.status='approved'` check without code changes. |
| Tests | `backend/tests/test_document_repo_v2.py` (new) | 25 cases covering upload-writes-to-versions, auto_approve flow, new-version increment, is_current flip, status reset after re-upload, version list excludes file_data, per-version download bytes, revert with internal-only gate, rules CRUD + 409-in-use + auto_approve forces requires_approval=false, acceptance gate respecting both rule modes, preview inline/attachment branching, partner-admin delete with reference check, uploaded_by_name fallback, migration importability. |
| Tests | `backend/tests/test_partner_documents_api.py` | Sprint-21 test updated to AD-34 -- file_data now expected on `DocumentVersion` not on `PartnerDocument`. |
| Frontend | `frontend/src/pages/PartnerDocuments.jsx` | Version badge column (clickable when count > 1); inline version history panel; new `NewVersionModal` triggered by per-row "+ Version" button; Preview button for previewable MIME types; Delete button for partner_admin (handles 409); Uploaded By column. Internal mode adds a Revert button on non-current versions. |
| Frontend | `frontend/src/pages/QuoteDetail.jsx` | Pick Existing tab shows version badge (e.g. `v3 of 5`) next to each document. Upload New tab fetches `/admin/document-type-rules` on mount and renders a gate-info hint ("auto-approved on upload" / "requires approval" / "no rule configured") below the document type select. |
| Frontend | `frontend/src/pages/ProgramConfig.jsx` | New "Document Rules" tab (system_admin only, hidden via `adminOnly` filter). Summary cards (Total / Auto-Approve / Requires Approval), CRUD table with Add / Edit / Delete modal. Auto-approve toggle forces requires_approval=false in the UI to match server behaviour. 409 on delete shows inline alert. |
| Docs | `CLAUDE.md`, `CLAUDE_HISTORY.md`, `PROJECT_CONTEXT.md`, `RUNBOOK.md` | Sprint 22 entries, AD-34 added, Jira config table extended with Sprint 21 + 22 IDs, obsolete "Jira API token 401" note removed. |

### New API endpoints (9)

- `POST /partners/{id}/documents/{doc_id}/versions`
- `GET /partners/{id}/documents/{doc_id}/versions`
- `GET /partners/{id}/documents/{doc_id}/versions/{version_id}/download`
- `POST /partners/{id}/documents/{doc_id}/versions/{version_id}/revert`
- `GET /partners/{id}/documents/{doc_id}/preview`
- `GET /admin/document-type-rules`
- `POST /admin/document-type-rules`
- `PATCH /admin/document-type-rules/{rule_id}`
- `DELETE /admin/document-type-rules/{rule_id}`

### Lessons

1. **Append-then-update beats truncate-then-rewrite for big router files.**
   The Sprint 21 + 22 churn on `documents_router.py` taught me the routine:
   add new endpoints at the bottom; touch existing ones only for the
   specific behaviour change; never reflow whole sections "for clarity".
   The diff stays reviewable and the regression surface stays small.
2. **`auto_approve` is the right shortcut; `requires_approval` is the right
   gate.** Two independent booleans on the rule table accommodate the
   common shapes (auto-approve-then-skip-gate, manual-approve-then-honour-
   gate) without inventing more workflow primitives. The UI enforces
   `auto_approve => !requires_approval` for sanity; the API silently does
   the same coercion if a direct caller submits both true.
3. **`fp-page` removal carried into Sprint 22.** Sprint 21 hotfix removed
   the class on PartnerDocuments.jsx; the version UI rebuild stayed in the
   same plain-div layout. No new layout footguns introduced.
4. **The acceptance gate now has a single point of truth.** Before
   Sprint 22 the gate was a hardcoded `requires_approval=False` baked
   into the code. Now `document_type_rules.requires_approval` drives it.
   Admins can flip the policy via the new ProgramConfig tab without code
   changes, and the next sprint that touches the gate doesn't have to
   re-litigate the FPRM-353 design.

---

## Sprint 22 Hotfix -- Document Repository v2 Bug Fixes (Phase 6)

**Tests:** 765 -> **766** (+1 net; new `requires_approval` upload case added,
delete/no-rule cases reworked in place).

Single PR `fix: Sprint 22 hotfix — document delete, auto-approve, rule delete guard`.
Three bugs filed under epic FPRM-299 (no fix version / no native sprint, same
hotfix pattern as the Sprint 21 hotfix).

### Bugs fixed

| Ticket | Bug | Fix |
|---|---|---|
| FPRM-383 | Partner-admin self-service delete set `status='rejected'` instead of deleting | Unreferenced documents are now permanently removed (`db.delete(doc)`); the `document_versions` rows cascade away via FK `ondelete=CASCADE` + ORM `cascade="all, delete-orphan"`. The 409 path (document still referenced) is unchanged. |
| FPRM-384 | Auto-approve default wrong at upload time | Upload status now derives from `document_type_rules`: `auto_approve=true` → `approved`; `requires_approval=true` → `pending_review`; **no matching rule → `approved`** (default is auto-approve). Previously a missing rule defaulted to `pending_review`. |
| FPRM-385 | Document-type-rule delete blocked by in-use 409 guard | The in-use guard on `DELETE /admin/document-type-rules/{id}` was removed — rules are freely deletable at any time. Existing documents of that type keep whatever status they received at upload (no cascade status change). |

### Files changed

| Area | File | Change |
|---|---|---|
| Backend router | `backend/routers/documents_router.py` | Partner-admin delete path hard-deletes unreferenced docs; upload `initial_status` derivation rewritten (no-rule → approved); rule-delete in-use 409 guard removed. |
| Tests | `backend/tests/test_document_repo_v2.py` | `no_rule_defaults_to_pending` → `..._to_approved`; new `test_upload_requires_approval_rule_sets_status_pending`; `delete_in_use_returns_409` → `..._succeeds` (204, doc survives); `delete_unreferenced_succeeds` now asserts permanent delete + version cascade. |
| Tests | `backend/tests/test_documents.py` | `test_upload_document_as_partner_admin` now asserts `status=approved` (no rule for `nda`). |
| Tests | `backend/tests/test_partner_documents_api.py` | `test_list_documents_filters_by_status` reworked — second `nda` upload is explicitly flipped to `rejected` since uploads now auto-approve by default. |

### Behaviour-change note

The no-rule upload default flip (FPRM-384) means **partner documents now auto-approve
on upload unless a `document_type_rules` row with `requires_approval=true` governs the
type.** This intentionally changes activation timing for orgs with no governing rules
(documents count toward activation immediately). The `contract` seed row keeps
contracts gated; teams wanting a manual-review gate for other types must add a rule.

### Lessons

1. **A "safe default" is a product decision, not a code default.** Sprint 22 shipped
   `pending_review` as the missing-rule default reasoning it was the conservative
   choice; the business actually wanted auto-approve so routine attachments don't pile
   up in a review queue nobody watches. The rule table now encodes the exceptions.
2. **Soft-delete needs a reason to exist.** The self-service delete was soft (status
   flip) for an audit trail that `document_versions` already preserves for *referenced*
   docs — and unreferenced docs have nothing worth keeping. Permanent delete is simpler
   and matches the partner's mental model of "delete".

---

## Sprint 22 Hotfix #2 — Case-insensitive document_type_rules matching (Phase 6)

**Date:** 2026-05-29 · **PR:** #183 · **Migration head:** 038 (unchanged) ·
**Tests:** 766 → **769** (+3 regression cases).

Single bug **FPRM-386** under epic FPRM-299 (hotfix pattern — no fix version / no
native sprint).

### Bug fixed

| Ticket | Symptom | Root cause | Fix |
|---|---|---|---|
| FPRM-386 | `requires_approval=true` documents (e.g. NDA) were auto-approved on upload instead of landing `pending_review`. | The Program Config → Document Rules form is a free-text input, so an admin stored a rule as `document_type="NDA"`. Uploads send the canonical lowercase code `nda`, and the rule lookup was an exact, case-sensitive `==`, so it found no rule and fell through to the auto-approve default (FPRM-384). | Rule lookup in the upload endpoint is now case-insensitive + whitespace-trimmed (`LOWER(TRIM(...))`) on both the type-validation and status-derivation paths, via a shared `_find_rule_for_type` helper. The rule-create duplicate check is also case-insensitive so `NDA`/`nda` can't coexist. The PR #182 conditional and the no-rule→approved default are unchanged. The acceptance gate is unaffected (it compares against the hardcoded `quote_acceptance` constant). |

### Files changed

| Area | File | Change |
|---|---|---|
| Backend router | `backend/routers/documents_router.py` | New `_find_rule_for_type` helper (case-insensitive + trimmed); used at the upload type-validation lookup, the status-derivation lookup, and the rule-create duplicate check. `from sqlalchemy import func` added. |
| Tests | `backend/tests/test_document_repo_v2.py` | +3: `test_upload_matches_rule_case_insensitively` (rule `NDA` ↔ upload `nda` → `pending_review`), `test_upload_matches_rule_ignoring_whitespace`, `test_rule_create_duplicate_is_case_insensitive` (409). |

### Investigation note

The originally-suspected "broken conditional" did **not** reproduce — the PR #182
status conditional was already correct and its `requires_approval` test was green. An
empirical repro (`rule=NDA, upload=nda → approved`) isolated the real cause as the
exact-match lookup, confirmed by the free-text Document Rules form. The fix targets
matching, not the conditional.

### Lessons

1. **"Tests green" ≠ "behaviour correct" when the test data is too tidy.** The Sprint 22
   `requires_approval` test used a same-cased type (`contract`/`contract`), so it never
   exercised the casing path that broke in production. The regression test now seeds the
   rule with a *different* casing than the upload — mirroring the real free-text entry.
2. **Free-text identifiers need normalisation at the matching layer, not just the UI.**
   Fixing the dropdown alone would leave existing mis-cased rows broken; normalising the
   lookup repairs production data immediately and is resilient to any future UI.

---

*Docs PR (2026-05-29): established a dedicated "Phase 7 Backlog" section in CLAUDE.md as the single authoritative home for deferred work; re-added Dynamic RBAC (Phase 5 deferral that had dropped off the written list) as the anchor item. No code change. PR #184.*

---

## Sprint 23 PR A — Sprint 22 Carry-Forward (Phase 6)

**Date:** 2026-05-29 · **PR:** #185 · **Migration head:** 038 → **039** ·
**Tests:** 769 → **786** (+17). Fix version "Sprint 23" (10934), native sprint 907.
PR B (Asset Library, migration 040) is a separate prompt run after this merges.

Six stories (FPRM-387…392), 12 subtasks (FPRM-397…408). All under epic FPRM-299.
Closes the 8 Sprint 22 UI-testing carry-forward items.

### Stories / subtasks

| Story | Items | Summary |
|---|---|---|
| S1 FPRM-387 (S1.1/S1.2) | #5,#7 | Migration 039 dual-table seed + reconcile; universal approval gate verified on every upload path (partner-documents, version, quote-attach) via the shared `_find_rule_for_type` helper. |
| S2 FPRM-388 (S2.1/S2.2) | #8,#3 | ProgramConfig → Document Rules: free-text type field becomes a `<select>` sourced from `GET /config/document-types` (+ "Add new type…" creating a `document_types` vocabulary row); label renamed "Requires Approval". |
| S3 FPRM-389 (S3.1/S3.2) | #6 | Partner self-accept (AD-35): `quote:accept_own` permission added to partner roles; quote status handler allows partner own-org `sent → accepted` only; portal QuoteDetail exposes attach proof + Mark as Accepted for partners. |
| S4 FPRM-390 (S4.1/S4.2) | #4,#1 | Version revert widened to `partner_admin` own-org (AD-36, supersedes FPRM-374); audit action renamed `document.reverted` → `document.version_reverted`; version list now returns `uploaded_by_name`; version panel shows Uploaded By + a confirm dialog before revert. |
| S5 FPRM-391 (S5.1/S5.2) | #2 | Upload size cap raised 10 MB → **25 MB** (AD-37); no server-side type allowlist existed (only the FE `accept` filter, now removed); quote-attach FE guard aligned to 25 MB. |
| S6 FPRM-392 (S6.1/S6.2) | — | These four canonical-doc updates. |

### Migration 039 (data only, no schema change)

Seeds `proof_of_fiscal_domicile`, `w9`, `insurance_certificate`, `nda`,
`security_assessment` into `document_type_rules` (requires_approval=true,
auto_approve=false) AND the same set + `contract`/`quote_acceptance` into the
`document_types` vocabulary. Reconciles every DISTINCT in-use
`partner_documents.document_type` into both tables. Idempotent (`WHERE NOT
EXISTS`); `downgrade()` removes only the five rule rows it introduced.

### Endpoint note

No NEW endpoint shipped. `GET /config/document-types` already existed as the
DocumentTypeConfig *vocabulary* endpoint and was deliberately **not** repurposed
to return rules (it has tested consumers + drives upload validation). Both the
upload form and the admin Document Rules dropdown are wired to it. This is the
two-table model recorded as **AD-38**. (The Jira ticket text predates this
decision and describes a "new" endpoint returning rules; the implementation
follows the owner's two-table direction.)

### ADs recorded

AD-35 (partner self-accept), AD-36 (partner_admin revert — **supersedes
FPRM-374**), AD-37 (size cap replaces type allowlist), AD-38 (two-table document
model).

### Lessons

1. **Check for path collisions before adding a "new" endpoint.** The prompt's
   `GET /config/document-types` already existed with a different (tested) shape.
   Surfacing it to the owner produced the cleaner two-table model instead of a
   breaking repurpose.
2. **Widening a permission means inverting its old test.** The Sprint 22
   `test_revert_as_partner_admin_returns_403` asserted the exact behaviour AD-36
   reverses — it had to flip to a 200 success assertion, not just get a new
   sibling test.
3. **Frontend `accept=` filters are not a security control.** The "type
   allowlist" lived only in the browser; the backend already accepted any MIME.
   AD-37 made the real gate (size) explicit on both sides.

---

## Sprint 23 PR B — Asset Library (Phase 6)

**Date:** 2026-05-29 · **PR:** #186 · **Migration head:** 039 → **040** ·
**Tests:** 786 → **799** (+13). **Sprint 23 fully closed (PR A #185 + PR B #186).**

Four stories (FPRM-393…396), 9 subtasks (FPRM-409…417). FR-PORT-020 → FR-PORT-023.

### Stories / subtasks

| Story | Summary |
|---|---|
| S7 FPRM-393 (S7.1/S7.2) | Models (`AssetCategory`, `Asset`, `AssetDownloadLog`) + migration 040 (3 tables, FK-safe downgrade) + `assets_router.py`: partner `GET /assets` + `GET /assets/{id}/download`; internal `GET/POST/PATCH/DELETE /internal/assets` + `/internal/assets/{id}/download-logs`; `GET/POST/PATCH/DELETE /internal/asset-categories`. 13 tests. |
| S8 FPRM-394 (S8.1/S8.2) | `PortalAssets.jsx` at `/portal/assets`; portal nav placeholder "Assets" enabled + renamed **Resources**; card grid + category filter + search + pagination (20/page) + fetch+Blob download (AD-20). |
| S9 FPRM-395 (S9.1/S9.2) | `InternalAssets.jsx` at `/internal/assets`; **Assets** nav added to InternalLayout between Quotes and Users; upload modal (file→base64, 10 MB guard) + list filters + per-row edit/activate + download-count → log drill-down modal + category management (add/rename/reorder/deactivate). |
| S10 FPRM-396 (S10.1/S10.2/S10.3) | These four canonical-doc updates + AD-39. |

### New endpoints
`GET /assets`, `GET /assets/{id}/download`, `GET /internal/assets`, `POST /internal/assets`, `PATCH /internal/assets/{id}`, `DELETE /internal/assets/{id}`, `GET /internal/assets/{id}/download-logs`, `GET/POST /internal/asset-categories`, `PATCH/DELETE /internal/asset-categories/{id}`.

### Migration 040
Creates `asset_categories`, `assets` (base64 `file_data`), `asset_download_logs`. Existence-checked creates; `downgrade()` drops in FK-safe order (logs → assets → categories).

### AD recorded
AD-39 — asset base64 storage; 10 MB cap (independent of the 25 MB partner-documents cap); `file_data` never in list responses; soft-delete; visibility `all`/`tier:`/`category:`.

### Lessons
1. **Enable the placeholder, don't duplicate it.** PartnerPortalLayout already had a disabled "Assets" nav item at `/portal/assets`; the right move was to enable + rename it to "Resources", not add a second nav row.
2. **Partners have no category-list endpoint.** Categories are internal-only, so the portal filter derives its options from the assets it can see (a broad page-size fetch) rather than calling a partner categories API that doesn't exist.

---

> *Docs PR (2026-05-30): added a "Phase 6 Backlog / Sprint Candidates" section to CLAUDE.md (sibling to Phase 7 Backlog) capturing three product gaps from Sprint 23 UI testing — partner deal messaging, asset reactivate, PortalAssets redesign. No code change. PR #187.*

---

## Sprint 24 PR A — Sprint 23 carry-forward bugs (Phase 6)

**Date:** 2026-05-30 · **PR:** #188 · **Migration head:** **040 (unchanged — no migration)** ·
**Tests:** 799 → **802** (+3). First of a two-PR Sprint 24 (PR B = Channel Manager
Assignment + approval routing, migration 041, runs only after PR A merges).

Four stories (FPRM-418…421). Subtasks omit fixVersions / customfield_10020 per AD-10.

### Stories / subtasks

| Story | Summary |
|---|---|
| S1 FPRM-418 (S1.1/S1.2) | **Unify document-type dropdown + vocabulary admin (AD-40).** New shared `frontend/src/components/DocumentTypeSelect.jsx` sourced only from `GET /config/document-types`; swapped into every surface — PartnerDocuments upload modal **and** the list type-filter, QuoteDetail quote-attach (replaced a hardcoded 4-item list — the divergence bug), and the Program Config Document Rules picker. New Program Config **Document Types** tab (`DocumentTypesTab`) is the vocabulary admin: view all (incl. archived) + add + archive/reactivate, reusing the existing `POST /config/document-types` + `PATCH /config/document-types/{id}` (**no new endpoint** — the config-admin POST already existed). The Document Rules tab's inline "Add new type" was removed (vocabulary now lives in the Document Types tab). |
| S2 FPRM-419 (S2.1) | **Download-log names not UUIDs.** `GET /internal/assets/{id}/download-logs` now batch-resolves `user_name` (`users.full_name`) + `partner_org_name` (`partner_organizations.legal_name`); raw ids retained for a null-name fallback. `InternalAssets.jsx` LogsModal renders names with id fallback. |
| S3 FPRM-420 (S3.1) | **Cross-tenant preview leak on logout (security).** New `frontend/src/utils/session.js` `clearSession()` revokes tracked preview blob object-URLs + clears tenant web storage; both layouts' `logout()` call it; PartnerDocuments preview registers its URL via `trackPreviewUrl`. Closes the leak where a prior org's preview stayed openable after logout→login until a hard refresh (backend already 403s the cross-org re-fetch). |
| S4 FPRM-421 (S4.1/S4.2) | These four canonical-doc updates + AD-40. |

### Backend changes
`backend/routers/assets_router.py` — `asset_download_logs` joins User + PartnerOrganization for names (batched, no N+1). No schema/migration change. No change to `config_router.py` (the vocabulary POST/PATCH already existed) and **`test_document_types_config.py` is unchanged** per the prompt constraint.

### Tests (+3)
`tests/test_assets.py::test_download_logs_resolve_user_and_org_names`; new file
`tests/test_document_type_vocab_unification.py` (2 tests — single-source vocabulary incl. `nda`; an admin-added type appears in the shared list). Frontend has no blocking JS test runner, so the divergence fix is verified by `npm run build` + the API-level unification tests.

### AD recorded
AD-40 — one shared document-type vocabulary (`GET /config/document-types`) via a single `DocumentTypeSelect` on every upload surface; never filtered/overridden per surface; vocabulary admin = Program Config Document Types tab over the existing POST/PATCH.

### Lessons
1. **The fix already had half its plumbing.** The config-admin `POST /config/document-types` and `PATCH` existed; S1 only needed the shared component + a tab, not a new endpoint. Reading `config_router.py` first avoided adding a duplicate.
2. **A security leak can live entirely in the client cache.** The backend already 403'd cross-org fetches; the leak was a `blob:` URL surviving a 30s timer across a session switch. Tracking preview URLs and revoking on logout is the seam.
3. **Process:** built the PR body from a file (not inline backticks); drove the git/PR flow through one self-guarding script and read the log back to verify (carried from PR #187).

