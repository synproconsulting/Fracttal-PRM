# Fracttal PRM — Project Context

> This file is the single source of truth for Claude Code and Claude chat sessions.
> Load it at the start of every session to restore full project context.

> Sprint history lives in CLAUDE_HISTORY.md (created at first sprint closeout)

---

## What This Project Is

A new Partner Relationship Management (PRM) system to onboard and manage Fracttal system resellers and implementation partners. Built and maintained by an AI-powered Virtual Development Team using Claude Code as the Dev Agent, a rule-based auto-merger as the Manager Agent, and direct Jira REST API calls for sprint setup.

**Owner:** Johan Wessels — SynPro Consulting
**Started:** May 2026
**Current state:** Sprint 9 closed — Phase 3 (Deal Registration) underway; Sprint 10 (conflict checking + commission visibility) remains. Backend adds `DealMessage` model + migration 016, collaboration thread endpoints (`GET/POST /deal-registrations/{id}/messages`, `POST /internal/deals/{id}/request-info`) and the existing submit accepts `info_required → submitted` (FPRM-139). `partner_legal_name` surfaces in deal list + detail responses (FPRM-143). Document type vocabulary is admin-configurable via new `document_types` table + migration 017 (FPRM-144); `partner_documents.document_type` converted from PG enum to VARCHAR. `baseline_training_complete` now has admin endpoints (`POST /partners/{id}/activation/training-complete|training-reset`) and is part of the activation_complete gate (migration 018 backfills already-active partners) (FPRM-145). Frontend gains `DealDetail` at `/portal/deals/:id` and `InternalDealDetail` at `/internal/deals/:id` with collab thread, status banners, and action panel. Sprint 9 fix version 10632 + native sprint 605 closed. Sprint history in CLAUDE_HISTORY.md.

---

## Live Deployments

| Service | URL |
|---|---|
| Control Centre (frontend) | https://control-centre-service-production.up.railway.app |
| Fracttal PRM Backend (FastAPI) | https://fracttal-prm-backend-production.up.railway.app |
| Fracttal PRM Frontend (React) | https://fracttal-prm-frontend-production.up.railway.app |

> The Control Centre is shared across all products. It manages Fracttal PRM via the SynPro VSDC backend's product credentials system — no separate Control Centre deployment needed.

---

## Hard Rules

> These rules are non-negotiable and apply to every session and every change — no exceptions.

**Never commit directly to `main`.** All changes — including single-line fixes, cleanups, corrections, and documentation updates — must go through:
1. A `feature/` or `fix/` branch
2. A pull request
3. CI pipeline
4. Auto-merger review and merge

Committing directly to `main` bypasses the audit trail and CI gates. If a direct-to-main commit is ever made by mistake, a retroactive PR must be opened immediately.

**SonarCloud and Railway deploy are not merge-gate checks — by design.** Both run with `continue-on-error: true` in `ci.yml` and are intentionally excluded from the auto-merger's blocking check list. Only unit tests (Python 3.11 + 3.12) and the bandit security scan are blocking.

**`backend/requirements.txt` is a critical file.** Before writing it, always read the existing content first. Never remove any existing dependency — only append new ones. Removing a package breaks the deployed Railway service for every feature that depends on it.

**`GITHUB_TOKEN` cannot trigger `workflow_dispatch` events — use `PAT_TOKEN`.** GitHub blocks the built-in `GITHUB_TOKEN` from dispatching workflows. Any workflow dispatch API call must use `PAT_TOKEN`.

**`FRONTEND_URL` in Railway must be `*` or explicitly include the Control Centre origin.** The backend CORS middleware reads `FRONTEND_URL` from the environment. Set `FRONTEND_URL=*` in Railway backend service variables to avoid blocking the Control Centre.

**Backend routers must never import from outside the `backend/` directory.** The `backend/` service is a self-contained Railway deployment. Any cross-directory import crashes the service at startup. Every router must be fully self-contained — inline the logic or use direct HTTP calls.

**Always read `auth.py` before creating any new router in `backend/`.** The exact name of the auth dependency function must be verified before use. Assuming the name without reading the file produces routers that crash at startup.

**Security hardening tickets must list required Railway environment variable changes in the acceptance criteria.** Hardening changes are ineffective until the new variables are set in the Railway service dashboard. Acceptance criteria for any security ticket that touches environment config must include: variable name, required value format, and which Railway service to update.

**Never run two Claude Code instances simultaneously on this project.** Concurrent instances produce race conditions, duplicate PRs, and split-brain Jira state.

**Claude Code is the Dev Agent — do not invoke any agent scripts directly.** Claude Code implements all tickets directly via the GitHub Contents API. No agent scripts are invoked programmatically.

**The rule-based auto-merger is the Manager Agent.** PRs are merged automatically by the rule-based auto-merger in `ci.yml` when all blocking CI checks pass. Do not invoke any manager agent scripts directly.

**Sprint setup is performed directly via Jira API calls from Claude Code.** All sprint setup (fix version creation, native sprint creation, ticket assignment, execution order, story points, priority) is done via direct Jira REST API calls. No PM Agent scripts are invoked.

**When Claude Code flags a discrepancy at the end of its output, resolve it in the current action — never defer to a follow-up.** Any inconsistency in CLAUDE.md or CLAUDE_HISTORY.md must be corrected in the same PR, not a follow-up.

**Jira ticket lifecycle: transition to In Progress before starting implementation.** Leave In Progress when PR is opened. Transition to Done only when the PR is merged to `main` and confirmed by the auto-merger. Never transition to Done on PR open.

**Before opening any fix PR that corrects a bug discovered during the current sprint, create a Jira bug ticket first.** Assign it to the current sprint (fix version + native sprint). Reference the ticket key in the PR title using conventional commit format: `fix(FPRM-XX): description`. Transition to In Progress before starting, leave In Progress when PR opens, Done on merge. No fix PR may be opened without a corresponding Jira ticket.

**One PR at a time — no exceptions.** Before opening any PR (feature, fix, or docs), verify that zero PRs are currently open in the repository via the GitHub API. If any PR is open, wait for it to merge before opening a new one. This applies to all PR types without exception.


**Every Claude Code session must start with a clean working tree pulled from main.** Before running `claude --dangerously-skip-permissions`, execute this sequence in order — no exceptions:

```cmd
cd "C:\Johan\SynPro Consulting\Fracttal PRM"
git fetch origin
git status
git checkout main
git reset --hard origin/main
git clean -fd --exclude=Documentation/
```

This discards any untracked files or locally-modified tracked files left by a prior Claude Code session and aligns the working tree exactly with `origin/main`, while preserving the local-only `Documentation/` folder (RUNBOOK.md, sprint prompts, contracts, requirements docs). Everything else canonical is on GitHub — `git clean -fd --exclude=Documentation/` is always safe. If you skip this step and Claude Code operates on a stale or dirty working tree, it will read outdated CLAUDE.md, PROJECT_CONTEXT.md, and CLAUDE_HISTORY.md files and produce incorrect results.

**`git pull origin main` alone is not sufficient.** A `git pull` does not remove untracked files written by prior Claude Code sessions. Use `git reset --hard origin/main && git clean -fd --exclude=Documentation/` to guarantee a clean state without losing the local `Documentation/` reference folder.

**Never run `git clean -fd` without `--exclude=Documentation/`.** The repo-root `Documentation/` folder is untracked but canonical — it holds RUNBOOK.md (read by every sprint prompt), every sprint's ClaudeCode prompt, partner contracts, and requirements docs. A bare `git clean -fd` deletes all of it including the prompt currently being executed.

---

## Key Architectural Decisions

These are conscious design choices that must not be accidentally reversed. Full Decision / Why / Consequence / Do not text lives in PROJECT_CONTEXT.md Section 6.

### AD-1 · Backend uses flat module layout — no packages, no `src/` subdirectory
All Python source files sit directly in `backend/` with no `src/` subdirectory and no `__init__.py`. Imports are flat (`from models import ...`).

### AD-2 · No git CLI — all GitHub operations use the REST API
Branches, commits, and PRs are created entirely via the GitHub Contents API and Git Trees API over HTTP — no `git` binary required.

### AD-3 · Feature branches are always recreated from `main`, never updated in place
Before creating a branch, delete any existing branch with the same name and recreate fresh from the latest `main` SHA, guaranteeing clean diffs.

### AD-4 · Jira sprints are tracked via fix versions, not native Agile sprints
Sprints are assigned via Jira's `fixVersions` field; JQL must dual-query `fixVersion = {fix_id} OR sprint = {native_id}` to catch all tickets.

### AD-5 · `backend/` is a self-contained service — no cross-directory imports at runtime
Every file in `backend/` must import only from stdlib, pip-installed packages in `backend/requirements.txt`, and other files within `backend/` itself.

### AD-6 · Jira API calls proxied through the shared SynPro VSDC backend
The Control Centre never calls Jira directly — all Jira requests go through `/proxy/jira/*` on the shared UAT backend with `product_id` identifying Fracttal PRM.

### AD-7 · SonarCloud and Railway deploy are not merge-gate checks
Both run with `continue-on-error: true` — only unit tests and bandit scan are blocking merge.

### AD-8 · `models.py` uses portable types; migrations use PostgreSQL-native types
SQLAlchemy `Uuid` and `JSON` in models keep sqlite test runs working; Alembic migrations use `postgresql.UUID`/`postgresql.JSONB` directly.

### AD-9 · Public + tenant-scoped + permission-required + internal-only permission tiers
Every endpoint falls into one of four tiers; tenant scoping always lives in the handler, never inside `require_permission`.

### AD-10 · Sub-tasks inherit fix-version and sprint from their parent — never set on the Sub-task issue itself
Setting them on the subtask returns HTTP 400. JQL dual-query still surfaces subtasks via parent membership.

### AD-11 · Draft token pattern for unauthenticated public access
Per-application `draft_token` query param authorises public partner-application endpoints; `audit_log.actor_id` nullable so anonymous events log cleanly.

### AD-12 · Partner provisioning is a single function in a dedicated module
`backend/provisioning.py` `provision_partner_from_application` creates org + profile + invite (+ activation checklist since Sprint 7); idempotent on `application.partner_org_id`. Imported lazily by the router.

### AD-13 · Email notifications never raise
`backend/notifications.py` `send_email` wraps `smtplib` with dev-mode stdout fallback; every call site wraps in `try/except` belt-and-braces.

### AD-14 · Activation checklist recalc is the single source of truth
`backend/activation.py` `recalculate_activation(db, partner_org_id)` is called after profile update, document approval, and contract-date change. Provisioning creates the all-False row; the function auto-creates one on first read for orgs that pre-date Sprint 7. `baseline_training_complete` hardcoded False until Sprint 10.

### AD-15 · Role-based route guards in React via `ProtectedRoute`
`ProtectedRoute` checks the JWT role against an allowed list; partner-only routes live under `/portal/*` inside `PartnerPortalLayout`, internal-only routes under `/internal/*`. Token stored in `localStorage` under `'token'`. JWT carries `partner_org_id` (FPRM-119) so the layout can resolve the user's org without a round-trip.

---

## Repository

- **GitHub org:** `synproconsulting`
- **Repo:** `Fracttal-PRM`
- **Default branch:** `main`
- **Branch naming:** `feature/fprm-{ticket}-{slug}` or `fix/fprm-{ticket}-{slug}`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Frontend | React + Vite |
| Database | PostgreSQL (Railway managed) |
| Hosting | Railway — project ID `e5c41b7a-b96c-449d-964f-aba615d4cae0` |
| Task tracking | Jira Cloud — `synproconsulting.atlassian.net`, project key `FPRM` |
| Source control | GitHub — `synproconsulting/Fracttal-PRM` |
| CI/CD | GitHub Actions |
| Control Centre | Shared — `https://control-centre-service-production.up.railway.app` |

---

## Project Structure (target — greenfield)

```
Fracttal-PRM/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── auth.py              # JWT authentication
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # DB connection
│   ├── requirements.txt     # Python dependencies
│   └── tests/               # pytest test suite
├── frontend/
│   └── src/                 # React frontend
├── .github/
│   └── workflows/
│       └── ci.yml           # CI pipeline
└── README.md
```

> **`backend/` layout:** Flat — all Python source files sit directly in `backend/` with no `src/` subdirectory and no `__init__.py` package files. Tests go in `backend/tests/`. Imports inside `backend/` are flat (e.g. `from models import ...`).

---

## Jira Configuration

| Setting | Value |
|---|---|
| Site | `synproconsulting.atlassian.net` |
| Project key | `FPRM` |
| Jira board ID | `67` |
| Execution order field | `customfield_10071` |
| Story points field | `customfield_10016` |
| Sprint IDs (native) | Sprint 1: `501`, Sprint 2: `534`, Sprint 3: `535`, Sprint 4: `536`, Sprint 5: `537`, Sprint 6: `538`, Sprint 7: `539`, Sprint 8: `572`, Sprint 9: `605` |
| Sprint fix version IDs | Sprint 1: `10528`, Sprint 2: `10561`, Sprint 3: `10562`, Sprint 4: `10563`, Sprint 5: `10564`, Sprint 6: `10565`, Sprint 7: `10566`, Sprint 8: `10599`, Sprint 9: `10632` |

**Sprint query pattern:**
```python
jql = f"project = FPRM AND (fixVersion = {fix_id} OR sprint = {native_id})"
```

---

## Railway Configuration

| Setting | Value |
|---|---|
| Railway Project ID | `e5c41b7a-b96c-449d-964f-aba615d4cae0` |
| Backend service name | `fracttal-prm-backend` |
| Frontend service name | `fracttal-prm-frontend` |

---

## CI/CD Pipeline

Triggered on every push to `feature/*` branches:

| Stage | What it does | Blocking? |
|---|---|---|
| Matrix test | pytest on Python 3.11 + 3.12 | Yes |
| Security scan | bandit on `backend/` | No (--exit-zero) |
| SonarCloud | Full code analysis | No (continue-on-error) |
| Playwright E2E | Browser tests against live backend | No (continue-on-error) |
| Deploy | Railway GraphQL API redeploy (main branch only) | No |

---

## Control Centre Integration

Fracttal PRM is managed via the shared Control Centre. The product record in the SynPro VSDC database contains all Fracttal PRM credentials:

| Field | Value |
|---|---|
| `jira_project_key` | `FPRM` |
| `jira_board_id` | `67` |
| `jira_base_url` | `https://synproconsulting.atlassian.net` |
| `github_org` | `synproconsulting` |
| `github_repo` | `Fracttal-PRM` |
| `railway_project_id` | `e5c41b7a-b96c-449d-964f-aba615d4cae0` |

---

## Environment Variables (.env — local development)

```
JIRA_BASE_URL=https://synproconsulting.atlassian.net
JIRA_EMAIL=synproconsulting@gmail.com
JIRA_API_TOKEN=<rotate at id.atlassian.com>
JIRA_PROJECT_KEY=FPRM
JIRA_BOARD_ID=67
ANTHROPIC_API_KEY=<from console.anthropic.com>
GITHUB_TOKEN=<from github.com/settings/tokens — needs repo + workflow scope>
GITHUB_USERNAME=synproconsulting
GITHUB_REPO=Fracttal-PRM
RAILWAY_TOKEN=<from Railway account settings>
RAILWAY_PROJECT_ID=e5c41b7a-b96c-449d-964f-aba615d4cae0
```

**GitHub Secrets (for Actions):** `PAT_TOKEN`, `RAILWAY_TOKEN`, `RAILWAY_PROJECT_ID`, `SONAR_TOKEN`

---

## Local Development

```bash
# Activate venv (Windows)
cd "C:\Johan\SynPro Consulting\Fracttal PRM"
.venv\Scripts\activate

# Test Jira connection
python test_connection.py

# Run backend locally
cd backend
uvicorn main:app --reload

# Run frontend locally
cd frontend
npm run dev
```

---

## Key Conventions

- **Commit format:** `feat(fprm-XX): description` (conventional commits)
- **PR title format:** `feat(FPRM-XX): description` or `fix(FPRM-XX): description`
- **Story points:** Fibonacci — 1, 2, 3, 5, 8, 13 (max 8 per story)
- **Execution order:** `customfield_10071` in Jira — determines implementation sequence
- **ADF:** Acceptance criteria written in Atlassian Document Format in Jira descriptions
- **CORS:** Jira calls always go via the shared FastAPI proxy — never direct from browser

---

## Backend Dependencies (`backend/requirements.txt`)

Current pinned versions on `main`. **Read this file before modifying — never remove packages, only append.** Authoritative source is `backend/requirements.txt` itself; this table is a quick reference.

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.115.12 | Web framework (bumped in FPRM-40 sweep for Python 3.13 compat) |
| `uvicorn` | 0.34.2 | ASGI server (bumped in FPRM-40 sweep) |
| `starlette` | 0.46.2 | ASGI toolkit (pinned in FPRM-40 — fastapi vendors it; explicit pin keeps it in range fastapi 0.115.x requires) |
| `sqlalchemy` | 2.0.36 | ORM (bumped in FPRM-38 for Python 3.13 compat) |
| `pydantic` | 2.11.4 | Data validation (bumped in FPRM-37 after FPRM-19's 2.7.4 still missed a Python 3.13 wheel on Railpack) |
| `psycopg2-binary` | 2.9.10 | PostgreSQL driver (bumped in FPRM-39; 2.9.10+ bundles libpq, removes Railpack libpq.so.5 dependency) |
| `pyjwt` | 2.10.1 | JWT handling (bumped in FPRM-40 sweep) |
| `python-dotenv` | 1.0.0 | Env loading |
| `alembic` | 1.14.0 | DB migrations (matched to sqlalchemy 2.0.36 in FPRM-38) |
| `slowapi` | 0.1.9 | Rate limiting (PyPI latest as of FPRM-40 sweep — no newer release) |
| `httpx` | 0.28.1 | Async HTTP client (bumped in FPRM-40 sweep) |
| `pytest` | 8.3.5 | Test suite (bumped in FPRM-40 sweep) |
| `passlib[bcrypt]` | 1.7.4 | Password hashing (Sprint 2 / FPRM-23) |
| `bcrypt` | 4.0.1 | passlib backend |
| `email-validator` | 2.1.0 | pydantic `EmailStr` support (Sprint 2 / FPRM-23) |

---

## Known Issues / Technical Debt

Active items only — historical Sprint follow-ups live in `CLAUDE_HISTORY.md`.

- **JWT logout blacklist is in-memory only.** Lost on backend restart; not safe for multi-instance deploys.
- **Password reset has no email backend yet.** Reset URLs are logged to stdout via `print`. A real email integration (SES / SendGrid / etc) is queued for a later sprint. Sprint 6 lifecycle notifications use SMTP with stdout fallback (AD-13) — the password-reset path still needs to adopt the same pattern.
- **SonarCloud scan fails on every CI run** (non-blocking — `continue-on-error: true`). Needs a `sonar-project.properties` file and a linked SonarCloud project to produce useful output.
- **`FPRM-89` — `audit_log.actor_id` stores string `"None"` on anonymous events.** Cosmetic; rows are otherwise correct. Parked Low.
- **`FPRM-104` — endpoints using `_user_from_bearer` cannot be tested via `app.dependency_overrides[get_current_user]`.** Affected: `GET /applications/{id}/timeline`, `GET+POST /applications/{id}/messages`. Tests work with real JWTs in the meantime. Parked Low.
- **SMTP env vars not yet set on the `fracttal-prm-backend` Railway service.** Lifecycle email notifications (Sprint 6 / FPRM-93) fall back to stdout in production until `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `CHANNEL_OPS_EMAIL` are set. No code change required — manual ops follow-up.

---

## Tools Available

- **Claude Code** — Dev Agent for all implementation
- **Atlassian Rovo MCP** — available for direct Jira management from Claude chat
