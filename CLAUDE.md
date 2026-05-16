# Fracttal PRM — Project Context

> This file is the single source of truth for Claude Code and Claude chat sessions.
> Load it at the start of every session to restore full project context.

> Sprint history lives in CLAUDE_HISTORY.md (created at first sprint closeout)

---

## What This Project Is

A new Partner Relationship Management (PRM) system to onboard and manage Fracttal system resellers and implementation partners. Built and maintained by an AI-powered Virtual Development Team using Claude Code as the Dev Agent, a rule-based auto-merger as the Manager Agent, and direct Jira REST API calls for sprint setup.

**Owner:** Johan Wessels — SynPro Consulting
**Started:** May 2026
**Current state:** Sprint 2 closed (Authentication delivered). Backend and frontend live on Railway. Sprint history in CLAUDE_HISTORY.md.

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
| Sprint IDs (native) | Sprint 1: `501`, Sprint 2: `534` |
| Sprint fix version IDs | Sprint 1: `10528`, Sprint 2: `10561` |

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
| `fastapi` | 0.104.1 | Web framework |
| `uvicorn` | 0.24.0 | ASGI server |
| `sqlalchemy` | 2.0.36 | ORM (bumped in FPRM-38 for Python 3.13 compat) |
| `pydantic` | 2.11.4 | Data validation (bumped in FPRM-37 after FPRM-19's 2.7.4 still missed a Python 3.13 wheel on Railpack) |
| `psycopg2-binary` | 2.9.10 | PostgreSQL driver (bumped in FPRM-39; 2.9.10+ bundles libpq, removes Railpack libpq.so.5 dependency) |
| `pyjwt` | 2.8.0 | JWT handling |
| `python-dotenv` | 1.0.0 | Env loading |
| `alembic` | 1.14.0 | DB migrations (matched to sqlalchemy 2.0.36 in FPRM-38) |
| `slowapi` | 0.1.9 | Rate limiting |
| `httpx` | 0.27.0 | Async HTTP client |
| `pytest` | 7.4.3 | Test suite |
| `passlib[bcrypt]` | 1.7.4 | Password hashing (Sprint 2 / FPRM-23) |
| `bcrypt` | 4.0.1 | passlib backend |
| `email-validator` | 2.1.0 | pydantic `EmailStr` support (Sprint 2 / FPRM-23) |

---

## Known Issues / Technical Debt

Active items only — historical Sprint follow-ups live in `CLAUDE_HISTORY.md`.

- **Alembic migrations not yet applied to live Railway DB.** Sprint 2 added `001_create_users_table` and `002_create_password_reset_tokens` but they haven't been run against the live PostgreSQL. Auth endpoints will 500 in production until either the start command is updated to `alembic upgrade head && uvicorn …` or the migration is run once manually via Railway shell. CI tests use sqlite + `Base.metadata.create_all` so they bypass this.
- **JWT logout blacklist is in-memory only.** Lost on backend restart; not safe for multi-instance deploys. Likely Sprint 3+ work.
- **Password reset has no email backend yet.** Reset URLs are logged to stdout via `print`. A real email integration (SES / SendGrid / etc) is queued for a later sprint.
- **SonarCloud scan fails on every CI run** (non-blocking — `continue-on-error: true`). Needs a `sonar-project.properties` file and a linked SonarCloud project to produce useful output.

---

## Tools Available

- **Claude Code** — Dev Agent for all implementation
- **Atlassian Rovo MCP** — available for direct Jira management from Claude chat
