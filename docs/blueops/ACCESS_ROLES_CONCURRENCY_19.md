# access_roles concurrency assessment for Odoo 19

## Decision

Do not cherry-pick `CybroOdoo/CybroAddons#419` into 19.0.

The current 19.0 module still performs state-changing registry work from `_register_hook()`, so the concurrency hazard class remains relevant. The upstream implementation is based on 17.0 and includes OPL-licensed coordinator code; this repository's `access_roles` module is AGPL. We therefore use the upstream PR only as behavioral evidence and reimplement independently after runtime reproduction.

## Static evidence in current 19.0

The audit inventories every `_register_hook()` in `access_roles/models` and reports calls that can mutate persistent state. Current known examples include:

- `button.registry._register_hook()` -> `get_all_buttons()` -> registry creates
- `filter.registry._register_hook()` -> `get_all_filters()` -> create/write
- `groupby.registry._register_hook()` -> `get_all_groupby()` -> create/write
- `tab.registry._register_hook()` -> `get_all_tabs()` -> registry creates
- `res.groups._register_hook()` -> `_update_role_groups_view()` -> generated view write

These hooks execute during registry/module loading, exactly when multiple Odoo workers can contend on the same database during startup or update.

## Runtime reproduction gate on dev1

Use an isolated QA database with `access_roles` installed.

1. Record current branch SHA and database name.
2. Start Odoo with at least 2 workers and normal cron workers.
3. Upgrade `access_roles` while multiple workers initialize against the same database.
4. Repeat cold starts at least 10 times.
5. Search logs for PostgreSQL serialization failures, deadlocks, duplicate-key errors, aborted transactions and registry load failures.
6. Confirm button/filter/groupby/tab registries and the generated role groups view are complete after every run.
7. Capture startup duration and query/error counts.

### Reproduction success criteria

`HAZARD_CONFIRMED` if any concurrent run produces a serialization/deadlock/duplicate-write failure attributable to these hooks.

`HAZARD_NOT_REPRODUCED` only after 10 clean multi-worker cold starts plus one module upgrade. This does not prove impossibility; it lowers priority for invasive changes.

## Implementation contract if confirmed

Reimplement under AGPL with these properties:

- preserve native/core `_register_hook()` chains, especially on `res.groups`
- move heavy writes out of per-model startup hooks
- coordinate one rebuild per database transaction/startup wave
- use a PostgreSQL transaction-scoped advisory lock or equivalent deterministic DB primitive
- use a fresh cursor/environment for post-commit rebuild work
- make losing workers skip safely without leaving registries empty
- log lock acquisition, skip, duration and failure
- keep operations idempotent
- add regression coverage for two concurrent rebuild attempts

## Non-goals

- no direct copy of OPL code from upstream #419
- no process-local threading lock as the only guard
- no blanket retry loop hiding database errors
- no skipping Odoo core hooks to suppress the race

## Next action

Run the dev1 reproduction gate. Only if the hazard is confirmed should a focused implementation PR replace the mutating startup hooks with one coordinated rebuild path.
