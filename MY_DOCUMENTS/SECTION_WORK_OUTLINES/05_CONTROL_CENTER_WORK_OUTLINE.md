# Control Center — Work Outline

Control Center is the configuration and governance area. It should control how a shop's SignGuy AI account works without becoming a second location for normal daily operations.

## 1. Confirm what belongs in Control Center

- Company Settings
- Users, Roles, and Permissions
- Integrations
- Production Workflow configuration
- Pricing Defaults and the complete Pricing Foundation
- Subscriptions and AI Credits
- Feature Access and entitlements
- Portals and shared configuration where appropriate
- Data & Security
- Platform Governance and AI Governance for platform-authorized roles only

## 2. Separate shop settings from platform controls

- Clearly identify settings a shop owner may change.
- Keep SignGuy AI platform administration hidden from normal tenants.
- Separate tenant subscription billing from customer invoices and payments.
- Separate AI-provider governance from daily AI tool use.
- Prevent a normal shop owner from changing platform-wide defaults, plans, fees, or governance rules.

## 3. Correct the navigation

- Review the current Overview, Company Settings, Integrations, Production Workflows, Subscriptions, AI Credits, Feature Access, AI Governance, and Data & Security tabs.
- Add a clear Users, Roles, and Permissions destination if it is missing.
- Move Pricing Defaults from Business & Finance into Control Center.
- Decide whether Portals belongs as its own module or inside related settings.
- Hide platform-only modules unless the signed-in user has platform authority.

## 4. Decide internal tabs and ribbons

- Define internal tabs for Company, Users and Permissions, Integrations, Pricing Foundation, Production Workflows, Subscription, Credits, Feature Access, Portals, and Security.
- Keep Save, Test Connection, Invite User, Add Role, Run Pricing Quiz, Export Data, and similar actions in contextual ribbons.
- Do not repeat settings navigation as ribbon buttons.
- Add clear warnings and confirmation steps for changes that affect pricing, access, data, billing, or production workflows.

## 5. Create a complete Control Center feature audit

- Audit every visible setting and backend configuration contract.
- Identify working settings, saved-but-unused settings, platform-only controls, mock integrations, and placeholders.
- Trace which operational features actually consume each setting.
- Document permissions, tenant scope, audit history, defaults, validation, and rollback behavior.

## 6. Create and verify the Control Center gap list

- Number missing settings, dead controls, incorrect placement, permission problems, unsafe defaults, disconnected configuration, and incomplete integrations.
- Verify every finding against pages, APIs, models, settings services, provider adapters, permissions, tenant filters, audit logs, and tests.
- Separate tenant configuration gaps from platform governance gaps.
- Group the work into safe batches instead of changing every setting at once.

## 7. Complete company and user administration

- Company identity, contact details, locations, departments, hours, branding, numbering, locale, and general defaults
- User invitations, activation, deactivation, roles, permission groups, and access review
- Employee-account connections without confusing employee records with login accounts
- Owner/admin recovery and protection against removing the final authorized administrator
- Complete audit history for sensitive access changes

## 8. Complete integrations

- Email, file storage, Stripe, AI providers, and other approved connections
- Clear Connected, Needs Attention, Test, Disconnect, and Error states
- Secure secret handling without displaying stored credentials
- Tenant-specific versus platform-managed connections
- Webhook status, retry information, and integration activity where useful

## 9. Complete Pricing Foundation

- One dedicated area listing every default pricing value used by calculators
- Global Shop Rate quiz and detailed worksheets for labor, design, install, machine, overhead, and other rates
- Materials, components, services, markups, margins, waste, minimums, methods, category choices, and formula settings
- Category-specific setup and pricing quizzes
- Clear “show the math” explanations and test calculations
- A separate Benchmark Program Values section listing every field eligible for anonymous opt-in benchmarking
- Versioning and snapshots so changing today's default does not rewrite old Quotes or Orders

## 10. Complete production workflow configuration

- Workflow templates, stages, required steps, roles, departments, qualifications, equipment needs, and status rules
- Safe editing rules for workflows already used by Work Orders
- Versioning so new workflow changes do not corrupt historical production records
- Clear difference between configuring a workflow here and completing production work in Shop Operations

## 11. Complete subscriptions, credits, and feature access

- Current plan, add-ons, billing history, payment method, trial state, and subscription status
- AI credit balance, included credits, purchases, usage, and adjustments
- Entitlement checks that control access without destroying tenant data
- Clear handling for expired trials, failed platform payments, cancelled subscriptions, and reactivation
- Separate platform subscription charges from a shop's Stripe customer payments

## 12. Complete data, security, portals, and governance

- Audit logs, exports, retention, deletion requests, security status, and account protection
- Portal configuration shared by Customer Portal, Employee Portal, Webstore Owner Portal, and Wrap Lab where appropriate
- Platform Governance visible only to authorized platform roles
- AI Governance for providers, limits, review requirements, and platform policies
- Clear owner decisions for dangerous or irreversible controls

## 13. Clean up, test, and verify

- Remove dead settings and duplicate configuration pages.
- Refactor oversized settings, pricing, permissions, entitlement, integration, and governance files.
- Test that every saved setting is enforced by the correct operational workflow.
- Test tenant isolation, permissions, audit history, subscriptions, credits, provider failures, pricing snapshots, and workflow versioning.
- Run backend tests, frontend tests, and the frontend build.

## 14. Update the registers and perform the final review

- Record every fixed and remaining Control Center issue.
- Document sensitive owner decisions separately from implementation gaps.
- Add branch, commit, test, and limitation evidence.
- Perform a final Control Center code review with special attention to security, pricing, billing, permissions, and tenant separation.
