# CybroAddons upstream adoption policy

## Objective

Turn `conexaoazul/CybroAddons` into a controlled donor-code radar for Odoo 19 instead of a dependency accumulator.

The automated radar ranks recently updated pull requests from `CybroOdoo/CybroAddons` and produces evidence for human/agent review. Ranking is intentionally biased toward capabilities with higher expected operational or revenue leverage for Conexao Azul.

## Priority order

### P0 — platform and revenue

- REST/API, webhooks and external integration
- authentication, authorization, access control and auditability
- subscriptions, recurring billing, payment and invoicing
- CRM, lead and sales automation
- automation, queue, cron and workflow capabilities
- dashboards, KPI and operational reporting

### P1 — service and self-service

- helpdesk, SLA and ticket automation
- WhatsApp/messaging integrations
- customer/reseller portal improvements
- documents/signature flows
- performance and reliability improvements

### P2 — ERP breadth

- inventory, stock and purchase automation
- project and timesheet improvements

### P3 — cosmetic

Themes, fonts, colors and purely visual changes should normally be ignored unless they remove measurable friction in a revenue or support journey.

## Decision matrix

For each high-scoring candidate, record:

| Field | Required decision |
|---|---|
| Source | Upstream PR number and source SHA |
| Odoo 19 native overlap | Prefer native when equivalent |
| OCA 19.0 overlap | Prefer maintained OCA when ownership cost is lower |
| BlueApps overlap | Extend/consolidate an existing canonical module where possible |
| License | Confirm compatibility before copying code |
| Security | Review auth, ACLs, sudo, controllers, external input and secrets |
| Data model | Check schema conflicts, migrations and multi-company behavior |
| Observability | Add structured logs/metrics/traces for critical flows |
| Tests | Unit/integration/smoke evidence appropriate to the capability |
| Deployment | QA first; production only after explicit release gate |
| Action | `CHERRY_PICK`, `EXTRACT`, `REIMPLEMENT`, `WATCH`, or `IGNORE` |

## Canonical adoption rule

`Odoo 19 native > maintained OCA 19.0 > existing BlueApps capability > selective Cybro donor code > new custom implementation`

This is not a rigid source preference when requirements differ. It is a maintenance-cost default. A Cybro implementation may win when it has a meaningful capability gap and passes the gates above.

## Golden path for a selected candidate

1. Radar identifies a high-value PR.
2. Agent inspects its diff and dependency chain.
3. Compare with Odoo 19, OCA 19.0 and BlueApps equivalents.
4. Select the smallest reusable capability.
5. Port into the canonical destination module rather than importing an avoidable dependency tree.
6. Add provenance metadata in the implementation PR.
7. Run lint/static checks and module install/update smoke tests.
8. Run functional QA on the dev1/self-hosted runner when the capability needs Odoo/database/external-service validation.
9. Merge only with evidence attached to the implementation PR.

## Operator handoff

For candidates requiring runtime validation, the dev1 operator should receive only the unresolved runtime work:

- exact implementation PR/SHA
- addons path and module(s) to install/update
- database/tenant used for QA
- expected smoke commands
- acceptance criteria
- external credentials/services required, if any
- artifact/log location to attach back to the PR

Do not ask dev1 to redo upstream discovery or architecture triage already captured by the radar and implementation PR.
