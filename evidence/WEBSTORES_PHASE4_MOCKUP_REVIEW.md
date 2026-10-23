# Webstores Phase 4: manual mockup preparation and visual owner review

Base: PR #64 merged into main at `d5fb0861af7a437b4b34f69b3d5effb2686b1f58`. Owner explicitly authorized this next independent increment while P1/P2 remain held. Continue the existing nine-phase roadmap; this is not completion of all Phase 4.

## Remaining Phase 4 classification

| Requirement | Current disposition / dependency |
| --- | --- |
| Questionnaire explanations, unmatched requests, explicit template selection and private draft creation | Already implemented in PR #64; reused unchanged. Recommendations do not verify supplier stock, capabilities or pricing. |
| Product editor, manual colors/sizes/SKUs, personalization, categories and cents fields | Existing working canonical product CRUD; reused. Owner now also sees submitted option/personalization labels. Manual values are not Engine calculations or supplier confirmations. |
| Managed artwork, mockup records and independent approval decisions | Existing backend services; missing editor preparation and visual owner image review completed here. Independent of pricing migration. |
| Submitted product snapshots, approval history and private further revisions | PR #64 architecture retained. This increment connects immutable mockup files to those submitted IDs and preserves their decision metadata through private replacement. |
| Saved item/configuration/package to Webstore offer linkage | Still requires the canonical P1/P2 receiving contracts and approved source ownership. No speculative contract added. |
| Engine-priced proposals, unit/batch basis, cost completeness, minima, safeguards and repricing | Held for the existing Price Lab stability gates, P1 qualification/authorization and P2 integration. No Engine or Price Lab changes in this increment. |
| Starter library governance, assumed batch/MOQ shortfalls, fulfillment defaults | D-16, D-23 and D-24 remain unresolved owner decisions for their owning slices. No default policy invented. |
| Automatic AI images, supplier integration and subsequent Phase 4 features | Not implemented or called here. Real AI additionally requires approved provider/image capability and metering integration, independent of the manual path. |

## Implemented boundary

The existing **Images and Mockups** tab now uploads/selects managed files, registers customer artwork through the existing artwork service, previews a prepared mockup with staff authentication, and requires explicit staff review before attaching it to the private product draft. Existing association controls moved here from Review Status, avoiding a duplicate association panel. Save Product remains the canonical revision update; existing Send Product Approval freezes the product. Existing Send Mockup Approval is enabled only for a reviewed mockup in the saved current product submission. The backend enforces the same sequence and tenant/product artwork scope.

Staff artwork/mockup uploads use existing canonical FileRecord `internal` visibility. The owner general setup-file list and download route exclude these private files. Submitted mockup images are delivered only by a protected product/mockup image route: active owner/manager assignment, tenant/store/product scope, verifiable submitted snapshot membership, shop review and existing safe inline-image rules are required. No storage keys or private file IDs are returned to owners. Anonymous, foreign tenant, revoked owner and unsubmitted-image requests are denied. Public product eligibility is unchanged.

Mockup file references are immutable through existing APIs: a replacement uses another canonical mockup record and changes the product association through the existing product revision service. No new snapshot store/versioning framework is introduced. An internal `mockup_associations_managed` marker distinguishes explicit association removal from the pre-existing fallback for legacy `owner_visible` records; removing the last selected mockup must not silently restore an old one. Existing legacy fallback remains for untouched records.

Owner product decisions now use the verified submitted snapshot, with existing revision/invalidation/hash guards. Approving a mockup first therefore does not invalidate the pending product merely because mockup decision metadata changed. Owner decision badges are refreshed only for the same frozen mockup content/IDs, including after a private replacement; new draft mockups never enter that projection. Owner requests for changes still require a comment, including when the product has already been approved and a mockup remains pending.

The shared authenticated media renderer accepts an optional image class so mockups show their entire image at review size. Existing callers retain their original styling. The deferred staff product thumbnail and duplicate Create Custom Product controls are unchanged.

## Verification

- Focused backend: 21 passed across new mockup review, PR #64 visibility, Stage 4a, Stage 4b and Stage 5 compatibility tests. After the final retained-decision/image-availability adjustment, 17 passed across mockup review, owner visibility and existing Stage 2 setup/file tests. These overlap; they are not additive suite totals.
- Focused frontend: 25 distinct tests passed across mockup preparation, owner approvals, product foundation and recommendations. After the final mockup query refresh, the 11 affected preparation/foundation tests passed again. Existing foundation test mock logs a known unrelated undefined `webstore-messages` query warning; assertions pass.
- New backend cases cover approve/request-changes, artwork upload, staff review gates, foreign artwork, read-only staff denial, tenant/owner/revoked isolation, protected bytes, direct setup download denial, private replacement, resubmission, unchanged submission evidence and retained approved product/history. Existing visibility cases cover public eligibility and approval invalidation.
- Actual application browser checks used the existing disposable harness: private MongoDB prefix, run-owned storage, normal staff/owner password authentication, dev bypass disabled, provider credentials blank. No normal shop data, payments, orders or paid AI calls were used. Staff selected Hat from recommendations; configured Navy/Adjustable, SKU and manual sample $32; uploaded customer artwork and a prepared PNG; explicitly reviewed/attached/saved; confirmed owner branding/product view omitted the unsubmitted Hat; submitted product and mockup; owner saw the real image/options and approved mockup then product; staff saved a new private name and additional alternate image; owner retained the submitted Hat/$32/original image/history and explanatory notice. Full replacement, request changes and resubmission are also exercised by focused backend tests.
- Normal CI is the repository's unchanged push/PR workflow: backend suite, frontend suite and production build on both events. The exact head, final six-check receipt and draft PR URL are recorded in the PR/checks and the existing local nine-phase checklist. No manual CI rerun is required absent a concrete failure.
- Final three mockup cases passed after adding retained replaced-file bytes and removal-of-all-associations assertions. The submitted image lookup includes replaced links while still rejecting removed files and preserving the snapshot/tenant/owner guards. The run-owned browser server, frontend and private MongoDB were disposed after capture.

## Actual browser evidence

All files below are actual browser captures of the isolated app, not substitute UI mockups. The Hat artwork is a clearly labeled manual workflow illustration in `backend/tests/fixtures/webstore-hat-mockup.png`, not a supplier/decoration capability claim or AI output. Full-page images preserve workspace context; the owner detail is a direct browser capture of the product card.

- `screenshots/phase4-mockup-staff-private.jpg`: reviewed image attached to the saved, not-submitted staff draft.
- `screenshots/phase4-mockup-owner-private-hidden.jpg`: owner setup and branding omit the unfinished Hat.
- `screenshots/phase4-mockup-owner-review.jpg`: submitted Hat image, Navy/Adjustable option and both decision controls.
- `screenshots/phase4-mockup-owner-approved.jpg`: owner approval succeeded.
- `screenshots/phase4-mockup-staff-revision.jpg`: staff can see the private name and alternate image alongside the old approved mockup.
- `screenshots/phase4-mockup-owner-retained.jpg` and `screenshots/phase4-mockup-owner-retained-detail.jpg`: owner sees only the last submitted version and original image/history.

The older seeded tee has no actual mockup file. Early full-page captures consequently show its legacy metadata with an unavailable-image placeholder; final projection omits an image URL for records without a reviewed file. A namespace-less SVG test file was accepted by existing upload checks but did not render; the workflow was completed with PNG. Existing SVG sanitization rejects standard namespace URLs; that separate existing file-policy limitation was not weakened or repaired here. PNG/JPG/WebP remain the dependable manual path.

## AI readiness: real versus placeholder

`webstore_staff_ai.py` already invokes canonical AI Studio/Gateway through capability lookup, Webstores/AI entitlements, permission checks, credit-account preview, explicit exact-credit confirmation, idempotency, saved action/result and usage records. This is real orchestration and metering, **currently backed by local mock output** (`h7_local_mock`, `external_provider_calls: 0`). Its Webstore mockup action sends text context and returns saved text/JSON; it neither ingests logo pixels nor generates/stores an image. A mockup label/cost button is not proof of real image generation. The panel now states that clearly before execution and warns that confirming a local demonstration still uses the displayed credits.

Future real image generation must extend the existing approved Gateway capability/provider adapter with permission-checked artwork input, compatible image output and existing cost/credit controls. Persist successful output via the same FileRecord/FileLink storage and WebstoreMockup association, initially private and unreviewed. Staff must inspect the returned image and approve its use before normal product submission. Failed/retried generations must use existing action idempotency and credit settlement rules; no second AI service, asset library or approval workflow is needed. Provider selection, actual image generation and paid evaluation remain unauthorized. This increment prepares the manual review/storage destination, not a ready-to-enable provider integration.

## Next boundary

One focused draft PR; owner acceptance required. No merge or deployment. After acceptance, prioritize qualification of the canonical saved product/configuration/package and pricing proposal path under the existing P1/P2 gates when separately authorized. Until those contracts are approved, do not introduce provisional Webstore pricing, batch/MOQ or fulfillment policies. Real AI and supplier automation can be postponed; the manual mockup review path works without them. No onboarding, Help Center or Business Assistant work is included.
