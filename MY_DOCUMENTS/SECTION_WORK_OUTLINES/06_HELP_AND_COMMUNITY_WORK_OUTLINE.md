# Help & Community — Work Outline

This section should help users learn the app, finish setup, find answers, report problems, request features, contact support, and participate in the SignGuy AI community. The existing Help & Community feature audit is the starting record.

## 1. Confirm what belongs in Help & Community

- Help Center
- Documentation
- Onboarding
- Community
- Bug Reports
- Feature Requests
- Contact Support
- What's New
- Keep internal platform management and moderation controls separate from the normal customer-facing experience.

## 2. Correct the module navigation

- Review whether all eight current modules need permanent top-level tabs.
- Group closely related destinations if the row becomes crowded.
- Make the Help Center the clear starting point.
- Keep onboarding easy to resume.
- Separate Community discussions from private support requests and bug reports.

## 3. Decide internal tabs and ribbons

- Define internal tabs for Help Center topics, documentation categories, onboarding progress, community feeds, bug status, feature-request status, support conversations, and release notes.
- Choose actions such as Search Help, Resume Setup, Ask Community, Report Bug, Request Feature, Contact Support, and View What's New.
- Do not use ribbon actions as duplicate navigation.
- Make public, tenant, staff, moderator, and platform-admin actions visibly different.

## 4. Update the complete feature audit

- Re-audit the existing Help & Community document against the newest code.
- Identify real content, real submission workflows, static placeholders, disabled controls, moderation tools, and backend-only foundations.
- Check search, attachments, notifications, status history, comments, votes, permissions, and tenant/public boundaries.
- Mark any AI search or guided help as optional; basic documentation and support must work without AI.

## 5. Create and correct the Help & Community gap list

- Number missing pages, placeholder buttons, broken submissions, missing status history, moderation risks, permission problems, and incomplete onboarding steps.
- Separate content-writing needs from application-code gaps.
- Separate public community features from private tenant support records.
- Group shared needs such as attachments, notifications, search, comments, and moderation.

## 6. Verify gaps against the code

- Inspect pages, routes, APIs, models, services, permissions, tenant/public scope, notifications, moderation, and tests.
- Confirm that submitted bugs, feature requests, and support messages are actually stored and manageable.
- Confirm that users can return to their submissions and see real status.
- Require evidence before calling a help or community workflow complete.

## 7. Complete Help Center and Documentation

- Searchable help landing page organized by plain-language tasks
- Documentation categories that match the current app navigation
- Contextual help links from important pages and forms
- Clear beginner instructions, examples, screenshots, and troubleshooting
- Version-aware content so old instructions do not describe removed navigation
- Helpful empty states and definitions inside the app

## 8. Complete onboarding

- Progress that saves and resumes
- Required versus optional steps
- Company, users, permissions, integrations, pricing, workflow, and feature setup links
- Guided test cases that prove important setup values work
- Clear completion state without blocking users from revisiting setup
- Non-AI onboarding path plus optional AI guidance where approved

## 9. Complete Community

- Posts, categories, comments, reactions or votes, search, notifications, and reporting
- Shop identity and profile visibility rules
- Moderation, removal, locking, and abuse controls
- Clear difference between general discussion, product help, feature requests, and private support
- Protection against spam and unsafe attachments

## 10. Complete Bug Reports and Feature Requests

- Structured submission forms with screenshots, attachments, steps, expected result, and actual result
- Statuses, comments, staff responses, duplicates, links, and notifications
- Voting or interest tracking for feature requests if approved
- Platform-admin tools for triage, assignment, priority, and resolution
- No false promise that a submission automatically becomes scheduled work

## 11. Complete Contact Support and What's New

- Private support conversations with status, priority, attachments, replies, and notifications
- Clear boundary between support and community posts
- Release notes connected to actual versions and meaningful changes
- What's New notices that can be dismissed and reviewed later
- Links from release notes to relevant documentation

## 12. Fix permissions, privacy, and moderation

- Protect private support messages and tenant-specific bug details.
- Keep platform moderation permissions separate from tenant roles.
- Prevent private files or customer information from becoming public community attachments.
- Add audit history for moderation and status changes.
- Test public, authenticated, tenant, staff, moderator, and platform-admin access separately.

## 13. Clean up, test, and verify

- Remove placeholder pages, dead buttons, duplicate submission forms, and outdated help copy.
- Refactor large help, community, support, notification, and attachment files.
- Test submissions, comments, votes, search, onboarding progress, attachments, notifications, moderation, permissions, and tenant separation.
- Run backend tests, frontend tests, and the frontend build.
- Review the actual user experience from a new shop owner's point of view.

## 14. Update the registers and perform the final review

- Record completed and remaining Help & Community issues.
- Separate missing written content from missing software behavior.
- Add branch, commit, tests, and limitation evidence.
- Perform a final category-specific code review and update the main issue register.
