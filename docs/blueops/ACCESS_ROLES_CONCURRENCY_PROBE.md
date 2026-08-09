# access_roles multi-worker concurrency probe

## Goal

Prove or falsify the Odoo 19 concurrency hazard before changing registry hooks.

The current 19.0 addon performs database writes from `_register_hook()` in:

- `button.registry`
- `filter.registry`
- `groupby.registry`
- `tab.registry`
- `res.groups`

This is a high-risk startup path when multiple Odoo workers initialize the same database concurrently.

## Why this is clean-room

Upstream `CybroOdoo/CybroAddons#419` demonstrates the behavioral class of failure, but its new coordinator file is OPL-licensed. Do not copy that implementation. The only reusable facts are the externally observable problem and general PostgreSQL/Odoo primitives that are independently available.

Odoo 19 itself uses `env.cr.postcommit.add(...)`, so post-commit coordination is a native primitive available for an independent implementation.

## Required dev1 reproduction

Use an isolated QA database with `access_roles` installed.

1. Set workers >= 2.
2. Ensure all registry tables are present and writable.
3. Restart Odoo repeatedly while forcing simultaneous worker registry initialization.
4. In a second variant, update `access_roles` while workers are enabled.
5. Capture PostgreSQL/Odoo logs for:
   - `SerializationFailure`
   - `could not serialize access due to concurrent update`
   - duplicate/unique constraint errors
   - deadlocks
   - registry initialization retries
6. Repeat at least 10 cold starts or until the fault is reproduced.
7. Record whether each startup completes and whether the registry tables are complete.

## Evidence schema

Publish a short result in the PR with:

- Odoo SHA/version
- CybroAddons SHA
- database name masked
- worker count
- number of attempts
- failures observed
- representative stack trace with secrets removed
- registry row counts after startup
- conclusion: `REPRODUCED`, `NOT_REPRODUCED`, or `INCONCLUSIVE`

## Implementation gate

Only implement concurrency coordination if the issue is reproduced or if static review proves that simultaneous hooks can mutate the same rows without an existing serialization boundary.

Preferred clean-room direction if confirmed:

1. remove addon-specific heavy writes from individual `_register_hook()` methods while preserving Odoo core hook chaining;
2. schedule one coordinated rebuild after the registry transaction commits;
3. use a transaction-scoped PostgreSQL advisory lock with a Conexao Azul-owned lock key;
4. open a fresh cursor/environment for the rebuild;
5. make the rebuild idempotent;
6. log skip/acquire/duration/result without business data;
7. add multi-worker QA proving no deadlock and complete registries.

## Do not

- copy the OPL coordinator from upstream #419;
- override `res.groups._register_hook()` without calling the core chain correctly;
- hold a session advisory lock indefinitely;
- silently skip a required rebuild without leaving evidence;
- merge a concurrency fix validated only with `workers = 0`.
