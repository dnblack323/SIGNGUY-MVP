# Webstores Phase 4 — first product selection increment

## Gap review and Code Quality Assessment before implementation — October 22, 2026

Owner authorized the first clearly defined incomplete Phase 4 increment, continuing merged main `9a34355`. Existing nine-phase roadmap and corrected doc 11 remain controlling; this is a scoped increment record, not a replacement roadmap.

| Existing subsystem | Current evidence / gap | Assessment / decision |
|---|---|---|
| Product templates / products / seven-tab workspace | Tenant/platform templates, private drafts, revision checks, variants, categories and existing template-to-draft controls already work in source and retained tests. Canonical saved-item/package linkage is incomplete. | Keep existing services and records. Do not create a new catalog or extend provisional pricing contracts. |
| Questionnaire review | Frozen submitted answers, conditional visibility and deterministic staff brief already exist. Starting product ideas can already start drafts. | Keep; reuse visible completed answers. No free-text AI interpretation. |
| Product planning | Existing Products tab displays a disabled AI suggestions placeholder. No deterministic request-to-template shortlist exists. | Needs extension: explained shortlist from existing active templates. Select into existing draft controls; no automatic creation. |
| Artwork / mockups / owner approvals | Canonical setup files, artwork/mockup associations, staff review and owner product approval exist. Template preview and Gateway-controlled local mock AI actions exist. | Keep; no second artwork store, paid generation or replacement approval flow. New mockup generation remains a later increment. |
| Pricing / fulfillment | Existing manual product prices and launch approval snapshots exist. Engine upgrade, canonical saved-item/package contracts and separate shop/retail price evidence remain dependencies. Supplier stock/capability facts are not established by template metadata. | Hold price proposals and policy changes for approved receiving contracts. Recommendations make no price/stock/capability claims. D-16 new starter governance, D-23 shortfall policy and D-24 defaults are not guessed. |

**First increment / order:** (1) deterministic template shortlist with request/type reasons and unmatched-request guidance; (2) staff selection in current Products tab; (3) scoped permission/regression tests and isolated staff/owner browser proof; (4) one draft PR, owner review. Subsequent catalog/configuration, pricing, mockup and approval increments retain their existing roadmap dependencies and separate scope boundaries.

**Workflow:** staff reviews the completed questionnaire, sees active matching templates and the reasons, selects one into the existing template picker, then uses the existing draft controls and product editor. Staff still checks actual supplier stock, sizes/colors, fulfillment, artwork/mockups and price before sending anything to the owner. Existing owner approvals and launch gates remain authoritative; nothing publishes automatically.

**Scope / complexity:** Class B selection/read-model extension; tenant/auth boundaries receive focused correctness coverage. No price fields are added or recalculated, no provider called and no new lifecycle/database/task system. Existing legacy template prices remain outside recommendation output and do not become verified pricing evidence. No new global starter families or governed content are seeded by this increment.

## Implementation and verification

Implemented: a read-only staff endpoint and an explained shortlist in the existing Products tab. Matches use visible frozen submitted/reviewed questionnaire answers and declared active template types/store suitability. The panel honors declined extras, flags unmatched requests, marks templates already selected and selects into the existing picker. It does not create a draft until staff uses the existing Add From Template action.

**Focused verification:** 13 backend tests passed (4 new recommendation/permission cases plus 9 existing product-foundation cases); 44 frontend tests passed across recommendations, product foundation, stage shell/branding and owner product approval. Coverage includes foreign tenants, canonical platform templates, missing read permission, assignment restrictions, portal-token rejection, hidden/draft questionnaire answers, archived templates, deterministic/read-only results and explicit draft creation. Normal GitHub CI is required on the draft PR; see the PR checks and local owner checklist for current results.

**Actual browser verification:** normal password authentication on a run-owned isolated MongoDB/backend/frontend, with dev bypass disabled and provider keys blank. Staff saw requested hats/hoodies, the owner's colors/sizes and fulfillment context, declined extras and unmatched yard signs. Selecting Hat changed the existing picker without creating a product; explicitly clicking Add From Template created an incomplete Private Catalog draft with approval status `not submitted`. The shortlist then marked it already selected. The Owner Portal opened with its own session after staff sign-out, showed the existing approved tee and new not-submitted draft, and retained packet/Terms/payment launch gates. No approval, Terms acceptance, publishing or provider action was performed. Existing owner draft visibility is retained; private catalog here means not buyer-published, not hidden from its owner. Demo prices shown in screenshots are inherited existing template/product values, not validated calculations or new recommendations.

- [Staff shortlist and selected existing picker](phase4-staff-product-shortlist.png)
- [Explicitly created private catalog draft](phase4-staff-private-draft.png)
- [Existing owner product/packet review](phase4-owner-review.png)

The run-owned smoke server and private MongoDB were disposed after capture. Normal local databases, unrelated worktrees and owner documents were preserved.

**Limits / remaining work:** matching is deterministic against declared product types/categories and store-type metadata; audience, colors, personalization and fulfillment are displayed as review context, not invented template capabilities. No supplier availability feed, new catalog linkage, Engine upgrade, proposed price calculation, paid AI/provider evaluation, generated mockup, automatic approval or publication. Existing downstream editing/approval/file flows are reused. D-16/D-23/D-24 and canonical pricing/catalog dependencies remain open for their applicable increments. This increment is ready for owner review; Phase 4 as a whole is incomplete. Owner approval is required before merge or deployment.
