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
| `cmtest@test.com` | `TestPass123!` | `channel_manager` | Internal reviewer — no tenant scope. Created during post-Sprint-20 UX & workflow validation. Use for the channel-manager-only paths in §17 (conflict rerun, deal won, retract gate, pipeline toggle) and any future scenario that needs an internal reviewer below system_admin. |

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

### Build PR bodies from a file, never from an inline shell command with backticks

When creating/updating a PR via the GitHub API, read the body from a file (e.g. a file-based PATCH, or `gh pr create --body-file`), not from an inline `python -c "..."` / shell string that contains backticks. In a double-quoted shell command, backticks trigger command-substitution **before** the script runs, so any `` `code spans` `` in the body get executed as commands and stripped — the published PR body comes out mangled. Observed on the PR #184 docs PR; fixed there with a file-based PATCH. Markdown bodies (which always contain backticks) must go through a file.

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
| Partner document uploads auto-approve by default (FPRM-384) | Since the Sprint 22 hotfix, `POST /partners/{id}/documents` sets `status=approved` unless a `document_type_rules` row for that `document_type` has `requires_approval=true` (then `pending_review`). The `contract` seed is gated; `quote_acceptance` and unruled types auto-approve. | When testing the manual review path, first create/flip a rule with `requires_approval=true` via `POST/PATCH /admin/document-type-rules`. The §11 step-7 "approve both docs as system_admin" is now only needed for `requires_approval` types. |
| Rule `document_type` matching is **case-insensitive + whitespace-trimmed** (FPRM-386) | The Program Config → Document Rules form is free-text. Originally the upload lookup was an exact `==`, so a rule typed as `NDA` never matched an upload of `nda` → the `requires_approval` gate was silently bypassed and the doc auto-approved. The match is now normalised (`LOWER(TRIM(...))`) on both sides, and the rule-create duplicate check is case-insensitive (can't create both `NDA` and `nda`). | No action — a rule entered in any casing now governs uploads of the canonical lowercase code. Don't rely on case to create variant rules; they're treated as the same type. |
| Partner self-service delete is permanent (FPRM-383) | `DELETE /partners/{id}/documents/{doc_id}` as a `partner_admin` now hard-deletes an unreferenced document (versions cascade) instead of soft-flagging `rejected`. If the doc is referenced by a quote, it still 409s. | To delete, first remove all `document_references` (detach from quotes); then the partner delete succeeds and the row is gone. |
| Document-type rules are freely deletable (FPRM-385) | `DELETE /admin/document-type-rules/{id}` no longer 409s when documents of that type exist. Existing documents keep their status. | None — delete any rule at any time as system_admin. |
| Partners can self-accept their own quotes (Sprint 23 / FPRM-389, AD-35) | `partner_user`/`partner_admin` may attach a `quote_acceptance` doc to, and `PATCH /quotes/{id}/status`→`accepted`, a quote in their own org. They cannot create/edit/submit/retract/delete; retract stays system_admin-only. | To test: as a partner, open the quote in the portal (status `sent`), attach proof, then click **Mark as Accepted**. Accept without an attachment → 422; another org's quote → 403. |
| Partner_admin can revert own-org document versions (Sprint 23 / FPRM-390, AD-36) | Supersedes the Sprint 22 internal-only rule. Revert emits a `document.version_reverted` audit event; the UI shows a confirm dialog. `partner_user` still excluded. | Revert button appears in the version-history panel for internal roles and `partner_admin`. Another org → 403/404. |
| Document uploads gated by **size (25 MB)**, not type (Sprint 23 / FPRM-391, AD-37) | The PDF/JPG/PNG allowlist is removed (it only ever lived in the browser `accept` filter; the backend never enforced type). `POST /partners/{id}/documents` and `.../versions` reject `file_size_bytes > 26214400`. Asset Library (PR B) keeps its own 10 MB cap. | Any file type ≤25 MB uploads; >25 MB → 422 "Maximum upload size is 25 MB." |
| Document types are data-driven (Sprint 23 / FPRM-387, AD-38) | Two tables: `document_types` = vocabulary (the dropdown list, served by `GET /config/document-types`); `document_type_rules` = approval policy. Migration 039 seeds both. `GET /config/document-types` was NOT repurposed to return rules. | Manage selectable types + rules in Program Config → Document Rules (the type field is now a dropdown + "Add new type"). |
| Asset Library (Sprint 23 PR B / FPRM-393, AD-39) | Enablement assets stored base64 in `assets.file_data`; **10 MB upload cap** (channel_ops_admin+, `POST /internal/assets`); `file_data` never in list responses; download (`GET /assets/{id}/download`) is logged (`asset_download_logs`) + increments `download_count`. Deletes are **soft** (`is_active=false`, system_admin). Visibility: `all` / `tier:<tier>` / `category:<code>` enforced on the partner list + download. | Partners browse at **/portal/assets** ("Resources" nav); internal manage at **/internal/assets** ("Assets" nav). Visibility-denied download → 404. The 10 MB asset cap is independent of the 25 MB partner-documents cap. |

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

## 14. End-to-End Happy Path Validation — Phase 4 Sprint 11 (Internal Shell + Dashboards)

After deploying Sprint 11 (PRs #78–#83 squashed into `main` and Railway deploys settled), run this happy-path validation against production. All steps green = Sprint 11 fully validated.

Substitute `<ADMIN_TOKEN>` (any internal role with dashboard access) and `<PARTNER_TOKEN>` (a partner_admin of an org with at least one deal).

### 1. Internal dashboard summary endpoint

```cmd
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/dashboard/summary" -H "Authorization: Bearer <ADMIN_TOKEN>"
```

Expect `200` with this shape:
```json
{
  "applications": {"pending_review": ..., "info_required": ..., "total_this_month": ...},
  "deals":        {"submitted": ..., "under_review": ..., "approved_this_month": ..., "total_pipeline_value": ...},
  "partners":     {"active": ..., "pending_activation": ..., "total": ...},
  "conflicts":    {"open": ...}
}
```

A `sales_rep` / `partner_admin` token must return `403`.

### 2. Partner dashboard summary endpoint

```cmd
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/<PARTNER_ORG_ID>/dashboard/summary" -H "Authorization: Bearer <PARTNER_TOKEN>"
```

Expect `200`. Confirm `deals` totals match the partner's own deal pipeline (compare against `GET /deal-registrations?limit=100`), `activation.items_complete` matches the checked boxes in `GET /partners/{id}/activation`, and `documents` counts match `GET /partners/{id}/documents` grouped by `status`. A different partner_admin's token against this `partner_id` must return `403` with detail "not your organisation".

### 3. Cancel info request — application

Pick an application currently in `info_required` status (use `GET /internal/applications?status=info_required`). Then:

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/applications/<APP_ID>/cancel-info-request" -H "Authorization: Bearer <ADMIN_TOKEN>"
```

Expect `200` with `{"id":"…","status":"in_review","info_request_message":null}`. Confirm via `GET /applications/<APP_ID>` that the status flipped. Calling cancel again should return `400` "Application is not in info_required status". A `partner_admin` token must return `403`.

### 4. Cancel info request — deal

Pick a deal in `info_required` (use `GET /internal/deals?status=info_required`). Then:

```cmd
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/<DEAL_ID>/cancel-info-request" -H "Authorization: Bearer <ADMIN_TOKEN>"
```

Expect `200` with status `under_review`. Then `GET /deal-registrations/<DEAL_ID>/messages` should include a new internal message with body "Info request cancelled by reviewer." A `partner_admin` token must return `403`. `sales_rep` must return `403`.

### 5. Forgot-password flow (manual, browser + Railway logs)

1. In the browser at `https://fracttal-prm-frontend-production.up.railway.app/login`, click **Forgot password?** — lands on `/forgot-password`.
2. Submit an email of a known active user. UI shows the generic "If that email is registered…" success message. The actual reset link prints to Railway backend logs (SMTP env vars not yet set — see §10 + CLAUDE.md Known Issues).
3. Copy the URL from logs and open it in the browser. It must contain `?token=…` and render `/reset-password` with both password fields.
4. Submit a new password. Expect redirect to `/login` with the green toast "Password reset successfully. Please log in."
5. Sign in with the new password — destination is `/internal/home` for internal roles (FPRM-179) or `/portal/home` for partner roles.

### 6. Frontend smoke (browser)

1. **Internal**: log in as a `system_admin` → lands on `/internal/home` (not `/internal/applications`). InternalLayout sidebar shows Home/Applications/Partners/Deals/Users/Program Config/Reports — Partners/Users/Program Config/Reports rendered as greyed "soon" placeholders. KPI tiles populate; "Open Conflicts" pulses red if > 0; clicking "Review Applications" navigates to the queue.
2. **Internal**: as a `channel_manager`, confirm Users is hidden (system_admin-only) and the rest of the visible items are unchanged.
3. **Partner**: log in as a `partner_admin` → `/portal/home` shows the new KPI tile row, activation widget (or green "Activated ✅" banner), and Recent Deals table. "Info Required" tile pulses red if > 0. Click a deal in the Recent Deals table → opens `/portal/deals/:id`.
4. **Cancel Info Request**: open an `info_required` application via `/internal/applications/<id>`. The "Cancel Info Request" button is visible (only in this status). Click it → confirm modal → on confirm the button disappears and the badge flips to "In Review".
5. **Cancel Info Request**: same for a deal at `/internal/deals/<id>` — modal copy matches "Cancel the info request?" and "Info request cancelled by reviewer." appears as a new system message in the thread.

### Known operational notes (Sprint 11)

- **`InternalLayout` is a hard cut-over.** All `/internal/*` routes now resolve through the layout. If a future route lands without being added to the nested `<Route path="/internal">` block in `App.jsx`, the page will 404 — there is no longer a "bare" internal route variant.
- **Login destination for internal users is `/internal/home`.** A redirect to `/internal/applications` no longer happens out of `Login.jsx`. Any link or doc that explicitly references the post-login destination should now point at `/internal/home`.
- **`PartnerApplication.info_request_message` is in-memory only.** The cancel-info-request endpoint reads it with `getattr(..., None)`. Tests that exercise this endpoint must set the attribute *after* row construction (the SQLAlchemy constructor rejects unknown kwargs). See `test_cancel_info_request.py::_make_application`.
- **Aggregate-count test files require per-test table cleanup.** `test_dashboard.py` and `test_partner_dashboard.py` use a module-scoped engine but truncate all tables in the `db_session` fixture teardown — otherwise prior tests' rows inflate counts. Any future "count things in the DB and assert" test should follow that pattern.
- **Dashboard endpoints are query-side aggregates.** `GET /internal/dashboard/summary` and `GET /partners/{id}/dashboard/summary` run multiple count queries per call. If the deals or applications tables grow large enough that the dashboard becomes slow, the right move is index review (status, partner_org_id, reviewed_at) before introducing a roll-up table.

---

## 15. End-to-End Happy Path Validation — Phase 4 (Admin Foundation & Reporting)

Run this after Sprint 14 closes. It exercises every Phase 4 deliverable: internal user management, partners list, status management, program config, reporting, and partner pipeline view.

Use Command Prompt (`cmd`) for curl with `%token%`.

### Step 1 — Internal user management (Sprint 12)

Get a `system_admin` JWT per § 2. Then:

```cmd
set token=<system_admin token>

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/users" -H "Authorization: Bearer %token%"
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/users/invite" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"email\":\"new-cm@example.com\",\"full_name\":\"New CM\",\"role\":\"channel_manager\"}"
```

Expect `200` from GET (paginated `{total, items, …}`) and `201` from invite (new user record + a stdout/email line with the reset URL).

### Step 2 — Partner org status management (Sprint 13 / FPRM-208)

```cmd
curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/internal/partners/<partner_id>/status" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"status\":\"suspended\"}"
```

Expect `200` with the new status. `applicant` returns `400`.

### Step 3 — Program configuration (Sprint 13)

```cmd
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/config/approval-steps" -H "Authorization: Bearer %token%"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/config/tiers" -H "Authorization: Bearer %token%"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/config/activation-criteria" -H "Authorization: Bearer %token%"
```

Each returns a populated list (2 approval-step seeds, 3 tier seeds, 6 activation-criterion seeds).

### Step 4 — Internal reporting (Sprint 14 / FPRM-221)

```cmd
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/reports/pipeline" -H "Authorization: Bearer %token%"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/reports/cycle-times" -H "Authorization: Bearer %token%"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/reports/conflicts" -H "Authorization: Bearer %token%"
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/reports/partner-activity" -H "Authorization: Bearer %token%"
```

Each returns its documented shape (see PROJECT_CONTEXT.md §1). On an empty database, `/pipeline` returns `{by_partner: [], by_category: [], by_tier: [], totals: {…all zeros…}}`.

CSV export (note the redirect-free output):

```cmd
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/reports/pipeline/export" -H "Authorization: Bearer %token%" -o pipeline_export.csv
```

Expect `pipeline_export.csv` to contain the header `Partner Name,Category,Tier,Deal Name,Customer Name,Deal Value,Status,Submitted Date,Approved Date,Commission Rate` on the first line.

### Step 5 — Partner pipeline (Sprint 14 / FPRM-229)

Get a `partner_admin` JWT for an active partner org per § 2. Then:

```cmd
set ptoken=<partner_admin token>

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/<partner_org_id>/pipeline" -H "Authorization: Bearer %ptoken%"
```

Expect `200` with 6 keys (`draft`, `submitted`, `under_review`, `info_required`, `approved`, `rejected`). Hitting another org's id returns `403`. Calling the same endpoint with a `system_admin` token returns `403` — internal users use `/internal/reports/pipeline` instead.

### Step 6 — UI checklist

Open `https://fracttal-prm-frontend-production.up.railway.app`:

1. **Internal**: log in as `system_admin` → land on `/internal/home`. Sidebar shows Home/Applications/Partners/Partner Users/Deals/Users/Program Config/**Reports** — **Reports is live (no `soon` chip)**.
2. **Internal**: click **Program Config** — three tabs render (Approval Workflow / Partner Tiers / Activation Checklist), each populated with the seed data.
3. **Internal**: click **Reports** → `/internal/reports`. Three sections render (Pipeline Overview / Cycle Times / Conflict Report). Change the date preset → tiles + chart + table refetch. Click **Export CSV ↓** → browser downloads `pipeline_export.csv` (not a 401).
4. **Partner**: log in as a `partner_admin` → `/portal/home`. The new **My pipeline** widget shows 4 compact tiles + `View Pipeline →`. Click it → land on `/portal/deals?view=pipeline`. Kanban view shows 6 columns, each with a count badge + total value. Click the **List ☰** toggle → existing deal table renders.
5. **Partner**: change the status filter → both views re-fetch and update.

### Known operational notes (Sprint 14)

- **Report endpoints aggregate at query time (AD-17).** All counts are computed inline from the live `deal_registrations` table. Acceptable through Phase 5.
- **CSV export uses fetch + Blob (AD-16).** `window.location.href` cannot send the Authorization header — would 401. Tests that simulate CSV download must mirror this pattern.
- **`/partners/{id}/pipeline` is partner_admin only by design.** System admins seeking the same data go to `/internal/reports/pipeline` (which has broader aggregation).
- **recharts is now a frontend dependency.** Future chart additions should reuse recharts components and the existing `PALETTE` palette in `InternalReports.jsx`. No other charting library is allowed.

---

## 16. End-to-End Happy Path Validation — Phase 5 (Quoting Module & Enforcement)

Run after Railway deploys catch up (migrations 023–026 + Sprint 15–18 code). All Phase 5 happy paths exercised end to end.

Use Command Prompt (`cmd`) for curl with `%token%`.

### Step 1 — Confirm migrations + pricing catalogue seed

```
curl https://fracttal-prm-backend-production.up.railway.app/health
REM Expect: {"status":"ok","service":"fracttal-prm-backend","database":"connected"}

set token=<system_admin token>

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/config/pricing/plans" -H "Authorization: Bearer %token%"
REM Expect: 3 rows (starter / professional / enterprise) with feature_pack_annual / transactional_user_annual / limited_tech_user_annual

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/config/pricing/addons" -H "Authorization: Bearer %token%"
REM Expect: 21 rows from the add-on catalogue
```

### Step 2 — Create a quote on an existing deal

```
REM Get a partner_admin token for an org with at least one approved deal (see §3)
set ptoken=<partner_admin token>

REM Pick a deal id from /deal-registrations
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/deal-registrations" -H "Authorization: Bearer %ptoken%"
set deal_id=<id from above>

curl -X POST "https://fracttal-prm-backend-production.up.railway.app/deals/%deal_id%/quotes" -H "Authorization: Bearer %ptoken%" -H "Content-Type: application/json" -d "{\"feature_plan\":\"enterprise\",\"qty_transactional_users\":5,\"qty_limited_tech_users\":25,\"currency_code\":\"USD\"}"
REM Expect: 201 + active_version_data with grand_total_after_discount ~ 16608.00 (Sprint 15 spec example 1)
set quote_id=<id from response>
```

### Step 3 — Scenario management (Sprint 18 / FPRM-283)

```
REM Add two more versions labelled good / best
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/versions" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"feature_plan\":\"starter\",\"qty_transactional_users\":5,\"qty_limited_tech_users\":25,\"scenario_label\":\"good\"}"
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/versions" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"feature_plan\":\"professional\",\"qty_transactional_users\":5,\"qty_limited_tech_users\":25,\"scenario_label\":\"better\"}"

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/scenarios" -H "Authorization: Bearer %ptoken%"
REM Expect: scenarios array length >= 2 in canonical order; active_scenario possibly null until PATCH

curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/active-scenario" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"scenario_label\":\"better\"}"
REM Expect: 200 with active_scenario=better
```

### Step 4 — PDF generation + download (Sprint 16)

```
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/versions/1/generate-pdf" -H "Authorization: Bearer %token%"
REM Expect: {"pdf_filename":"quote-...","pdf_generated_at":"..."}

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/versions/1/pdf" -H "Authorization: Bearer %token%" -o quote_v1.pdf
REM Expect: quote_v1.pdf written; open and inspect — header, line-item table, totals, currency symbol
```

### Step 5 — CSV exports (Sprint 16 / AD-20)

```
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/deals?export=csv" -H "Authorization: Bearer %token%" -o deals_export.csv
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/partners?export=csv" -H "Authorization: Bearer %token%" -o partners_export.csv
REM Expect: text/csv body with header row in first line for each
```

### Step 6 — Dynamic activation criteria (Sprint 17 / FPRM-270)

```
set partner_id=<partner_org_id>
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/%partner_id%/activation/criteria" -H "Authorization: Bearer %token%"
REM Expect: {required_criteria:[{criterion_key,description,is_met}], activation_complete, config_source}
REM config_source is "dynamic" if an activation_checklist_config row matches the partner's category/tier, else "fallback"
```

### Step 7 — Multi-step approval enforcement (Sprint 17 / FPRM-274)

```
REM Confirm a partner application's approval_progress when at least one approval_workflow_steps row exists for partner_application
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/applications/<app_id>" -H "Authorization: Bearer %token%"
REM Expect: GET response includes approval_progress {total_steps, completed_steps, current_step_order, current_step_name, current_required_role}

REM A user whose role does NOT match current_required_role should receive 403 on POST /approve
```

### Step 8 — Internal quote dashboard (Sprint 18 / FPRM-287)

```
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/quotes" -H "Authorization: Bearer %token%"
REM Expect: {items:[...], total:N, page:1, page_size:20, summary:{total_quotes, draft, sent, accepted, expired, pipeline_total}}

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/quotes?status=sent" -H "Authorization: Bearer %token%"
REM Expect: items filtered to sent only

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/quotes?search=Acme" -H "Authorization: Bearer %token%"
REM Expect: items where quote_name OR deal_name contains "Acme"
```

### Step 9 — Partner quote history (Sprint 18 / FPRM-291)

```
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/%partner_id%/quotes" -H "Authorization: Bearer %ptoken%"
REM Expect: 200 with items for that partner's quotes

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/partners/%partner_id%/quotes" -H "Authorization: Bearer %token%"
REM Expect: 403 with detail mentioning /internal/quotes (internal users are blocked here)
```

### Step 10 — UI browser checklist

Open https://fracttal-prm-frontend-production.up.railway.app:

1. **Internal as system_admin** → sidebar shows new **Quotes** item between Deals and Users; click → `/internal/quotes` renders summary cards + filter row + paginated table. Filters re-fetch on change; row link opens the linked deal.
2. **Internal deal detail** → header shows the new quote chip (status + version + grand total) next to the Commission/Partner chips, or a dashed "No quote yet" chip when none exists.
3. **Internal QuoteDetail** → when 2+ versions have scenario labels, the Scenario Comparison panel renders between Versions and Line Items. "Select This Option" PATCHes /active-scenario + /active-version and refreshes; ⭐ marker moves to the selected card.
4. **Partner portal** → sidebar shows **My Quotes** between Commissions and the disabled Training item; click → `/portal/quotes` renders the filterable table.
5. **Partner DealDetail** → when the quote has `active_scenario`, the PortalQuoteSection shows the "Your recommended option: …" badge; when 2+ scenarios exist, a read-only scenario-tab row appears.
6. **Currency formatting** — change quote currency in the form (USD → EUR) for a *new* quote and confirm the symbol changes everywhere it renders (live preview, detail view, portal section).

### Known operational notes (Phase 5)

- **No FX conversion (AD-23).** `currency_code` is a display label; numeric totals do not convert. Partners requesting EUR vs USD comparisons see the same numbers with a different symbol.
- **Scenario / version are independent (AD-24).** Internal users can move the active version separately from the active scenario; the partner-facing "Select This Option" CTA keeps them in lock-step for the common case.
- **PDF artefacts stored as base64 on the row (AD-19).** Surviving Railway redeploys does NOT depend on persistent disk. Regenerating overwrites idempotently.
- **All authenticated downloads use fetch+Blob (AD-20).** Anchor `href` or `window.location.href` would 401 on JWT-only endpoints.
- **Pricing seeds are migration-time.** Migration 023 inserts 30 rows via `WHERE NOT EXISTS`. Empty pricing means the migration didn't run — first place to check on any "quote engine returns 0" report.

---

*Phase 5 complete: Sprint 18 closeout — May 2026.*

---

## 17. End-to-End Happy Path Validation — Phase 6 Post-Sprint-20 (UX & Workflow Fixes, PRs #128–#163)

Run this after the post-Sprint-20 UX & workflow fixes session deploys settle on Railway. Exercises the four workflow capabilities added on top of Sprint 20: manual conflict-check rerun, Commission Rates admin tab, Deal Won with accepted-quote requirement, and quote document upload + acceptance gate.

Use Command Prompt (`cmd`) with `%token%`. Substitute `<CHANNEL_MGR_TOKEN>` with a token for `cmtest@test.com` (channel_manager, from §2) and `<ADMIN_TOKEN>` for `admin2@test.com` (system_admin).

### Step 1 — Manual conflict-check rerun

Pick a deal whose `conflict_status` is stale or wrong (e.g. flipped to `clear` before a competing deal was registered). As an internal reviewer:

```cmd
set itoken=<CHANNEL_MGR_TOKEN>

curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/<DEAL_ID>/conflict-check" -H "Authorization: Bearer %itoken%"
```

Expect `200` with the recomputed `conflict_status` + `conflict_checked_at` + `conflict_notes`. Confirm via `GET /deal-registrations/<DEAL_ID>` that the timestamp moved. Audit log gains a `deal_registration.conflict_rechecked` event. A `partner_admin` token must return `403`.

### Step 2 — Commission Rates admin tab

```cmd
set token=<ADMIN_TOKEN>

curl -X GET "https://fracttal-prm-backend-production.up.railway.app/internal/config/commission-rates" -H "Authorization: Bearer %token%"
```

Expect `200` with the active rows from `commission_structures` (24 seeded rows minimum, post-Sprint-20 admin edits on top). Each item now carries `is_active`, `created_at`, `updated_at` (migration 031).

```cmd
REM Create a new rate
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/config/commission-rates" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"partner_category_code\":\"reseller\",\"commission_type\":\"co_sell_shared\",\"year\":\"year_2_plus\",\"commission_pct\":15.0,\"notes\":\"Phase 6 validation rate\"}"
REM Capture the returned id as %rate_id%

REM Update it
curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/internal/config/commission-rates/<rate_id>" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"commission_pct\":18.0}"

REM Soft delete (system_admin only)
curl -X DELETE "https://fracttal-prm-backend-production.up.railway.app/internal/config/commission-rates/<rate_id>" -H "Authorization: Bearer %token%"
```

Expect `201` / `200` / `204`. A `channel_manager` token must return `403` on POST and DELETE. The frontend `/internal/program-config` page shows the new **Commission Rates** tab with the seeded + ad-hoc rows; filtering by `is_active=false` surfaces the soft-deleted rate from the DELETE above.

### Step 3 — Deal Won flow with accepted-quote requirement

Pick an approved deal that has at least one quote.

```cmd
set deal_id=<APPROVED DEAL ID with at least one quote>
set quote_id=<QUOTE ID on that deal>

REM Attempt won without accepted quote (should fail)
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/%deal_id%/won" -H "Authorization: Bearer %token%"
```

Expect `422` with detail mentioning "at least one accepted quote required". Now accept a quote:

```cmd
REM Move quote to sent then accepted (requires a signed_acceptance document — see Step 4 first if the quote has no document)
curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/status" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"status\":\"sent\"}"
curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/status" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"status\":\"accepted\"}"

REM Retry won
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/internal/deals/%deal_id%/won" -H "Authorization: Bearer %token%"
```

Expect `200` with deal status `won`. Confirm via `GET /deal-registrations/%deal_id%` that any *other* non-terminal quote versions on the deal are now `cancelled` (cascade behaviour). Audit log gains `deal_registration.won` plus one `quote.cascade_cancelled` per cancelled quote.

### Step 4 — Quote document upload + acceptance gate

Pick a quote currently in `sent` status without a `signed_acceptance` document.

```cmd
set quote_id=<SENT QUOTE ID>

REM Confirm acceptance is currently gated
curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/status" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"status\":\"accepted\"}"
```

Expect `422` with detail mentioning the missing `signed_acceptance` document.

```cmd
REM Upload a signed_acceptance document (base64-encode a small PDF first)
REM PowerShell oneliner to base64-encode: [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\path\to\acceptance.pdf"))
curl -X POST "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/documents" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"document_type\":\"signed_acceptance\",\"document_name\":\"acceptance.pdf\",\"file_data_base64\":\"<BASE64>\",\"mime_type\":\"application/pdf\",\"file_size_bytes\":12345}"

REM List + download to verify the round-trip
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/documents" -H "Authorization: Bearer %token%"
set doc_id=<id from previous GET>
curl -X GET "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/documents/%doc_id%/download" -H "Authorization: Bearer %token%" -o acceptance_roundtrip.pdf
```

Expect `201` upload, `200` list with one item (no base64 blob in the list response), `200` download with the original MIME and `Content-Disposition: attachment` header. Open the downloaded PDF to confirm it matches the source.

```cmd
REM Now the acceptance gate clears
curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/status" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"status\":\"accepted\"}"
```

Expect `200` with status `accepted`. Audit `quote_document.uploaded` + `quote.status_changed`.

```cmd
REM Optional: retract test (system_admin only)
curl -X PATCH "https://fracttal-prm-backend-production.up.railway.app/quotes/%quote_id%/status" -H "Authorization: Bearer %token%" -H "Content-Type: application/json" -d "{\"status\":\"sent\"}"
```

Expect `200` (admin) — `accepted → sent` retract. A `channel_manager` token must return `403` on the same retract call.

### Step 5 — Frontend smoke (browser)

1. **Internal as channel_manager (cmtest)** → `/internal/deals/<id>` shows a "Re-run Conflict Check" button in the Conflict Check card; click → confirm toast + refreshed timestamp.
2. **Internal as system_admin** → `/internal/program-config` shows a new **Commission Rates** tab between the existing program-config tabs; rows list with edit / soft-delete affordances.
3. **Internal as system_admin** → `/internal/deals/<id>` on an approved deal with no accepted quote shows the **Mark as Won** button disabled with a tooltip explaining the accepted-quote requirement.
4. **Internal as system_admin** → `/internal/deals/<id>` quote modal shows the new **Documents** section; upload a PDF; refresh and confirm the entry persists with a Download action.
5. **Internal as system_admin** → on an `accepted` quote, the **Retract to Sent** action is visible (system_admin only); confirm it disappears for cmtest.
6. **Partner portal** → `/portal/deals/<id>` shows the redesigned header: **Pipeline Value** badge + **Quote Accepted** chip when applicable; Sortable column headers on `/portal/deals` (List view) honour ↕/↑/↓ glyphs.
7. **Pipeline toggle** → on `/internal/deals/<id>` quote modal, toggle the **Include in Pipeline** checkbox; refresh `/internal/quotes` and confirm the Pipeline column updates.

### Known operational notes (post-Sprint-20)

- **The acceptance gate is router-side.** The `quote_documents` table itself has no constraint linking documents to quote status. The router-level check is in `quotes_router.py` on the `PATCH /quotes/{id}/status` happy path. Future bulk-import paths must replicate the gate or bypass it explicitly.
- **`accepted → sent` retract is system_admin only by design.** Opening it to channel_manager would invite accidental retract on partner-facing approvals. Keep this scope narrow — it is a break-glass operation.
- **`POST /internal/deals/{id}/won` cascade-cancels every non-terminal quote on the deal.** Reviewers should verify the *correct* quote is `accepted` before calling /won — the cascade is irreversible without a system_admin retract on each cancelled quote.
- **`/internal/config/commission-rates` is admin-maintained per AD-25.** No Alembic migration is required to add, deactivate, or adjust commission percentages. The quote engine continues to read rates live from `commission_structures` (AD-18 corollary).
- **Conflict re-check is best-effort, same as submit-time.** A `conflict_checker` raise is caught and logged; the response still returns 200 with whatever conflict state survived. Monitor Railway backend logs after any deploy touching `conflict_checker.py`.

---

## Sprint 21 operational notes — Centralised Document Repository (2026-05-27)

**Migration head:** 033 → **036**. Migrations 034 (extend `partner_documents` with
`file_data`), 035 (create `document_references`), 036 (backfill + drop
`quote_documents`).

- **Where do quote acceptance files live now?** In `partner_documents`. The
  `quote_documents` table no longer exists post-migration 036. If a quote shows
  as missing its acceptance evidence after deploy, check the join:
  `SELECT * FROM document_references WHERE entity_type='quote' AND entity_id=<quote_id>`.
- **`file_data` is never returned in list / metadata / patch responses by
  design (AD-33).** Use the dedicated `GET /partners/{id}/documents/{doc_id}/download`
  endpoint to retrieve binary content. If a client appears to lose file content,
  check the request path -- a list-endpoint response will never include bytes.
- **The acceptance gate now requires `status='approved'` on the underlying
  document.** Uploading a doc and creating a reference is not enough -- an
  internal user must approve the document (PATCH status=approved) before the
  quote can transition to accepted. This is intentional (a pending review is
  not yet evidence) and is a behaviour change vs Sprint 20.
- **`/internal/quotes/export` is the canonical CSV export for the internal
  quote dashboard** (closes the Sprint 16 TODO). It mirrors the filter surface
  of `GET /internal/quotes` so the same view round-trips to CSV. Partner-side
  `GET /partners/{id}/quotes?export=csv` now also includes a `Deal Status`
  column -- if a downstream consumer parses by column position, update them.
- **Four legacy quote-document endpoints (`POST`, `GET`, `GET .../download`,
  `DELETE` under `/quotes/{quote_id}/documents`) have been removed.** Any
  external consumer must switch to the centralised path
  `/partners/{partner_id}/documents/...` plus references.
- **Jira token in `.env` is currently 401.** The Sprint 21 Phase A (fix
  version + native sprint + 5 stories) was therefore not auto-created; rotate
  the token at id.atlassian.com before the next sprint so the prompt
  template's API path works again. The PR for Sprint 21 uses a placeholder
  `FPRM-AD33` slug instead of a concrete story key.

---

*Post-Sprint-20 UX & Workflow Fixes complete: PRs #128–#163 — 2026-05-22.*

*Frontend fix session 2026-05-26: AD-33 centralised document repository decision recorded; CI trigger extended to docs/** branches (PR #170); design standardisation pass A completed (PRs #171–#173); PROMPT_TEMPLATE.md created as new canonical document; Fix PR B1 (PR #174): draft quote lock bug fixed, portal/quotes modal restored, Approved→Accepted rename completed; Fix PR B2 (PR #175): backend date filter bug fixed. Fix PR C (PR #176): DealQueue.jsx redesign, Won card dollar value, Accepted Pipeline label, InternalHome Accepted label. Fix PR D (PR #177): DealQueue full-width layout, date filter wiring fixes on both deal pages. Fix PR E (PR #178): GET /internal/deals date filter backend fix (+4 tests, 719→723). Pre-Sprint-21 UI testing session fully complete.*

*Sprint 21 (2026-05-27): Centralised document repository implementation — migrations 034–036, 10 new endpoints, 4 legacy quote-document endpoints retired, 738 tests (up from 723).*

---

## Sprint 21 Hotfix operational notes (2026-05-27)

- **If "Mark as Accepted" fails silently:** check that a `document_references`
  row exists with `entity_type='quote'` and `entity_id=<quote_id>` linked to a
  non-deleted `partner_documents` row. The Sprint 21 hotfix (FPRM-353)
  **removed** the `status='approved'` requirement on the partner document --
  the attachment itself is sufficient evidence. If the gate is still firing,
  query both tables directly to confirm the row chain is intact.
- **`/internal/quotes` payload includes `deal_status` per row** (Sprint 21
  hotfix FPRM-357). External consumers that parse by column position should
  re-index.
- **Document attachment from a quote offers two paths in one panel**
  (Upload New / Pick Existing). Pick Existing only creates a
  `document_references` row -- the underlying `partner_documents` row is
  unchanged. Removing the attachment from the quote (the Delete button on
  the attached-docs list) removes the reference only; the underlying file
  survives for use on other quotes / deals / records.

---

*Sprint 21 Hotfix (2026-05-27): FPRM-353/354/355/356/357 -- acceptance gate relaxed (no longer requires approved status), QuoteDetail document section gains Pick Existing tab, internal partner-documents page uses full-width layout, deal_status surfaced on `/internal/quotes` and rendered in both quotes tables. +2 tests (738 → 740).*

---

## Sprint 22 operational notes — Document Repository v2 (2026-05-27)

**Migration head:** 036 → **038**. Migrations 037 (`document_versions` table + `partner_documents.current_version_number` / `version_count` + backfill of v1 from existing `file_data`), 038 (`document_type_rules` table + seed `quote_acceptance` / `contract`).

- **Where do uploaded bytes live now?** In `document_versions.file_data`, one
  row per version, exactly one with `is_current=true`. The
  `partner_documents.file_data` column is **deprecated** (AD-34) and not
  written by new code. If a download returns unexpected content, check the
  join:
  `SELECT * FROM document_versions WHERE document_id=<doc_id> AND is_current=true`.
  An empty result means the row has not been migrated yet — the legacy
  fallback in the download endpoint reads `partner_documents.file_data`
  as a safety net for any straggler.
- **Approval workflow rules.** Seeded defaults (migration 038):
  `quote_acceptance` — auto-approve / no manual step;
  `contract` — requires approval.
  Admins manage further rules via Program Config → **Document Rules**
  (system_admin only). The acceptance gate in `quotes_router.py` reads
  `document_type_rules.requires_approval` at runtime, so policy flips
  take effect immediately on the next quote PATCH.
- **Auto-approve forces "no manual approval".** The Document Rules
  modal couples the two booleans: setting `auto_approve = true` zeroes
  `requires_approval`. The backend silently does the same coercion if a
  direct API caller submits both true.
- **Partner self-service delete** (`partner_admin` role on own org) is
  available on the portal Documents page. The endpoint returns 409 if any
  `document_references` row points at the document — the partner must
  remove the document from every quote before deleting. Hard-delete by
  `channel_ops_admin` / `system_admin` (which removes all references too)
  is unchanged.
- **Preview vs download.** `/preview` returns `Content-Disposition: inline`
  for PDF + common image MIME types; everything else falls back to
  `attachment`. The portal Documents table shows a "Preview" button only
  when the MIME type is in the inline-supported set.
- **Versioning — revert is internal-only.** Channel managers /
  channel_ops_admin / system_admin can roll a document back to a previous
  version; partner_admin cannot self-revert (audit trail preservation).
  The previous current version is NOT deleted — both rows survive.
- **Uploaded By column.** The list response includes `uploaded_by_name`
  (User.full_name with email fallback). Historical rows with
  `uploaded_by_user_id IS NULL` return `null`.

---

*Sprint 22 (2026-05-27): Document Repository v2 — migrations 037/038, 9 new endpoints, AD-34 deprecation of partner_documents.file_data, versioning UI on portal + internal, Document Rules admin tab. +25 tests (740 → 765).*

*Sprint 22 hotfix #2 (2026-05-29, FPRM-386, PR #183): case-insensitive + whitespace-trimmed document_type_rules matching on upload — a free-text rule entered as `NDA` now governs uploads of the lowercase code `nda`; rule-create dedupe is case-insensitive. +3 tests (766 → 769).*

*RUNBOOK created: May 2026*
*Sources: Sprint 1–3 Console Dialog, Sprint 4 Console Dialog, Sprint 5–22 closeout, Sprint 21 hotfix, Sprint 22 hotfix #2.*
*Sprint 23 PR A (2026-05-29, PR #185): migration 039 (dual-table document-type seed/reconcile); partner self-accept own quotes (AD-35); partner_admin version revert (AD-36); 25 MB upload size cap replaces type allowlist (AD-37); two-table document model (AD-38). +17 tests (769 → 786).*

*Sprint 23 PR B (2026-05-29, PR #186): Asset Library — migration 040 (asset_categories, assets, asset_download_logs); base64 storage + 10 MB cap (AD-39); /assets + /internal/assets endpoints; PortalAssets ("Resources") + InternalAssets ("Assets") pages. +13 tests (786 → 799). Sprint 23 closed (PR A #185 + PR B #186).*

*Last updated: 2026-05-30 — docs PR: Phase 6 Backlog / Sprint Candidates section added to CLAUDE.md (PR #PRNUM).*
*Update this file whenever a new operational lesson is learned — do not let lessons live only in console dialogs.*
