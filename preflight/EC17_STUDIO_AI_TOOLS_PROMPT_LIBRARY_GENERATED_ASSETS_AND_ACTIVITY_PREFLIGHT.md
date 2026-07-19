# EC17 Studio AI Tools, Prompt Library, Generated Assets, and AI Activity Preflight

**Status:** PREFLIGHT COMPLETE - READY TO BUILD
**Date:** 2026-07-19
**Branch:** `CODEX-ec17-branch`
**Starting HEAD:** `e67351f90015428653e662f2bde4e7c05652e997`
**Upstream:** `origin/CODEX-ec17-branch`
**Remote parity:** `origin/main` and `origin/CODEX-ec17-branch` both at `e67351f90015428653e662f2bde4e7c05652e997`
**EC16 closure ancestor:** `8bd064e658d1bfd50afab05dc2abf5d3c9e44ae0` present in history before EC17 work
**Working tree at preflight start:** clean

## 1. Authority

The owner authorized EC17 implementation on `CODEX-ec17-branch` after the EC17 owner-decision worksheet was accepted. The subsequent authoritative add-on controls wherever it is more specific.

Controlling inputs:

- `specs_pack/extracted/EC17_Studio_AI_Tools_OWNER_REVIEW_REQUIRED.docx`
- Owner EC17 implementation authorization prompt
- Owner EC17 authoritative add-on dated 2026-07-19
- EC16 shared AI gateway contracts and evidence
- EC13 entitlement/commercial boundaries, EC14 Webstore contracts, EC15 Wrap Lab contracts, and EC10 template/document contracts

## 2. Holds and Boundaries

Resolved for EC17:

- H4 is closed for EC17 Studio AI Tools only.
- H5/H8 are closed for EC17 because the owner supplied the final Keep/Combine/Change/Rename/Defer/Remove tool decisions.

Still active:

- H7 remains active. EC17 may use deterministic local/mock generation through EC16 contracts, but may not activate live commercial AI, final numeric AI-credit pricing, production provider/model assignments, external AI provider calls, BYOK, MCP, realtime voice, Meta integrations, unsupported credentials, or secrets.
- EC18 remains not started. Business Assistant, action parser, assistant memory, assistant email, realtime voice, intent/navigation classification, and assistant chat are not EC17 tools.
- EC19 and later checkpoints remain not started.

Explicit EC17 exclusions:

- No external provider calls.
- No Stripe, Checkout Session, subscription, billing portal, webhook, trial, setup-package, AI-credit-pack, EC4 invoice/payment, Webstore payout, or EC15 asset-replacement mutation.
- No autonomous email sending, social publishing, campaign scheduling, Webstore publishing, pricing mutation, record-status mutation, proof/artwork approval, production packet approval, refund, or assistant action execution.
- No final numeric AI-credit prices in tenant UI.

## 3. Approved Active Capability Identifiers

EC17 must use these stable capability identifiers unless an existing EC16 registry already contains an equivalent canonical identifier.

Design and image:

- `studio.image.sign_mockup`
- `studio.image.banner_concept`
- `studio.image.logo_concepts`
- `studio.image.logo_refresh`
- `studio.image.mockup`
- `studio.image.wrap_mockup`
- `studio.image.custom_concept`
- `studio.image.edit_fill`
- `studio.image.motorsports_graphics`
- `studio.image.photo_cleanup`
- `studio.artwork.vector_guidance`
- `studio.artwork.font_finder`

Marketing and branding:

- `studio.text.marketing_content`
- `studio.text.completed_job_post`
- `studio.text.social_pack`
- `studio.text.content_calendar`
- `studio.text.campaign_plan`
- `studio.text.copy_writer`
- `studio.text.brand_kit`
- `studio.text.idea_brainstorm`
- `studio.text.review_reply`

Business writing and documents:

- `studio.text.email_draft`
- `studio.text.document_draft`
- `studio.text.proposal_draft`
- `studio.research.permit_guidance`

Pricing and embedded tools:

- `pricing.advisory`
- `pricing.insights`
- `pricing.historical_invoice_analysis`
- `wrap_lab.cost_guidance`
- `pricing.setup_suggestions`
- `webstore.product_description`

Documented but inactive in EC17:

- EC18-only: `assistant.email_draft`, `assistant.chat`, `assistant.action_parse`, `assistant.voice_transcription`, `assistant.voice_reply`, `assistant.intent_classify`, `assistant.navigation_classify`, `assistant.memory_compress`.
- Removed by owner: `order.service_prefill`, `studio.text.bulk_followup`.
- Future Meta integration only: `integration.facebook.message_classify`, `integration.facebook.order_extract`.

## 4. Final Tool Families

EC17 uses four primary tenant-facing areas:

- Design & Image Studio
- Marketing & Brand Studio
- Business Writing & Documents
- Pricing & Profitability

AI Image Generator must be visually prominent. Individual tools may contain modes, and the UI must show only fields relevant to the selected mode.

## 5. Credit Display

Tenant UI displays `AI credits apply` plus configurable non-commercial usage bands. No final numeric credit charge is shown.

Usage-band metadata:

- Light: short rewrite, small text transformation, brief reply, or simple idea list.
- Standard: normal text generation such as an email, product description, review reply, or social caption.
- Heavy: long-form, context-heavy, document, campaign, multi-platform, historical analysis, or multiple-output generation.
- Premium: image generation, image editing, vision/OCR, file analysis, or other provider-expensive work.

The band definitions belong in catalog metadata, not scattered frontend conditionals.

## 6. Tool Contract Highlights

- Generated images, image edits, mockups, logo concepts, wrap concepts, motorsports graphics, saved brand-kit documents, saved campaign plans, saved document drafts, saved proposal drafts, and saved artwork analysis reports normally save as Generated Assets.
- Email drafts, review replies, product descriptions, short marketing text, and pricing recommendations normally save first as editable drafts/history; they become Generated Assets, documents, templates, or content assets only through an explicit save action.
- Completed-job marketing must show customer/publicity permission state when available, warn when unknown or missing, and never claim customer approval or alter authorization records.
- Social outputs support primary caption, alternate caption, image alt text, hashtags, calls to action, posting suggestions, and editable platform-specific versions.
- Historical Pricing Import Analysis accepts PDF, CSV, Excel, and canonical import formats; preserves the source file; validates type/size; produces structured proposed values, confidence, warnings, duplicate signals, and field mappings; and does not apply imports until a future canonical pricing workflow authorizes it.
- Permit Guidance accepts jurisdiction, state, city, address, sign/project details, zoning/property information supplied by the user, and linked context; it produces checklists and draft descriptions, never current permit-rule claims, legal advice, or approval guarantees.
- Document Writer supports General Business Document, Proposal, Scope of Work, Standard Operating Procedure, Job Description, Policy or Instructions, Customer Letter, Customer or Order Document, and Contract Draft. Contract Drafts require a visible legal-review warning.
- Email Draft Assistant supports Quote Follow-up, Payment Reminder, Thank-you Email, Overdue Invoice Email, Job Update, Job-Complete Email, Proof/Approval Request where permitted, and Custom Email. It never sends or records an email as sent.
- Brand Kit outputs may become reusable brand context only with explicit confirmation. Existing logos/brand data are preserved.
- Image Edit Fill records original source image, selected region or mask, instruction, preserve-area instructions, optional reference image, output aspect/dimensions, and revision relationships. Source images are always preserved.

## 7. Permissions and Tenant Isolation

Every executable EC17 tool requires `ai_tool:use` plus linked-module permissions:

- Email drafts: email write plus relevant Customer, Quote, Order, or Invoice read permission.
- Webstore product content and product mockups: `webstore:manage`.
- Wrap concepts and wrap cost guidance: `wrap_lab:manage`.
- Pricing setup changes: `pricing:write`.
- Pricing advice and insights: `pricing:read`.
- Artwork analysis: authorized document/file read permission.
- Saved generated assets or documents: `document:write`.
- Order-linked marketing: `order:read`.

Use canonical repository permission names when the worksheet wording differs. Do not create duplicate synonymous permissions. Backend validation is authoritative. Portal tokens remain rejected by staff routes. Every referenced business record must be tenant-validated.

## 8. EC16 Gateway Boundary

EC17 tool runs must route through the EC16 gateway, action request, context packet, prompt-version, usage ledger, provider-cost ledger, credit ledger, governance, budget, idempotency, and tenant-isolation contracts.

EC17 may bootstrap deterministic local/mock capability metadata for the approved capability identifiers while H7 is active. This bootstrap must not call external providers, use secrets, expose provider/model/token language to tenant users, or activate live commercial AI.

## 9. Required Indexes

EC17 must add indexes for tool catalog lookup, tenant prompt lookup and version lifecycle, generated-asset lookup and revision relationships, AI activity filtering, contextual launch references, historical pricing import-analysis proposals, pricing setup proposals, reusable brand-context approval records if implemented, and idempotency keys.

## 10. Required Tests

Targeted EC17 tests must verify approved and inactive capability identifiers, permissions, tenant isolation, portal-token rejection, generated-asset versus editable-draft behavior, EC16 linkage, customer-publicity warnings, social alt text, historical PDF/CSV/Excel import boundaries, permit verification/source boundaries, complete email/document modes, Contract Draft legal warning, usage-band metadata, reusable brand-context boundary, source-image preservation, and absence of external provider, Meta, OCR, permit-research, AI image, Stripe, checkout, webhook, send, publish, pricing mutation, or record mutation.

## 11. Expected Files

Documentation and tracking:

- `preflight/EC17_STUDIO_AI_TOOLS_PROMPT_LIBRARY_GENERATED_ASSETS_AND_ACTIVITY_PREFLIGHT.md`
- `docs/modules/ec17_studio_ai_tools.md`
- `evidence/EC17_IMPLEMENTATION_COMPLETION_REPORT.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/checkpoint_reference_table.md`
- `memory/owner_specification_hold_register.md`
- `memory/progress_register.md`

Backend:

- `backend/app/models/ai_studio.py`
- `backend/app/repositories/ai_studio.py`
- `backend/app/services/ai_studio.py`
- `backend/app/routers/ai_studio.py`
- `backend/app/core/db.py`
- `backend/server.py`
- `backend/tests/test_ec17_ai_studio_catalog.py`
- `backend/tests/test_ec17_generated_assets.py`
- `backend/tests/test_ec17_prompt_library_activity.py`

Frontend:

- `frontend/src/lib/aiStudio.js`
- `frontend/src/pages/AIStudioPage.jsx`
- `frontend/src/pages/GeneratedAssetsPage.jsx`
- `frontend/src/pages/PromptLibraryPage.jsx`
- `frontend/src/pages/AIActivityPage.jsx`
- `frontend/src/components/ai/AIContextualActions.jsx`
- `frontend/src/__tests__/AIStudioPage.test.jsx`
- `frontend/src/App.js`
- `frontend/src/lib/navigation.js`

## 12. Preflight Result

EC17 is authorized, owner tool decisions are recorded, H5/H8 are resolved for EC17, and H7 remains active. This preflight step is documentation and tracking only. No EC17 implementation occurred before this preflight.
