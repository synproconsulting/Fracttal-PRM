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
