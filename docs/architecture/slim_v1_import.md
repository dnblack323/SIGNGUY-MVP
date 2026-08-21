# SignGuy Slim V1 Import Boundary

This document records the Version 1 Part 6 boundary for importing a validated
SignGuy Slim `.signguy-backup` file into the full SignGuy MVP product.

## Entry Point

- Route: `POST /api/slim-import/preview`
- Route: `POST /api/slim-import/confirm`
- Route: `GET /api/slim-import/runs/{import_run_id}`
- Frontend: Control Center > Import from SignGuy Slim

Preview validates the encrypted container and produces a report without writing
tenant data. Confirm revalidates the same backup, requires the typed shop-name
confirmation, and writes only into the selected empty target tenant.

## Security Boundary

- The backup must use the Slim V1 Part 5 container signature, format, product,
  KDF, encryption algorithm, and section manifest.
- The importer derives the encryption key from the submitted passphrase and
  never stores the passphrase or derived key.
- Owner/admin staff permission is required. Frontend visibility is not
  authoritative.
- Imports are limited to the actor's tenant in the current MVP tenant model.
- Existing operational tenant data blocks import.
- Completed import receipts prevent reimporting the same backup into the same
  tenant.
- Attachments are checksum-verified and staged into private storage.
- Failed imports compensate inserted records and staged storage keys.

## Imported Scope

- Tenant shop profile fields compatible with MVP.
- Customers.
- Estimates as quotes and quote line items.
- Orders and order line items.
- Production-required Slim order items as Work Orders.
- Invoices and invoice line items.
- Calendar events.
- Notes, reminders, and audit-history context where compatible.
- File records and attachments for supported attachment types.
- Source-to-target mappings and a permanent import run receipt.

Historical prices, totals, statuses, and manual paid amounts are preserved as
history. The importer does not recalculate historical records through the MVP
Pricing Engine.

## Explicit Exclusions

- No platform tenant creation.
- No user or password creation.
- No Stripe, payment processor, or payment transaction creation.
- No Webstores, customer portal, Decision Room, inventory, payroll, AI, or
  commercial-account import.
- No merge into non-empty tenant data.
- No Version 2 routes, navigation, placeholders, or scaffold.
