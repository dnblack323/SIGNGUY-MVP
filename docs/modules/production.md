# Production Module (EC5)

The Production experience is a VIEW over the shared `work_orders` collection — there is NO parallel production collection.

- `GET /api/production/board` groups current-version Work Orders into status columns and returns `overdue` flags derived from `due_date`.
- Every drag-and-drop / column transition on the frontend calls the same `POST /api/work-orders/{id}/transition` route; the backend enforces allowed transitions + reasons.
- Priority order + due-date ascending is the default sort.

Legacy Job Ticket / Production Ticket terminology is banned. Translate any legacy reference to Order Item + Work Order + Work Order Summary.
