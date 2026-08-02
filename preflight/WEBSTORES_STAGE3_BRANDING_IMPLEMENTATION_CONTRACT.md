# Webstores Stage 3 Branding Implementation Contract

Repository: `dnblack323/SIGNGUY-MVP`

Expected baseline: `5071d9d188c6d26b927155c15180c11d3d018601`

Status: planning-only implementation contract. This document authorizes no
application implementation by itself.

## 1. Scope and Locked Decisions

Stage 3 is limited to Webstore Branding and Storefront Presentation Foundation.

Stage 3 must implement:

- A structured branding draft workspace for staff, assigned Store Owners, and
  assigned Store Managers.
- Immutable branding versions.
- Owner and staff approval of exact immutable review snapshots.
- Activation through the authoritative `webstores.active_branding_version_id`
  pointer.
- Public storefront presentation from the active approved branding version only.
- Public-safe image derivative processing and serving.
- Draft-only import from Stage 2 owner intake answers and setup files.
- Branding readiness that is deterministic and separate from launch, catalog,
  checkout, Stripe, donation, payout, AI, or product setup readiness.

Locked decisions:

- `webstores.active_branding_version_id` is the only authoritative active
  branding pointer.
- Active branding remains in use while a later working draft exists.
- A working draft may be consumed by activation and retained as frozen history.
- A new working draft may be created after activation while an active version
  exists.
- Review snapshots, approvals, invalidations, versions, activation events,
  derivative metadata, cleanup events, and audit events are append-only except
  where this document explicitly defines operation-status updates.
- Store Managers may request Owner Review and may respond to requested changes
  by editing permitted draft fields.
- Store Managers may not issue owner change-request decisions, staff
  change-request decisions, Owner approval, staff approval, activation, or
  restore.
- Private source files never become public assets.
- Public asset bytes are served only when the requested derivative is referenced
  by the current active branding version and the Webstore public route gate
  passes.

Explicit exclusions:

- No Stage 4 catalog work.
- No EC4 work.
- No unrelated EC9 work.
- No Stripe Checkout.
- No payment provider integration.
- No donations implementation.
- No payout implementation.
- No AI image generation or AI content generation.
- No launch-packet approval reuse.
- No Webstore Launch readiness replacement.
- No pricing, Banner calculator, Quote, Order, Work Order, or customer portal
  change.

## 2. Current Repository Inventory

The following files were verified as present in the repository at the expected
baseline.

### `backend/app/models/webstore.py`

Current classes:

- `WebstoreOwner`
- `Webstore`
- `WebstoreProductTemplate`
- `WebstoreProduct`
- `WebstoreQuestionnaireSubmission`
- `WebstoreAccessAssignment`
- `WebstoreInvitation`
- `WebstoreQuestionnaireTemplate`
- `WebstoreSetupFile`
- `WebstoreAnswerApplication`
- `WebstoreArtworkFile`
- `WebstoreMockup`
- `WebstoreLaunchPacket`
- `WebstoreBuyerOrder`
- `WebstorePurchaseIntent`
- `WebstorePaymentEvent`
- `WebstoreLedgerEntry`
- `WebstoreActivity`
- `WebstoreAIUsageEvent`
- `WebstoreStripeConnectRecord`

Current constants and fields:

- `WEBSTORE_TYPES = ("b2b", "fundraiser", "event", "promotional", "employee", "general")`
- `WEBSTORE_LIFECYCLE_STATES`
- `Webstore.public_slug`
- `Webstore.store_type`
- `Webstore.status`
- `Webstore.description`
- `Webstore.branding`
- `Webstore.checkout_enabled`
- `Webstore.public_url`
- `Webstore.setup_state`
- `Webstore.setup_profile`
- `Webstore.setup_requirements`
- `Webstore.primary_owner_assignment_id`

Current behavior:

- `Webstore.branding` is a loose dictionary.
- No active branding version pointer exists.
- No typed branding draft/version/approval/derivative contracts exist.

Preserved behavior:

- Six Webstore types remain canonical.
- Existing Stage 1 purchase-intent and payment-event models remain unchanged.
- Existing Stage 2 owner/manager assignment and setup models remain unchanged.

Stage 3 modification:

- Add typed branding models in this file.
- Add `active_branding_version_id`, `active_branding_snapshot_hash`,
  `branding_activation_operation_id`, `branding_activated_at`, and
  `branding_activated_by_user_id` to `Webstore`.
- Preserve legacy `branding` only as compatibility input for initializing a new
  draft. It is not public authority.

What must not be reused:

- `Webstore.branding` must not be serialized directly to public storefronts.
- `Webstore.owner_approved_at` must not be used as branding approval.
- `Webstore.launch_packet_id` must not be used as branding version evidence.

Compatibility risk:

- Existing records may contain arbitrary `branding` data. Stage 3 readers must
  treat legacy `branding` as untrusted and must not publish it unless it has
  been converted into a Stage 3 immutable version through review, approval, and
  activation.

### `backend/app/services/webstores.py`

Current functions relevant to Stage 3:

- `_public_store`
- `_portal_store`
- `_public_product`
- `_ensure_public_slug`
- `_storefront_by_slug`
- `public_storefront`
- `launch_readiness`
- `_audit`
- `_owner_portal_store`
- `owner_portal_list`
- `owner_portal_detail`
- `create_artwork`
- `create_mockup`
- `generate_launch_packet`
- `owner_approve_launch_packet`
- `reports`

Current behavior:

- `_public_store` includes the loose `branding` dictionary.
- `_portal_store` includes the loose `branding` dictionary.
- `_storefront_by_slug` requires `store.status == "live"`.
- Public storefront products are filtered by tenant id, Webstore id, status
  `active`, and `public = True`.
- Checkout remains disabled by `PUBLIC_CHECKOUT_ENABLED = False`.
- `launch_readiness` computes `public_branding` from name, slug, and
  public slug only.
- `_owner_portal_store` enforces portal owner/manager assignment scope.

Preserved behavior:

- Public purchase-intent totals remain server-authoritative.
- Public checkout remains disabled.
- Live/closed/archive lifecycle gates remain unchanged.
- Existing launch-readiness route remains launch readiness, not branding
  readiness.

Stage 3 modification:

- Public storefront response must read active branding version and no longer
  expose loose `branding`.
- Portal response must expose only the portal branding serializer defined in
  this document.
- Add branding readiness as a separate service response.
- Add active-version public asset reference resolution.

What must not be reused:

- `create_artwork` must not be used as the derivative pipeline. It only creates
  artwork metadata.
- `owner_approve_launch_packet` must not be reused for Owner branding approval.
- `launch_readiness` must not be modified to claim complete Webstore readiness
  from branding alone.

Compatibility risk:

- Public storefront currently includes product fields such as `webstore_id`.
  Stage 3 must not add branding draft/version/internal ids to the public
  response.

### `backend/app/services/webstore_setup.py`

Current constants:

- `WEBSTORE_SETUP_STATES`
- `ACTIVE_ASSIGNMENT_STATUSES`
- `ACCEPTABLE_INVITATION_STATUSES`
- `MAX_SETUP_FILE_BYTES = 50 * 1024 * 1024`
- `SAFE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf", "svg", "ai", "eps", "csv", "xlsx", "docx"}`
- `DOWNLOAD_ONLY_EXTENSIONS = {"ai", "eps", "csv", "xlsx", "docx"}`
- `BLOCKED_EXTENSIONS`
- `LOCKED_ANSWER_FIELDS`
- `SAFE_ANSWER_MAPPING`

Current functions relevant to Stage 3:

- `_looks_like`
- `_detect_content_type`
- `_safe_file_record`
- `_svg_is_safe`
- `store_setup_file`
- `upload_setup_file`
- `portal_upload_setup_file`
- `list_setup_files`
- `portal_list_setup_files`
- `download_setup_file`
- `remove_setup_file`
- `answer_application_preview`
- `apply_questionnaire_answers`
- `reverse_answer_application`
- `_setup_progress`
- `_refresh_setup_state`

Current behavior:

- Staff and portal users can upload setup files.
- Setup file source bytes are stored with private `storage_key`.
- Basic signature checks exist for PNG, JPEG, WebP, PDF, and SVG.
- `_svg_is_safe` is marker-based and not sufficient for public SVG serving.
- `answer_application_preview` returns a dry-run of safe answer mappings.
- `apply_questionnaire_answers` directly mutates `webstores`.

Preserved behavior:

- Stage 2 setup files and owner intake remain private source data.
- Stage 2 setup progress remains separate from branding readiness.
- Stage 2 answer application remains available for its existing direct
  Webstore-field use.

Stage 3 modification:

- Add branding import-candidate functions that read Stage 2 answers/files and
  write only to a branding draft after explicit confirmation.
- Do not mutate the original questionnaire submission, setup file, or loose
  Webstore branding during branding import.

What must not be reused:

- `apply_questionnaire_answers` must not be used for Stage 3 branding import,
  because it mutates `webstores`.
- `_svg_is_safe` must not be treated as sufficient for public derivatives.

Compatibility risk:

- Existing setup files include AI/EPS. They are permitted as private source
  files but cannot become public derivatives.

### `backend/app/services/webstore_payments.py`

Current functions relevant to Stage 3:

- `_existing_event`
- `_wait_for_terminal_event`
- `_event_response`
- `process_verified_payment_event`

Current behavior:

- Verified-payment processing is internal-only.
- It uses unique provider event keys.
- It uses `find_one_and_update` to claim a purchase intent.
- It records processing, duplicate, and failed states.

Preserved behavior:

- Stage 3 must not change payment processing.

Stage 3 modification:

- Use the same repository-compatible strategy for branding activation:
  durable operation record, unique idempotency key, single-document CAS pointer
  update, and retryable recovery.

What must not be reused:

- Payment event collections and statuses must not be used for branding.

Compatibility risk:

- This repository does not currently rely on Mongo multi-document transactions
  for Webstore payment processing. Branding activation must therefore be
  recoverable without requiring a transaction.

### `backend/app/repositories/webstores.py`

Current class and methods:

- `WebstoreRepository`
- `insert`
- `get`
- `find_one`
- `list`
- `update`

Current behavior:

- `get`, `list`, and `update` are tenant-scoped.
- `update` writes `$set` and refreshes `updated_at`.

Preserved behavior:

- Repository helper remains usable for simple tenant-scoped reads and writes.

Stage 3 modification:

- Branding activation must use direct service-level `find_one_and_update`
  rather than repository `update`, because activation requires exact pointer
  and draft-revision CAS filters.

What must not be reused:

- Repository `update` must not be used for activation or draft consumption.

Compatibility risk:

- Generic updates are too broad for race-sensitive activation.

### `backend/app/routers/webstores.py`

Current route methods:

- `GET /webstores`
- `POST /webstores`
- `GET /webstores/setup/questionnaire-templates`
- `POST /webstores/setup/questionnaire-templates`
- `PATCH /webstores/setup/questionnaire-templates/{template_id}`
- `GET /webstores/{webstore_id}`
- `PATCH /webstores/{webstore_id}`
- `POST /webstores/{webstore_id}/status`
- `GET /webstores/{webstore_id}/launch-readiness`
- `GET /webstores/{webstore_id}/reports`
- `GET /webstores/{webstore_id}/setup-progress`
- `GET /webstores/{webstore_id}/assignments`
- `POST /webstores/{webstore_id}/assignments`
- `POST /webstores/{webstore_id}/assignments/{assignment_id}/resend`
- `POST /webstores/{webstore_id}/assignments/{assignment_id}/revoke`
- `POST /webstores/{webstore_id}/primary-owner`
- `GET /webstores/{webstore_id}/questionnaire`
- `GET /webstores/{webstore_id}/questionnaire-response`
- `POST /webstores/{webstore_id}/questionnaire/{submission_id}/return`
- `POST /webstores/{webstore_id}/questionnaire/apply-preview`
- `POST /webstores/{webstore_id}/questionnaire/apply`
- `POST /webstores/{webstore_id}/answer-applications/{application_id}/reverse`
- `GET /webstores/{webstore_id}/setup-files`
- `POST /webstores/{webstore_id}/setup-files`
- `GET /webstores/{webstore_id}/setup-files/{file_id}/download`
- `POST /webstores/{webstore_id}/setup-files/{file_id}/remove`
- `POST /webstores/{webstore_id}/products`
- `GET /webstores/{webstore_id}/products`
- `POST /webstores/{webstore_id}/artwork`
- `POST /webstores/{webstore_id}/mockups`
- `POST /webstores/{webstore_id}/ai-contracts`
- `POST /webstores/{webstore_id}/launch-packets`
- `POST /webstores/{webstore_id}/launch-packets/{packet_id}/send`
- `POST /webstores/buyer-orders/{buyer_order_id}/bridge`
- `POST /webstores/ledger/{ledger_entry_id}/platform-fee-reversals`
- `GET /webstores/owners/list`
- `POST /webstores/owners`
- `GET /webstores/product-templates/list`
- `POST /webstores/product-templates`

Current permission helper:

- Routes use `get_current_user`.
- Service functions enforce `Perm.WEBSTORE_READ`, `Perm.WEBSTORE_WRITE`, and
  `Perm.WEBSTORE_MANAGE`.

Preserved behavior:

- Existing routes remain.

Stage 3 modification:

- Add staff branding routes under `/webstores/{webstore_id}/branding`.

What must not be reused:

- `PATCH /webstores/{webstore_id}` must not become a bypass for approved
  public branding.

Compatibility risk:

- Existing callers can still pass `branding` to `PATCH`; Stage 3 must prevent
  that loose field from becoming public authority.

### `backend/app/routers/webstore_owner_portal.py`

Current route methods:

- `GET /portal/webstores`
- `POST /portal/webstores/invitations/accept`
- `GET /portal/webstores/{webstore_id}`
- `POST /portal/webstores/{webstore_id}/questionnaire`
- `GET /portal/webstores/{webstore_id}/questionnaire`
- `POST /portal/webstores/{webstore_id}/questionnaire/draft`
- `GET /portal/webstores/{webstore_id}/setup-progress`
- `GET /portal/webstores/{webstore_id}/setup-files`
- `POST /portal/webstores/{webstore_id}/setup-files`
- `GET /portal/webstores/{webstore_id}/setup-files/{file_id}/download`
- `POST /portal/webstores/{webstore_id}/launch-packets/{packet_id}/approve`

Current portal identity helper:

- `_webstore_identity` accepts `portal_type` values `webstore_owner` and
  `webstore_manager`.
- It requires portal permission `portal:webstore_owner_admin` or
  `portal:webstore_manager_ops`.

Preserved behavior:

- Owner/manager portal authentication and setup workflow stay intact.

Stage 3 modification:

- Add portal branding routes for draft read/edit, preview, request owner
  review, request changes, Owner approval, and portal-safe history.

What must not be reused:

- `approve_launch` must not be reused for branding approval.

Compatibility risk:

- Manager and owner are currently accepted by the same route dependency.
  Stage 3 service-level checks must separate Store Owner and Store Manager
  authority.

### `backend/app/routers/public_webstores.py`

Current route methods:

- `GET /public/webstores/{slug}`
- `POST /public/webstores/{slug}/buyer-orders`
- `POST /public/webstores/{slug}/purchase-intents`

Current behavior:

- `GET /public/webstores/{slug}` calls `public_storefront`.
- Buyer order route calls `create_purchase_intent`.
- Purchase intent route calls `create_purchase_intent`.

Preserved behavior:

- Checkout remains disabled.
- Purchase requests do not create canonical orders.

Stage 3 modification:

- Add `GET /public/webstores/{slug}/assets/{public_asset_key}`.
- Public storefront route reads active branding version.

What must not be reused:

- Public purchase routes must not serve branding asset bytes.

Compatibility risk:

- Public asset-key guessing must reveal neither existence nor private metadata
  for draft or inactive assets.

### `backend/app/core/db.py`

Current Webstore index definitions:

- `webstore_owners.id`
- `webstore_owners.tenant_id,email`
- `webstore_owners.tenant_id,status`
- `webstore_owners.tenant_id,portal_identity_id`
- `webstores.id`
- `webstores.tenant_id,slug`
- `webstores.public_slug`
- `webstores.tenant_id,owner_id`
- `webstores.tenant_id,status,updated_at`
- `webstores.tenant_id,setup_state,updated_at`
- `webstores.tenant_id,creation_idempotency_key`
- `webstores.tenant_id,launched_at`
- `webstore_access_assignments.id`
- `webstore_access_assignments.tenant_id,webstore_id,role,status`
- `webstore_access_assignments.tenant_id,webstore_id,email,role,status`
- `webstore_access_assignments.tenant_id,webstore_id,is_primary_owner`
- `webstore_setup_files.id`
- `webstore_setup_files.tenant_id,webstore_id,status,created_at`
- `webstore_setup_files.tenant_id,webstore_id,category,version`
- `webstore_answer_applications.id`
- `webstore_answer_applications.tenant_id,webstore_id,idempotency_key`
- `webstore_purchase_intents` idempotency and provider indexes
- `webstore_payment_events` provider event indexes
- `webstore_activity_events` tenant/Webstore indexes

Preserved behavior:

- Existing Stage 1 and Stage 2 indexes remain unchanged.

Stage 3 modification:

- Add the branding indexes specified in section 7.

What must not be reused:

- Existing `webstores.public_slug` uniqueness is for slug routing only. It is
  not active branding version uniqueness.

Compatibility risk:

- Adding a unique snapshot-hash index would block valid restored versions.

### `backend/app/core/permissions.py`

Current relevant permissions:

- `Perm.WEBSTORE_READ = "webstore:read"`
- `Perm.WEBSTORE_WRITE = "webstore:write"`
- `Perm.WEBSTORE_MANAGE = "webstore:manage"`
- `PortalPerm.PORTAL_WEBSTORE_OWNER_ADMIN`
- `PortalPerm.PORTAL_WEBSTORE_MANAGER_OPS`
- `has_platform_admin_access`

Preserved behavior:

- Staff permissions remain role-derived.
- Portal permissions do not satisfy tenant staff permissions.
- Platform permissions do not satisfy ordinary tenant `Perm` checks.

Stage 3 modification:

- No new permission strings are required for Stage 3.
- Service checks use existing Webstore permissions and portal assignment rows.

What must not be reused:

- Platform admin must not automatically impersonate a tenant user.

Compatibility risk:

- Platform support access must be explicit and audited if used.

### `backend/app/services/storage.py`

Current functions:

- `_storage_root`
- `_safe_storage_path`
- `initialize`
- `build_key`
- `put_bytes`
- `get_bytes`

Current behavior:

- Storage keys are backend-owned and tenant-scoped.
- Storage keys are not public URLs.
- Test environment uses in-memory object storage.

Preserved behavior:

- Private source bytes remain backend-proxied.

Stage 3 modification:

- Use service-specific keys for private branding sources, temporary derivative
  output, and final immutable derivative output.

What must not be reused:

- Raw storage key must not be returned as `public_asset_key`.

Compatibility risk:

- `get_bytes` returns `application/octet-stream`; derivative metadata must carry
  public response `Content-Type`.

### `backend/app/services/audit.py`

Current functions:

- `record_audit`
- `list_audit`

Current behavior:

- `record_audit` requires `actor_user_id` and `actor_email`.

Preserved behavior:

- Stage 3 writes must include actor id and actor email.

Stage 3 modification:

- Add branding write events through existing audit helper and Webstore activity
  helper.

What must not be reused:

- Audit `diff` must not contain storage keys, token hashes, source bytes, or
  credentials.

Compatibility risk:

- Activation audit failure must be recoverable without corrupting active
  pointer ownership.

### `frontend/src/pages/WebstoreDetailPage.jsx`

Current components and behavior:

- Uses `PageHeader`.
- Uses cards for Setup Progress, Owners and Managers, Setup Files,
  Questionnaire Review, Launch Gates, Products, Launch Packet, Reporting.
- Uses API wrappers from `frontend/src/lib/webstores.js`.
- Launch button calls `setWebstoreStatus(id, "live")`.
- Public link uses `store.public_url` or public slug.

Preserved behavior:

- Existing setup, assignments, files, questionnaire, launch gate, product, and
  reporting panels remain.

Stage 3 modification:

- Add Branding tab/panel inside this page.
- Add staff editor, preview, validation, approvals, activation controls, asset
  picker, import intake, and history.

What must not be reused:

- Launch button must not activate branding.
- Answer application controls must not directly write branding.

Compatibility risk:

- The page is already dense; Stage 3 must use tabs/panels rather than adding
  another long unstructured card stack.

### `frontend/src/pages/WebstoreOwnerPortalPage.jsx`

Current components and behavior:

- Shows setup progress.
- Shows questionnaire.
- Shows setup files.
- Shows products.
- Shows launch packet approval.
- Uses `portalApi`.

Preserved behavior:

- Existing owner intake workflow remains.

Stage 3 modification:

- Add branding editor and portal-safe history.
- Add Owner approval action.
- Add Manager request-review and response-to-changes behavior.

What must not be reused:

- `Approve launch` must not approve branding.

Compatibility risk:

- Owner and manager route access is shared; UI and backend must enforce
  different capability results.

### `frontend/src/pages/PublicWebstorePage.jsx`

Current behavior:

- Fetches `/public/webstores/{slug}`.
- Displays Webstore name and description.
- Displays product cards.
- Shows disabled checkout explanation.
- Saves purchase request through `/purchase-intents`.

Preserved behavior:

- Disabled checkout messaging remains.
- Product display and purchase request behavior remain Stage 1 behavior.

Stage 3 modification:

- Render active branding fields from public storefront serializer.
- Fetch public asset URLs generated from active derivative references.

What must not be reused:

- Authenticated preview endpoints must not be used by the public page.

Compatibility risk:

- Draft branding must not leak to the public route.

### `frontend/src/lib/webstores.js`

Current API wrappers:

- `listWebstores`
- `getWebstore`
- `createWebstoreOwner`
- `createWebstore`
- `getWebstoreSetupProgress`
- `listWebstoreAssignments`
- `createWebstoreAssignment`
- `resendWebstoreInvitation`
- `revokeWebstoreAssignment`
- `getWebstoreQuestionnaire`
- `getWebstoreQuestionnaireResponse`
- `previewWebstoreAnswerApplication`
- `applyWebstoreAnswers`
- `reverseWebstoreAnswerApplication`
- `listWebstoreSetupFiles`
- `uploadWebstoreSetupFile`
- `listProductTemplates`
- `createProductFromTemplate`
- `updateWebstore`
- `generateLaunchPacket`
- `sendLaunchPacket`
- `getLaunchReadiness`
- `setWebstoreStatus`
- `getWebstoreReports`

Preserved behavior:

- Existing wrappers remain.

Stage 3 modification:

- Add wrappers for branding draft, save, import candidates, derivative
  generation, preview, request review, request changes, owner approve, staff
  approve, activate, restore, history, and readiness.

What must not be reused:

- `updateWebstore` must not write approved public branding.

Compatibility risk:

- Frontend could accidentally keep using loose `branding`; tests must assert
  Stage 3 routes are used.

### `frontend/src/lib/navigation.js`

Current definitions:

- `PRIMARY_NAV_AREAS`
- Shop Operations module includes `webstores` at `/webstores`.
- `findAreaForPath`
- `activeModuleForPath`
- `NAV_AREAS`

Preserved behavior:

- Webstores remains under Shop Operations.
- No new primary app area is created.

Stage 3 modification:

- Add Webstore Detail contextual ribbon command definitions when the active
  route is `/webstores/:id`.

What must not be reused:

- Do not add a separate branding module tab under Shop Operations.

Compatibility risk:

- Stage 3 actions must not duplicate module navigation.

### `frontend/src/components/app-shell/AppShell.jsx`

Current behavior:

- Renders primary sidebar, module navigation, contextual ribbon, quick access
  toolbar, and workspace dock reserved space.
- Shows auth-bypass banner when development bypass is active.

Preserved behavior:

- Shell structure remains.

Stage 3 modification:

- No planned change. If command rendering already supports route-specific
  commands from `navigation.js`, this file remains unchanged.

What must not be reused:

- App shell must not contain Webstore-specific business logic.

Compatibility risk:

- Shell edits can affect unrelated app layout, so Stage 3 must avoid this file.

## 3. Canonical Terminology

`Working draft`:

- Editable branding record for one Webstore.
- Stored in `webstore_branding_drafts`.
- At most one current editable draft per Webstore.

`Consumed draft`:

- A draft that was successfully activated.
- Stored in `webstore_branding_drafts`.
- Has `editable = false`.
- Has `activated_at`.
- Has `activated_version_id`.

`Review cycle`:

- One review attempt for one draft revision.
- Has `review_cycle`.
- Created when Owner Review is requested.
- Replaced by a new `review_cycle` after any material edit.

`Review snapshot`:

- Immutable copy of draft content, derivative references, validation result,
  and snapshot hash for approval.
- Has `review_snapshot_id`.

`Approval`:

- Immutable owner or staff approval row tied to one `review_snapshot_id`,
  `snapshot_hash`, and `draft_revision`.

`Approval invalidation`:

- Immutable event proving a previous review cycle is no longer current because
  draft content materially changed.

`Branding version`:

- Immutable public-serving candidate created from an approved review snapshot.
- Stored in `webstore_branding_versions`.

`Active branding version`:

- The branding version id stored on `webstores.active_branding_version_id`.

`Private source asset`:

- Original uploaded or imported source file.
- Never served publicly.

`Public derivative`:

- Sanitized, processed, immutable output referenced by a branding version.
- Served publicly only through the active-version asset route.

`Public route gate`:

- Public Webstore slug exists.
- Webstore record exists.
- Webstore `status == "live"`.
- Webstore has `active_branding_version_id`.
- Requested derivative is referenced by that exact active version.
- Derivative metadata status is `available`.
- Derivative `retired_at` is absent.

## 4. Draft Lifecycle Transition Table

States permitting material edits:

- `draft`
- `changes_requested_by_owner`
- `changes_requested_by_staff`

States rejecting material edits:

- `review_requested`
- `owner_approved`
- `staff_approved`
- `ready_for_activation`
- any draft with `activation_lock_operation_id` present
- any draft with `editable = false`
- any draft with `consumed_at` present

Nonmaterial save:

- Permitted in `draft`, `changes_requested_by_owner`, and
  `changes_requested_by_staff`.
- Updates only nonmaterial UI metadata such as local collapsed editor panels or
  non-public staff workspace preferences when those fields exist.
- Does not increment `draft_revision`.
- Does not change `state`.
- Does not change `review_cycle`.
- Does not change `review_snapshot_id`.
- Does not affect approvals.
- Writes audit event `webstore.branding_draft_nonmaterial_saved`.
- Returns HTTP `200`.

Consumed draft edit request:

- Returns HTTP `409`.
- Error code: `BRANDING_DRAFT_CONSUMED`.
- No write occurs.
- No revision is created.
- No approval invalidation is created.
- Audit event: `webstore.branding_draft_edit_rejected_consumed`.

Change-request reopening:

- `Request Changes as Store Owner` or `Request Changes as staff` records one
  approval invalidation event and moves the draft into
  `changes_requested_by_owner` or `changes_requested_by_staff`.
- That request-changes decision is the only operation that writes the
  invalidation for the review cycle.
- The first successful material `Save Draft` after either change-request state
  increments `draft_revision`, changes `state` back to `draft`, clears the
  mutable current-review references `review_cycle`, `review_snapshot_id`,
  `snapshot_hash`, and `validation_result_id`, and preserves all historical
  snapshots, approvals, comments, invalidations, and audit events.
- The first material edit after requested changes does not create another
  invalidation event.

Staff approval recovery state:

- `staff_approved` is a real persisted state.
- The staff-approval operation first inserts the immutable staff approval, then
  transitions the draft to `staff_approved`, then creates the immutable branding
  version, then transitions the draft to `ready_for_activation`.
- If the staff-approval operation fails after inserting the staff approval, the
  draft remains locked in `staff_approved` until the same operation resumes.
- No edit, approval, new review request, request changes, restore, or activation
  is allowed while a staff-approval operation is incomplete.

| Starting state | Action | Actor/capability | Preconditions | Resulting state | Draft revision behavior | Review-cycle behavior | Approval effect | Audit event | HTTP result |
|---|---|---|---|---|---|---|---|---|---|
| none | Create draft | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned owner, assigned manager | Webstore exists in same tenant; no editable draft exists | `draft` | set `draft_revision = 1` | set `review_cycle = 1`; `review_snapshot_id = null` | none | `webstore.branding_draft_created` | `201` |
| none | Create draft from active version | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned owner, assigned manager | Webstore has active version; no editable draft exists | `draft` | set `draft_revision = 1` | set `review_cycle = active_version.review_cycle + 1`; `review_snapshot_id = null` | none | `webstore.branding_draft_created_from_active` | `201` |
| none | Portal create draft | assigned Store Owner or assigned Store Manager | Active assignment matches tenant, Webstore, portal identity, and status `active`; no editable draft exists | `draft` | set `draft_revision = 1` | set `review_cycle = 1` when no active version; otherwise set `review_cycle = active_version.review_cycle + 1`; `review_snapshot_id = null` | none | `webstore.branding_draft_created` | `201` |
| none | Restore as New Draft | staff `webstore:manage`, tenant admin, platform support with explicit tenant support context | Version exists in same tenant/Webstore; no editable draft exists | `draft` | set `draft_revision = 1` | set `review_cycle = restored_version.review_cycle + 1`; `review_snapshot_id = null` | none | `webstore.branding_version_restored_as_draft` | `201` |
| none | Create draft | any actor | An editable draft already exists | unchanged | unchanged | unchanged | unchanged | `webstore.branding_draft_create_rejected_existing_draft` | `409 EXISTING_BRANDING_DRAFT` |
| `draft` | Save material edit | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned owner, assigned manager | Draft `editable = true`; no activation lock; request `draft_revision` equals stored revision | `draft` | increment by 1 | unchanged when no current review cycle exists | none | `webstore.branding_draft_saved` | `200` |
| `changes_requested_by_owner` | Save material edit | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned owner, assigned manager | Draft `editable = true`; no activation lock; request revision and review cycle match; invalidation already exists from owner change request | `draft` | increment by 1 | increment `review_cycle` by 1 exactly once; clear `review_snapshot_id`, `snapshot_hash`, `validation_result_id`, `review_operation_id` | prior approvals remain historical | `webstore.branding_draft_saved_after_owner_changes` | `200` |
| `changes_requested_by_staff` | Save material edit | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned owner, assigned manager | Draft `editable = true`; no activation lock; request revision and review cycle match; invalidation already exists from staff change request | `draft` | increment by 1 | increment `review_cycle` by 1 exactly once; clear `review_snapshot_id`, `snapshot_hash`, `validation_result_id`, `review_operation_id` | prior approvals remain historical | `webstore.branding_draft_saved_after_staff_changes` | `200` |
| `draft` | Save nonmaterial edit | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned owner, assigned manager | Draft `editable = true`; no activation lock; request revision matches | `draft` | unchanged | unchanged | unchanged | `webstore.branding_draft_nonmaterial_saved` | `200` |
| `changes_requested_by_owner` | Save nonmaterial edit | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned owner, assigned manager | Draft `editable = true`; no activation lock; request revision matches | `changes_requested_by_owner` | unchanged | unchanged | unchanged | `webstore.branding_draft_nonmaterial_saved` | `200` |
| `changes_requested_by_staff` | Save nonmaterial edit | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned owner, assigned manager | Draft `editable = true`; no activation lock; request revision matches | `changes_requested_by_staff` | unchanged | unchanged | unchanged | `webstore.branding_draft_nonmaterial_saved` | `200` |
| `review_requested` | Save material edit | any actor | State is locked | `review_requested` | unchanged | unchanged | unchanged | `webstore.branding_draft_edit_rejected_locked` | `409 BRANDING_DRAFT_LOCKED` |
| `owner_approved` | Save material edit | any actor | State is locked | `owner_approved` | unchanged | unchanged | unchanged | `webstore.branding_draft_edit_rejected_locked` | `409 BRANDING_DRAFT_LOCKED` |
| `staff_approved` | Save material edit | any actor | Staff-approval operation incomplete or state locked | `staff_approved` | unchanged | unchanged | unchanged | `webstore.branding_draft_edit_rejected_staff_approval_in_progress` | `409 STAFF_APPROVAL_IN_PROGRESS` |
| `ready_for_activation` | Save material edit | any actor | State is locked | `ready_for_activation` | unchanged | unchanged | unchanged | `webstore.branding_draft_edit_rejected_locked` | `409 BRANDING_DRAFT_LOCKED` |
| any state | Save material edit | any actor | Draft has `activation_lock_operation_id` present | unchanged | unchanged | unchanged | unchanged | `webstore.branding_draft_edit_rejected_activation_in_progress` | `409 BRANDING_ACTIVATION_IN_PROGRESS` |
| any state | Save material edit | any actor | Draft `editable = false` or `consumed_at` present | unchanged | unchanged | unchanged | unchanged | `webstore.branding_draft_edit_rejected_consumed` | `409 BRANDING_DRAFT_CONSUMED` |
| `draft` | Request Owner Review | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned manager | Request-owner-review operation claim succeeds; draft revision and existing review cycle match; exact canonical content validates without blockers | `review_requested` | unchanged | reuse existing `review_cycle`; create `review_snapshot_id`, `review_operation_id`, and validation result through recoverable operation | none | `webstore.branding_owner_review_requested` | `200` |
| `changes_requested_by_owner` | Request Owner Review | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned manager | Rejected because a material save must return state to `draft` first | `changes_requested_by_owner` | unchanged | unchanged | unchanged | `webstore.branding_owner_review_request_rejected_changes_not_saved` | `409 CHANGES_MUST_BE_SAVED` |
| `changes_requested_by_staff` | Request Owner Review | staff `webstore:write`, staff `webstore:manage`, tenant admin, assigned manager | Rejected because a material save must return state to `draft` first | `changes_requested_by_staff` | unchanged | unchanged | unchanged | `webstore.branding_owner_review_request_rejected_changes_not_saved` | `409 CHANGES_MUST_BE_SAVED` |
| `review_requested` | Request Owner Review | any actor | Review already requested for current revision | `review_requested` | unchanged | unchanged | unchanged | `webstore.branding_owner_review_request_rejected` | `409 REVIEW_ALREADY_REQUESTED` |
| `owner_approved` | Request Owner Review | any actor | Owner approval already exists for current snapshot | `owner_approved` | unchanged | unchanged | unchanged | `webstore.branding_owner_review_request_rejected` | `409 REVIEW_ALREADY_APPROVED` |
| `staff_approved` | Request Owner Review | any actor | Staff approval operation in progress | `staff_approved` | unchanged | unchanged | unchanged | `webstore.branding_owner_review_request_rejected` | `409 STAFF_APPROVAL_IN_PROGRESS` |
| `ready_for_activation` | Request Owner Review | any actor | Version already ready for activation | `ready_for_activation` | unchanged | unchanged | unchanged | `webstore.branding_owner_review_request_rejected` | `409 BRANDING_READY_FOR_ACTIVATION` |
| `review_requested` | Request Changes as Store Owner | assigned owner | Snapshot matches current review; owner assignment active | `changes_requested_by_owner` | unchanged | append one invalidation event for current review cycle | no approval created | `webstore.branding_changes_requested_by_owner` | `200` |
| `owner_approved` | Request Changes as staff | staff `webstore:manage`, tenant admin, platform support with explicit tenant support context | Owner approval exists for current snapshot; staff actor authorized | `changes_requested_by_staff` | unchanged | append one invalidation event for current review cycle | owner approval remains historical | `webstore.branding_changes_requested_by_staff` | `200` |
| `review_requested` | Store Owner Approve | assigned owner | Review snapshot matches current draft; owner assignment active; validation snapshot matches; no blockers | `owner_approved` | unchanged | unchanged | insert owner approval | `webstore.branding_owner_approved` | `200` |
| `draft` | Store Owner Approve | assigned owner | No review snapshot | `draft` | unchanged | none | none | `webstore.branding_owner_approval_rejected` | `409 REVIEW_SNAPSHOT_REQUIRED` |
| `changes_requested_by_owner` | Store Owner Approve | assigned owner | Review cycle invalidated by request changes | `changes_requested_by_owner` | unchanged | invalidated | none | `webstore.branding_owner_approval_rejected` | `409 APPROVAL_INVALIDATED` |
| `changes_requested_by_staff` | Store Owner Approve | assigned owner | Review cycle invalidated by request changes | `changes_requested_by_staff` | unchanged | invalidated | none | `webstore.branding_owner_approval_rejected` | `409 APPROVAL_INVALIDATED` |
| `owner_approved` | Store Owner Approve | assigned owner | Owner approval already exists for current snapshot | `owner_approved` | unchanged | unchanged | unchanged | `webstore.branding_owner_approval_rejected_duplicate` | `409 OWNER_APPROVAL_EXISTS` |
| `staff_approved` | Store Owner Approve | assigned owner | Staff approval operation in progress | `staff_approved` | unchanged | unchanged | unchanged | `webstore.branding_owner_approval_rejected_duplicate` | `409 STAFF_APPROVAL_IN_PROGRESS` |
| `ready_for_activation` | Store Owner Approve | assigned owner | Version already ready for activation | `ready_for_activation` | unchanged | unchanged | unchanged | `webstore.branding_owner_approval_rejected_duplicate` | `409 BRANDING_READY_FOR_ACTIVATION` |
| `owner_approved` | Staff Approve | staff `webstore:manage`, tenant admin, platform support with explicit tenant support context | Staff-approval operation claim succeeds; owner approval and validation snapshot match exactly | `ready_for_activation` after persisted intermediate `staff_approved` | unchanged | unchanged | insert staff approval; allocate version number; create immutable version | `webstore.branding_staff_approved` and `webstore.branding_version_created` | `200` |
| `draft` | Staff Approve | staff `webstore:manage` | Owner approval missing | `draft` | unchanged | none | none | `webstore.branding_staff_approval_rejected` | `409 OWNER_APPROVAL_REQUIRED` |
| `review_requested` | Staff Approve | staff `webstore:manage` | Owner approval missing | `review_requested` | unchanged | unchanged | none | `webstore.branding_staff_approval_rejected` | `409 OWNER_APPROVAL_REQUIRED` |
| `changes_requested_by_owner` | Staff Approve | staff `webstore:manage` | Review cycle invalidated | `changes_requested_by_owner` | unchanged | invalidated | none | `webstore.branding_staff_approval_rejected` | `409 APPROVAL_INVALIDATED` |
| `changes_requested_by_staff` | Staff Approve | staff `webstore:manage` | Review cycle invalidated | `changes_requested_by_staff` | unchanged | invalidated | none | `webstore.branding_staff_approval_rejected` | `409 APPROVAL_INVALIDATED` |
| `staff_approved` | Staff Approve | staff `webstore:manage` | Same idempotency key and payload for incomplete operation | `staff_approved` or `ready_for_activation` after recovery | unchanged | unchanged | no duplicate approval | existing operation resumes or replays | `202` while leased, `200` after completion |
| `ready_for_activation` | Staff Approve | staff `webstore:manage` | Staff approval already completed | `ready_for_activation` | unchanged | unchanged | unchanged | `webstore.branding_staff_approval_rejected_duplicate` | `409 STAFF_APPROVAL_EXISTS` |
| `ready_for_activation` | Activate Branding | staff `webstore:manage`, tenant admin, platform support with explicit tenant support context | Version exists; pointer expectation matches; activation lease acquired; draft revision matches | consumed draft, not editable | unchanged | unchanged | approvals remain historical facts | activation events and audit as defined in section 6 | `200` |
| `draft` | Activate Branding | staff `webstore:manage` | Not ready | `draft` | unchanged | unchanged | unchanged | `webstore.branding_activation_rejected` | `409 BRANDING_NOT_READY` |
| `review_requested` | Activate Branding | staff `webstore:manage` | Owner/staff approvals missing | `review_requested` | unchanged | unchanged | unchanged | `webstore.branding_activation_rejected` | `409 BRANDING_NOT_READY` |
| `owner_approved` | Activate Branding | staff `webstore:manage` | Staff approval missing | `owner_approved` | unchanged | unchanged | unchanged | `webstore.branding_activation_rejected` | `409 STAFF_APPROVAL_REQUIRED` |
| `staff_approved` | Activate Branding | staff `webstore:manage` | Staff approval operation incomplete | `staff_approved` | unchanged | unchanged | unchanged | `webstore.branding_activation_rejected` | `409 STAFF_APPROVAL_IN_PROGRESS` |
| `changes_requested_by_owner` | Activate Branding | staff `webstore:manage` | Review cycle invalidated | `changes_requested_by_owner` | unchanged | invalidated | unchanged | `webstore.branding_activation_rejected` | `409 APPROVAL_INVALIDATED` |
| `changes_requested_by_staff` | Activate Branding | staff `webstore:manage` | Review cycle invalidated | `changes_requested_by_staff` | unchanged | invalidated | unchanged | `webstore.branding_activation_rejected` | `409 APPROVAL_INVALIDATED` |

## 5. Review, Approval, and Invalidation Model

Review snapshot creation:

- Triggered only by `Request Owner Review`.
- Captures exact draft content, selected derivative ids, section order, field
  schema version, validation snapshot, draft revision, and content hashes.
- Writes one document to `webstore_branding_review_snapshots`.

Review snapshot document fields:

- `id`
- `created_by_operation_id`
- `tenant_id`
- `webstore_id`
- `draft_id`
- `draft_revision`
- `review_cycle`
- `snapshot_hash`
- `content_hash`
- `asset_reference_hash`
- `field_schema_version`
- `validation_schema_version`
- `validation_result_id`
- `snapshot_content`
- `selected_derivative_ids`
- `created_by_actor_type`
- `created_by_user_id`
- `created_by_portal_identity_id`
- `created_by_assignment_id`
- `created_by_email`
- `committed_to_draft_at`
- `superseded_at`
- `superseded_reason_code`
- `created_at`
- `updated_at`

Owner approval fields:

- `approval_id`
- `approval_type = "owner"`
- `tenant_id`
- `webstore_id`
- `draft_id`
- `review_snapshot_id`
- `review_cycle`
- `snapshot_hash`
- `approver_user_id`
- `approved_at`
- `invalidated_at`
- `invalidation_id`
- `comment`
- `created_at`
- `updated_at`

Staff approval fields:

- `staff_approval_id`
- `created_by_operation_id`
- `approval_id`
- `approval_type = "staff"`
- `tenant_id`
- `webstore_id`
- `draft_id`
- `review_snapshot_id`
- `review_cycle`
- `snapshot_hash`
- `approver_user_id`
- `approved_at`
- `invalidated_at`
- `invalidation_id`
- `comment`
- `created_at`
- `updated_at`

Approval invalidation event fields:

- `id`
- `tenant_id`
- `webstore_id`
- `draft_id`
- `previous_draft_revision`
- `new_draft_revision`
- `previous_review_cycle`
- `previous_review_snapshot_id`
- `previous_snapshot_hash`
- `reason_code`
- `actor_type`
- `actor_user_id`
- `actor_portal_identity_id`
- `actor_assignment_id`
- `actor_email`
- `created_at`
- `updated_at`

Approval indexes:

```python
await db.webstore_branding_approvals.create_index("approval_id", unique=True)
await db.webstore_branding_approvals.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("review_snapshot_id", 1), ("review_cycle", 1), ("approval_type", 1)],
    unique=True,
)
await db.webstore_branding_approvals.create_index(
    "staff_approval_id",
    unique=True,
    partialFilterExpression={"approval_type": "staff", "staff_approval_id": {"$exists": True}},
)
await db.webstore_branding_approvals.create_index(
    "created_by_operation_id",
    unique=True,
    partialFilterExpression={"approval_type": "staff", "created_by_operation_id": {"$exists": True}},
)
await db.webstore_branding_approvals.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("draft_id", 1), ("review_cycle", 1), ("approval_type", 1)]
)
await db.webstore_branding_approvals.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("invalidated_at", 1)]
)
await db.webstore_branding_approval_invalidations.create_index("id", unique=True)
await db.webstore_branding_approval_invalidations.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("draft_id", 1), ("review_snapshot_id", 1), ("review_cycle", 1)],
    unique=True,
)
```

Current approval validity computation:

1. Read current editable draft by `tenant_id`, `webstore_id`, and
   `editable = True`.
2. Read `draft.review_cycle`, `draft.review_snapshot_id`,
   `draft.snapshot_hash`, and `draft.draft_revision`.
3. Read owner approval with the same `tenant_id`, `webstore_id`,
   `review_snapshot_id`, `snapshot_hash`, `draft_revision`, and
   `approval_type = "owner"`.
4. Read staff approval with the same keys and `approval_type = "staff"`.
5. Read invalidation where `previous_review_snapshot_id` equals the draft
   current `review_snapshot_id`.
6. If invalidation exists, both approvals are historical and not current.
7. If owner approval is missing, owner approval is not current.
8. If staff approval is missing, staff approval is not current.
9. No approval document is updated or deleted during this computation.

Approval invalidation timing:

- Request Changes creates the one append-only invalidation for the affected
  approval and review cycle.
- A later material Save Draft increments the revision, opens a new review cycle,
  returns the draft to `draft`, clears mutable current-review references, and
  does not create another invalidation.
- A nonmaterial save does not change revision, review cycle, state, approvals,
  snapshots, validation records, or invalidation records.
- Approval rows remain immutable historical records.

## 6. Activation Operation and Boundary Recovery

Activation uses the canonical workflow-operation base model in section 7 with
`operation_type = "activate_branding"` and the activation extension fields in
`WebstoreBrandingActivationOperationExtension`.

Operation fields, status enum, terminal response fields, lease fields, and
indexes are not redefined in this section. The only valid base names are:
`operation_id`, `canonical_request_hash`, `operation_status`,
`operation_step`, `terminal_http_status`, and `terminal_response_body`.

Activation request fields:

- `target_version_id`
- `target_draft_id`
- `target_draft_revision`
- `expected_active_version_id`
- `idempotency_key`

If `expected_active_version_id` is omitted:

- Backend reads the target draft.
- Backend uses `draft.base_active_version_id`.
- Backend stores that value on the operation before attempting the pointer CAS.
- After the operation is claimed, pointer CAS uses only the stored caller
  expectation or the stored draft `base_active_version_id`; it does not reread
  the current active pointer to replace the expectation.

Canonical request hash:

- SHA-256 of canonical JSON containing:
  - `tenant_id`
  - `webstore_id`
  - `target_version_id`
  - `target_draft_id`
  - `target_draft_revision`
  - `expected_active_version_id`
  - `idempotency_key`

Same-key different payload:

- If an existing operation has the same idempotency key and different
  `canonical_request_hash`, return HTTP `409`.
- Error code: `IDEMPOTENCY_KEY_REUSED`.
- No pointer update occurs.
- No draft consumption occurs.
- Audit event: `webstore.branding_activation_rejected_idempotency_mismatch`.

Pointer update fields on `webstores`:

- `active_branding_version_id`
- `active_branding_snapshot_hash`
- `branding_activation_operation_id`
- `branding_activated_at`
- `branding_activated_by_user_id`
- `updated_at`

Pointer CAS filter when an active version is expected:

```python
{
  "tenant_id": tenant_id,
  "id": webstore_id,
  "active_branding_version_id": expected_active_version_id
}
```

Pointer CAS filter when no active version is expected:

```python
{
  "tenant_id": tenant_id,
  "id": webstore_id,
  "$or": [
    {"active_branding_version_id": {"$exists": False}},
    {"active_branding_version_id": None},
    {"active_branding_version_id": ""}
  ]
}
```

Pointer CAS update:

```python
{
  "$set": {
    "active_branding_version_id": target_version_id,
    "active_branding_snapshot_hash": target_snapshot_hash,
    "branding_activation_operation_id": operation_id,
    "branding_activated_at": now_iso,
    "branding_activated_by_user_id": actor_user_id,
    "updated_at": now_iso
  }
}
```

Activation ownership:

- An operation owns the active pointer only when
  `webstores.branding_activation_operation_id == operation_id`.
- If the target version is active but the pointer names another
  `branding_activation_operation_id`, this operation returns
  `409 ACTIVE_VERSION_CHANGED` and becomes `conflicted`.
- If the pointer names this operation, retries may complete missing success
  event, draft consumption, audit, and terminal-response writes without
  repeating pointer CAS.

Draft consumption CAS filter:

```python
{
  "tenant_id": tenant_id,
  "webstore_id": webstore_id,
  "id": target_draft_id,
  "draft_revision": target_draft_revision,
  "state": "ready_for_activation",
  "editable": True,
  "consumed_at": None,
  "activated_version_id": {"$in": [None, ""]},
  "activation_lock_operation_id": operation_id
}
```

Draft consumption update:

```python
{
  "$set": {
    "editable": False,
    "consumed_at": now_iso,
    "consumed_by_activation_at": now_iso,
    "consumed_by_activation_operation_id": operation_id,
    "activated_at": now_iso,
    "activated_version_id": target_version_id,
    "updated_at": now_iso
  },
  "$unset": {
    "activation_lock_operation_id": "",
    "activation_lock_owner_token": "",
    "activation_lock_acquired_at": "",
    "activation_lock_expires_at": ""
  }
}
```

Activation lock:

- Before pointer CAS, set on the draft:
  - `activation_lock_operation_id = operation_id`
  - `activation_lock_owner_token = lease_owner_token`
  - `activation_lock_acquired_at = now_iso`
  - `activation_lock_expires_at = now_iso + finite lease ttl`
- Filter:
```python
{
  "tenant_id": tenant_id,
  "webstore_id": webstore_id,
  "id": target_draft_id,
  "draft_revision": target_draft_revision,
  "state": "ready_for_activation",
  "editable": True,
  "consumed_at": None,
  "$or": [
    {"activation_lock_operation_id": {"$exists": False}},
    {"activation_lock_operation_id": None},
    {"activation_lock_operation_id": operation_id}
  ]
}
```

Lease algorithm:

- Lease acquisition is an atomic operation update.
- Lease owner token is a unique random value generated for one worker attempt.
- Lease has finite expiration.
- Lease renewal succeeds only when operation id and lease owner token both
  match.
- Same idempotency key and same payload while another live lease owns the
  operation returns HTTP `202` with `operation_id`, `operation_step`, and
  `Retry-After`.
- Same idempotency key and same payload after terminal completion returns the
  stored terminal response exactly.
- Same idempotency key and different canonical request hash returns HTTP `409`
  with error code `IDEMPOTENCY_KEY_REUSED`.

Edit blocking while activation is in progress:

- Any edit request where `activation_lock_operation_id` exists returns
  HTTP `409`.
- Error code: `BRANDING_ACTIVATION_IN_PROGRESS`.
- No write occurs.
- Audit event: `webstore.branding_draft_edit_rejected_activation_in_progress`.

Successful activation sequence:

1. Create or read operation by unique idempotency key.
2. Reject same-key different payload.
3. Validate draft, version, approvals, validation snapshot, derivatives, and
   pointer expectation.
4. Set draft activation lock.
5. Insert `activation_attempted` event.
6. CAS update `webstores` active pointer and operation ownership fields.
7. Update operation to `pointer_updated`.
8. Insert `activation_succeeded` event.
9. Consume draft with CAS.
10. Update operation to `draft_consumed`.
11. Write Webstore activity and audit event.
12. Update operation to `completed` with `terminal_http_status` and
    `terminal_response_body`.
13. Return terminal response.

Recovery after individual write failures:

- Operation record created, draft lock fails:
  - Operation becomes `failed`.
  - `failure_code = "draft_not_ready_or_locked"`.
  - No pointer change.
  - No draft consumption.
  - Retry with same key returns failed terminal response.

- Draft lock succeeds, attempt event fails:
  - Operation remains `pending`.
  - Draft lock remains owned by operation id.
  - Retry with same key writes missing attempt event and continues.
  - Different operation receives HTTP `409` with
    `BRANDING_ACTIVATION_IN_PROGRESS`.

- Attempt event succeeds, pointer CAS fails:
  - Operation becomes `conflicted`.
  - `failure_code = "ACTIVE_VERSION_CHANGED"`.
  - HTTP result is exactly `409 ACTIVE_VERSION_CHANGED`.
  - Draft activation lock is cleared after verifying the stored lock owner equals
    this operation id and the pointer does not contain this operation id.
  - Draft remains editable.
  - No active pointer change by this operation.
  - Retry with same key returns conflicted terminal response.
  - A different operation targeting the same or a different version and losing
    pointer CAS is `conflicted`, not `failed`.
  - A successful operation never becomes `conflicted` because another request
    observed or replayed the already-updated active pointer.

- Pointer CAS succeeds, operation status update fails:
  - Webstore pointer contains `branding_activation_operation_id = operation_id`.
  - Retry proves operation ownership by reading the Webstore pointer fields.
  - Retry updates operation to `pointer_updated`.
  - Retry continues success event, draft consumption, audit, and terminal update.

- Pointer CAS succeeds, activation-success event fails:
  - Webstore pointer contains operation id.
  - Operation status is `processing`.
  - Operation step is `pointer_updated` or `activation_attempt_recorded`.
  - Retry inserts missing `activation_succeeded` event with same operation id.
  - Retry consumes draft.

- Success event succeeds, draft-consumption fails:
  - Webstore pointer contains operation id.
  - Success event contains operation id.
  - Draft still has activation lock owned by operation id.
  - Retry performs draft consumption CAS.
  - If draft is already consumed by the same operation id, retry continues.
  - If draft is consumed by another operation id, operation becomes
    `conflicted` with `failure_code = "CONSUMPTION_OWNERSHIP_MISMATCH"`;
    the pointer remains authoritative and human support review is required.

- Draft consumption succeeds, audit write fails:
  - Webstore pointer contains operation id.
  - Draft has `editable = false` and
    `consumed_by_activation_operation_id = operation_id`.
  - Retry writes missing audit event.
  - Retry then writes terminal response.

- Audit succeeds, terminal operation update fails:
  - Webstore pointer contains operation id.
  - Draft is consumed by operation id.
  - Success event exists for operation id.
  - Audit event exists for operation id.
  - Retry updates operation to `completed` and returns terminal response.

- Response is lost after full success:
  - Retry with same key and same canonical request hash returns
    `terminal_response_body` with `terminal_http_status`.

Activation boundary-recovery table:

| Boundary failure | Persisted records | Records absent | Operation status and step | Retry behavior | Exact HTTP result | Audit result | Records unchanged |
|---|---|---|---|---|---|---|---|
| Operation creation fails | none | operation, lock, events, pointer, consumption, audit | no operation | client may retry with same key as a new request | original request returns `500 OPERATION_CREATE_FAILED` | none | Webstore, draft, version, approvals |
| Lease acquisition fails because another live lease owns same key | operation | lock, events, pointer, consumption, audit | `processing`, existing step | caller waits and retries | `202` with `operation_id`, `operation_step`, `Retry-After` | none | Webstore, draft, version, approvals |
| Draft lock CAS fails | operation | lock, events, pointer, consumption, audit | `conflicted`, `lease_acquired` | same-key replay returns stored conflict | `409 BRANDING_DRAFT_LOCK_CONFLICT` | rejection audit only | active pointer, draft revision, version |
| Activation attempted event insert fails after lock | operation, draft lock | attempt event, pointer, success event, consumption, audit | `processing`, `draft_lock_acquired` | retry inserts attempt event and continues | `202` until completed by owner lease | none until event succeeds | active pointer, version, approvals |
| Pointer CAS fails | operation, draft lock, attempt event | pointer ownership, success event, consumption, audit | `conflicted`, `activation_attempt_recorded` | same-key replay returns stored conflict and clears owned lock | `409 ACTIVE_VERSION_CHANGED` | `activation_conflicted` and rejection audit | active pointer not changed by losing op, version |
| Success event fails after pointer update | operation, draft lock, attempt event, pointer | success event, consumption, audit | `processing`, `pointer_updated` | retry proves pointer ownership and inserts success event | `202` until recovered | none until success event written | active pointer target, version |
| Draft consumption fails after success event | operation, draft lock, attempt event, pointer, success event | consumption, audit | `processing`, `activation_success_recorded` | retry consumes the draft with owned lock | `202` until recovered | none until consumption succeeds | active pointer target, version |
| Audit fails after draft consumption | operation, pointer, success event, consumed draft | audit terminal | `processing`, `draft_consumed` | retry writes missing audit | `202` until recovered | audit written once | active pointer, version, draft content |
| Terminal update fails after audit | operation, pointer, success event, consumed draft, audit | terminal response | `processing`, `audit_event_persisted` | retry stores terminal response and marks completed | `200` after recovery | no duplicate audit | active pointer, version, draft |
| Lost response after completion | operation, pointer, success event, consumed draft, audit, terminal response | none | `completed`, `terminal_response_stored` | replay stored terminal response exactly | stored `200` | no duplicate audit | all records |

Why unsuccessful activation cannot expose incomplete version:

- Public storefront reads only `webstores.active_branding_version_id`.
- Pointer CAS is the only step that exposes a version.
- Pointer CAS writes `branding_activation_operation_id` with the version.
- If later recovery steps fail, public reads still serve the immutable version
  whose derivatives and validation were checked before pointer CAS.
- Draft consumption and audit can be retried because operation ownership is on
  the Webstore pointer.
- If pointer CAS does not succeed, public storefront continues serving the
  prior active version.

New draft after activation:

- A new draft is possible only after the consumed draft has
  `editable = false`.
- The unique editable-draft index then allows a new editable draft to be
  inserted.
- New draft uses current `webstores.active_branding_version_id` as
  `base_active_version_id`.

## 7. Complete Data Models and Indexes

### `Webstore` additive fields

- `active_branding_version_id: Optional[str]`
- `active_branding_snapshot_hash: Optional[str]`
- `branding_activation_operation_id: Optional[str]`
- `branding_activated_at: Optional[str]`
- `branding_activated_by_user_id: Optional[str]`

### `WebstoreBrandingDraft`

- `id`
- `tenant_id`
- `webstore_id`
- `state`
- `editable`
- `draft_revision`
- `base_active_version_id`
- `derived_from_version_id`
- `restored_from_version_id`
- `review_cycle`
- `review_snapshot_id`
- `review_operation_id`
- `snapshot_hash`
- `field_schema_version`
- `content`
- `selected_derivative_ids`
- `validation_result_id`
- `activation_lock_operation_id`
- `activation_lock_owner_token`
- `activation_lock_acquired_at`
- `activation_lock_expires_at`
- `consumed_at`
- `consumed_by_activation_at`
- `consumed_by_activation_operation_id`
- `activated_at`
- `activated_version_id`
- `created_by_actor_type`
- `created_by_user_id`
- `created_by_portal_identity_id`
- `created_by_assignment_id`
- `created_by_email`
- `created_at`
- `updated_at`

### `WebstoreBrandingReviewSnapshot`

- `id`
- `created_by_operation_id`
- `tenant_id`
- `webstore_id`
- `draft_id`
- `draft_revision`
- `review_cycle`
- `snapshot_hash`
- `content_hash`
- `asset_reference_hash`
- `field_schema_version`
- `validation_schema_version`
- `validation_result_id`
- `snapshot_content`
- `selected_derivative_ids`
- `created_by_actor_type`
- `created_by_user_id`
- `created_by_portal_identity_id`
- `created_by_assignment_id`
- `created_by_email`
- `committed_to_draft_at`
- `superseded_at`
- `superseded_reason_code`
- `created_at`
- `updated_at`

### `WebstoreBrandingVersion`

- `id`
- `tenant_id`
- `webstore_id`
- `version_number`
- `snapshot_hash`
- `content_hash`
- `asset_reference_hash`
- `field_schema_version`
- `snapshot_content`
- `selected_derivative_ids`
- `source_draft_id`
- `source_draft_revision`
- `source_review_cycle`
- `source_review_snapshot_id`
- `review_snapshot_id`
- `validation_result_id`
- `validation_schema_version`
- `validator_implementation_version`
- `validated_draft_revision`
- `derived_from_version_id`
- `restored_from_version_id`
- `created_by_user_id`
- `created_by_email`
- `created_at`
- `updated_at`

Identical `snapshot_hash` values are permitted across version numbers.

### `WebstoreBrandingApproval`

Fields are defined in section 5.

### `WebstoreBrandingApprovalInvalidation`

Fields are defined in section 5.

### `WebstoreBrandingOperation`

Used for recoverable, idempotent `request_owner_review`, `staff_approve`, and
`activate_branding` operations.

- `operation_id`
- `tenant_id`
- `webstore_id`
- `draft_id`
- `operation_type`
- `idempotency_key`
- `canonical_request_hash`
- `expected_draft_revision`
- `expected_review_cycle`
- `lease_owner_token`
- `lease_expires_at`
- `attempt_count`
- `operation_status`
- `operation_step`
- `failure_code`
- `terminal_http_status`
- `terminal_response_body`
- `created_at`
- `updated_at`
- `completed_at`
- `failed_at`
- `conflicted_at`

Operation type enum:

- `request_owner_review`
- `staff_approve`
- `activate_branding`

`operation_status` enum:

- `pending`
- `processing`
- `completed`
- `failed`
- `conflicted`

`operation_step` is operation-specific and records the last successfully
completed persistence boundary. Step enums are defined once in the operation
extension sections below and must be reused unchanged by models, recovery
tables, APIs, audits, and tests.

Idempotency behavior:

- Same tenant, Webstore, operation type, and idempotency key with the same
  canonical request hash reuses the existing operation.
- If the existing operation is leased by another worker and not terminal,
  response is HTTP `202` with `operation_id`, `operation_step`, and
  `Retry-After`.
- If the existing operation is terminal, response replays
  `terminal_http_status` and `terminal_response_body` exactly.
- Same tenant, Webstore, operation type, and idempotency key with a different
  canonical request hash returns HTTP `409 IDEMPOTENCY_KEY_REUSED`.
- Expired leases can be claimed atomically by another worker, which resumes from
  the persisted `operation_step`.

Required base indexes:

```python
await db.webstore_branding_operations.create_index("operation_id", unique=True)
await db.webstore_branding_operations.create_index(
    [("tenant_id", 1), ("operation_type", 1), ("idempotency_key", 1)],
    unique=True,
)
await db.webstore_branding_operations.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("draft_id", 1), ("operation_type", 1), ("operation_status", 1)]
)
await db.webstore_branding_operations.create_index(
    [("operation_status", 1), ("lease_expires_at", 1)]
)
```

### `WebstoreBrandingRequestOwnerReviewOperationExtension`

Base operation rows with `operation_type = "request_owner_review"` have these
extension fields:

- `operation_id`
- `intended_validation_result_id`
- `intended_review_snapshot_id`
- `canonical_snapshot_hash`
- `actor_user_id`
- `actor_email`

`request_owner_review` `operation_step` enum:

- `operation_created`
- `lease_acquired`
- `context_verified`
- `canonical_content_serialized`
- `snapshot_hash_calculated`
- `content_validated`
- `validation_result_persisted`
- `review_snapshot_persisted`
- `draft_review_requested`
- `audit_event_persisted`
- `terminal_response_stored`

Authoritative sequence:

1. Create or retrieve the idempotent operation.
2. Acquire the operation lease.
3. Verify tenant, Webstore, actor, expected revision, and review cycle.
4. Serialize the exact canonical draft content.
5. Calculate the snapshot hash.
6. Validate that exact content.
7. Persist the validation result.
8. Persist the immutable review snapshot.
9. CAS the draft to `review_requested`.
10. Persist the audit/event record.
11. Store the terminal response.
12. Mark the operation `completed`.

The operation preallocates and persists `intended_validation_result_id`,
`intended_review_snapshot_id`, and `canonical_snapshot_hash`. Every retry
reuses those identifiers.

Validation results and review snapshots created by this operation include:

- `created_by_operation_id`
- `draft_id`
- `draft_revision`
- `review_cycle`
- `snapshot_hash`
- `committed_to_draft_at`
- `superseded_at`
- `superseded_reason_code`

They begin uncommitted. They become authoritative only after the draft CAS
succeeds and the draft references their exact ids.

If the draft CAS fails because revision, review cycle, or state changed:

- Operation becomes `conflicted`.
- Response is exactly `409 DRAFT_REVISION_CHANGED` unless a more specific
  state-conflict code is listed for that state.
- The uncommitted validation result and review snapshot are marked superseded.
- They are not deleted.
- Draft is not modified.
- No approval is created.
- No audit claims review began.

If draft CAS succeeds but audit/event or terminal operation update fails:

- Operation remains recoverable.
- Retry recognizes ownership from `draft.review_operation_id`.
- Retry writes the missing audit/event and terminal response.
- Retry does not create another snapshot, validation record, or review cycle.

Request Owner Review boundary-recovery table:

| Boundary failure | Persisted records | Records absent | Operation status and step | Retry behavior | Exact HTTP result | Audit result | Records unchanged |
|---|---|---|---|---|---|---|---|
| Operation creation fails | none | operation, validation, snapshot, draft review refs, audit | no operation | client may retry as a new same-key request | `500 OPERATION_CREATE_FAILED` | none | draft, approvals, versions |
| Lease acquisition fails because another worker owns same key | operation | validation, snapshot, draft review refs, audit | `processing`, existing step | caller waits and retries same key | `202` with `operation_id`, `operation_step`, `Retry-After` | none | draft, approvals, versions |
| Failure after lease acquisition | operation | validation, snapshot, draft review refs, audit | `processing`, `lease_acquired` | retry verifies context and continues | `202` until recovered | none | draft, approvals, versions |
| Context verification fails | operation | validation, snapshot, draft review refs, audit | `failed`, `lease_acquired` | same-key replay returns terminal failure | exact validation error such as `403` or `409 DRAFT_REVISION_CHANGED` | rejection audit only when actor and Webstore are known | draft content, approvals, versions |
| Failure after context verification | operation | validation, snapshot, draft review refs, audit | `processing`, `context_verified` | retry serializes canonical content and continues | `202` until recovered | none | draft content, approvals, versions |
| Canonical content serialization fails | operation | validation, snapshot, draft review refs, audit | `failed`, `context_verified` | same-key replay returns terminal failure | `422 BRANDING_CONTENT_INVALID` | rejection audit | draft content, approvals, versions |
| Failure after canonical content serialization | operation | validation, snapshot, draft review refs, audit | `processing`, `canonical_content_serialized` | retry calculates snapshot hash and continues | `202` until recovered | none | draft content, approvals, versions |
| Failure after snapshot hash calculation | operation with `canonical_snapshot_hash` | validation, snapshot, draft review refs, audit | `processing`, `snapshot_hash_calculated` | retry validates content and continues | `202` until recovered | none | draft content, approvals, versions |
| Validation fails with blockers | operation | validation, snapshot, draft review refs, audit | `failed`, `snapshot_hash_calculated` | same-key replay returns terminal failure | `409 BRANDING_VALIDATION_BLOCKED` | rejection audit | draft state, approvals, versions |
| Validation-result insertion fails | operation | validation, snapshot, draft review refs, audit | `processing`, `content_validated` | retry inserts validation result with preallocated id | `202` until recovered | none | draft, approvals, versions |
| Review-snapshot insertion fails | operation, uncommitted validation result | snapshot, draft review refs, audit | `processing`, `validation_result_persisted` | retry inserts snapshot with preallocated id | `202` until recovered | none | draft, approvals, versions |
| Draft CAS fails | operation, uncommitted validation result, uncommitted snapshot | committed review refs, audit | `conflicted`, `review_snapshot_persisted` | retry marks uncommitted records superseded and replays conflict | `409 DRAFT_REVISION_CHANGED` | no review-began audit | draft, approvals, versions |
| Audit/event fails after draft CAS | operation, committed validation, committed snapshot, draft review refs | audit, terminal response | `processing`, `draft_review_requested` | retry recognizes draft review operation ownership and writes audit | `202` until recovered | audit written once | draft content, approvals, versions |
| Terminal update fails | operation, committed validation, committed snapshot, draft review refs, audit | terminal response | `processing`, `audit_event_persisted` | retry stores terminal response and marks completed | `200` after recovery | no duplicate audit | draft content, approvals, versions |
| Lost response after completion | operation, committed validation, committed snapshot, draft review refs, audit, terminal response | none | `completed`, `terminal_response_stored` | replay stored terminal response exactly | stored `200` | no duplicate audit | all records |

### `WebstoreBrandingStaffApprovalOperationExtension`

Base operation rows with `operation_type = "staff_approve"` have these
extension fields:

- `operation_id`
- `review_snapshot_id`
- `snapshot_hash`
- `intended_staff_approval_id`
- `intended_branding_version_id`
- `allocated_version_number`
- `approver_user_id`
- `approver_email`

`staff_approve` `operation_step` enum:

- `operation_claimed`
- `lease_acquired`
- `context_validated`
- `staff_approval_inserted`
- `draft_staff_approved`
- `version_number_allocated`
- `branding_version_inserted`
- `draft_ready_for_activation`
- `audit_events_persisted`
- `terminal_response_stored`

Authoritative sequence:

1. Create or retrieve the idempotent operation.
2. Acquire the operation lease.
3. Validate actor, tenant, Webstore, draft, revision, review cycle, review
   snapshot, Owner approval, validation result, snapshot hash, and validator
   versions.
4. Insert the operation-owned staff approval using the unique approval indexes.
5. If that insert loses to another operation, mark the losing operation
   `conflicted` and return exactly `409 STAFF_APPROVAL_ALREADY_RECORDED`.
6. CAS the draft to persisted `staff_approved`, referencing the winning
   operation and staff approval.
7. Allocate the branding-version number exactly once for the winning operation.
8. Insert the immutable branding version using the preallocated branding-version
   id.
9. CAS the draft to `ready_for_activation`.
10. Persist required audit and domain events.
11. Store the terminal HTTP status and response.
12. Mark operation `completed`.

The winning operation preallocates `intended_staff_approval_id` and
`intended_branding_version_id`. It does not allocate `allocated_version_number`
until after it owns the staff approval and the draft has entered
`staff_approved`.

Repository-compatible version allocation:

- Allocation uses an atomic `find_one_and_update` on
  `webstore_branding_version_sequences` scoped by tenant id and Webstore id.
- The same update writes the returned number to
  `WebstoreBrandingStaffApprovalOperationExtension.allocated_version_number`
  only when that field is absent and the operation already owns the staff
  approval.
- If the process crashes after sequence increment but before operation update,
  the retry detects the missing operation allocation, performs one new atomic
  allocation, and leaves the prior number as an allowed gap.
- If `allocated_version_number` is present, retry reuses that number and does
  not increment the sequence.

Two different idempotency keys attempting to approve the same review snapshot:

- Only one operation may insert the staff approval.
- The losing operation must not reuse the winning approval.
- The losing operation must not persist `allocated_version_number`.
- The losing operation must not insert a branding version.
- The losing operation becomes `conflicted`.
- The losing operation returns exactly `409 STAFF_APPROVAL_ALREADY_RECORDED`.
- The winning operation remains unchanged.

If staff approval insert succeeds and a later step fails:

- Draft is locked against edits, new review requests, Owner decisions, other
  staff approvals, and activation until recovery completes.
- Retry resumes the same operation.
- Historical Owner approval and staff approval remain immutable.
- Retry never allocates another version number.

Staff Approval boundary-recovery table:

| Boundary failure | Persisted records | Records absent | Operation status and step | Retry behavior | Exact HTTP result | Audit result | Records unchanged |
|---|---|---|---|---|---|---|---|
| Operation claim fails | none | operation, staff approval, version, draft state change, audit | no operation | client may retry as a new same-key request | `500 OPERATION_CREATE_FAILED` | none | draft, owner approval, versions |
| Lease acquisition fails because another worker owns same key | operation | staff approval, version, draft state change, audit | `processing`, existing step | caller waits and retries same key | `202` with `operation_id`, `operation_step`, `Retry-After` | none | draft, owner approval, versions |
| Context validation fails | operation | staff approval, version number, version, audit | `failed` | `lease_acquired` | unchanged | lease terminal | same-key replay returns terminal failure | exact validation failure such as `409 OWNER_APPROVAL_REQUIRED` | rejection audit | draft, owner approval, versions |
| Staff approval insert loses unique claim | operation | loser staff approval, version number, version, draft change | `conflicted` | `context_validated` | unchanged | lease terminal | same-key replay returns stored conflict | `409 STAFF_APPROVAL_ALREADY_RECORDED` | one idempotent conflict audit/event | winning operation, winning approval, draft |
| Staff approval inserted, draft CAS to `staff_approved` fails | operation, operation-owned staff approval | version number, version, ready state, audit | `processing` | `staff_approval_inserted` | unchanged or existing state if already moved by same operation | lease may expire | retry CASes draft to `staff_approved` | `503 STAFF_APPROVAL_RECOVERY_REQUIRED` with operation id and `Retry-After` | none until recovered | owner approval, staff approval content, versions |
| Draft entered `staff_approved`, version allocation persistence fails | operation, staff approval, draft `staff_approved` | allocated version number, version, ready state, audit | `processing` | `draft_staff_approved` | `staff_approved` | lease may expire | retry allocates once and records number on operation | `503 STAFF_APPROVAL_RECOVERY_REQUIRED` with operation id and `Retry-After` | none until recovered | owner approval, staff approval, draft content |
| Version number recorded, version insert fails | operation with `allocated_version_number`, staff approval, draft `staff_approved` | version, ready state, audit | `processing` | `version_number_allocated` | `staff_approved` | lease may expire | retry inserts version with preallocated id and recorded number | `503 STAFF_APPROVAL_RECOVERY_REQUIRED` with operation id and `Retry-After` | none until recovered | owner approval, staff approval |
| Branding version unique conflict | operation, staff approval, draft `staff_approved` | ready state, audit | `conflicted` | `version_number_allocated` | `staff_approved` | lease terminal | same-key replay returns stored conflict | `409 STAFF_APPROVAL_ALREADY_RECORDED` | conflict audit | winning version, owner approval, staff approval |
| Version inserted, ready CAS fails | operation, staff approval, version | ready state, audit | `processing` | `branding_version_inserted` | `staff_approved` | lease may expire | retry CASes draft to `ready_for_activation` | `503 STAFF_APPROVAL_RECOVERY_REQUIRED` with operation id and `Retry-After` | none until recovered | owner approval, staff approval, version content |
| Audit/event fails after ready state | operation, staff approval, version, draft ready | audit, terminal response | `processing` | `draft_ready_for_activation` | `ready_for_activation` | lease may expire | retry writes audit/events | `503 STAFF_APPROVAL_RECOVERY_REQUIRED` with operation id and `Retry-After` | audit written once | owner approval, staff approval, version |
| Terminal response fails after audit | operation, staff approval, version, draft ready, audit | terminal response, completed status | `processing` | `audit_events_persisted` | `ready_for_activation` | lease may expire | retry stores terminal response | `503 STAFF_APPROVAL_RECOVERY_REQUIRED` with operation id and `Retry-After` | no duplicate audit | all persisted branding records |
| Completion status fails after terminal response | operation, staff approval, version, draft ready, audit, terminal response | completed status | `processing` | `terminal_response_stored` | `ready_for_activation` | lease may expire | retry marks operation `completed` | `503 STAFF_APPROVAL_RECOVERY_REQUIRED` with operation id and `Retry-After` until completed | no duplicate audit | all records |
| Lost response after completion | operation, staff approval, version, draft ready, audit, terminal response, completed status | none | `completed` | `terminal_response_stored` | `ready_for_activation` | no active lease | replay stored terminal response exactly | stored `200` | no duplicate audit | all records |

### `WebstoreBrandingActivationOperationExtension`

Base operation rows with `operation_type = "activate_branding"` have these
extension fields:

- `operation_id`
- `target_version_id`
- `target_version_number`
- `target_snapshot_hash`
- `target_draft_id`
- `target_draft_revision`
- `expected_active_version_id`
- `attempt_event_id`
- `success_event_id`
- `audit_event_id`
- `pointer_updated_at`
- `draft_consumed_at`

`activate_branding` `operation_step` enum:

- `operation_created`
- `lease_acquired`
- `draft_lock_acquired`
- `activation_attempt_recorded`
- `pointer_updated`
- `activation_success_recorded`
- `draft_consumed`
- `audit_event_persisted`
- `terminal_response_stored`

### `WebstoreBrandingVersionSequence`

Authoritative per-Webstore branding-version sequence.

- `id`
- `tenant_id`
- `webstore_id`
- `next_version_number`
- `created_at`
- `updated_at`

Rules:

- One sequence row exists per tenant/Webstore.
- Version number allocation is atomic.
- Version numbers are never reused.
- Gaps are allowed after failed operations.
- Retry of the same `staff_approve` operation reuses
  `WebstoreBrandingStaffApprovalOperationExtension.allocated_version_number`;
  it does not allocate a new number.

### `WebstoreBrandingActivationEvent`

Append-only activation event collection.

- `id`
- `tenant_id`
- `webstore_id`
- `operation_id`
- `target_version_id`
- `target_draft_id`
- `event_type`
- `expected_active_version_id`
- `actual_active_version_id`
- `failure_code`
- `created_by_user_id`
- `created_by_email`
- `created_at`

Event type enum:

- `activation_attempted`
- `activation_succeeded`
- `activation_conflicted`
- `activation_failed`

Rules:

- Events are append-only and never overwritten.
- Retry inserts the same logical event idempotently by tenant id, Webstore id,
  operation id, and event type.
- Conflict and failure events are distinct; a lost pointer CAS writes
  `activation_conflicted`, not `activation_failed`.
- Audit is mandatory and recoverable; if audit write fails after durable
  activation state changes, retry completes the missing audit before returning
  terminal success.

### `WebstoreBrandingAsset`

- `id`
- `tenant_id`
- `webstore_id`
- `source_type`
- `source_setup_file_id`
- `source_upload_filename`
- `source_extension`
- `source_content_type`
- `source_detected_content_type`
- `source_size_bytes`
- `source_storage_key`
- `source_sha256`
- `uploaded_by_actor_type`
- `uploaded_by_user_id`
- `uploaded_by_portal_identity_id`
- `uploaded_by_assignment_id`
- `uploaded_by_email`
- `status`
- `retired_at`
- `retired_by_actor_type`
- `retired_by_user_id`
- `retired_reason`
- `created_at`
- `updated_at`

Status enum:

- `available`
- `retired`
- `processing_blocked`

### `WebstoreBrandingDerivativeOperation`

- `operation_id`
- `tenant_id`
- `webstore_id`
- `source_asset_id`
- `source_asset_content_hash`
- `source_detected_format`
- `source_width`
- `source_height`
- `orientation_normalization`
- `slot`
- `canonical_request_hash`
- `idempotency_key`
- `operation_status`
- `operation_step`
- `lease_owner_token`
- `lease_expires_at`
- `target_width`
- `target_height`
- `output_format`
- `output_quality`
- `jpeg_background_color`
- `focal_point_x`
- `focal_point_y`
- `crop_mode`
- `calculated_crop_left`
- `calculated_crop_top`
- `calculated_crop_width`
- `calculated_crop_height`
- `transform_spec_hash`
- `sanitizer_schema_version`
- `temporary_storage_key`
- `final_storage_key`
- `derivative_content_hash`
- `public_asset_key`
- `content_type`
- `content_length`
- `etag`
- `terminal_http_status`
- `terminal_response_body`
- `failure_code`
- `failure_detail`
- `attempt_count`
- `created_by_actor_type`
- `created_by_user_id`
- `created_by_portal_identity_id`
- `created_by_assignment_id`
- `created_by_email`
- `created_at`
- `updated_at`
- `started_at`
- `finalized_at`
- `failed_at`

Derivative operations use the canonical `operation_status` enum from
`WebstoreBrandingOperation`: `pending`, `processing`, `completed`, `failed`,
and `conflicted`.

Derivative `operation_step` enum:

- `pending`
- `claimed`
- `writing_temp`
- `bytes_written`
- `metadata_finalizing`
- `completed`
- `failed`

### `WebstoreBrandingDerivative`

- `id`
- `tenant_id`
- `webstore_id`
- `source_asset_id`
- `derivative_operation_id`
- `slot`
- `derivative_hash`
- `canonical_request_hash`
- `transform_spec_hash`
- `public_asset_key`
- `storage_key`
- `output_format`
- `content_type`
- `content_length`
- `width`
- `height`
- `quality`
- `crop_x`
- `crop_y`
- `crop_width`
- `crop_height`
- `focal_x`
- `focal_y`
- `status`
- `retired_at`
- `retired_by_actor_type`
- `retired_by_user_id`
- `retired_reason`
- `created_at`
- `updated_at`

Status enum:

- `available`
- `retired`
- `failed`

### `WebstoreBrandingCleanupEvent`

- `id`
- `tenant_id`
- `webstore_id`
- `operation_id`
- `source_asset_id`
- `temporary_storage_key`
- `final_storage_key`
- `cleanup_reason`
- `cleanup_status`
- `failure_detail`
- `created_at`
- `updated_at`

Cleanup status enum:

- `pending`
- `completed`
- `failed`

### `WebstoreBrandingValidationResult`

- `id`
- `created_by_operation_id`
- `tenant_id`
- `webstore_id`
- `draft_id`
- `validated_draft_revision`
- `validated_review_snapshot_id`
- `validated_snapshot_hash`
- `review_cycle`
- `snapshot_hash`
- `validation_schema_version`
- `field_schema_version`
- `validator_implementation_version`
- `validated_at`
- `committed_to_draft_at`
- `superseded_at`
- `superseded_reason_code`
- `error_codes`
- `warning_codes`
- `field_errors`
- `field_warnings`
- `contrast_results`
- `accessibility_results`
- `created_at`
- `updated_at`

### Indexes

```python
await db.webstores.create_index([("tenant_id", 1), ("active_branding_version_id", 1)])

await db.webstore_branding_drafts.create_index("id", unique=True)
await db.webstore_branding_drafts.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("editable", 1)],
    unique=True,
    partialFilterExpression={"editable": True},
)
await db.webstore_branding_drafts.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("updated_at", -1)]
)

await db.webstore_branding_review_snapshots.create_index("id", unique=True)
await db.webstore_branding_review_snapshots.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("review_cycle", 1)]
)
await db.webstore_branding_review_snapshots.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("snapshot_hash", 1)]
)

await db.webstore_branding_versions.create_index("id", unique=True)
await db.webstore_branding_versions.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("version_number", 1)],
    unique=True,
)
await db.webstore_branding_versions.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("snapshot_hash", 1)]
)
await db.webstore_branding_versions.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("review_snapshot_id", 1)],
    unique=True,
)

await db.webstore_branding_approvals.create_index("approval_id", unique=True)
await db.webstore_branding_approvals.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("review_snapshot_id", 1), ("review_cycle", 1), ("approval_type", 1)],
    unique=True,
)
await db.webstore_branding_approvals.create_index(
    "staff_approval_id",
    unique=True,
    partialFilterExpression={"approval_type": "staff", "staff_approval_id": {"$exists": True}},
)
await db.webstore_branding_approvals.create_index(
    "created_by_operation_id",
    unique=True,
    partialFilterExpression={"approval_type": "staff", "created_by_operation_id": {"$exists": True}},
)
await db.webstore_branding_approvals.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("draft_id", 1), ("review_cycle", 1), ("approval_type", 1)]
)
await db.webstore_branding_approvals.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("invalidated_at", 1)]
)

await db.webstore_branding_approval_invalidations.create_index("id", unique=True)
await db.webstore_branding_approval_invalidations.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("draft_id", 1), ("review_snapshot_id", 1), ("review_cycle", 1)],
    unique=True,
)

await db.webstore_branding_assets.create_index("id", unique=True)
await db.webstore_branding_assets.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("status", 1), ("created_at", -1)]
)
await db.webstore_branding_assets.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("source_setup_file_id", 1)]
)

await db.webstore_branding_derivative_operations.create_index("operation_id", unique=True)
await db.webstore_branding_derivative_operations.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("source_asset_id", 1), ("slot", 1), ("canonical_request_hash", 1)],
    unique=True,
)
await db.webstore_branding_derivative_operations.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("idempotency_key", 1)],
    unique=True,
)

await db.webstore_branding_derivatives.create_index("id", unique=True)
await db.webstore_branding_derivatives.create_index("public_asset_key", unique=True)
await db.webstore_branding_derivatives.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("source_asset_id", 1), ("slot", 1), ("derivative_hash", 1)],
    unique=True,
)
await db.webstore_branding_derivatives.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("status", 1)]
)

await db.webstore_branding_cleanup_events.create_index("id", unique=True)
await db.webstore_branding_cleanup_events.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("operation_id", 1)]
)

await db.webstore_branding_validation_results.create_index("id", unique=True)
await db.webstore_branding_validation_results.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("draft_id", 1), ("validated_draft_revision", 1)]
)
await db.webstore_branding_validation_results.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("validated_review_snapshot_id", 1), ("validated_snapshot_hash", 1)]
)

await db.webstore_branding_operations.create_index("operation_id", unique=True)
await db.webstore_branding_operations.create_index(
    [("tenant_id", 1), ("operation_type", 1), ("idempotency_key", 1)],
    unique=True,
)
await db.webstore_branding_operations.create_index(
    [("tenant_id", 1), ("webstore_id", 1), ("draft_id", 1), ("operation_type", 1), ("operation_status", 1)]
)
await db.webstore_branding_operations.create_index(
    [("operation_status", 1), ("lease_expires_at", 1)]
)
```

## 8. Canonical Storefront Field Schema

Canonical content root: `content`.

No schema path uses `theme.identity`.

No section uses duplicate visibility fields. The authoritative visibility fields
are under `content.sections`.

Logo visibility and ordering:

- `logo` is a valid section identifier exactly once in
  `content.sections.order`.
- `content.sections.logo_visible` is the only authoritative visibility source
  for the logo section.
- No `content.logo.visible`, `content.logo.enabled`, serializer-level logo
  visibility flag, or UI-local logo visibility source is allowed.
- Defaults, validators, serializers, UI state, public responses, and tests must
  all derive logo visibility from `content.sections.logo_visible`.

Section identifiers:

- `header`
- `logo`
- `hero`
- `announcement`
- `description`
- `catalog_slot`
- `fulfillment`
- `policies`
- `contact`
- `footer`

Default section order:

```json
[
  "header",
  "logo",
  "hero",
  "announcement",
  "description",
  "catalog_slot",
  "fulfillment",
  "policies",
  "contact",
  "footer"
]
```

### Theme and identity

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.theme.primary_color` | string | yes | hex `#RRGGBB` | `#0f172a` | staff write, staff manage, assigned owner, assigned manager | active or draft | valid hex | `theme_primary_color` | contrast may block review | Stage 3 |
| `content.theme.secondary_color` | string | yes | hex `#RRGGBB` | `#ffffff` | staff write, staff manage, assigned owner, assigned manager | active or draft | valid hex | `theme_secondary_color` | contrast may block review | Stage 3 |
| `content.theme.accent_color` | string | yes | hex `#RRGGBB` | `#0ea5e9` | staff write, staff manage, assigned owner, assigned manager | active or draft | valid hex | `theme_accent_color` | contrast may block review | Stage 3 |
| `content.theme.background_color` | string | yes | hex `#RRGGBB` | `#f8fafc` | staff write, staff manage, assigned owner, assigned manager | active or draft | valid hex | `theme_background_color` | contrast may block review | Stage 3 |
| `content.theme.text_color` | string | yes | hex `#RRGGBB` | `#111827` | staff write, staff manage, assigned owner, assigned manager | active or draft | valid hex | `theme_text_color` | contrast may block review | Stage 3 |
| `content.theme.heading_font` | string | yes | `system`, `serif`, `rounded`, `condensed` | `system` | staff write, staff manage | active or draft | enum only | `theme_heading_font` | none | Stage 3 |
| `content.theme.body_font` | string | yes | `system`, `serif`, `rounded` | `system` | staff write, staff manage | active or draft | enum only | `theme_body_font` | none | Stage 3 |
| `content.theme.button_style` | string | yes | `solid`, `outline`, `soft` | `solid` | staff write, staff manage | active or draft | enum only | `theme_button_style` | none | Stage 3 |
| `content.identity.store_name` | string | yes | 80 chars | existing Webstore name | staff write, staff manage, assigned owner, assigned manager | active or draft | non-empty text | `store_name` | blank blocks review | Stage 3 |
| `content.identity.subtitle` | string | no | 140 chars | empty string | staff write, staff manage, assigned owner, assigned manager | active or draft | plain text | `identity_subtitle` | none | Stage 3 |
| `content.identity.store_type_label_override` | string | no | 40 chars | canonical type label | staff write, staff manage | active or draft | plain text | `store_type_label` | none | Stage 3 presentation only |

### Header

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.header.layout` | string | yes | `centered`, `left_aligned`, `compact` | `centered` | staff write, staff manage | `content.sections.header_visible = true` | enum only | `header_layout` | none | Stage 3 |

### Logo

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.logo.derivative_id` | string | no | existing derivative id | null | staff write, staff manage, assigned owner, assigned manager | `content.sections.logo_visible = true` | derivative same tenant/Webstore, status `available`, not retired | `logo_public_url` | unavailable derivative blocks review | Stage 3 |
| `content.logo.alt_text` | string | required if derivative id exists | 140 chars | empty string | staff write, staff manage, assigned owner, assigned manager | logo derivative exists | plain text | `logo_alt_text` | blank blocks review | Stage 3 |
| `content.logo.placement` | string | yes | `header`, `hero`, `footer` | `header` | staff write, staff manage | logo derivative exists | enum only | `logo_placement` | none | Stage 3 |

### Hero

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.hero.headline` | string | required if hero visible | 90 chars | store name | staff write, staff manage, assigned owner, assigned manager | `content.sections.hero_visible = true` | plain text | `hero_headline` | blank blocks review | Stage 3 |
| `content.hero.subheadline` | string | no | 160 chars | empty string | staff write, staff manage, assigned owner, assigned manager | hero visible | plain text | `hero_subheadline` | none | Stage 3 |
| `content.hero.body` | rich text | no | 1200 chars | empty string | staff write, staff manage, assigned owner, assigned manager | hero visible | rich-text allowlist | `hero_body` | unsafe content rejected | Stage 3 |
| `content.hero.image_derivative_id` | string | no | existing derivative id | null | staff write, staff manage, assigned owner, assigned manager | hero visible | derivative same tenant/Webstore, status `available`, not retired | `hero_image_public_url` | unavailable derivative blocks review | Stage 3 |
| `content.hero.image_alt_text` | string | required if image derivative id exists | 140 chars | empty string | staff write, staff manage, assigned owner, assigned manager | image derivative exists | plain text | `hero_image_alt_text` | blank blocks review | Stage 3 |
| `content.hero.focal_x` | number | no | `0.0` to `1.0` | `0.5` | staff write, staff manage, assigned owner, assigned manager | image derivative exists | numeric range | `hero_focal_x` | none | Stage 3 |
| `content.hero.focal_y` | number | no | `0.0` to `1.0` | `0.5` | staff write, staff manage, assigned owner, assigned manager | image derivative exists | numeric range | `hero_focal_y` | none | Stage 3 |

### Announcement

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.announcement.text` | string | required if announcement visible | 240 chars | empty string | staff write, staff manage, assigned owner, assigned manager | `content.sections.announcement_visible = true` | plain text | `announcement_text` | blank blocks review | Stage 3 presentation only |
| `content.announcement.style` | string | yes | `info`, `deadline`, `celebration`, `warning` | `info` | staff write, staff manage | announcement visible | enum only | `announcement_style` | none | Stage 3 presentation only |

### Description

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.description.body` | rich text | no | 3000 chars | existing Webstore description | staff write, staff manage, assigned owner, assigned manager | `content.sections.description_visible = true` | rich-text allowlist | `description_body` | unsafe content rejected | Stage 3 |

### Section visibility and ordering

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.sections.order` | array | yes | each section id exactly once | default order | staff manage | active or draft | exact known ids only | `section_order` | invalid order blocks review | Stage 3 |
| `content.sections.header_visible` | boolean | yes | true/false | true | staff write, staff manage | active or draft | boolean | `section_header_visible` | if false, hero must be visible | Stage 3 |
| `content.sections.logo_visible` | boolean | yes | true/false | true | staff write, staff manage, assigned owner, assigned manager | active or draft | boolean | `section_logo_visible` | none | Stage 3 |
| `content.sections.hero_visible` | boolean | yes | true/false | true | staff write, staff manage | active or draft | boolean | `section_hero_visible` | if false, header must be visible | Stage 3 |
| `content.sections.announcement_visible` | boolean | yes | true/false | false | staff write, staff manage, assigned owner, assigned manager | active or draft | boolean | `section_announcement_visible` | see announcement | Stage 3 |
| `content.sections.description_visible` | boolean | yes | true/false | true | staff write, staff manage, assigned owner, assigned manager | active or draft | boolean | `section_description_visible` | none | Stage 3 |
| `content.sections.catalog_slot_visible` | boolean | yes | true/false | false | staff manage | authenticated preview only | boolean | omitted without real catalog products | none | later catalog dependency |
| `content.sections.fulfillment_visible` | boolean | yes | true/false | false | staff write, staff manage, assigned owner, assigned manager | active or draft | boolean | `section_fulfillment_visible` | none | Stage 3 presentation only |
| `content.sections.policies_visible` | boolean | yes | true/false | false | staff write, staff manage, assigned owner, assigned manager | active or draft | boolean | `section_policies_visible` | none | Stage 3 presentation only |
| `content.sections.contact_visible` | boolean | yes | true/false | false | staff write, staff manage, assigned owner, assigned manager | active or draft | boolean | `section_contact_visible` | if true, email or phone required | Stage 3 |
| `content.sections.footer_visible` | boolean | yes | true/false | true | staff write, staff manage, assigned owner, assigned manager | active or draft | boolean | `section_footer_visible` | none | Stage 3 |

### Future catalog slot

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.catalog_slot.title` | string | no | 80 chars | `Products` | staff manage | authenticated preview only | plain text | omitted without real catalog products | none | later catalog dependency |
| `content.catalog_slot.message` | string | no | 240 chars | empty string | staff manage | authenticated preview only | plain text | omitted without real catalog products | none | later catalog dependency |

### Fulfillment and pickup

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.fulfillment.pickup_summary` | string | no | 500 chars | empty string | staff write, staff manage, assigned owner, assigned manager | `content.sections.fulfillment_visible = true` | plain text | `fulfillment_pickup_summary` | none | presentation only, not pickup scheduling |
| `content.fulfillment.turnaround_text` | string | no | 240 chars | empty string | staff write, staff manage, assigned owner, assigned manager | fulfillment visible | plain text | `fulfillment_turnaround_text` | none | presentation only, not production deadline |

### Policies

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.policies.return_policy_summary` | string | no | 1000 chars | empty string | staff write, staff manage, assigned owner, assigned manager | `content.sections.policies_visible = true` | plain text | `policies_return_policy_summary` | none | presentation only, not legal policy engine |
| `content.policies.order_deadline_display_text` | string | no | 240 chars | empty string | staff write, staff manage, assigned owner, assigned manager | policies visible | plain text | `policies_order_deadline_display_text` | none | presentation only, not ordering cutoff authority |

### Contact and help

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.contact.public_email` | string | no | 254 chars | empty string | staff write, staff manage, assigned owner, assigned manager | `content.sections.contact_visible = true` | valid email | `contact_public_email` | invalid rejects save | Stage 3 |
| `content.contact.public_phone` | string | no | 40 chars | empty string | staff write, staff manage, assigned owner, assigned manager | contact visible | phone chars only | `contact_public_phone` | invalid rejects save | Stage 3 |
| `content.contact.help_text` | string | no | 500 chars | empty string | staff write, staff manage, assigned owner, assigned manager | contact visible | plain text | `contact_help_text` | none | Stage 3 |

### Footer

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.footer.note` | string | no | 500 chars | empty string | staff write, staff manage, assigned owner, assigned manager | `content.sections.footer_visible = true` | plain text | `footer_note` | none | Stage 3 |
| `content.footer.link_1_label` | string | no | 60 chars | empty string | staff write, staff manage, assigned owner, assigned manager | footer visible | required if link 1 URL set | `footer_link_1_label` | invalid blocks review | Stage 3 |
| `content.footer.link_1_url` | string | no | 500 chars | empty string | staff write, staff manage, assigned owner, assigned manager | footer visible | protocol `https`, `mailto`, or `tel` | `footer_link_1_url` | invalid rejects save | Stage 3 |
| `content.footer.link_2_label` | string | no | 60 chars | empty string | staff write, staff manage, assigned owner, assigned manager | footer visible | required if link 2 URL set | `footer_link_2_label` | invalid blocks review | Stage 3 |
| `content.footer.link_2_url` | string | no | 500 chars | empty string | staff write, staff manage, assigned owner, assigned manager | footer visible | protocol `https`, `mailto`, or `tel` | `footer_link_2_url` | invalid rejects save | Stage 3 |

### B2B fields

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.type.b2b.organization_name` | string | no | 120 chars | empty string | staff write, staff manage, assigned owner, assigned manager | Webstore type `b2b` | plain text | `type_b2b_organization_name` | none | presentation only |
| `content.type.b2b.buyer_instructions` | rich text | no | 1200 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `b2b` | rich-text allowlist | `type_b2b_buyer_instructions` | unsafe rejected | presentation only, not access control |
| `content.type.b2b.access_message` | string | no | 300 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `b2b` | plain text | `type_b2b_access_message` | none | presentation only, not buyer restriction |

### Fundraiser fields

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.type.fundraiser.beneficiary_name` | string | no | 120 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `fundraiser` | plain text | `type_fundraiser_beneficiary_name` | none | presentation only |
| `content.type.fundraiser.story` | rich text | no | 1800 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `fundraiser` | rich-text allowlist | `type_fundraiser_story` | unsafe rejected | presentation only |
| `content.type.fundraiser.goal_display_text` | string | no | 160 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `fundraiser` | plain text | `type_fundraiser_goal_display_text` | none | presentation only, not accounting goal |
| `content.type.fundraiser.donation_message` | string | no | 240 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `fundraiser` | plain text | `type_fundraiser_donation_message` | none | presentation only, does not enable donations |

### Event fields

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.type.event.name` | string | no | 120 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `event` | plain text | `type_event_name` | none | presentation only |
| `content.type.event.date_display_text` | string | no | 160 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `event` | plain text | `type_event_date_display_text` | none | presentation only, not schedule authority |
| `content.type.event.location_display_text` | string | no | 240 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `event` | plain text | `type_event_location_display_text` | none | presentation only |
| `content.type.event.pickup_note` | string | no | 300 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `event` | plain text | `type_event_pickup_note` | none | presentation only, not pickup appointment |

### Promotional fields

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.type.promotional.promoted_name` | string | no | 120 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `promotional` | plain text | `type_promotional_promoted_name` | none | presentation only |
| `content.type.promotional.brand_story` | rich text | no | 1600 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `promotional` | rich-text allowlist | `type_promotional_brand_story` | unsafe rejected | presentation only |
| `content.type.promotional.social_link_1_label` | string | no | 60 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `promotional` | required if URL set | `type_promotional_social_link_1_label` | invalid blocks review | Stage 3 |
| `content.type.promotional.social_link_1_url` | string | no | 500 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `promotional` | protocol `https`, `mailto`, or `tel` | `type_promotional_social_link_1_url` | invalid rejects save | Stage 3 |
| `content.type.promotional.social_link_2_label` | string | no | 60 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `promotional` | required if URL set | `type_promotional_social_link_2_label` | invalid blocks review | Stage 3 |
| `content.type.promotional.social_link_2_url` | string | no | 500 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `promotional` | protocol `https`, `mailto`, or `tel` | `type_promotional_social_link_2_url` | invalid rejects save | Stage 3 |

### Employee fields

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.type.employee.company_name` | string | no | 120 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `employee` | plain text | `type_employee_company_name` | none | presentation only |
| `content.type.employee.eligibility_message` | string | no | 500 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `employee` | plain text | `type_employee_eligibility_message` | none | presentation only, not access restriction |
| `content.type.employee.uniform_program_note` | string | no | 500 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `employee` | plain text | `type_employee_uniform_program_note` | none | presentation only, not HR/payroll rule |

### General fields

| Key | Type | Required | Max or enum | Default | Editable by | Visibility condition | Write validation | Public serializer field | Readiness effect | Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| `content.type.general.store_purpose` | string | no | 120 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `general` | plain text | `type_general_store_purpose` | none | presentation only |
| `content.type.general.message` | rich text | no | 1600 chars | empty string | staff write, staff manage, assigned owner, assigned manager | type `general` | rich-text allowlist | `type_general_message` | unsafe rejected | Stage 3 |
| `content.type.general.layout_style` | string | yes | `simple`, `branded`, `event_like` | `simple` | staff write, staff manage | type `general` | enum only | `type_general_layout_style` | none | Stage 3 presentation only |

## 9. Exact Permission Matrix

Platform support prerequisite:

- `has_platform_admin_access(user) == True`
- explicit tenant id selected by a server-owned platform-support route
- support reason supplied
- support actor id and email recorded
- ordinary tenant route does not grant automatic platform impersonation

| Capability | Platform support with explicit tenant support context | Tenant owner/admin role | Staff with `webstore:write` | Staff with `webstore:manage` | Assigned Store Owner | Assigned Store Manager | Public shopper | Unauthenticated visitor |
|---|---|---|---|---|---|---|---|---|
| Create draft | allow | allow | allow | allow | allow | allow | deny | deny |
| Edit identity | allow | allow | allow | allow | allow | allow | deny | deny |
| Edit shared public content | allow | allow | allow | allow | allow | allow | deny | deny |
| Edit type-specific content | allow | allow | allow | allow | allow | allow | deny | deny |
| Reorder sections | allow | allow | deny | allow | deny | deny | deny | deny |
| Change `content.sections.header_visible` | allow | allow | allow | allow | deny | deny | deny | deny |
| Change `content.sections.logo_visible` | allow | allow | allow | allow | allow | allow | deny | deny |
| Change `content.sections.hero_visible` | allow | allow | allow | allow | deny | deny | deny | deny |
| Change `content.sections.announcement_visible` | allow | allow | allow | allow | allow | allow | deny | deny |
| Change `content.sections.description_visible` | allow | allow | allow | allow | allow | allow | deny | deny |
| Change `content.sections.catalog_slot_visible` | allow | allow | deny | allow | deny | deny | deny | deny |
| Change `content.sections.fulfillment_visible` | allow | allow | allow | allow | allow | allow | deny | deny |
| Change `content.sections.policies_visible` | allow | allow | allow | allow | allow | allow | deny | deny |
| Change `content.sections.contact_visible` | allow | allow | allow | allow | allow | allow | deny | deny |
| Change `content.sections.footer_visible` | allow | allow | allow | allow | allow | allow | deny | deny |
| Preview authenticated draft | allow | allow | allow | allow | allow | allow | deny | deny |
| Request Owner Review | allow | allow | allow | allow | deny | allow | deny | deny |
| Request Changes as Store Owner | deny | deny | deny | deny | allow | deny | deny | deny |
| Request Changes as staff | allow | allow | deny | allow | deny | deny | deny | deny |
| Respond to requested changes by editing draft | allow | allow | allow | allow | allow | allow | deny | deny |
| Owner Approve | deny | deny | deny | deny | allow | deny | deny | deny |
| Staff Approve | allow | allow | deny | allow | deny | deny | deny | deny |
| Activate Branding | allow | allow | deny | allow | deny | deny | deny | deny |
| Restore as New Draft | allow | allow | deny | allow | deny | deny | deny | deny |
| View private source summary | allow | allow | allow | allow | allow | allow | deny | deny |
| Download private source | allow | allow | deny | allow | allow | allow | deny | deny |
| Generate derivative | allow | allow | allow | allow | allow | allow | deny | deny |
| Select derivative | allow | allow | allow | allow | allow | allow | deny | deny |
| Retire private source | allow | allow | deny | allow | deny | deny | deny | deny |
| Retire unused derivative | allow | allow | deny | allow | deny | deny | deny | deny |
| View full audit | allow | allow | deny | allow | deny | deny | deny | deny |
| View portal-safe history | allow | allow | allow | allow | allow | allow | deny | deny |
| Retrieve public storefront response | public route checks only | public route checks only | public route checks only | public route checks only | public route checks only | public route checks only | allow after public route gate | allow after public route gate |
| Retrieve public derivative bytes | public route checks only | public route checks only | public route checks only | public route checks only | public route checks only | public route checks only | allow after public route gate | allow after public route gate |

### Visibility Field Authority

| Field path | Staff read/write authority | Owner read/write authority | Manager read/write authority | Preview visibility | Public serializer behavior | Validation rule | UI control | Denied-request result |
|---|---|---|---|---|---|---|---|
| `content.sections.header_visible` | `webstore:write` and `webstore:manage` can read/write | read only | read only | visible in authenticated preview as `section_header_visible` | serialized as `section_header_visible` for active version | boolean; if false, `content.sections.hero_visible` must be true | Staff Header visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |
| `content.sections.logo_visible` | `webstore:write` and `webstore:manage` can read/write | assigned active Store Owner can read/write | assigned active Store Manager can read/write | visible in authenticated preview as `section_logo_visible` | serialized as `section_logo_visible` for active version | boolean; sole logo visibility source | Logo visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |
| `content.sections.hero_visible` | `webstore:write` and `webstore:manage` can read/write | read only | read only | visible in authenticated preview as `section_hero_visible` | serialized as `section_hero_visible` for active version | boolean; if false, `content.sections.header_visible` must be true | Staff Hero visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |
| `content.sections.announcement_visible` | `webstore:write` and `webstore:manage` can read/write | assigned active Store Owner can read/write | assigned active Store Manager can read/write | visible in authenticated preview as `section_announcement_visible` | serialized as `section_announcement_visible` for active version | boolean; when true, announcement text is required | Announcement visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |
| `content.sections.description_visible` | `webstore:write` and `webstore:manage` can read/write | assigned active Store Owner can read/write | assigned active Store Manager can read/write | visible in authenticated preview as `section_description_visible` | serialized as `section_description_visible` for active version | boolean | Description visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |
| `content.sections.catalog_slot_visible` | `webstore:manage` can read/write; `webstore:write` can read only | read only | read only | visible only in authenticated preview as `section_catalog_slot_visible` | omitted until real catalog products exist | boolean; no public catalog placeholder | Staff Catalog-slot visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |
| `content.sections.fulfillment_visible` | `webstore:write` and `webstore:manage` can read/write | assigned active Store Owner can read/write | assigned active Store Manager can read/write | visible in authenticated preview as `section_fulfillment_visible` | serialized as `section_fulfillment_visible` for active version | boolean | Fulfillment visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |
| `content.sections.policies_visible` | `webstore:write` and `webstore:manage` can read/write | assigned active Store Owner can read/write | assigned active Store Manager can read/write | visible in authenticated preview as `section_policies_visible` | serialized as `section_policies_visible` for active version | boolean | Policies visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |
| `content.sections.contact_visible` | `webstore:write` and `webstore:manage` can read/write | assigned active Store Owner can read/write | assigned active Store Manager can read/write | visible in authenticated preview as `section_contact_visible` | serialized as `section_contact_visible` for active version | boolean; when true, public email or public phone is required | Contact visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |
| `content.sections.footer_visible` | `webstore:write` and `webstore:manage` can read/write | assigned active Store Owner can read/write | assigned active Store Manager can read/write | visible in authenticated preview as `section_footer_visible` | serialized as `section_footer_visible` for active version | boolean | Footer visibility toggle | `403 VISIBILITY_FIELD_FORBIDDEN` |

## 10. Seven Fully Expanded Serializers

### Staff draft serializer permitted fields

- `webstore_id`
- `webstore_name`
- `public_slug`
- `store_type`
- `active_branding_version_id`
- `active_branding_snapshot_hash`
- `draft_id`
- `draft_state`
- `draft_revision`
- `editable`
- `base_active_version_id`
- `derived_from_version_id`
- `restored_from_version_id`
- `review_cycle`
- `review_snapshot_id`
- `snapshot_hash`
- `field_schema_version`
- `validation_result_id`
- `validation_schema_version`
- `validated_draft_revision`
- `validated_review_snapshot_id`
- `validated_snapshot_hash`
- `validated_at`
- `validation_error_codes`
- `validation_warning_codes`
- `theme_primary_color`
- `theme_secondary_color`
- `theme_accent_color`
- `theme_background_color`
- `theme_text_color`
- `theme_heading_font`
- `theme_body_font`
- `theme_button_style`
- `identity_store_name`
- `identity_subtitle`
- `identity_store_type_label_override`
- `header_layout`
- `logo_derivative_id`
- `logo_public_url`
- `logo_alt_text`
- `logo_placement`
- `hero_headline`
- `hero_subheadline`
- `hero_body`
- `hero_image_derivative_id`
- `hero_image_public_url`
- `hero_image_alt_text`
- `hero_focal_x`
- `hero_focal_y`
- `announcement_text`
- `announcement_style`
- `description_body`
- `section_order`
- `section_header_visible`
- `section_logo_visible`
- `section_hero_visible`
- `section_announcement_visible`
- `section_description_visible`
- `section_catalog_slot_visible`
- `section_fulfillment_visible`
- `section_policies_visible`
- `section_contact_visible`
- `section_footer_visible`
- `catalog_slot_title`
- `catalog_slot_message`
- `fulfillment_pickup_summary`
- `fulfillment_turnaround_text`
- `policies_return_policy_summary`
- `policies_order_deadline_display_text`
- `contact_public_email`
- `contact_public_phone`
- `contact_help_text`
- `footer_note`
- `footer_link_1_label`
- `footer_link_1_url`
- `footer_link_2_label`
- `footer_link_2_url`
- `type_b2b_organization_name`
- `type_b2b_buyer_instructions`
- `type_b2b_access_message`
- `type_fundraiser_beneficiary_name`
- `type_fundraiser_story`
- `type_fundraiser_goal_display_text`
- `type_fundraiser_donation_message`
- `type_event_name`
- `type_event_date_display_text`
- `type_event_location_display_text`
- `type_event_pickup_note`
- `type_promotional_promoted_name`
- `type_promotional_brand_story`
- `type_promotional_social_link_1_label`
- `type_promotional_social_link_1_url`
- `type_promotional_social_link_2_label`
- `type_promotional_social_link_2_url`
- `type_employee_company_name`
- `type_employee_eligibility_message`
- `type_employee_uniform_program_note`
- `type_general_store_purpose`
- `type_general_message`
- `type_general_layout_style`
- `readiness_active_version_status`
- `readiness_working_draft_status`
- `readiness_approval_status`
- `readiness_asset_status`
- `readiness_accessibility_status`
- `readiness_branding_stage_complete`
- `readiness_blocking_reason_codes`
- `readiness_message`
- `created_at`
- `updated_at`

Staff draft serializer forbidden fields:

- `_id`
- `tenant_id`
- `owner_id`
- `source_storage_key`
- `derivative_storage_key`
- `storage_key`
- `temporary_storage_key`
- `final_storage_key`
- `token_hash`
- `invitation_token`
- `raw_source_bytes`
- `raw_svg`
- `raw_event_snapshot`
- `supplier_name`
- `supplier_cost_cents`
- `production_cost_cents`
- `margin_cents`
- `platform_internal_notes`
- `staff_private_notes`
- `stripe_account_id`
- `stripe_checkout_session_id`
- `provider_payment_id`
- `provider_event_id`
- `lease_owner_token`
- `activation_lock_operation_id`
- `activation_lock_owner_token`
- `activation_lock_acquired_at`
- `activation_lock_expires_at`
- `lease_expires_at`

### Staff immutable version/history serializer permitted fields

- `webstore_id`
- `webstore_name`
- `public_slug`
- `store_type`
- `version_id`
- `version_number`
- `snapshot_hash`
- `content_hash`
- `asset_reference_hash`
- `field_schema_version`
- `source_draft_id`
- `source_draft_revision`
- `source_review_cycle`
- `source_review_snapshot_id`
- `review_snapshot_id`
- `validation_result_id`
- `validation_schema_version`
- `validator_implementation_version`
- `validated_draft_revision`
- `derived_from_version_id`
- `restored_from_version_id`
- `is_current_active_version`
- `activated_at`
- `theme_primary_color`
- `theme_secondary_color`
- `theme_accent_color`
- `theme_background_color`
- `theme_text_color`
- `theme_heading_font`
- `theme_body_font`
- `theme_button_style`
- `identity_store_name`
- `identity_subtitle`
- `identity_store_type_label_override`
- `header_layout`
- `logo_derivative_id`
- `logo_public_url`
- `logo_alt_text`
- `logo_placement`
- `hero_headline`
- `hero_subheadline`
- `hero_body`
- `hero_image_derivative_id`
- `hero_image_public_url`
- `hero_image_alt_text`
- `hero_focal_x`
- `hero_focal_y`
- `announcement_text`
- `announcement_style`
- `description_body`
- `section_order`
- `section_header_visible`
- `section_logo_visible`
- `section_hero_visible`
- `section_announcement_visible`
- `section_description_visible`
- `section_catalog_slot_visible`
- `section_fulfillment_visible`
- `section_policies_visible`
- `section_contact_visible`
- `section_footer_visible`
- `catalog_slot_title`
- `catalog_slot_message`
- `fulfillment_pickup_summary`
- `fulfillment_turnaround_text`
- `policies_return_policy_summary`
- `policies_order_deadline_display_text`
- `contact_public_email`
- `contact_public_phone`
- `contact_help_text`
- `footer_note`
- `footer_link_1_label`
- `footer_link_1_url`
- `footer_link_2_label`
- `footer_link_2_url`
- `type_b2b_organization_name`
- `type_b2b_buyer_instructions`
- `type_b2b_access_message`
- `type_fundraiser_beneficiary_name`
- `type_fundraiser_story`
- `type_fundraiser_goal_display_text`
- `type_fundraiser_donation_message`
- `type_event_name`
- `type_event_date_display_text`
- `type_event_location_display_text`
- `type_event_pickup_note`
- `type_promotional_promoted_name`
- `type_promotional_brand_story`
- `type_promotional_social_link_1_label`
- `type_promotional_social_link_1_url`
- `type_promotional_social_link_2_label`
- `type_promotional_social_link_2_url`
- `type_employee_company_name`
- `type_employee_eligibility_message`
- `type_employee_uniform_program_note`
- `type_general_store_purpose`
- `type_general_message`
- `type_general_layout_style`
- `created_by_user_id`
- `created_by_email`
- `created_at`
- `updated_at`

Staff immutable version/history serializer forbidden fields:

- `_id`
- `tenant_id`
- `owner_id`
- `source_storage_key`
- `derivative_storage_key`
- `storage_key`
- `temporary_storage_key`
- `final_storage_key`
- `token_hash`
- `invitation_token`
- `raw_source_bytes`
- `raw_svg`
- `raw_event_snapshot`
- `supplier_name`
- `supplier_cost_cents`
- `production_cost_cents`
- `margin_cents`
- `platform_internal_notes`
- `staff_private_notes`
- `stripe_account_id`
- `stripe_checkout_session_id`
- `provider_payment_id`
- `provider_event_id`
- `lease_owner_token`
- `lease_expires_at`

### Store Owner serializer permitted fields

- `webstore_id`
- `webstore_name`
- `public_slug`
- `store_type`
- `draft_id`
- `draft_state`
- `draft_revision`
- `editable`
- `review_cycle`
- `review_snapshot_id`
- `snapshot_hash`
- `field_schema_version`
- `validation_schema_version`
- `validated_draft_revision`
- `validated_review_snapshot_id`
- `validated_snapshot_hash`
- `validated_at`
- `validation_error_codes`
- `validation_warning_codes`
- `theme_primary_color`
- `theme_secondary_color`
- `theme_accent_color`
- `theme_background_color`
- `theme_text_color`
- `identity_store_name`
- `identity_subtitle`
- `header_layout`
- `logo_derivative_id`
- `logo_public_url`
- `logo_alt_text`
- `logo_placement`
- `hero_headline`
- `hero_subheadline`
- `hero_body`
- `hero_image_derivative_id`
- `hero_image_public_url`
- `hero_image_alt_text`
- `hero_focal_x`
- `hero_focal_y`
- `announcement_text`
- `announcement_style`
- `description_body`
- `section_header_visible`
- `section_logo_visible`
- `section_hero_visible`
- `section_announcement_visible`
- `section_description_visible`
- `section_fulfillment_visible`
- `section_policies_visible`
- `section_contact_visible`
- `section_footer_visible`
- `fulfillment_pickup_summary`
- `fulfillment_turnaround_text`
- `policies_return_policy_summary`
- `policies_order_deadline_display_text`
- `contact_public_email`
- `contact_public_phone`
- `contact_help_text`
- `footer_note`
- `footer_link_1_label`
- `footer_link_1_url`
- `footer_link_2_label`
- `footer_link_2_url`
- `type_b2b_organization_name`
- `type_b2b_buyer_instructions`
- `type_b2b_access_message`
- `type_fundraiser_beneficiary_name`
- `type_fundraiser_story`
- `type_fundraiser_goal_display_text`
- `type_fundraiser_donation_message`
- `type_event_name`
- `type_event_date_display_text`
- `type_event_location_display_text`
- `type_event_pickup_note`
- `type_promotional_promoted_name`
- `type_promotional_brand_story`
- `type_promotional_social_link_1_label`
- `type_promotional_social_link_1_url`
- `type_promotional_social_link_2_label`
- `type_promotional_social_link_2_url`
- `type_employee_company_name`
- `type_employee_eligibility_message`
- `type_employee_uniform_program_note`
- `type_general_store_purpose`
- `type_general_message`
- `owner_approval_status`
- `staff_approval_status`
- `can_request_owner_review`
- `can_request_changes_as_owner`
- `can_owner_approve`
- `can_staff_approve`
- `can_activate`
- `portal_history_event_id`
- `portal_history_event_type`
- `portal_history_created_at`
- `portal_history_actor_role`
- `portal_history_summary`

Store Owner serializer forbidden fields:

- `_id`
- `tenant_id`
- `owner_id`
- `active_branding_version_id`
- `source_storage_key`
- `derivative_storage_key`
- `storage_key`
- `temporary_storage_key`
- `final_storage_key`
- `token_hash`
- `invitation_token`
- `raw_source_bytes`
- `raw_svg`
- `raw_event_snapshot`
- `actor_user_id`
- `actor_email`
- `supplier_name`
- `supplier_cost_cents`
- `production_cost_cents`
- `margin_cents`
- `platform_internal_notes`
- `staff_private_notes`
- `stripe_account_id`
- `stripe_checkout_session_id`
- `provider_payment_id`
- `provider_event_id`
- `lease_owner_token`
- `lease_expires_at`

### Store Manager serializer permitted fields

- `webstore_id`
- `webstore_name`
- `public_slug`
- `store_type`
- `draft_id`
- `draft_state`
- `draft_revision`
- `editable`
- `review_cycle`
- `review_snapshot_id`
- `snapshot_hash`
- `field_schema_version`
- `validation_schema_version`
- `validated_draft_revision`
- `validated_review_snapshot_id`
- `validated_snapshot_hash`
- `validated_at`
- `validation_error_codes`
- `validation_warning_codes`
- `theme_primary_color`
- `theme_secondary_color`
- `theme_accent_color`
- `theme_background_color`
- `theme_text_color`
- `identity_store_name`
- `identity_subtitle`
- `header_layout`
- `logo_derivative_id`
- `logo_public_url`
- `logo_alt_text`
- `logo_placement`
- `hero_headline`
- `hero_subheadline`
- `hero_body`
- `hero_image_derivative_id`
- `hero_image_public_url`
- `hero_image_alt_text`
- `hero_focal_x`
- `hero_focal_y`
- `announcement_text`
- `announcement_style`
- `description_body`
- `section_header_visible`
- `section_logo_visible`
- `section_hero_visible`
- `section_announcement_visible`
- `section_description_visible`
- `section_fulfillment_visible`
- `section_policies_visible`
- `section_contact_visible`
- `section_footer_visible`
- `fulfillment_pickup_summary`
- `fulfillment_turnaround_text`
- `policies_return_policy_summary`
- `policies_order_deadline_display_text`
- `contact_public_email`
- `contact_public_phone`
- `contact_help_text`
- `footer_note`
- `footer_link_1_label`
- `footer_link_1_url`
- `footer_link_2_label`
- `footer_link_2_url`
- `type_b2b_organization_name`
- `type_b2b_buyer_instructions`
- `type_b2b_access_message`
- `type_fundraiser_beneficiary_name`
- `type_fundraiser_story`
- `type_fundraiser_goal_display_text`
- `type_fundraiser_donation_message`
- `type_event_name`
- `type_event_date_display_text`
- `type_event_location_display_text`
- `type_event_pickup_note`
- `type_promotional_promoted_name`
- `type_promotional_brand_story`
- `type_promotional_social_link_1_label`
- `type_promotional_social_link_1_url`
- `type_promotional_social_link_2_label`
- `type_promotional_social_link_2_url`
- `type_employee_company_name`
- `type_employee_eligibility_message`
- `type_employee_uniform_program_note`
- `type_general_store_purpose`
- `type_general_message`
- `owner_approval_status`
- `staff_approval_status`
- `can_request_owner_review`
- `can_request_changes_as_owner`
- `can_owner_approve`
- `can_staff_approve`
- `can_activate`
- `portal_history_event_id`
- `portal_history_event_type`
- `portal_history_created_at`
- `portal_history_actor_role`
- `portal_history_summary`

Store Manager serializer forbidden fields:

- `_id`
- `tenant_id`
- `owner_id`
- `active_branding_version_id`
- `source_storage_key`
- `derivative_storage_key`
- `storage_key`
- `temporary_storage_key`
- `final_storage_key`
- `token_hash`
- `invitation_token`
- `raw_source_bytes`
- `raw_svg`
- `raw_event_snapshot`
- `actor_user_id`
- `actor_email`
- `supplier_name`
- `supplier_cost_cents`
- `production_cost_cents`
- `margin_cents`
- `platform_internal_notes`
- `staff_private_notes`
- `stripe_account_id`
- `stripe_checkout_session_id`
- `provider_payment_id`
- `provider_event_id`
- `lease_owner_token`
- `lease_expires_at`

### Authenticated preview serializer permitted fields

- `webstore_id`
- `webstore_name`
- `public_slug`
- `store_type`
- `preview_source`
- `preview_draft_id`
- `preview_version_id`
- `preview_revision`
- `theme_primary_color`
- `theme_secondary_color`
- `theme_accent_color`
- `theme_background_color`
- `theme_text_color`
- `theme_heading_font`
- `theme_body_font`
- `theme_button_style`
- `identity_store_name`
- `identity_subtitle`
- `identity_store_type_label_override`
- `header_layout`
- `logo_public_url`
- `logo_alt_text`
- `logo_placement`
- `hero_headline`
- `hero_subheadline`
- `hero_body`
- `hero_image_public_url`
- `hero_image_alt_text`
- `hero_focal_x`
- `hero_focal_y`
- `announcement_text`
- `announcement_style`
- `description_body`
- `section_order`
- `section_header_visible`
- `section_logo_visible`
- `section_hero_visible`
- `section_announcement_visible`
- `section_description_visible`
- `section_catalog_slot_visible`
- `section_fulfillment_visible`
- `section_policies_visible`
- `section_contact_visible`
- `section_footer_visible`
- `catalog_slot_title`
- `catalog_slot_message`
- `fulfillment_pickup_summary`
- `fulfillment_turnaround_text`
- `policies_return_policy_summary`
- `policies_order_deadline_display_text`
- `contact_public_email`
- `contact_public_phone`
- `contact_help_text`
- `footer_note`
- `footer_link_1_label`
- `footer_link_1_url`
- `footer_link_2_label`
- `footer_link_2_url`
- `type_b2b_organization_name`
- `type_b2b_buyer_instructions`
- `type_b2b_access_message`
- `type_fundraiser_beneficiary_name`
- `type_fundraiser_story`
- `type_fundraiser_goal_display_text`
- `type_fundraiser_donation_message`
- `type_event_name`
- `type_event_date_display_text`
- `type_event_location_display_text`
- `type_event_pickup_note`
- `type_promotional_promoted_name`
- `type_promotional_brand_story`
- `type_promotional_social_link_1_label`
- `type_promotional_social_link_1_url`
- `type_promotional_social_link_2_label`
- `type_promotional_social_link_2_url`
- `type_employee_company_name`
- `type_employee_eligibility_message`
- `type_employee_uniform_program_note`
- `type_general_store_purpose`
- `type_general_message`
- `type_general_layout_style`
- `validation_error_codes`
- `validation_warning_codes`

Authenticated preview serializer forbidden fields:

- `_id`
- `tenant_id`
- `owner_id`
- `active_branding_version_id`
- `source_storage_key`
- `derivative_storage_key`
- `storage_key`
- `temporary_storage_key`
- `final_storage_key`
- `token_hash`
- `invitation_token`
- `raw_source_bytes`
- `raw_svg`
- `raw_event_snapshot`
- `actor_user_id`
- `actor_email`
- `supplier_name`
- `supplier_cost_cents`
- `production_cost_cents`
- `margin_cents`
- `platform_internal_notes`
- `staff_private_notes`
- `stripe_account_id`
- `stripe_checkout_session_id`
- `provider_payment_id`
- `provider_event_id`
- `lease_owner_token`
- `lease_expires_at`

### Public Storefront serializer permitted fields

- `public_slug`
- `store_name`
- `store_type`
- `store_type_label`
- `theme_primary_color`
- `theme_secondary_color`
- `theme_accent_color`
- `theme_background_color`
- `theme_text_color`
- `theme_heading_font`
- `theme_body_font`
- `theme_button_style`
- `identity_subtitle`
- `header_layout`
- `logo_public_url`
- `logo_alt_text`
- `logo_placement`
- `hero_headline`
- `hero_subheadline`
- `hero_body`
- `hero_image_public_url`
- `hero_image_alt_text`
- `hero_focal_x`
- `hero_focal_y`
- `announcement_text`
- `announcement_style`
- `description_body`
- `section_order`
- `section_header_visible`
- `section_logo_visible`
- `section_hero_visible`
- `section_announcement_visible`
- `section_description_visible`
- `section_catalog_slot_visible`
- `section_fulfillment_visible`
- `section_policies_visible`
- `section_contact_visible`
- `section_footer_visible`
- `fulfillment_pickup_summary`
- `fulfillment_turnaround_text`
- `policies_return_policy_summary`
- `policies_order_deadline_display_text`
- `contact_public_email`
- `contact_public_phone`
- `contact_help_text`
- `footer_note`
- `footer_link_1_label`
- `footer_link_1_url`
- `footer_link_2_label`
- `footer_link_2_url`
- `type_b2b_organization_name`
- `type_b2b_buyer_instructions`
- `type_b2b_access_message`
- `type_fundraiser_beneficiary_name`
- `type_fundraiser_story`
- `type_fundraiser_goal_display_text`
- `type_fundraiser_donation_message`
- `type_event_name`
- `type_event_date_display_text`
- `type_event_location_display_text`
- `type_event_pickup_note`
- `type_promotional_promoted_name`
- `type_promotional_brand_story`
- `type_promotional_social_link_1_label`
- `type_promotional_social_link_1_url`
- `type_promotional_social_link_2_label`
- `type_promotional_social_link_2_url`
- `type_employee_company_name`
- `type_employee_eligibility_message`
- `type_employee_uniform_program_note`
- `type_general_store_purpose`
- `type_general_message`
- `type_general_layout_style`
- `checkout_enabled`
- `checkout_unavailable_reason`
- `product_id`
- `product_name`
- `product_description`
- `product_category`
- `product_type`
- `product_sku`
- `product_selling_price_cents`
- `product_currency`
- `product_variants`
- `product_personalization_enabled`
- `product_image_file_ids`
- `product_mockup_ids`
- `product_public`
- `product_featured`
- `product_status`

Public Storefront serializer forbidden fields:

- `_id`
- `id`
- `tenant_id`
- `webstore_id`
- `owner_id`
- `active_branding_version_id`
- `active_branding_snapshot_hash`
- `branding_activation_operation_id`
- `draft_id`
- `draft_revision`
- `review_cycle`
- `review_snapshot_id`
- `snapshot_hash`
- `content_hash`
- `asset_reference_hash`
- `source_draft_id`
- `source_review_cycle`
- `source_review_snapshot_id`
- `source_storage_key`
- `derivative_storage_key`
- `storage_key`
- `temporary_storage_key`
- `final_storage_key`
- `token_hash`
- `invitation_token`
- `raw_source_bytes`
- `raw_svg`
- `raw_event_snapshot`
- `actor_user_id`
- `actor_email`
- `created_by_user_id`
- `created_by_email`
- `supplier_name`
- `supplier_cost_cents`
- `production_cost_cents`
- `margin_cents`
- `platform_internal_notes`
- `staff_private_notes`
- `stripe_account_id`
- `stripe_checkout_session_id`
- `provider_payment_id`
- `provider_event_id`
- `lease_owner_token`
- `lease_expires_at`
- `catalog_slot_title`
- `catalog_slot_message`

### Public asset response permitted fields

The public asset response is a byte response. It has no JSON body.

Permitted response headers:

- `Content-Type`
- `Content-Length`
- `ETag`
- `Cache-Control`
- `X-Content-Type-Options`
- `Content-Security-Policy`
- `Content-Disposition`

Permitted status codes:

- `200`
- `304`
- `404`

Public asset response forbidden fields:

- `_id`
- `id`
- `tenant_id`
- `webstore_id`
- `source_asset_id`
- `derivative_operation_id`
- `source_storage_key`
- `derivative_storage_key`
- `storage_key`
- `temporary_storage_key`
- `final_storage_key`
- `token_hash`
- `invitation_token`
- `raw_source_bytes`
- `raw_svg`
- `actor_user_id`
- `actor_email`
- `created_by_user_id`
- `created_by_email`
- `supplier_name`
- `supplier_cost_cents`
- `production_cost_cents`
- `margin_cents`
- `platform_internal_notes`
- `staff_private_notes`
- `stripe_account_id`
- `stripe_checkout_session_id`
- `provider_payment_id`
- `provider_event_id`
- `lease_owner_token`
- `lease_expires_at`

## 11. Derivative Claim, Processing, Storage, Serving, and Retirement

Supported private source inputs:

- PNG
- JPEG
- WebP
- SVG
- AI
- EPS

Supported public derivative outputs:

- PNG
- JPEG
- WebP
- sanitized SVG

Unsupported source response:

- HTTP `415`
- Error code: `UNSUPPORTED_SOURCE_FORMAT`
- No derivative operation record is created.
- No derivative bytes are written.
- Audit event: `webstore.branding_derivative_rejected_unsupported_source`

AI/EPS treatment:

- AI and EPS may be stored as private source assets.
- AI and EPS cannot be decoded into public derivatives in Stage 3.
- Requesting derivative generation from AI/EPS without a supported preview
  returns HTTP `415`.
- Error code: `UNSUPPORTED_SOURCE_FORMAT`.
- No public asset key is created.

Limits:

- Maximum upload bytes: `52_428_800`.
- Maximum decoded pixels: `40_000_000`.
- Maximum decoded width: `8000`.
- Maximum decoded height: `8000`.
- Maximum SVG source bytes: `2_000_000`.
- Hero output max width: `2400`.
- Hero output max height: `1200`.
- Logo output max width: `1024`.
- Logo output max height: `1024`.
- General output longest side: `2400`.
- JPEG quality: `85`.
- WebP quality: `85`.
- PNG compression level: `6`.

File signature detection:

- JPEG: first bytes `FF D8`.
- PNG: first bytes `89 50 4E 47 0D 0A 1A 0A`.
- WebP: bytes 0-3 `RIFF` and bytes 8-11 `WEBP`.
- SVG: decoded leading XML contains `<svg` before byte 512.

MIME mismatch:

- If provided MIME conflicts with detected content type, return HTTP `415`.
- Error code: `MIME_SIGNATURE_MISMATCH`.
- No derivative operation is created.

Decompression-bomb rejection:

- If decoded pixel count exceeds `40_000_000`, return HTTP `413`.
- Error code: `IMAGE_LIMIT_EXCEEDED`.
- A cleanup event is written only when a temporary key had already been
  created.
- Final immutable storage key is not written.

Safe derivative claim/write/finalize process:

1. Compute `canonical_request_hash` from tenant id, Webstore id, source asset
   id, slot, output format, dimensions, quality, crop mode, focal coordinates,
   transform spec hash, orientation normalization choice, and source SHA-256.
2. Atomically claim or retrieve `webstore_branding_derivative_operations` by
   tenant id, Webstore id, source asset id, slot, and canonical request hash.
3. If the same idempotency key is reused with a different canonical request
   hash, return HTTP `409 IDEMPOTENCY_KEY_REUSED`.
4. If existing operation is `completed`, replay its stored terminal response
   exactly. First successful derivative creation stores `201`; replay returns
   the stored `201`.
5. If existing operation is not terminal and another live lease owns it, return
   HTTP `202` with `operation_id`, `operation_step`, and `Retry-After`.
6. Claim or renew the operation lease with a unique owner token and finite
   expiration.
7. Update status to `writing_temp`.
8. Write processed bytes to an operation-specific temporary key:
   `branding/tmp/{tenant_id}/{webstore_id}/{operation_id}.{ext}`.
9. Update status to `bytes_written`.
10. Calculate `derivative_hash` from final derivative bytes and
    `transform_spec_hash` from canonical transform parameters.
11. Copy the temporary bytes to the immutable final key:
    `branding/{tenant_id}/{webstore_id}/{derivative_hash}/{transform_spec_hash}.{format}`.
    This repository storage service uses write/read behavior only, so the
    selected implementation is copy temp bytes to the final immutable key, then
    delete the operation temp key.
12. Update operation status to `metadata_finalizing`.
13. Insert or verify derivative metadata with generated opaque
    `public_asset_key`.
14. Delete only the temporary key owned by this operation.
15. Update operation status to `completed` and save terminal response.

Derivative HTTP outcomes:

- First successful derivative creation: `201`.
- Same operation replay after completion: stored `201` response replayed
  exactly.
- A separate request resolving to an already finalized identical derivative:
  `200`.
- Concurrent same-key request while processing: `202`.
- Same idempotency key with different payload: `409 IDEMPOTENCY_KEY_REUSED`.
- Unsupported source format, including AI/EPS without a supported preview:
  `415 UNSUPPORTED_SOURCE_FORMAT`.
- Invalid or malicious SVG: `422 UNSAFE_SVG`.
- MIME/signature mismatch: `415 MIME_SIGNATURE_MISMATCH`.
- Decompression bomb or decoded-pixel violation:
  `413 IMAGE_LIMIT_EXCEEDED`.

Cleanup safety:

- Cleanup deletes only `temporary_storage_key` for the same operation id.
- Cleanup never deletes `final_storage_key`.
- Cleanup never deletes a key referenced by a derivative metadata row.
- Losing duplicate operation does not own successful bytes and cannot delete
  successful bytes.

Orphan recovery:

- A scheduled or on-demand recovery reads derivative operations with status
  `claimed`, `writing_temp`, `bytes_written`, or `metadata_finalizing` whose
  lease expired.
- `claimed`: another worker may acquire the lease and either continue
  processing or mark failed when the source asset is no longer usable.
- `writing_temp`: if temp bytes do not exist, retry writes them; if temp bytes
  exist, continue to `bytes_written`.
- `bytes_written`: if final immutable bytes are absent, copy temp bytes to the
  final immutable key; if final bytes exist, verify hash and continue.
- `metadata_finalizing`: if derivative metadata is absent but final bytes exist,
  reconstruct metadata from operation fields and final byte headers; if metadata
  exists, verify exact logical match and complete.
- A worker that does not own the live lease receives HTTP `202`.
- Same operation key after terminal completion replays the stored terminal
  response exactly.
- A separate request resolving to the already finalized identical derivative
  returns HTTP `200`.
- Same key with a different payload returns `409 IDEMPOTENCY_KEY_REUSED`.
- Orphan temporary bytes may be deleted only when they belong to the operation
  temp key and no live lease owns the operation.
- Orphan final immutable bytes are never deleted by cleanup; recovery reconciles
  metadata or records a cleanup event requiring support review.
- Terminal responses can be reconstructed only from verified operation,
  derivative metadata, final hash, and public asset key; otherwise the operation
  remains recoverable or failed with a concrete failure code, never indefinite
  `202`.

Derivative recovery table:

| Operation step | Persisted records | Records absent | Operation status | Retry behavior | Exact HTTP result | Cleanup event | Records unchanged |
|---|---|---|---|---|---|---|---|
| `pending` | operation only | temp bytes, final bytes, metadata, terminal response | `pending` | acquire lease and continue to claim | `202` while leased, final terminal after owner completes | none | source asset, Webstore, draft, versions |
| `claimed` | operation with canonical transform fields | temp bytes, final bytes, metadata, terminal response | `processing` | lease takeover after expiration; recompute nothing except source availability check | `202` while leased, final terminal after owner completes | none | source asset bytes, draft, versions |
| `writing_temp` | operation and lease | final bytes, metadata, terminal response | `processing` | retry writes or verifies operation temp bytes | `202` while leased, final terminal after owner completes | cleanup event only if abandoned temp is deleted | source asset, final bytes |
| `bytes_written` | operation and temp bytes | metadata, terminal response | `processing` | copy temp bytes to final immutable key or verify existing final hash | `202` while leased, final terminal after owner completes | cleanup event if operation temp is deleted after final verification | source asset, final immutable object |
| `metadata_finalizing` | operation and final immutable bytes | terminal response when missing | `processing` | reconstruct or verify metadata, then store terminal response | `202` while leased, final terminal after owner completes | none for final object | source asset, final immutable object |
| `completed` | operation, final bytes, metadata, terminal response | none | `completed` | replay stored terminal response | stored `201` for same operation; `200` for separate identical derivative request | no cleanup | all records |
| `failed` | operation with failure code | terminal success | `failed` | replay stored terminal failure | stored failure status | cleanup event persisted when temp cleanup occurs | source asset, Webstore, drafts, versions |

`public_asset_key`:

- Generated opaque identifier mapped to one derivative row.
- Not derived from `derivative_hash`, transform hash, tenant id, Webstore id,
  source id, or storage key.
- Contains no storage path.
- Is unique in `webstore_branding_derivatives`.
- Is returned only by serializers that are allowed to reference a public-safe
  derivative.

PNG transparency behavior:

- Preserve alpha channel.
- Output color mode RGBA.
- Strip metadata.

Image transform order:

1. Verify source signature and MIME.
2. Decode safely within byte and pixel limits.
3. Normalize orientation from image metadata before crop.
4. Apply crop rectangle and focal-point rules against oriented dimensions.
5. Resize to slot-specific maximum dimensions.
6. Encode output.
7. Strip metadata.

Focal-point and crop calculations:

- Normalize orientation before measuring or cropping.
- `focal_point_x` and `focal_point_y` are required in the inclusive range
  `0.0` to `1.0`.
- Let `source_w` and `source_h` be the oriented source dimensions.
- Let `target_ratio = target_width / target_height`.
- Let `source_ratio = source_w / source_h`.
- If `source_ratio > target_ratio`, crop width is
  `floor(source_h * target_ratio)` and crop height is `source_h`.
- If `source_ratio < target_ratio`, crop width is `source_w` and crop height is
  `floor(source_w / target_ratio)`.
- If ratios are equal, crop width is `source_w` and crop height is `source_h`.
- Desired crop center is
  `round_half_up(focal_point_x * source_w)`,
  `round_half_up(focal_point_y * source_h)`.
- Crop left is desired center x minus half crop width, rounded with
  `round_half_up`, then clamped to `0` through `source_w - crop_width`.
- Crop top is desired center y minus half crop height, rounded with
  `round_half_up`, then clamped to `0` through `source_h - crop_height`.
- Persist `calculated_crop_left`, `calculated_crop_top`,
  `calculated_crop_width`, and `calculated_crop_height` on the derivative
  operation.
- Retry reuses the persisted calculated crop rectangle. It does not recalculate
  crop math from a request body.

JPEG background behavior:

- JPEG does not preserve transparency.
- Transparent pixels composite onto `#ffffff`.
- Output color mode RGB.
- Strip metadata.

WebP behavior:

- Preserve alpha when source contains alpha.
- Strip metadata.

SVG output dimensions:

SVG sanitation contract:

- Allowed elements: `svg`, `g`, `path`, `rect`, `circle`, `ellipse`, `line`,
  `polyline`, `polygon`, `text`, `tspan`, `defs`, `linearGradient`,
  `radialGradient`, `stop`, `clipPath`, `mask`, `title`, `desc`.
- Allowed attributes: `viewBox`, `width`, `height`, `x`, `y`, `x1`, `y1`,
  `x2`, `y2`, `cx`, `cy`, `r`, `rx`, `ry`, `d`, `points`, `transform`,
  `fill`, `stroke`, `stroke-width`, `stroke-linecap`, `stroke-linejoin`,
  `opacity`, `fill-opacity`, `stroke-opacity`, `font-family`, `font-size`,
  `font-weight`, `text-anchor`, `offset`, `stop-color`, `stop-opacity`,
  `clip-path`, `mask`, `id`, `role`, `aria-label`.
- Allowed URL/reference forms are internal fragment references only:
  `url(#local-id)` and `#local-id`.
- Forbidden elements: `script`, `foreignObject`, `iframe`, `object`, `embed`,
  `image`, `audio`, `video`, `canvas`, `style`, `link`, `meta`.
- Forbidden attributes: any attribute beginning with `on`, `href`,
  `xlink:href`, `src`, `style`, `data-*` carrying executable data, and any
  external URL.
- Script and event-handler presence rejects the SVG.
- External-resource references reject the SVG.
- Inline CSS is not accepted; presentation must use allowed attributes.
- Namespace handling allows only the SVG namespace and strips unsupported
  namespace declarations after validation.
- Require sanitized SVG to have a `viewBox`.
- If width/height are absent, derive dimensions from viewBox.
- If width/height exceed output limits, scale viewBox dimensions for metadata.
- Maximum SVG source bytes are `2_000_000`.
- Maximum element count is `10_000`.
- Maximum path command count is `100_000`.
- Persist `sanitizer_schema_version` on the derivative operation and metadata.
- Exact rejection code for invalid or malicious SVG is `422 UNSAFE_SVG`.
- Serve sanitized SVG with `Content-Type: image/svg+xml`.

Response headers:

- `Content-Type`: derivative metadata content type.
- `Content-Length`: derivative metadata content length.
- `ETag`: quoted derivative hash.
- `Cache-Control`: `public, max-age=31536000, immutable`.
- `X-Content-Type-Options`: `nosniff`.
- `Content-Security-Policy`: `default-src 'none'; img-src 'self'; style-src 'unsafe-inline'`.
- `Content-Disposition`: `inline`.

Retention and retirement:

- Source asset can be retired while derivatives remain.
- Derivative referenced by active version cannot be retired.
- Derivative referenced by historical version cannot be deleted.
- Retired derivative remains in metadata.
- Public route returns `404` for retired derivative.
- Source and derivative records are retained while referenced by any immutable
  version.

Public asset retrieval:

- Route verifies the opaque `public_asset_key` belongs to the requested
  Webstore.
- Route verifies the derivative is referenced by the active branding version.
- Route verifies the Webstore passes the existing public lifecycle gate.
- Route verifies derivative status is `available`, safe, not retired, and final
  immutable bytes exist.
- A guessed key from another Webstore, tenant, inactive version, draft,
  historical version, retired derivative, or unavailable derivative returns
  `404` without metadata.
- Public asset response streams bytes only; it does not return derivative
  metadata JSON, storage keys, tenant ids, source ids, margins, costs, or staff
  notes.

## 12. Stage 2 Import Intake

Import Intake route:

- `POST /webstores/{webstore_id}/branding/import-intake/preview`
- `POST /webstores/{webstore_id}/branding/import-intake/apply`

No editor-open side effects:

- `GET /webstores/{webstore_id}/branding/draft` creates no draft.
- `GET /webstores/{webstore_id}/branding/draft` creates no import candidates.
- `GET /webstores/{webstore_id}/branding/draft` mutates no setup files.
- `GET /webstores/{webstore_id}/branding/draft` mutates no questionnaire
  answers.

Allowed answer sources:

- `store_name`
- `description`
- `audience`
- `goals`
- `pickup_instructions`
- `event_start_at`
- `event_location`
- `notes`

Allowed setup file sources:

- active setup file with category `logo`
- active setup file with category `hero`
- active setup file with category `brand`
- active setup file with extension `png`
- active setup file with extension `jpg`
- active setup file with extension `jpeg`
- active setup file with extension `webp`
- active setup file with extension `svg`
- active setup file with extension `ai`
- active setup file with extension `eps`

Import candidate fields:

- `candidate_id`
- `tenant_id`
- `webstore_id`
- `draft_id`
- `draft_revision`
- `source_type`
- `source_collection`
- `source_id`
- `source_field`
- `source_file_id`
- `source_file_version`
- `source_value_hash`
- `target_field`
- `current_value`
- `candidate_value`
- `requires_derivative`
- `safe_to_apply`
- `blocked_reason_code`

Dry-run response fields:

- `webstore_id`
- `draft_id`
- `draft_revision`
- `candidate_id`
- `target_field`
- `current_value`
- `candidate_value`
- `source_type`
- `source_id`
- `source_field`
- `source_file_id`
- `source_file_version`
- `requires_derivative`
- `safe_to_apply`
- `blocked_reason_code`
- `dry_run = true`

Apply request fields:

- `draft_id`
- `draft_revision`
- `selected_candidate_ids`
- `confirm = true`
- `idempotency_key`

Apply CAS filter:

```python
{
  "tenant_id": tenant_id,
  "webstore_id": webstore_id,
  "id": draft_id,
  "draft_revision": draft_revision,
  "editable": True,
  "state": {"$in": ["draft", "changes_requested_by_owner", "changes_requested_by_staff"]}
}
```

Apply behavior:

- Empty `selected_candidate_ids` returns HTTP `400`.
- Unknown candidate id returns HTTP `400`.
- Stale draft revision returns HTTP `409`.
- If current field value differs from dry-run `current_value`, return HTTP
  `409` with `branding_import_stale_candidate`.
- Apply increments draft revision by 1.
- Apply writes only selected target fields to draft content.
- Apply does not mutate `webstores`.
- Apply does not mutate `webstore_questionnaire_submissions`.
- Apply does not mutate `webstore_setup_files`.
- Apply writes audit event `webstore.branding_intake_import_applied`.

Public derivative requirement:

- Imported setup artwork remains private source.
- It becomes public only after derivative generation, derivative selection,
  review snapshot creation, owner approval, staff approval, and activation.

## 13. Validation and Accessibility

Validation result persisted fields:

- `created_by_operation_id`
- `validation_schema_version`
- `field_schema_version`
- `validator_implementation_version`
- `draft_id`
- `validated_draft_revision`
- `validated_review_snapshot_id`
- `validated_snapshot_hash`
- `review_cycle`
- `review_snapshot_id`
- `snapshot_hash`
- `validated_at`
- `committed_to_draft_at`
- `superseded_at`
- `superseded_reason_code`
- `error_codes`
- `warning_codes`
- `field_errors`
- `field_warnings`
- `contrast_results`
- `accessibility_results`

Save-draft validation rejects:

- unknown field path
- invalid enum value
- invalid hex color
- invalid URL protocol
- invalid external HTTPS URL syntax
- invalid email
- invalid phone
- unsafe rich text
- invalid derivative reference
- unsupported Webstore type-specific field

Request-review validation rejects:

- validation result missing
- validation result draft revision mismatch
- validation result snapshot hash mismatch
- validation schema version mismatch
- validator implementation version below required version
- validation result has error codes
- validation result has accessibility blockers
- selected derivative missing
- selected derivative retired
- selected derivative unavailable

Request Owner Review validation source:

- Backend serializes the exact canonical draft content that will become the
  review snapshot.
- Validation result is persisted for that exact content, draft id, draft
  revision, review snapshot id, snapshot hash, validation schema version,
  field schema version, validator implementation version, timestamp, error
  codes, warning codes, and accessibility measurements.
- The review snapshot stores the same snapshot hash and validation result id.
- No later request may substitute a different validation result for the same
  approval or activation path.

Owner approval validation rejects:

- validation result missing
- validation result review snapshot id mismatch
- validation result snapshot hash mismatch
- validation result draft revision mismatch
- validation schema version mismatch
- validator implementation version below required version
- validation result has error codes
- validation result has accessibility blockers
- actor is not assigned Store Owner
- assignment status not `active`
- review cycle invalidated

Staff approval validation rejects:

- owner approval missing
- validation result missing
- validation result review snapshot id mismatch
- validation result snapshot hash mismatch
- validation result draft revision mismatch
- validation schema version mismatch
- validator implementation version below required version
- validation result has error codes
- validation result has accessibility blockers
- actor lacks `webstore:manage`
- review cycle invalidated

Activation validation rejects:

- draft state not `ready_for_activation`
- draft `editable` is false
- validation result missing
- validation result review snapshot id mismatch
- validation result snapshot hash mismatch
- validation result draft revision mismatch
- validation schema version mismatch
- validator implementation version below required version
- validation result has error codes
- validation result has accessibility blockers
- owner approval missing
- staff approval missing
- target version missing
- target version snapshot hash mismatch
- target version review snapshot id mismatch
- target version validation result id mismatch
- target version validation schema version mismatch
- target version validator implementation version mismatch
- target version validated draft revision mismatch
- expected active version mismatch
- selected derivative missing
- selected derivative retired
- selected derivative unavailable

WCAG rules:

- Normal text contrast minimum: `4.5:1`.
- Large text contrast minimum: `3:1`.
- Large text means `24px` normal weight or `18.66px` bold.
- System may suggest alternate colors.
- System must not silently overwrite colors.

Accessibility blockers:

- `alt_text_missing`
- `contrast_failed`
- `heading_hierarchy_invalid`
- `tap_target_too_small`
- `focus_state_missing`
- `keyboard_reorder_missing`

Allowed link protocols:

- `https`
- `mailto`
- `tel`

External HTTPS domains:

- Accepted when URL parser confirms scheme `https`, hostname is present, and
  URL length is `500` characters or fewer.

Rich-text tag allowlist:

- `p`
- `br`
- `strong`
- `em`
- `ul`
- `ol`
- `li`
- `a`

Rich-text attribute allowlist:

- `href`
- `rel`
- `target`

XSS handling:

- Unsafe rich text is rejected.
- Unsafe content is not silently stripped.
- Error code: `unsafe_rich_text`.

Blocking reason message mapping:

- `active_version_missing`: `No active branding version exists yet.`
- `draft_missing`: `No branding draft exists.`
- `review_snapshot_missing`: `Request Owner Review before approval.`
- `owner_approval_missing`: `Store Owner approval is required for this review snapshot.`
- `staff_approval_missing`: `Staff approval is required after Store Owner approval.`
- `approval_invalidated`: `Branding changed after approval; request review again.`
- `snapshot_hash_mismatch`: `The approval snapshot no longer matches this draft.`
- `stale_draft_revision`: `This draft changed. Reload before continuing.`
- `selected_derivative_missing`: `A selected image is missing.`
- `selected_derivative_retired`: `A selected image was retired and must be replaced.`
- `selected_derivative_unavailable`: `A selected image is not ready for public use.`
- `alt_text_missing`: `Add alt text for every visible image.`
- `contrast_failed`: `Color contrast does not meet accessibility requirements.`
- `heading_hierarchy_invalid`: `Heading order must be readable by assistive technology.`
- `tap_target_too_small`: `Interactive controls must be at least 44 by 44 CSS pixels.`
- `focus_state_missing`: `Interactive controls must have a visible focus state.`
- `keyboard_reorder_missing`: `Section reordering must be keyboard accessible.`
- `required_text_missing`: `Required visible text is missing.`
- `section_order_invalid`: `Section order must include each supported section once.`
- `unsafe_content`: `Remove unsafe content before review.`
- `ACTIVE_VERSION_CHANGED`: `Active branding changed. Reload before activating.`
- `BRANDING_ACTIVATION_IN_PROGRESS`: `Branding activation is already in progress.`
- `branding_draft_consumed`: `This draft was already activated and cannot be edited.`

## 14. Composite Readiness

Returned fields:

- `active_version_status`
- `working_draft_status`
- `asset_status`
- `accessibility_status`
- `validation_status`
- `approval_status`
- `activation_status`
- `blocking_reasons`
- `branding_stage_complete`
- `message`

Readiness calculations are independent. Active branding never short-circuits
validation, accessibility, asset, review, or approval blockers on a later
working draft. `blocking_reasons` includes every applicable current-draft
blocker.

| Returned field | Persisted inputs | Enum values | Calculation order and precedence | Blocking codes | User-facing messages |
|---|---|---|---|---|---|
| `active_version_status` | `webstores.active_branding_version_id`, `webstores.active_branding_snapshot_hash`, `webstore_branding_versions.id`, `webstore_branding_versions.snapshot_hash`, `webstore_branding_versions.review_snapshot_id`, `webstore_branding_versions.validation_result_id`, selected active-version derivative ids, `webstore_branding_derivatives.status`, `webstore_branding_derivatives.retired_at` | `none`, `active`, `active_asset_blocked`, `active_validation_blocked` | First calculate against the current immutable active version only. Missing active pointer yields `none`. Missing/retired/unavailable active derivative yields `active_asset_blocked`. Missing or mismatched active validation linkage yields `active_validation_blocked`. Otherwise `active`. | `active_version_missing`, `active_derivative_missing`, `active_derivative_retired`, `active_derivative_unavailable`, `active_validation_missing`, `active_validation_mismatch` | `No active branding version exists yet.`, `Active branding has an asset issue.`, `Active branding validation evidence is incomplete.`, `Active branding is in use.` |
| `working_draft_status` | editable draft by `tenant_id` and `webstore_id`, `webstore_branding_drafts.state`, `webstore_branding_drafts.editable`, `webstore_branding_drafts.consumed_at`, `webstore_branding_drafts.activation_lock_operation_id` | `none`, `draft`, `review_requested`, `changes_requested_by_owner`, `changes_requested_by_staff`, `owner_approved`, `staff_approved`, `ready_for_activation`, `activation_locked`, `consumed` | Calculate independently of active version. No editable draft yields `none`. Activation lock yields `activation_locked`. Consumed draft yields `consumed`. Otherwise mirror draft state. | `draft_missing`, `BRANDING_ACTIVATION_IN_PROGRESS`, `branding_draft_consumed` | `No branding draft exists.`, `Branding activation is already in progress.`, `This draft was already activated and cannot be edited.` |
| `asset_status` | current draft or active version visible derivative references, `selected_derivative_ids`, `content.sections.*_visible`, `webstore_branding_derivatives.id`, `webstore_branding_derivatives.tenant_id`, `webstore_branding_derivatives.webstore_id`, `webstore_branding_derivatives.status`, `webstore_branding_derivatives.retired_at` | `none_required`, `ready`, `blocked` | Check every visible derivative reference. No visible derivative references yields `none_required`. All same-tenant/Webstore available not-retired derivatives yields `ready`. Any missing, retired, unavailable, unsafe, or cross-Webstore derivative yields `blocked`. | `selected_derivative_missing`, `selected_derivative_retired`, `selected_derivative_unavailable` | `A selected image is missing.`, `A selected image was retired and must be replaced.`, `A selected image is not ready for public use.` |
| `accessibility_status` | matching validation result, `accessibility_results`, `error_codes`, `warning_codes`, `validator_implementation_version` | `not_checked`, `passed`, `blocked` | Missing matching validation result yields `not_checked`. Any accessibility blocker code yields `blocked`. Otherwise `passed`. | `alt_text_missing`, `contrast_failed`, `heading_hierarchy_invalid`, `tap_target_too_small`, `focus_state_missing`, `keyboard_reorder_missing` | messages from blocking reason mapping |
| `validation_status` | `webstore_branding_validation_results.validation_schema_version`, `field_schema_version`, `validator_implementation_version`, `validated_draft_revision`, `validated_review_snapshot_id`, `validated_snapshot_hash`, `error_codes` | `missing`, `stale`, `blocked`, `passed` | Missing result yields `missing`. Draft revision, snapshot, schema, or validator mismatch yields `stale`. Error codes yield `blocked`. Otherwise `passed`. | `validation_missing`, `stale_draft_revision`, `snapshot_hash_mismatch`, `validation_schema_mismatch`, `validator_version_mismatch`, `unsafe_content`, `section_order_invalid`, `required_text_missing` | `Run validation before review.`, `This draft changed. Reload before continuing.`, `The approval snapshot no longer matches this draft.` |
| `approval_status` | current review snapshot id/hash/cycle, owner approval, staff approval, approval invalidations | `none`, `owner_required`, `staff_required`, `both_valid`, `invalidated`, `stale` | Missing current review snapshot yields `none`. Invalidation for current snapshot yields `invalidated`. Approval rows for other revision/hash yield `stale`. Missing owner approval yields `owner_required`. Missing staff approval yields `staff_required`. Exact owner and staff approvals yield `both_valid`. | `review_snapshot_missing`, `owner_approval_missing`, `staff_approval_missing`, `approval_invalidated`, `snapshot_hash_mismatch` | messages from blocking reason mapping |
| `activation_status` | draft state, staff approval, immutable version for review snapshot, `activation_lock_operation_id`, active pointer expectation | `not_ready`, `ready`, `activating`, `blocked`, `active_version_changed` | Activation lock yields `activating`. Draft not `ready_for_activation` yields `not_ready`. Missing version or approval linkage yields `blocked`. Expected active mismatch yields `active_version_changed`. Otherwise `ready`. | `staff_approval_missing`, `target_version_missing`, `ACTIVE_VERSION_CHANGED`, `BRANDING_ACTIVATION_IN_PROGRESS` | `Staff approval is required after Store Owner approval.`, `Active branding changed. Reload before activating.`, `Branding activation is already in progress.` |
| `blocking_reasons` | all inputs above | array of reason codes | Collect every blocker from asset, accessibility, validation, approval, and activation checks before choosing primary display message. | every code listed in this table and in section 13 mapping | message map resolves each code |
| `branding_stage_complete` | active version id, active version review snapshot id, active version snapshot hash, active version validation result id, active version validation schema version, active version validator implementation version, active version validated draft revision, active selected derivatives | `true`, `false` | `true` only when active pointer references an immutable version whose selected derivatives are available/not retired and whose six validation linkage fields exactly match authoritative approval evidence. Public lifecycle status is ignored for this calculation. | active-version blocker codes above | `Branding stage is complete.`, `Branding stage is not complete.` |

Composite primary display precedence:

1. Calculate every subfield and collect every current-draft blocker.
2. If active-version status is blocked, primary message describes the active
   version blocker.
3. If current draft has blockers, primary message describes the first blocker
   by this order: validation, accessibility, asset, approval, activation.
4. If active branding exists and a later draft exists, add
   `Active branding remains in use; new branding changes are in progress.`
   as an additive display condition.
5. If no active branding and no draft exists, primary message is
   `No active branding version exists yet.`
6. If active branding exists and no draft blockers exist, primary message is
   `Active branding is in use.`

Public lifecycle eligibility does not determine whether the branding workflow is
complete. Catalog, checkout, Stripe, payment, launch, donation, fulfillment, and
public Webstore readiness are outside `branding_stage_complete`.

## 15. Staff, Owner, Manager, and Public User Experiences

Staff Webstore Detail:

- Branding appears as a Webstore Detail tab/panel.
- The panel includes editor sections, asset picker, import intake, preview,
  validation, approvals, activation, and history.
- Staff with `webstore:write` can edit draft, request Owner Review, generate
  derivatives, select derivatives, and view portal-safe history.
- Staff with `webstore:manage` can also request staff changes, staff approve,
  activate, restore as new draft, retire unused derivatives, download private
  sources, and view full audit.

Store Owner Portal:

- Branding editor appears below setup progress and before launch packet.
- Owner can edit permitted content, upload/select assets, request changes as
  Owner, and Owner Approve exact review snapshot.
- Owner cannot staff approve, activate, restore, reorder sections, or view full
  staff audit.

Store Manager Portal:

- Branding editor appears in same portal location.
- Manager can edit permitted content, upload/select assets, request Owner
  Review, and respond to requested changes by editing permitted draft fields.
- Manager cannot request changes as approver, Owner Approve, staff approve,
  activate, restore, reorder sections, or view full staff audit.

Public storefront:

- Public page renders only active branding version.
- Public page does not render draft.
- Public page does not render review snapshots.
- Public page does not render history.
- Public page does not render future catalog slot text without real catalog
  products.
- Public checkout remains disabled with honest messaging.

UI actions:

- `Import Intake`
- `Save Draft`
- `Preview`
- `Request Owner Review`
- `Request Changes`
- `Owner Approve`
- `Staff Approve`
- `Activate Branding`
- `Restore as New Draft`
- `View History`

Unsaved changes:

- Dirty editor disables approval and activation.
- Navigation away shows confirmation.
- Successful save refreshes `draft_revision`.

Stale revision:

- HTTP `409 stale_draft_revision` displays `This draft changed. Reload before continuing.`
- UI does not auto-merge changes.

Keyboard behavior:

- All controls are reachable by keyboard.
- Section reordering has Move Up and Move Down buttons.
- Escape closes modal/picker and returns focus.
- Focus ring is visible.

Preview:

- Desktop preview width: `1280`.
- Mobile preview width: `390`.
- Preview uses authenticated preview serializer.
- Preview never calls the public storefront route for drafts.

## 16. API Contract

Staff routes:

- `GET /webstores/{webstore_id}/branding/draft`
- `POST /webstores/{webstore_id}/branding/draft`
- `PATCH /webstores/{webstore_id}/branding/draft/{draft_id}`
- `POST /webstores/{webstore_id}/branding/import-intake/preview`
- `POST /webstores/{webstore_id}/branding/import-intake/apply`
- `POST /webstores/{webstore_id}/branding/assets`
- `GET /webstores/{webstore_id}/branding/assets`
- `GET /webstores/{webstore_id}/branding/assets/{asset_id}/download`
- `POST /webstores/{webstore_id}/branding/assets/{asset_id}/derivatives`
- `POST /webstores/{webstore_id}/branding/assets/{asset_id}/retire`
- `POST /webstores/{webstore_id}/branding/derivatives/{derivative_id}/retire`
- `GET /webstores/{webstore_id}/branding/preview`
- `POST /webstores/{webstore_id}/branding/request-owner-review`
- `POST /webstores/{webstore_id}/branding/request-changes`
- `POST /webstores/{webstore_id}/branding/staff-approve`
- `POST /webstores/{webstore_id}/branding/activate`
- `POST /webstores/{webstore_id}/branding/versions/{version_id}/restore`
- `GET /webstores/{webstore_id}/branding/history`
- `GET /webstores/{webstore_id}/branding/readiness`

Portal routes:

- `GET /portal/webstores/{webstore_id}/branding`
- `POST /portal/webstores/{webstore_id}/branding/draft`
- `PATCH /portal/webstores/{webstore_id}/branding/draft/{draft_id}`
- `POST /portal/webstores/{webstore_id}/branding/assets`
- `GET /portal/webstores/{webstore_id}/branding/assets`
- `GET /portal/webstores/{webstore_id}/branding/assets/{asset_id}/download`
- `POST /portal/webstores/{webstore_id}/branding/assets/{asset_id}/derivatives`
- `GET /portal/webstores/{webstore_id}/branding/preview`
- `POST /portal/webstores/{webstore_id}/branding/request-owner-review`
- `POST /portal/webstores/{webstore_id}/branding/request-changes`
- `POST /portal/webstores/{webstore_id}/branding/owner-approve`
- `GET /portal/webstores/{webstore_id}/branding/history`

Portal draft creation contract:

- Route: `POST /portal/webstores/{webstore_id}/branding/draft`.
- Auth: authenticated Store Owner or Store Manager portal identity.
- Assignment check: assignment must match tenant id, Webstore id, portal
  identity, role `store_owner` or `store_manager`, and status `active`.
- Revoked, expired, different-Webstore, different-tenant, or inactive
  assignments return `403` without exposing whether another Webstore exists.
- If no editable draft exists, create draft revision `1` with state `draft`,
  `editable = true`, `base_active_version_id` set to the current active
  branding version id or `null`, no review cycle, and no approval refs.
- If an editable draft already exists for the same tenant/Webstore, return
  `409 EXISTING_BRANDING_DRAFT` with the portal-safe draft serializer.
- Existing active branding version remains active and public while the draft is
  edited.
- Response status is `201` for creation and `409` for existing draft.
- Serializer is portal allowlist only; no tenant id, storage key, internal cost,
  margin, staff note, operation lease, or platform-only field is returned.
- Audit event: `webstore.branding_draft_created`.
- Cross-tenant and cross-Webstore attempts produce no draft, no review cycle, no
  approval, no version, and no audit event.

Public routes:

- `GET /public/webstores/{slug}`
- `GET /public/webstores/{slug}/assets/{public_asset_key}`

HTTP errors:

- `400` invalid request shape or rejected unsafe content.
- `403` permission denied.
- `404` tenant/Webstore/asset not found or public gate failed.
- `409` stale revision, invalid state transition, invalid approval sequence,
  activation conflict, active derivative retirement denial.
- `413` upload or decoded image too large.
- `415` unsupported source type or MIME/signature mismatch.
- `422` unsafe SVG or rejected branding content.

## 17. Backend Given/When/Then Tests

Backend test file:

`backend/tests/test_webstores_stage3_branding.py`

| Test name | Actor and authority | Starting records | Request | Exact status/result | Persisted writes | Records unchanged | Audit/idempotency result | Response fields absent |
|---|---|---|---|---|---|---|---|---|
| `test_create_draft_staff_write` | staff role with `webstore:write` | tenant Webstore, no draft | `POST /webstores/{id}/branding/draft` | `201`, state `draft` | one editable draft revision 1 | Webstore active pointer unchanged | audit `webstore.branding_draft_created` | `tenant_id`, `storage_key` |
| `test_create_draft_owner_assigned` | active owner assignment | tenant Webstore, no draft | `POST /portal/webstores/{id}/branding/draft` | `201`, state `draft` | one editable draft revision 1 | active pointer unchanged | audit `webstore.branding_draft_created` | `tenant_id`, `storage_key` |
| `test_create_draft_cross_tenant_denied` | staff from tenant B | tenant A Webstore | staff create draft | `404` | none | all tenant A records unchanged | no audit | `tenant_id`, `owner_id` |
| `test_create_draft_cross_webstore_denied_for_manager` | manager assigned to Webstore A | Webstore B exists | portal create draft for B | `403` | none | Webstore B unchanged | no audit | `tenant_id`, `storage_key` |
| `test_revoked_assignment_denied` | revoked owner assignment | Webstore exists | portal get branding | `403` | none | draft unchanged | no audit | `tenant_id`, `storage_key` |
| `test_save_edit_permitted_in_draft` | assigned manager | draft revision 1 | `PATCH` identity subtitle | `200`, revision 2 | draft updated | approvals unchanged | audit `webstore.branding_draft_saved` | `tenant_id`, `storage_key` |
| `test_save_edit_denied_in_review_requested` | staff write | draft state `review_requested` | `PATCH` content | `409` | none | draft revision unchanged | audit `webstore.branding_draft_edit_rejected_locked` | `tenant_id` |
| `test_consumed_draft_edit_denied` | staff manage | consumed draft editable false | `PATCH` content | `409` | none | consumed draft unchanged | audit `webstore.branding_draft_edit_rejected_consumed` | `tenant_id` |
| `test_request_owner_review_by_manager_allowed` | assigned manager | valid draft, validation passed | portal request owner review | `200`, state `review_requested` | review cycle and snapshot inserted | active pointer unchanged | audit `webstore.branding_owner_review_requested` | `tenant_id`, `storage_key` |
| `test_request_owner_review_validation_blocked` | staff write | draft with contrast blocker | staff request review | `409` | none | draft state unchanged | audit `webstore.branding_owner_review_rejected_validation` | `tenant_id` |
| `test_owner_requests_changes` | assigned owner | review requested | portal request changes | `200`, state `changes_requested_by_owner` | invalidation event | approvals unchanged | audit `webstore.branding_changes_requested_by_owner` | `tenant_id` |
| `test_material_edit_after_requested_changes_reopens_draft_once` | assigned owner | state `changes_requested_by_owner`, invalidation already written | save material edit | `200`, state `draft`, revision incremented | current review refs cleared | historical snapshot, approvals, comments, invalidation unchanged | no duplicate invalidation | `tenant_id` |
| `test_nonmaterial_save_after_requested_changes_does_not_reopen_review` | assigned manager | state `changes_requested_by_staff`, invalidation already written | save nonmaterial editor metadata | `200`, state `changes_requested_by_staff`, revision unchanged | only nonmaterial metadata changes | review refs and approvals unchanged | no duplicate invalidation | `tenant_id` |
| `test_manager_cannot_request_changes_as_approver` | assigned manager | review requested | portal request changes | `403` | none | review snapshot unchanged | no audit | `tenant_id` |
| `test_staff_requests_changes_after_owner_approval` | staff manage | owner approved | staff request changes | `200`, state `changes_requested_by_staff` | invalidation event | owner approval unchanged | audit `webstore.branding_changes_requested_by_staff` | `tenant_id` |
| `test_owner_approve_exact_snapshot` | assigned owner | review requested, validation snapshot matches | portal owner approve | `200`, state `owner_approved` | one owner approval | review snapshot unchanged | audit `webstore.branding_owner_approved` | `tenant_id` |
| `test_owner_approve_stale_validation_denied` | assigned owner | review snapshot hash differs from validation | portal owner approve | `409` | none | approvals unchanged | audit `webstore.branding_owner_approval_rejected` | `tenant_id` |
| `test_staff_approve_requires_owner_first` | staff manage | review requested no owner approval | staff approve | `409` | none | approvals unchanged | audit `webstore.branding_staff_approval_rejected` | `tenant_id` |
| `test_staff_approve_creates_version_and_ready_state` | staff manage | owner approved | staff approve | `200`, state `ready_for_activation` | staff approval and immutable version | owner approval unchanged | audit `webstore.branding_staff_approved`; audit `webstore.branding_version_created` | `storage_key` |
| `test_historical_approvals_immutable_after_reopened_edit` | staff write | owner approval then staff change request | edit reopened draft | `200` | invalidation event and new revision | owner approval unchanged | audit draft saved | `tenant_id` |
| `test_activation_success_consumes_draft` | staff manage | ready draft, version, approvals | activate | `200` | Webstore pointer fields, consumed draft, events, audit, operation `completed` | version content unchanged | idempotency terminal response | `storage_key` |
| `test_activation_same_key_same_payload_replays` | staff manage | successful operation | retry same request | `200` same response | none | all records unchanged | terminal response replay | `storage_key` |
| `test_activation_same_key_different_payload_rejected` | staff manage | operation exists | retry with different target | `409 IDEMPOTENCY_KEY_REUSED` | no pointer write | operation unchanged | audit idempotency mismatch | `storage_key` |
| `test_activation_pointer_cas_failure_conflicted` | staff manage | expected active stale | activate | `409 ACTIVE_VERSION_CHANGED` | operation `conflicted`, conflict event | active pointer unchanged | audit activation rejected | `storage_key` |
| `test_activation_pointer_success_operation_update_failure_recovers` | staff manage | simulated failure after pointer | retry same key | `200` | operation `completed`, draft consumed | pointer target unchanged | same operation owns pointer | `storage_key` |
| `test_activation_success_event_failure_recovers` | staff manage | simulated missing success event | retry | `200` | success event written | pointer unchanged | same operation id | `storage_key` |
| `test_activation_draft_consumption_failure_recovers` | staff manage | pointer set, draft still locked by operation | retry | `200` | draft consumed | pointer unchanged | same operation id | `storage_key` |
| `test_activation_audit_failure_recovers` | staff manage | pointer and draft consumed, audit missing | retry | `200` | audit written | pointer and draft unchanged | same operation id | `storage_key` |
| `test_activation_same_key_while_leased_returns_processing` | two staff manage actors | activation operation leased by first worker | same key and same payload during processing | `202` with `operation_id`, `operation_step`, `Retry-After` | none by second request | pointer and draft unchanged by second request | no duplicate audit | `storage_key` |
| `test_concurrent_activation_same_version` | two staff manage actors | one ready version | two different keys activate | first `200`, second `409 ACTIVE_VERSION_CHANGED` | one pointer write | version unchanged | one success op, one `conflicted` op | `storage_key` |
| `test_concurrent_activation_different_versions` | two staff manage actors | two ready versions from separate historical drafts and operations, same expected pointer | concurrent activate | one `200`, one `409 ACTIVE_VERSION_CHANGED` | one pointer write | losing version inactive | one success op, one `conflicted` op | `storage_key` |
| `test_activation_operation_create_failure` | staff manage | ready draft and version | simulated operation insert failure | `500 OPERATION_CREATE_FAILED` | none | pointer, draft, version unchanged | no audit | `storage_key` |
| `test_activation_expired_lease_takeover_recovers` | staff manage | expired activation lease at `draft_lock_acquired` | retry same key | `200` | pointer, success event, consumed draft, audit, terminal response | version content unchanged | lease transferred, one operation completed | `storage_key` |
| `test_activation_draft_lock_failure_exact_conflict` | staff manage | ready draft locked by another activation operation | activate | `409 BRANDING_DRAFT_LOCK_CONFLICT` | operation conflicted | pointer, draft content, version unchanged | rejection audit | `storage_key` |
| `test_activation_terminal_update_failure_replays_after_recovery` | staff manage | pointer, success event, consumed draft, audit exist without terminal response | retry same key | `200` | terminal response stored, operation completed | pointer, draft, version unchanged | no duplicate audit | `storage_key` |
| `test_activation_lost_response_replays` | staff manage | completed activation operation | retry same key | stored `200` | none | pointer, draft, version unchanged | terminal response replay | `storage_key` |
| `test_import_intake_preview_no_side_effects` | staff write | submitted questionnaire, setup files, draft | preview import | `200` dry run | none | Webstore, draft, answers, files unchanged | no audit | `storage_key`, `tenant_id` |
| `test_import_intake_apply_selected_fields_only` | staff write | dry-run candidates, draft revision 1 | apply two selected candidates | `200` | draft revision 2, selected fields | questionnaire and setup files unchanged | audit import applied | `storage_key` |
| `test_import_intake_stale_revision_denied` | staff write | draft revision changed after preview | apply old revision | `409` | none | draft unchanged | no mutation audit | `storage_key` |
| `test_unsafe_rich_text_rejected` | owner | draft | save `<script>` body | `400` | none | draft unchanged | audit rejection | `tenant_id` |
| `test_dangerous_url_rejected` | owner | draft | save `javascript:` URL | `400` | none | draft unchanged | audit rejection | `tenant_id` |
| `test_malicious_svg_rejected` | staff write | source upload | generate derivative | `422 UNSAFE_SVG` | failed operation | source unchanged | cleanup event persisted for owned temp key | `storage_key` |
| `test_mime_signature_mismatch_rejected` | staff write | fake PNG bytes | generate derivative | `415 MIME_SIGNATURE_MISMATCH` | failed operation | source unchanged, no derivative metadata | audit rejection | `storage_key` |
| `test_decompression_bomb_rejected` | staff write | large decoded image | generate derivative | `413 IMAGE_LIMIT_EXCEEDED` | failed operation and cleanup event | no derivative metadata | audit rejection | `storage_key` |
| `test_metadata_removed_from_derivative` | staff write | JPEG with EXIF | generate derivative | `201` | derivative without metadata | source unchanged | audit derivative created | `storage_key` |
| `test_derivative_initial_creation_returns_201` | staff write | supported PNG source | generate derivative | `201` | operation completed, derivative metadata, final immutable bytes | source asset unchanged | audit derivative created | `storage_key` |
| `test_derivative_completed_operation_replays_201` | staff write | completed derivative operation with stored `201` | retry same key | stored `201` | none | source, operation, derivative unchanged | terminal response replay | `storage_key` |
| `test_derivative_existing_identical_finalized_returns_200` | staff write | finalized identical derivative from different operation | generate same transform with new key | `200` | no duplicate derivative row | source and existing derivative unchanged | reuse audit | `storage_key` |
| `test_concurrent_derivative_generation_processing_response` | staff write and owner | same canonical request hash, first worker lease active | concurrent derivative generate | first request continues, second returns `202` with `operation_id`, `operation_step`, `Retry-After` | one operation row | source unchanged | no duplicate cleanup or audit | `storage_key` |
| `test_derivative_same_key_retry_after_completion` | staff write | completed derivative operation with stored `201` | retry same key and payload | stored `201` terminal replay | none | derivative and source unchanged | no duplicate cleanup or audit | `storage_key` |
| `test_derivative_same_key_different_payload_rejected` | staff write | operation exists | retry same key with different transform | `409 IDEMPOTENCY_KEY_REUSED` | none | operation, derivative, and source unchanged | audit idempotency mismatch | `storage_key` |
| `test_derivative_recovery_from_pending` | staff write | derivative operation at `pending` with expired lease | retry same key | `201` | final bytes, metadata, terminal response | source asset unchanged | no cleanup event | `storage_key` |
| `test_derivative_recovery_from_claimed` | staff write | derivative operation at `claimed` with expired lease | retry same key | `201` | temp bytes, final bytes, metadata, terminal response | source asset unchanged | no cleanup event | `storage_key` |
| `test_derivative_recovery_from_writing_temp` | staff write | derivative operation at `writing_temp` with expired lease | retry same key | `201` | temp bytes, final bytes, metadata, terminal response | source asset unchanged | cleanup event absent | `storage_key` |
| `test_derivative_recovery_from_bytes_written` | staff write | derivative operation at `bytes_written` with temp bytes | retry same key | `201` | final bytes, metadata, terminal response | source asset unchanged | cleanup event persisted for deleted temp key | `storage_key` |
| `test_derivative_recovery_from_metadata_finalizing` | staff write | derivative operation at `metadata_finalizing` with final bytes | retry same key | `201` | metadata and terminal response | final immutable object unchanged | cleanup event absent | `storage_key` |
| `test_derivative_recovery_from_failed` | staff write | derivative operation at `failed` with terminal failure | retry same key | stored terminal failure | none | source asset and Webstore unchanged | no duplicate cleanup event | `storage_key` |
| `test_derivative_crop_focal_orientation_persisted` | staff write | JPEG with orientation and focal point | generate derivative | `201` | normalized crop rectangle persisted | source asset unchanged | audit derivative created | `storage_key` |
| `test_derivative_unsupported_ai_eps_returns_415` | staff write | AI source without supported preview | generate derivative | `415 UNSUPPORTED_SOURCE_FORMAT` | failed operation | no derivative metadata | rejection audit | `storage_key` |
| `test_derivative_mime_signature_mismatch_returns_415` | staff write | fake PNG bytes | generate derivative | `415 MIME_SIGNATURE_MISMATCH` | failed operation | source unchanged, no derivative metadata | rejection audit | `storage_key` |
| `test_derivative_malicious_svg_returns_422` | staff write | SVG with script handler and owned temp key | generate derivative | `422 UNSAFE_SVG` | failed operation and cleanup event for owned temp key | source unchanged, no derivative metadata | rejection audit | `storage_key` |
| `test_derivative_svg_allowlist_acceptance` | staff write | safe SVG using allowed elements and attributes | generate derivative | `201` | sanitized derivative and sanitizer schema version | source unchanged | audit derivative created | `storage_key` |
| `test_derivative_final_object_reconciliation` | staff write | operation with final bytes and missing metadata | retry same key | `200` | metadata reconstructed, terminal response stored | final immutable object unchanged | no cleanup of final object | `storage_key` |
| `test_derivative_cleanup_recovery_temp_only` | staff write | operation temp written then failure | cleanup recovery | `200` cleanup completed | cleanup event | final derivative absent | audit cleanup | `final_storage_key` |
| `test_source_retirement_keeps_derivative` | staff manage | source with derivative | retire source | `200` | source retired | derivative retained | audit source retired | `storage_key` |
| `test_active_derivative_retirement_denied` | staff manage | active version references derivative | retire derivative | `409` | none | derivative unchanged | audit retirement denied | `storage_key` |
| `test_public_asset_key_guess_denied` | visitor | live Webstore active version | request guessed key | `404` | none | all records unchanged | no audit | all metadata fields |
| `test_public_lifecycle_denial` | visitor | status draft with active version | public storefront | `404` | none | all records unchanged | no audit | all branding fields |
| `test_staff_draft_serializer_exact_allowlist` | staff write | draft has private fields | get draft | `200` | none | all unchanged | no audit | staff draft forbidden fields |
| `test_staff_history_serializer_exact_allowlist` | staff manage | version history | get history | `200` | none | all unchanged | no audit | staff history forbidden fields |
| `test_owner_serializer_exact_allowlist` | owner | assigned store | portal branding get | `200` | none | all unchanged | no audit | owner forbidden fields |
| `test_manager_serializer_exact_allowlist` | manager | assigned store | portal branding get | `200` | none | all unchanged | no audit | manager forbidden fields |
| `test_preview_serializer_exact_allowlist` | staff write | draft preview | get preview | `200` | none | all unchanged | no audit | preview forbidden fields |
| `test_public_storefront_serializer_exact_allowlist` | visitor | live active store | get public storefront | `200` | none | all unchanged | no audit | public forbidden fields |
| `test_public_asset_response_has_no_json_metadata` | visitor | live active derivative | get asset | `200` bytes | none | all unchanged | no audit | all public asset forbidden fields |
| `test_all_six_webstore_types` | staff write | six Webstores | save type fields | `200` each | six drafts | active pointers unchanged | audit per save | wrong-type fields absent publicly |
| `test_accessibility_blocks_review_owner_staff_activation` | staff and owner | draft with blockers | request review, owner approve, staff approve, activate | each blocked operation returns `409` | no approvals, no activation | draft unchanged | rejection audits | `tenant_id` |
| `test_request_owner_review_operation_recovers_without_duplicate_snapshot` | staff write | valid draft, simulated response loss after snapshot insert | retry same key | `200` terminal replay | one review snapshot only | draft revision unchanged | one audit event | `storage_key` |
| `test_request_owner_review_operation_create_failure` | staff write | valid draft | simulated operation insert failure | `500 OPERATION_CREATE_FAILED` | none | draft, approvals, versions unchanged | no audit, no operation | `tenant_id`, `storage_key` |
| `test_request_owner_review_lease_acquisition_processing` | staff write | operation leased by worker | same key same payload | `202` with `operation_id`, `operation_step`, `Retry-After` | none by second request | draft, validation, snapshot unchanged by second request | existing lease retained | `tenant_id`, `storage_key` |
| `test_request_owner_review_validation_insert_failure_recovers` | staff write | operation at `content_validated` | retry same key | `200` | validation result, snapshot, draft review refs, audit, terminal response | draft content, approvals unchanged | one operation completed | `storage_key` |
| `test_request_owner_review_snapshot_insert_failure_recovers` | staff write | operation with uncommitted validation result | retry same key | `200` | one review snapshot, draft review refs, audit, terminal response | validation id reused, draft content unchanged | one operation completed | `storage_key` |
| `test_request_owner_review_draft_cas_failure_supersedes_uncommitted_records` | staff write | operation has uncommitted validation and snapshot, draft revision changed | retry same key | `409 DRAFT_REVISION_CHANGED` | validation and snapshot marked superseded | draft, approvals, versions unchanged | no review-began audit | `storage_key` |
| `test_request_owner_review_audit_failure_recovers` | staff write | draft references operation snapshot, audit missing | retry same key | `200` | audit and terminal response | validation, snapshot, draft content unchanged | one audit event | `storage_key` |
| `test_request_owner_review_terminal_update_failure_recovers` | staff write | draft review refs and audit exist, operation not terminal | retry same key | `200` | terminal response stored and operation completed | validation, snapshot, draft unchanged | no duplicate audit | `storage_key` |
| `test_request_owner_review_lost_response_replays` | staff write | completed request-owner-review operation | retry same key | stored `200` | none | all records unchanged | terminal response replay | `storage_key` |
| `test_request_owner_review_expired_lease_recovers` | staff write | expired operation lease at `review_snapshot_persisted` | retry same key | `200` | draft review refs, audit, terminal response | validation and snapshot ids reused | lease transferred, one operation completed | `storage_key` |
| `test_request_owner_review_same_key_different_payload_rejected` | staff write | operation exists | retry same key with changed draft revision | `409 IDEMPOTENCY_KEY_REUSED` | none | operation, draft, validation, snapshot unchanged | no audit | `storage_key` |
| `test_staff_approval_operation_recovers_from_staff_approved_state` | staff manage | owner approved, failure after staff approval insert | retry same key | `200`, state `ready_for_activation` | one staff approval, one version | owner approval unchanged | one audit set | `storage_key` |
| `test_staff_approval_each_boundary_recovers` | staff manage | owner approved and simulated failure after each write boundary | retry same key for each boundary case | `200` per boundary case | one staff approval, one version, draft ready | owner approval and review snapshot unchanged | same operation ids reused | `storage_key` |
| `test_staff_approval_concurrent_same_snapshot_loser_conflicted` | two staff manage actors | owner approved review snapshot | two different idempotency keys staff approve | winner `200`, loser `409 STAFF_APPROVAL_ALREADY_RECORDED` | one staff approval, one branding version, no loser `allocated_version_number` | winner operation unchanged | loser operation `conflicted` | `storage_key` |
| `test_staff_approval_unique_approval_conflict` | staff manage | approval row already exists for review snapshot | staff approve with different key | `409 STAFF_APPROVAL_ALREADY_RECORDED` | no second approval | existing approval, draft, version unchanged | conflict audit | `storage_key` |
| `test_staff_approval_unique_version_conflict` | staff manage | version already exists for review snapshot | staff approve with different key | `409 STAFF_APPROVAL_ALREADY_RECORDED` | no second version | existing version and approval unchanged | conflict audit | `storage_key` |
| `test_staff_approval_version_allocation_failure_reuses_number` | staff manage | allocated version number then failure before approval insert | retry same key | `200` | one staff approval and one version with allocated number | sequence not incremented by retry | no duplicate audit | `storage_key` |
| `test_staff_approval_lost_response_replays` | staff manage | completed staff-approve operation | retry same key | stored `200` | none | approvals, version, draft unchanged | terminal response replay | `storage_key` |
| `test_cleanup_event_persisted_when_temp_cleanup_occurs` | staff write | derivative operation with temp key only | cleanup recovery | `200` cleanup completed | cleanup event persisted | final immutable key absent | audit cleanup | `final_storage_key` |
| `test_active_branding_with_later_draft` | visitor | active version plus draft | public storefront | `200` active content | none | draft unchanged | no audit | draft fields absent |
| `test_visibility_field_permissions_exact` | staff, owner, manager | editable draft | attempt each `content.sections.*_visible` field | staff allowed per schema; owner and manager denied header, hero, catalog | only allowed fields persist | denied fields unchanged | denial audit for forbidden writes | `tenant_id`, `storage_key` |
| `test_readiness_independent_subfields` | staff write | draft with validation, asset, approval, and activation blockers | get readiness | all subfields and all `blocking_reasons` returned | none | all records unchanged | no audit | `tenant_id`, `storage_key` |
| `test_active_branding_with_blocked_later_draft_readiness` | staff write | active version exists and later draft has blockers | get readiness | active status shown and draft blockers listed | none | active pointer and draft unchanged | no audit | `tenant_id`, `storage_key` |
| `test_active_version_validation_linkage_exact` | staff manage | active version missing one validation linkage field | get readiness and activate | readiness blocked, activation `409 VALIDATION_SNAPSHOT_MISMATCH` | none | active version, draft, approvals unchanged | rejection audit for activation | `storage_key` |
| `test_future_catalog_slot_omitted_publicly` | visitor | active version has catalog slot text, no real products | public storefront | `200` | none | version unchanged | no audit | `catalog_slot_title`, `catalog_slot_message` |

## 18. Frontend Given/When/Then Tests

Frontend test file:

`frontend/src/__tests__/WebstoresStage3Branding.test.jsx`

| Test name | Actor and authority | Starting UI/API state | UI action | Exact UI result | Persisted writes | Records unchanged | Audit/idempotency result | Response fields absent |
|---|---|---|---|---|---|---|---|---|
| `renders_staff_branding_tab` | staff write | Webstore detail API includes draft | open `/webstores/:id` | Branding panel visible | none | all records unchanged | no audit | `storage_key`, `tenant_id` |
| `renders_allowed_ribbon_actions` | staff manage | Webstore detail route | view ribbon | nine allowed action labels visible | none | all records unchanged | no audit | n/a |
| `does_not_render_disallowed_manager_approval_actions` | assigned manager | portal branding response | open owner portal | request review visible; approve/activate hidden | none | all records unchanged | no audit | `tenant_id`, `storage_key` |
| `owner_can_approve_exact_snapshot` | assigned owner | portal response state `review_requested` | click Owner Approve | success toast and state `owner_approved` | owner approval API called once | draft content unchanged | audit expected by API | `storage_key` |
| `unsaved_changes_disable_approval_and_activation` | staff manage | ready draft loaded | edit field | approval and activation buttons disabled | none until save | server records unchanged | no audit | n/a |
| `stale_revision_error_shows_reload` | staff write | API returns `409 stale_draft_revision` | save draft | reload banner visible | none | records unchanged | no audit | n/a |
| `keyboard_reordering_works` | staff manage | section order loaded | tab to Move Down and press Enter | order changes locally then saves | draft revision increments after save | active version unchanged | audit save | n/a |
| `desktop_mobile_preview_toggle` | staff write | preview data available | click mobile preview | preview width uses mobile class | none | records unchanged | no audit | `tenant_id`, `storage_key` |
| `asset_picker_hides_storage_keys` | staff write | asset API includes public-safe summary | open picker | no storage key text in DOM | none | records unchanged | no audit | `storage_key` |
| `validation_errors_render_per_field` | owner | validation errors returned | view editor | field error next to field | none | records unchanged | no audit | n/a |
| `public_page_uses_active_branding` | visitor | public API returns active branding | open public page | active hero displayed | none | records unchanged | no audit | draft fields |
| `future_catalog_slot_not_public` | visitor | public API omits catalog slot | open public page | no placeholder catalog slot | none | records unchanged | no audit | `catalog_slot_title`, `catalog_slot_message` |
| `public_asset_guess_error_has_no_metadata` | visitor | asset API returns 404 | request guessed asset | generic unavailable state | none | records unchanged | no audit | all asset metadata |

## 19. Regression Commands

Backend Stage 3 focused:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_webstores_stage3_branding.py -q
```

Backend Stage 2 focused:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_webstores_stage2_setup.py -q
```

Backend Stage 1, Stage 2, and EC14 Webstores:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_webstores_stage2_setup.py backend/tests/test_webstores_stage1_foundation.py backend/tests/test_ec14_webstores.py -q
```

Portal, permissions, numbering, and reporting regressions:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_ec6_portal_docs.py backend/tests/test_ec6_portal_payment.py backend/tests/test_ec8c_employee_portal.py backend/tests/test_permissions_scope.py backend/tests/test_ec2_permissions.py backend/tests/test_record_numbering_checkpoint.py backend/tests/test_report_builder_complete_system.py -q
```

Frontend Webstores:

```powershell
cd frontend
npm.cmd test -- --runTestsByPath src/__tests__/WebstoresStage1.test.jsx src/__tests__/WebstoresStage3Branding.test.jsx --watchAll=false
```

Frontend production build:

```powershell
cd frontend
npm.cmd run build
```

Backend compile/import:

```powershell
backend\.venv\Scripts\python.exe -m compileall backend/app
```

Whitespace:

```powershell
git diff --check
```

## 20. End-to-End Acceptance Criteria

Acceptance criteria:

- Staff with `webstore:write` can create a branding draft.
- Assigned Store Manager can create a branding draft for assigned Webstore.
- Assigned Store Manager can request Owner Review.
- Assigned Store Manager cannot request changes as approver.
- Assigned Store Manager cannot Owner Approve.
- Assigned Store Manager cannot staff approve.
- Assigned Store Manager cannot activate.
- Assigned Store Owner can review the exact immutable snapshot.
- Assigned Store Owner approval is tied to `review_snapshot_id`,
  `snapshot_hash`, and `draft_revision`.
- Staff approval requires valid Owner approval first.
- Staff approval creates a distinct immutable version and sets draft state to
  `ready_for_activation`.
- Authorized staff activates branding.
- Activation writes `active_branding_version_id`,
  `active_branding_snapshot_hash`, `branding_activation_operation_id`,
  `branding_activated_at`, and `branding_activated_by_user_id`.
- Activation consumes the draft with `editable = false`.
- New draft creation becomes possible after draft consumption.
- Existing active branding remains public while later draft edits occur.
- Public routes expose only active approved branding for a Webstore with
  `status = "live"`.
- Private source files never become public.
- Public derivative route requires active version reference and public route
  gate.
- Failure and retry boundaries do not corrupt Webstore pointer, draft,
  approvals, versions, assets, audit history, operation records, or idempotency
  records.
- Stage 1 purchase-intent and verified-payment foundation tests still pass.
- Stage 2 setup and owner-intake tests still pass.
- No catalog implementation is added.
- No checkout implementation is added.
- No Stripe implementation is added.
- No donation implementation is added.
- No launch-packet approval replacement is added.
- No AI implementation is added.

## 21. Exact File Inventory

Existing files that must change:

- `backend/app/models/webstore.py`: add Stage 3 branding models and Webstore
  active pointer fields.
- `backend/app/core/db.py`: add Stage 3 indexes.
- `backend/app/services/webstores.py`: update public/portal serializers and
  public storefront active branding resolution.
- `backend/app/services/webstore_setup.py`: add branding import-candidate and
  draft-only import application helpers.
- `backend/app/routers/webstores.py`: add staff branding routes.
- `backend/app/routers/webstore_owner_portal.py`: add Store Owner and Store
  Manager branding routes.
- `backend/app/routers/public_webstores.py`: add public asset route and active
  branding storefront response integration.
- `backend/app/services/storage.py`: add deterministic branding storage-key
  helper and content-type preserving retrieval helper for derivatives.
- `frontend/src/lib/webstores.js`: add branding API wrappers.
- `frontend/src/lib/navigation.js`: add Webstore Detail contextual ribbon
  command definitions for Stage 3 actions.
- `frontend/src/pages/WebstoreDetailPage.jsx`: add staff Branding workspace.
- `frontend/src/pages/WebstoreOwnerPortalPage.jsx`: add owner/manager Branding
  workspace.
- `frontend/src/pages/PublicWebstorePage.jsx`: render active branding
  storefront presentation.

Existing files that must remain unchanged:

- `frontend/src/components/app-shell/AppShell.jsx`: shell already renders
  contextual ribbon; Stage 3 must not add Webstore business logic here.
- `backend/app/services/webstore_payments.py`: verified-payment processing is
  out of Stage 3 scope.
- `backend/app/repositories/webstores.py`: generic repository helper remains
  unchanged; activation uses direct CAS service logic.
- `backend/app/core/permissions.py`: existing `webstore:*` and portal
  permissions are sufficient for Stage 3.
- `backend/app/services/audit.py`: existing audit helper remains sufficient.

New files:

- `backend/app/services/webstore_branding.py`: draft lifecycle, review cycles,
  review snapshots, approvals, invalidations, immutable versions, activation,
  readiness, staff/portal/public serializers, and audit orchestration.
- `backend/app/services/webstore_branding_assets.py`: private source asset
  registration, derivative claim/write/finalize processing, public asset gate,
  cleanup recovery, retention, and retirement.
- `backend/tests/test_webstores_stage3_branding.py`: backend Stage 3 contract
  tests listed in section 17.
- `frontend/src/components/webstores/WebstoreBrandingEditor.jsx`: staff and
  portal editor panels using the canonical schema fields.
- `frontend/src/components/webstores/WebstoreBrandingPreview.jsx`:
  authenticated desktop/mobile preview rendering.
- `frontend/src/components/webstores/WebstoreBrandingAssetPicker.jsx`: private
  source summary, derivative generation, derivative selection, and storage-key
  hiding.
- `frontend/src/components/webstores/WebstoreBrandingHistory.jsx`: full staff
  history and portal-safe history rendering.
- `frontend/src/__tests__/WebstoresStage3Branding.test.jsx`: frontend Stage 3
  UI tests listed in section 18.
- `evidence/WEBSTORES_STAGE3_BRANDING_STOREFRONT_EVIDENCE.md`: evidence file
  to be written during implementation verification, not during this contract
  task.

Tracking files to update during implementation, not during this contract task:

- `preflight/EC14_WEBSTORES_PREFLIGHT_AND_IMPLEMENTATION_PLAN.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/PRD.md`
- `memory/checkpoint_reference_table.md`
- `memory/progress_register.md`

Protected Banner calculator files that must remain unchanged:

- `backend/app/services/pricing_flat_sqft.py`
- `backend/app/services/pricing_snapshot.py`
- `backend/app/services/starter_defaults.py`
- `backend/tests/test_banner_pricing_owner_decisions.py`
- `frontend/src/components/commerce/LineItemDialog.jsx`
- `frontend/src/components/pricing/CategorySpecificFields.jsx`
- `frontend/src/pages/PricingCalculatorPage.jsx`

## 22. Compatibility, Migration, and Risks

Compatibility:

- Existing loose `Webstore.branding` remains stored.
- Existing loose `Webstore.branding` is never serialized publicly as Stage 3
  branding authority.
- New draft creation may initialize fields from existing Webstore name,
  description, store type, setup profile, and legacy branding after validation.
- Existing public slug behavior remains.
- Existing public purchase-intent behavior remains.
- Existing setup files remain private.
- Existing launch packet approval remains separate.

Migration:

- No bulk migration runs in Stage 3.
- Existing Webstores without active branding show `active_version_status =
  "none"`.
- Staff may create a new draft from existing Webstore fields.
- Activation creates the first immutable active version.

Risks:

- Image processing library availability must be confirmed during
  implementation.
- SVG sanitization must be strict enough for public serving.
- Public storefront currently exposes product `webstore_id`; Stage 3 must not
  expand public internal identifiers.
- Activation recovery must be tested with simulated failures at every defined
  boundary.
- Frontend state management must prevent stale draft results and unsaved
  approval actions.

## 23. Explicitly Deferred Work

Deferred work:

- Stage 4 catalog improvements.
- Stripe Checkout.
- Stripe Connect payout.
- Donation collection.
- Fundraiser accounting goals.
- Event scheduling authority.
- Employee eligibility enforcement.
- Pickup appointment scheduling.
- Production deadline authority.
- Launch-packet replacement.
- AI-generated branding.
- AI-generated copy.
- Webstore real checkout.
- Webstore public account login.
- EC4 customer invoice/payment changes.
- EC9 pricing changes.
- Banner calculator changes.
