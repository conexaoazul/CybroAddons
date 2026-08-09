# Cybro upstream radar handoff

## What this PR delivers

- deterministic heuristic ranking of recently updated `CybroOdoo/CybroAddons` PRs
- Odoo 19 bias and platform/revenue priority signals
- Markdown and JSON evidence artifacts
- weekly GitHub Actions execution plus manual dispatch
- adoption policy that prevents blind dependency import

## After merge

1. Run `Cybro Upstream ROI Radar` manually once on `19.0`.
2. Read the top 20 candidates in the Actions job summary/artifact.
3. For the first candidate scoring `EXTRACT_OR_REIMPLEMENT`, inspect the upstream PR diff and dependency chain.
4. Search Odoo 19 native, OCA 19.0 and BlueApps for functional overlap.
5. Open a focused implementation PR in the canonical destination repository/module.
6. Attach source PR/SHA, overlap decision, license review and QA plan.
7. Use dev1 only for runtime validation that cannot be proven in GitHub/static review.

## Runtime QA contract for dev1

For each selected port, validate only the relevant surface:

- clean module install/update
- registry startup with no traceback
- ACL/multi-company behavior when applicable
- critical user journey smoke test
- external API/payment/messaging sandbox only when required
- logs/evidence returned to the implementation PR

## Stop conditions

Do not port a candidate when:

- Odoo 19 already provides equivalent behavior cleanly
- maintained OCA 19.0 solves it with lower ownership cost
- BlueApps already contains the capability and consolidation is cheaper
- license provenance is unclear
- the upstream implementation weakens ACL/auth/security boundaries
- dependency fan-out is larger than the differentiated value
