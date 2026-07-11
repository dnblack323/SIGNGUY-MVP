# Terminology Contract (LOCKED — EC1)

## Canonical terms

Customer, Lead, Quote, Quote Line Item, Order, Order Item, Work Order, Work Order Summary, Invoice, Payment, Proof, Approval, Document, Template, Questionnaire, Form, Signature Request, Webstore, Wrap Project, Tenant, Organization, User, Employee, Platform Admin, AI Credit, Subscription, Add-on, Entitlement.

## Prohibited canonical terms

- Job
- Job Item
- Job Ticket
- Production Ticket
- Job Ticket Summary

Prohibited terms **may** appear in:
- `/app/memory/**` (agent history + running instructions)
- `/app/docs/**` (this contract references them for prohibition)
- `/app/evidence/**` (audit trail)
- `/app/preflight/**` (module preflight docs)
- `/app/SIGNGUY_AI_*.md` (historical audit/migration documents)
- `/app/plan.md`, `/app/README.md`, `/app/PRICING_DEFAULTS_AUDIT.md`, `/app/design_guidelines.md`
- `/app/backend/tests/**` (test docstrings may reference historical evidence)
- `/app/backend/scripts/**` (migration scripts may name legacy fields)
- `/app/frontend/src/components/ui/**` (shadcn upstream)

Prohibited terms must **not** appear in canonical application paths listed in `backend/app/core/terminology_guard.py::CANONICAL_PATHS`.

## Enforcement

- `backend/app/core/terminology_guard.py` scans canonical paths for prohibited terms.
- Test `backend/tests/test_terminology_guard.py::test_canonical_paths_are_clean` fails the build if any canonical file contains a prohibited term.
- The guard file self-excludes because it necessarily contains every prohibited term as a regex pattern.

## Naming rules

- API routes: plural, kebab-case (`/api/orders`, `/api/work-orders`). Never `/jobs`.
- MongoDB collections: `orders`, `order_items`, `work_orders`, `invoices`, `payments`, `wrap_projects`. Never `jobs`.
- Model class names: `Order`, `OrderItem`, `WorkOrder`. Never `Job`, `JobItem`, `JobTicket`.
- Field names: money commerce = `_cents` suffix (integer); FKs = `<entity>_id`; timestamps = `<verb>_at` (UTC).
- Audit events: `<domain>.<verb>`. Never `job.*`.
