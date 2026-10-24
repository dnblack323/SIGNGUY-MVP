# Help and Documentation V1

## One authoritative source

Documentation lives in `backend/app/help_content/articles/*.md` (front matter + Markdown) with the taxonomy and contextual-help definitions in `catalog.py`. `HelpCenterService.sync_seed_content()` loads them into the existing `help_articles` and `contextual_help_definitions` collections at startup and on platform bootstrap.

- Idempotent: unique slugs, upsert-by-slug, safe from several workers.
- Seed-managed rows (`content_source="seed"`) are refreshed when the packaged text changes (`seed_hash`).
- Rows edited through `POST /api/help/platform/articles` become `content_source="custom"` and are never overwritten.
- Seed articles removed from the package are archived, never deleted.
- Draft/published/archived and platform-admin-only editing are unchanged. Tenant users never see drafts or archived articles, even with `include_archived=true`.

## API changes

`GET /help/articles` is lightweight (no body; `include_body=true` adds it), searches every term across title, summary, body, keywords, aliases, module and category (key or label), escapes user input, ranks by relevance and returns a snippet. `GET /help/categories` serves the taxonomy with counts. `GET /help/articles/{slug}` resolves aliases. `POST /help/support/escalations` was removed: Contact Support uses the single community support queue (`/community/support`).

## Reuse classification

| Area | Class | Notes |
|---|---|---|
| Help article models, publishing, platform permissions, feedback | KEEP | unchanged |
| Contextual help popover and definitions | KEEP / UPDATE | now links to the full article; 10 new surfaces |
| Community support, bug reports, feature requests, notifications | KEEP | forms and status display improved; no new queue |
| Help Center page | UPDATE | now the home; article reader moved to Documentation |
| `support_escalations` flow in Help Center | REMOVE | duplicate of the community support queue; the model and indexes remain in onboarding-owned files until that branch merges |
| signguyai `DocsLayout` | REUSE (idea) | category groups, collapsible sections, search, mobile menu; its search box never filtered anything |
| signguyai docs text | UPDATE | Getting Started, Customers, Orders, Invoicing, Pricing, Webstores, Wrap, AI, FAQ restructured around current MVP names (orders not jobs, Production Board, Pricing Foundation) |
| Original CSV import/export, branding profile, apparel tiers, Stripe Connect wording, webstore flow | REMOVE | not present or different in MVP; not documented |
| Public marketing site, docs screenshots | MISSING | future work |

## Known limitations (documented to users)

See the "Community and known limitations" article. Not built here: community comments/spaces/moderation UI, Founder administration, bug attachments, customer "Invite to portal" button, article editor UI.

## Original website assets worth migrating later

`signguyai` public nav and footer, docs hero copy, screenshots under its docs pages, and the pricing/feature marketing sections. Public site redevelopment is separate work.
