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
