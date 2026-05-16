# Railway Setup Checklist — Fracttal PRM

This checklist documents the manual Railway dashboard and GitHub Secrets configuration that must be completed before Sprint 1 deployments will succeed. Tracked by **FPRM-6** (Sprint 1, Story 1).

> **Owner:** Johan Wessels — SynPro Consulting
> **Railway Project ID:** `e5c41b7a-b96c-449d-964f-aba615d4cae0`
> **Status (2026-05-16):** Railway services and GitHub Secrets are NOT yet configured. Sprint 1 implementation will scaffold the code; deployments will not work until this checklist is complete.

---

## 1. Railway Services

All three services live in Railway project `e5c41b7a-b96c-449d-964f-aba615d4cae0`.

### 1.1 Create `fracttal-prm-backend`

| Setting | Value |
|---|---|
| Source | GitHub repo `synproconsulting/Fracttal-PRM` |
| Root directory | `backend/` |
| Build command | (auto — Nixpacks detects Python) |
| Start command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Auto-deploy branch | `main` |

### 1.2 Create `fracttal-prm-frontend`

| Setting | Value |
|---|---|
| Source | GitHub repo `synproconsulting/Fracttal-PRM` |
| Root directory | `frontend/` |
| Build command | `npm run build` |
| Start command | `serve dist` |
| Auto-deploy branch | `main` |

### 1.3 Add PostgreSQL database service

- Add the **PostgreSQL** plugin to the project.
- Link it to `fracttal-prm-backend` so Railway auto-provisions `DATABASE_URL` as a reference variable on the backend service.

---

## 2. Backend Service Environment Variables

Set the following on `fracttal-prm-backend` (Variables tab):

| Variable | Value |
|---|---|
| `JWT_SECRET` | (generate a strong random 256-bit secret) |
| `JWT_EXPIRY_HOURS` | `168` |
| `FRONTEND_URL` | `*` |
| `JIRA_BASE_URL` | `https://synproconsulting.atlassian.net` |
| `JIRA_EMAIL` | `synproconsulting@gmail.com` |
| `JIRA_API_TOKEN` | (the active token from `id.atlassian.com`) |
| `JIRA_PROJECT_KEY` | `FPRM` |
| `JIRA_BOARD_ID` | `67` |
| `GITHUB_TOKEN` | (PAT with `repo` + `workflow` scope) |
| `GITHUB_USERNAME` | `synproconsulting` |
| `GITHUB_REPO` | `Fracttal-PRM` |
| `DATABASE_URL` | (auto-provisioned from PostgreSQL plugin reference) |

> `FRONTEND_URL=*` is required per CLAUDE.md hard rule — the backend CORS middleware reads this and any other value will block the Control Centre.

---

## 3. GitHub Secrets

Add the following to `synproconsulting/Fracttal-PRM` → **Settings → Secrets and variables → Actions**:

| Secret | Value | Used by |
|---|---|---|
| `PAT_TOKEN` | Personal Access Token (`repo` + `workflow` scope) | Auto-merger workflow dispatch (cannot use `GITHUB_TOKEN` — hard rule) |
| `RAILWAY_TOKEN` | Token from Railway → Account → Tokens | CI deploy step |
| `RAILWAY_PROJECT_ID` | `e5c41b7a-b96c-449d-964f-aba615d4cae0` | CI deploy step |
| `SONAR_TOKEN` | Token from `sonarcloud.io` → My Account → Security | SonarCloud analysis (non-blocking) |

### Current state (verified 2026-05-16 via GitHub API)

| Secret | Present? |
|---|---|
| `PAT_TOKEN` | MISSING |
| `RAILWAY_TOKEN` | MISSING |
| `RAILWAY_PROJECT_ID` | MISSING |
| `SONAR_TOKEN` | MISSING |

All four must be added before the CI pipeline created in FPRM-8 can dispatch the auto-merger or trigger a Railway redeploy.

---

## 4. Verification Steps

After the above is complete:

1. **Backend service** — visit `https://fracttal-prm-backend-production.up.railway.app/health` (created in FPRM-9) — should return `{"status": "ok", "service": "fracttal-prm-backend", "database": "connected"}`.
2. **Frontend service** — visit the Railway-assigned URL — should display the Fracttal PRM landing page.
3. **GitHub Actions** — push a trivial change to any `feature/*` branch; the CI workflow (from FPRM-8) should run pytest matrix + bandit, and the auto-merger should merge once tests pass.
4. **CLAUDE.md update** — once backend and frontend Railway URLs are confirmed live, the Sprint 1 closeout PR will update the "Live Deployments" table in `CLAUDE.md`.

---

## 5. Blockers / Follow-ups

- Backend and frontend Railway public URLs cannot be added to `CLAUDE.md` until Johan completes section 1.
- CI auto-merger and Railway deploy steps in `.github/workflows/ci.yml` (FPRM-8) will fail until section 3 is complete.
