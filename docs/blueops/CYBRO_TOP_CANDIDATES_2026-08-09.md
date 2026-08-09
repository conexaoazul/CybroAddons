# CybroAddons high-value candidate queue — 2026-08-09

This queue seeds the automated radar with a manually verified first pass over upstream PRs. It is not an instruction to cherry-pick blindly.

## Tier A — advance first

### PR #422 — auto_database_backup reliability fixes

**Upstream:** `CybroOdoo/CybroAddons#422`  
**Base:** `19.0`  
**Scope:** 1 file, +61/-15  
**Why it matters:** prevents stale error state and leaked backup temp files, including cleanup after abnormal termination; upstream author reports production validation on Odoo 19.  
**Current fork overlap:** the refactored `19.0` implementation already clears `generated_exception` in `_finalize_run()` after a successful backup. The remaining useful delta is temporary-file hygiene, especially the S3 path and recovery after abnormal worker termination.  
**Decision:** `EXTRACT_REMAINING_DELTA`, not a direct cherry-pick.  
**Guardrail:** do not blindly sweep generic `/tmp/tmp*` entries. Prefer Odoo-backup-owned temp prefixes/context managers and cleanup rules that cannot delete unrelated process data.  
**QA:** install/update, successful backup, forced failed upload, recovery to green state, interrupted backup, temp cleanup, disk-usage observation.

### PR #419 — access_roles multi-worker serialization protection

**Upstream:** `CybroOdoo/CybroAddons#419`  
**Base:** `17.0`  
**Scope:** 8 files, +82/-48  
**Why it matters:** uses PostgreSQL advisory transaction locking to prevent concurrent registry-population serialization errors. This pattern is relevant to multi-worker/self-hosted Odoo reliability and permission management.  
**Decision:** `REIMPLEMENT_AFTER_19_REVIEW`  
**Destination:** only if the same concurrency hazard exists in our Odoo 19 access-role implementation.  
**QA:** reproduce with multiple workers; prove no deadlock, no skipped required initialization and correct retry/startup behavior.

## Tier B — already absorbed or consolidate first

### PR #413 — provider-neutral S3-compatible backups

**Upstream:** `CybroOdoo/CybroAddons#413`  
**Base:** `18.0`  
**Scope:** 3 files, +157/-1  
**Current fork overlap:** `19.0` already exposes `aws_endpoint_url` and `aws_region`, builds boto3 clients through `_get_s3_client_kwargs()`, labels the destination as `Amazon S3 / S3-Compatible`, and provides a connection test.  
**Decision:** `ALREADY_ABSORBED`; retain only as provenance/QA inspiration.  
**QA follow-up:** MinIO/R2/Wasabi-compatible endpoint smoke, credentials failure, upload/download, path isolation and secret redaction.

### PR #423 — crm_dashboard full i18n including pt_BR

**Upstream:** `CybroOdoo/CybroAddons#423`  
**Base:** `19.0`  
**Scope:** 17 files, +3802/-100, mostly localization assets  
**Why it matters:** fixes locale-sensitive month/activity labels and adds pt_BR among multiple languages.  
**Decision:** `EXTRACT` only if `crm_dashboard` remains part of the canonical CRM experience.  
**Guardrail:** do not import thousands of translation lines into a dashboard we plan to replace or consolidate.

### PR #401 — REST API serialization and GET query parameters

**Upstream:** `CybroOdoo/CybroAddons#401`  
**Base:** `18.0`  
**Intent:** API-key auth compatibility, safer serialization, ISO date/datetime, binary handling, GET query params and logging.  
**Current caveat:** GitHub currently reports this PR with no changed files even though its description is useful.  
**Decision:** `PATTERN_ONLY`; do not port directly from this PR until a concrete diff/SHA is available. Compare the ideas against our API/control-plane architecture and Odoo 19 native API capabilities.

## Tier C — idea source, not near-term merge

### PR #299 — direct pip packaging

**Upstream:** `CybroOdoo/CybroAddons#299`  
**Base:** `16.0`  
**Scope:** 1635 files, +5717/-1  
**Why it matters:** packaging addons for pip can improve immutable builds and dependency management.  
**Decision:** `REIMPLEMENT_AS_BUILD_PATTERN`, never cherry-pick wholesale. The blast radius is too large and the target is old.

## Recommended sequence

1. Finish only the missing #422 temp-lifecycle delta in a focused Odoo 19 PR; do not re-port the stale-error fix that already exists.
2. Mark #413 as absorbed and add provider-neutral S3 smoke coverage instead of duplicating code.
3. Reproduce the #419 concurrency failure against our Odoo 19 worker model before writing code.
4. Treat #401 as architecture input for API hardening, not donor code in its current PR state.
5. Adopt #423 only where it survives CRM dashboard consolidation.
6. Convert #299's packaging concept into a separate modern Odoo 19 build/distribution design if useful.
