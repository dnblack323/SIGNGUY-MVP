# SIGNGUY MVP — Help & Community Feature Audit

**Repository:** `dnblack323/SIGNGUY-MVP`  
**Audited branch:** `main`  
**Code baseline:** `5c5303e9216c8013c8ec793f2574aba3f559d6d1`  
**Audit date:** August 16, 2026  
**Scope:** Help & Community, including Help Center, Documentation, Onboarding, contextual help, Community, Founders spaces, Bug Reports, Feature Requests, Contact Support, article feedback, subscription guidance, and What’s New.

This is a repository-level feature audit. A capability is credited only when current code contains a usable interface, working backend behavior, or a clearly wired integration. Backend-only workflows, duplicate systems, inaccessible controls, thin aliases, and provider-deferred features are identified separately.

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
- **Optional:** the core feature works without AI and offers a separate, user-triggered AI action.
- **Required:** a live AI provider is necessary for the feature.
- **Planned / inactive:** an AI-shaped contract exists, but no live model is connected.

## Executive scorecard

| Final category | Usable app score | Backend depth | AI | Summary |
|---|---:|---:|---|---|
| Help Center | **3/5 — Solid** | 4/5 | No | Search, categories, article reading, feedback, contextual guidance, billing guidance, and support entry exist; the content library is only nine short articles. |
| Documentation | **2/5 — Basic alias** | 4/5 | No | The route exists but opens the same unfiltered Help Center; there is no documentation-specific index, hierarchy, deep-link system, or rich guide experience. |
| Onboarding | **4/5 — Advanced foundation** | 5/5 | No | Sixteen tenant-scoped setup tasks, canonical completion detection, progress, company/pricing/template actions, setup-package handoff, and permissions are real; several exercises remain manual or misleading. |
| Contextual Help | **3/5 — Solid foundation** | 4/5 | No | Reusable popover component and five registered help definitions exist, but coverage across the app is very limited. |
| Community | **2/5 — Basic UI / advanced backend** | 5/5 | No | Posts and voting are usable after a space exists, but the page omits post detail, comments, search, editing, reporting, moderation, and space management. |
| Founders Community | **2/5 — Basic read view** | 4/5 | No | Secure founder-only scopes and grant/revoke contracts exist; the visible Founders tab is read-only and founder administration is backend-only. |
| Bug Reports | **2/5 — Basic UI / advanced backend** | 5/5 | No | Users can submit and track basic reports, while steps, expected/actual behavior, browser metadata, attachments, duplicate handling, and status administration are inaccessible in the UI. |
| Feature Requests | **3/5 — Solid contributor view** | 5/5 | No | Submit, global list, voting, status, and staff responses work; roadmap administration, duplicate relationships, release links, filters, and detail history are missing from the UI. |
| Contact Support | **2/5 — Conflicted implementation** | 5/5 for routed support | No | The routed support engine is strong, but Help Center creates records in a second, simpler support system, splitting the canonical queue. |
| What’s New | **1/5 — Foundation only** | 2/5 | No | The route opens the ordinary Help Center and one static release-notes article; no release feed, versions, dates, unread state, or linked shipped features. |
| Help content administration | **1/5 — Backend only** | 4/5 | No | Draft/publish/archive and platform-managed content contracts exist, but there is no article editor or publishing UI. |
| Community/support administration | **1/5 — Backend only** | 5/5 | No | Moderation, assignments, internal notes, status transitions, duplicate handling, and Founder grants exist only through APIs. |

### Overall assessment

Help & Community has a strong backend foundation and the correct eight destinations in navigation. The best current feature is **Onboarding**, which reuses canonical company settings, pricing, templates, portals, billing, AI-governance, and order records rather than creating shadow setup data. The strongest hidden system is the **Community/Support backend**, with tenant/platform/founder scopes, moderation, voting, duplicate handling, attachments, routing, assignments, notifications, internal notes, and audits.

The visible product is much thinner than that backend:

- Documentation and What’s New are aliases of the same general Help Center page.
- Community does not expose comments even though every post displays a comment count.
- A fresh tenant cannot create or manage a Community space from the page.
- Bug Reports exposes only four of the many modeled report fields.
- Contact Support is split between two unrelated record collections.
- No frontend administration exists for articles, community moderation, bugs, features, Founder access, or support queues.

No Help & Community feature currently requires AI. The Pricing Setup Assistant is deterministic, historical invoice analysis is explicitly unavailable/provider-deferred, and contextual help is stored documentation—not generated guidance.

## Current Help & Community navigation

The current module navigation contains eight items:

1. Help Center — `/help`
2. Documentation — `/help/docs`
3. Onboarding — `/help/onboarding`
4. Community — `/help/community`
5. Bug Reports — `/help/bugs`
6. Feature Requests — `/help/feature-requests`
7. Contact Support — `/help/contact`
8. What’s New — `/help/whats-new`

There is also a legacy/canonical direct Onboarding route at `/onboarding`, matched by the Onboarding navigation item.

### Shared-page architecture

- Help Center, Documentation, and What’s New all render `HelpCenterPage`.
- Community, Bug Reports, Feature Requests, and Contact Support all render `CommunityPage` with a different default tab.
- Onboarding renders `OnboardingPage` from both `/onboarding` and `/help/onboarding`.

Reusing components is sensible. The problem is that Documentation and What’s New do not change the content or filter at all, while the Community routes still display the page title **Community** even when the selected destination is Bugs, Features, or Support.

## 1. Help Center

**Rating: 3/5 — Solid**  
**Backend depth: 4/5**  
**AI: No**

### Search and discovery

- Full Help Center permission gate through `help:read`.
- Search across article title, body, keywords, and module.
- Category filter.
- Article list with title, category, and body preview.
- Article reading panel.
- Refresh action.
- Empty search state.

### Available categories

- Onboarding.
- Role Guides.
- Module Guides.
- Billing.
- AI.
- Trust.
- Release Notes.

The UI also includes an `all` option.

### Bootstrapped article library

The current platform bootstrap creates nine short published articles:

1. Getting Started.
2. Owner Guide.
3. Staff Guide.
4. Pricing Setup Guide.
5. Templates and Placeholders.
6. Failed Subscription Guidance.
7. AI Boundaries.
8. Privacy and Data Deletion.
9. Release Notes.

### Article feedback

- Helpful button.
- Needs Work button.
- Tenant-scoped feedback record.
- Article ID and slug linkage.
- Optional feedback comment in the backend model.
- Idempotency support.

**Feedback rating: 3/5 — Solid foundation**

The page does not offer the optional comment field, show whether the user already voted, allow changing feedback cleanly, or provide an admin feedback dashboard.

### Failed-subscription guidance

- Reads the current tenant subscription and billing account.
- Detects current, recently past due, deeper past due, and suspension-eligible states.
- Returns safe next-step guidance.
- Does not mutate subscription or billing records.
- Only loads for users with `subscription:read`.

**Rating: 4/5 — Advanced contextual guidance**  
**AI: No**

This correctly keeps EC13 billing records authoritative. The limitation is that the Help Center header always requests contextual guidance for `billing.subscriptions`, even when the user is reading unrelated help.

### Article lifecycle backend

- Draft.
- Published.
- Archived.
- Platform-managed flag.
- Audience list.
- Module and search keywords.
- Version field.
- Publish and archive timestamps.
- Platform-admin upsert.
- Platform-admin status transition.
- Audited content changes.

### Important access-control issue

Normal article reads hide draft and archived content by default. However, both list and article-detail endpoints accept `include_archived=true` while requiring only `help:read`. The service does not recheck platform-admin status before removing the published-status filter. A staff user could therefore request non-published articles directly through the API.

The `audience` field is also modeled but not enforced in the search/read service. This should be fixed before sensitive platform-only help content is introduced.

### Missing Help Center features

- Rich Markdown or structured article rendering.
- Table of contents.
- Article sections and anchors.
- Related articles.
- Breadcrumbs.
- Direct article URLs in the frontend.
- Recently viewed or saved articles.
- Search highlighting and relevance ranking.
- Screenshots, GIFs, video, downloads, or interactive walkthroughs.
- Article version history.
- View analytics and failed-search analytics.
- Support status follow-up from the embedded form.
- Full article authoring and publishing UI.
- App-wide breadth: nine short articles cannot document the current MVP’s major workflows.

## 2. Documentation

**Rating: 2/5 — Basic alias**  
**Backend depth: 4/5 through Help Articles**  
**AI: No**

### What exists

- Dedicated navigation item.
- Dedicated route at `/help/docs`.
- Same searchable article collection as Help Center.
- Module-guide category.
- Role-guide category.
- Platform-managed article lifecycle.

### What the route actually does

`/help/docs` renders exactly the same `HelpCenterPage` as `/help`. It does not:

- Default to Module Guides.
- Display a documentation index.
- Organize articles by application area.
- Show module coverage.
- Present a documentation tree.
- Deep-link to a selected article.
- Distinguish quick help from full reference documentation.

### Assessment

Documentation is a label and route, not yet a distinct feature. Either remove the duplicate navigation item and keep one Help Center, or make Documentation a real structured knowledge base. Keeping two menu items that open the same unfiltered page creates unnecessary navigation without adding capability.

## 3. Onboarding

**Rating: 4/5 — Advanced foundation**  
**Backend depth: 5/5**  
**AI: No**

### 3.1 Launch checklist

The platform-managed `shop_launch_v1` program contains sixteen tasks:

#### Core

- Company Profile — required.

#### Billing

- Stripe Payments — recommended and conditional when payments are used.

#### Team

- Employees and Roles — recommended.

#### Production

- Production Workflow — recommended.

#### Pricing

- Pricing Setup Assistant — required.
- Historical Invoice Import — optional.
- Product and Service Categories — recommended.

#### Templates

- Order Templates — recommended.
- Questionnaires — recommended.

#### Portal

- Customer Portal — recommended.
- Test Portal — recommended.

#### Documents

- Documents — recommended.

#### Communications

- Notifications — recommended.

#### Operations

- First Order — required.

#### AI

- AI Credits and Limits — recommended.

#### Commercial

- Setup Package Handoff — optional.

### Checklist behavior

- Platform-managed, versioned onboarding program.
- One tenant-scoped onboarding instance.
- Per-task state.
- Required, recommended, and optional levels.
- Dependency display.
- Not Started, In Progress, Completed, Skipped, Deferred, and Blocked statuses.
- Progress bar and completed/total count.
- Required-task count in the backend response.
- Recommended next task, prioritizing required tasks.
- Complete action.
- Skip action.
- Owner/admin write restriction.
- Staff read access.
- Customer portal identities denied.
- Audited status changes.

### Canonical completion detection

The dashboard checks real tenant records and automatically recognizes completion for:

- Company profile settings.
- Stripe billing account.
- Additional active employees/users.
- Active production workflow.
- Applied pricing quiz.
- Historical invoice import record.
- Pricing categories after pricing setup.
- Active tenant templates.
- Enabled/active customer portal.
- Documents.
- Questionnaire templates.
- Notification preferences.
- Test Portal response.
- First Order.
- AI governance policies.
- Setup-package handoff.

**Rating: 5/5 — Standout foundation**

This is the correct architecture: onboarding observes and calls canonical services rather than storing a second version of company, pricing, template, portal, or order truth.

### Checklist gaps

- Task dependencies are displayed but not enforced when a user manually marks a task complete.
- The checklist does not provide a description, explanation, route, or action button for each task.
- Complete and Skip are icon-only actions.
- The page cannot set In Progress, Deferred, or Blocked even though the backend supports them.
- Skip reasons and deferred dates are supported by the backend but not collected in the UI.
- Overall percent complete counts all sixteen tasks equally; it is not a clear launch-readiness score based on the three required tasks.
- A required task can be manually marked complete without canonical completion evidence.
- There is no per-user onboarding, only tenant-level launch setup.
- No resume-tour, dismiss-tour, first-login walkthrough, or role-specific onboarding path.

### 3.2 Company Profile setup

- Shop name.
- Email.
- Phone.
- Website.
- Owner/admin Apply action.
- Writes approved values through the canonical Settings service.
- Backend also supports legal name, address, timezone, and branding values.
- Creates an onboarding response and completes the task.

**Rating: 3/5 — Solid**

The UI does not preload existing values and does not expose legal name, address, timezone, or branding.

### 3.3 Pricing Scenario

- Nine pricing categories:
  - Banners
  - Rigid Signs
  - Cut Vinyl
  - Digital Print
  - Vehicle Graphics
  - Apparel
  - Services
  - Promotional
  - Custom
- Project-duration input.
- Crew size.
- Material-cost estimate.
- Customer charge.
- Price floor.
- Difficulty value in state/backend contract.
- Backend supports design, install, setup, and finishing flags.
- Creates a canonical pricing-quiz submission.
- Displays derived suggestions.
- Applies accepted shop defaults through the canonical pricing service.
- Marks Pricing Setup Assistant complete after application.

**Rating: 3/5 — Solid but rough**  
**AI: No; the name “Pricing Setup Assistant” does not indicate a live model**

Important limitations:

- The UI displays raw JSON suggestions.
- It does not explain the math in ordinary language.
- It does not let the owner select individual suggested defaults; **Apply Suggested Defaults** submits the whole suggested defaults map.
- The visible page does not expose design/install/setup/finishing flags or a difficulty selector.
- Currency units are not clearly labeled.
- It duplicates part of the fuller Pricing Foundation setup experience instead of guiding users into it.

### 3.4 Historical Invoice Import

- File name.
- File type.
- File size in bytes.
- Import metadata record.
- Request-analysis flag.
- Provider-deferred boundary.
- Warning that no OpenAI, OCR, or provider call was made.
- Does not mutate invoices or payments.

**Rating: 1/5 — Foundation only**  
**AI: Planned / inactive**

This is not a file import. There is no uploader, file parsing, column mapping, duplicate preview, extraction, review table, or application step. The button correctly says **Record Import**, but the surrounding title can still imply more than it does.

### 3.5 Placeholder Exercise and template creation

- Canonical allowed-placeholder registry.
- Placeholder categories for customer, order, shop, and date/time tokens.
- Example email content.
- Customer-name and order-number sample context.
- Preview.
- Unknown-placeholder rejection.
- Missing-placeholder reporting.
- Canonical template validation.
- Save as a real reusable email template.
- Creates onboarding exercise history.
- Completes Order Templates after a canonical template is saved.
- No AI credits consumed.

**Rating: 4/5 — Advanced learning exercise**  
**AI: No**

The preview is displayed as raw JSON rather than a polished rendered message and missing-field checklist.

### 3.6 Setup Package handoff

- Detects the tenant’s setup-package purchase.
- Displays current handoff status.
- Displays package/message information.
- Mark Ready action.
- Supported backend states: Not Started, Ready for Intake, In Progress, Blocked, Complete.
- Does not create Stripe checkout or alter the commercial purchase.
- Uses the canonical setup-package purchase.

**Rating: 3/5 — Solid handoff**  
**AI: No**

The visible action can only mark the package Ready for Intake; there is no intake questionnaire, assignee, appointment, checklist, blocker reason, conversation, or owner-visible completion history.

### 3.7 Test Portal

- Record Manual Check button.
- Stores a tenant-scoped applied onboarding response.
- Marks Test Portal complete.

**Rating: 1/5 — Foundation only**  
**AI: No**

It does not open a portal, create a test identity, verify a magic link, run an approval flow, validate permissions, or capture test results. A manual button can mark the task complete without evidence.

## 4. Contextual Help

**Rating: 3/5 — Solid foundation**  
**Backend depth: 4/5**  
**AI: No**

### Reusable component behavior

- Help icon button.
- Popover content.
- Surface-key lookup.
- Optional module filter.
- Loading state.
- Component disappears when no help definition exists.

### Current registered contextual help definitions

1. Onboarding Dashboard — setup progress.
2. Pricing Quiz — provisional suggestions and approval.
3. Templates Editor — placeholders.
4. Billing Subscriptions — failed payments.
5. Studio Assistant — canonical Assistant boundary.

### Visible usage found in the current pages

- Onboarding page header.
- Pricing Scenario card.
- Placeholder Exercise card.
- Help Center header.

### Limitations

- Five definitions are far too few for the current application.
- No field-level help registry is exposed in the UI.
- No deep link to the related full article is rendered by the popover, even though `article_slug` is stored.
- No role-specific hint rendering.
- No feedback from the contextual popover.
- No screenshots or guided action.
- No analytics for frequently opened help or unresolved surfaces.
- The Help Center itself requests billing contextual help regardless of the article being viewed.

## 5. Community

**Rating: 2/5 — Basic UI / advanced backend**  
**Backend depth: 5/5**  
**AI: No**

### Community scopes

- Platform-wide spaces.
- Tenant-only spaces.
- Founders-only spaces.
- Active/archive state.
- Visibility policy.
- Posting policy.
- Moderation policy.
- Voting enabled/disabled.

### Post types

- Discussion.
- Question.
- Announcement.
- Showcase.
- Bug Report.
- Feature Request.

The visible Community form only offers Discussion, Question, and Showcase.

### Visible contributor features

- Select a visible non-Founder space.
- Create a post with type, title, and body.
- List accessible posts across spaces.
- Post status.
- Comment count.
- Vote count.
- Upvote.
- Pinned badge.
- Founder tab.
- Empty states.

### Advanced backend features

- Search by title/body.
- Filter by space, post type, and status.
- Pagination.
- Post detail with comments.
- Edit by author or moderator.
- Nested comment replies.
- Reply notification to the post author.
- Vote add/remove with idempotent counting.
- Rate limiting.
- Post reporting.
- Linked tenant record validation for Customer, Order, Task, and Work Order.
- Secret/token/header content rejection.
- Tenant/platform/founder visibility enforcement.
- Customer portal denial.
- Audit events.

### Moderation backend

- Hide/unhide.
- Lock/unlock.
- Pin/unpin.
- Archive/restore.
- Mark duplicate.
- Move between spaces.
- Moderation reason.
- Post history.
- Hide/unhide/archive/restore comments.

### Major UI gaps

- No create/manage/archive/restore Community space interface.
- No starter-space creation visible for a new tenant.
- If no accessible space exists, the Post button is disabled and the user cannot fix it from this page.
- No post-detail page or drawer.
- No comments are displayed or creatable despite showing comment counts.
- No nested replies.
- No post editing.
- No vote removal.
- No search, filters, pagination, or sort controls.
- No linked-record picker.
- No reporting action.
- No moderation controls.
- No author names, avatars, timestamps, or last-activity display.
- No notifications/preferences interface.
- No attachments.
- No unread/follow/subscription state.

## 6. Founders Community

**Rating: 2/5 — Basic read view**  
**Backend depth: 4/5**  
**AI: No**

### Backend features

- Founders-only space scope.
- Explicit access grant.
- Explicit revocation.
- Grant reason.
- Grant/revoke actor and timestamps.
- Founder flag synchronized to the user record.
- Platform-admin-only management.
- Founder space access revalidated against a fresh user record.
- Founder isolation tests.

### Visible Founders tab

- Lists Founder spaces.
- Lists Founder posts.
- Shows comment counts.
- Clear empty state explaining that access is explicitly granted.

### Missing Founder experience

- No create-post form for Founder spaces.
- No post detail or comments.
- No voting.
- No founder directory.
- No Founder badge/profile indicator.
- No grant/revoke management UI.
- No onboarding benefit or program explanation.
- No dedicated announcements, feedback sessions, release previews, or founder-only roadmap.

## 7. Bug Reports

**Rating: 2/5 — Basic UI / advanced backend**  
**Backend depth: 5/5**  
**AI: No**

### Visible submission fields

- Title.
- Severity: Low, Medium, High, Critical.
- Reproducibility free-text field.
- Description.

### Visible tracking

- Current user’s reports.
- Title.
- Severity.
- Status.
- Description.
- Staff response when present.

### Backend report fields

- Steps to reproduce, up to twenty.
- Expected behavior.
- Actual behavior.
- Browser metadata.
- Up to five attachment file IDs.
- Tenant ownership validation for attachments.
- Idempotency key.
- Duplicate-of relationship.
- Linked support request.
- Submitter.
- Status lifecycle.

### Bug statuses

- Submitted.
- Triaged.
- Needs Info.
- Confirmed.
- In Progress.
- Fixed.
- Closed.
- Duplicate.
- Not Reproducible.

### Platform controls

- Update status.
- Add staff response.
- Link support request.
- Mark duplicate.
- Notify submitter about status changes.
- Audit changes.
- Platform admins can list all reports; normal users see only their own reports.

### Safety

- Browser metadata strips authorization, cookie, token, password, secret, and API-key-like fields.
- Only scalar allowlisted-style metadata values are retained.
- Attachments must belong to the report’s tenant.
- Cross-tenant linked support records are rejected.

### Major UI gaps

- No steps-to-reproduce editor.
- No expected-versus-actual fields.
- No automatic safe browser/app version capture.
- No screenshot/file attachment control.
- No affected page/route.
- No submit idempotency key from the page.
- No detail/history view.
- No Needs Info conversation.
- No duplicate link.
- No linked support ticket.
- No platform triage/admin interface.
- Severity is not constrained to an enum in the backend model/service even though the UI offers four options.

## 8. Feature Requests

**Rating: 3/5 — Solid contributor view**  
**Backend depth: 5/5**  
**AI: No**

### Visible contributor features

- Title.
- Free-text category.
- Description.
- Submit.
- Global feature-request list.
- Vote count.
- Upvote.
- Current status.
- Staff response.
- Sort from backend by vote count and then creation date.

### Status lifecycle

- Submitted.
- Under Review.
- Planned.
- In Progress.
- Released.
- Declined.
- Duplicate.

### Advanced backend behavior

- Tenant and submitter ownership fields.
- Idempotent submission contract.
- Platform-admin status and priority controls.
- Staff response.
- Duplicate relationship.
- Vote transfer from the duplicate request to the canonical request.
- Duplicate self-target prevention.
- Submitter notification on status change.
- Related release-note field in the model.
- Audit events.

### Major UI gaps

- No status/category/search filters.
- No roadmap grouping by Planned/In Progress/Released.
- No request detail/history.
- No comments or staff conversation.
- No attachment/mockup.
- No affected-module selector.
- Category is uncontrolled free text.
- No unvote.
- No “My Requests” view.
- No duplicate/canonical link display.
- No related release-note link.
- No platform roadmap/triage interface.
- The page does not send an idempotency key.

### Privacy/product decision to confirm

The backend intentionally lists feature requests across all tenants, allowing a shared platform roadmap and voting pool. The response also includes internal tenant and submitter IDs. The UI does not display those IDs, but the public response shape should be minimized to fields actually intended for cross-tenant community visibility.

## 9. Contact Support

**Rating: 2/5 — Conflicted implementation**  
**Routed Support backend: 5/5**  
**AI: No**

There are two separate support systems.

### System A — Routed Community Support Requests

Used by `/help/contact` and the Support tab in `CommunityPage`.

#### Visible request types

- Shop Configuration Question.
- Internal Workflow Help.
- Local Employee Access Help.
- Tenant Operational Issue.
- Product Bug.
- Feature Request.
- Login or Platform Access.
- Privacy or Data Request.

#### Additional backend-supported types not shown in the page

- Billing Platform Issue.
- Platform Service Problem.

#### Routing behavior

- Shop/workflow/employee/configuration issues route to tenant admins when an active owner/admin exists.
- If no tenant admin exists, those requests route to platform admins.
- Product bugs, feature requests, login/platform access, billing/platform, privacy, and platform-service issues route to SignGuy platform admins.
- The page previews the destination before submission.
- A user-supplied destination cannot override routing rules.

#### Backend support-ticket features

- Subject and description.
- Requester and tenant.
- Open, Acknowledged, Waiting on User, Waiting on Support, Resolved, and Closed statuses.
- Priority.
- Assignment.
- Tenant-admin versus platform-admin visibility.
- Route history.
- Linked Customer.
- Linked Order.
- Linked Task.
- Linked Bug Report.
- Linked Feature Request.
- Cross-tenant link validation.
- Idempotent creation contract.
- Internal support notes.
- Internal-note visibility restriction.
- Closed timestamp.
- Notifications to tenant owners, platform admins, and requester.
- Audit history.

#### Visible limitations

- Only request type, route preview, subject, and description can be entered.
- No record linking.
- No attachment.
- No ticket detail.
- No conversation/replies.
- No status timeline.
- No update, close, reopen, or priority actions.
- No assignment interface.
- No internal-note interface.
- No service-level target or response-time display.
- The page does not send an idempotency key.

### System B — Help Center Support Escalations

Used by the Contact Support card embedded in `HelpCenterPage`.

- Subject.
- Message.
- Source surface.
- Open, Triaged, Resolved, and Closed statuses in the model.
- Tenant and creator.
- Idempotency.
- Audit event.

It does not use the routed support engine, request types, destination preview, assignments, internal notes, linked records, notifications, or ticket visibility rules.

### Canonical duplication defect

The EC19 preflight explicitly stated that the existing EC12 Support Request records would remain authoritative for support routing. The implementation nevertheless introduced `support_escalations` and wired the Help Center form to it. This creates two support queues and makes it possible for a Help Center request to bypass the actual routing/notification workflow.

**Required correction:** remove the duplicate escalation record path or convert it into a thin adapter that creates a canonical routed `SupportRequest` with `source_surface="help_center"`.

## 10. What’s New

**Rating: 1/5 — Foundation only**  
**Backend depth: 2/5**  
**AI: No**

### What exists

- Navigation item.
- Route at `/help/whats-new`.
- Release Notes category.
- One bootstrapped Release Notes article.
- Feature Request model has a related release-note ID field.

### Current behavior

The route opens the same unfiltered Help Center page as `/help`. The release-notes article contains one short sentence naming recent checkpoints. There is no route-aware selection or Release Notes filter.

### Missing What’s New features

- Release title and version.
- Release date.
- Detailed change list.
- Added/changed/fixed categories.
- Screenshots or demonstrations.
- Links to affected modules.
- Links from released feature requests.
- Read/unread state.
- New-release badge in navigation.
- Dismiss or Mark Read.
- Filter by release/date/module.
- Breaking-change or required-action notices.
- Release-note authoring/publishing UI.
- Email/in-app release announcement.

## 11. Help and Community administration

**Visible admin rating: 1/5 — Backend only**  
**Backend depth: 5/5**  
**AI: No**

### Help administration available only through APIs

- Create/update article by slug.
- Draft/publish/archive lifecycle.
- Platform-admin restriction.
- Search keywords and module.
- Audience and version fields.
- Contextual help definitions through bootstrap/data layer.
- Audit records.

### Community administration available only through APIs

- Create/update/archive/restore spaces.
- Posting and voting policy.
- Hide/unhide/lock/pin/archive/move/duplicate posts.
- Moderate comments.
- Review reported posts.
- Founder grants/revocations.

### Product feedback administration available only through APIs

- Feature status/priority/staff response.
- Feature duplicate merge with vote transfer.
- Bug status/staff response/support link.
- Bug duplicate handling.

### Support administration available only through APIs

- Destination-aware visibility.
- Status and priority.
- Assignment validation.
- Internal notes.
- Requester notifications.
- Resolution/closed timestamps.

### Missing operational consoles

- Help Content Manager.
- Contextual Help Manager.
- Community Space Manager.
- Moderation Queue.
- Founder Program Manager.
- Bug Triage Board.
- Feature Roadmap Board.
- Tenant Support Queue.
- Platform Support Queue.
- Help feedback analytics.

Without these surfaces, the system can accept community and support data but ordinary administrators cannot operate the lifecycle through the product.

## 12. Permissions and access

### Current permission set

- `help:read`
- `help:manage`
- `onboarding:read`
- `onboarding:write`
- `community:read`
- `community:post`
- `community:moderate`
- `support:read`
- `support:write`

### Default roles

- Owner/admin receive the full permission catalog.
- Staff receive Help read, Onboarding read, Community read/post, and Support read/write.
- Onboarding write is additionally restricted to owner/admin in the page and service.
- Platform master Help content and platform/founder spaces require platform-admin authority.
- Portal identities are blocked from internal Help, Onboarding, and Community routes.

### UI permission mismatch

`CommunityPage` loads spaces, posts, feature requests, bug reports, and support requests together through one `Promise.all`, regardless of the active route or permissions. A custom role that can read Community but not read Support can fail the entire Community page. Likewise, the page renders post, feature, bug, vote, and support-create controls without checking the corresponding write permissions; the backend correctly rejects unauthorized actions, but the UI should hide or disable them.

### Article-read mismatch

As noted earlier, `include_archived=true` bypasses the published-only filter without a platform-admin check, and article audiences are not enforced.

## 13. Notification and audit coverage

**Rating: 4/5 — Advanced backend**  
**AI: No**

### Notifications

- Community reply notification to the post author.
- Feature-request status notification to the submitter.
- Bug-report status notification to the submitter.
- Tenant support request notification to tenant owners.
- Platform support request notification to platform admins.
- Support status notification to the requester.

### Audit events

- Space create/update/archive/restore.
- Post create/edit/moderate/report.
- Comment create/moderate.
- Vote changes.
- Feature create/status/duplicate.
- Bug create/status/duplicate.
- Founder grant/revoke.
- Support create/status/internal note.
- Onboarding task and setup actions.
- Help article changes.
- Help support escalation.

### Limitations

- Notification failures are intentionally swallowed, so core actions still succeed; the UI does not show delivery state.
- No notification preference controls are exposed in Help & Community.
- No digest, follow, watch, mention, or moderator-notification workflow.
- No admin audit/history view is linked from community or support records.

## 14. Features by advancement

### Standout / 5-level foundations

- Canonical onboarding completion detection across settings, pricing, workflows, templates, portals, documents, orders, AI governance, and setup packages.
- Routed Support Request backend with tenant/platform destinations, link validation, assignments, notes, notifications, and audits.
- Community scope enforcement across platform, tenant, and Founder spaces.
- Feature duplicate merge with vote transfer.

### Advanced / 4-level capabilities

- Versioned tenant onboarding program and task-state model.
- Pricing Scenario routed through canonical Pricing Quiz application.
- Placeholder exercise routed through canonical Template validation/rendering.
- Community moderation backend.
- Bug-report safety, lifecycle, and attachment/link validation backend.
- Notification and audit coverage.
- Failed-subscription guidance that does not mutate billing.

### Solid / 3-level capabilities

- Help Center search and categories.
- Article feedback.
- Onboarding Company Profile setup.
- Setup Package handoff.
- Contextual Help foundation.
- Feature Request contributor view.

### Basic / 2-level capabilities

- Documentation route.
- Community contributor page.
- Founders read view.
- Bug Reports page.
- Contact Support visible workflow because of duplicate systems and missing ticket interaction.

### Foundation / 1-level capabilities

- What’s New.
- Historical Invoice Import analysis.
- Test Portal validation.
- Help content administration UI.
- Community moderation/admin UI.
- Bug, feature, Founder, and support operations consoles.

## 15. Features absent from the current experience

- Complete in-app documentation for every main area/module.
- Guided tours and coach marks.
- First-login role-specific onboarding.
- Interactive tutorials or sandbox data.
- Video/GIF help.
- Real article deep links and table of contents.
- Help search analytics and unanswered-search reporting.
- Article authoring/publishing interface.
- Contextual help authoring interface.
- Community space management UI.
- Post detail/comments/replies.
- Community search and filters.
- User profiles, follows, mentions, bookmarks, or subscriptions.
- Community attachments.
- Moderation queue and moderator tools.
- Founder program management UI.
- Full bug-report form and attachment capture.
- Automatic safe environment/app-version capture.
- Bug triage board.
- Feature roadmap board.
- Canonical release-note linkage.
- Full support conversation and ticket detail.
- Tenant/platform support administration console.
- SLA, response time, or support availability display.
- Real release feed and unread What’s New state.
- Any AI-powered Help & Community workflow.

## 16. Highest-value corrections

1. Consolidate Help Center `support_escalations` into the canonical routed `support_requests` system.
2. Build one Support ticket detail/conversation experience for requester, tenant admin, and platform admin.
3. Fix Help article authorization: only platform admins may include draft/archived content, and audience must be enforced.
4. Make Documentation either a real structured knowledge base or remove its duplicate menu item.
5. Make What’s New a real release feed with versions, dates, module links, read state, and released-feature links.
6. Add Community post detail, comments, replies, editing, search, filtering, and vote removal.
7. Add Community space creation/management and ensure every eligible tenant has a usable starter space.
8. Add permission-aware data loading and controls to `CommunityPage`; do not require every Community/Support permission to load every tab.
9. Expose the full Bug Report fields, automatic safe environment capture, attachments, status history, and Needs Info conversation.
10. Build platform Bug Triage and Feature Roadmap consoles using the already-complete backend lifecycle.
11. Add Founder access management and Founder posting/commenting.
12. Make onboarding checklist tasks open the exact canonical setup screen and enforce required completion evidence.
13. Separate required launch readiness from overall optional/recommended completion percentage.
14. Replace raw JSON in Pricing and Placeholder exercises with readable previews and selective approval.
15. Turn Test Portal into a real guided portal verification flow.
16. Expand contextual help and documentation coverage across every main area before launch.

## 17. Recommended final Help & Community structure

The current eight-item menu is too fragmented for the amount of visible content. A cleaner final structure is:

1. **Help Center**
   - Search
   - Documentation
   - Role Guides
   - Contextual Help
2. **Onboarding**
   - Launch Checklist
   - Guided Setup
   - Setup Package
3. **Community**
   - Discussions
   - Questions
   - Showcases
   - Founders
4. **Feedback**
   - Bug Reports
   - Feature Requests
5. **Support**
   - New Request
   - My Requests
   - Tenant Support Queue for authorized admins
6. **What’s New**

This preserves all required features while reducing repeated top-level destinations. If the product keeps eight menu items, Documentation and What’s New must become genuinely distinct pages rather than aliases.

## 18. Verification evidence

### Community/support backend coverage

Three focused backend tests verify:

- Tenant, platform, and Founder spaces.
- Cross-tenant space isolation.
- Post idempotency.
- Comments.
- Idempotent voting.
- Secret-like content rejection.
- Pinning and voting disablement.
- Founder access grants.
- Portal denial.
- Feature idempotency, voting, status, and duplicate merge.
- Bug idempotency, metadata sanitation, status, and duplicate handling.
- Tenant versus platform support routing.
- Destination-override rejection.
- Cross-tenant bug/feature link rejection.
- Support idempotency.
- Tenant/platform visibility.
- Internal notes.
- Assignment restrictions.
- Resolution timestamps.
- Notifications.

### Onboarding/help backend coverage

Three focused backend tests verify:

- Idempotent platform bootstrap.
- Owner/admin write and staff read boundaries.
- Portal denial.
- Canonical Company Profile application.
- Pricing scenario and applied suggestions.
- Historical-import provider-deferred state and no invoice/payment mutation.
- Placeholder registry, missing values, and unknown-token rejection.
- Canonical template creation with no AI usage.
- Setup-package handoff without creating checkout.
- Tenant isolation.
- Help article draft/publish visibility.
- Search.
- Contextual help.
- Role guides.
- Idempotent feedback.
- Help support escalation creation.
- Read-only failed-subscription guidance.
- Platform-admin article management.

### Frontend coverage

Two focused frontend tests cover:

- Onboarding dashboard rendering.
- Progress and recommended task.
- Setup package visibility.
- Placeholder preview.
- Help articles.
- Billing guidance.
- Article feedback.
- Help Center support submission.

There is no focused frontend Community page test in the audited tree. Backend tests do not prove that comment, moderation, triage, Founder management, or support administration is usable through the interface.

## 19. Principal code evidence

The audit was grounded primarily in current navigation/router code, frontend pages, backend models/services/routers, focused tests, and module documentation, including:

- [Help & Community navigation](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/frontend/src/lib/navigation.js)
- [Application routes](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/frontend/src/App.js)
- [Help Center page](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/frontend/src/pages/HelpCenterPage.jsx)
- [Onboarding page](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/frontend/src/pages/OnboardingPage.jsx)
- [Community, Bugs, Features, Founders, and Support page](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/frontend/src/pages/CommunityPage.jsx)
- [Contextual Help component](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/frontend/src/components/help/ContextualHelp.jsx)
- [Onboarding service](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/app/services/onboarding.py)
- [Onboarding models](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/app/models/onboarding.py)
- [Onboarding router](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/app/routers/onboarding.py)
- [Help Center service](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/app/services/help_center.py)
- [Help Center router](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/app/routers/help_center.py)
- [Community and support service](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/app/services/community_service.py)
- [Community models](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/app/models/community.py)
- [Community router](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/app/routers/community.py)
- [Permission catalog and default roles](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/app/core/permissions.py)
- [Community/support tests](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/tests/test_ec12_phase12g_community_support.py)
- [Onboarding/help tests](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/backend/tests/test_ec19_onboarding_help.py)
- [Onboarding/help frontend tests](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/frontend/src/__tests__/ec19.onboarding-help.test.jsx)
- [EC19 module documentation](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/docs/modules/ec19_onboarding_help_center.md)
- [EC19 preflight](https://github.com/dnblack323/SIGNGUY-MVP/blob/5c5303e9216c8013c8ec793f2574aba3f559d6d1/preflight/EC19_ONBOARDING_HELP_CENTER_CONTEXTUAL_HELP_AND_APP_DOCUMENTATION_PREFLIGHT.md)

## Final verdict

Help & Community is **a strong backend system presented through an incomplete frontend**. Onboarding is credible and correctly connected to canonical setup records. Community, Bugs, Features, Founder access, and routed Support have serious production-shaped service logic. The safety work—tenant isolation, portal denial, secret filtering, attachment validation, moderation, duplicate handling, routing, notifications, and auditing—is better than the visible page suggests.

The section is not launch-complete because ordinary users and administrators cannot use most of those capabilities. Documentation and What’s New are duplicate routes, Community has no comments or management, Bug Reports collects too little diagnostic information, and Contact Support is split across two queues. The duplicate support system is the first defect to fix because it creates operational confusion and contradicts the stated single-source-of-truth design.

After support is consolidated, the best return comes from exposing the backend already built: post detail/comments, Community spaces, bug triage, feature roadmap, Founder management, support ticket detail, and content administration. No AI work is needed to make this section strong; the missing work is product completion, content depth, permissions, and operational UI.
