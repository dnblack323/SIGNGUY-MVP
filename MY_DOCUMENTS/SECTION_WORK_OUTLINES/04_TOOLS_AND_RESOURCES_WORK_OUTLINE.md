# Tools & Resources — Work Outline

This section should become the clear home for reusable resources, creative tools, the Business Assistant, AI tools, prompts, generated assets, and activity history. The existing Tools & Resources feature audit is the starting record.

## 1. Confirm what belongs in Tools & Resources

- Keep the Studio, Business Assistant, Design & Image, Marketing & Brand, Writing & Documents, Pricing & Profitability tools, Prompt Library, Generated Assets, and AI Activity here.
- Place the full reusable Library and Templates management workspace here, even when other records link to library items.
- Keep Pricing Foundation configuration in Control Center; Tools & Resources may contain advisory or calculation helpers but should not silently own pricing rules.
- Keep customer-specific files attached to Customers, Quotes, Orders, Webstores, or Wrap Lab instead of moving them into a disconnected library copy.
- Separate reusable assets from generated outputs and record attachments.

## 2. Correct the module navigation

- Review whether the current Studio-first navigation explains the section clearly.
- Add or expose Library and Templates if their management pages exist or are completed.
- Decide whether the tool-category tabs should remain separate or be grouped inside a Tool Catalog.
- Keep the Business Assistant easy to find without letting it replace normal non-AI workflows.
- Avoid several tabs that all lead to the same underlying tool grid.

## 3. Decide internal tabs and ribbons

- Define internal tabs for the Studio, Business Assistant, Tool Catalog, Library, Templates, Prompt Library, Generated Assets, and AI Activity.
- Choose contextual actions such as New Prompt, Run Tool, Upload Resource, Create Template, Save to Library, Attach to Record, Review Output, and View Usage.
- Keep navigation out of the ribbon.
- Make AI-credit costs and review requirements visible before an action runs.

## 4. Update the complete feature audit

- Re-audit all visible tools and their backend support against the newest code.
- Distinguish working tools, local/mock behavior, disabled controls, provider-dependent tools, and advertised placeholders.
- Document inputs, outputs, saved history, permissions, credit use, generated files, and record connections.
- Identify whether each tool requires AI, optionally uses AI, or should work without it.

## 5. Create and correct the Tools & Resources gap list

- Number incomplete tools, missing provider connections, broken save flows, confusing categories, unsafe file handling, permission gaps, and placement problems.
- Separate core release work from expensive or later AI tools.
- Combine repeated problems that come from the same shared provider, storage, credit, or output system.
- Do not treat a tool card or prompt box as a completed feature unless the full workflow works.

## 6. Verify gaps against the code

- Inspect tool pages, AI gateway services, provider adapters, entitlement checks, credit ledger behavior, storage, output history, permissions, tenant filters, and tests.
- Confirm that buttons call real actions and return usable results.
- Verify that outputs can be reviewed, saved, downloaded, reused, or attached where promised.
- Require code and workflow evidence before marking an AI feature complete.

## 7. Complete the Business Assistant

- Reliable conversation flow, context retrieval, safe actions, and clear answers
- Links and actions that open the correct SignGuy AI records
- Permission-aware access to tenant data
- Non-AI fallback paths for work that should not require the assistant
- Conversation and action history without exposing information from another shop
- Clear boundary between advice, drafts, and actions that actually change business records

## 8. Complete the tool categories

- Design & Image tools
- Marketing & Brand tools
- Writing & Document tools
- Pricing & Profitability advisory tools
- Prompt Library and reusable prompts
- Any calculators or utilities that belong here rather than in Pricing Foundation
- A consistent run, review, save, attach, and reuse workflow for every tool

## 9. Complete Library, Templates, and asset workflows

- Reusable documents, forms, questionnaires, prompts, checklists, brand assets, artwork resources, and templates
- Categories, search, tags, versions, ownership, archive status, and permissions
- Clear links from reusable resources to the records that used them
- Generated Assets with review status, source, prompt, provider, date, and usage history
- Protection against silently changing old records when a template is later edited

## 10. Complete AI credits, provider, and governance connections

- Check entitlement before running a paid AI tool.
- Show the expected credit cost or usage rule.
- Record successful, failed, cancelled, and refunded usage correctly.
- Handle missing provider configuration and provider failures clearly.
- Send platform-level AI policies to Control Center instead of hiding them inside individual tools.

## 11. Fix permissions, privacy, and output safety

- Control who may use tools, view history, manage prompts, manage templates, and access generated assets.
- Keep tenant information isolated during context retrieval and storage.
- Mark generated content that requires human review.
- Preserve prompt, provider, model, input, output, and attachment history when required for audit purposes.
- Prevent private customer or employee information from appearing in unrelated tool history.

## 12. Clean up the interface and code

- Remove dead tool cards, duplicate categories, confusing labels, and inconsistent result layouts.
- Use one shared tool-run and output system instead of rebuilding it for every tool.
- Split oversized AI, Studio, asset, prompt, and document files.
- Keep provider-specific code behind shared service boundaries.

## 13. Test and verify

- Test tool permissions, entitlements, credits, provider failures, retries, saved output, generated assets, record attachments, and tenant isolation.
- Test every tool category through the visible interface.
- Run backend tests, frontend tests, and the frontend build.
- Confirm that normal app workflows remain usable when AI is unavailable.

## 14. Update the registers and perform the final review

- Record completed and remaining Tools & Resources issues.
- Add branches, commits, tests, limitations, and provider requirements.
- Perform a final category-specific code review.
- Update the main issue register with any cross-cutting AI, file, credit, or security risks.
