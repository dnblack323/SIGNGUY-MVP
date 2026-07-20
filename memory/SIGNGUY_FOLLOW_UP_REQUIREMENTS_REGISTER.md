# SignGuy Follow-Up Requirements Register

Last updated: July 20, 2026

This register tracks owner requirements discussed while preparing EC17 that are not authorized as complete EC17 implementation. Some were included in the EC17 prompt as record-only gaps; they must not be treated as implemented until verified in code, tested, and assigned to a completed checkpoint.

## Status meanings

- **Record-only in EC17:** Codex was told to document or audit the requirement, not necessarily implement it.
- **Partially in EC17:** EC17 owns an integration or contextual AI entry point, while another module owns the full workflow.
- **Not yet sent:** Still needs to be included in a future implementation prompt.
- **Verify:** Inspect the completed code before deciding whether follow-up work is needed.

## Document Library, DocuLink, Templates, and Onboarding

| Requirement | Current instruction status | Future action |
|---|---|---|
| Central placeholder system for Customer, Order, Quote, Invoice, Webstore, shop, and date fields | Partially in EC17 | Verify the canonical template engine; complete in the Document Library/DocuLink checkpoint if missing. |
| Easy **Insert Placeholder** picker | Partially in EC17 | Verify UI and add if missing. |
| Automatic placeholder replacement with missing-value warnings and preview | Closed for EC19 onboarding/template exercise | EC19 adds `/api/onboarding/placeholders/preview`, frontend preview, missing-value warnings, and targeted tests. Broader document-specific placeholder expansion stays with the Document Library/DocuLink checkpoint. |
| Tenant company logo, colors, header, footer, contact information, and branding | Partially in EC17 | Verify canonical tenant-branding integration. |
| AI-created document can be saved as a reusable template | EC17 implementation requirement | Verify after EC17. |
| Reusing a saved template without AI generation does not consume AI credits | Verified for EC19 onboarding template exercise | EC19 template exercise reuses canonical template validation/rendering and targeted tests verify no `ai_usage_events` are created. |
| Onboarding step where the user customizes or creates a sample template using placeholders | Closed in EC19 | EC19 adds the onboarding placeholder/template exercise and targeted backend/frontend tests. |
| Contextual Document Creator shortcuts from Customer, Quote, Order, Invoice, Webstore, and Wrap Lab | Partially in EC17 | Verify after EC17 and complete module-specific gaps later. |
| Context is preselected from the open record but remains visible/changeable | EC17 implementation requirement | Verify after EC17. |
| AI email button inside the normal email composer | EC17 implementation requirement where architecture permits | Verify after EC17. |

## Platform Billing, Promotions, and Stripe

| Requirement | Current instruction status | Future action |
|---|---|---|
| Platform promo codes for subscriptions | Record-only in EC17 | EC13 commercial follow-up. |
| Promo codes for setup packages | Record-only in EC17 | EC13 commercial follow-up. |
| Promo codes for AI credit packages if commercially approved | Record-only in EC17 | EC13 commercial follow-up. |
| Stripe product and price provisioning manifest/checklist | Record-only in EC17 | Audit EC13 commercial catalog and create before live Stripe setup. |
| Checklist includes internal key, Stripe name, description, recurring/one-time status, interval, cents, tax behavior, entitlements, Founder treatment, test/live IDs, and activation status | Not yet guaranteed as implementation | Include in EC13 commercial activation prompt. |
| Keep platform promotion codes separate from Webstore shopper coupons | Record-only in EC17 | Enforce in EC13/EC14 follow-up tests. |
| Do not incorrectly create platform Stripe Products for transaction fees or every individual Webstore item | Not yet guaranteed as implementation | Confirm against EC13/EC14 Stripe boundary before provisioning. |

## Webstore Setup and Questionnaires

| Requirement | Current instruction status | Future action |
|---|---|---|
| One shared core questionnaire plus type-specific sections for each Webstore type | Record-only in EC17 | EC14 Webstore readiness follow-up. |
| Questionnaire sections include owner info, purpose/type, branding, products, pricing/share, fundraising/donations, sponsors, dates, fulfillment, Stripe onboarding, approvals, and artwork | Record-only in EC17 | EC14 follow-up. |
| Display one questionnaire section at a time, not one long page | Record-only in EC17 | EC14 follow-up. |
| Progress indicator, Back, Save and Continue, Resume Later, and section validation | Record-only in EC17 | EC14 follow-up. |
| Conditional questions; for example, sponsor questions only when sponsors are enabled | Record-only in EC17 | EC14 follow-up. |
| Questions vary appropriately for B2B, Fundraiser, Event, Promotional, Employee, and General stores | Record-only in EC17 | EC14 follow-up. |
| Every questionnaire answer maps to a defined setup field or labeled informational answer | Record-only in EC17 | EC14 follow-up. |
| Preserve original questionnaire answers | Record-only in EC17 | EC14 follow-up. |
| AI summarizes answers for sign-shop staff without replacing originals | Record-only in EC17 | EC14 plus EC17 integration follow-up. |
| Store owner can upload images, logos, and artwork during questionnaire/setup | Record-only in EC17 | EC14 follow-up. |

## Webstore Templates, Catalogs, Mockups, and Approval

| Requirement | Current instruction status | Future action |
|---|---|---|
| Universal reusable Webstore template library | Record-only in EC17 | Verify EC14; implement in follow-up if missing. |
| Every Webstore has its own independent product catalog | Existing owner rule; record-only reminder in EC17 | Verify EC14 implementation and tests. |
| Applying a universal template copies starting data without sharing one live product record among stores | Not yet guaranteed as implementation | Add EC14 verification test. |
| Staff can quickly create product mockups from Webstore product editing | Partially in EC17 | EC17 provides AI Product Mockup entry; verify full EC14 workflow. |
| Staff can send selected product mockup revisions to the store owner | Record-only in EC17 | EC14 follow-up. |
| Store owner can approve, reject, or request changes | Record-only in EC17 | EC14 follow-up. |
| Preserve revisions, comments, approver, approval time, and approved revision | Record-only in EC17 | EC14 follow-up. |
| Unapproved mockups cannot appear in the public store | Record-only in EC17 | EC14 follow-up and tests. |
| AI concept/mockup is not automatically a formal production proof | EC17 safety requirement | Verify EC17/EC14 integration. |

## Webstore Shopper Promo Codes

| Requirement | Current instruction status | Future action |
|---|---|---|
| Store-specific shopper promo codes | Record-only in EC17 | EC14 commercial follow-up. |
| Percentage or fixed discount | Record-only in EC17 | EC14 follow-up. |
| Start/end dates, usage limits, minimum purchase, applicable products, and active state | Record-only in EC17 | EC14 follow-up. |
| Discount snapshot stored on the buyer order | Record-only in EC17 | EC14 follow-up. |
| Webstore code cannot discount the SignGuy platform subscription | Record-only in EC17 | Cross-domain test. |

## Development Preview Environment

| Requirement | Current instruction status | Future action |
|---|---|---|
| Full application preview without Emergent | Not yet sent | Create a dedicated development-environment task. |
| GitHub Codespaces configuration | Not yet sent | Add a dev container after inspecting repository dependencies. |
| MongoDB available inside the development environment | Not yet sent | Configure a service/container or approved development database. |
| Automatically forward frontend port 3000 and backend port 8001 | Not yet sent | Configure Codespaces forwarded ports. |
| Safe development login and seed data | Not yet sent | Use development-only settings; never weaken production authentication. |
| One-command startup and clear health checks | Not yet sent | Add documented scripts after dependency audit. |
| Local PowerShell launcher as an alternative to Codespaces | Not yet sent | Add after local environment is stable. |

## Priority recommendation

1. Finish and verify EC17 without expanding it into unrelated commercial work.
2. Establish a reliable full-stack preview environment.
3. Perform an EC14 Webstore readiness audit because a real customer is waiting for a store.
4. Complete missing questionnaire, template/catalog, product mockup approval, and shopper coupon work.
5. Complete the Document Library/DocuLink placeholder and onboarding gaps.
6. Complete EC13 promotion codes and the Stripe provisioning manifest before live commercial activation.
