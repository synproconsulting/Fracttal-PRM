# Fracttal PRM — Project Context

> This file is the single source of truth for Claude Code and Claude chat sessions.
> Load it at the start of every session to restore full project context.

> Sprint history lives in CLAUDE_HISTORY.md (created at first sprint closeout)

---

## What This Project Is

A new Partner Relationship Management (PRM) system to onboard and manage Fracttal system resellers and implementation partners. Built and maintained by an AI-powered Virtual Development Team using Claude Code as the Dev Agent, a rule-based auto-merger as the Manager Agent, and direct Jira REST API calls for sprint setup.

**Owner:** Johan Wessels — SynPro Consulting
**Started:** May 2026
**Current state:** **Sprint 22 — Document Repository v2 — complete.** Sprint 22 takes the centralised document repository to its production-ready form. Migration **037** creates `document_versions` (one binary row per version, `is_current` flag) and adds `current_version_number` + `version_count` denormalised pointers to `partner_documents`; the migration backfills every existing row that had `file_data` into a v1 row. Migration **038** creates `document_type_rules` with seed rows `quote_acceptance` (auto-approve, no manual approval) and `contract` (requires approval). Alembic head moves from 036 → **038**. **AD-34** records the new rule: `partner_documents.file_data` is deprecated, all new bytes live in `document_versions.file_data`. The upload, download, and preview endpoints all read from `document_versions where is_current=true`. Nine new endpoints: per-document version upload/list/download/revert (internal only) + preview + `/admin/document-type-rules` CRUD. The acceptance gate now consults the rule table — `requires_approval` controls whether `PartnerDocument.status='approved'` is required (preserves the FPRM-353 hotfix behaviour for `quote_acceptance` via the seed). Frontend: portal Documents page gets version badge + inline history panel + new-version modal + preview button + partner self-service delete + Uploaded By column; QuoteDetail Pick Existing tab shows version badges; ProgramConfig has a system_admin-only Document Rules tab; the quote attach panel shows gate-info hints based on the rule. **A post-Sprint-22 hotfix (FPRM-383/384/385) refined three behaviours:** partner-admin self-service delete now *permanently* removes an unreferenced document (versions cascade) instead of soft-flagging it `rejected`; the upload status default flipped so a document type with **no** governing `document_type_rules` row is **auto-approved** (`requires_approval=true` rules still land `pending_review`); and the document-type-rule delete endpoint no longer 409s when documents of that type exist — rules are freely deletable, existing docs keep their status. **A follow-up hotfix (FPRM-386, PR #183)** made `document_type_rules` matching **case-insensitive + whitespace-trimmed**: the free-text Document Rules form had let an admin store a rule as `NDA` while uploads send the lowercase code `nda`, so the exact-match lookup missed and `requires_approval` docs were silently auto-approved; the lookup is now normalised on both sides and the rule-create duplicate check is case-insensitive. **786 backend tests passing.** **Last PR merged: #185** — **Sprint 23 PR A** (Sprint 22 carry-forward, migration **039**). Migration head moves 038 → **039** (data-only: seeds the canonical KYC + contract document types into BOTH `document_types` (vocabulary) and `document_type_rules` (approval policy), and reconciles every in-use type). Carry-forward items closed: data-driven document types + universal approval gate on every upload path (case-insensitive, FPRM-386); Program Config → Document Rules type **dropdown** + "Requires Approval" label; **partner self-accept** — `partner_user`/`partner_admin` may attach proof-of-acceptance and mark their own-org quote `accepted` (AD-35); **partner_admin version revert** for own-org docs with confirm + `document.version_reverted` audit (AD-36, supersedes FPRM-374); uploaded-by name in the version panel; **upload size cap (25 MB)** replaces the file-type allowlist (AD-37). Two-table document model recorded as **AD-38**. The earlier #184 docs PR established the **Phase 7 Backlog** section (Dynamic RBAC anchor). **Sprint 23 PR B — Asset Library — complete (PR #186, migration 040).** Migration head moves 039 → **040** (creates `asset_categories`, `assets`, `asset_download_logs`). New `assets_router` adds the partner portal list + download and the internal asset/category management endpoints; binaries are stored base64 in `assets.file_data` and `file_data` is never returned by any list endpoint — only the download endpoint streams decoded bytes (**AD-39**, the AD-17/19/20 pattern). 10 MB cap on asset upload (independent of the 25 MB partner-documents cap). Visibility is `all` | `tier:<tier>` | `category:<code>`, enforced on the partner list + download. Frontend: portal **Resources** page (`PortalAssets.jsx`, card grid + filter + download) and internal **Assets** page (`InternalAssets.jsx`, upload/edit/activate + download-log drill-down + category management). **799 backend tests passing.** **Last PR merged: #PRNUM** (docs PR — added the Phase 6 Backlog / Sprint Candidates section). **Sprint 23 fully closed (PR A #185 + PR B #186).** Channel manager test user `cmtest@test.com / TestPass123!`. Phase 6 epic **FPRM-299** — Pricing Admin, Services Quote & Partner Enablement. Sprint history in CLAUDE_HISTORY.md.

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

**Every Claude Code session must end with a post-flight sync after the final PR merges.** After the closeout report prints and the final PR is confirmed merged to `main`, execute this sequence before exiting:

```cmd
cd "C:\Johan\SynPro Consulting\Fracttal PRM"
git fetch origin
git reset --hard origin/main
git clean -fd --exclude=Documentation/
```

This ensures the local working tree reflects the merged state on `origin/main` exactly, discards all session working files, and leaves the repo in a clean state for the next session. The post-flight sync is not optional — a session that ends without it leaves stale files that corrupt the next session's pre-flight read.

**Canonical docs must travel in the same PR as the code change that caused them.** CLAUDE.md, CLAUDE_HISTORY.md, PROJECT_CONTEXT.md, and RUNBOOK.md must be updated in the same branch and same PR as the implementation change. No deferred docs PRs. No separate reconciliation sessions. The rule is: if a PR changes behaviour, schema, endpoints, or components, it is incomplete until the four canonical docs reflect it. The auto-merger merging the PR is the moment the docs should already be current — not after.

This applies to every PR type: feature, fix, and docs. The only exception is a pure docs PR that corrects docs without any accompanying code change (e.g. adding an AD entry).

**Claude chat must follow `PROMPT_TEMPLATE.md` when generating Claude Code prompts.** This file defines the mandatory structure (pre-flight sync, zero-PR check, canonical doc reads, source file reads, implementation, docs update, PR rules, closeout report, post-flight sync) that every prompt must contain. It governs Claude chat as prompt author; CLAUDE.md governs Claude Code as Dev Agent. No duplication — different audiences, different purposes.

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

### AD-25 · Pricing catalogue is admin-maintainable
After Sprint 19, all pricing changes (plan prices, volume discount tiers, add-on catalogue) are data operations via the `/internal/config/pricing/*` admin API — never write a new Alembic migration to change a price. The quote engine reads pricing live from the DB at runtime (per AD-18) so changes take effect immediately for all new quotes; existing quote versions are not recalculated.

### AD-16 · Authenticated CSV downloads use fetch + Blob, never `window.location.href`
CSV and authenticated file downloads use `fetch` with `Authorization: Bearer`, `response.blob()`, `URL.createObjectURL`, and a temporary `<a>` click. Tokens in URLs leak via referrer and logs.

### AD-17 · Report aggregations are computed at query time, not pre-aggregated
`/internal/reports/*` endpoints compute all metrics inline from live rows. No pre-aggregated rollup tables exist. Acceptable through Phase 5; revisit if deal volumes exceed ~50k.

### AD-18 · `quote_engine.calculate_quote` is the single source of truth for software pricing
All Fracttal pricing arithmetic lives in `backend/quote_engine.py` — a pure module with no FastAPI imports. The router is the only caller; it converts `ValueError` to HTTP 422. Never inline pricing in a router.

### AD-19 · PDF artefacts are stored as base64-encoded text on the DB row
Generated quote PDFs are stored in `quote_versions.pdf_artifact_data` (Text column, base64). Railway has no persistent local storage across deploys; DB storage keeps PDFs durable and atomically tied to their `QuoteVersion`.

### AD-20 · Authenticated file downloads use fetch + Blob + `URL.createObjectURL`
Same pattern as AD-16 — codified as the canonical standard for every authenticated download (CSV, PDF, quote documents).

### AD-21 · Dynamic activation criteria resolved at runtime from `activation_checklist_config`
`recalculate_activation` derives required criteria by querying `activation_checklist_config` for the partner's category + tier. Falls back to the hardcoded four-flag rule when no config rows match. Never re-hardcode criterion lists in a router.

### AD-22 · Multi-step approval enforcement reads `approval_workflow_steps` at runtime
`POST /applications/{id}/approve` and `POST /internal/deals/{id}/approve` are step-gated. Shared helpers in `backend/approval_helpers.py`. Single-step legacy behaviour preserved when no steps are configured. system_admin satisfies any `required_role` as a break-glass bypass.

### AD-23 · Multi-currency display is render-time formatting; numeric storage is currency-agnostic
`quotes.currency_code` is a display label only. All monetary columns store plain `Numeric`. `frontend/src/utils/currency.js` `formatCurrency(amount, code)` applies the symbol at render time. No FX conversion.

### AD-24 · Quote scenario selection is independent of version selection; latest version per label wins
`quotes.active_scenario` and `quotes.active_version` are independent fields. `GET /quotes/{id}/scenarios` groups versions by `scenario_label` and returns the highest-numbered version per label.

### AD-26 · Filter bar layout standard
All list pages render filters in a single horizontal `fp-card` filter bar: dropdowns LEFT, search RIGHT, actions FAR RIGHT. Never stack filters vertically. Reference: `InternalQuotes.jsx`.

### AD-27 · Status badge style standard
All status badges use a tinted-background scheme (never solid/opaque). `approved/active` → `#E6F4EA` / `#2E7D32`; `draft/pending` → `#F5F7FA` / `#555`; `rejected/cancelled` → `#FEECEC` / `#C62828`. Use the shared `StatusBadge` component.

### AD-28 · Table implementation standard
All data tables use the `fp-table` CSS class. Column headers use `SortableTh` wherever sorting applies. No inline `<table style={...}>` for new pages.

### AD-29 · Input and select styling standard
All filter-bar `<select>` and `<input>` elements: `{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }`. Reference: `InternalQuotes.jsx`.

### AD-30 · Export CSV button standard
Export CSV always lives top-right in the page header. Discreet ghost style: `{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', color: '#718096' }`. Never inside the filter bar.

### AD-31 · Summary cards rule
Summary metric cards belong on data-aggregation pages (Quotes, Deals pipeline) and are absent on roster/management pages (Users, Partners list, Partner Users). Cards signal "this page summarises business state."

### AD-32 · `fp-card` wrapper standard
All filter bars, form sections, and content panels use the `fp-card` CSS class. No bare `<div style={{ border: …, padding: … }}>` for content panels.

### AD-33 · Centralised document repository — `partner_documents` is the single source of truth for all partner-scoped files
All file content is stored in exactly one row in `partner_documents` per file. Cross-record links (quote acceptance, deal attachments, etc.) are recorded in a separate `document_references` join table (`object_type` + `object_id` + `reference_type`). `partner_org_id` is the hard SOC II / ISO 27001 tenant isolation boundary — every endpoint enforces it without exception. `quote_documents` table retired in Sprint 21 and backfilled. Never create a second table that stores file content.

### AD-34 · `partner_documents.file_data` is deprecated; all binary content lives in `document_versions`
From Sprint 22 onwards every uploaded byte goes into `document_versions.file_data` (one row per version, `is_current=true` flag picks the current). `partner_documents.file_data` is retained on the table for backward compatibility with pre-Sprint-22 rows but new code must never read or write it. The download / preview / version-download endpoints always resolve via `document_versions where is_current=true`. A future Phase 7 migration will null-and-drop the column once all reads are migrated. `partner_documents.current_version_number` and `version_count` are denormalised pointers updated atomically with version inserts.

### AD-35 · Partner roles may self-accept their own-org quote (Sprint 23 / FPRM-389)
`partner_user` and `partner_admin` may, on a quote belonging to their own org, attach a proof-of-acceptance document and `PATCH /quotes/{id}/status` → `accepted` (gated on the `quote:accept_own` permission). They may NOT create / edit / submit / retract / delete; `accepted → sent` retract stays system_admin-only. Tenant scope (`current_user.partner_org_id == quote.partner_org_id`) is enforced in the handler per AD-9, never in `require_permission`. The acceptance gate (a `document_references` row with `entity_type='quote'`, `label='quote_acceptance'`) still applies.

### AD-36 · Document-version revert is open to `partner_admin` for own-org documents (Sprint 23 / FPRM-390)
Supersedes the Sprint 22 internal-only decision (FPRM-374). `partner_admin` may revert versions of their own org's documents (own-org enforced in the handler); internal roles unchanged; `partner_user` still excluded. Every revert emits a `document.version_reverted` audit event and the UI requires a confirm dialog.

### AD-37 · Partner document uploads are gated by size (≤25 MB), not file type (Sprint 23 / FPRM-391)
The PDF/JPG/PNG allowlist is removed — any `mime_type` is accepted. `POST /partners/{id}/documents` and `POST .../versions` reject `file_size_bytes > 26214400` (25 MB) with 422. The Asset Library (PR B) keeps its own independent 10 MB cap.

### AD-38 · Two-table document model: `document_types` is the vocabulary, `document_type_rules` is the approval policy (Sprint 23 / FPRM-387)
`document_types` (code, label, is_active) is the validated list of selectable types shown in dropdowns and surfaced by `GET /config/document-types`. `document_type_rules` (requires_approval, auto_approve) is the per-type approval policy that drives the upload status + acceptance gate. Migration 039 seeds canonical types into BOTH tables with the same key and reconciles every in-use type. The approval-rule lookup fires on every upload path (partner-documents, version, quote-attach) via the shared case-insensitive + trimmed `_find_rule_for_type` helper (FPRM-386). `GET /config/document-types` is NOT repurposed to return rules — it stays the vocabulary endpoint.

### AD-39 · Asset Library binaries are base64 in `assets.file_data`; `file_data` never appears in list responses (Sprint 23 / FPRM-393)
Enablement assets follow the AD-17/AD-19/AD-20 pattern: binary content is stored base64-encoded in `assets.file_data` (Railway has no persistent local filesystem). List endpoints (`GET /assets`, `GET /internal/assets`) NEVER return `file_data` — only `GET /assets/{id}/download` streams the decoded bytes (which also increments `download_count` and writes an `asset_download_logs` row). Upload cap is **10 MB** (independent of the 25 MB partner-documents cap). Deletes are **soft** (`is_active=false`). Visibility is `all` | `tier:<tier>` | `category:<code>`, enforced on the partner list + download against the caller's org tier/category. `system_admin` only for delete; `channel_ops_admin`+ for create/update.

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
| Sprint IDs (native) | Sprint 1: `501`, Sprint 2: `534`, Sprint 3: `535`, Sprint 4: `536`, Sprint 5: `537`, Sprint 6: `538`, Sprint 7: `539`, Sprint 8: `572`, Sprint 9: `605`, Sprint 10: `638`, Sprint 11: `671`, Sprint 12: `704`, Sprint 13: `705`, Sprint 14: `706`, Sprint 15: `739`, Sprint 16: `740`, Sprint 17: `741`, Sprint 18: `742`, Sprint 19: `775`, Sprint 20: `808`, Sprint 21: `841`, Sprint 22: `874` |
| Sprint fix version IDs | Sprint 1: `10528`, Sprint 2: `10561`, Sprint 3: `10562`, Sprint 4: `10563`, Sprint 5: `10564`, Sprint 6: `10565`, Sprint 7: `10566`, Sprint 8: `10599`, Sprint 9: `10632`, Sprint 10: `10665`, Sprint 11: `10698`, Sprint 12: `10731`, Sprint 13: `10732`, Sprint 14: `10733`, Sprint 15: `10766`, Sprint 16: `10767`, Sprint 17: `10768`, Sprint 18: `10769`, Sprint 19: `10802`, Sprint 20: `10835`, Sprint 21: `10868`, Sprint 22: `10901` |

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
- **SMTP env vars not yet set on the `fracttal-prm-backend` Railway service.** Lifecycle email notifications (Sprint 6 / FPRM-93) fall back to stdout in production until `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `CHANNEL_OPS_EMAIL` are set. No code change required — manual ops follow-up. The Sprint 11 forgot-password UI (FPRM-186) consumes the same fallback path until SMTP is configured.
- **`PartnerApplication.info_request_message` is not a real column.** The model has no `info_request_message` Column; the request-info endpoint sets it as an in-memory Python attribute and returns it in the response, never persisting it. The Sprint 11 cancel-info-request endpoint reads it via `getattr(..., None)` to avoid `AttributeError` on applications that never had a request. A proper migration to persist this field would unblock historical reporting of past info requests on applications — parked Low.
- **`PartnerTier` enum vs `PartnerTierConfig` table.** Two parallel constructs since Sprint 13: the enum is referenced by `partner_organizations.tier`; the `partner_tiers` table holds admin-configurable tier records. Carried into Phase 6 — migrating the FK and retiring the enum is queued for the Phase 6 admin-foundation pass.
- **Multi-role users not supported.** A `User.role` is a single string. Sales-side roles (`sales_rep`, `sales_ops`) cannot also hold partner-side roles. Phase 6 may revisit if HubSpot integration requires sales-rep + partner-admin co-roles.
- **`datetime.utcnow()` deprecation warnings throughout codebase.** Python 3.12+ deprecates `datetime.utcnow()` in favour of `datetime.now(timezone.utc)`. Non-blocking today but will break in Python 3.14. Phase 6 sweep planned.
- **HubSpot integration (FR-HS) deferred to Phase 6.** Detailed design inputs already documented; implementation queued for Phase 6 Sprint 1.
- **Implementation services pricing quote deferred — Sprint 20 reframe.** Originally planned as the Sprint 20 theme, deferred again pending business design input on service categories, day rates, and discount rules. Sprint 20 was reframed into Deal Enhancements (full SPICED form, internal deal creation, addon category/sort). Will be scheduled as a dedicated future sprint once design is confirmed.
- **Full deal form reuse in internal "New Deal" modal.** Story 3 (FPRM-317) shipped a focused modal capturing Partner Org + Section A core + opening SPICED instead of embedding the whole `DealRegistrationForm.jsx` page. Extracting that page into a reusable presentational component (so internal create and partner edit share the same JSX) is queued for a future polish sprint. Channel managers create initial drafts via the modal; partners flesh out remaining Section B fields in the portal before submitting.
- **Addon catalogue category taxonomy is empty post-migration 028.** Per AD-25 the categorisation is admin-maintainable data, not seeded by the migration. Until channel ops admins assign categories to the 68 existing add-ons via the Pricing tab, every add-on falls into the quote-form's "Other" group. Manual data-entry follow-up, not a code change.
- **No FX conversion across currencies.** `quotes.currency_code` is display only (AD-23). Cross-currency comparisons or real FX rates are out of scope for Phase 5 and not on the Phase 6 backlog yet.

---

## Phase 6 Backlog / Sprint Candidates

> Product features and improvements deferred to a LATER Phase 6 sprint. These are product
> scope, not deferred architecture — they are NOT Phase 7 and may be implemented in Phase 6
> when a sprint picks them up. Captured here (not just in chat/handoff) so they don't drift
> off the list. Each item notes its origin and a SUGGESTED (not yet committed) target sprint.

- **Partner collaboration messaging on deals** — partner users must be able to send messages
  on a deal. The Collaboration panel currently shows "No messages yet" with no way to
  compose/post. Origin: Sprint 23 UI testing (gap logged after case A9). Suggested target:
  Sprint 25. Note: largest of the three — a real feature, not a tweak.
- **Admin Reactivate for soft-deleted assets and categories** — only deactivate exists today;
  admins need to reactivate a soft-deleted asset or category. Origin: Sprint 23 UI testing
  (gap at case B2). Suggested target: Sprint 25.
- **PortalAssets layout redesign** — replace the tile/card grid with the standard internal
  list + filter layout for consistency with the internal pages. Origin: Sprint 23 UI testing
  (gap at case B11). Suggested target: Sprint 25.

---

## Phase 7 Backlog (do not implement before Phase 7)

> Authoritative list of work consciously deferred to Phase 7. This is the single source
> of truth for Phase 7 scope — the handoff template and sprint dialogs are convenience
> copies only. Add deferrals here in the same PR that defers them so nothing drops off.
> Claude Code must NOT implement any item below while Phase 6 is in progress.

- **Dynamic RBAC (anchor feature)** — make the role permission matrix editable and
  data-driven via Program Config. Replace the hardcoded `backend/permissions.py` role
  checks with a DB-driven lookup backed by new `roles`, `permissions`, and
  `role_permissions` tables. Cross-cutting: touches every router endpoint via
  `require_permission`. The read-only matrix already shipped in Sprint 12 (FPRM-190,
  PR #90, `InternalUsers.jsx`); only the editable/data-driven half is deferred. Deferred
  from Phase 5 (22 May 2026); re-added to the written backlog 29 May 2026 after it dropped
  off the list. Must include self-lockout and privilege-escalation guards, a break-glass
  system_admin path that can never lose its own management permission, audit on every
  matrix change, and cache invalidation on permission edits.
- **`datetime.utcnow()` → `datetime.now(UTC)`** deprecation sweep (Python 3.14 prep). _(See the matching "Known Issues / Technical Debt" entry above.)_
- **Training catalog and qualification management** (FR-TRN, FR-QUAL).
- **Token blacklist persistence** (currently in-memory; not multi-instance safe). _(See the matching "Known Issues / Technical Debt" entry above.)_
- **MFA / refresh-token pattern.**
- **Centralised `audit_log` table** consolidation.
- **Login history table.**
- **Row-level export scoping.**
- **`partner_documents.file_data` column drop** (AD-34 cleanup — drop only once every row
  has a corresponding `document_versions` entry).

---

## Tools Available

- **Claude Code** — Dev Agent for all implementation
- **Atlassian Rovo MCP** — available for direct Jira management from Claude chat
