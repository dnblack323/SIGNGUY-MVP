# SIGNGUY MVP — Tools & Resources Feature Audit

**Repository:** `dnblack323/SIGNGUY-MVP`  
**Audited branch:** `main`  
**Code baseline:** `66c0c49fb6450268ad784c7a5e291257442b3c20`  
**Audit date:** August 16, 2026  
**Scope:** Tools & Resources, including Studio, Business Assistant, voice, Design & Image, Marketing & Brand, Writing & Documents, Pricing & Profitability, Prompt Library, Generated Assets, AI Activity, AI credits/governance, the hidden shared document Library, and the hidden Pricing Calculators workspace.

This is a repository-level feature audit. A capability is credited only when current code contains a usable interface, working backend behavior, or a clearly wired integration. A large catalog entry is not treated as a working AI feature when the runtime only returns local mock data.

## Rating and AI legend

| Score | Classification | Meaning |
|---:|---|---|
| 5 | Standout / advanced | Deep, production-shaped workflow with strong safeguards, history, permissions, and useful end-to-end integration. |
| 4 | Advanced | Substantial and valuable workflow with meaningful edge-case handling; a few completeness or polish gaps remain. |
| 3 | Solid | Real, useful functionality, but the experience is narrower, partially manual, or missing important surfaces. |
| 2 | Basic | Limited or awkward workflow with major omissions or backend-only pieces. |
| 1 | Foundation only | Models, services, or an isolated route exist, but normal users cannot complete the intended workflow. |
| 0 | Placeholder / absent | Mentioned, reserved, or implied but not implemented as a usable feature. |

**AI labels**

- **No:** deterministic workflow; AI is not involved or required.
- **Optional:** the core workflow works without AI and AI is a separate assistance action.
- **Required:** a live AI provider is necessary for the feature to deliver its intended result.
- **Planned / inactive:** the interface and AI contract exist, but the present runtime does not call a live model.
- **Conditional:** live AI works only when the corresponding provider is configured and enabled.

## Executive scorecard

| Final category | Usable app score | Backend depth | AI | Summary |
|---|---:|---:|---|---|
| Studio Overview | **2/5 — Basic** | 4/5 | Planned / inactive | Useful catalog launcher and family navigation, but it presents local mock tools as draft creators and does not clearly separate demo output from live AI. |
| Business Assistant | **4/5 — Advanced safeguards; 3/5 answer breadth** | 5/5 | Mixed | Source-linked deterministic text answers, reviewable action proposals, memory, routines, insights, and conditional live OpenAI voice. |
| Design & Image | **1/5 — Foundation only** | 4/5 | Planned / inactive | Six tools and eighteen modes are modeled, but current runs create text/JSON mock records—not images, edits, vectors, fonts, logos, or mockups. |
| Marketing & Brand | **2/5 — Basic** | 4/5 | Planned / inactive | Six tools and nineteen modes create reviewable local drafts with good safety boundaries; no live model, publishing, scheduling, or visible approved-brand workflow. |
| Writing & Documents | **2/5 — Basic** | 4/5 | Planned / inactive | Nineteen modes cover email and document types, but current outputs are local mock text records rather than polished editable/exportable documents. |
| Pricing & Profitability Studio | **1/5 — Foundation only** | 4/5 | Planned / inactive | Five advisory modes exist, but analysis/import/setup outputs are mocks and cannot change canonical pricing. |
| Prompt Library | **2/5 — Basic UI / advanced model** | 4/5 | No to manage; AI when consumed | Published prompt versioning and immutability exist, but the UI only creates and publishes a hard-coded Content Writer prompt. |
| Generated Assets | **2/5 — Basic index** | 4/5 | No to manage | Tenant-safe list and backend detail/archive exist; the page offers no preview, open, edit, accept, download, reuse, or archive actions. |
| AI Activity | **2/5 — Basic** | 4/5 | No | Shows tool, mode, result type, usage band, and context; omits time, actor, status, credits charged, provider/model, duration, failures, and details. |
| Shared Document Library | **3/5 — Solid but hidden** | 4/5 | No | Authenticated upload/search/download/archive and visibility control exist at `/documents`, but no Tools & Resources navigation item exposes it. |
| Pricing Calculators | **5/5 — Standout but hidden** | 5/5 | No | Nine category calculators, authoritative pricing, comparisons, cost/profit evidence, method setup, and saved calculations exist at `/pricing-calculator` but are absent from this section’s menu. |
| AI Credits | **4/5 — Advanced supporting control** | 5/5 | No | Tenant balances, reservations, commits/releases, ledger, alerts, and gateway history are real; the run screen still hides exact pre-run and post-run charges. |
| AI Governance | **3/5 — Solid visibility** | 5/5 | No | Provider/model, request, usage, policy, cost-cap, and alert infrastructure is deep; the present page is mostly read-only visibility. |

### Overall assessment

Tools & Resources has an unusually strong **AI governance and safety foundation**, a genuinely advanced **Business Assistant action boundary**, and a standout **non-AI Pricing Calculator**. However, the visible Studio catalog is far ahead of the runtime. Its 17 tools and 61 modes currently run through local contract providers with `external_provider_calls: 0`. Design modes do not generate images. Writing and marketing modes do not call a language model. Historical pricing import does not parse the supplied file.

The section therefore has two different maturity levels:

- **Architecture maturity: high.** Tenant isolation, permissions, entitlements, immutable prompts, idempotency, credit reservation/commit/release, usage ledgers, cost ledgers, budget policies, audit events, context validation, safety warnings, and human confirmation are thoughtfully designed.
- **End-user output maturity: low-to-moderate.** Most Studio results are local mock text/JSON, important management actions are backend-only, and the strongest ordinary tools are hidden from navigation.

The product should not market the current Design & Image area as real image generation or editing. The most valuable next release is to connect approved provider adapters, expose exact credit charges, add review/save/export workflows, and place Library and Calculators in the actual Tools & Resources navigation.

## Current navigation versus the intended tools workspace

### Current Tools & Resources navigation

1. Studio
2. Business Assistant
3. Design & Image
4. Marketing & Brand
5. Writing & Documents
6. Pricing & Profitability
7. Prompt Library
8. Generated Assets
9. AI Activity

All nine routes are registered. The four family routes reuse the same `AIStudioPage` and select a family from the URL. This reuse is reasonable, but the pages are filtered catalog views rather than independently developed workspaces.

### Important routed tools missing from the section

- **Library** at `/documents`.
- **Pricing Calculators** at `/pricing-calculator`.
- **AI Credits** at `/settings/ai-credits`.
- **AI Governance** at `/settings/ai-governance` for platform AI administrators.

AI Credits and Governance reasonably belong in Control Center. Library and Pricing Calculators should be visible Tools & Resources destinations.

## 1. Studio Overview

**Rating: 2/5 — Basic**  
**Backend depth: 4/5**  
**AI: Planned / inactive for current Studio runs**

### Implemented features

- Four tool-family cards:
  - Design & Image Studio
  - Marketing & Brand Studio
  - Business Writing & Documents
  - Pricing & Profitability
- Tool selector and mode selector.
- Featured AI Image Generator card.
- Dynamic input rendering for text, long text, number, selection, and file-reference contracts.
- Required-field enforcement.
- URL-driven tool, mode, record context, and publicity-permission context.
- Usage-band display: light, standard, heavy, premium.
- “AI credits apply” disclosure.
- Tool/mode warnings and operational boundaries.
- Create Draft action.
- Result type, usage band, warnings, and boundary display.
- Quick links to Prompt Library, Generated Assets, and AI Activity.
- Permission gate through `ai_tool:use`.

### Important limitations

- The page does not show the exact credit charge before execution.
- It does not show the exact committed charge or remaining balance afterward.
- It labels the action **Create Draft** even when the mode is supposed to produce an image or analysis.
- Results are shown in a read-only text area.
- No visible edit, accept, reject, save-to-canonical-record, open-in-document, download, export, duplicate, revise, or regenerate workflow.
- File-reference fields are modeled in the catalog, but the generic page does not provide a real file picker/uploader for them.
- There is no prominent global banner stating that the entire Studio runtime is local mock/test output.
- The featured image card says modes are ready for “local mock generation,” but this distinction is easy to miss.

### Runtime truth

The Studio service explicitly states that no external provider calls are made. It bootstraps:

- Provider: `ec17_local_mock`
- Model: `ec17_local_contract_model`
- Prompt version: `ec17-local-1`
- Generated provenance: `h7_local_mock: true`
- External provider calls: `0`

Successful mock runs are nevertheless metered through the credit gateway using the capability’s default charge. That is technically consistent with the gateway contract but should not be a customer-billable behavior without an explicit “test credit” policy.

## 2. Business Assistant

**Rating: 4/5 for safeguards and action design; 3/5 for current answer breadth**  
**Backend depth: 5/5**  
**AI: Mixed — text answers are deterministic; voice is conditional live AI**

### 2.1 Workspace and global access

- Dedicated full-page workspace at `/studio/assistant`.
- Compact assistant launcher in the persistent workspace dock.
- Permission gate through `ai_assistant:use`.
- Five modes:
  - Owner
  - Operations
  - Finance
  - Production
  - Workforce
- Current record-context display.
- Text input and conversation history.
- Source badges linking directly to canonical app records.
- AI-credit disclosure.
- Prompt Library and Studio cross-links.

**Rating: 4/5 — Advanced**  
The combination of global launcher and focused workspace makes the assistant available without forcing users to leave their current workflow.

### 2.2 Tenant-record context

Supported context types:

- Customer
- Quote
- Order
- Invoice
- Work Order
- Webstore
- Wrap Project
- Employee
- Task

For each supported record, the backend:

- Applies the record-specific read permission.
- Resolves only within the current tenant.
- Stores a context snapshot.
- Records the source route and source update time.
- Uses source timestamps to detect stale proposals before execution.

**Rating: 5/5 — Standout context safety**  
**AI: No for validation; optional input to assistant workflows**

### 2.3 Current text intelligence

The present text assistant is **not an open-ended language-model chat**. It uses deterministic phrase matching and database queries for these supported questions:

- Latest invoice.
- Open/unpaid/overdue invoices and total balance basis.
- Invoice-basis revenue for the last seven days.
- Tasks due today.
- Next scheduled vehicle drop-off or installation.
- Jobs behind schedule, using overdue tasks as the safest available signal.
- Quotes that may need follow-up.
- Margin/profit/losing-money questions using issued invoices and pricing snapshots while explicitly identifying missing actual costs.
- Production blockers/late jobs from recent Work Orders.
- Workers scheduled today.
- A selected record-context acknowledgement and follow-up prompt.

Each supported answer can include:

- Canonical source type and ID.
- Direct application route.
- Calculation basis.
- Date range.
- Source update time.
- Missing-data disclosures.

**Rating: 3/5 — Solid**  
**AI: No in the current text runtime**

This is reliable for the supported questions and safer than pretending to know unavailable facts. It is still narrow: arbitrary summaries, natural follow-up reasoning, cross-record synthesis, conversational reference resolution, and general shop questions fall back to a canned capability list.

### 2.4 Quick actions

Permission-filtered quick actions include:

- Latest invoice.
- Overdue invoices.
- Money this week.
- Quote follow-ups.
- Production blockers.
- Workers today.
- Draft customer email.
- Completed wrap post delegation to Studio.

**Rating: 3/5 — Solid**  
**AI: Mixed; deterministic queries and reviewable draft/delegation actions**

### 2.5 Reviewable action proposals

Supported proposal types:

- Email draft.
- Document draft.
- Navigation suggestion.
- Bulk email drafts.
- Internal task.
- Internal note.
- Report draft.
- AI Studio delegation.

Proposal lifecycle:

- Proposed.
- Edited in backend contract.
- Confirmed.
- Canceled.
- Expired.
- Executing.
- Succeeded.
- Failed.
- Stale.
- Unsupported.

Safety behavior:

- A proposal cannot execute before confirmation.
- Execution is idempotent.
- Source records are rechecked for staleness.
- Required permissions are checked again.
- Unsupported actions fail closed.
- Email and bulk-email actions create drafts only; no email is sent.
- Document/report actions create editable drafts only; nothing is exported, printed, emailed, or published.
- Studio delegation opens an existing Studio tool and does not auto-generate an asset.
- Internal task and internal note are the two action types that can make real canonical writes after confirmation.

**Rating: 5/5 — Standout action boundary**  
**AI: Optional for proposal creation; execution is deterministic**

### Proposal UI gap

The backend supports editing a proposal, but the current proposal card only displays JSON and offers Confirm, Execute, and Cancel. Users cannot edit the payload in the visible interface before confirmation. This keeps the rating below a complete 5-level end-user experience even though the service boundary is excellent.

### 2.6 Memory

- Save a personal preference/note.
- List retained memory.
- Delete memory.
- Tenant and user scoping.
- Secret/credential rejection.
- Audited save and delete actions.

**Rating: 3/5 — Solid**  
**AI: No for storage; future assistant use**

Gaps: free-form keys are generated from timestamps in the current UI; there is no category, source, expiration, edit, review queue, or visible explanation of when memory affects answers.

### 2.7 Routines

- Create a named routine from a prompt.
- Select assistant mode.
- List routines.
- Rename.
- Enable.
- Pause.
- Delete/archive.
- Store next-run and lifecycle fields in the backend model.
- `generated_proposal_only` safety contract.

**Rating: 2/5 — Basic**  
**AI: Planned / inactive for autonomous execution**

The interface resembles automation management, but the repository evidence verifies CRUD and proposal-only safety—not a background scheduler that actually runs routines and delivers results.

### 2.8 Proactive insights

- Generate and list insights.
- Current implemented insight: count of open, non-paid invoices.
- Source citation to the Invoice list.
- Deduplication by tenant/date.
- Dismiss action.

**Rating: 2/5 — Basic**  
**AI: No**

The framework is good, but one deterministic insight is not yet a broad proactive intelligence system.

### 2.9 Voice assistant

- OpenAI Realtime architecture using WebRTC.
- Backend-created ephemeral client secret; the platform API key is never returned to the browser.
- OpenAI Safety Identifier header.
- Configurable Realtime model and voice.
- Browser microphone capture.
- Server VAD or push-to-talk.
- Live user transcription.
- Live assistant audio and transcript.
- Listening, thinking, speaking, interruption, reconnecting, denied, unavailable, and error states.
- Interrupt response.
- Retry/reconnect path.
- Text fallback.
- Voice function call limited to `propose_assistant_action`.
- Voice-created proposal still requires visible user confirmation.
- Session rate limiting.
- Positive-credit check before activation.
- Per-provider-event usage metering with idempotency.
- Input/output audio-second tracking.
- Raw audio is not stored.
- Safe “OpenAI Voice is not configured” state.

**Rating: 4/5 — Advanced when configured**  
**AI: Required and conditional**

This is the only current end-user Tools & Resources feature with a real external AI-provider path. It is inactive when the OpenAI API key or Realtime feature flag is missing. Repository tests validate the secret boundary and WebRTC event flow with mocks; they do not prove a production account is currently configured.

## 3. Design & Image

**Category rating: 1/5 — Foundation only**  
**Backend/catalog depth: 4/5**  
**AI: Planned / inactive; a live image/vision provider is required for intended results**

The catalog is thoughtfully structured, but every current mode returns local text/JSON mock content. No bitmap, vector, layered design, mask edit, font match, or production file is generated.

### 3.1 AI Image Generator — 1/5

- General Text-to-Image.
- Custom Image Concept.
- Premium usage band.
- Prompt and optional context notes.
- Saves a generated-asset record.

**Current result:** text concept metadata, not an image.

### 3.2 Mockup Generator — 1/5

- Sign Mockup.
- Banner Mockup.
- Product Mockup.
- Webstore context warning.
- Never auto-publishes.

**Current result:** local mock concept record, not a rendered mockup.

### 3.3 Logo Lab — 1/5

- New Logo Concepts.
- Refresh Existing Logo.
- Source-image reference contract.
- Original-preservation rule.
- Trademark/production-ready disclaimer.

**Current result:** no logo image or vector is produced.

### 3.4 Vehicle Graphics Studio — 1/5

- Vehicle Wrap Concept.
- Race Number Design.
- Driver Name Plate.
- Team Branding.
- Concept/not-production-ready warning.

**Current result:** no vehicle template placement, measured wrap layout, print panel, or rendered vehicle preview.

### 3.5 Photo Editor — 1/5

- Enhance Photo.
- Edit/Replace Area.
- Add or Remove Object.
- Background Change.
- Source image reference.
- Mask/selected-region description.
- Preserve-area instructions.
- Reference-image field.
- Output aspect/dimension field.
- Original-preservation boundary.

**Current result:** the service explicitly warns that no real image edit occurred.

### 3.6 Artwork Assistant — 1/5

- Artwork Check.
- Vector Preparation Guidance.
- Font Finder.
- Document-read permission requirement.
- Advisory-only and uncertainty warnings.

**Current result:** no real file analysis, DPI check, bleed check, color-space inspection, vector conversion, font detection, or production approval.

### Design & Image features absent

- Real text-to-image generation.
- Real image-to-image editing.
- Image upload picker in the generic Studio form.
- Mask drawing/selection interface.
- Visual preview canvas.
- Before/after comparison.
- Resolution/aspect presets.
- Transparent-background output.
- Vector output.
- Sign dimensions, scale, bleed, safe area, or cut path.
- Vehicle make/model/year templates.
- Production-file validation.
- Download/export.
- Version comparison.
- Accept/reject/revise workflow.

## 4. Marketing & Brand

**Category rating: 2/5 — Basic**  
**Backend/catalog depth: 4/5**  
**AI: Planned / inactive; intended draft generation requires AI**

### 4.1 Social Post Builder — 2/5

- Quick Project Post.
- Completed-Work Showcase.
- Multi-Platform Post Pack.
- Platform-list input.
- Facebook and Instagram draft structures in local mock output.
- Required customer/publicity permission state: confirmed, unknown, or missing.
- Additional warning when authorization is unknown or missing.
- No direct publishing or scheduling.

The publicity gate is excellent product judgment. The content itself is currently formulaic local mock text.

### 4.2 Content Writer — 1/5

- Business Copy.
- Website or Advertising Copy.
- Blog and SEO Content.
- Standard/heavy usage classification.
- Editable-draft storage.

Missing: live generation, tone controls, audience, length, keywords, SEO scoring, variants, rewrite tools, citations, and export.

### 4.3 Campaign Planner — 2/5

- Campaign Ideas.
- Campaign Plan.
- Content Calendar.
- Proposed-plan warning.
- No external campaign creation or scheduling.

The planned outputs are useful, but the current generated record is local placeholder content and the calendar is not an interactive schedule.

### 4.4 Brand Kit Builder — 2/5

- Brand Ideas.
- Tagline Generator.
- Color Palette.
- Brand Voice.
- Suggestion-only boundary until approved.

Advanced backend brand-context fields exist for:

- Logo file IDs.
- Colors.
- Typography.
- Brand voice.
- Audience.
- Business description.
- Values.
- Taglines.
- Preferred wording.
- Prohibited wording.
- Suggested, approved, and archived lifecycle.

The router can create and approve brand context, but no current Studio page exposes that approval workflow. This prevents the brand kit from becoming reusable authoritative context.

### 4.5 Product Content Builder — 2/5

- Product Name Suggestions.
- Product Description Draft.
- Webstore Product Content.
- Editable-draft boundary.
- Never changes price, availability, order, or payment.
- Requires confirmation before applying text.
- Never auto-publishes.

Missing: visible product picker, product-field preview, before/after diff, apply-to-product action, SEO metadata, image alt text, bulk products, and live AI.

### 4.6 Review Reply Assistant — 2/5

- Positive Review Reply.
- Negative Review Reply.
- Neutral or Custom Reply.
- Human-review requirement.
- Negative-response guardrail against invented promises, refunds, admissions, or legal statements.

Missing: review-source integration, customer/review picker, sentiment context, multiple variants, apply/copy action, and direct response workflow.

## 5. Writing & Documents

**Category rating: 2/5 — Basic**  
**Backend/catalog depth: 4/5**  
**AI: Planned / inactive; intended writing generation requires AI**

### 5.1 Email Draft Assistant — 2/5

Modes:

- Quote Follow-up.
- Payment Reminder.
- Thank-you Email.
- Overdue Invoice Email.
- Project Update.
- Project-Complete Email.
- Proof/Approval Request.
- Custom Email.

Safeguards:

- Requires email-send permission even though it creates drafts only.
- Never sends automatically.
- Payment reminder never changes payment status.
- Results are editable-draft records in the backend.

Missing: recipient/entity picker, subject/body fields, visible editable composer, attachment selection, send handoff, copy action, tone/length controls, and conversation history.

### 5.2 Proposal Builder — 2/5

- Proposal mode.
- Template-read permission.
- Heavy usage band.
- Generated-asset storage.
- Editable-draft/preview-before-reuse warning.

Missing: proposal sections, line items, pricing, terms, customer merge fields, template selection, rich editing, approval/signature, PDF export, and live generation.

### 5.3 Document Writer — 2/5

Modes:

- General Business Document.
- Proposal.
- Scope of Work.
- Standard Operating Procedure.
- Project Description.
- Policy or Instructions.
- Customer Letter.
- Customer or Order Document.
- Contract Draft.

Safeguards:

- Contract output is draft-only.
- Legal review is required.
- No claim of legal sufficiency.
- Template-read permission.

Missing: rich-text editor, template selection, merge fields, sections, page layout, headers/footers, branding, comments, approval, signatures, revision history, PDF/DOCX export, and save-to-Documents action.

### 5.4 Permit Guidance — 1/5

- Permit Checklist mode.
- Jurisdiction.
- State.
- City/municipality.
- Project address.
- Sign type.
- Sign dimensions.
- Illumination.
- Mounting method.
- User prompt.
- Informational-only and local-authority-verification warnings.
- No legal advice or approval guarantee.

The input contract is strong, but there is no live research provider, municipal-code lookup, cited source retrieval, current-law verification, permit-form connection, or authoritative checklist. A local mock is not sufficient for jurisdictional guidance.

## 6. Pricing & Profitability Studio

**Category rating: 1/5 — Foundation only**  
**Backend/catalog depth: 4/5**  
**AI: Planned / inactive**

### 6.1 Pricing Advisor — 1/5

- Standard advisory draft.
- Pricing-read permission.
- Explicitly cannot modify Quote, Order, Invoice, catalog price, or Pricing Foundation.

### 6.2 Pricing Insights — 1/5

- Heavy analysis draft.
- Warning not to invent conclusions without adequate data.
- No visible record/date/filter scope.

### 6.3 Historical Pricing Import Analysis — 1/5

- PDF, CSV, XLSX, and XLS file-type contract.
- Source filename and file-size metadata.
- Extracted-values model.
- Proposed Pricing Foundation mapping.
- Duplicate-signal model.
- Confidence and warnings.
- Explicit no-change boundary.

**Current result:** deterministic mock extraction values with confidence `mock`. The page does not upload or parse the source file.

### 6.4 Wrap Cost Guidance — 1/5

- Heavy advisory mode.
- Cannot mutate Wrap Lab, Quotes, Orders, Invoices, or Pricing Foundation.

### 6.5 Shop Pricing Setup Assistant — 1/5

- Proposed defaults and section model.
- Current-versus-proposed comparison model.
- Owner/admin confirmation requirement.
- Canonical Pricing Foundation application boundary.

The router can create a proposal, but the current UI cannot review and apply one through the canonical pricing service.

### Pricing authority assessment

The Studio pricing family correctly avoids becoming a second price authority. Final values should continue to come from Pricing Foundation and the canonical pricing engine. AI may explain, suggest, identify missing data, or propose settings; it should not silently write prices.

## 7. Pricing Calculators — hidden standout tool

**Rating: 5/5 — Standout / advanced**  
**AI: No**  
**Current route:** `/pricing-calculator`  
**Navigation status:** Routed but absent from Tools & Resources.

### Supported categories

- Banners.
- Rigid Signs.
- Digital Print.
- Cut Vinyl.
- Apparel.
- Promotional.
- Vehicle Graphics.
- Services.
- Custom.

### Calculator inputs

- Category.
- Width and height.
- Inch/foot unit handling.
- Quantity.
- Material or category default.
- Design-needed toggle.
- Install-needed toggle.
- Category-specific fields.
- Canonical material profile.
- Pricing components.
- Saved/common item.
- Optional saved-item defaults.
- Manual selling-price override.

### Authoritative outputs

- Authoritative selling price.
- Canonical pricing method.
- Selected comparison method.
- Profit margin.
- Profit amount.
- Warnings.
- Errors.
- Tier-price preview.
- Cost breakdown.
- Category detail sections.
- Unsupported/unavailable methods with reasons.

### Banner method comparison

- Square Foot plus Add-ons.
- Cost Plus.
- Target Margin.
- Materials, Labor, and Overhead.
- Minimum Charge.
- Deliberate comparison selection without replacing the authoritative canonical result.

### Method setup

- Current configuration and version.
- Primary method.
- Available-method visibility.
- Simple setup preview.
- Apply Simple Setup.
- Advanced enabled-method selection.
- Advanced primary-method selection.
- Version-aware save.
- Read-only setup state for users without write permission.

### Saved Calculation Library

- Name and notes.
- Explicit save.
- Reopen as a fresh working copy.
- Recalculate against current pricing.
- Saved price versus current price.
- Price-changed badge.
- Separate library view.

### Safety and quality

- Permission gates for calculate, read, and write.
- Fails closed when normalized cents are invalid.
- Honest loading/error/unavailable states.
- No replacement price is guessed when a tier is missing.
- Banner comparisons do not override canonical authority.
- Strong frontend regression coverage across categories, calculations, configuration, saving, reuse, and error handling.

### Assessment

This is the strongest actual tool in the section and requires no AI. It should be a first-class Tools & Resources item named **Calculators**, with Pricing Calculators as its initial workspace.

## 8. Prompt Library

**Rating: 2/5 — Basic UI / advanced backend model**  
**AI: No for management; prompts are consumed by AI capabilities**

### Implemented UI

- Lists platform starter and tenant prompts.
- Shows name, status, tool, mode, and description.
- Create form for name and template.
- Permission-gated creation through `ai_prompt:write`.
- Immediately publishes the newly created prompt.
- Read permission through `ai_prompt:read`.

### Advanced backend capabilities

- Platform-starter versus tenant ownership.
- Tool, mode, family, and capability association.
- Description, category, and tags.
- Required and optional variables.
- Draft, published, and archived states.
- Version numbers.
- Published-prompt immutability.
- Create-new-version contract.
- Update and archive endpoints.
- Link to the gateway’s canonical prompt version.

### Major UI limitations

- Creation is hard-coded to Content Writer / Business Copy.
- No tool or mode selector.
- No variable editor.
- No description/category/tag fields in creation.
- No save-as-draft choice.
- No edit/new-version UI.
- No archive action.
- No duplicate/fork action.
- No search, filter, sort, or tags interface.
- No preview with sample variables.
- No “Use in Studio” action.
- No usage count, author, creation date, publish date, or version history display.

## 9. Generated Assets

**Rating: 2/5 — Basic index**  
**Backend depth: 4/5**  
**AI: No for management; records originate from Studio runs**

### Current page

- Tenant-scoped asset list.
- Title.
- Tool.
- Asset type.
- Status.
- Boundary indicator.
- Explicit “Local mock” label when provenance contains `h7_local_mock`.
- Permission gate through `document:read`.

### Backend asset model

- Tool, mode, family, capability, and usage band.
- Result storage type.
- Draft, saved, and archived status.
- Text and structured JSON content.
- File metadata.
- Warnings.
- Provenance.
- Action request and prompt version references.
- Context record linkage.
- Source assets and source links.
- Parent asset and revision number.
- Accepted-as canonical-record metadata.
- Detail and archive endpoints.

### Missing page features

- Asset detail/open action.
- Visual or document preview.
- Edit.
- Rename.
- Download/export.
- Archive/restore action.
- Accept or reject.
- Revise/regenerate.
- Version history.
- Source/prompt/context inspection.
- Link to the canonical record after acceptance.
- Search, filter, sort, folders, tags, and bulk actions.
- Editable Drafts page, even though the backend has a drafts list endpoint.

### Naming issue

The page labels its table **Library**, which risks confusing generated records with the real shared Documents library. Rename this area **Generated Assets** consistently and reserve **Library** for canonical user files.

## 10. AI Activity

**Rating: 2/5 — Basic**  
**Backend depth: 4/5**  
**AI: No**

### Current page fields

- Tool.
- Mode.
- Result type.
- Usage band.
- Context.
- Most-recent-first ordering from generated assets and editable drafts.
- Permission gate through `ai_history:read`.

### Missing fields and actions

- Timestamp.
- Actor/user.
- Request and result status.
- Exact credits charged.
- Provider and model.
- Prompt version.
- Duration.
- Provider cost.
- Failure reason.
- Warnings.
- Input/prompt.
- Output preview.
- Source/context links.
- Request/detail drawer.
- Search/filter/date range.
- Export.
- Retry/re-run.

The separate AI Credits page has richer gateway history, including capability, provider, model, status, and credits. Those two histories should link to each other or be combined into one drill-down experience.

## 11. Shared Document Library — hidden

**Rating: 3/5 — Solid**  
**AI: No**  
**Current route:** `/documents`  
**Navigation status:** Routed but absent from Tools & Resources.

### Implemented features

- Shared file library.
- Private-by-default behavior.
- Authenticated downloads.
- Multi-file upload.
- Drag-and-drop upload area.
- File browser.
- Search by original filename.
- Visibility toggle.
- Download.
- Archive with confirmation.
- Upload progress/disabled state.
- Empty states.
- Link to Form Maker.

### Missing Library features

- Folders and collections despite a folder icon/mental model.
- Tags and advanced filters.
- File preview.
- Detail panel and metadata editing.
- Version history and replacement.
- Restore archived files.
- Bulk actions.
- Share links and granular access.
- Link files to customers, quotes, orders, work orders, employees, or projects from the Library page.
- Unified view of uploaded files, generated assets, forms, templates, signatures, and exports.
- Direct “Save to Library” from Studio results.

### Assessment

This is a real, useful Library and should be added to Tools & Resources navigation. Generated Assets should feed into or link to it after explicit acceptance, not compete with it under a second “Library” label.

## 12. AI Credits and metering

**Rating: 4/5 — Advanced supporting control**  
**Backend depth: 5/5**  
**AI: No**

### Tenant credit account

- Included balance.
- Purchased balance.
- Reserved credits.
- Available-credit calculation.
- Active/inactive account status.
- Low-credit threshold.

### Ledger lifecycle

- Grant.
- Adjustment.
- Reserve before execution.
- Commit after success.
- Release after failure.
- Idempotent ledger entries.
- Balance-after fields.
- Included credits consumed before purchased credits.
- Negative-balance protection.

### Request metering

- Capability-based default credit charge.
- Entitlement check.
- User AI permission check.
- Allowed model selection.
- Provider/model active-state check.
- Request idempotency.
- Received, executing, blocked, failed, and succeeded states.
- Usage ledger.
- Provider-cost ledger.
- Duration and result fields.
- Failure releases reserved credits.
- Zero-credit and low-credit alerts.

### AI Credits page

- Available, included, purchased, and reserved balances.
- Open-alert notice.
- Credit ledger table.
- Gateway history with capability, status, provider, model, and credit charge.
- Refresh.
- Separate `ai_credit:read` and `ai_history:read` behavior.

### Important credit issues

- Studio only says “AI credits apply”; exact numeric pricing is deliberately omitted from the catalog.
- The user cannot see an estimated charge before clicking Create Draft.
- The Studio result does not show actual credits committed or remaining balance.
- Current EC17/EC18 local contract executions can consume default credits even though no external provider is called.
- Voice checks only that available credits are positive before opening a session; final per-event usage is metered afterward.

Recommendation: display **estimated credits**, **maximum possible charge**, **actual charge**, **remaining balance**, and a conspicuous **test/local mock** badge. Local mock runs should be free or use non-monetary test credits.

## 13. AI Governance

**Rating: 3/5 — Solid visibility / advanced backend**  
**Backend depth: 5/5**  
**AI: No**

### Backend governance capabilities

- Provider configuration.
- Credential mode and credential reference.
- Supported modalities.
- BYOK-support flag.
- Model profiles.
- Estimated input/output unit costs.
- Capability registry.
- Allowed model lists.
- Published prompt versions.
- Global, tenant, capability, and model policies.
- Daily request limits.
- Daily credit limits.
- Daily provider-cost limits.
- Capability disable policy.
- Low-credit threshold.
- Budget/rate-limit/spend-cap alerts.
- Provider health events.
- Platform dashboard totals.
- Audit events.
- Tenant-scoped history.

### Current Governance page

- Tenant credit-account count.
- Request count.
- Usage-row count.
- Open-alert count.
- External provider-call count.
- Provider and model list/status.
- Credential mode.
- Model task category and intensity.
- Policy scope/status/limits.
- Recent credit ledger.
- Platform-admin-only access.

### Missing management UI

- Create/edit/activate provider.
- Secure credential setup.
- Create/edit model profile.
- Create/edit capability.
- Create/edit/publish prompt version.
- Create/edit/activate governance policy.
- Acknowledge/resolve alerts.
- Provider health controls.
- Tenant credit grants/adjustments from this page.
- Usage and cost charts.
- Per-tenant/per-capability drill-down.
- Provider failover or model routing.

## 14. Full AI Studio catalog inventory

The current catalog contains **17 tools and 61 modes**.

| Family | Tool | Modes | Usage class | Current AI truth |
|---|---|---|---|---|
| Design & Image | AI Image Generator | General Text-to-Image; Custom Image Concept | Premium | Local mock; no image generated |
| Design & Image | Mockup Generator | Sign Mockup; Banner Mockup; Product Mockup | Premium | Local mock; no rendered mockup |
| Design & Image | Logo Lab | New Logo Concepts; Refresh Existing Logo | Premium | Local mock; no image/vector |
| Design & Image | Vehicle Graphics Studio | Vehicle Wrap Concept; Race Number Design; Driver Name Plate; Team Branding | Premium | Local mock; no vehicle graphics |
| Design & Image | Photo Editor | Enhance Photo; Edit/Replace Area; Add or Remove Object; Background Change | Premium | Local mock; no image edit |
| Design & Image | Artwork Assistant | Artwork Check; Vector Preparation Guidance; Font Finder | Premium | Local mock; no actual file analysis |
| Marketing & Brand | Social Post Builder | Quick Project Post; Completed-Work Showcase; Multi-Platform Post Pack | Standard/heavy | Local draft with publicity safeguards |
| Marketing & Brand | Content Writer | Business Copy; Website or Advertising Copy; Blog and SEO Content | Standard/heavy | Local mock draft |
| Marketing & Brand | Campaign Planner | Campaign Ideas; Campaign Plan; Content Calendar | Light/heavy | Local mock plan/calendar |
| Marketing & Brand | Brand Kit Builder | Brand Ideas; Tagline Generator; Color Palette; Brand Voice | Light/standard | Local mock suggestions |
| Marketing & Brand | Product Content Builder | Product Name Suggestions; Product Description Draft; Webstore Product Content | Light/standard | Local mock draft; no auto-publish |
| Marketing & Brand | Review Reply Assistant | Positive Review Reply; Negative Review Reply; Neutral or Custom Reply | Light/standard | Local mock draft; human review required |
| Writing & Documents | Email Draft Assistant | Quote Follow-up; Payment Reminder; Thank-you Email; Overdue Invoice Email; Project Update; Project-Complete Email; Proof/Approval Request; Custom Email | Standard | Local draft; never auto-sent |
| Writing & Documents | Proposal Builder | Proposal | Heavy | Local generated-asset record |
| Writing & Documents | Document Writer | General Business Document; Proposal; Scope of Work; Standard Operating Procedure; Project Description; Policy or Instructions; Customer Letter; Customer or Order Document; Contract Draft | Standard/heavy | Local mock document text |
| Writing & Documents | Permit Guidance | Permit Checklist | Heavy | Local mock; no live jurisdiction research |
| Pricing & Profitability | Pricing & Profitability | Pricing Advisor; Pricing Insights; Historical Pricing Import Analysis; Wrap Cost Guidance; Shop Pricing Setup Assistant | Standard/heavy/premium | Local mock advisory/analysis only |

## 15. Feature-strength ranking

### Standout / 5-level capabilities

- Canonical Pricing Calculators workspace.
- Business Assistant proposal-confirm-execute safety boundary.
- Tenant/context permission and stale-source validation.
- Credit reserve/commit/release and governance enforcement backend.

### Advanced / 4-level capabilities

- Conditional OpenAI Realtime voice architecture.
- Global Business Assistant launcher plus full workspace.
- Source citations and explicit missing-data calculations.
- AI credit account/ledger/history page.
- Generated-asset, editable-draft, prompt-version, brand-context, and gateway data models.

### Solid / 3-level capabilities

- Deterministic Business Assistant business questions.
- Secure shared Documents library.
- Assistant memory and quick actions.
- AI Governance visibility page.

### Basic / 2-level capabilities

- Studio Overview.
- Marketing & Brand current outputs.
- Writing & Documents current outputs.
- Prompt Library interface.
- Generated Assets interface.
- AI Activity interface.
- Assistant routines and proactive insights.

### Foundation / 1-level capabilities

- Design & Image actual output.
- Permit Guidance actual research.
- Historical pricing file analysis.
- Shop Pricing Setup Assistant application.
- Live AI for Studio text/image tools.

## 16. Features that are backend-only or disconnected

- Editable Drafts list has an endpoint but no page.
- Generated Asset detail and archive endpoints have no visible actions.
- Prompt update, new-version, and archive contracts are not exposed.
- Brand Context create/approve lifecycle is not exposed.
- Historical Pricing Import Analysis creation is not a real file-upload/analyze workflow.
- Pricing Setup Proposal creation and canonical application are not exposed.
- Assistant proposal edit contract is not exposed in the proposal card.
- Conversation list/get endpoints are not presented as saved conversation navigation.
- Library and Pricing Calculators are routed but missing from Tools & Resources navigation.
- AI Credits and AI Governance are separated under Control Center and do not deep-link from Studio run details.

## 17. Features absent from the current repository experience

- Live provider-backed Studio text generation.
- Live image generation, editing, vision, OCR, or vectorization.
- Full image/document preview and export workflow.
- Canonical acceptance workflow from Generated Assets to Documents/templates/products/records.
- Unified Library spanning uploaded files and accepted generated assets.
- Rich document editor and DOCX/PDF creation from Studio.
- E-signatures or signature requests inside Tools & Resources.
- Real municipal permit research with current citations.
- Real historical pricing file parsing.
- Direct marketing publishing/scheduling.
- Social/review platform integrations.
- General conversational AI for text assistant.
- Background execution engine for Assistant routines.
- Broad proactive-insight library.
- Exact Studio credit estimate/receipt.
- Tenant-facing BYOK setup.
- User-facing provider/model choice.
- AI run comparison, evaluation, feedback, or quality rating.
- Search and filters across Generated Assets and AI Activity.

## 18. Permission and safety findings

### Strong controls

- Every major AI area is permission-gated.
- Assistant context is tenant-isolated and record-permission-aware.
- Portal users are rejected from staff AI surfaces.
- Assistant actions require explicit confirmation before execution.
- Email and publishing are never automatic.
- Source staleness is checked before mutation.
- Image originals are contractually preserved.
- Social content records publicity-permission state.
- Contract and permit outputs carry legal/verification warnings.
- Pricing Studio cannot become a second price authority.
- Published prompt versions are immutable.
- Credits are reserved before work and released after simulated failure.
- Voice uses ephemeral credentials and does not store raw audio.

### Controls needing improvement

- The generic Studio page cannot collect several modeled file-reference inputs properly.
- Exact credit charge is hidden at the point of action.
- Local mock runs should not look equivalent to live AI runs.
- Proposal editing is backend-only despite an “edited” lifecycle state.
- `email_draft_assistant` requires `email:send`; a dedicated draft permission would better reflect its non-sending behavior.
- Generated Assets requires document-read permission, but asset-specific read/write permissions would be clearer.
- Platform Governance is deep in backend behavior but mostly observation-only in UI.

## 19. Highest-value corrections

1. Add **Library** and **Calculators** to Tools & Resources navigation.
2. Put an unmistakable **Local Mock / No Live AI Provider** banner across every EC17 Studio family until live adapters are enabled.
3. Make local mock runs free or meter them with non-monetary test credits.
4. Connect the shared provider layer to live OpenAI text and image capabilities with per-capability model routing, without weakening the existing confirmation and tenant boundaries.
5. Show estimated credits before execution and actual credits/remaining balance afterward.
6. Build real input controls for file upload, image selection, masks, dimensions, record pickers, platform selection, audience, tone, and output format.
7. Add result review actions: edit, accept, reject, revise, regenerate, download, and save to Library/canonical record.
8. Expose Editable Drafts as a first-class queue or merge them into Generated Assets with clear result-type filters.
9. Complete Prompt Library with tool/mode selection, variables, drafts, versions, archive, search, preview, and Use in Studio.
10. Expose and operationalize approved Brand Context so every appropriate generation can use reusable brand truth.
11. Add proposal editing to Business Assistant before confirmation.
12. Label text Business Assistant as record-backed smart help until open-ended AI is truly connected; retain its cited deterministic answers as reliable tools.
13. Expand proactive insights beyond open invoices and either implement routine scheduling or clearly label routines as saved prompts.
14. Connect AI Activity, AI Credits, and Generated Assets through request-level drill-down.
15. Keep Pricing Calculators deterministic and authoritative; use AI only for explanations and reviewable suggestions.

## 20. Recommended final Tools & Resources structure

1. **Overview**
2. **Business Assistant**
3. **Design & Image**
4. **Marketing & Brand**
5. **Writing & Documents**
6. **Calculators**
7. **Prompt Library**
8. **Library**
9. **AI Activity**

Within **Library**, use filters rather than separate competing destinations:

- Uploaded Files.
- Generated Assets.
- Editable Drafts.
- Forms.
- Templates.
- Archived.

Keep **AI Credits** in Control Center for tenant administrators and **AI Governance** in Platform Administration, but link both from AI Activity/run details for authorized users.

## 21. Verification evidence

Current code includes focused automated coverage for the most important contracts:

- EC16 AI gateway contracts, governance, and metering.
- EC17 Studio catalog identifiers, permissions, platform bootstrap, inactive capabilities, credit disclosure, and zero external provider calls.
- EC18 Assistant entitlement, permissions, tenant isolation, source-linked BI answers, non-mutating invoice questions, confirmation-required proposals, canonical task/note execution, draft-only email behavior, memory secret rejection, routines, insights, Studio delegation, and no-invention margin disclosures.
- EC18 Realtime voice secret boundary, Safety Identifier, provider/model/voice configuration, raw-audio non-retention, and idempotent usage metering.
- Frontend Studio family/mode rendering.
- Frontend Business Assistant context, sources, quick actions, memory, routines, insights, unconfigured voice fallback, mocked WebRTC, push-to-talk, transcription, and usage events.
- Eleven Pricing Calculator frontend tests covering authoritative and comparison results, category switching, minimum evidence, deliberate method selection, fail-closed behavior, method setup, explicit saving, reuse/recalculation, and permissions.

Automated tests validate contracts and mocks; they do not prove that a production OpenAI key is present, that a real Realtime call has completed in production, or that any Studio text/image provider is live.

## 22. Principal code evidence

The audit was grounded primarily in current navigation/router code, frontend pages, backend models/services/routers, and focused tests, including:

- [Tools & Resources navigation](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/lib/navigation.js)
- [Application routes](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/App.js)
- [AI Studio page](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/pages/AIStudioPage.jsx)
- [AI Studio catalog and local runtime](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/app/services/ai_studio.py)
- [AI Studio router](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/app/routers/ai_studio.py)
- [AI Studio records](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/app/models/ai_studio.py)
- [Business Assistant page](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/pages/BusinessAssistantPage.jsx)
- [Business Assistant panel and voice client](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/components/assistant/AssistantPanel.jsx)
- [Business Assistant service](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/app/services/business_assistant.py)
- [Business Assistant router](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/app/routers/business_assistant.py)
- [AI gateway, credits, and governance](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/app/services/ai_gateway.py)
- [Prompt Library](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/pages/PromptLibraryPage.jsx)
- [Generated Assets](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/pages/GeneratedAssetsPage.jsx)
- [AI Activity](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/pages/AIActivityPage.jsx)
- [Shared Documents library](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/pages/DocumentsPage.jsx)
- [Pricing Calculators](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/pages/PricingCalculatorPage.jsx)
- [AI Credits page](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/pages/AICreditsPage.jsx)
- [AI Governance page](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/pages/PlatformAIGovernancePage.jsx)
- [EC17 Studio tests](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/tests/test_ec17_ai_studio_catalog.py)
- [EC18 Assistant foundation tests](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/tests/test_ec18_assistant_foundation.py)
- [EC18 Assistant intelligence tests](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/tests/test_ec18_assistant_intelligence.py)
- [EC18 Assistant voice tests](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/backend/tests/test_ec18_assistant_voice.py)
- [Pricing Calculator tests](https://github.com/dnblack323/SIGNGUY-MVP/blob/66c0c49fb6450268ad784c7a5e291257442b3c20/frontend/src/__tests__/PricingCalculatorPage.test.jsx)

## Final verdict

Tools & Resources is **architecturally advanced but uneven as a shipped product**. The repository has the hard parts many MVPs skip: tenant isolation, permissions, entitlements, citations, immutable prompt versions, credit ledgers, governance policies, stale-data checks, confirmation boundaries, and a safe Realtime voice design. It also has a truly excellent deterministic Pricing Calculator.

The visible Studio, however, should be treated as a **provider-ready prototype**, not a finished AI suite. The catalog’s 17 tools and 61 modes are valuable product definitions, but most current outputs are local mocks. Design & Image is the clearest example: it has eighteen named modes yet produces no actual images.

The best next move is not to add more catalog entries. It is to make the existing ones real, reviewable, and connected: live provider execution, accurate credit receipts, real file/image controls, editable outputs, canonical acceptance, Library integration, and honest mock/live labeling. At the same time, expose the non-AI Library and Pricing Calculators that are already useful today.
