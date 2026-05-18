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

