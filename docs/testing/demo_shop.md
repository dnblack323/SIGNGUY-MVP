# SIGNGUY DEMO SHOP (developer-only seed / reset)

One permanent, fictional demonstration shop for development and demos. Everything is invented (people, businesses,
`example.com` emails, `555-01xx` phones, demonstration prices). It is created through the same routers and services the UI
uses, so numbering, snapshots, activity records and validation behave exactly as they do for real shops.

```bash
cd backend
python -m scripts.demo_shop seed        # idempotent: creates what is missing, changes nothing that exists
python -m scripts.demo_shop verify      # read-only: relationships, money, files, screens, one-tenant checks
python -m scripts.demo_shop reset --confirm signguy_local   # DESTRUCTIVE: drops signguy_local, then seeds
```

Options: `--env-file <path>` (the development `.env`; default `backend/.env`), `--storage-path <backend>/.data/object_storage`
(where the running app reads files; default is this checkout's), `--disposable` (seed an isolated test database created by
`python -m tests._test_env run -- ...`; used by the tests).

## Safety (all enforced before any connection or write)

* Targets exactly `signguy_local` on `localhost:27017` (unauthenticated, ENV=development, AUTH_DEV_BYPASS=true). Any other
  database name, remote/authenticated URL, production env or CI run is refused. There is no wildcard and no tenant-delete code.
* `reset` needs `--confirm signguy_local`, refuses while operations are running on the database, and drops that one database
  only. It never touches the MongoDB server or other databases. Stop the app first.
* Live integrations are switched off in the seeding process: SendGrid, Stripe, OpenAI and SMS keys are blanked, so no email,
  charge or AI call can happen. Stores never enable checkout and no payment provider is configured.
* No HTTP route or UI button calls this tool.

## What it creates

1 tenant (`SIGNGUY DEMO SHOP`, slug `dev-shop`, the dev-login contract), 5 users (owner + 4 staff/employees), 18 customers,
25 quotes -> 20 orders -> 20 work orders with production stages in realistic states (waiting for artwork/approval, on hold,
in design, in production, ready, scheduled for install, completed), 20 invoices with deposits, partial and full payments, one
overdue, 14 expenses, materials/inventory/vendors/equipment, pricing profiles and components, two weeks of published shop
schedule, calendar events, tasks, time records, an announcement, 20 generated artwork files attached to customers/orders, 5
Wrap Lab vehicles and projects (including one full lifecycle with warranty), and 4 Webstores at different setup stages, built
through the owner portal (questionnaire, return for changes, branding review, product/mockup approvals).

## Known limits (current app behavior, not seed shortcuts)

* Webstores cannot be taken live or sent a launch packet: checkout needs Stripe (disabled), publishing branding needs an
  approved packet, and an owner who accepted an invitation is not yet a "verified recipient" for packet delivery.
* The Webstores feature entitlement is granted to the demo tenant with one direct write (the platform has no entitlement-write
  API yet), and the owner's emailed invitation link is stood in for by installing a one-time token (no email is sent).
* Commercial catalog / subscription pricing is not seeded: it needs owner-approved prices. The shop is "unbilled" (full access).
