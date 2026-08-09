# Access Roles concurrency QA — Odoo 19

## Why this exists

The current Odoo 19 `access_roles` module rebuilds several registries from
`_register_hook()`. That startup path can execute concurrently when multiple
workers initialize the same database. Upstream PR #419 proposes coordination,
but its new mixin is OPL-licensed. This repository must not copy that code.

## Decision gate

Do **not** add advisory locks until the failure is reproduced against this
19.0 branch. The goal of this QA is to distinguish a real Odoo 19 concurrency
bug from a stale Odoo 17 concern.

## dev1 reproduction

1. Check out the PR SHA and update/install `access_roles` in an isolated QA DB.
2. Configure Odoo with at least 4 workers and a PostgreSQL log level sufficient
   to capture serialization/deadlock errors.
3. Restart the Odoo service repeatedly and perform at least 10 cold registry
   initializations of the same QA database.
4. In parallel, run two or more module-update processes against the same QA DB
   only if the environment is disposable.
5. Capture Odoo and PostgreSQL logs around registry initialization.
6. Verify these models after each run:
   - `button.registry`
   - `filter.registry`
   - `groupby.registry`
   - `tab.registry`
7. Compare record counts and duplicate-key/serialization/deadlock errors across
   runs.

## PASS

Mark the concurrency concern `NOT_REPRODUCED_19` when all repeated cold starts
and safe concurrent updates complete without serialization/deadlock errors and
registry counts remain stable.

## FAIL / implementation trigger

Mark it `REPRODUCED_19` when logs show concurrent transaction failures or the
registry tables become inconsistent. Only then open a focused implementation
PR using a clean-room coordination design. Candidate strategies, in order:

1. avoid writes in `_register_hook` entirely and move rebuild to an explicit,
   idempotent post-install/post-upgrade operation;
2. make registry population transactionally idempotent with database-enforced
   uniqueness/upserts where appropriate;
3. if coordination is still required, implement a small PostgreSQL advisory
   transaction lock from first principles, with tests proving no deadlock and
   no permanently skipped required rebuild.

## Required evidence

Attach `artifacts/access-roles-concurrency/audit.json`, Odoo logs, PostgreSQL
errors (if any), worker count, Odoo SHA, module SHA, DB name (redacted if
needed), record counts and final decision: `NOT_REPRODUCED_19` or
`REPRODUCED_19`.
