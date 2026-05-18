# Fracttal PRM — Operational Runbook

> This file captures hard-won procedural knowledge from Sprints 1–10.
> It is the single source of truth for HOW to do operational tasks — not what to build.
> Load this file alongside CLAUDE.md at the start of every session and before any pre-sprint validation.

---

## 1. Pre-Sprint Session Startup

Every Claude Code session must start with this sequence — no exceptions:

```cmd
cd "C:\Johan\SynPro Consulting\Fracttal PRM"
git pull origin main
claude --dangerously-skip-permissions
```

**Why `--dangerously-skip-permissions`:** Without it, Claude Code stops and prompts for permission on every PowerShell command, breaking autonomous execution. Always use this flag.

**Why `git pull` first:** Claude Code reads CLAUDE.md, PROJECT_CONTEXT.md, and CLAUDE_HISTORY.md from the local filesystem. If local files are behind main (e.g. after a sprint that merged PRs), Claude Code operates on stale context. Always pull before starting.

**What `git pull` does NOT cover:** Untracked files and locally-modified tracked files that were written by a prior Claude Code session but never committed locally. If the working tree is dirty after `git pull`, run:

```cmd
git fetch origin
git status
git checkout main
git reset --hard origin/main
git clean -fd --exclude=Documentation/
```

This discards local modifications and untracked files and aligns perfectly with `origin/main`, while preserving the local-only `Documentation/` folder. Safe to run — everything else canonical is on GitHub.

**Never run bare `git clean -fd` without `--exclude=Documentation/`.** The Documentation/ folder contains local reference files. Bare git clean deletes it. Fixed in FPRM-88 (Sprint 6 PR #41).

---

## 2. Authenticating Against the Live Backend

### The Swagger Authorize Button Does NOT Work

The Fracttal PRM backend only exposes OAuth2PasswordBearer in its OpenAPI spec, not a simple bearerAuth scheme. The Swagger UI "Authorize" padlock only shows the OAuth2 form, which does not accept a raw JWT token. **Do not attempt to use the Swagger Authorize button for authenticated endpoint testing.**

This is a known docs gap (noted in Sprint 4 — fix deferred). All authenticated testing must be done via curl in Command Prompt.

### Step 1 — Get a Token

**Option A — via Swagger (easiest for getting the token):**

1. Open `https://fracttal-prm-backend-production.up.railway.app/docs`
2. Find `POST /auth/login`
3. Click **Try it out**
4. Enter the JSON body:
```json
{
  "email": "admin2@test.com",
  "password": "TestPass123!"
}
```
5. Click **Execute**
6. Copy the `access_token` value from the response

**Option B — via curl in Command Prompt:**

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/auth/login" -H "Content-Type: application/json" -d "{\"email\":\"admin2@test.com\",\"password\":\"TestPass123!\"}"
```

### Step 2 — Set Token and Call Authenticated Endpoints

**Must be done in Command Prompt (cmd), NOT PowerShell.**

PowerShell uses `$token` syntax which conflicts with cmd variable expansion. Use cmd:

```cmd
set token=<paste full access_token here — no quotes, no spaces around =>

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/auth/me" -H "Authorization: Bearer %token%"
```

Note `%token%` (cmd syntax) — not `$token` (PowerShell syntax).

### Known Test Users on Railway

| Email | Password | Role | Notes |
|---|---|---|---|
| `admin@test.com` | `TestPass123!` | `partner_user` | Created in Sprint 4 testing — role is WRONG due to pre-fix registration bug. Do not use for admin tests. |
| `admin2@test.com` | `TestPass123!` | `system_admin` | Created after FPRM-73 role bug fix. Use this for all system_admin endpoint tests. |
| `partneradmin@testcorp.com` | `PartnerPass123!` | `partner_admin` | Created via invite flow test. Linked to Test Partner Corp org. |
| `s8test@partner.com` | `PartnerPass123!` | `partner_admin` | Sprint 8 test user. Linked to Sprint 8 Test Corp org (8b1dfc59-380a-4fc3-809e-949880cbb3b0). |
| `phase3a-v2@testpartner.com` | `PartnerPass123!` | `partner_admin` | Phase 3A Test Partner Ltd — fully activated. Org `b223c3b0-623e-405c-b056-6f076811e518`. |
| `conflicttest2@testpartner.com` | `PartnerPass123!` | `partner_admin` | Conflict Test Partner 2 — fully activated. Org `bf6dcf16-65e4-4ef9-b5e8-9a36608b82a8`. Use as second org for §13 conflict-detected path. |

**Important:** If you need a fresh user with a specific role, always register a new user — do not try to update an existing user's role in the database. The `role` column is set at registration and not exposed via a patch endpoint.

### If Token Returns `{"detail":"Invalid token"}`

The JWT has expired (7-day expiry) or was signed with a different `JWT_SECRET` than what Railway currently has set. Get a fresh token by logging in again. Do not debug further — just re-login.

---

## 3. Testing the Live Backend — Standard Validation Sequence

Use this checklist before every sprint to confirm the prior sprint's deliverables are intact.

### Health Check (no auth required)

```
https://fracttal-prm-backend-production.up.railway.app/health
```

Expected: `{"status":"ok","service":"fracttal-prm-backend","database":"connected"}`

If `"database":"connected"` is missing, Railway's PostgreSQL service is down or DATABASE_URL is misconfigured.

### Public Endpoints (no auth required)

```cmd
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/config/partner-categories"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/config/commission-structures"
```

### Authenticated Endpoints (requires system_admin token)

```cmd
set token=<system_admin token>

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/auth/me" -H "Authorization: Bearer %token%"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners" -H "Authorization: Bearer %token%"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/admin/audit-log" -H "Authorization: Bearer %token%"
```

### Creating a Test Partner Org

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/partners" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"legal_name\":\"Test Partner Corp\",\"program_type\":\"distributor\",\"partner_category\":\"master\"}"
```

Copy the `id` from the response — you'll need it for invite and application tests.

### Document Upload Field Names

`POST /partners/{id}/documents` requires `document_name` and `file_path` — **not** `file_name` or `file_url` as their names might suggest. The API returns sequential 422 validation errors that do not name the expected fields, so picking the wrong names burns time.

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/partners/<partner_id>/documents" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"document_type\":\"nda\",\"document_name\":\"nda.pdf\",\"file_path\":\"uploads/nda.pdf\"}"
```

Discovered Sprint 10 — tracked as FPRM-174. The same field names apply to the public application upload endpoint `POST /applications/{id}/documents?draft_token=...`.

### Invite Flow Test

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/partners/<partner_id>/users/invite" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"email\":\"partneradmin@testcorp.com\",\"invited_role\":\"partner_admin\"}"
```

Copy the `token` from the response, then accept:

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/auth/accept-invite" -H "Content-Type: application/json" -d "{\"token\":\"<invite_token>\",\"password\":\"PartnerPass123!\",\"full_name\":\"Partner Admin User\"}"
```

### Phase 2 Application Flow Test (run before Sprint 8 and after any deploy touching applications, provisioning, activation, or auth)

```cmd
REM Step 1 — Create and submit application (public, no auth)
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/applications" -H "Content-Type: application/json" -d "{\"applicant_email\":\"test@example.com\",\"applicant_name\":\"Test Applicant\"}"
REM Copy id and draft_token, then:
curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/applications/<id>?draft_token=<token>" -H "Content-Type: application/json" -d "{\"legal_name\":\"Test Corp\",\"terms_accepted\":true}"
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/applications/<id>/submit?draft_token=<token>"

REM Step 2 — Approve (system_admin token required)
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/applications/<id>/approve" -H "Authorization: Bearer %token%"

REM Step 3 — Verify provisioning
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/<partner_org_id>" -H "Authorization: Bearer %token%"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/<partner_org_id>/activation" -H "Authorization: Bearer %token%"

REM Step 4 — Send invite and accept
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/partners/<partner_org_id>/users/invite" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"email\":\"newpartner@test.com\",\"invited_role\":\"partner_admin\"}"
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/auth/accept-invite" -H "Content-Type: application/json" -d "{\"token\":\"<invite_token>\",\"password\":\"PartnerPass123!\",\"full_name\":\"Test Partner\"}"

REM Step 5 — Confirm partner_admin access
set partnertoken=<access_token from accept-invite response>
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/auth/me" -H "Authorization: Bearer %partnertoken%"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/<partner_org_id>/activation" -H "Authorization: Bearer %partnertoken%"
```

Expected: 201 → 200 (submitted) → 200 (approved, partner_org_id returned) → org status=active → checklist all False → access_token returned with role=partner_admin → activation_complete=False.

### Known Behaviour: Invite Token Not Retrievable via GET

The provisioning flow creates a PartnerUserInvite record automatically but there is no GET endpoint to retrieve the token after the fact. To get a usable invite token for testing, send a fresh invite via POST /partners/{id}/users/invite. The returned token is immediately usable.

### Known Behaviour: 404 vs 403 on Tenant Isolation

When a partner_admin tries to access another org's data, the backend returns 404 ("Partner not found") instead of 403 ("Access denied"). This is intentional security-by-obscurity behaviour — it does not reveal whether the resource exists. **This is not a bug — do not raise a ticket for it.**

---

## 4. Railway Deployment Verification

### Checking Migration Status

After any deploy, open Railway → fracttal-prm-backend → Deployments → click the latest deployment → view logs.

**Correct behaviour when migrations are already at head (no new migrations):**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO:     Started server process [1]
```
No `Running upgrade` lines = already at head. This is correct, not a problem.

**Correct behaviour when new migrations apply:**
```
INFO  [alembic.runtime.migration] Running upgrade 008 -> 009, <migration name>
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO:     Started server process [1]
```

**If you see an ERROR between the alembic line and uvicorn start:** migrations failed. Check the error message — it's usually a missing column, wrong type, or a Python 3.13 package incompatibility.

### Railway Start Command

The backend start command is:
```
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

Railway's `rootDirectory` is already `/backend` — do NOT add `cd backend &&`. The container starts inside `/backend/` already.

### Triggering a Redeploy

Railway auto-deploys on every push to `main`. To trigger manually: Railway → fracttal-prm-backend → Deployments → Redeploy.

---

## 5. Python Package Compatibility — Python 3.13 on Railpack

Railway defaults new services to Python 3.13. The Sprint 1 pins (Oct/Nov 2023) were all incompatible. These have all been upgraded and are confirmed Python 3.13 compatible as of Sprint 2/3:

| Package | Current Version | Fixed in |
|---|---|---|
| `pydantic` | 2.11.4 | FPRM-37 |
| `sqlalchemy` | 2.0.36 | FPRM-38 |
| `alembic` | 1.14.0 | FPRM-38 |
| `psycopg2-binary` | 2.9.10 | FPRM-39 |
| `fastapi` | 0.115.12 | FPRM-40 |
| `uvicorn` | 0.34.2 | FPRM-40 |
| `pyjwt` | 2.10.1 | FPRM-40 |
| `httpx` | 0.28.1 | FPRM-40 |
| `pytest` | 8.3.5 | FPRM-40 |
| `starlette` | 0.46.2 | FPRM-40 |

If a new package is added to `requirements.txt` and Railway fails to build, check if the pinned version has a Python 3.13 wheel. The pattern is: upgrade to the latest stable release, which almost always has 3.13 support.

**Never use `railway.toml` with `nixPkgs` for Python version pinning** — Railway uses Railpack, not Nixpacks. The `railway.toml` Nixpacks syntax is ignored and will not work.

---

## 6. Local Development Environment

### Working Directory
```
C:\Johan\SynPro Consulting\Fracttal PRM
```

### Activating the Local venv

The `.venv` was created in Sprint 4 using Python 3.13:

```cmd
cd "C:\Johan\SynPro Consulting\Fracttal PRM"
.venv\Scripts\activate
```

### Running Backend Locally

```cmd
cd backend
uvicorn main:app --reload
```

### Running Tests Locally

```cmd
cd backend
pytest tests/ -v
```

### Shell Behaviour Notes

- Claude Code runs in **PowerShell** (`.venv` activation prompt shows as `(.venv)`)
- Manual curl tests must be run in **Command Prompt (cmd)**, not PowerShell
- `$variable` syntax = PowerShell; `%variable%` syntax = cmd
- If you see `'$token' is not recognized` — you are in cmd, not PowerShell. Use `%token%` instead.

**Documentation/ folder must not be deleted by git clean.** Always use `git clean -fd --exclude=Documentation/`. The folder is intentionally untracked — it holds local operational reference files. Fixed in FPRM-88.

---

## 7. Jira Operational Notes

### Sprint Query Pattern

Always dual-query — native sprint IDs and fix versions get out of sync:

```python
jql = f"project = FPRM AND (fixVersion = {fix_id} OR sprint = {native_id})"
```

### Subtask Issue Type

The correct issue type name is `Sub-task` (hyphenated). `Subtask` (no hyphen) is rejected by this Jira instance with a 400 error.

### Closed Sprints

Bug tickets discovered after a sprint closes cannot be added to the closed native sprint (Jira rejects it). Assign to the fix version only — the fix version is the durable traceability mechanism (AD-4).

### Jira API Calls go Through Proxy

The Control Centre never calls Jira directly — all Jira requests in the frontend go through `/proxy/jira/*` on the shared SynPro VSDC backend with `product_id` identifying Fracttal PRM. Claude Code calls Jira directly via REST API using credentials from `.env`.

### Auto-merger 405 Race Condition

The rule-based auto-merger occasionally returns `HTTP 405` on its merge attempt even when all blocking checks are green. Observed on Sprint 10 PR #73 (FPRM-160). When it happens:

1. Confirm the blocking checks (`Test (Python 3.11)`, `Test (Python 3.12)`, bandit security scan) are all green on the PR.
2. Merge the PR manually via the GitHub UI — do not retry the auto-merger dispatch and do not rebase.
3. The sprint still closes cleanly; no follow-up ticket is required.

Root cause is a race between GitHub's check-suite settling and the auto-merger's merge call. Do not treat the 405 as a CI failure.

---

## 8. GitHub and CI/CD Notes

### CI Triggers

CI runs on push to `feature/**` and `fix/**` branches. Both prefixes are valid. The `ci.yml` fix was applied in FPRM-20 (Sprint 1).

### Auto-Merger Check Names

The auto-merger's blocking check filter uses title-cased names: `"Test (Python 3.11)"` and `"Test (Python 3.12)"` — not lowercase. If you reuse any monitor script as a template, ensure the BLOCKING set matches these exact strings.

### GITHUB_TOKEN vs PAT_TOKEN

`GITHUB_TOKEN` (the built-in Actions token) cannot trigger `workflow_dispatch` events. Use `PAT_TOKEN` for all workflow dispatch API calls.

### One PR at a Time

Before opening any PR, verify zero open PRs via the GitHub API. The auto-merger serialises merges — opening a second PR while one is pending causes race conditions.

---

## 9. Project File Management

### Files That Must Be Uploaded as Project Files (not just chat attachments)

All of these must be in the Claude Project as uploaded files — not just generated in chat:

- `CLAUDE.md`
- `PROJECT_CONTEXT.md`
- `CLAUDE_HISTORY.md`
- `FPRM_Phase1_Jira_Tickets.md`
- `FPRM_Phase2_Jira_Tickets.md`
- `FPRM_Sprint1_ClaudeCode_Prompt.md` through current sprint
- `RUNBOOK.md` (this file)

### Why This Matters

Files attached to a chat session are not available in new sessions. Only files uploaded to the Claude Project persist automatically. If a file was generated in a chat and not uploaded to the project, the next session will not have it — leading to the "I don't have that file" disconnect between sessions.

### Keeping Files in Sync

The canonical copy of `CLAUDE.md`, `PROJECT_CONTEXT.md`, `CLAUDE_HISTORY.md`, and `RUNBOOK.md` is in the **GitHub repo**. The copies in the Claude Project are reference copies for planning sessions. After any sprint that updates these files via PR, update the Claude Project copies too.

---

## 10. Known System Limitations and Gotchas

| Issue | Detail | Workaround |
|---|---|---|
| Swagger bearerAuth not exposed | OpenAPI spec only shows OAuth2, not bearerAuth. Authorize button doesn't work for JWT testing. | Use curl in cmd with `%token%` syntax. |
| Existing user role not updatable | `role` is set at registration. Old test users retain their original (possibly wrong) role. | Register new test users when you need a specific role. |
| Local venv path conflict | Claude Code was initially picking up the VSDC project's venv instead of the Fracttal PRM one. | `.venv` now exists at `C:\Johan\SynPro Consulting\Fracttal PRM\.venv`. Claude Code finds it automatically. |
| Git not initialised locally | The local repo was initialised in Sprint 4. If it ever needs reinitialising: `git init`, `git remote add origin https://github.com/synproconsulting/Fracttal-PRM.git`, `git fetch origin`, `git checkout -f main`. | |
| `git checkout main` fails on first init | Untracked files from prior Claude Code sessions block checkout. Use `git checkout -f main` to force. | |
| Credentials must never be pasted in chat | Jira tokens, Railway tokens, GitHub PATs — all go directly into `.env` file. Never paste into any chat interface. | Create/edit `.env` manually in VS Code or Notepad. |
| Invite token not retrievable via GET | Provisioning creates PartnerUserInvite automatically but no GET /invites endpoint exists. | Send a fresh invite via POST /partners/{id}/users/invite to get a usable token for testing. |
| Notification calls must be try/except wrapped | Email failures crash the endpoint if unwrapped. AD-13. | All send_email() calls in routers wrapped in try/except. Never call unwrapped in a router. |
| Endpoints using _user_from_bearer not testable via dependency_overrides | Manual Authorization header reads bypass FastAPI dependency injection. FPRM-104 tracks this. | Mint a real JWT in tests or use the public draft_token path. Do not use app.dependency_overrides[get_current_user] for these endpoints. |
| JWT payload missing partner_org_id | Sprint 7 bug FPRM-119 — JWT was missing partner_org_id claim. Fixed in PR #48. | If portal pages fail to load partner data, check GET /auth/me returns partner_org_id in the response. |
| SMTP env vars not set on Railway | Email notifications fall back to stdout logging (AD-13 dev mode). No crash. | Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, CHANNEL_OPS_EMAIL, FRONTEND_URL on fracttal-prm-backend Railway service when ready for live email delivery. |
| Partners created via POST /partners have no profile record | `profile_complete` can never flip → `activation_complete` stuck at False. Tracked in FPRM-172. | Until the fix lands, provision test partners via the application flow (POST /applications → submit → approve) — `provision_partner_from_application` is the only path that creates the PartnerProfile row. |
| `commission_rate_snapshot` always null when `commission_type=standard` | No `standard` row exists in `commission_structures` — the lookup `(category, type, year_1)` finds no match and snapshot stays null. Tracked in FPRM-173. | Use one of the seeded vocab values: `autonomous_sell`, `indirect_sell`, `direct_sell`, `co_sell_shared`. Sprint 10 / FPRM-158 aligned the deal form to this list. |
| Document upload fields are `document_name` + `file_path` | Sending `file_name` / `file_url` returns sequential 422s without naming the expected fields. Tracked in FPRM-174. | Use the field names from § 3 above — same shape for `POST /partners/{id}/documents` and `POST /applications/{id}/documents`. |
| `partner_profiles` has no POST endpoint | The profile row is only created by `provisioning.provision_partner_from_application`. There is no standalone create route. | Always provision test partners via the application flow (see FPRM-172 row above). PATCH /partner-profiles/{id} only works on existing rows. |
| Auto-merger occasionally returns 405 on merge | Race between GitHub check-suite settling and the auto-merger's merge call. Observed Sprint 10 PR #73 (FPRM-160). | Merge the PR manually via the GitHub UI once blocking checks are green. See § 7 for the full procedure. Sprint still closes cleanly. |

---

## 11. End-to-End Happy Path Validation — Phase 2

Run this after every Sprint 5–7 deploy and before starting Sprint 8. It exercises the full public-application → internal-review → provisioning → invite → portal → activation chain.

Use Command Prompt (`cmd`) for curl with `%token%`; PowerShell uses `$token` and will not interpolate cleanly.

### Step 1 — Submit a new application (public, no auth)

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/applications" -H "Content-Type: application/json" -d "{\"applicant_email\":\"happypath+%RANDOM%@test.com\"}"
```

Record the returned `id` and `draft_token`. Fill in the required fields and submit:

```cmd
set app_id=<id from above>
set draft_token=<draft_token from above>

curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/applications/%app_id%?draft_token=%draft_token%" -H "Content-Type: application/json" -d "{\"applicant_name\":\"Happy Path Tester\",\"legal_name\":\"Happy Path Co\",\"requested_categories\":[\"reseller\"],\"terms_accepted\":true}"

curl -X POST "https://fracttal-prm-backend-production.up.railway.app/applications/%app_id%/submit?draft_token=%draft_token%"
```

Confirm response shows `status=submitted` and `submitted_at` is populated.

### Step 2 — Approve as internal user (system_admin)

Get a system_admin JWT per § 2 of this RUNBOOK. Then:

```cmd
set token=<system_admin token>

curl -X POST "https://fracttal-prm-backend-production.up.railway.app/applications/%app_id%/approve" -H "Authorization: Bearer %token%"
```

Confirm response includes `status=approved`, `partner_org_id` (UUID), and `invite_token` (hex). Save the `partner_org_id` and `invite_token`.

### Step 3 — Confirm provisioning

```cmd
set partner_id=<partner_org_id from above>

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/%partner_id%" -H "Authorization: Bearer %token%"
```

Expect `status=active`, `legal_name=Happy Path Co`.

```cmd
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/%partner_id%/activation" -H "Authorization: Bearer %token%"
```

Expect all four flags `false` and `activation_complete=false`. (`partner_org_id` matches.)

### Step 4 — Accept the invite

```cmd
set invite_token=<invite_token from approve response>

curl -X POST "https://fracttal-prm-backend-production.up.railway.app/auth/accept-invite" -H "Content-Type: application/json" -d "{\"token\":\"%invite_token%\",\"full_name\":\"Happy Path Tester\",\"password\":\"HappyPath123!\"}"
```

Expect 201 with `access_token`, `user.role=partner_admin`, `user.partner_org_id` matching `%partner_id%`.

### Step 5 — Login as the new partner_admin and confirm JWT

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/auth/login" -H "Content-Type: application/json" -d "{\"email\":\"<applicant_email from Step 1>\",\"password\":\"HappyPath123!\"}"

set ptoken=<access_token from response>

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/auth/me" -H "Authorization: Bearer %ptoken%"
```

Confirm `/auth/me` returns `role=partner_admin` and `partner_org_id` matches `%partner_id%` (FPRM-119 verification).

### Step 6 — Confirm the portal loads in the browser

Open `https://fracttal-prm-frontend-production.up.railway.app/login`, sign in with the new credentials. Expect:

- Landing on `/portal/home`
- Header shows the org name and the user email
- `Pending Activation` badge (yellow)
- `Activate your account` widget visible with 0/3 items complete
- Task tiles all show `Coming soon`
- Sidebar — Home active, profile/documents nav items live, others disabled

### Step 7 — Confirm activation gates from the portal

- Click `Complete profile`, fill the profile form so completeness ≥ 80%, save, return to `/portal/home`. Refresh and confirm `Complete your partner profile` is ticked.
- Click `Upload documents`, upload a placeholder PDF as `fiscal_id`, and another as `id_legal_representative`. As system_admin (from § 2) hit `PATCH /partners/{partner_id}/documents/{doc_id}` with `{"status": "approved"}` for both. Refresh the partner view of `/portal/home` and confirm `Upload required documents` is ticked.
- The third row (`Sign the partnership agreement`) stays unticked until a channel team member sets `contract_start_date` on the partner via `PATCH /partners/{partner_id}`.

The whole flow exercises Sprints 5, 6, and 7 end-to-end. If any step fails, capture the curl output and open a bug ticket in the current sprint before moving on.

---

## 12. End-to-End Happy Path Validation — Phase 3A (Deal Registration & Review Workflow)

Run this end-to-end against the production Railway backend before starting Sprint 10. Exercises the full Sprint 8 + Sprint 9 deal lifecycle — submit, internal review, info request, partner reply, resubmit, approve.

### Prerequisites

- A fully activated partner (`activation_complete = True`) exists in the system. Use the partner created in Phase 2 validation (§ 11), then mark training complete via `POST /partners/{partner_id}/activation/training-complete` as `system_admin` (FPRM-145 added training to the gate — existing happy-path partners must also have `baseline_training_complete=True`).
- A `partner_admin` JWT for that partner (see § 2 for token-fetching).
- A `channel_manager` or `system_admin` JWT for the internal reviewer.

### Step 1 — Submit a deal registration

```cmd
set ptoken=<partner_admin token>

curl -X POST "https://fracttal-prm-backend-production.up.railway.app/deal-registrations" -H "Authorization: Bearer %ptoken%" -H "Content-Type: application/json" -d "{\"customer_name\":\"Test Customer Corp\",\"customer_domain\":\"testcustomer.com\",\"deal_name\":\"Phase 3A Test Deal\",\"commission_type\":\"reseller\",\"estimated_deal_value\":15000}"
```

Expect `201`, `status=draft`, `partner_org_id` set, `commission_rate_snapshot=null` (not yet submitted). Capture the returned `id` as `%deal_id%`.

### Step 2 — Submit the draft

```cmd
set deal_id=<id from step 1>

curl -X POST "https://fracttal-prm-backend-production.up.railway.app/deal-registrations/%deal_id%/submit" -H "Authorization: Bearer %ptoken%"
```

Expect `200`, `status=submitted`, `submitted_at` set, `commission_rate_snapshot` populated (if a `commission_structures` row exists for the partner's category + `commission_type=reseller` + `year_1`).

### Step 3 — Internal reviewer starts review

```cmd
set itoken=<channel_manager or system_admin token>

curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/%deal_id%/start-review" -H "Authorization: Bearer %itoken%"
```

Expect `200`, `status=under_review`, `reviewer_id` populated.

### Step 4 — Internal reviewer requests more info

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/%deal_id%/request-info" -H "Authorization: Bearer %itoken%" -H "Content-Type: application/json" -d "{\"message\":\"Please provide the customer's registered address.\"}"
```

Expect `200`, `status=info_required`. Verify the message landed in the thread:

```cmd
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/deal-registrations/%deal_id%/messages" -H "Authorization: Bearer %itoken%"
```

Expect at least one message with `sender_type=internal`.

### Step 5 — Partner responds and resubmits

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/deal-registrations/%deal_id%/messages" -H "Authorization: Bearer %ptoken%" -H "Content-Type: application/json" -d "{\"message\":\"Customer address: 123 Main St, Buenos Aires.\"}"
```

Expect `201`, message appears in subsequent `GET /messages` with `sender_type=partner`.

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/deal-registrations/%deal_id%/submit" -H "Authorization: Bearer %ptoken%"
```

Expect `200`, `status=submitted` (transition from `info_required → submitted`).

### Step 6 — Internal reviewer approves

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/%deal_id%/start-review" -H "Authorization: Bearer %itoken%"

curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/%deal_id%/approve" -H "Authorization: Bearer %itoken%" -H "Content-Type: application/json" -d "{\"review_notes\":\"Deal approved — Phase 3A validation.\"}"
```

Expect `200`, `status=approved`, `reviewed_at` populated, `review_notes` set.

All six steps green = Phase 3A chain confirmed. Safe to proceed with Sprint 10.

### Frontend smoke check

After backend validation, open `https://fracttal-prm-frontend-production.up.railway.app`:

1. Sign in as the partner. `/portal/deals` lists the deal; click the deal name → lands on `/portal/deals/:deal_id`. Status banner reflects `approved` with green tone.
2. Sign in as the internal reviewer. `/internal/deals` lists the deal with the **partner org legal name** in the Partner column (not the UUID — FPRM-143). Click the deal name → lands on `/internal/deals/:deal_id`. Commission snapshot, conflict status (not_checked), and the full collab thread render.

### Known operational note: training gate (FPRM-145)

Any partner that has not yet had `POST /partners/{id}/activation/training-complete` called for them will have `activation_complete=False`, so step 1 returns `412 {detail, activation_url}`. This is intentional. Before running this validation against a fresh partner, ensure training has been marked complete by an admin.

---

## 13. End-to-End Happy Path Validation — Phase 3 (Conflict Checking + Commission Override)

Run this after every Sprint 10+ deploy and **before starting Phase 4**. Exercises the full Sprint 8 + 9 + 10 deal lifecycle including the conflict checker and commission override paths.

### Prerequisites

- A fully-activated partner exists (`activation_complete = True`). Sprint 10 / FPRM-156 relaxed the `documents_uploaded` rule — one approved document is now sufficient. A partner created via Phase 2 validation (§11) and then `POST /partners/{id}/activation/training-complete` should pass.
- A `partner_admin` JWT for that partner. The Phase 3A validator script in `.sprint10/bug_0_validate.py` invites a fresh user (`s10val+<random>@phase3atest.com`) and accepts the invite to mint one when no partner_admin exists for an org.
- A `channel_manager` or `system_admin` JWT for the internal reviewer (`admin2@test.com` works for system_admin per §2).
- For the conflict-detected path: a **second** activated partner org in a different account, so two different `partner_org_id` values can both register against the same `customer_domain`.

### Clear path (no conflict)

```cmd
set ptoken=<partner_admin token>
set itoken=<channel_manager / system_admin token>

REM 1. Create + submit
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/deal-registrations" -H "Authorization: Bearer %ptoken%" -H "Content-Type: application/json" -d "{\"customer_name\":\"Clear Customer\",\"customer_domain\":\"clearpath.com\",\"deal_name\":\"Clear Path Deal\",\"commission_type\":\"autonomous_sell\"}"
REM Capture the returned id as %deal_id%
set deal_id=<id>
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/deal-registrations/%deal_id%/submit" -H "Authorization: Bearer %ptoken%"
```

Expect `200`, `status=submitted`, `conflict_status=clear` (no other deals against `clearpath.com`).

```cmd
REM 2. Start review + approve
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/%deal_id%/start-review" -H "Authorization: Bearer %itoken%"
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/%deal_id%/approve" -H "Authorization: Bearer %itoken%" -H "Content-Type: application/json" -d "{\"review_notes\":\"Phase 3 happy path — approved.\"}"
```

Expect `status=approved`. Confirm `conflict_status` stayed `clear` throughout.

### Conflict-detected path

1. Have **partner A** submit a deal against `hotdomain.com` (steps as above, but for the first partner_admin).
2. As **partner B** (different org's partner_admin), submit a deal against the same `hotdomain.com`:

```cmd
set ptoken_b=<partner_admin token from a different org>
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/deal-registrations" -H "Authorization: Bearer %ptoken_b%" -H "Content-Type: application/json" -d "{\"customer_name\":\"Conflict Customer\",\"customer_domain\":\"hotdomain.com\",\"deal_name\":\"B's Attempt\",\"commission_type\":\"autonomous_sell\"}"
set b_deal=<returned id>
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/deal-registrations/%b_deal%/submit" -H "Authorization: Bearer %ptoken_b%"
```

Expect `conflict_status=conflict_detected`, `conflict_notes` mentioning the domain and conflict count.

3. As an internal reviewer (`channel_manager` or `system_admin`), override the conflict:

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/%b_deal%/override-conflict" -H "Authorization: Bearer %itoken%" -H "Content-Type: application/json" -d "{\"override_notes\":\"Customers confirmed this is a parent/subsidiary case — different buying centres.\"}"
```

Expect `200`, `conflict_status=clear`, `conflict_notes` ends with `[OVERRIDE by <reviewer email>]: <override_notes>`.

4. As `partner_admin`, attempt to call the override endpoint — expect `403`.

### Commission rate visibility

```cmd
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/<partner_id>/commission-rates" -H "Authorization: Bearer %ptoken%"
```

Expect `200` with `partner_category_code` matching the partner's category and `items` populated with the seeded commission_structures rows.

### Frontend smoke (browser)

1. Sign in as the partner. Sidebar shows the **Commissions** item (enabled, no "Coming soon"). Click it → `/portal/commissions` renders the rate table.
2. Click **Register a Deal**, fill in a customer + select **Autonomous Sell** → helper text reads `Applicable rate (Year 1): 50%` (matches the seeded `autonomous_sell + year_1` row).
3. Sign in as the internal reviewer. Open the conflict-detected deal at `/internal/deals/:id`. **Conflict Check** card shows red `Conflict Detected ⚠️` + the notes + **Override Conflict** button.
4. Click **Override Conflict** — modal opens, requires min-10-char notes, on confirm the badge flips green `Clear ✅` and a transient `Conflict overridden` toast appears bottom-right.
5. Open the same deal as the partner (`/portal/deals/:id`) — confirm no conflict status / notes / override controls are visible to partners.

All steps green = Phase 3 fully validated. Safe to proceed with Phase 4.

### Known operational notes (Sprint 10)

- **Conflict checker is best-effort.** If `conflict_checker.check_deal_conflict` raises, the submit endpoint swallows it inside try/except so the status flip and commission snapshot still persist. The deal will simply carry `conflict_status='not_checked'`. Monitor backend logs after deploys touching `conflict_checker.py` or `deal_registrations_router.py`.
- **`channel_ops_admin` cannot override.** Only `channel_manager` + `system_admin` are in `OVERRIDE_ROLES`. If ops complain about a 403, that is by design — point them at a `channel_manager` JWT.
- **Form commission_type vocabulary** is fixed to `autonomous_sell / indirect_sell / direct_sell / co_sell_shared` after FPRM-158 — these are the only values that resolve a row in `commission_structures` for the rate preview helper.

---

*RUNBOOK created: May 2026*
*Sources: Sprint 1–3 Console Dialog, Sprint 4 Console Dialog, Sprint 5–10 closeout*
*Last updated: Sprint 10 closeout / Phase 3 complete — May 2026*
*Update this file whenever a new operational lesson is learned — do not let lessons live only in console dialogs.*
