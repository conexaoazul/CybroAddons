# Access Roles concurrency handoff (Odoo 19)

## Why this exists

`access_roles` currently performs five independent registry rebuild operations from `_register_hook()` during registry/module loading. Upstream PR `CybroOdoo/CybroAddons#419` reports serialization failures under multiple workers and proposes PostgreSQL advisory locking, but its new coordinator file is OPL-licensed. We therefore do not copy that implementation.

The Git-side probe in `scripts/access_roles_concurrency_probe.py` documents the current Odoo 19 hazard. The remaining step is runtime reproduction on a disposable QA database before implementing an AGPL-native coordinator.

## dev1 runtime QA

Use a disposable Odoo 19 QA database with `access_roles` installed. Do not run this against production.

1. Record the current SHA and worker configuration.
2. Upgrade `access_roles` once with a single worker and save the log as the control case.
3. Repeat the same registry/module-load path with multiple workers/processes starting concurrently.
4. Search logs for PostgreSQL serialization/deadlock errors, duplicate registry writes, failed view regeneration, aborted transactions, or partial registry tables.
5. Verify counts and basic integrity for `button.registry`, `filter.registry`, `groupby.registry`, `tab.registry`, and the generated access-role groups view.
6. Run the scenario at least 5 times. A single clean run is not proof that contention is absent.
7. Attach logs, exact commands, worker count, DB name (sanitized if needed), SHA, and pass/fail evidence to the PR.

## Decision gate

- **If the failure reproduces:** implement one AGPL coordinator that schedules the rebuild after commit, acquires a transaction-scoped PostgreSQL advisory lock, uses a fresh cursor/environment, rebuilds the five derived structures once, and emits duration/skip/failure logs.
- **If it does not reproduce:** do not add locking yet. Keep the probe and record the tested concurrency envelope.

## Guardrails for the implementation PR

- no source copied from the OPL coordinator in upstream #419;
- rely only on the concurrency pattern and PostgreSQL/Odoo public APIs;
- preserve Odoo 19 `env.cr.postcommit` semantics;
- no global/session advisory lock; use transaction-scoped locking;
- do not silently swallow rebuild failures;
- runtime QA must demonstrate both two-process contention and normal single-process module upgrade;
- rollback plan is removal of the coordinator and restoration of the existing hooks.
