# EC17 Studio AI Tools Runtime Contracts

**Status:** IMPLEMENTED - CI PENDING
**Checkpoint:** EC17 Studio AI Tools, Prompt Library, Generated Assets, and AI Activity
**Primary route:** `/api/ai-studio`

## Boundaries

EC17 implements tenant-facing Studio AI tool catalog, Prompt Library, Generated Assets, editable draft/history storage, AI Activity, contextual launch links, and proposal boundaries for pricing/import workflows.

All executable Studio runs route through EC16 action requests, context packets, prompt versions, usage ledger, provider-cost ledger, credit ledger, governance, idempotency, permissions, and tenant isolation. EC17 does not call external providers.

H7 remains active. Tenant UI displays `AI credits apply` and usage bands only; no final numeric credit prices are shown. The EC17 local/mock platform bootstrap uses EC16 capabilities with a non-commercial local mock provider, zero provider cost, and no secrets.

EC17 does not implement EC18 assistant/chat/action parser/voice/memory, Meta integrations, BYOK, MCP, EC19 onboarding/help, Stripe, Checkout, subscriptions, webhooks, EC4 invoice/payment mutation, EC13 catalog mutation, EC14 payout mutation, EC15 asset replacement, email sending, social publishing, campaign scheduling, Webstore publishing, pricing mutation, proof/artwork approval, production packet approval, refund, or autonomous assistant actions.

## Active Families

- Design & Image Studio
- Marketing & Brand Studio
- Business Writing & Documents
- Pricing & Profitability

AI Image Generator is featured in the Studio UI. Tools expose modes; selecting a mode changes the displayed fields and warnings.

## Approved Capability Identifiers

Active EC17 identifiers:

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
- `studio.text.marketing_content`
- `studio.text.completed_job_post`
- `studio.text.social_pack`
- `studio.text.content_calendar`
- `studio.text.campaign_plan`
- `studio.text.copy_writer`
- `studio.text.brand_kit`
- `studio.text.idea_brainstorm`
- `studio.text.review_reply`
- `studio.text.email_draft`
- `studio.text.document_draft`
- `studio.text.proposal_draft`
- `studio.research.permit_guidance`
- `pricing.advisory`
- `pricing.insights`
- `pricing.historical_invoice_analysis`
- `wrap_lab.cost_guidance`
- `pricing.setup_suggestions`
- `webstore.product_description`

Inactive in EC17:

- EC18-only: `assistant.email_draft`, `assistant.chat`, `assistant.action_parse`, `assistant.voice_transcription`, `assistant.voice_reply`, `assistant.intent_classify`, `assistant.navigation_classify`, `assistant.memory_compress`.
- Removed: `order.service_prefill`, `studio.text.bulk_followup`.
- Future Meta only: `integration.facebook.message_classify`, `integration.facebook.order_extract`.

## Backend Collections

- `ai_studio_prompt_entries`
- `ai_generated_assets`
- `ai_studio_editable_drafts`
- `ai_studio_brand_contexts`
- `ai_studio_pricing_import_analyses`
- `ai_studio_pricing_setup_proposals`

Generated assets and editable drafts link to EC16 `ai_action_requests`, `ai_context_packets`, `ai_prompt_versions`, usage rows, provider-cost rows, and credit ledger entries.

## Storage Rules

Normally saved as Generated Assets:

- generated images;
- image edits;
- mockups;
- logo concepts;
- wrap concepts;
- motorsports graphics;
- saved brand-kit documents;
- saved campaign plans;
- saved document drafts;
- saved proposal drafts;
- saved artwork analysis reports.

Normally saved as editable drafts/history first:

- email drafts;
- review replies;
- product descriptions;
- short marketing text;
- pricing recommendations.

Email drafts are never sent by EC17. Review replies and product descriptions remain editable and are not published or applied automatically.

## Special Tool Contracts

- Completed-job marketing records customer/publicity permission state when supplied, warns when unknown or missing, produces primary caption, alternate caption, image alt text, hashtags, call to action, posting suggestions, and editable platform versions, and never publishes.
- Historical Pricing Import Analysis accepts PDF, CSV, XLSX, and XLS metadata, preserves the source-file reference, validates type/size, returns deterministic mock extracted values, mappings, duplicate signals, confidence, and warnings, and does not apply imports.
- Permit Guidance collects jurisdiction/state/city/address/sign/project details and returns checklists and warnings. It does not perform external research, invent current permit rules, give legal advice, or guarantee approval.
- Document Writer includes General Business Document, Proposal, Scope of Work, Standard Operating Procedure, Job Description, Policy or Instructions, Customer Letter, Customer or Order Document, and Contract Draft. Contract Drafts carry a legal-review warning.
- Email Draft Assistant includes Quote Follow-up, Payment Reminder, Thank-you Email, Overdue Invoice Email, Job Update, Job-Complete Email, Proof/Approval Request, and Custom Email. Outputs are editable drafts only.
- Brand Kit suggestions can become approved reusable tenant/customer brand context only through explicit approval. Existing logos and brand data are preserved.
- Image Edit Fill records source image, mask/region, fill instruction, preserve-area instructions, optional reference image, output dimensions, revision/source relationships, and a source-preservation flag.

## Permissions

Every executable tool requires `ai_tool:use` and active `ai_studio` entitlement. EC16 then enforces capability entitlement, credit, governance, and idempotency checks.

Linked-module permissions:

- Email drafts: `email:send` plus linked record read permission when context is supplied.
- Webstore product content/mockups: `webstore:manage`.
- Wrap contexts: `wrap_lab:write`.
- Pricing setup and setup proposals: `pricing:write`.
- Pricing advice, insights, historical import analysis, and wrap cost guidance: `pricing:read`.
- Artwork analysis: `document:read`.
- Generated asset save/archive: `document:write`.
- Generated asset reads: `document:read`.
- Activity: `ai_history:read`.
- Prompt reads/writes: `ai_prompt:read` / `ai_prompt:write`.

Backend checks are authoritative. Portal tokens are rejected by the staff-route auth dependency. Every context record is tenant-validated by collection and `tenant_id`.

## Frontend Surfaces

- `/studio`
- `/studio/design-image`
- `/studio/marketing-brand`
- `/studio/writing-documents`
- `/studio/pricing-profitability`
- `/studio/prompts`
- `/studio/assets`
- `/studio/activity`

Contextual launch links are available from Customer, Quote, Order, Invoice, Webstore, and Wrap Lab detail pages. Links preload visible context through query parameters only; backend permission and tenant checks still control execution.

## Indexes

EC17 indexes cover prompt lookup/version lifecycle, generated asset lookup by tenant/tool/mode/status/action/prompt/context/source/revision/parent/idempotency, editable draft lookup and idempotency, brand context ownership/approval, historical import analysis status/source/type, and pricing setup proposal status/creator.

## Tests

Targeted tests cover approved and inactive capability identifiers, no tenant-facing numeric credit charge in catalog, platform-only bootstrap, portal rejection, entitlement and credit-gated local execution, generated asset storage, editable draft behavior, EC16 action/usage/cost linkage, tenant isolation, social publicity warnings and alt text, prompt publication immutability, activity hidden fields, complete email/document mode inventories, permit warnings and fields, and historical import safe boundaries.
