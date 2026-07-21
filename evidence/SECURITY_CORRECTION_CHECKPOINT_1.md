# Security Correction Checkpoint 1

Date: 2026-07-21
Branch: `CODEX-ux1-branch`
Scope: tenant isolation corrections, permanent `PLATFORM_CREATOR` authorization, and backend test-environment repair.

## Starting Point

- Current checkpoint sequence: EC19 foundation complete; UX1 not started.
- This checkpoint does not start UX1, EC20, EC21, or EC22.
- Backend security authority remains `backend/app/core/permissions.py`, `backend/app/deps.py`, `docs/architecture/permission_catalog.md`, `docs/security/EC2_SECURITY_POSTURE.md`, and `docs/security/production_startup_guards.md`.

## Verified Tenant-Isolation Inventory

| File | Function or symbol | Operation | Record identifier | Boundary observed | Status before correction | Correction | Required test |
|---|---|---|---|---|---|---|---|
| `backend/app/routers/customers.py` | `update_customer` | reread after update | `customer_id` | update was tenant-scoped; reread used bare `id` | VULNERABLE | reread by `id + tenant_id` | tenant-scoped reread |
| `backend/app/routers/users.py` | `update_user` | update and reread | `user_id` | prefetch tenant-scoped; update/reread used bare `id` | VULNERABLE | update/reread by `id + tenant_id` | self-promotion rejection |
| `backend/app/routers/quotes.py` | `update_quote`, `set_status`, `archive_quote` | update and reread | `quote_id` | prefetch tenant-scoped; mutation/reread used bare `id` | VULNERABLE | mutation/reread by `id + tenant_id` | representative route coverage |
| `backend/app/routers/quotes.py` | quote line item routes | update/delete/reread | `quote_id`, `item_id` | parent/item verified; mutation/reread used bare item or quote id | VULNERABLE | child mutations by `id + quote_id + tenant_id`; parent updates by `id + tenant_id` | child-boundary test |
| `backend/app/routers/orders.py` | `update_order`, `set_order_status` | reread/status update | `order_id` | prefetch/update partially scoped; status update/reread used bare `id` | VULNERABLE | mutation/reread by `id + tenant_id` | representative route coverage |
| `backend/app/routers/orders.py` | order item routes | update/delete/reread | `order_id`, `item_id` | parent/item verified; mutation/reread/delete used bare item id | VULNERABLE | child mutations by `id + order_id + tenant_id` | child-boundary test |
| `backend/app/routers/invoices.py` | `update_invoice`, `set_invoice_status`, legacy payment shim | update/reread/payment-derived updates | `invoice_id` | prefetch tenant-scoped; updates/rereads used bare `id` | VULNERABLE | mutation/reread by `id + tenant_id`; void check latest read scoped | representative route coverage |
| `backend/app/services/payment_service.py` | manual/stripe payment mutations | delete/update/reread after scoped lookup | `payment_id`, generated payment id | user-initiated lookup scoped; some follow-up writes used bare `id` | VULNERABLE | follow-up writes by `id + tenant_id`; webhook lookup remains provider-token based then tenant-scoped for updates | payment service coverage |
| `backend/app/services/work_order_service.py` | `transition`, `assign`, `regenerate` | update/reread/supersede | `work_order_id` | initial read tenant-scoped; follow-up writes/rereads used bare `id` | VULNERABLE | follow-up writes/rereads by `id + tenant_id` | representative route coverage |
| `backend/app/routers/work_orders.py` | `patch_wo`, `get_summary` | reread and joined reads | `wo_id`, `order_id`, `customer_id` | work order read scoped; reread and summary joins used bare ids | VULNERABLE | reread and joins by tenant | summary boundary coverage |
| `backend/app/routers/payments.py` | payment routes | read/delegate | `invoice_id`, `payment_id` | route lookups and service entry points are tenant-scoped | SAFE | no stylistic change | existing plus service tests |
| `backend/app/routers/public_actions.py`, portal routers | portal/public token access | public/portal reads | token hash, portal identity | dedicated token/identity boundaries present | CANNOT_VERIFY in this checkpoint | no code changed | follow-up portal/public sweep |
| `backend/app/repositories/webstores.py`, `backend/app/repositories/wrap_lab.py` | repository access | tenant repository CRUD | entity id | repository methods include `tenant_id` for get/update/list | SAFE | no stylistic change | existing EC14/EC15 tests |
| `backend/app/services/production_board_service.py` | board bulk actions | bulk stage operations | `stage_ids` | delegates to tenant-scoped stage service; board queries use tenant filters | SAFE by inspection | no stylistic change | existing EC11 tests |
| `backend/app/services/business_assistant.py` | assistant/memory/routine/voice | tenant-owned assistant records | record ids | most user-facing reads are scoped; some stale/dismissal updates by bare id remain outside this correction batch | MEDIUM follow-up | not corrected here | EC18 security sweep |

## PLATFORM_CREATOR Contract

- `PLATFORM_CREATOR` is represented by stored `platform_role = "PLATFORM_CREATOR"` and `platform:creator` permission.
- `thesigntistslab@gmail.com` is used only by controlled assignment/bootstrap to locate an existing account by normalized email.
- Runtime authorization uses stored role/permission fields through `has_platform_admin_access`.
- Existing explicit `platform_admin`, stored platform role `admin`/`owner`, and scoped platform permissions remain valid.
- Tenant owner/admin roles do not grant platform access.
- Role assignment writes both audit and activity records.

## Test Environment Repair

- `backend/tests/conftest.py` now forces `ENV=test`, disables live provider integrations, permits the existing fake Stripe placeholder path through `AUTH_DEV_BYPASS=true`, and supplies safe local test DB defaults before importing app settings.
- Default test DB: `mongodb://localhost:27017`, database `signguy_test_<xdist worker>_<random suffix>` to avoid cross-run residue.
- Pytest temp files are routed to repo-local ignored `.pytest_tmp_root/` to avoid Windows permission failures on the default `pytest-current` temp link.
- Operators may override with `TEST_MONGO_URL` and `TEST_DB_NAME`.
- Tests no longer rely on production `.env` values during pytest import.

## Remaining Risks

- MEDIUM: Portal/public-token routes were read for boundary shape but need a dedicated exhaustive token-field audit in a follow-up checkpoint.
- MEDIUM: EC18 Business Assistant contains some internally prechecked follow-up updates by bare id; no normal cross-tenant route exploit was verified in this checkpoint, but it should receive a focused EC18 follow-up sweep.
- LOW: Provider webhook lookup remains provider-reference based because external provider events do not carry authenticated tenant identity; subsequent internal updates are now tenant-scoped where payment rows expose tenant identity.
