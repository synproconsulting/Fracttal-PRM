# PROJECT_CONTEXT.md - Fracttal PRM



> Deep implementation reference for Claude Code sessions.

> Supplements CLAUDE.md - read CLAUDE.md first for project overview, sprint history, and environment setup.

> Last updated: Frontend Fix Session 2026-05-26 (PRs #169–#173, migration head 033, 711 tests)



---



## Table of Contents



1. [API Endpoints](#1-api-endpoints)

2. [Database Schema](#2-database-schema)

3. [Component Structure & Data Flow](#3-component-structure--data-flow)

4. [CI/CD Logic & Skip Rules](#4-cicd-logic--skip-rules)

5. [Error Handling Patterns](#5-error-handling-patterns)

6. [Architectural Decisions](#6-architectural-decisions)



---



## 1. API Endpoints



**Base URL:** `https://fracttal-prm-backend-production.up.railway.app` (live since Sprint 1 closeout)



**Framework:** FastAPI (Python 3.11+)



**CORS:** Configured via `FRONTEND_URL` env var (default: `*`). Must be `*` or explicitly include the Control Centre URL (`https://control-centre-service-production.up.railway.app`). Set `FRONTEND_URL=*` in Railway `fracttal-prm-backend` service variables.



### Public Endpoints



| Method | Path | Rate Limit | Description |

|--------|------|------------|-------------|

| GET | `/` | None | Root info — returns service name + version |

| GET | `/health` | None | Health check — `{status, service, database}`, always 200 (DB unreachable → `database: unreachable`, never 500) |

| POST | `/auth/register` | 10/min per IP | Create user with role `partner_user` (hardcoded — external users cannot self-elevate). Body: `{email, password, full_name?}` → 201 `{id, email}`. 409 on duplicate email. |

| POST | `/auth/login` | 10/min per IP | Authenticate. Body: `{email, password}` → 200 `{access_token, token_type, expires_in}`. 401 on bad credentials or inactive account. |

| POST | `/auth/password-reset/request` | None | Always returns 200 `{message: "If that email exists, …"}`. If user exists, generates a UUID reset token with 1h expiry and logs URL to stdout (no email backend yet). |

| POST | `/auth/password-reset/confirm` | None | Body: `{token, new_password}`. 200 on success; 400 if token invalid/used/expired. |

| POST | `/auth/accept-invite` | None | Body: `{token, password, full_name?}` → 201 `{access_token, token_type, expires_in, user}`. Creates a User with role + partner_org_id from the invite, marks invite accepted_at. 404 unknown token, 400 expired/already-accepted, 409 email-already-registered. |

| GET | `/config/partner-categories` | None | List active partner categories — public so the registration form can render. Returns `{items: [{id, code, display_name, deal_reg_sla_hours, max_discount_pct, monthly_fee_usd, ...}]}`. |

| POST | `/applications` | None | Create a draft partner application. Body: `{applicant_email, ...optional fields}` → 201 `{id, draft_token}`. The returned token (30-day expiry) authorises subsequent PATCH/submit/document calls — see AD-11. |

| GET | `/applications/{id}` | None / Bearer | Fetch an application. Public via `?draft_token=...`; internal users with `partner_application:read_all` (channel_manager+) can access any application via JWT. 401 if neither is supplied. |

| PATCH | `/applications/{id}` | None | Public draft update via `?draft_token=...`. Only writable fields are mutated. 400 if status ∉ {draft, info_required}; 403 on bad token; 410 if draft expired. |

| POST | `/applications/{id}/submit` | None | Public submit via `?draft_token=...`. Validates `legal_name`, `applicant_email`, `applicant_name`, `terms_accepted`. On success sets `status=submitted` and `submitted_at=now`. Audit logged as `partner_application.submitted` with `actor=None`. |

| POST | `/applications/{id}/documents` | None | Public document metadata upload via `?draft_token=...`. Body: `{document_type, document_name, file_path, file_size_bytes?, mime_type?}`. Actual file storage is pending — only metadata is persisted today. |

| GET | `/applications/{id}/timeline` | None / Bearer | Return audit-log entries for the application. Public via `?draft_token=...` OR internal Bearer with `partner_application:read_all`. |

| GET | `/applications/{id}/messages` | None / Bearer | Message thread between applicant and reviewers. Public via `?draft_token=...` OR internal Bearer. |

| POST | `/applications/{id}/messages` | None / Bearer | Post a message. Public path records `sender_type=applicant`; internal path records `sender_type=internal` with the JWT user's id+email. |



### Bearer-Authenticated Endpoints



| Method | Path | Permission | Description |

|--------|------|------------|-------------|

| POST | `/auth/logout` | any | Invalidate caller's token (in-memory blacklist). Returns 200. |

| POST | `/auth/refresh` | any | Issue a new access token, invalidate the current one. Returns same shape as `/auth/login`. |

| GET | `/auth/me` | any | Returns `{id, email, role, full_name, partner_org_id}` for the authenticated user. `partner_org_id` added Sprint 7 / FPRM-119 so the portal frontend can resolve the user's org without an extra round-trip. |

| GET | `/admin/audit-log` | `user_management:read_all` (system_admin) | Paginated audit-log query. Query params: `page`, `page_size` (≤200), `object_type`, `actor_id`, `date_from`, `date_to`. Returns `{total, page, page_size, items}`. |

| GET | `/partners` | `partner_organization:read_all` (internal) | List partner organizations. Query: `skip`, `limit` (≤200). Returns `{total, skip, limit, items}`. |

| GET | `/partners/{id}` | any (tenant-scoped) | Get one partner. Partner-side users 403 unless the id matches their own `partner_org_id`. |

| POST | `/partners` | `partner_organization:create` (channel_ops_admin, system_admin) | Create partner. Required: `legal_name`, `program_type`, `partner_category`. Audit logged. |

| PATCH | `/partners/{id}` | channel_ops_admin / system_admin (any) or partner_admin (own only) | Update partner. `id` and `created_at` are immutable. Audit logged. |

| GET | `/partners/{id}/documents` | any (tenant-scoped) | List documents for the partner. |

| POST | `/partners/{id}/documents` | any (tenant-scoped) | Upload document metadata. Required: `document_type`, `document_name`, `file_path`. `proof_of_fiscal_domicile` rejected if `expiry_date < today - 90d`. Audit logged as `partner_document.upload`. |

| PATCH | `/partners/{id}/documents/{doc_id}` | internal roles only | Review/update status, review_notes, expiry_date. Status change is logged as `partner_document.status_change`. |

| POST | `/partners/{id}/users/invite` | partner_admin (own) / channel_ops_admin / system_admin | Generate a 72h invite token. Body: `{email, invited_role}` where invited_role ∈ {`partner_user`, `partner_admin`}. Audit `partner_user.invite_sent`. |

| GET | `/partners/{id}/users` | any (tenant-scoped) | List users where `partner_org_id == {id}`. |

| PATCH | `/partners/{id}/users/{user_id}` | partner_admin (own) / channel_ops_admin / system_admin | Disable/enable (`is_active`), role change (`partner_user` ↔ `partner_admin`), update `full_name`. Each change audited (`partner_user.disabled` / `partner_user.enabled` / `partner_user.role_changed`). |

| GET | `/partners/{id}/activities` | any (tenant-scoped, internal-filtered) | List activities. Partner-side users only see `is_internal=False`. |

| POST | `/partners/{id}/activities` | internal roles only (channel_manager+) | Create activity. Required: `activity_type`, `title`. `is_internal` defaults True. Audit `partner_activity.create`. |

| PATCH | `/partners/{id}/activities/{activity_id}` | creator OR channel_ops_admin / system_admin | Update activity. Audit `partner_activity.update`. |

| POST | `/config/partner-categories` | `system_config:update_all` (channel_ops_admin, system_admin) | Create a new partner category. |

| GET | `/config/commission-structures` | internal roles only | List all commission structures across categories. |

| PATCH | `/config/commission-structures/{id}` | `system_config:update_all` | Update commission_pct / subpartner_uplift_pct / applies_to_upsell / notes. Audit logged. |

| GET | `/applications` | `partner_application:read_all` (channel_manager, channel_ops_admin, system_admin) | Paginated application list. Query: `status` (comma-separated to filter multiple), `skip`, `limit` (≤200). Returns `{total, skip, limit, items}` ordered by `submitted_at` desc. |

| POST | `/applications/{id}/approve` | `partner_application:read_all` (channel_manager+) | Approve a submitted/in_review application. Triggers `provision_partner_from_application` (creates `PartnerOrganization` + `PartnerProfile` + `PartnerUserInvite`). Sets status=approved, links `partner_org_id`. Audit `partner_application.approved`. |

| POST | `/applications/{id}/reject` | `partner_application:read_all` (channel_manager+) | Reject an application. Body: `{rejection_reason}` (required). Sets status=rejected. Audit `partner_application.rejected`. |

| POST | `/applications/{id}/request-info` | `partner_application:read_all` (channel_manager+) | Request more info. Body: `{message}` (required). Sets status=info_required. Applicant can resume via the existing draft_token. Audit `partner_application.info_requested`. |
| GET | `/partner-profiles/{partner_org_id}` | any (tenant-scoped) | Sprint 7 / FPRM-106. Fetch the PartnerProfile keyed by `partner_org_id` (1:1 with the org). Partner-side users 403 unless the org matches their JWT `partner_org_id`. |
| PATCH | `/partner-profiles/{partner_org_id}` | partner_admin (own) / channel_ops_admin / system_admin | Sprint 7 / FPRM-106. Updates whitelisted PartnerProfile fields, recalculates `profile_completeness_pct` (fraction of 11 PROFILE_FIELDS non-null × 100), triggers `recalculate_activation` (AD-14). Audit `partner_profile.update`. |
| GET | `/partners/{id}/activation` | partner_admin (own) / any internal role | Sprint 7 / FPRM-107. Returns the PartnerActivationChecklist. Auto-initialises the row by calling `recalculate_activation` if one is missing (for orgs that pre-date Sprint 7). |
| POST | `/partners/{id}/activation/recalculate` | channel_manager / channel_ops_admin / system_admin | Sprint 7 / FPRM-107. Forces a recalc of every checklist flag. Audit `partner_activation.recalculated`. |
| POST | `/deal-registrations` | partner_admin (own org) **or** channel_manager / channel_ops_admin / system_admin (with `partner_org_id` in body) | Sprint 8 / FPRM-128. Sprint 20 / FPRM-317 added the internal-create path: when the caller is an internal role, `partner_org_id` must be supplied in the body, the org must be `PartnerStatus.active`, the activation gate is **skipped**, `created_on_behalf_of=True` is set, and the audit action is `deal_registration.created_internal` (with `partner_org_id` in `after_state`). partner_admin path unchanged — still activation-gated (`412 {detail, activation_url}`) and sets `created_on_behalf_of=False`. Required body for both paths: `customer_name`, `deal_name`. Sprint 20 / FPRM-316 extended the body whitelist with 35 Section A + B keys (engagement_date, prospect_phone, compiled_by, prospect_contact_name/position, prospect_website, industry_sector, company_size, feature_plan_preference, current_system, old_system, inventory_stores, work_orders_prs, monitoring_system, 13 need_* booleans + integration_with + languages_required, about_client, pain, impact, critical_event, decision, next_steps). `created_on_behalf_of` is deliberately **excluded** from the whitelist — it is server-set on the internal path only. Date strings for `estimated_close_date` and `engagement_date` are coerced server-side (`_coerce_dates`) for Postgres/SQLite parity. |
| GET | `/deal-registrations` | any (tenant-scoped) | Sprint 8 / FPRM-128. List deals. partner roles see only own org; internal roles see all (optionally filtered by `?partner_org_id=`). Supports `?status=&limit=&offset=`. `from_date` / `to_date` filters applied to `submitted_at` (PR #175 fix). End-of-day handling on `to_date`. 422 on malformed date strings. |
| GET | `/deal-registrations/{id}` | any (tenant-scoped) | Sprint 8 / FPRM-128. Read one deal. partner_admin 403 on cross-org access. Sprint 20 / FPRM-316 — response includes all 36 new Section A + B columns plus `created_on_behalf_of` via the existing `_serialize` (which auto-walks `__table__.columns`). |
| PATCH | `/deal-registrations/{id}` | partner_admin (own org, draft only) | Sprint 8 / FPRM-128. Update writable customer + deal fields. 400 if status ≠ draft. Sprint 20 / FPRM-316 body whitelist matches the POST extension above; `created_on_behalf_of` stays excluded so partners cannot toggle it. Date-string coercion via `_coerce_dates`. Audit `deal_registration.updated`. |
| POST | `/deal-registrations/{id}/submit` | partner_admin (own org) | Sprint 8 / FPRM-128. Transitions `draft|info_required` → `submitted`, sets `submitted_at`, snapshots `(commission_structure_id, commission_rate_snapshot)` by resolving `commission_structures` on `(partner_category_code, commission_type, year_1)`. Sprint 10 / FPRM-157 — runs `conflict_checker.check_deal_conflict` after the status flip and writes `conflict_status`/`conflict_checked_at`/`conflict_notes`; the checker is wrapped in try/except so a checker failure cannot roll back the submit. If no commission row matches, commission fields stay null (no error). Audit `deal_registration.submitted`. |
| DELETE | `/deal-registrations/{id}` | partner_admin (own org, draft only) | Sprint 8 / FPRM-128. Hard-delete a draft. 400 if status ≠ draft. Audit `deal_registration.deleted`. |
| GET | `/internal/deals` | channel_manager / channel_ops_admin / system_admin | Sprint 8 / FPRM-134. Internal queue. Supports `?status=&partner_org_id=&limit=&offset=`. Orders by `submitted_at` desc nulls-last. partner_admin → 403. |
| POST | `/internal/deals/{id}/start-review` | review roles | Sprint 8 / FPRM-134. `submitted → under_review`. Records reviewer_id. Audit `deal_registration.review_started`. |
| POST | `/internal/deals/{id}/approve` | review roles | Sprint 8 / FPRM-134. `under_review → approved`. Requires body `{review_notes}` (422 otherwise). Audit `deal_registration.approved`. |
| POST | `/internal/deals/{id}/reject` | review roles | Sprint 8 / FPRM-134. `under_review → rejected`. Requires body `{review_notes}` (422 otherwise). Audit `deal_registration.rejected`. |
| GET | `/deal-registrations/{id}/messages` | any (tenant-scoped) | Sprint 9 / FPRM-139. Chronological collaboration thread for a deal. Partner roles 403 on cross-org access; internal roles see any thread. |
| POST | `/deal-registrations/{id}/messages` | any (tenant-scoped) | Sprint 9 / FPRM-139. Append a message. `sender_type` derived from caller role (`partner` or `internal`). `sender_id` + `sender_email` populated from JWT. Audit `deal_registration.message_posted`. |
| POST | `/internal/deals/{id}/request-info` | review roles | Sprint 9 / FPRM-139. `under_review → info_required`. Body `{message}` required. Posts the reviewer note to the thread. Audit `deal_registration.info_required`. |
| GET | `/config/document-types` | None | Sprint 9 / FPRM-144. Public. Returns active document types `{items: [{id, code, label, is_active, ...}]}`. Pass `?include_inactive=true` for admin tooling. |
| POST | `/config/document-types` | `system_config:update_all` | Sprint 9 / FPRM-144. Create a new document type vocabulary entry. 409 on duplicate code. Audit `document_type.create`. |
| PATCH | `/config/document-types/{id}` | `system_config:update_all` | Sprint 9 / FPRM-144. Update `label` / `is_active` (code immutable). Audit `document_type.update`. |
| POST | `/partners/{id}/activation/training-complete` | channel_manager / channel_ops_admin / system_admin | Sprint 9 / FPRM-145. Flip `baseline_training_complete=True` for a partner; triggers `recalculate_activation`. Audit `partner_activation.training_complete`. |
| POST | `/partners/{id}/activation/training-reset` | channel_manager / channel_ops_admin / system_admin | Sprint 9 / FPRM-145. Reverse the training flag to False. `activated_at` is intentionally preserved across resets. Audit `partner_activation.training_reset`. |
| GET | `/partners/{id}/commission-rates` | partner_admin (own) / any internal role | Sprint 10 / FPRM-158. Returns the rows from `commission_structures` matching the partner's `partner_category_code`. Partner-side users 403 on cross-org access. Response: `{partner_category_code, items: [{commission_type, year, percentage, subpartner_uplift_pct, applies_to_upsell, notes}]}`. |
| POST | `/internal/deals/{id}/override-conflict` | channel_manager / system_admin only | Sprint 10 / FPRM-157. Override a `conflict_detected` deal back to `conflict_status=clear`. Body requires `override_notes` (free-text rationale appended to `conflict_notes` with the reviewer's email tag). Channel_ops_admin explicitly excluded. Audit `deal_registration.conflict_overridden`. |
| GET | `/internal/dashboard/summary` | system_admin / channel_ops_admin / channel_manager | Sprint 11 / FPRM-179. Internal home roll-up: applications, deals, partners, conflicts counts. All counts computed at query time from existing tables. |
| GET | `/partners/{id}/dashboard/summary` | system_admin / channel_ops_admin / channel_manager / partner_admin (own) | Sprint 11 / FPRM-183 (widened in Sprint 12 / FPRM-190). Partner home roll-up: deals counts by status, activation `items_complete/items_total`, document counts. |
| POST | `/applications/{id}/cancel-info-request` | channel_manager+ | Sprint 11 / FPRM-186. `info_required → under_review`. Audit `partner_application.cancel_info_request`. |
| POST | `/internal/deals/{deal_id}/cancel-info-request` | review roles | Sprint 11 / FPRM-186. `info_required → under_review`, posts a system message to the deal thread. Audit `deal_registration.cancel_info_request`. |
| GET | `/internal/users` | system_admin | Sprint 12 / FPRM-194. Paginated internal-user list. Filters: `role`, `is_active`, `skip`, `limit`. |
| GET | `/internal/users/{user_id}` | system_admin | Sprint 12 / FPRM-194. Get one internal user. |
| POST | `/internal/users/invite` | system_admin | Sprint 12 / FPRM-194. Create a new internal user with a random unguessable password; mints a 7-day `PasswordResetToken` and sends a welcome email via `notifications.send_email`. Audit `internal_user.invited`. |
| PATCH | `/internal/users/{user_id}/role` | system_admin | Sprint 12 / FPRM-194. Change role; blocks self-modification and demoting the last active system_admin. Audit `internal_user.role_changed`. |
| POST | `/internal/users/{user_id}/disable` | system_admin | Sprint 12 / FPRM-194. Sets `is_active=False`. Audit `internal_user.disabled`. |
| POST | `/internal/users/{user_id}/reactivate` | system_admin | Sprint 12 / FPRM-194. Sets `is_active=True`. Audit `internal_user.reactivated`. |
| GET | `/internal/partner-users` | system_admin / channel_ops_admin | Sprint 12 / FPRM-202. Cross-org partner-user list (distinct from per-tenant `/partners/{id}/users`). |
| POST | `/internal/partner-users/invite` | system_admin / channel_ops_admin | Sprint 12 / FPRM-202. Invite a partner user under any org. |
| PATCH | `/internal/partner-users/{user_id}/role` | system_admin / channel_ops_admin | Sprint 12 / FPRM-202. Change `partner_user` ↔ `partner_admin`. |
| POST | `/internal/partner-users/{user_id}/disable` | system_admin / channel_ops_admin | Sprint 12 / FPRM-202. Disable any partner user. |
| POST | `/internal/partner-users/{user_id}/reactivate` | system_admin / channel_ops_admin | Sprint 12 / FPRM-202. Reactivate any partner user. |
| GET | `/internal/partners` | system_admin / channel_ops_admin / channel_manager | Sprint 12 / FPRM-205. Cross-org partner list with search/status/tier/category filters, page/page_size pagination, activation status join. |
| PATCH | `/internal/partners/{id}/status` | system_admin / channel_ops_admin | Sprint 13 / FPRM-208. Set `active` / `suspended` / `terminated` / `inactive` (400 on `applicant` — only the approval flow may set that). Audit `partner_org.status_changed`. |
| GET / POST / PATCH / DELETE | `/internal/config/approval-steps[/{id}]` | system_admin / channel_ops_admin (writes), any internal (reads), system_admin only (delete) | Sprint 13 / FPRM-209. CRUD for `approval_workflow_steps`. Delete is soft. |
| GET / POST / PATCH | `/internal/config/tiers[/{id}]` | system_admin / channel_ops_admin (writes), any internal (reads) | Sprint 13 / FPRM-213. CRUD for `partner_tiers` (409 on duplicate name). |
| POST / DELETE | `/internal/config/tiers/{tier_id}/eligibility-rules[/{rule_id}]` | system_admin / channel_ops_admin (add), system_admin only (delete) | Sprint 13 / FPRM-213. Add/remove rules of types `min_deals_approved` / `min_revenue` / `required_certification` / `min_win_rate`. |
| GET / POST / PATCH / DELETE | `/internal/config/activation-criteria[/{id}]` | system_admin / channel_ops_admin (writes), any internal (reads) | Sprint 13 / FPRM-213. CRUD for `activation_checklist_config`. Delete is soft. |
| GET | `/internal/reports/pipeline` | system_admin / channel_ops_admin / channel_manager / sales_ops | Sprint 14 / FPRM-221. Pipeline roll-up: by-partner, by-category, by-tier, totals. Optional `from_date` / `to_date` / `partner_category` / `tier` filters. All counts aggregated at query time. |
| GET | `/internal/reports/cycle-times` | system_admin / channel_ops_admin / channel_manager / sales_ops | Sprint 14 / FPRM-221. All-time cycle-time metrics: overall average days, by-category-and-month series, slowest-5 deals. |
| GET | `/internal/reports/conflicts` | system_admin / channel_ops_admin / channel_manager / sales_ops | Sprint 14 / FPRM-221. Conflict rate + count + unresolved (non-approved/rejected) deals. Same filter shape as `/pipeline`. |
| GET | `/internal/reports/partner-activity` | system_admin / channel_ops_admin / channel_manager / sales_ops | Sprint 14 / FPRM-221. Per-partner last-deal-submitted, deals-in-90-days, activation status, document count. Active partners only. |
| GET | `/internal/reports/pipeline/export` | system_admin / channel_ops_admin / channel_manager / sales_ops / finance_approver | Sprint 14 / FPRM-221. CSV export of the pipeline dataset. `Content-Type: text/csv` + `Content-Disposition: attachment; filename=pipeline_export.csv`. |
| GET | `/partners/{id}/pipeline` | partner_admin (own org only) | Sprint 14 / FPRM-229. Deals grouped by status into 6 keys (`draft`/`submitted`/`under_review`/`info_required`/`approved`/`rejected`). Optional `status`/`from_date`/`to_date` filters. 403 to internal roles by design — internal users use `/internal/reports/pipeline`. `from_date` / `to_date` applied to `submitted_at` (PR #175 fix). End-of-day handling on `to_date`. 422 on malformed date strings. |
| POST | `/deals/{deal_id}/quotes` | partner_admin (own deal) + channel_manager / channel_ops_admin / system_admin | Sprint 15 / FPRM-246. Create a Quote bound to a registered deal. Body: `{quote_name?, currency_code?, feature_plan, feature_plan_discount_pct?, qty_transactional_users, qty_limited_tech_users, selected_addon_keys?, scenario_label?}`. Calls `quote_engine.calculate_quote` (AD-18); persists `QuoteVersion` v1 + `QuoteLineItem` rows. Engine `ValueError` -> 422. Audit `quote.created`. |
| GET | `/deals/{deal_id}/quotes` | tenant-scoped (partner roles own org only) | Sprint 15 / FPRM-246. List quotes for a deal; returns summary array with `grand_total_after_discount` joined from the active version. |
| GET | `/quotes/{quote_id}` | tenant-scoped | Sprint 15 / FPRM-246. Quote header + `active_version_data` containing the ordered line items. |
| POST | `/quotes/{quote_id}/versions` | channel_manager / channel_ops_admin / system_admin | Sprint 15 / FPRM-246. Add a new version. `version_number = max(existing) + 1`. Does NOT auto-change `active_version`. Audit `quote.version_added`. |
| PATCH | `/quotes/{quote_id}/active-version` | channel_manager / channel_ops_admin / system_admin | Sprint 15 / FPRM-246. Re-point `quotes.active_version`. 422 if the target version doesn't exist or is soft-deleted. Optional `scenario_label`. Audit `quote.version_activated`. |
| PATCH | `/quotes/{quote_id}/status` | channel_manager / channel_ops_admin / system_admin | Sprint 15 / FPRM-246. State machine: `draft -> sent`, `sent -> accepted`, `sent -> expired`. Other transitions return 422. Audit `quote.status_changed`. |
| GET | `/quotes/{quote_id}/versions` | tenant-scoped | Sprint 15 / FPRM-246. List all versions (incl. soft-deleted) — `{version_number, scenario_label, feature_plan, grand_total_after_discount, created_at, is_deleted}`. |
| DELETE | `/quotes/{quote_id}/versions/{version_number}` | channel_ops_admin / system_admin | Sprint 15 / FPRM-246. Soft-delete (`is_deleted = True`). Cannot delete the currently active version (422). Audit `quote.version_deleted`. |
| GET | `/internal/config/pricing/plans` | any authenticated user | Sprint 15 / FPRM-246. Active `FeaturePlanPrice` rows — needed by the quote form UI. |
| GET | `/internal/config/pricing/addons` | any authenticated user | Sprint 15 / FPRM-246. Active `AddonCatalogItem` rows — needed by the quote form UI. |
| GET | `/partners/{partner_org_id}/activation/criteria` | partner_admin (own org) or any internal role | Sprint 17 / FPRM-270 (AD-21). Returns resolved required criteria for the partner: `{required_criteria: [{criterion_key, description, is_met}], activation_complete, config_source}`. `config_source` is `"dynamic"` when matching `activation_checklist_config` rows exist, `"fallback"` when the legacy four-flag default applies. |
| PATCH | `/quotes/{quote_id}/active-scenario` | channel_manager / channel_ops_admin / system_admin | Sprint 18 / FPRM-283 (AD-24). Re-point `quotes.active_scenario`. Body `{scenario_label: "good"|"better"|"best"|null}`. 422 if the label has no non-deleted version on the quote. Null clears the selection. Audit `quote.scenario_selected`. |
| GET | `/quotes/{quote_id}/scenarios` | tenant-scoped | Sprint 18 / FPRM-283 (AD-24). Returns `{scenarios: [{scenario_label, version_number, feature_plan, grand_total_after_discount, is_active}], active_scenario}`. Groups non-deleted versions by `scenario_label`, returns the latest version per label, in canonical good/better/best order. |
| GET | `/internal/quotes` | channel_manager / channel_ops_admin / system_admin | Sprint 18 / FPRM-287. Cross-deal quote dashboard. Filters: `status` / `partner_org_id` / `feature_plan` / `search` (matches `quote_name` or `deal_name`). Pagination: `page` (>=1) / `page_size` (1–100, default 20). Returns `{items, total, page, page_size, summary}`. `summary` rolls up system-wide totals and pipeline value (expired excluded). Joins Quote → active QuoteVersion → DealRegistration → PartnerOrganization. |
| GET | `/partners/{partner_org_id}/quotes` | partner_admin / partner_user (own org only) | Sprint 18 / FPRM-291. Partner-facing quote history scoped to the user's own org. Internal users are 403'd (use `/internal/quotes`). Optional `?status=` filter. Returns `{items: [{quote_name, deal_name, feature_plan, currency_code, grand_total_after_discount, status, active_version, active_scenario, ...}]}` with grand totals joined from the active non-deleted version. Note: response missing `deal_status` field — needed for Won/Closed Won summary cards in `PortalQuotes.jsx`. Sprint 21 backlog (aligns with document repository work). |
| GET | `/internal/config/pricing/plans` | any authenticated user; `?include_inactive=true` admin-only | Sprint 15; Sprint 19 / FPRM-300 (AD-25) extended with `?include_inactive=true` (admin-only) to surface deactivated + scheduled rows. Always includes `is_active` in the response. Ordered by `plan_code, effective_from DESC`. |
| POST | `/internal/config/pricing/plans` | channel_ops_admin / system_admin | Sprint 19 / FPRM-300 (AD-25). Create a new FeaturePlanPrice row. Required body: `plan_code` (starter/professional/enterprise), `feature_pack_annual`, `transactional_user_annual`, `limited_tech_user_annual`, `effective_from` (ISO date). Audit `pricing.plan_price_created`. |
| PATCH | `/internal/config/pricing/plans/{plan_price_id}` | channel_ops_admin / system_admin | Sprint 19 / FPRM-300. Update price fields, effective_from, or is_active. Audit `pricing.plan_price_updated`. |
| DELETE | `/internal/config/pricing/plans/{plan_price_id}` | system_admin only | Sprint 19 / FPRM-300. Soft delete (`is_active=False`). 422 if it would leave a plan with zero active rows. Audit `pricing.plan_price_deactivated`. |
| GET | `/internal/config/pricing/volume-tiers` | any authenticated user; `?include_inactive=true` admin-only | Sprint 19 / FPRM-300. Returns active `VolumeDiscountTier` rows ordered by `min_users`. |
| POST | `/internal/config/pricing/volume-tiers` | channel_ops_admin / system_admin | Sprint 19 / FPRM-300. Create a tier. Body: `min_users`, `max_users` (null = no upper bound), `transactional_user_discount_pct`, `limited_tech_user_discount_pct`. 422 if the new band overlaps any active tier. Audit `pricing.volume_tier_created`. |
| PATCH | `/internal/config/pricing/volume-tiers/{tier_id}` | channel_ops_admin / system_admin | Sprint 19 / FPRM-300. Update min/max/discounts/is_active. Min/max changes re-run the overlap check against other active tiers. Audit `pricing.volume_tier_updated`. |
| DELETE | `/internal/config/pricing/volume-tiers/{tier_id}` | system_admin only | Sprint 19 / FPRM-300. Soft delete with gap-coverage check: 422 if removing this tier would leave a gap unless `?force=true`. Audit `pricing.volume_tier_deactivated`. |
| GET | `/internal/config/pricing/addons` | any authenticated user; `?include_inactive=true` admin-only | Sprint 15; Sprint 19 / FPRM-300 extended with `?include_inactive=true` admin-only; Sprint 20 / FPRM-318 added `?category=<name>` filter (use literal `__null__` to match uncategorised rows) and includes `category` + `sort_order` in the response. Ordering: `(category, sort_order, display_name)`. |
| POST | `/internal/config/pricing/addons` | channel_ops_admin / system_admin | Sprint 19 / FPRM-300. Create an add-on. Body: `addon_key` (unique, case-insensitive), `display_name`, `monthly_price`, `available_starter`, `available_professional`. `included_enterprise` always True. 422 on duplicate key. Audit `pricing.addon_created`. `category` and `sort_order` are NOT accepted on create — set them via PATCH after create (FPRM-318). |
| PATCH | `/internal/config/pricing/addons/{addon_id}` | channel_ops_admin / system_admin | Sprint 19 / FPRM-300. Update display_name / monthly_price / availability flags / is_active. Sprint 20 / FPRM-318 extended body with `category` (String, empty string clears to null) and `sort_order` (Integer, negatives clamped to 0; non-int → 422). Audit `pricing.addon_updated`. |
| DELETE | `/internal/config/pricing/addons/{addon_id}` | system_admin only | Sprint 19 / FPRM-300. Soft delete (`is_active=False`). Audit `pricing.addon_deactivated`. |
| GET | `/admin/audit-log` | system_admin (`user_management:read_all`) | Existing endpoint; Sprint 19 / FPRM-308 adds `?action_prefix=` (matches `action LIKE '{prefix}.%'`) and `?export=csv` (text/csv with `Content-Disposition: attachment`). Same Bearer-header auth as JSON path (AD-20). |
| POST | `/internal/deals/{id}/conflict-check` | channel_manager / channel_ops_admin / system_admin | Post-Sprint-20 (PR #141). Manual re-run of `conflict_checker.check_deal_conflict` against an existing deal; updates `conflict_status`, `conflict_checked_at`, `conflict_notes`. Surface for internal users to refresh stale conflict state after data changes. Audit `deal_registration.conflict_rechecked`. |
| GET | `/internal/config/commission-rates` | any internal role (read); channel_ops_admin / system_admin (writes) | Post-Sprint-20 (PR #142, migration 031). Admin CRUD over `commission_structures` rows. List supports `?partner_category_code=&commission_type=&is_active=` filters; rows include `is_active`, `created_at`, `updated_at`. |
| POST | `/internal/config/commission-rates` | channel_ops_admin / system_admin | Post-Sprint-20 (PR #142). Create a commission rate. Body: `partner_category_code`, `commission_type`, `year`, `commission_pct`, `subpartner_uplift_pct?`, `applies_to_upsell?`, `notes?`, `is_active?`. Audit `commission_rate.created`. |
| PATCH | `/internal/config/commission-rates/{id}` | channel_ops_admin / system_admin | Post-Sprint-20 (PR #142). Update mutable fields (`commission_pct`, `subpartner_uplift_pct`, `applies_to_upsell`, `notes`, `is_active`). Identity tuple (`partner_category_code`, `commission_type`, `year`) is immutable. Audit `commission_rate.updated`. |
| DELETE | `/internal/config/commission-rates/{id}` | system_admin | Post-Sprint-20 (PR #142). Soft delete (sets `is_active=False`). Audit `commission_rate.deactivated`. |
| POST | `/internal/deals/{id}/won` | channel_manager / channel_ops_admin / system_admin | Post-Sprint-20 (PRs #156 + #157, migration 032). Mark an approved deal as **won**. Requires at least one quote on the deal with `status='accepted'` (422 otherwise). Cascade-cancels any other non-terminal quote versions on the deal (engine state moves to `cancelled` with audit). Audit `deal_registration.won` + per-quote `quote.cascade_cancelled`. |
| PATCH | `/quotes/{id}/status` | channel_manager / channel_ops_admin / system_admin (`sent → accepted` and `draft → sent`); **system_admin only** for `accepted → sent` (retract) | Post-Sprint-20 (PR #161). Extends Sprint 15 state machine with `accepted → sent` as a system_admin-only retract path; remaining transitions unchanged. Terminal states (`cancelled`, `expired`, `won`-bound) reject further mutation (422). Audit `quote.status_changed` (retains the original action; `before`/`after` columns capture the retract). |
| PATCH | `/quotes/{id}/pipeline-inclusion` | channel_manager / channel_ops_admin / system_admin | Post-Sprint-20 (PRs #147 + #149 + #153, migration 032). Toggle `quotes.include_in_pipeline` (Boolean, default True). Drives the per-deal `pipeline_total` aggregation on `/internal/deals` and `/partners/{id}/pipeline`. Audit `quote.pipeline_inclusion_toggled`. |
| POST | `/quotes/{id}/documents` | partner_admin (own org) + channel_manager / channel_ops_admin / system_admin | Post-Sprint-20 (PR #158, migration 033). Attach a document to a quote (e.g. signed acceptance PDF). Body: `{document_type, document_name, file_data_base64, mime_type?, file_size_bytes?}`. Only metadata + base64 blob are persisted (no external blob store — same constraint as AD-19). Audit `quote_document.uploaded`. |
| GET | `/quotes/{id}/documents` | tenant-scoped | Post-Sprint-20 (PR #158). List attached documents for a quote (omits the base64 blob). |
| GET | `/quotes/{id}/documents/{doc_id}/download` | tenant-scoped | Post-Sprint-20 (PR #158). Stream the attached document back as the original MIME with `Content-Disposition: attachment`. Same fetch+Blob client pattern as AD-20. |
| DELETE | `/quotes/{id}/documents/{doc_id}` | channel_ops_admin / system_admin | Post-Sprint-20 (PR #158). Remove an attached document. Audit `quote_document.deleted`. Acceptance-gate logic re-evaluates on next status PATCH: when the partner attempts `sent → accepted`, the backend requires at least one non-deleted `QuoteDocument` of `document_type='signed_acceptance'` (422 otherwise). |



### JWT Token Spec



- Algorithm: HS256 (signed with `JWT_SECRET` env var)

- Expiry: from `JWT_EXPIRY_HOURS` env var, default 168 (7 days)

- Payload: `{sub: user_id_uuid, email, role, exp}`

- Header: `Authorization: Bearer <token>`

- Logout adds the token to an **in-memory** server-side blacklist — lost on backend restart (see Sprint 3 follow-ups in CLAUDE_HISTORY.md)



> Additional endpoints documented here as sprints deliver them.



---



## 2. Database Schema



### Tables (as of Sprint 7)



| Table | Migration | Purpose |

|---|---|---|

| `users` | `001_create_users_table` (+ FK added in `004`) | Authenticated users. Columns: `id` (UUID PK), `email` (unique indexed), `hashed_password`, `full_name`, `is_active`, `is_verified`, `role` (string — validated against `UserRole` enum at auth time), `partner_org_id` (UUID, nullable, FK → partner_organizations.id), `created_at`, `updated_at`. FK constraint `fk_users_partner_org_id` added in migration 004. |

| `password_reset_tokens` | `002_create_password_reset_tokens` | Single-use password reset tokens. Columns: `id` (UUID PK), `token` (unique indexed), `user_id` (FK → users.id), `expires_at`, `used` (bool), `created_at`. 1-hour expiry enforced in handler. |

| `audit_log` | `003_create_audit_log` (+ `009` makes `actor_id` nullable) | Append-only audit trail. Columns: `id` (UUID PK), `timestamp` (indexed), `actor_id` (FK → users.id, **nullable since 009 for anonymous events**), `actor_role` (`"anonymous"` when actor is None), `action` (dot-notation e.g. `partner_profile.update`), `object_type` (indexed), `object_id` (UUID), `before_state` / `after_state` (JSON), `ip_address`, `notes`. Write via `audit.log_audit_event(...)`; read via `GET /admin/audit-log`. |

| `partner_organizations` | `004_create_partner_organizations` | Central partner record. Columns: `id` (UUID PK), `legal_name` (not null), `dba_name`, `website`, `hq_address` (JSONB), `phone`, `email`, `program_type` (ENUM distributor/subpartner), `partner_category` (ENUM master/promotor/reseller), `parent_partner_id` (FK self-ref, nullable), `tier` (ENUM registered/silver/gold, nullable), `territory`/`industries`/`authorized_offerings`/`delivery_capabilities` (JSONB), `status` (ENUM applicant/active/suspended/inactive/terminated), `monthly_fee_status` (ENUM current/overdue/waived), `contract_start_date`, `contract_end_date`, `auto_renew` (bool default true), `certification_expiry_date`, `hubspot_company_id`, `created_at`, `updated_at`. |

| `partner_profiles` | `004_create_partner_organizations` | Onboarding questionnaire. Columns: `id`, `partner_org_id` (FK unique), `year_established`, `employee_count`, `annual_revenue`, `shareholders` (JSONB), `cmms_experience` + `cmms_experience_description`, `other_software_products`, `sales_marketing_strategy`, `technical_support_team` + `technical_support_description`, `implementation_services` + `implementation_description`, `partnership_goals`, `market_growth_plan`, `additional_info`, `profile_completeness_pct` (default 0), `updated_at`. |

| `partner_documents` | `005_create_partner_documents` | Legal/compliance documents. Columns: `id`, `partner_org_id` (FK), `document_type` (ENUM: id_legal_representative, power_of_attorney, articles_of_incorporation, beneficial_owners_list, fiscal_id, proof_of_fiscal_domicile, bank_certificate, nda, insurance, other), `document_name`, `file_path`, `file_size_bytes`, `mime_type`, `uploaded_by_user_id` (FK users), `uploaded_at`, `expiry_date`, `status` (ENUM pending_review/approved/rejected/expired, default pending_review), `review_notes`, `reviewed_by_user_id` (FK users, nullable), `reviewed_at`. Indexed on `partner_org_id`. |

| `partner_user_invites` | `006_create_partner_user_invites` | 72-hour invite tokens. Columns: `id`, `partner_org_id` (FK), `email`, `invited_role` (ENUM partner_user/partner_admin), `token` (unique indexed), `invited_by_user_id` (FK users), `expires_at`, `accepted_at` (nullable), `created_at`. |

| `partner_activities` | `007_create_partner_activities` | Notes / tasks / calls / meetings / emails / status-change events. Columns: `id`, `partner_org_id` (FK indexed), `activity_type` (ENUM), `title`, `body`, `due_date`, `completed_at`, `created_by_user_id` (FK users), `assigned_to_user_id` (FK users, nullable), `is_internal` (bool, default true), `created_at`. |

| `partner_category_configs` | `008_create_partner_category_and_commission` | Configurable partner tiers. Columns: `id`, `code` (unique indexed), `display_name`, `description`, `deal_reg_sla_hours`, `max_discount_pct` (numeric), `monthly_fee_usd` (numeric default 200), `is_active`, `created_at`, `updated_at`. **Seeded with 3 rows: master/promotor/reseller** (SLA 48/72/96h, discount cap 40/30/20%). |

| `commission_structures` | `008_create_partner_category_and_commission` | Commission lookup per (category, type, year). Columns: `id`, `partner_category_code` (FK → partner_category_configs.code), `commission_type` (ENUM autonomous_sell/indirect_sell/direct_sell/co_sell_shared), `year` (ENUM year_1/year_2_plus), `commission_pct` (numeric), `subpartner_uplift_pct` (numeric default 10.0), `applies_to_upsell` (bool default true), `notes`. **Seeded with 24 rows** per Fracttal Distributor Agreement: autonomous_sell Y1=50% Y2+=30%, indirect_sell 30%/30%, direct_sell 10%/10%, co_sell_shared 25%/25%; subpartner uplift +10% applies only to Y1. |

| `partner_applications` | `009_create_partner_applications` + `010_application_review_columns` | Public partner-application drafts and submitted applications. Columns: `id` (UUID PK), `status` (ENUM `application_status`: draft/submitted/in_review/info_required/approved/rejected, default draft), `applicant_email` (not null), `applicant_name`, `applicant_phone`, `applicant_title`, `legal_name`, `dba_name`, `website`, `hq_address` (JSONB), `phone`, `requested_categories` / `territory` / `industries` (JSONB arrays), `year_established`, `employee_count`, `annual_revenue`, `shareholders` (JSONB), `other_software_products`, `cmms_experience` (bool) + `cmms_experience_description`, `sales_marketing_strategy`, `technical_support_team` (bool) + `technical_support_description`, `implementation_services` (bool) + `implementation_description`, `partnership_goals`, `market_growth_plan`, `additional_info`, `references` (JSONB array), `terms_accepted` (bool default false) + `terms_accepted_at`, `draft_token` (unique, indexed) + `draft_expires_at` (30-day TTL), `submitted_at`, `reviewer_id` (FK users, nullable — populated in Sprint 6), `review_notes`, `reviewed_at`, `partner_org_id` (FK partner_organizations, nullable — populated on approval by `provisioning.provision_partner_from_application`), `rejection_reason` (TEXT NULL — populated on POST /reject, **added in migration 010**), `info_request_message` (TEXT NULL — populated on POST /request-info, **added in migration 010**), `created_at`, `updated_at`. |

| `partner_application_documents` | `009_create_partner_applications` | Supporting documents uploaded with an application. Columns: `id` (UUID PK), `application_id` (FK partner_applications, indexed), `document_type` (string — free-form for the public form), `document_name`, `file_path`, `file_size_bytes`, `mime_type`, `uploaded_at`. Only metadata is recorded today — actual file storage backend is pending. |

| `partner_application_messages` | `011_create_partner_application_messages` | Message thread between applicants and internal reviewers (Sprint 6 / FPRM-91). Columns: `id` (UUID PK), `application_id` (FK partner_applications, indexed), `sender_type` (ENUM `application_message_sender`: applicant/internal), `sender_id` (FK users.id, nullable — null when sender_type=applicant), `sender_email`, `message` (TEXT), `created_at`. |
| `partner_activation_checklists` | `012_create_partner_activation_checklists` | Sprint 7 / FPRM-107 / AD-14. One row per partner org, created by `provision_partner_from_application` with all flags False. Recomputed by `backend/activation.py` `recalculate_activation(db, partner_org_id)` after every profile update, document approval, and contract-date change. Columns: `id` (UUID PK), `partner_org_id` (UUID FK unique to `partner_organizations.id`), `profile_complete` (bool — true when `profile_completeness_pct >= 80`), `documents_uploaded` (bool — **Sprint 10 / FPRM-156**: true when the partner has at least one approved `partner_documents` row; the earlier "both fiscal_id + id_legal_representative" rule became unworkable once FPRM-144 made document_types admin-configurable), `terms_signed` (bool — true when `partner_organizations.contract_start_date IS NOT NULL`), `baseline_training_complete` (bool, default False — flipped via `POST /partners/{id}/activation/training-complete` since FPRM-145), `activation_complete` (bool — true when all four gates are True), `activated_at` (datetime, set on the first transition to `activation_complete=True` and never cleared on regression), `updated_at`. |
| `deal_registrations` | `013_create_deal_registrations` (+ `027_extend_deal_registrations` in Sprint 20) | Sprint 8 / FPRM-125. Deal opportunities registered by partner_admins. Columns: `id` (UUID PK), `partner_org_id` (UUID FK to `partner_organizations.id`, not null), `status` (string, default `draft`; lifecycle: draft/submitted/under_review/info_required/approved/rejected/expired), customer info — `customer_name` (not null), `customer_domain`, `customer_contact_name`, `customer_contact_email`, `customer_contact_phone`, `customer_industry`, `customer_country`, `customer_region`; deal info — `deal_name` (not null), `estimated_deal_value` (Float), `estimated_close_date` (Date), `deal_notes` (Text), `commission_type` (string); commission snapshot (immutable after submit) — `commission_structure_id` (UUID FK to `commission_structures.id`, nullable), `commission_rate_snapshot` (Float); conflict check (Sprint 10) — `conflict_checked_at` (DateTime), `conflict_status` (string, default `not_checked`), `conflict_notes` (Text); lifecycle/review — `submitted_at`, `reviewer_id` (UUID FK to `users.id`), `reviewed_at`, `review_notes` (Text), `created_at`, `updated_at`. Index on `(partner_org_id, status)`. **Sprint 20 / FPRM-315 (migration 027) added 36 columns**: Section A additional prospect/engagement fields (`engagement_date` Date, `prospect_phone` String, `compiled_by` String, `prospect_contact_name` String, `prospect_contact_position` String, `prospect_website` String, `industry_sector` String, `company_size` String, `feature_plan_preference` String); Section B Current Systems (`current_system`, `old_system`, `inventory_stores`, `work_orders_prs`, `monitoring_system` — each String accepting none|excel|paper|social_media|cmms|other); Section B Feature Requirements (`need_asset_depreciation`, `need_wo_wr`, `need_reports`, `need_tool_management`, `need_purchasing`, `need_integration` + `integration_with` String, `need_multi_language` + `languages_required` String, `need_asset_management`, `need_document_management`, `need_cost_tracking`, `need_monitoring`, `need_schedule_third_parties`, `need_track_labour` — all Boolean nullable for three-state checkboxes); Section B SPICED narratives (`about_client`, `pain`, `impact`, `critical_event`, `decision`, `next_steps` — all Text nullable); plus `created_on_behalf_of` (Boolean NOT NULL, `server_default='false'`, set True by FPRM-317 internal-create path only). |
| `deal_messages` | `016_create_deal_messages` | Sprint 9 / FPRM-139. Collaboration thread on a deal registration. Columns: `id` (UUID PK), `deal_id` (UUID FK to `deal_registrations.id`, not null), `sender_type` (string — `partner` or `internal`), `sender_id` (UUID FK to `users.id`, nullable), `sender_email` (string, not null), `message` (Text, not null), `created_at` (DateTime, not null). Index on `(deal_id, created_at)`. |
| `document_types` | `017_create_document_types_config` | Sprint 9 / FPRM-144. Admin-configurable document type vocabulary, replacing the hardcoded `DocumentType` enum. Columns: `id` (UUID PK), `code` (unique indexed string), `label`, `is_active` (bool, default true), `created_at`, `updated_at`. Seeded with the 10 original enum values. The migration also converts `partner_documents.document_type` from a PG enum to VARCHAR so admin-added types can be inserted at runtime (same pattern as FPRM-138 migration 015). |
| `users.last_login_at` | `020_add_last_login_at_to_users` | Sprint 12 / FPRM-194. Adds a `last_login_at` DateTime column (nullable) to `users`; stamped by the `auth_router.login` happy path. Surfaced by the internal user management UI. |
| `approval_workflow_steps` | `021_create_approval_workflow_steps` | Sprint 13 / FPRM-209. Admin-configurable approval steps. Columns: `id` (UUID PK), `workflow_type` (`partner_application` / `deal_registration`), `step_order` (integer), `step_name` (string), `assignee_role` (role string), `is_active` (bool), `created_at`, `updated_at`. Seeded with 2 default rows (`Channel Ops Review` for partner_application, `Channel Manager Review` for deal_registration). Multi-step enforcement is deferred to Phase 5. |
| `partner_tiers` | `022_create_tier_and_checklist_config` | Sprint 13 / FPRM-213. Admin-configurable tier definitions (model class `PartnerTierConfig` to avoid clashing with the existing `PartnerTier` enum). Columns: `id` (UUID PK), `name` (unique), `rank` (integer — controls order), `commission_uplift_pct` (numeric), `description` (text), `is_active` (bool), `created_at`, `updated_at`. Seeded with 3 rows (Registered/Silver/Gold). `partner_organizations.tier` still references the legacy enum — Phase 5 will migrate the FK and retire the enum. |
| `partner_tier_eligibility_rules` | `022_create_tier_and_checklist_config` | Sprint 13 / FPRM-213. Rules attached to a tier (FK cascade on delete). Columns: `id` (UUID PK), `tier_id` (FK), `rule_type` (one of `min_deals_approved` / `min_revenue` / `required_certification` / `min_win_rate`), `threshold_value` (numeric), `notes` (text). |
| `activation_checklist_config` | `022_create_tier_and_checklist_config` | Sprint 13 / FPRM-213. Admin-configurable activation criteria. Columns: `id` (UUID PK), `criterion_code` (unique), `display_name`, `description`, `is_required` (bool default true), `is_active` (bool default true), `scoped_category` (string nullable), `scoped_tier` (string nullable), `created_at`, `updated_at`. Seeded with 6 rows mirroring the 4 hard-coded flags in `activation.py` plus 2 placeholders (`contract_signed`, `training_advanced_complete`). Dynamic enforcement deferred to Phase 5. |
| `feature_plan_prices` | `023_create_pricing_catalogue` | Sprint 15 / FPRM-239. Per-plan annual list prices. Columns: `id` (UUID PK), `plan_code` (string: `starter`/`professional`/`enterprise`), `feature_pack_annual`/`transactional_user_annual`/`limited_tech_user_annual` (Numeric(10,2)), `is_active` (bool default true), `effective_from` (date), `created_at`. Seeded with 3 rows per the Fracttal Pricing and Quotation Specification (Starter 1161/540/240, Professional 2868/720/240, Enterprise 8028/900/240). |
| `volume_discount_tiers` | `023_create_pricing_catalogue` | Sprint 15 / FPRM-239. Volume discount bands applied to Transactional and Limited Technician users. Columns: `id` (UUID PK), `min_users` / `max_users` (Integer; `max_users` null = unbounded top band), `transactional_user_discount_pct` / `limited_tech_user_discount_pct` (Numeric(5,2)), `is_active` (bool default true). Seeded with 6 rows (1-10, 11-50, 51-100, 101-300, 301-500, 500+) at 0/30/40/50/60/70%. |
| `addon_catalog_items` | `023_create_pricing_catalogue` (+ `028_addon_category_sort_order` in Sprint 20) | Sprint 15 / FPRM-239. Catalogue of add-ons selectable for Starter / Professional. Columns: `id` (UUID PK), `addon_key` (unique string), `display_name`, `monthly_price` (Numeric(10,2)), `available_starter` / `available_professional` (bool), `included_enterprise` (bool default true), `is_active` (bool default true). Seeded with 21 rows per the spec add-on table. **Sprint 20 / FPRM-318 (migration 028) added 2 columns**: `category` (String, nullable — admin-assigned via PATCH, never seeded per AD-25) and `sort_order` (Integer NOT NULL, default 0, `server_default='0'` for the backfill on existing 68 rows). Default GET ordering is `(category NULLS LAST, sort_order, display_name)`. |
| `quotes` | `024_create_quotes` | Sprint 15 / FPRM-239. Quote header bound to a deal_registration. Columns: `id` (UUID PK), `deal_id` (UUID FK to `deal_registrations.id`, not null), `partner_org_id` (FK), `created_by` (FK users), `quote_name` (nullable), `currency_code` (String(3) default `USD` — display only, no FX conversion in Phase 5), `active_version` (Integer default 1), `active_scenario` (nullable), `status` (`draft`/`sent`/`accepted`/`expired` default `draft`), `created_at`, `updated_at`. Index on `deal_id`. |
| `quote_versions` | `024_create_quotes` | Sprint 15 / FPRM-239. Versioned pricing snapshot. Columns: `id` (UUID PK), `quote_id` (FK), `version_number` (Integer), `scenario_label` (nullable: `good`/`better`/`best`/null), `feature_plan` (string), `feature_plan_discount_pct` (Numeric(5,2) default 0), `qty_transactional_users`/`qty_limited_tech_users` (Integer), `selected_addons` (JSON list of addon_key strings), `grand_total_before_discount`/`grand_total_after_discount` (Numeric(12,2)), `pdf_artifact_path` (nullable — Sprint 16), `created_at`, `is_deleted` (bool default false — soft-delete). Unique constraint `(quote_id, version_number)`; index on `quote_id`. |
| `quote_line_items` | `024_create_quotes` | Sprint 15 / FPRM-239. Individual line items computed by `quote_engine.calculate_quote`. Columns: `id` (UUID PK), `quote_version_id` (FK), `line_order` (Integer), `line_type` (`feature_pack`/`transactional_user`/`limited_tech_user`/`addon`/`free_allocation`), `description`, `quantity`, `unit_price` (Numeric(10,2)), `discount_pct` (Numeric(5,2) default 0), `total_before_discount`/`total_after_discount` (Numeric(12,2)), `addon_key` (nullable — set when `line_type == 'addon'`). Index on `quote_version_id`. |
| `approval_step_records` | `026_create_approval_step_records` | Sprint 17 / FPRM-274 (AD-22). Per-step audit trail for the multi-step approval workflow. Columns: `id` (UUID PK), `workflow_type` (`partner_application` / `deal_registration`), `object_id` (UUID — polymorphic; no FK since it can reference either parent table), `step_order` (Integer), `step_name` (String — snapshotted at action time), `required_role` (String — snapshotted), `actor_id` (FK `users.id`), `action` (`approved` / `rejected` / `info_required`), `notes` (Text nullable), `actioned_at` (DateTime). Indexes on `object_id` and `(workflow_type, object_id)` for back-reference reads. |
| `deal_registrations.qty_*` columns | `029_add_license_qty_to_deal_registrations` | Post-Sprint-20 (PRs #128–#163). Adds `qty_transactional_users` (Integer, nullable) and `qty_limited_tech_users` (Integer, nullable) to `deal_registrations` so the deal form can capture user counts at deal-creation time instead of only at quote time. Originally noted as a Sprint 20 spec deviation — addressed here. Backfill leaves existing rows null; the quote engine continues to read user counts from `quote_versions` (AD-18) so historical quotes are unaffected. The migration also confirms `customer_contact_position` lands on the model. |
| `deal_registrations.customer_contact_position` | `030_add_customer_contact_position` | Post-Sprint-20 hotfix. Adds the `customer_contact_position` (String, nullable) column that migration 029 attempted but missed on certain SQLite test paths. Idempotent — uses `IF NOT EXISTS` guard. Carries no other schema changes. |
| `commission_structures.is_active` + timestamps | `031_extend_commission_structures` | Post-Sprint-20 (PR #142). Adds `is_active` (Boolean NOT NULL, `server_default='true'` so the backfill flips existing rows to active) plus `created_at` / `updated_at` (DateTime, `server_default=NOW()`) to `commission_structures`. Unblocks the Commission Rates admin tab (soft-delete + audit timestamps). Per AD-25, commission catalogue entries are admin-maintained data after this migration; new migrations are not required to add or deactivate rates. |
| `quotes.include_in_pipeline` + `quote_versions.includes_software` / `includes_services` | `032_pipeline_toggle_and_quote_composition` | Post-Sprint-20 (PRs #147 + #149 + #153). Adds `quotes.include_in_pipeline` (Boolean NOT NULL, `server_default='true'`) — every existing quote backfills to True so per-deal `pipeline_total` aggregations remain stable post-deploy. Also adds `quote_versions.includes_software` and `quote_versions.includes_services` (both Boolean NOT NULL, `server_default='true'` / `server_default='false'` respectively) so quotes can flag their composition for future services-quote work. The aggregation helper in `deal_registrations_router._compute_pipeline_total` reads `include_in_pipeline` exclusively — `estimated_deal_value` is no longer summed into pipeline totals. |
| `quote_documents` | `033_create_quote_documents` | Post-Sprint-20 (PR #158). New table for documents attached to a quote (signed acceptance PDFs, addenda, supporting collateral). Columns: `id` (UUID PK), `quote_id` (UUID FK to `quotes.id`, indexed), `document_type` (String — open vocabulary; the acceptance gate matches `'signed_acceptance'`), `document_name` (String), `file_data_base64` (Text — base64-encoded blob per AD-19; large quotes may push toward S3 in a later phase), `mime_type` (String, nullable), `file_size_bytes` (Integer, nullable), `uploaded_by_user_id` (FK `users.id`), `uploaded_at` (DateTime), `is_deleted` (Boolean NOT NULL default false — soft delete). Index on `quote_id`. Acceptance gate (router-level, not a constraint): `PATCH /quotes/{id}/status` rejects `sent → accepted` unless at least one non-deleted `QuoteDocument` exists with `document_type='signed_acceptance'`. |



**Migration strategy:** Alembic with `alembic upgrade head` as Railway pre-deploy command on `fracttal-prm-backend`.



**Key rules:**

- Every new table requires an Alembic migration — never use SQLAlchemy `create_all()` directly in production

- All migration `upgrade()` functions must be idempotent — use `if_not_exists=True` and existence checks

- When introducing Alembic to an existing database, run `alembic stamp head` first to initialise migration history without running DDL

- Migration files live in `backend/alembic/versions/` — Claude Code reads and modifies them via GitHub Contents API (no local checkout required)

- New migration files committed to the repo are picked up and applied automatically on the next Railway deploy — no manual intervention required



---



## 3. Component Structure & Data Flow



> Populated as frontend components are built.



### Backend (`backend/`)



Flat module layout — all Python source files sit directly in `backend/`. No `src/` subdirectory, no `__init__.py` files. Tests go in `backend/tests/`. Imports are flat: `from models import ...`



**Auth + RBAC dependency pattern (Sprint 3 canonical).** Use these imports for any new router that needs authentication or permission gating:



```python

from auth import get_current_user

from permissions import require_permission, apply_tenant_filter

from field_visibility import filter_sensitive_fields

```



| Need | Use |

|---|---|

| Authenticated route, no permission check | `Depends(get_current_user)` |

| Authenticated + permission required | `Depends(require_permission("resource:action"))` — returns 403 if role lacks permission |

| Partner-tenant scoping on a query | `query = apply_tenant_filter(query, current_user, ModelClass)` — partner roles filtered to own `partner_org_id`, internal roles see all |

| Strip sensitive fields from response | `data = filter_sensitive_fields(model_dict, current_user)` — strips `margin_pct`/`internal_notes`/`cost_price` from partner-side responses |



Permission strings follow `{resource}:{action}` — see `permissions.PERMISSIONS` for the full matrix. Don't duplicate the auth check inside the handler — `require_permission` handles 401 (no token, expired token, unknown role) AND 403 (token valid but role insufficient).



### Frontend (`frontend/src/`)



Vite + React 18, with `react-router-dom@^6` for client-side routing (introduced in Sprint 5).



```

frontend/src/

├── main.jsx                         # ReactDOM root, wraps <App/> in <BrowserRouter>; imports Fracttal One tokens

├── App.jsx                          # Top-level <Routes>: /, /login, /register, /register/confirmation, /resume-application, /accept-invite, /portal/* (nested under PartnerPortalLayout including /portal/deals* and /portal/commissions — Sprint 10), /internal/applications, /internal/applications/:id, /internal/partners/:id/profile, /internal/partners/:id/documents, /internal/deals

├── styles/

│   └── tokens.css                   # Sprint 8 / FPRM-122 — Fracttal One design system: CSS custom properties (Inter font, #1A6EBB primary, #F5F7FA sidebar, status colours, spacing scale, radius) + utility classes (fp-btn, fp-card, fp-badge, fp-table, fp-modal, fp-field floating-label inputs, fp-shell portal chrome, fp-tile dashboard cards, fp-progress, fp-checklist, fp-page wrappers, fp-alert)

├── layouts/

│   └── PartnerPortalLayout.jsx      # Sprint 7 / FPRM-105 → restyled in Sprint 8 / FPRM-122 → Commissions enabled in Sprint 10 / FPRM-158. Left sidebar with icon + label nav (Home, Profile, Documents, Register a Deal, My Pipeline, Commissions; Training/Assets/Support still disabled until later sprints), top header with breadcrumb left + org name / email / logout right, mobile hamburger drawer.

├── components/

│   ├── ProtectedRoute.jsx           # JWT auth guard - decodes localStorage 'token', redirects to /login if missing/invalid or role not in allowed list

│   └── ActivationChecklist.jsx      # Sprint 7 / FPRM-107 → restyled Sprint 8 / FPRM-122. Card with progress bar + fraction (3 / 3), per-item left colour indicator (green when done) and call-to-action links.

└── pages/

    ├── Login.jsx                    # Sprint 7 / FPRM-105 → restyled Sprint 8 / FPRM-122 — centred Fracttal-branded auth card, floating-label inputs, primary blue button.

    ├── AcceptInvite.jsx             # Sprint 7 / FPRM-105 → restyled Sprint 8 / FPRM-122 — same auth card style, floating labels.

    ├── PartnerHome.jsx              # Sprint 7 / FPRM-105 → restyled Sprint 8 / FPRM-122 — welcome header + status badge + activation progress bar + ActivationChecklist + dashboard tile grid; "Register a Deal" tile **unlocked** and routes to /portal/deals/new.

    ├── PartnerProfile.jsx           # Sprint 7 / FPRM-106 → restyled Sprint 8 / FPRM-122 — adapts to /portal/profile and /internal/partners/:id/profile. Floating-label edit form, save button top-right, completeness progress bar + badge.

    ├── PartnerDocuments.jsx         # Sprint 7 / FPRM-108 → restyled Sprint 8 / FPRM-122. Top-right upload button opens a modal; table with status badge chips (approved=green, pending_review=yellow, rejected=red); internal Approve/Reject inline actions; reject modal requires review_notes.

    ├── DealRegistrationForm.jsx     # Sprint 8 / FPRM-131 — two-section form (Customer / Deal) at /portal/deals/new and /portal/deals/:id/edit. Floating-label inputs, industry/country dropdowns, Save-as-draft + Submit (Submit calls Save first, then POST /submit). 412 response surfaces an inline activation banner with link to /portal/home. Successful submit sets a sessionStorage toast and redirects to /portal/deals. Sprint 10 / FPRM-158 — commission_type vocabulary aligned with commission_structures (autonomous_sell / indirect_sell / direct_sell / co_sell_shared); fetches `/partners/{id}/commission-rates` on mount and shows "Applicable rate (Year 1): X%" helper text below the dropdown, falling back to "Rate not on file for this commission type" or silently omitting if the fetch fails.

    ├── CommissionRates.jsx          # Sprint 10 / FPRM-158 — partner-facing commission table at /portal/commissions inside PartnerPortalLayout. Pulls `GET /partners/{id}/commission-rates` using the JWT's partner_org_id and renders a Fracttal One table (Commission Type | Year | Rate | Notes). Header reads "Your Commission Rates — [Partner Category]". Empty state: "No commission rates found for your partner category.".

    ├── DealList.jsx                 # Sprint 8 / FPRM-131 — partner pipeline at /portal/deals. Status badge chips (draft=grey, submitted=blue, under_review/info_required=yellow, approved=green, rejected=red, expired=grey), USD-formatted value, link to edit. Empty state with CTA, success toast on first render after submit. Won card updated to sum of pipeline_total (PR #176). Accepted Pipeline label corrected (PR #176). Date filter inputs re-added PR #177, wired to GET /partners/{id}/pipeline.

    ├── DealQueue.jsx                # Sprint 8 / FPRM-134 → Sprint 9 / FPRM-141+143. Internal deals page at /internal/deals. Rebuilt PR #176 to match portal/deals layout — summary cards, date filter bar, fp-table, Accepted labels, Won card dollar value. Deal name links to `/internal/deals/:id`. Actions column removed — all per-deal actions live on the detail page. Full-width layout fix PR #177. Date filter params correctly wired PR #177 (backend `list_internal_deals` does not yet honour them — TODO inline).

    ├── DealDetail.jsx               # Sprint 9 / FPRM-140 — partner-facing read-only deal detail at /portal/deals/:id. Customer + deal field display, status-specific banner, collaboration thread, info_required → message + Resubmit panel. Draft state shows "Edit draft" routing to DealRegistrationForm.

    ├── InternalDealDetail.jsx       # Sprint 9 / FPRM-141 — internal deal review page at /internal/deals/:id. Read-only fields, Commission Snapshot section (commission_structure_id + commission_rate_snapshot + commission_type), Conflict Check section (Sprint 10 / FPRM-159 adds the override UI: red "Conflict Detected ⚠️" badge + "Override Conflict" button → modal with required min-10-char override_notes that POSTs to /internal/deals/{id}/override-conflict and surfaces a transient "Conflict overridden" toast), always-on collaboration thread, status-sensitive Quick Actions panel (Start Review / Request Info / Approve / Reject with modals).

    ├── RegisterPartner.jsx          # Public 10-step partner application form (Sprint 5)

    ├── RegisterConfirmation.jsx     # Post-submit thank-you page (?ref=<application_id>)

    ├── ApplicationQueue.jsx         # Internal queue for channel_manager+ (table with status filter + search)

    ├── ApplicationReview.jsx        # Internal review detail page (Sprint 6) — read-only field view + Approve/Reject/Request-Info action panel + audit-log timeline

    ├── ApplicationResume.jsx        # Public applicant resume page (Sprint 6) — loads by ?id=&draft_token=, surfaces reviewer info_request_message, editable form, message thread, Resubmit
    │
    ├── QuoteForm.jsx                # Sprint 16 / FPRM-254 — quote create + new-version form with sticky live-preview panel; Sprint 18 / FPRM-283 — scenario selector greys out already-created labels in new-version mode and surfaces an "All 3 scenarios created" hint.
    ├── QuoteDetail.jsx              # Sprint 16 / FPRM-254 — version browser + line-item table + status state machine + PDF generate/download; Sprint 18 / FPRM-283 — scenario comparison panel between Versions and Line Items renders only when /quotes/{id}/scenarios returns at least one entry. "Select This Option" PATCHes /active-scenario then /active-version. Version lock applies to accepted/expired/cancelled only — draft and sent remain fully editable. PR #174 fix.
    ├── InternalQuotes.jsx           # Sprint 18 / FPRM-287 — cross-deal quote dashboard at /internal/quotes. Summary card row (Total / Draft / Sent / Accepted / Pipeline Value), status / plan / search filters, paginated table; row links to /internal/deals/:id. Uses shared `utils/currency.js` for amounts.
    └── PortalQuotes.jsx             # Sprint 18 / FPRM-291 — partner-facing quote history at /portal/quotes inside PartnerPortalLayout. Read-only table with status filter; row links back to /portal/deals/:id. Internal users redirected by ProtectedRoute (partner roles only). Rebuilt PR #172 to match InternalQuotes.jsx design — 7 summary cards, full filter bar, SortableTh table, isReadOnly QuoteDetail modal, Partner column removed. QuoteDetail opens as modal overlay — PR #174 fix.

```



**Public registration flow (`RegisterPartner.jsx`).** Steps 1-10 walk through Company → Contact → Business → Reseller Experience → Technical Capabilities → Partnership Goals → References → Additional Info → Documents → Review & Submit. On Step 1 completion the form calls `POST /applications` to mint `{id, draft_token}` which is cached in component state and `localStorage` under `fprm_draft_{id}`. Every field change debounces a `PATCH /applications/{id}?draft_token=...` after 2 seconds. The Save & Continue Later panel surfaces a bookmarkable URL containing the draft token; revisiting that URL pulls the draft back in via `GET /applications/{id}?draft_token=...`. Step 10's Submit button POSTs to `/applications/{id}/submit?draft_token=...`, clears the localStorage cache, and navigates to `/register/confirmation?ref={id}`.



**Internal queue (`ApplicationQueue.jsx`).** Requires JWT with role in {`channel_manager`, `channel_ops_admin`, `system_admin`} (enforced by `ProtectedRoute`). Lists applications via `GET /applications` with optional `?status=` filter; client-side search across company name, applicant name, email. Status badge colours: submitted=blue, in_review=yellow, info_required=orange, approved=green, rejected=red. Row click routes to `/internal/applications/{id}` (review detail page lands Sprint 6).

**Internal review (`ApplicationReview.jsx`, Sprint 6 / FPRM-90).** Same auth guard as the queue. Loads `GET /applications/{id}` plus `GET /applications/{id}/timeline`, renders all application sections A–H in read-only form, with a sticky right sidebar exposing Approve / Reject (modal with required reason) / Request Info (modal with required message) buttons. Sidebar also shows the audit timeline and an internal-only reviewer notes textarea. Action buttons are disabled once status is approved or rejected.

**Applicant resume (`ApplicationResume.jsx`, Sprint 6 / FPRM-91).** Public route at `/resume-application?id=...&draft_token=...`. When status=info_required the reviewer message is highlighted at the top; below it the applicant can edit the long-form fields, exchange messages with the reviewer (`GET`/`POST /applications/{id}/messages`), and Resubmit (PATCH + POST /submit). On successful resubmit the user is routed back to `/register/confirmation?ref=<id>`.



---



## 4. CI/CD Logic & Skip Rules



### `ci.yml` Job Summary



| Job | Condition | Blocking | What it does |

|-----|-----------|----------|--------------|

| test (3.11, 3.12) | Always | Yes | pytest, skip `tests/e2e/`, upload coverage |

| security | Always | No (`--exit-zero`) | bandit scan on `backend/` |

| sonarcloud | main push only | No (continue-on-error) | Full code analysis |

| playwright | main push only | No (continue-on-error) | E2E against live backend |

| deploy | main push only | No | Railway GraphQL API `serviceInstanceRedeploy` mutation |



### Blocking CI Jobs (will prevent auto-merge)



- `test` matrix jobs (Python 3.11 and 3.12)

- `security` scan (bandit)



### Non-Blocking CI Jobs



- SonarCloud analysis — triggered selectively from Control Centre before TEST/PROD promotion, not on every PR

- Playwright E2E — informational at this stage

- Railway deploy — runs after merge to `main`, not a pre-merge gate



### Railway Deploy (GraphQL API)



Uses `serviceInstanceRedeploy` mutation via `curl` + `jq` — no Railway CLI required (AD-21 pattern from SynPro VSDC):

- Service name: `fracttal-prm-backend` (and `fracttal-prm-frontend` for frontend deploys)

- Railway Project ID: `e5c41b7a-b96c-449d-964f-aba615d4cae0`

- Full API response echoed to CI logs

- Step exits 0 on any error (non-blocking)



**GitHub Secrets required:**



| Secret | Description |

|--------|-------------|

| `PAT_TOKEN` | Personal Access Token (repo + workflow scope) |

| `RAILWAY_TOKEN` | Railway account token |

| `RAILWAY_PROJECT_ID` | `e5c41b7a-b96c-449d-964f-aba615d4cae0` |

| `SONAR_TOKEN` | SonarCloud token (optional until configured) |



### Graceful Skip



If `backend/` or `tests/` directories don't exist yet, test jobs skip without failing. This allows the CI pipeline to be committed before all directories are created.



---



## 5. Error Handling Patterns



### Backend

- Non-2xx responses raise `HTTPException` with appropriate status codes

- All routers are fully self-contained — no cross-directory imports (AD-5)

- Auth dependency: always verify exact function name in `auth.py` before using in any router

- `requirements.txt` is critical — read before writing, never remove packages



### Frontend

- API errors extracted from `error.response.data.detail` for display

- Loading states handled per-component

- JWT token stored in `localStorage` under key `"token"` — consistent across all components



### CORS

- `FRONTEND_URL=*` in Railway — required for Control Centre proxy calls to work

- `allow_credentials` must be `False` when `FRONTEND_URL=*` (CORS spec requirement)

- Bearer token auth (`Authorization: Bearer ...`) works correctly without `allow_credentials=True`



> Additional patterns documented here as they emerge sprint by sprint.



---



## 6. Architectural Decisions



These are conscious design choices — not defaults or accidents. Understanding the *why* prevents future sessions from accidentally reversing them.



---



### AD-1 · Backend uses flat module layout — no packages, no `src/` subdirectory



**Decision:** All Python source files sit directly in `backend/`. No `src/` subdirectory, no `__init__.py` files. Imports are flat: `from models import ...`



**Why:** The backend is a focused FastAPI service. A package hierarchy adds indirection without benefit. The flat layout also matches how Railway's Procfile resolves modules at startup.



**Do not:** Create `src/` subdirectories or `__init__.py` files inside `backend/`.



---



### AD-2 · No git CLI — all GitHub operations use the REST API



**Decision:** Claude Code creates branches, commits files, and opens PRs entirely via the GitHub Contents API and Git Trees API over HTTP. No `git` binary required.



**Why:** Claude Code works anywhere Python and HTTP are available. Base64 encoding handles binary-safe file content. The SHA-based update protocol replaces the need for local refs.



**Consequence:** File updates require the current blob SHA — always fetch the existing SHA before updating a file. The `read_file` step before every `stage_file` is mandatory.



---



### AD-3 · Feature branches are always recreated from `main`, never updated in place



**Decision:** Before creating a branch, delete any existing branch with the same name and recreate it fresh from the latest `main` SHA.



**Why:** Starting fresh from `main` guarantees a clean, minimal diff and eliminates merge conflicts entirely.



**Consequence:** Any work committed to a branch that has not yet been merged to `main` will be lost if Claude Code retriggers for the same ticket. The branch is ephemeral — `main` is the source of truth.



---



### AD-4 · Jira sprints tracked via fix versions, not native Agile sprints



**Decision:** Tickets are assigned to sprints using Jira's `fixVersions` field. Sprint IDs map to Jira versions pre-created before each sprint.



**Why:** Fix versions are simpler to create and query programmatically and don't require board access configuration.



**Consequence:** A dual JQL query is always needed: `fixVersion = {fix_id} OR sprint = {native_id}`. Neither field alone is reliable. Always pre-create the fix version manually and verify before sprint setup.



---



### AD-5 · `backend/` is a self-contained service — no cross-directory imports at runtime



**Decision:** Every Python file in `backend/` must import only from stdlib, pip-installed packages in `backend/requirements.txt`, and other files within `backend/` itself.



**Why:** Railway deploys `backend/` as a standalone service. No other project directories exist on the Railway filesystem at runtime. Cross-directory imports crash the service at startup silently until the first request hits the broken router.



**Do not:** Use `sys.path.insert` to import from parent directories — it does not work in Railway. Inline the logic as local helpers instead.



---



### AD-6 · Jira API calls proxied through the shared SynPro VSDC backend



**Decision:** The Control Centre never calls Jira directly for Fracttal PRM data — all Jira requests go through `/proxy/jira/*` on the shared SynPro VSDC UAT backend (`https://synpro-virtual-dev-team-production.up.railway.app`), with `product_id` identifying the Fracttal PRM product record.



**Why:** Jira's REST API does not set permissive CORS headers, blocking direct browser-to-Jira calls. The shared proxy pattern avoids duplicating proxy infrastructure across products.



**Consequence:** The SynPro VSDC backend must be running and accessible for Fracttal PRM's Control Centre data to load. The Fracttal PRM product record in the SynPro VSDC database must have correct credentials.



**Do not:** Add direct Jira calls to the Control Centre frontend. The proxy pattern is load-bearing.



---



### AD-8 · `models.py` uses portable SQLAlchemy types; migrations use PostgreSQL-native types



**Decision:** All Column definitions in `backend/models.py` use generic SQLAlchemy types (`Uuid`, `JSON`) rather than PostgreSQL-dialect types (`UUID`, `JSONB`). Alembic migration files, on the other hand, use `postgresql.UUID(as_uuid=True)` and `postgresql.JSONB` since the target is always PostgreSQL on Railway.



**Why:** CI tests run against a fresh sqlite database created via `Base.metadata.create_all(...)`. Dialect-specific column types crash on sqlite (the original FPRM-35 incident in Sprint 2). Migration files only ever run against PostgreSQL via `alembic upgrade head` on Railway, so they can use the native, more efficient types.



**Do not:** Import from `sqlalchemy.dialects.postgresql` inside `models.py`. If a feature genuinely needs JSONB-specific operators, gate it on the engine type at runtime rather than baking dialect-specific types into the model definition.



---



### AD-9 · Public + tenant-scoped + internal-only permission tiers



**Decision:** Every new endpoint falls into one of four tiers:



| Tier | Pattern | Examples |

|---|---|---|

| Public | No auth dependency | `GET /health`, `POST /auth/register`, `GET /config/partner-categories` |

| Authenticated, tenant-scoped | `Depends(get_current_user)` + manual `partner_org_id` check for partner roles | `GET /partners/{id}`, `GET /partners/{id}/documents`, `GET /partners/{id}/activities` |

| Permission-required | `Depends(require_permission("resource:action"))` | `POST /partners`, `GET /admin/audit-log` |

| Internal-only | `Depends(get_current_user)` + manual `INTERNAL_ROLES` check OR a permission only internal roles hold | `PATCH /partners/{id}/documents/{doc_id}`, `GET /config/commission-structures` |



**Why:** Most endpoints have a mixed permission story — for example, partner_admin can update their *own* org but not others. A single declarative permission string doesn't capture "own org only" — that requires an explicit comparison against `current_user.partner_org_id` in the handler. The `require_permission(...)` dependency handles purely-role-based gates; tenant scoping always lives in the handler.



**Do not:** Try to fold tenant scoping into `require_permission`. Keep `require_permission` for role-based 403s; check tenant identity in handler bodies.



---



### AD-10 · Sub-tasks inherit fix-version and native sprint from their parent — never set explicitly on Sub-task issues



**Decision:** When creating Sub-tasks via the Jira REST API, do not include `fixVersions` or `customfield_10020` (sprint) fields in the payload. Jira rejects subtask creates that set these fields directly.



**Why:** Jira treats subtasks as fully owned by their parent — sprint and fix-version assignment cascade automatically. Setting them on the subtask returns `HTTP 400 — "Issue is a subtask and subtasks cannot be associated to a sprint"`.



**Consequence:** Subtask JQL queries by sprint still work — Jira surfaces the parent's sprint membership on the subtask. The `fixVersion = X OR sprint = Y` dual-query from AD-4 catches subtasks correctly.



---



### AD-11 · Draft token pattern — per-application secret for unauthenticated access



**Decision:** Public partner-application endpoints authenticate via a per-application `draft_token` query parameter rather than a JWT. The token is minted at `POST /applications` (returned alongside the new application id), stored as a unique column on `partner_applications`, and required on every subsequent `PATCH /applications/{id}`, `POST /applications/{id}/submit`, and `POST /applications/{id}/documents` call. `GET /applications/{id}` accepts either `?draft_token=` (public) or a Bearer JWT with `partner_application:read_all` (internal). The token has a 30-day TTL enforced by `draft_expires_at`; an expired token returns 410.



**Why:** Applicants are external prospects who don't yet have user accounts — we cannot require authentication before a partner record exists, and we don't want to require account creation just to start a draft. A per-application secret threaded through the URL is simple, bookmarkable (so applicants can resume later), and limits blast radius if leaked (it only authorises that one application).



**Consequence:** Routers handling these endpoints must validate the token against the database record on every call — never trust the application id alone. The `audit_log.actor_id` column is now nullable (migration 009) because `partner_application.submitted` events have no authenticated actor; `audit.log_audit_event` records `actor_role="anonymous"` in that case.



**Do not:** Reuse draft tokens for any other resource. Never extend the public surface to mutating endpoints that affect anything outside the single application identified by `{id}`.



---



### AD-7 · SonarCloud and Railway deploy are not merge-gate checks



**Decision:** Both run with `continue-on-error: true` in `ci.yml` and are excluded from the auto-merger's blocking check list. Only unit tests (Python 3.11 + 3.12) and bandit security scan are blocking.



**Why:** SonarCloud is triggered selectively from the Control Centre before promoting a build to TEST or PROD — running it on every feature-branch PR would be redundant and costly. Railway deploy only runs after merge to `main`, so it cannot be a pre-merge gate.



**Do not:** Add SonarCloud or Railway deploy as blocking conditions in any merge-readiness logic.



---



### AD-12 · Partner provisioning is a single function in a dedicated module

**Decision:** Approval of a partner application triggers `provision_partner_from_application(db, application_id, reviewer_id)` in `backend/provisioning.py`. This function — and only this function — creates the three rows that constitute an active partner: `PartnerOrganization`, `PartnerProfile`, `PartnerUserInvite` (partner_admin, 7-day expiry, hex token). It also links `application.partner_org_id`, sets `reviewer_id` and `reviewed_at`, and is idempotent on `application.partner_org_id` so re-running it on an already-provisioned application is safe.

**Why:** The provisioning sequence is load-bearing — getting it wrong leaves orphan organisations or missing invites and silently breaks the partner-onboarding handoff. Concentrating it in one function keeps the rules in one place, makes it testable in isolation (no router, no JWT, no audit-log noise), and prevents future state-change endpoints from accidentally re-implementing partner creation.

**Consequence:** `applications_router.approve_application` imports `provision_partner_from_application` lazily (inside the function body) so the router stays importable even when `provisioning.py` is missing during partial deploys. Audit logging stays in the router; provisioning never writes to `audit_log` itself.

**Do not:** Inline the provisioning logic into the approve endpoint or any other router. Do not skip the idempotency check — re-approval (manual or via retries) must not duplicate organisations.

---

### AD-13 · Email notification with dev-mode stdout fallback

**Decision:** `backend/notifications.py` wraps `smtplib` with `send_email(to, subject, body_html)`. If `SMTP_HOST` or `SMTP_USER` env vars are absent, the function prints the email content to stdout instead of attempting a connection. SMTP failures are caught and logged at error level. The function **never raises**. Every call site that triggers a notification (`POST /applications/{id}/submit | /approve | /reject | /request-info`) wraps `notify_*` in `try/except` as belt-and-braces defence so a buggy template or an SMTP outage cannot fail an API request.

**Why:** Email is a side effect that must be best-effort, not load-bearing. A hard SMTP dependency on `/applications/{id}/submit` would crash the public partner registration the first time SES credentials roll. The stdout fallback also keeps local dev, CI, and Railway preview deploys working without SMTP credentials.

**Consequence:** Production deploys need `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `CHANNEL_OPS_EMAIL`, `FRONTEND_URL` set on the `fracttal-prm-backend` Railway service. Without them the lifecycle still runs but no real emails are sent — they are logged to Railway's stdout.

**Do not:** Add new notification call sites that re-raise SMTP errors. Do not let template formatting raise inside endpoint bodies — defensive try/except in the router is mandatory.

---

### AD-14 · Activation checklist recalc is the single source of truth

**Decision:** `backend/activation.py` `recalculate_activation(db, partner_org_id)` is the only function that flips flags on `partner_activation_checklists`. It is called after:
- `PATCH /partner-profiles/{id}` (profile_completeness change → `profile_complete`)
- `PATCH /partners/{id}/documents/{doc_id}` when status flips to `approved` (`documents_uploaded`)
- `PATCH /partners/{id}` when `contract_start_date` is in the payload (`terms_signed`)
- `POST /partners/{id}/activation/recalculate` (manual recalc, internal only)

`provision_partner_from_application` creates the row with all flags False. The function also auto-creates the row on first read (`GET /partners/{id}/activation` initialises it via `recalculate_activation` if missing) — covers orgs provisioned before Sprint 7. `baseline_training_complete` is hardcoded `False` and excluded from the `activation_complete` gate until Sprint 10 wires it to real training records.

**Why:** Spreading the recalc rules across each call site invites drift — six months from now a new endpoint forgets to call recalc and partners get stuck in pending activation. Concentrating the logic in one function means a new flag only needs to be added in one place. The "best-effort" `try/except` wrapping at call sites (matching AD-13) keeps the activation recalc from blocking the primary mutation if `activation.py` has a bug.

**Consequence:** `activation_complete = True` requires `profile_complete AND documents_uploaded AND terms_signed`. Sprint 8+ deal-registration endpoints check this flag before allowing submission. The `activated_at` timestamp is set on the first transition only; subsequent recalculations that flip a flag off do NOT clear it (the partner was activated at that moment; later regression is a separate state to investigate).

**Do not:** Inline checklist flag-flipping logic into endpoint handlers. Do not call `recalculate_activation` from inside `activation.py` itself (no recursion). Do not let recalc failures break the parent mutation — always wrap in `try/except`.

---

### AD-15 · Role-based route guards in React via `ProtectedRoute`

**Decision:** Authenticated React routes are wrapped in `<ProtectedRoute roles={[...]}>`, which decodes the JWT from `localStorage['token']` and:
- Redirects to `/login` if no token or invalid token
- Redirects to `/login` if the JWT role is not in the allowed list

Partner-side routes (`/portal/*`) sit nested under `PartnerPortalLayout` which adds the chrome (top nav, sidebar, logout) and re-applies the partner-role check; internal routes (`/internal/*`) wrap the page directly. The JWT carries `partner_org_id` (FPRM-119) so the layout can fetch the user's org and pass it via `useOutletContext` to nested pages without a `/auth/me` round-trip on every navigation.

**Why:** A single guard component keeps the role check consistent across every page. A lost or expired token always lands the user on `/login` with a clear path back. Layout-level chrome (sidebar, logout) shouldn't repeat on every page.

**Consequence:** Every new partner-facing page goes under the `/portal` route with `<Route path="X" element={<MyPage />} />` inside the layout; the page uses `useOutletContext()` to access `{payload, orgName, token}`. Every internal page wraps in its own `<ProtectedRoute>` until a parallel `InternalLayout` is built.

**Do not:** Decode the JWT manually inside individual pages. Do not store the token under any key other than `'token'`. Do not bypass `ProtectedRoute` by exporting protected pages from public routes — even one bypass breaks the model.

---

### AD-16 · Authenticated CSV downloads use fetch + Blob, never `window.location.href`

**Decision:** Endpoints that return a CSV (or any other authenticated download) respond with `fastapi.Response(content=..., media_type="text/csv")` and a `Content-Disposition: attachment; filename=...` header. The frontend triggers the download via `fetch` with the `Authorization: Bearer` header, reads `response.blob()`, builds an object URL via `URL.createObjectURL(blob)`, sets `download` on a temporary `<a>` element, calls `.click()`, then revokes the URL.

**Why:** `window.location.href = "..."` or a plain anchor tag cannot send custom HTTP headers. Authenticated endpoints reject the request with 401 because they never see the JWT. The fetch+Blob pattern preserves the `Authorization` header while still triggering the browser's native Save-As dialog.

**Consequence:** Every CSV-export endpoint added in the future should follow this pattern on both sides. Don't reinvent it with `window.open` or query-string tokens.

**Do not:** Pass JWTs as query parameters to work around the header limitation. Tokens in URLs leak via referrer, browser history, and access logs.

---

### AD-17 · Report aggregations are computed at query time, not pre-aggregated

**Decision:** The `/internal/reports/*` endpoints (Sprint 14) compute every metric inline from the live `deal_registrations` / `partner_organizations` / `partner_activation_checklists` / `partner_application_documents` rows. No pre-aggregated reporting tables exist.

**Why:** At current data volumes (single-digit thousands of deals), Postgres handles the aggregations in milliseconds. A rollup table would be premature optimisation with operational cost: stale data when the rollup falls behind, an extra migration to maintain, an extra background job to operate.

**Consequence:** Acceptable through Phase 5. If deal volumes exceed ~50k or report queries start showing up in slow-query logs, introduce a nightly rollup table and switch the endpoints to read from it.

**Do not:** Add caching or memoisation to the report endpoints today — it would mask the real performance signal we'd want to see before introducing a rollup.

---



### AD-18 · `quote_engine.calculate_quote` is the single source of truth for software pricing calculations

**Decision:** All Fracttal software pricing arithmetic — Feature Pack pricing, volume-banded user lines, free Limited Technician allocation, Feature Plan discounts, add-on annualisation — is implemented exactly once, in `backend/quote_engine.py`. The engine is a pure module (no FastAPI imports, no router imports, no HTTP exceptions). It reads pricing live from `feature_plan_prices` / `volume_discount_tiers` / `addon_catalog_items`. It returns a `QuoteCalculationResult` dataclass of ordered `QuoteLineItemData` rows plus the two grand totals. Inputs that violate the spec rules raise `ValueError`. The router (`backend/routers/quotes_router.py`) is the only caller that turns those `ValueError`s into HTTP 422.

**Why:** Pricing is a high-blast-radius domain. Duplicating the rules — even partially, for "just a quick preview" or "client-side estimate" — invites drift between the engine and its mirrors. A single tested module with deterministic, side-effect-free behaviour can be exhaustively verified (21 unit tests cover all four worked examples from the Fracttal Pricing and Quotation Specification plus boundary cases). Pure imports also keep the engine importable in test code without spinning up the FastAPI app.

**Consequence:** Sprint 16's `QuoteForm.jsx` live-preview panel will implement the same rules client-side for UX latency, but the server response is authoritative — on submit, the persisted line items come from the engine, not the client preview. Future stories that touch pricing (add a new plan, change a volume band, introduce a different discount type) edit the engine and add tests; nothing else.

**Do not:** Inline pricing calculations in `quotes_router.py` or in any other router. Don't cache results across requests — pricing is read live so an admin price-table update takes effect immediately.

### AD-19 — PDF artefacts are stored as base64-encoded text on the DB row, not on the Railway filesystem

**Decision:** Generated quote PDFs (Sprint 16 / FPRM-258) are stored as base64-encoded strings in `quote_versions.pdf_artifact_data` (Text). The `POST /quotes/{id}/versions/{n}/generate-pdf` endpoint renders the PDF in-memory with reportlab and persists the bytes to the DB. The `GET /quotes/{id}/versions/{n}/pdf` endpoint reads the column, decodes, and streams it back as `application/pdf` with `Content-Disposition: attachment`.

**Why:** Railway services do not have persistent local storage across deploys. Anything written to `/tmp` or the working directory is gone the next deploy, which would silently invalidate every previously-generated PDF. Storing the artefact on the row keeps it durable, atomically tied to its `QuoteVersion`, and free for any internal/partner user with read access to download. There is no need (yet) for an S3 / object-store integration at quote-PDF sizes.

**Consequence:** Quote PDFs typically render at ~30-200 KB. At a few hundred thousand quote versions this remains well within Postgres budget. The endpoint regenerates and overwrites idempotently — calling generate-pdf again produces a fresh artefact with the current quote state. AD-19 explicitly does NOT extend to larger binaries (uploaded partner documents, application attachments, etc.) — those should use a dedicated blob store when they arrive.

**Do not:** Write generated artefacts to local disk. Do not skip the base64 round-trip and store raw bytes — the column is portable Text across SQLite (test) and Postgres (prod) only because it stays text-safe.

---

### AD-20 — Authenticated file downloads use fetch + Blob + `URL.createObjectURL`, never `window.location.href`

**Decision:** Every authenticated file download (CSV exports from Story 3, PDF downloads from Story 2) goes through the same browser-side pattern: `fetch(url, { headers: { Authorization: \`Bearer ${token}\` } })` -> `await response.blob()` -> `URL.createObjectURL(blob)` -> `<a href=url download=name>` programmatic click -> `URL.revokeObjectURL`. The pattern is implemented inline in every list page that has an Export CSV button and in `QuoteDetail.jsx` for PDF download.

**Why:** `window.location.href = '/path?token=...'` and direct anchor `href` cannot carry an `Authorization` header. Bearer tokens in the URL leak through referrer headers, browser history, and access logs. The fetch+Blob pattern sends the token correctly in the header, lets the server enforce the same auth checks as every other API call, and then materialises the binary response back into a browser download.

**Consequence:** Frontend bundles a few extra lines per page (or imports a tiny helper). The download flow shows the user the same loading/disabled-button affordances as any other fetch, which is the right UX. AD-20 supersedes any older code that used `window.location.href` for downloads — Sprint 14's reports CSV export already used fetch+Blob, AD-20 just codifies the pattern as the standard.

**Do not:** Pass the JWT as a query parameter to a download endpoint. Do not bypass the standard fetch pipeline for downloads — the auth header check matters as much for a CSV as for a JSON payload.

---

### AD-21 — Dynamic activation criteria are resolved at runtime from `activation_checklist_config`, with a hardcoded fallback

**Decision:** `backend/activation.py` `recalculate_activation` (signature frozen since Sprint 7 / AD-14) now derives the *set of required activation criteria* by querying `activation_checklist_config` for rows that match the partner's `partner_category` and `tier` (with NULL-as-wildcard for either column). The per-flag sub-computations (`profile_complete`, `documents_uploaded`, `terms_signed`, `baseline_training_complete`) are unchanged — only the gate that decides `activation_complete` is now dynamic. If no config rows match, the function falls back to the legacy four-flag rule (`HARDCODED_REQUIRED_KEYS`). A `CRITERION_KEY_MAP` translates each configured `criterion_key` to the boolean field on `PartnerActivationChecklist` that backs it; criterion keys without a model field are skipped gracefully (auto-satisfied) so admins can pre-seed criterion vocabulary that doesn't yet have model backing. The new endpoint `GET /partners/{id}/activation/criteria` surfaces the resolved criterion list + per-item met state + `config_source` so the portal can render a live, criteria-aware checklist.

**Why:** The Sprint 13 `activation_checklist_config` table existed since FPRM-213 but was never read by the enforcement function — admins could configure criteria but the enforcement function ignored them. Wiring it up was Phase 5's last enforcement gap (alongside AD-22). Backwards-compatibility was the load-bearing constraint: every existing production partner activated under the hardcoded rule, and we cannot silently lock them out. The fallback path preserves that exact behaviour when no admin-configured rows match.

**Consequence:** Adding a new criterion is now a config write, not a code change. The `CRITERION_KEY_MAP` only needs an entry when a *new model field* is introduced; alias keys (e.g. `contract_signed` → `terms_signed`) map to existing fields. The portal will surface any admin-added criterion automatically via the `/criteria` endpoint, with sensible defaults for the description and a generic "ask your channel manager" hint when no `KEY_ACTIONS` entry exists.

**Do not:** Reintroduce hardcoded criterion lists in router handlers or in the recalc engine. Do not change `recalculate_activation`'s signature — every caller passes `(db, partner_org_id)` and gets back the persisted checklist. Do not skip the fallback path — empty config rows must NOT activate every partner.

---

### AD-22 — Multi-step approval enforcement reads `approval_workflow_steps` at runtime; single-step fallback preserved

**Decision:** `POST /applications/{id}/approve` (FPRM-90 / Sprint 6) and `POST /internal/deals/{id}/approve` (FPRM-134 / Sprint 8) are now step-gated by the `approval_workflow_steps` table (migration 021, configured via `/internal/config/approval-steps` since Sprint 13). For each workflow object, the router looks up the active steps in `step_order`, finds the first step that does not yet have an `approved` `ApprovalStepRecord`, and requires the caller's role to match that step's `required_role`. Each successful step approval inserts an `ApprovalStepRecord`. **Intermediate-step approvals do not transition the object's status** — the status only flips to `approved` (and provisioning runs for applications) on the final step. Rejections at any step write an `action="rejected"` step record before flipping status to `rejected`. When no steps are configured for a workflow type, single-step legacy behaviour is preserved: any review-role user can approve directly, no step records are created, and `approval_progress` is `null` on GET responses.

The shared helpers live in `backend/approval_helpers.py` (`get_approval_step_context`, `build_approval_progress`, `record_step_action`) to avoid duplicating the logic in both routers and to keep the import graph acyclic.

**Why:** The Sprint 13 `approval_workflow_steps` table existed since FPRM-209 but was never enforced. Wiring it up closes the last Phase 4 deferral and gives admins real control over multi-stakeholder approval flows (e.g. Channel Ops Review → Channel Manager Review for high-value deals). The same backwards-compatibility constraint as AD-21 applies: existing production data assumes single-step approval; the fallback preserves it.

**Consequence:** Frontend `ApplicationReview.jsx` and `InternalDealDetail.jsx` consume `approval_progress` to render a step indicator and disable the Approve button when the logged-in user's role does not match the current step's `required_role`. The `approval_progress` block has shape `{total_steps, completed_steps, current_step_order, current_step_name, current_required_role}` — `current_*` fields are `null` once all steps are complete. The `step_name` and `required_role` columns on `ApprovalStepRecord` are *snapshotted* at action time so historical records survive future edits to `approval_workflow_steps`. The polymorphic `object_id` column carries no FK (a union-typed FK would require non-portable triggers); the back-reference is served by the `(workflow_type, object_id)` composite index.

**Do not:** Inline step-context logic in either router — both must use the helpers in `approval_helpers.py`. Do not transition object status on intermediate steps — only the final step transitions to `approved`. Do not skip the fallback path — empty `approval_workflow_steps` must NOT block approvals for legacy deployments.

---

### AD-23 — Multi-currency display is render-time formatting; numeric storage is currency-agnostic

**Decision:** `quotes.currency_code` is a display label on the Quote header only. Every monetary column (`feature_pack_annual`, `transactional_user_annual`, `limited_tech_user_annual`, `monthly_price`, `unit_price`, `total_before_discount`, `total_after_discount`, `grand_total_before_discount`, `grand_total_after_discount`) is a `Numeric` value persisted with no currency embedded. The frontend converts to a symbol-prefixed string at render time via `frontend/src/utils/currency.js` `formatCurrency(amount, code)` + `CURRENCY_SYMBOL` map (Sprint 18). The PDF generator uses the equivalent `CURRENCY_SYMBOL` map in `quotes_router.py`. No FX conversion is performed — the same numeric total simply renders with a different prefix when the Quote header is re-keyed to another currency.

**Why:** FX volatility would otherwise leak into the persisted quote totals and historical reporting. Display-only formatting keeps Phase 5 simple: a partner who wants the same software bundle priced in EUR vs USD gets the same numbers with a different symbol, and any future FX policy decision (real-time, daily, contract-locked) is a one-place change inside `formatCurrency` (or a dedicated FX engine) without rewriting any persisted rows.

**Consequence:** The currency picker in `QuoteForm.jsx` is `disabled={isNewVersion}` already — currency stays constant across a quote's lifetime to keep version comparisons meaningful. PDF and frontend share the same nine seeded currency codes (USD/EUR/GBP/AUD/CAD/ZAR/AED/SAR/EGP); adding a new currency is a single-line addition to both `CURRENCY_SYMBOL` maps with no schema change.

**Do not:** Persist currency symbols in any numeric column. Do not bake FX conversion into the quote engine — Phase 5 is explicitly display-only. Do not split `formatCurrency` into per-page helpers; the canonical implementation lives in `utils/currency.js`.

---

### AD-25 — Pricing catalogue is admin-maintainable (no Alembic migration required for price changes)

**Decision:** After Sprint 19 (FPRM-300 / FPRM-308), every row in `feature_plan_prices`, `volume_discount_tiers`, and `addon_catalog_items` is a data operation via the `/internal/config/pricing/*` admin API instead of an Alembic migration. The admin UI lives on a new "Pricing" tab inside `frontend/src/pages/ProgramConfig.jsx`. Soft-delete is the only deactivation mechanism (`is_active = False`) — rows are never hard-deleted, so the quote engine and audit history both stay coherent. Audit events are emitted on every write with action prefix `pricing.*` so `/admin/audit-log?action_prefix=pricing` surfaces the change timeline; CSV download follows AD-20 (fetch + Bearer + Blob).

Three guardrails preserve quote-engine integrity:

* **Last-active-row guard on plan prices.** `DELETE /internal/config/pricing/plans/{id}` returns 422 if the row would leave its `plan_code` with zero active rows. Add a replacement row first.
* **Range-overlap validation on volume tiers.** POST / PATCH reject ranges that intersect any other active tier. DELETE refuses (with a gap-coverage check) to leave the active set non-contiguous unless `?force=true`.
* **Effective-date scheduling on plan prices.** `quote_engine.calculate_quote` filters `effective_from <= today` so a row with a future date is stored but inert until its date — the admin UI badges those rows as "Scheduled".

**Why:** Pricing data lived inside migration 023 throughout Phase 5, which meant every price change required a code PR + CI run + Railway deploy. That cadence is incompatible with how partner pricing actually moves (commercial decisions, ad-hoc tier adjustments, scheduled annual increases). Moving the data behind an admin API keeps the schema frozen at migration 026, preserves the audit trail, and makes admin actions reversible (`is_active=True` again).

**Consequence:** All future pricing changes — new plans, new add-ons, discount adjustments, scheduled annual increases — are POSTs / PATCHes by `channel_ops_admin` or `system_admin`. Deactivations are `system_admin` only. The quote engine reads pricing live per AD-18, so changes take effect immediately for new quotes; existing `QuoteVersion` rows are never recalculated (they are snapshots at quote-creation time, by design).

**Do not:** Write a new Alembic migration to change a price. Do not hard-delete a pricing row — always soft delete via the admin API. Do not bypass the engine's `effective_from <= today` filter; scheduled rows are intentional. Do not move the `Pricing` tab into a separate page — it belongs alongside Approval Workflow / Tiers / Activation Checklist as program-config.

---

### AD-24 — Quote scenario selection is independent of version selection; latest version per label wins

**Decision:** `quotes.active_scenario` (string nullable) and `quotes.active_version` (integer) are independent fields. The two PATCH endpoints (`/active-scenario` and `/active-version`) move them separately; the partner-facing scenario-select action in `QuoteDetail.jsx` issues both calls in sequence so the active version always matches the active scenario, but the API contract does not couple them. `GET /quotes/{id}/scenarios` (Sprint 18 / FPRM-283) groups every non-deleted `QuoteVersion` by `scenario_label`, returns the highest-numbered version per label, and emits the canonical good/better/best ordering. Quotes with no scenario_label on any version return an empty `scenarios` array; the comparison UI conditionally hides the panel entirely in that state.

**Why:** Decoupling lets internal users explore scenarios without committing the active version (read-only mock-ups during a sales conversation), while the partner-facing "Select This Option" CTA keeps them in lock-step for the common case. "Latest version per label wins" means iterating on a scenario (add v4 also labelled "good") naturally supersedes the older v2 "good" without manual cleanup — partners always see the current good/better/best view.

**Consequence:** Internal `QuoteForm.jsx` (new-version mode) greys out scenario labels already present on the quote and disables the dropdown once all three exist — preventing duplicate scenarios from being added without forcing a hard error. The PDF artefact and `PortalQuoteSection` both surface the *active* scenario by name when set; the partner-facing portal is read-only — only internal write roles can PATCH `/active-scenario`.

**Do not:** Re-introduce a non-null FK between `quotes.active_scenario` and a specific `quote_versions.id` — the column is intentionally a free-form label so iteration is cheap. Do not validate that `active_version` matches the latest version of `active_scenario` — the two endpoints are independent by design. Do not extend scenario_label vocabulary without coordinating with the frontend canonical order (good → better → best).

---

### AD-26 — Filter bar layout standard

**Decision:** All list pages must render filters in a **single horizontal `fp-card` filter bar**. Layout order: filter dropdowns LEFT, search text input RIGHT (`flex: 1`), action buttons (Export CSV, Pipeline-only toggle, etc.) FAR RIGHT. Never stack filters vertically. Never wrap individual filters in labelled flex-column blocks.

**Why:** Mixed conventions (some pages vertical-stacked, some horizontal, some unwrapped) make the UI feel inconsistent and confuse the eye when bouncing between screens. The canonical layout — established by `InternalQuotes.jsx` — keeps scanning predictable: filters left, search right, actions far right.

**Reference:** `frontend/src/pages/InternalQuotes.jsx`.

**Do not:** Add a new list page with `flex-direction: column` filters. Do not split filters into multiple rows. Do not place Export CSV inside the filter bar.

---

### AD-27 — Status badge style standard

**Decision:** All status badges use a **tinted-background scheme**, never solid/opaque backgrounds. The tint tokens are:

| Family | Background | Foreground |
|---|---|---|
| approved / active | `#E6F4EA` | `#2E7D32` |
| draft / pending | `#F5F7FA` | `#555` |
| rejected / cancelled | `#FEECEC` | `#C62828` |

Other semantic tones (sent / under_review / info_required) follow the same pattern (light-tinted background, dark accessible foreground) and are encoded in the shared `StatusBadge` component.

**Why:** Solid-background badges (white text on saturated colour) are harder to scan in dense tables and clash with the muted Fracttal One palette. The tinted scheme — pioneered by `InternalQuotes.jsx` — keeps colour as semantic signal without overwhelming the row.

**Reference:** `frontend/src/pages/InternalQuotes.jsx` (`StatusBadge` component).

**Do not:** Hand-roll a status badge with `background: <solid colour>; color: white;`. Use the shared component (or replicate the tinted pattern exactly).

---

### AD-28 — Table implementation standard

**Decision:** All data tables use the `fp-table` CSS class. Column headers use the shared `SortableTh` component wherever sorting is applicable. Inline `<table style={...}>` styles are not permitted for new pages and should be migrated when nearby code is touched.

**Why:** Inline table styles fork the visual grammar — borders, header background, padding, row hover — and accumulate drift across pages. A single CSS class plus a shared sortable header component keeps tables interchangeable and lets a future restyle land in one place.

**Reference:** `frontend/src/pages/DealQueue.jsx`, `frontend/src/pages/DealList.jsx`.

**Do not:** Add new list pages with inline `<table style={...}>` blocks. Do not re-implement sortable column headers — extend `SortableTh` if a new sort behaviour is needed.

---

### AD-29 — Input and select styling standard

**Decision:** All `<select>` and `<input>` elements inside filter bars share the same styling tokens:

```js
{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }
```

Date inputs use the same shape. Other inputs (form-level, modal, etc.) may use richer affordances (`fp-field` floating-label) but filter-bar controls stay on this baseline.

**Why:** Mixed padding / border tones / border-radius across filter inputs is the most visible inconsistency in the codebase. Locking the four properties keeps every filter bar visually uniform without forcing a heavier component abstraction.

**Reference:** `frontend/src/pages/InternalQuotes.jsx` (filter `<select>` / `<input>` elements).

**Do not:** Introduce a filter-bar input with different padding, border colour, border-radius, or font size. Do not omit the border (filter inputs always carry a `1px solid #E0E4EA` border).

---

### AD-30 — Export CSV button standard

**Decision:** Export CSV buttons always live **top-right in the page header**, alongside the page title or the primary action button. They are styled as discreet ghost-style buttons:

```js
{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', color: '#718096' }
```

The implementation uses the `fetch + Blob + URL.createObjectURL` pattern from AD-20 with the `Authorization: Bearer` header.

**Why:** Putting CSV export in the filter bar gives it the same visual weight as a filter, which it is not. Top-right next to the title (or near the primary CTA) groups it with other page-level actions. Discreet styling signals "secondary affordance" — the export is occasional, not constant.

**Reference:** `frontend/src/pages/InternalPartnerList.jsx` (`exportCSV` and header rendering).

**Do not:** Put Export CSV inside the filter bar. Do not style it as a primary button. Do not fall back to `window.location.href = '...?export=csv'` — the token will not travel as a header and the endpoint will 401 (this also restates AD-20).

---

### AD-31 — Summary cards rule

**Decision:** Summary metric cards (`SummaryCard`-style horizontal strip) belong on **data-aggregation pages** (Quotes, Deals pipeline) and are **legitimately absent** on roster / management pages (Users, Partner Users, Partners list).

**Why:** Summary cards are useful when the page is about money or volume — quote totals, pipeline values, deal counts. On a Users list, a strip of "Total: 42, Active: 38" cards is noise. The distinction keeps cards meaningful: their presence telegraphs "this page summarises business state," their absence telegraphs "this page is a roster."

**Reference:** `frontend/src/pages/InternalQuotes.jsx` (cards present), `frontend/src/pages/InternalUsers.jsx` (cards intentionally absent).

**Do not:** Add summary cards to roster / management pages just for visual symmetry. Do not omit summary cards on a new aggregation page — the precedent is set.

---

### AD-32 — `fp-card` wrapper standard

**Decision:** All filter bars, form sections, and content panels are wrapped in the `fp-card` CSS class. Raw `<div>` blocks with inline `border` / `padding` are not permitted for content panels — they fork the panel grammar (radius, shadow, spacing).

**Why:** The `fp-card` class is the single Fracttal One panel primitive. Bare divs with hand-rolled padding don't match the radius / shadow / border-colour of nearby cards and read as "almost the same, slightly off." One class, one panel grammar.

**Reference:** `frontend/src/pages/InternalQuotes.jsx`, `frontend/src/styles/tokens.css`.

**Do not:** Introduce a panel-like block with `<div style={{ border: '1px solid …', borderRadius: 6, padding: 12 }}>`. Use `<section className="fp-card">` (or `<div className="fp-card">`) instead.

---

### AD-33 — Centralised document repository

**Decision:** `partner_documents` stores the binary as base64 `file_data` (Text) following the AD-19 pattern, plus `partner_org_id` (FK, NOT NULL), `uploaded_by` (FK → users.id), `document_type` (String — free-form, not enum-constrained), `document_name`, `file_size_bytes`, `mime_type`, `notes` (nullable), `uploaded_at`, and the existing review/approval fields (`status`, `review_notes`, `reviewed_by`, `reviewed_at`, `expiry_date`).

The legacy `quote_documents` table (migration 033) is retired in Sprint 21: existing rows are backfilled into `partner_documents` + `document_references`, then the table is dropped.

**Tenant isolation (SOC II / ISO 27001 boundary):** `partner_org_id` on `partner_documents` is the hard isolation boundary. Every endpoint — read, write, download, delete — enforces `document.partner_org_id == current_user.partner_org_id` for partner roles. Internal roles may read documents scoped to an explicit `partner_id` route parameter; no endpoint ever returns documents without a `partner_org_id` filter. The `document_references` join rows are always accessed through a document that has already passed the tenant check — they never expose cross-partner data. Every document read, write, download, and delete emits an audit log event.

**Why:** Prior to Sprint 21, the system had two independent file-storage tables (`partner_documents` with a placeholder `file_path` string, and `quote_documents` with base64 `file_data`) with no cross-reference. This meant a file uploaded to a quote was invisible in the partner's document list, a document already on file could not be reused on a quote without re-uploading, and the portal/documents view was incomplete. A single repository with a reference table eliminates duplication, provides a complete document history per partner, and ensures the isolation boundary is enforced in exactly one place.

**Consequence:** The quote acceptance gate (originally on `quote_documents`) moves to `document_references`: `PATCH /quotes/{id}/status` with `status=accepted` checks for a `document_references` row with `object_type="quote"`, `object_id=<quote_id>`, `reference_type="quote_acceptance"` that resolves to a non-deleted `partner_documents` row. Uploading a document for a quote is a two-step operation: `POST /partners/{partner_org_id}/documents` (creates the file), then `POST /document-references` (links it to the quote). The picker in `QuoteDetail.jsx` can therefore show existing partner documents alongside a "Upload new" option — no re-upload required.

**Do not:** Create any new table that stores file content (`file_data` or `file_path`) outside of `partner_documents`. Do not access `document_references` rows without first verifying the parent `partner_documents.partner_org_id` against the current user's org. Do not hard-delete `partner_documents` rows that have references — soft-delete only (add `is_deleted` bool + `deleted_at` timestamp, enforce in queries). Do not add `document_type` as a Postgres ENUM — the free-string column accommodates both KYC types and transaction evidence types in one table without a migration per new type.

---

## Section 7 — Frontend Design Standards

### Reference Implementation

`frontend/src/pages/InternalQuotes.jsx` is the canonical reference for all list page layouts. When in doubt about a layout decision on a list page, mirror this file.

### List Page Layout Template

Every list page follows this structure:

1. **Page header row** — title (left) + primary action + Export CSV (right).
2. **Summary cards strip** (optional — data-aggregation pages only, per AD-31).
3. **Filter bar** — single `fp-card`: dropdowns LEFT, search RIGHT (`flex: 1`), toggles FAR RIGHT (AD-26).
4. **Data table** — `fp-table` class, `SortableTh` headers, tinted `StatusBadge`, consistent currency formatting (AD-28, AD-23).

### Shared Components

- `SortableTh` — sortable column header with ↕/↑/↓ glyph and `aria-sort` attribute. Source: `frontend/src/components/SortableTh.jsx`.
- `StatusBadge` — tinted-background status chip (AD-27).
- `formatCurrency(amount, currencyCode)` — currency formatting with symbol map. Source: `frontend/src/utils/currency.js`.
- `formatMoney(amount)` — whole-dollar formatting for pipeline / deal values (the partner-portal variant; same module).

### Color Tokens

- Primary: `#1A6EBB`
- Background: `#F5F7FA`
- Border: `#E0E4EA`
- Text muted: `#718096`
- Success: `#2E7D32` (tint: `#E6F4EA`)
- Warning: `#B7791F` (tint: `#FEFCE8`)
- Danger: `#C62828` (tint: `#FEECEC`)
- Font: Inter

### CSS Classes

- `fp-card` — content panel wrapper (AD-32).
- `fp-table` — data table (AD-28).
- `fp-btn--primary` — primary action (`#1A6EBB`).
- `fp-btn--ghost` — secondary / outline.
- `fp-btn--export-csv` — discreet export button (AD-30).

### Page-Specific Exceptions

- **`DealQueue.jsx`** — tab-based status filter (not a dropdown) is acceptable for workflow pages where the status transitions drive the user's attention.
- **`DealList.jsx`** — dual Kanban / List view mode is a valid extension on top of the standard list table.
- **Summary cards absent on `InternalUsers.jsx`, `PartnerUserManagement.jsx`, `InternalPartnerList.jsx`** — these are roster pages, not aggregation pages (AD-31).

---

## Appendix — Environment Variables



### Required for Backend (Railway `fracttal-prm-backend` service variables)



| Variable | Value | Description |

|----------|-------|-------------|

| `DATABASE_URL` | Auto-provisioned | PostgreSQL connection string |

| `JWT_SECRET` | Generate strong random string | JWT signing secret — never change after first deploy |

| `JWT_EXPIRY_HOURS` | `168` | Token lifetime (7 days) |

| `FRONTEND_URL` | `*` | CORS allowed origins |

| `ANTHROPIC_API_KEY` | From console.anthropic.com | Claude API key |

| `JIRA_BASE_URL` | `https://synproconsulting.atlassian.net` | Jira instance URL |

| `JIRA_EMAIL` | `synproconsulting@gmail.com` | Jira service account email |

| `JIRA_API_TOKEN` | Rotate at id.atlassian.com | Jira API token |

| `JIRA_PROJECT_KEY` | `FPRM` | Jira project key |

| `JIRA_BOARD_ID` | `67` | Jira Agile board ID |



### Required for CI (GitHub Secrets on `Fracttal-PRM` repo)



| Secret | Description |

|--------|-------------|

| `PAT_TOKEN` | Personal Access Token (repo + workflow scope) |

| `RAILWAY_TOKEN` | Railway account token (personal, not project-scoped) |

| `RAILWAY_PROJECT_ID` | `e5c41b7a-b96c-449d-964f-aba615d4cae0` |

| `SONAR_TOKEN` | SonarCloud token (add when SonarCloud is configured) |

