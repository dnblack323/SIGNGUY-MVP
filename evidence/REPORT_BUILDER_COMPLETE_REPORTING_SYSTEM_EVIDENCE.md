# Report Builder Complete Reporting System Evidence

**Branch:** `CODEX-reports-complete-reporting-system`

**Controlling authority:** `/app/specs_pack/source/SIGNGUY_AI_REPORT_CATALOG_AND_CUSTOM_REPORT_BUILDER_SPEC.pdf`

**Extracted text:** `/app/specs_pack/extracted/SIGNGUY_AI_REPORT_CATALOG_AND_CUSTOM_REPORT_BUILDER_SPEC.txt`

## Source Document Verification

- Title confirmed from page 1: `SIGNGUY AI | REPORT CATALOG & CUSTOM REPORT BUILDER SPEC`.
- Page count confirmed: 11 pages.
- Rendered inspection used the preserved PDF copy and a temporary local render under `tmp/pdfs/report_builder/`; those generated render artifacts are not part of the checkpoint.
- The older donor document `signguyai/memory/BUSINESS_FINANCE_REPORTING_ANALYTICS_REBUILD_DOC.md` was treated as supporting evidence only.

## Owner Decisions Applied

- Current application location is `Business & Finance -> Reports`.
- Official Webstore types are `B2B`, `Fundraiser`, `Event`, `Promotional`, and `General`.
- The PDF's older `Business Management -> Reports` label is superseded.
- The PDF/source discrepancy around an `Employee` Webstore type is recorded; reporting remains extensible and groups unknown or legacy values as `other_or_legacy` instead of adding `Employee` as an official type.

## Implemented Runtime Scope

- Preserved the controlling PDF and extracted searchable text in the repository specification structure.
- Expanded the backend standard report catalog with PDF-governed report families:
  - Overview
  - Financial
  - Operations
  - Customers & Sales
  - Webstores
  - Materials & Purchasing
  - Team & Labor
  - Wrap Lab
- Expanded Custom Report Builder datasets using allowlisted collections, fields, filters, grouping, and sorting.
- Added saved report definitions with tenant ownership, selected-user sharing, role sharing, archive/restore, duplicate, and fresh run behavior.
- Added export generation for CSV, XLSX, PDF, print, and specialized CSV variants.
- Added export history records.
- Added report schedules and manual schedule run history. Delivery is recorded as `test_no_email`; no production email/background worker was added.
- Added drill-down metadata on implemented report rows where source routes currently exist.
- Added tenant-scoped indexes for saved definitions, export history, schedules, and schedule runs.
- Rebuilt the Reports frontend workspace under the existing `/reports` route.

## Boundaries Preserved

- No dashboard customizer rebuild was started.
- No Webstore payout or storefront rebuild was started.
- No Wrap Lab workflow rebuild was started.
- No pricing, billing, authentication, deployment, EC19, or EC20 work was started.
- Routine report preview/run does not create saved definitions or export records.
- Reports read stored source values; they do not recalculate pricing, payouts, payroll tax, or commerce source totals.
- Blocked PDF requirements remain visible as blocked/deferred, not faked with demo data.

## Verification

- Focused backend reports suite: `10 passed, 6 warnings`.
  - Command: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_ec7_reports.py backend\tests\test_report_builder_complete_system.py`
- Focused frontend Reports workspace suite: `4 passed`.
  - Command: `npm.cmd test -- --runInBand --watchAll=false ReportsPageComplete.test.jsx`

## Remaining Blockers

- Dashboard widget publishing requires the future Dashboard Customizer contract.
- Detailed Webstore payout reports require the deferred Webstore payout rebuild.
- Deep Wrap Lab workflow analytics require the deferred Wrap Lab workflow rebuild.
- Payroll tax filing exports require statutory withholding/deduction contracts that do not exist yet.
- Production scheduled email/background delivery is not implemented; schedules can be created and manually run with durable run/export history.

## Status

`REPORT BUILDER IMPLEMENTED WITH DOCUMENTED SOURCE-CONTRACT BLOCKERS - READY FOR REVIEW`
