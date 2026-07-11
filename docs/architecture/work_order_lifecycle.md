# Work Order Snapshots + Versioning + Transitions + Summary (EC5)

## Overview
EC5 delivers the Production and Work Order pipeline as one permanent system. It layers a 9-state lifecycle, priority + due dates, immutable snapshots, versioned regeneration, and a printable summary on top of the existing `work_orders` collection. This document describes the whole surface — backend contracts + frontend workflows.

## Snapshots
Each Work Order embeds `items_snapshot: list[dict]` — a denormalized copy of only the Order Items where `production_required=true` at snapshot time. Fields captured: source `order_item_id`, description, quantity, category, product_type, dimensions, unit_of_measure, material_key, notes, unit_price_cents.

Snapshots are **immutable** after generation. `PATCH /work-orders/{id}` accepts only `production_instructions`, `internal_notes`, `priority`, `due_date`, `department` — never item content. Edits to the source Order Item do not mutate a released Work Order; use **regenerate** to pull a new snapshot.

## Generation
`POST /api/work-orders` accepts either:
- Modern: `{ order_id, priority, due_date, production_instructions, internal_notes, assigned_user_ids[] }`
- Legacy: `{ order_id, production_instructions, internal_notes, assigned_to }` (mirrored into `assigned_user_ids`).

Rules:
- Rejects orders with zero `production_required=true` items → `400 no_production_required_items`.
- **Duplicate active guard:** if a `current_version=True` Work Order already exists for the order, the existing row is returned with `already_exists=true`. No duplicate active WOs per Order.

**Frontend:** `GenerateWorkOrderDialog` on the Order Detail page collects priority / due date / instructions / assignees. If the API returns `already_exists=true`, a neutral toast is shown and the user stays on the order (an "Open work order" button now points to the existing WO).

## Regeneration / Supersede
`POST /api/work-orders/{id}/regenerate` (body `{reason}`, reason required) creates a **new** row with `version += 1`, `superseded_from = <old_id>`. The old row is marked `production_status="superseded"`, `current_version=False`, `superseded_by=<new_id>`, `supersede_reason` recorded. Prior versions remain readable.

**Frontend:**
- Available from **Work Order Detail** (header "Regenerate" button, disabled on terminal / superseded rows).
- Available from **Order Detail** while the active WO is not terminal — same modal.
- Superseded rows show two banners: an amber "SUPERSEDED — current version: open" banner on the old row and a subtle "Regenerated from earlier version" banner on the new row linking back.

## Versioning
`WorkOrder.version` starts at 1, `current_version=True`. Version chips render inline in Work Order lists and the detail header (`v{n}`). The `current_only=true` list filter (default on) hides superseded rows.

## Lifecycle & Transitions
Central `ALLOWED_TRANSITIONS` map in `services/work_order_service.py`:

| From | Allowed targets |
|------|-----------------|
| draft | released, cancelled |
| released | queued, in_progress, blocked, cancelled |
| queued | in_progress, blocked, cancelled |
| in_progress | blocked, ready, cancelled |
| blocked | released, queued, in_progress, cancelled |
| ready | completed, cancelled |
| completed | ∅ (terminal) |
| cancelled | ∅ (terminal) |
| superseded | ∅ (terminal via regenerate) |

`blocked` and `cancelled` require a `reason`. Invalid transitions → `400 invalid_transition:{from→to}`.

**Order coordination (safe subset):** `released→order.confirmed`, `in_progress→order.in_production`, `ready→order.ready`, `completed→order.completed`. Financial state is never touched by production transitions.

**Frontend:**
- **Production Board (`/work-orders/board`)** — HTML5 drag-and-drop between columns; dropping onto `blocked` or `cancelled` opens a reason-required modal. Invalid drops surface the backend error via toast.
- **Work Order Detail** — sidebar exposes only allowed next states as buttons, backed by the same `POST /work-orders/{id}/transition` endpoint. Reason modal fires for `blocked`/`cancelled`.
- Terminal states display an italic "Terminal status — no further transitions" note; block/cancel reasons render below the pill.

## Assignment
`POST /api/work-orders/{id}/assign` accepts `{user_ids[]}` and validates every id is a member of the caller's tenant (cross-tenant rejected). Newly assigned users receive an in-app notification through the EC2 `notify` helper (subject: `Assigned to work order W-{n}`).

**Frontend:** `AssignDialog` (multi-select checkboxes over `/users`) opened from the Work Order Detail sidebar. The board card also shows assignee chips.

## Summary
`GET /api/work-orders/{id}/summary` returns a printable payload:
```
{
  work_order_number, order_number, customer{id,name},
  priority, due_date, version, current_version,
  production_notes, status,
  items: [{ description, quantity, category, product_type,
            width_inches, height_inches, unit_of_measure,
            material_key, notes,
            unit_price_cents?  // only if caller has invoice:read
          }],
  generated_at
}
```
`unit_price_cents` is included ONLY when the caller carries `invoice:read`. Otherwise the payload is safe for the production floor.

**Frontend:** `PrintSummaryDialog` (opened from the WO detail header) renders the summary inside a dedicated `data-print-region` block, injects a scoped `@media print` stylesheet, and calls `window.print()`. A pricing-hidden banner renders when the caller lacks `invoice:read`. Superseded rows include a "SUPERSEDED" stamp.

## Production Board
`GET /api/production/board` groups current-version Work Orders by effective status, sorted by priority desc, then due_date asc. Each row includes `overdue: true` when `due_date` is in the past and the row is not `completed`/`cancelled`. Optional filters: `priority`, `assigned_user_id`, `customer_id`.

The Board is a **view** over the shared `work_orders` collection — no new collection.

**Frontend:** `/work-orders/board` — column-per-status Kanban with:
- priority + assignee filters,
- draggable cards (`work_order:write` gated),
- reason-required modal for `blocked` / `cancelled` drops,
- overdue chips + assignee chips + item count.

## Permissions
Every route is protected. UI controls are gated on the `/auth/me` permissions payload — never role strings:
- read (list / detail / board / summary): `work_order:read`
- write (generate / patch / transition / assign / regenerate): `work_order:write`
- pricing on summary: `invoice:read`

## Data compatibility
`effective_status(raw)` translates legacy `not_started→released`, `on_hold→blocked` on read. The MVP `POST /work-orders/{id}/production-status` endpoint remains, mapping legacy values through the new transition path. No destructive migration.

## Files
Backend:
- `backend/app/models/work_order.py`
- `backend/app/services/work_order_service.py`
- `backend/app/routers/work_orders.py`

Frontend:
- `frontend/src/pages/ProductionBoardPage.jsx`
- `frontend/src/pages/WorkOrderDetailPage.jsx`
- `frontend/src/pages/WorkOrdersPage.jsx`
- `frontend/src/pages/OrderDetailPage.jsx` (generate / regenerate hooks)
- `frontend/src/components/work-orders/GenerateWorkOrderDialog.jsx` (also exports `RegenerateDialog`, `TransitionReasonDialog`, `AssignDialog`, `AssigneePicker`)
- `frontend/src/components/work-orders/PrintSummaryDialog.jsx`
- `frontend/src/components/common/StatusPill.jsx` (extended `production` + new `priority` map)
- `frontend/src/lib/navigation.js` (Production Board flyout link)
- `frontend/src/App.js` (routes)
