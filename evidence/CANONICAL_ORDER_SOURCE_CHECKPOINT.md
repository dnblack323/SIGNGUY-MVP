# Canonical Order Source Foundation Checkpoint

## Starting-Point Verification

- Branch: `CODEX-ux1-branch`
- Starting `HEAD`: `11b517a98fe3ee93d027e9136e6b4f5c05145745`
- `origin/main`: `b06589e4ba71d4296a7986c7ca918af84e3607d8`
- `origin/CODEX-ux1-branch`: `11b517a98fe3ee93d027e9136e6b4f5c05145745`
- Starting ahead/behind versus `origin/CODEX-ux1-branch`: `0 0`
- Starting working tree: clean
- Checkpoint 3 commit already present and pushed: `11b517a98fe3ee93d027e9136e6b4f5c05145745`
- Checkpoint 3 note: the pushed commit message is `checkpoint3`; this checkpoint did not rewrite a published commit.

## Authoritative Requirements Used

- User instruction: close Security Correction Checkpoint 3 and establish Canonical Order Source Foundation.
- Owner approval instruction: close Canonical Order Source checkpoint and begin UX1 Shared Command/Ribbon Foundation.
- `evidence/SECURITY_CORRECTION_CHECKPOINT_3.md`
- `preflight/EC3_QUOTES_ORDERS_PRICING_PREFLIGHT.md`
- `preflight/EC10_ORDER_INTAKE_VISUAL_MARKUP_CUSTOMER_DECISION_ROOM_AND_TEMPLATES_PREFLIGHT.md`
- `preflight/EC14_WEBSTORES_PREFLIGHT_AND_IMPLEMENTATION_PLAN.md`
- `preflight/EC15_WRAP_LAB_PREFLIGHT_AND_IMPLEMENTATION_PLAN.md`
- `preflight/EC16_SHARED_AI_GATEWAY_USAGE_COST_CREDITS_AND_GOVERNANCE_PREFLIGHT.md`
- `preflight/EC18_PAID_BUSINESS_ASSISTANT_ACTIONS_INTELLIGENCE_AND_REALTIME_VOICE_PREFLIGHT.md`
- `SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`

## Owner Decisions Recorded

- `legacy_unknown` remains available in normal source filtering with user-facing label `Legacy / Unknown`.
- Wrap Lab remains link-only today.
- A future trusted Wrap Lab `Create Order` action may create canonical Orders with `order_source="wrap_lab"`.
- Linking an existing Order to a Wrap Lab project must never change the Order's original source.
- A future staff duplicate workflow should create a new `manual` Order and may record the original Order with `order_source_record_type="order"` and `order_source_record_id=<original order id>`; it must not inherit `quote`, `webstore`, or `wrap_lab`.
- A future customer reorder workflow should use a distinct `reorder` source with the original Order as the originating record.
- `reorder` is not added to the current contract because no actual reorder workflow exists.

## Existing Order-Creation Inventory

| Path | File and symbol | Current behavior | Tenant/permission boundary | Audit/event behavior | Canonical source | Correction |
| --- | --- | --- | --- | --- | --- | --- |
| Direct staff Order | `backend/app/routers/orders.py::create_order` | Creates `Order` directly from staff payload. | Requires `order:write`; validates customer by tenant. | Emits `order.created`. | `manual` | Assign `order_source="manual"` server-side and forbid payload spoofing. |
| Quote to Order | `backend/app/services/quote_conversion.py::convert_quote_to_order` through `backend/app/routers/quotes.py` | Converts a tenant quote to one Order and copies line items. Existing fields: `quote_id`, `source_quote_id`, `source_quote_revision`. | Quote lookup is tenant-scoped; router requires Quote conversion permission. | Quote router emits conversion audit; service preserves snapshot lineage. | `quote` | Assign `order_source="quote"` plus `order_source_record_type="quote"` and `order_source_record_id=<quote_id>`. |
| Webstore buyer order bridge | `backend/app/services/webstores.py::bridge_buyer_order_to_order` through `backend/app/routers/webstores.py` | Bridges a buyer order into canonical Orders and marks `bridged_order_id`. | Requires `webstore:manage`; buyer order lookup is tenant-scoped. | Emits `webstore.buyer_order_bridged`. | `webstore` | Assign `order_source="webstore"` plus `order_source_record_type="webstore_buyer_order"` and `order_source_record_id=<buyer_order_id>`. |
| Wrap Lab project link | `backend/app/services/wrap_lab.py::create_project` | Does not create Orders. It validates and links an existing `order_id`. | Requires `wrap_lab:write`; referenced Order is tenant-scoped. | Emits `wrap_lab.project_created`. | Reserved `wrap_lab`; legacy inference only | No creation-path mutation because no Wrap Lab Order conversion exists. Legacy rows without `order_source` infer `wrap_lab` from same-tenant `wrap_projects.order_id`. |
| Customer Portal actions | `backend/app/routers/portal_*`, `backend/app/services/decision_room_service.py` | Portal workflows read or decide against existing records; no canonical Order creation found. | Portal-token scoped. | Existing portal/decision events unchanged. | Not applicable | No change. |
| Intake conversion | `backend/app/services/intake_service.py` | `converted_to_order` status requires an existing `order_id`; no Order creation. | Referenced Order must exist in tenant. | Intake audit unchanged. | Not applicable | No change. |
| Duplicate/reorder workflows | Repository search for Order creation paths | No Order duplicate/reorder creation workflow found. | Not applicable | Not applicable | Not applicable | Documented absent; no implementation added. |
| Imports/API integrations/background jobs | Repository search | No active Order import, external API, or background Order creation path found. | Not applicable | Not applicable | Not applicable | Documented absent; no implementation added. |
| Business Assistant | `backend/app/services/business_assistant.py` | Supports conversations, citations, action proposals, and assistant actions; no Order creation action found. | Requires Business Assistant entitlement and `ai_assistant:use`. | Assistant audit unchanged. | Not applicable | No change. |

## Competing Source-Field Findings

- `Order.quote_id`, `Order.source_quote_id`, and `Order.source_quote_revision` are existing Quote compatibility fields and remain intact.
- `OrderItem.source_labels` and `selected_price_source` are pricing provenance fields, not Order creation source fields.
- Webstore uses `webstore_buyer_orders.bridged_order_id` and Webstore ledger `source_type/source_id`; these are module records, not canonical Order source.
- Wrap Lab uses `wrap_projects.order_id`, `quote_id`, and `work_order_id` to link existing records; it does not create Orders.
- Intake, production timeline, AI gateway, payments, and other modules have generic `source`, `source_type`, or `source_id` fields that are not Order provenance.
- The canonical Order field is therefore `order_source`, avoiding collision with existing module-specific `source_type` fields.

## Canonical Order Source Contract

- Field name: `order_source`
- Originating record fields: `order_source_record_type`, `order_source_record_id`
- Allowed values: `manual`, `quote`, `webstore`, `wrap_lab`, `email`, `facebook`, `legacy_unknown`
- Visible filter values: `manual`, `quote`, `webstore`, `wrap_lab`, `legacy_unknown`
- Visible legacy label: `Legacy / Unknown`
- Reserved hidden values: `email`, `facebook`
- Default for new direct Orders: `manual`
- Assignment rule: source is assigned only by trusted backend creation/conversion workflows.
- Immutability rule: normal Order create/update payloads cannot set or change source fields.
- API representation: Order read/list responses include normalized `order_source`, `order_source_record_type`, and `order_source_record_id`.
- Filter query contract: `GET /api/orders?order_source=manual,quote`; omit the parameter or use `all` for All Orders.
- Filter configuration: `GET /api/orders/source-filters` returns visible sources and reserved hidden sources for the future Orders ribbon.

## Legacy-Data Strategy

Legacy Orders are not rewritten. Read responses use deterministic tenant-scoped inference:

1. If `order_source` is present and valid, use it.
2. Else if `source_quote_id` or `quote_id` exists, infer `quote`.
3. Else if a same-tenant `webstore_buyer_orders.bridged_order_id` points at the Order, infer `webstore`.
4. Else if a same-tenant `wrap_projects.order_id` points at the Order, infer `wrap_lab`.
5. Else return `legacy_unknown`.

This avoids destructive migration and avoids blindly classifying every legacy row as manual.

## Creation-Path Corrections

- Direct staff Order creation now stores `order_source="manual"`.
- Quote conversion now stores `order_source="quote"` and records the originating Quote id.
- Webstore bridge now stores `order_source="webstore"` and records the originating buyer order id.
- Wrap Lab remains a same-Orders-system project link; no Order creation path was added.
- Existing Quote and Webstore idempotent re-entry paths return normalized source data for existing Orders.

## Filter Contract

- `GET /api/orders` supports `order_source` as a comma-separated canonical source filter.
- Unsupported values return HTTP 400.
- Filters remain tenant-scoped and combine with existing `status`, `customer_id`, `limit`, and `skip`.
- `search` was added for job/title/description/notes and numeric Order number matching so the future ribbon can combine source filters with search.
- Hidden `email` and `facebook` are not returned as visible filter options until real creation workflows exist.
- `legacy_unknown` is returned as `Legacy / Unknown`.
- No source-specific tabs or Order systems were added.

## Security and Entitlement Findings

- Direct browser payloads cannot set `order_source` or source record fields on create or update.
- Quote and Webstore source assignment happens inside trusted backend workflows after tenant-scoped originating record lookup.
- Wrap Lab legacy inference only honors same-tenant `wrap_projects.order_id`.
- Existing permissions are preserved: `order:read`, `order:write`, Quote conversion permissions, `webstore:manage`, and Wrap Lab permissions.
- Existing entitlement behavior for Webstores, Wrap Lab, AI, and Business Assistant was not changed.
- No public or portal response was expanded with provider metadata.

## Indexes Added

- `orders`: `(tenant_id, order_source, updated_at)`
- `orders`: `(tenant_id, order_source_record_type, order_source_record_id)`
- `webstore_buyer_orders`: `(tenant_id, bridged_order_id)` partial on string `bridged_order_id`
- Existing `wrap_projects`: `(tenant_id, order_id)` partial index was already present and supports legacy Wrap Lab inference.

## Tests Added

- `backend/tests/test_canonical_order_source.py`
  - Direct Order receives `manual`.
  - Browser-supplied protected source is rejected on create/update.
  - Quote conversion receives `quote`.
  - Webstore bridge receives `webstore`.
  - Legacy Wrap Lab inference is tenant-scoped.
  - Unknown legacy rows return `legacy_unknown`.
  - Source remains stable after normal updates.
  - Source filtering combines with status, search, limit, and skip.
  - Unsupported source handling returns 400.
  - Filter configuration hides reserved future sources and labels `legacy_unknown` as `Legacy / Unknown`.

## Verification Commands and Results

- PASS: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest backend/tests/test_canonical_order_source.py -q` -> 5 passed.
- PASS: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest backend/tests/test_orders_ec3.py backend/tests/test_quotes_ec3.py backend/tests/test_ec14_webstores.py backend/tests/test_ec15_wrap_lab.py backend/tests/test_work_orders_ec5.py backend/tests/test_security_correction_checkpoint3.py -q` -> 28 passed.
- PASS: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest backend/tests -q -n 0` -> 695 passed, 3 skipped.
- PASS: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest backend/tests -q` -> 695 passed, 3 skipped.
- PASS: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall backend/app backend/tests`.
- PASS: `git diff --check`.
- PASS: competing source-field search. Findings are documented above; no existing generic `source_type` field was repurposed.
- PASS: Order creation search. Trusted active creation paths now assign canonical source where they create canonical Orders. Remaining `db.orders.insert_one` occurrences are test fixtures or non-creation module records.
- Frontend tests/build: not run because no frontend files changed.

## Remaining Risks

- The Orders list normalizes source after fetching matching tenant/status/customer/search rows. This preserves correctness and legacy inference, but a future high-volume Orders list may need a dedicated backfill or aggregation path.
- Wrap Lab source is represented through legacy inference only because no Wrap Lab Order conversion workflow exists. Future trusted Wrap Lab `Create Order` behavior is documented above.
- Duplicate/reorder source behavior remains unimplemented because no Order duplicate/reorder workflow exists in the repository. Future staff duplicate and customer reorder semantics are documented above.

## Files Modified

- `backend/app/core/db.py`
- `backend/app/models/order.py`
- `backend/app/routers/orders.py`
- `backend/app/services/order_source.py`
- `backend/app/services/quote_conversion.py`
- `backend/app/services/webstores.py`
- `backend/tests/test_canonical_order_source.py`
- `evidence/CANONICAL_ORDER_SOURCE_CHECKPOINT.md`

## Recommended Next Checkpoint

Return to UX1 and establish the shared command/ribbon system before Workspace Dock or Dashboard Customizer.

## Owner Decisions Required

None for this checkpoint. The owner decisions supplied before closure are recorded above.

## No-Unrelated-Work Confirmation

- No UX1 visual rollout was started.
- No Workspace Dock, Dashboard Customizer, shared ribbon, or Admin Communication Center was built.
- No Stripe objects, bootstrap actions, provider calls, public portal behavior, EC19 work, or unrelated security behavior were changed.
- This checkpoint remains uncommitted and unpushed for owner review.
