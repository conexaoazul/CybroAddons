# CybroAddons high-value candidate queue — 2026-08-09

This queue seeds the automated radar with a manually verified first pass over upstream PRs. It is not an instruction to cherry-pick blindly.

## Tier A — advance first

### PR #422 — auto_database_backup reliability fixes

**Upstream:** `CybroOdoo/CybroAddons#422`  
**Base:** `19.0`  
**Scope:** 1 file, +61/-15  
**Why it matters:** prevents stale error state and leaked backup temp files, including cleanup after abnormal termination; upstream author reports production validation on Odoo 19.  
**Decision:** `EXTRACT_OR_REIMPLEMENT`  
**Destination:** canonical backup/infra capability, not a broad Cybro dependency.  
**QA:** install/update, successful backup, forced failed upload, recovery to green state, temp cleanup, disk-usage observation.

### PR #419 — access_roles multi-worker serialization protection

**Upstream:** `CybroOdoo/CybroAddons#419`  
**Base:** `17.0`  
**Scope:** 8 files, +82/-48  
**Why it matters:** uses PostgreSQL advisory transaction locking to prevent concurrent registry-population serialization errors. This pattern is relevant to multi-worker/self-hosted Odoo reliability and permission management.  
**Decision:** `REIMPLEMENT_AFTER_19_REVIEW`  
**Destination:** only if the same concurrency hazard exists in our Odoo 19 access-role implementation.  
**QA:** reproduce with multiple workers; prove no deadlock, no skipped required initialization and correct retry/startup behavior.

### PR #413 — provider-neutral S3-compatible backups

**Upstream:** `CybroOdoo/CybroAddons#413`  
**Base:** `18.0`  
**Scope:** 3 files, +157/-1  
**Why it matters:** S3-compatible endpoint support reduces backup-provider lock-in and fits self-hosted operations.  
**Decision:** `REVIEW_FOR_PORT` after comparing our existing backup/storage stack.  
**QA:** MinIO/S3-compatible endpoint, credentials failure, connection test, upload/download, path isolation and secret redaction.

## Tier B — valuable, but consolidate first

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

1. Advance #422 first because it is small, Odoo 19-native and directly improves backup reliability.
2. Compare #413 with current backup/storage capabilities; combine only the provider-neutral endpoint feature if missing.
3. Reproduce the #419 concurrency failure against our Odoo 19 worker model before writing code.
4. Treat #401 as architecture input for API hardening, not donor code in its current PR state.
5. Adopt #423 only where it survives CRM dashboard consolidation.
6. Convert #299's packaging concept into a separate modern Odoo 19 build/distribution design if useful.
