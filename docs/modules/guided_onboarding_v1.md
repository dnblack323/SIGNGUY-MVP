# Guided Onboarding V1

Three-stage guided setup at `/onboarding` (also `/help/onboarding`). It walks a new shop through
the **real** settings and records; it owns no copy of shop configuration.

## Stages

| Stage | Purpose | Required steps |
|---|---|---|
| Quick Start | Operational with the minimum setup | business info, address/contact, labor rates, production workflow, first customer, first order |
| Standard Setup | Normal business configuration | none (all recommended/optional) |
| Advanced Optimization | Optional systems, automation, analytics | none |

The step catalog is `backend/app/services/onboarding_catalog.py` (pure data: stage, level, what/why, owning route,
inline `form`, `detect` mode, `feature_key`, `help_slug`).

## Where each Quick Start step saves (no onboarding copy)

| Step | Saved through | Completion detected from |
|---|---|---|
| Business information / contact | `PUT /api/settings/company_profile` | `company_profile` settings |
| Branding | `PUT /api/settings/branding` | `branding` settings |
| Labor and pricing basics | `PATCH /api/pricing/settings/shop-defaults` (Pricing Foundation contract) | `pricing_settings.field_sources` (only owner-written fields) |
| Production workflow | `POST /api/production-workflows/{id}/set-default` | an active default workflow |
| First team member | `POST /api/employees` | `employees` |
| Payment preferences | `PUT /api/settings/invoicing_defaults` | `invoicing_defaults` settings |
| Portal preferences / Notifications | `PUT /api/settings/portal` / `notifications` | key present in settings |
| First customer / first order | `POST /api/customers`, `POST /api/orders` | `customers`, `orders` |

Completion is **derived on every dashboard read**, so changing or clearing a value later in Settings updates it.
`detect: "manual"` steps (no record to inspect) complete only through an explicit **Mark as reviewed**; pressing
Next never completes anything.

## Status rules

`not_started`, `in_progress`, `completed`, `skipped`, `deferred`, `blocked`.

* Required steps can be deferred but not skipped; optional steps can be skipped.
* `blocked` is computed with a reason: an unfinished dependency, or a feature not in the shop's plan
  (`feature_key` checked with the entitlement service). Plans, AI, Stripe and other paid providers are never required.
* Canonical steps cannot be completed by hand (`409 completion_is_derived`).

## First login

Home shows a dismissible banner to owners/admins until every required Quick Start step is done. It never
redirects and never reopens after **Not now**. Position is saved per shop (`POST /api/onboarding/position`) so
**Resume later** and `?step=<task_key>` return to the same place.

## API

`GET /api/onboarding/dashboard`, `POST /api/onboarding/tasks/{task_key}/status`, `POST /api/onboarding/position`,
`GET|POST /api/onboarding/setup-package-handoff` (EC13 boundary, unchanged), `POST /api/onboarding/platform/bootstrap`.

## Help link contract (shared with the Help agent)

Each step links to `/help/docs?article=<slug>`. Until the Help Center resolves `?article=`, the route opens the docs
index. Slugs used (no article content lives in onboarding):

`company-profile`, `branding`, `pricing-foundation`, `production-workflows`, `employees`, `invoices-and-payments`,
`customer-portal`, `customers`, `orders`, `time-clock`, `shop-schedule`, `materials`, `equipment`, `documents`,
`notifications`, `webstores`, `inventory`, `reports`, `wrap-lab`, `business-assistant`, `ai-credits`, `templates`.

## Known limits

* `portal` and `notifications` preferences are stored in the canonical settings namespaces; enforcement belongs to
  the portal/notification modules and is not yet read there.
* Price Lab Pricing Foundation integration is unfinished; labor rates use the current MVP shop-defaults contract.
* Standard/Advanced steps mostly link to the owning feature; only Quick Start has inline forms.
