# Security Correction Checkpoint 3

Status: OWNER_REVIEW_REQUIRED - uncommitted

## Starting Point

- VERIFIED_REPOSITORY_FACT: Branch was `CODEX-ux1-branch`.
- VERIFIED_REPOSITORY_FACT: Starting HEAD was `16b9787d8e854644475833177d2fb12f7cedcadd`.
- VERIFIED_REPOSITORY_FACT: `origin/CODEX-ux1-branch` matched local HEAD with ahead/behind `0 0`.
- VERIFIED_REPOSITORY_FACT: Remote `origin/main` resolved to `b06589e4ba71d4296a7986c7ca918af84e3607d8`.
- VERIFIED_REPOSITORY_FACT: Checkpoint 2 was already committed and pushed as `16b9787d8e854644475833177d2fb12f7cedcadd`.
- VERIFIED_REPOSITORY_FACT: Working tree was clean before Checkpoint 3 edits began.

## Authoritative Requirements Used

- DOCUMENTED_REQUIREMENT: `docs/architecture/EC6_ASSET_LIBRARY_AND_PORTAL.md` separates staff auth, portal auth, public tokens, scoped portal reads, and single-purpose public-token access.
- DOCUMENTED_REQUIREMENT: `docs/security/EC2_SECURITY_POSTURE.md` defines tenant isolation, permission enforcement, and dependency ordering.
- DOCUMENTED_REQUIREMENT: `docs/architecture/permission_catalog.md` keeps staff, platform, and portal permission scopes disjoint.
- DOCUMENTED_REQUIREMENT: `evidence/SECURITY_CORRECTION_CHECKPOINT_2.md` left Decision Room customer-safe response allowlists and Employee Portal per-domain response minimization as the next security review.
- DOCUMENTED_REQUIREMENT: `docs/production_stage_timer_boundary.md` requires Employee Portal production access to use employee portal auth and self-scope patterns.

## Decision Room Access Inventory

| Entry point | Auth | Tenant / actor boundary | Returned payload | Status |
| --- | --- | --- | --- | --- |
| `backend/app/routers/decision_room.py` staff routes | staff JWT + `Perm.DECISION_ROOM_*` | `user["tenant_id"]` | staff management objects | SAFE, intentionally broader |
| `backend/app/routers/decision_room_portal.py::list_rooms` | customer portal JWT + `portal:view_decision_rooms` | `identity["tenant_id"]` + `identity["customer_id"]` | summary list | SAFE |
| `decision_room_portal.py::get_room` | customer portal JWT | tenant + customer ownership | frozen published room | SAFE_AFTER_CORRECTION |
| `decision_room_portal.py::media` | customer portal JWT | tenant + customer ownership + frozen version media refs | storage response | SAFE |
| `decision_room_portal.py::submit_decision/list_my_decisions` | customer portal JWT | tenant + customer ownership + room | customer decision history | SAFE_AFTER_CORRECTION |
| `decision_room_portal.py::questions/overlays/save-for-later` | customer portal JWT | tenant + customer ownership + room + frozen anchors | customer-owned action records | SAFE_AFTER_CORRECTION |
| `backend/app/routers/public_actions.py` Decision Room routes | public action token | token action + parent type + exact room id + tenant | public room/action records | SAFE_AFTER_CORRECTION |
| `backend/app/services/decision_room_service.py` customer/public helpers | service boundary | server-derived tenant/customer/token | frozen published version and action records | SAFE_AFTER_CORRECTION |

## Decision Room Field Findings

- VERIFIED_REPOSITORY_FACT: Room detail already excluded internal room/option notes, cost/margin/pricing snapshot fields, staff ids, and inactive options.
- VERIFIED_REPOSITORY_FACT: Room detail exposed raw `file_ids` before checking whether each attachment was `customer_visible`.
- VERIFIED_REPOSITORY_FACT: `submit_customer_decision`, `list_my_customer_decisions`, `submit_save_for_later`, and `list_my_saved_for_later` returned raw persisted records with `tenant_id`, `customer_id`, `public_token_id`, `internal_review_status`, and `idempotency_key`.
- VERIFIED_REPOSITORY_FACT: Questions and overlays already returned customer-safe serializers.

## Decision Room Mutation Findings

- VERIFIED_REPOSITORY_FACT: Customer/public mutations bind tenant, customer, public token, room, frozen version, option, and media anchors server-side.
- VERIFIED_REPOSITORY_FACT: Public token routes call `resolve_public_token` with expected action, parent type, and exact room id.
- VERIFIED_REPOSITORY_FACT: Decision, question, overlay, and save-for-later writes record audit/domain events.
- VERIFIED_REPOSITORY_FACT: Customer-supplied identity and internal review fields are ignored; persisted values are server-derived.

## Employee Portal Access Inventory

| Domain | Entry point | Auth | Boundary | Status |
| --- | --- | --- | --- | --- |
| Profile/dashboard | `portal_employee.py` | employee portal JWT + portal permission | `identity["tenant_id"]`, `identity["employee_id"]` | SAFE_AFTER_CORRECTION |
| Time clock/time entries | `portal_employee.py` + `time_clock_service` | `portal:employee_time_clock` | self employee id only | SAFE_AFTER_CORRECTION |
| Timesheets | `portal_employee.py` + `timesheet_service` | `portal:employee_timesheet_view` | self employee id only | SAFE_AFTER_CORRECTION |
| Schedule/calendar/time-off | `portal_employee.py` + schedule/calendar/time-off services | `portal:employee_schedule_view` | self employee id only | SAFE_AFTER_CORRECTION |
| Pay | `portal_employee.py` + `payroll_service` | `portal:employee_pay_view` | self employee id only | SAFE, existing allowlist |
| Announcements | `portal_employee.py` + `announcement_service` | `portal:employee_view` | selected employee or all | SAFE_AFTER_CORRECTION |
| Tasks/comments | `portal_employee.py` + `task_service` | `portal:employee_tasks` | assigned employee + employee-visible | SAFE_AFTER_CORRECTION |
| Messages/preferences/digest | `portal_employee.py` + `communication_service` | `portal:employee_messages/profile` | employee participant + employee-visible | SAFE_AFTER_CORRECTION |
| Production portal | `portal_employee.py` + production services | `portal:employee_view` | assigned stage + employee-visible | SAFE_AFTER_CORRECTION |

## Employee Portal Field Findings

- VERIFIED_REPOSITORY_FACT: Employee profile previously used a denylist and could expose manager-controlled fields such as `tenant_id`, `role_label`, and `portal_access`.
- VERIFIED_REPOSITORY_FACT: Time clock, schedule, announcements, time-off, tasks/comments, messages, preferences, digest, and production stage action responses returned broader service documents.
- VERIFIED_REPOSITORY_FACT: Pay snapshot and transaction responses already used explicit allowlists and were preserved.
- VERIFIED_REPOSITORY_FACT: Production board list rows were already projected through `_portal_row`; stage action responses needed route-level minimization.

## Employee Portal Mutation Findings

- VERIFIED_REPOSITORY_FACT: Profile update accepts only `ProfileUpdateIn` fields with `extra="forbid"` and maps changes to self employee/portal identity.
- VERIFIED_REPOSITORY_FACT: Clock, break, timesheet refresh, schedule reads, pay reads, task transitions, time-off requests, messages, and production actions all use server-derived `identity["employee_id"]`.
- VERIFIED_REPOSITORY_FACT: Employee production stage mutations call `_get_own_stage` before shared stage-service mutation.
- VERIFIED_REPOSITORY_FACT: Manager-controlled payroll values, pay advances, payments, approved payroll values, and other employee ids are not accepted by Employee Portal mutation request models.

## Corrections Implemented

- Added Decision Room customer/public serializers for customer decisions and saved-for-later records.
- Filtered Decision Room customer/public option `file_ids` to records with `visibility == "customer_visible"` and not archived.
- Added Employee Portal route-level allowlisted serializers for employee profile, portal identity update result, time entries, shifts, timesheets, announcements, tasks, task comments, time-off requests, calendar feed, message threads, messages, preferences, digest, and production stage action responses.
- Preserved staff Decision Room response breadth and staff review/apply workflows.
- Preserved My Pay explicit self-pay fields, including `hourly_rate_cents`, because that route is intentionally the employee pay surface.
- Preserved `manager_note` only on the Employee Portal time-off request payload because the existing workflow uses that field as the employee-visible clarification prompt.

## Tests

- Added `backend/tests/test_security_correction_checkpoint3.py`.
- Updated Decision Room customer-decision and save-for-later regression expectations to assert persisted internal fields remain hidden from customer/public responses.

## Verification

- PASS: `python -m py_compile backend/app/routers/portal_employee.py backend/app/services/decision_room_service.py backend/tests/test_security_correction_checkpoint3.py`
- PASS: `python -m pytest backend/tests/test_security_correction_checkpoint3.py -q` -> 2 passed.
- PASS: Decision Room regression suite -> 63 passed.
- PASS: Employee Portal/time/schedule/payroll regression suite -> 53 passed.
- PASS: `python -m pytest backend/tests/test_security_correction_checkpoint1.py backend/tests/test_security_correction_checkpoint2.py -q` -> 10 passed.
- PASS: `python -m pytest backend/tests/test_ec11_phase11e_employee_production_kiosk.py -q` -> 3 passed.
- PASS: `python -m pytest backend/tests/test_ec12_phase12c_time_off.py::test_employee_request_review_clarification_cancel_and_security -q -n 0` -> 1 passed.
- PASS: `python -m pytest backend/tests -q -n 0` -> 690 passed, 3 skipped.
- PASS: `python -m pytest backend/tests -q` -> 690 passed, 3 skipped.
- PASS: `python -m compileall -q backend/app backend/tests/test_security_correction_checkpoint3.py`.
- PASS: `git diff --check`.
- PASS: Source searches for unrestricted internal-record returns and bare-id operations in Decision Room / Employee Portal domains were reviewed. Remaining hits are server-derived tenant/id enforcement, staff-only Decision Room review helpers, already-projected production board service rows, existing training/certification strips, the simple message-read `{ok, unread_count}` response, or intentionally retained Employee Portal self-pay/time-off fields.
- NOTE: The default `python` on PATH is LibreOffice Python and does not include `pytest`; verification used the bundled Codex runtime Python.

## Remaining Risks

- MEDIUM REASONABLE_INFERENCE: Employee Portal production board rows intentionally include customer/order/work-order labels and ids needed for assigned production work; no full order, pricing, or invoice records are returned.
- LOW REASONABLE_INFERENCE: My Pay intentionally exposes self hourly rate and gross/pay totals; this is required by the existing My Pay surface and remains permission-gated.
- LOW REASONABLE_INFERENCE: `manager_note` remains visible only in Employee Portal time-off responses when it functions as the manager's clarification/decision note to the requesting employee.
- INFORMATIONAL VERIFIED_REPOSITORY_FACT: Frontend files were not changed, so frontend build/test verification is not directly affected by this checkpoint.

## Deferred Work

- RECOMMENDATION: A later checkpoint can introduce typed Pydantic response models for portal routes. This checkpoint used route/service serializers to avoid broad router redesign.
- RECOMMENDATION: Future Employee Portal production UX changes should keep the `_portal_row` and `_public_production_stage_view` allowlists as the only portal-visible production projections.
