# Code Issue Register

This register tracks known code-review issues that should not be lost between stages. It is not a planning document and does not authorize scope expansion.

| ID | Issue | Area | Status | Verification |
| --- | --- | --- | --- | --- |
| CIR-001 | Concurrent invoice overpayment | Invoices / payments | Open | Needs focused fix and regression coverage. |
| CIR-002 | Incomplete Stripe webhook reconciliation | Stripe / payments | Open | Needs focused fix and regression coverage. |
| CIR-003 | Quote total/item disagreement | Quotes / pricing | Open | Needs focused fix and regression coverage. |
| CIR-004 | Failure-unsafe quote conversion | Quote to Order conversion | Open | Needs focused fix and regression coverage. |
| CIR-005 | Non-atomic single-use tokens | Token consumption | Open | Needs focused fix and regression coverage. |
| CIR-006 | Financial edits to completed/cancelled Orders | Orders / financial controls | Open | Needs focused fix and regression coverage. |
| CIR-007 | Duplicate current Work Orders under concurrency | Work Orders | Open | Needs focused fix and regression coverage. |
| CIR-008 | Missing restricted-store access enforcement | Public Webstores / access control | Open | Needs focused fix and regression coverage. |
| CIR-009 | Manufactured lifecycle milestone states | Webstores lifecycle | Open | Needs focused fix and regression coverage. |
| CIR-010 | Committed runtime logs | Repository hygiene | Open | Needs cleanup in a separate housekeeping pass. |
| CIR-011 | Oversized Webstores files | Webstores maintainability | Open | Needs targeted file split/refactor after current stage acceptance. |
| CIR-012 | React-version documentation mismatch | Frontend docs / dependencies | Open | Needs docs/dependency reconciliation. |
| CIR-013 | Deleted financial failure records instead of preserved audit history | Financial audit history | Open | Needs append-only/audit-preserving correction. |
| CIR-014 | Missing public-link default expiration | Shared Form Maker public requests | Fixed / Verified | Fixed with default 14-day expiration in `backend/app/services/forms_service.py`. Verified by `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_forms_stage3_webstore_adapter.py backend/tests/test_webstores_stage2_setup.py -q`. |
| CIR-015 | Reusable public submission links | Shared Form Maker public requests | Fixed / Verified | Fixed by rejecting already submitted public form requests. Verified by `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_forms_stage3_webstore_adapter.py backend/tests/test_webstores_stage2_setup.py -q`. |
| CIR-016 | Public submission using the latest template instead of its frozen snapshot | Shared Form Maker version snapshots | Fixed / Verified | Fixed by storing and submitting against the request's public-safe template snapshot. Verified by `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_forms_stage3_webstore_adapter.py backend/tests/test_webstores_stage2_setup.py -q`. |
| CIR-017 | Incomplete backend response validation | Shared Form Maker public responses | Fixed / Verified | Fixed with backend required-field, validation, and conditional-visibility enforcement. Verified by `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_forms_stage3_webstore_adapter.py backend/tests/test_webstores_stage2_setup.py -q`. |
| CIR-018 | Cross-tenant public attachment references | Shared Form Maker / DocuLink refs | Fixed / Verified | Fixed by tenant-validating submitted `file_id` attachment refs. Verified by `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_forms_stage3_webstore_adapter.py backend/tests/test_webstores_stage2_setup.py -q`. |
| CIR-019 | Legacy Webstore questionnaire writes acting as a second authority | Webstores questionnaire adapter | Fixed / Verified | Fixed by blocking legacy Webstore questionnaire template writes and routing reads through shared Form Maker-backed templates. Verified by `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_forms_stage3_webstore_adapter.py backend/tests/test_webstores_stage2_setup.py -q`. |

