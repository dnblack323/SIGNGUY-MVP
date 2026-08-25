# Repository and Product Documents to Keep

This is the plain-language retention list for important SignGuy product documents. The technical originals should remain in their established locations. This document records what they are for so they are not deleted, replaced, or confused with temporary prompts.

## Documents preserved inside `MY_DOCUMENTS`

### Current feature audits

- `CURRENT_FEATURE_AUDITS/SIGNGUY_MVP_Shop_Operations_Feature_Audit.md`
- `CURRENT_FEATURE_AUDITS/SIGNGUY_MVP_Business_and_Finance_Feature_Audit.md`
- `CURRENT_FEATURE_AUDITS/SIGNGUY_MVP_Team_and_Productivity_Feature_Audit.md`
- `CURRENT_FEATURE_AUDITS/SIGNGUY_MVP_Tools_and_Resources_Feature_Audit.md`
- `CURRENT_FEATURE_AUDITS/SIGNGUY_MVP_Help_and_Community_Feature_Audit.md`

These explain what each MVP section currently has, how advanced the features are, and whether AI is required.

### Section work outlines

The files in `SECTION_WORK_OUTLINES` explain what was done to Shop Operations and what process should be followed for every other section.

## Existing SIGNGUY-MVP technical records to keep in their current locations

- `/DONNELLS_WORKFLOW.md` — short current record of what was finished, what comes next, and what must not be started from the current branch.
- `/memory/progress_register.md` — detailed implementation progress.
- `/memory/MASTER_CHECKPOINT_CHECKLIST.md` — checkpoint completion record.
- `/memory/checkpoint_reference_table.md` — checkpoint and evidence reference.
- `/memory/code_issue_register.md` — current verified code issues and remaining open work.
- `/memory/CODE_ISSUE_REGISTER_FIX_PLAN.md` — plan for resolving registered code issues.
- `/memory/owner_specification_hold_register.md` — decisions that require Donnell's approval before implementation.
- `/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` — what each source repository contributed and how the MVP architecture is organized.
- `/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` — feature readiness and donor-repository evidence.
- `/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` — controlling consolidated MVP build plan.
- `/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md` — product scope and owner decisions.
- `/docs/architecture/navigation_contract.md` — approved app shell, sidebar, module tabs, ribbons, and permanent placement rules.
- `/preflight/` — approved plans and boundaries created before implementation.
- `/evidence/` — completion reports and verification evidence created after implementation.

These should not all be copied into `MY_DOCUMENTS`. The owner folder links and explains them while their authoritative technical copies remain where the development process expects them.

## Other SignGuy product documents to keep with their product work

- `Price_Lab_Windows_Implementation_Plan_Official.docx` — controlling Price Lab Windows product plan.
- `Price_Lab_Windows_Implementation_Plan.docx` — earlier repository-grounded Price Lab plan; retain as history but do not let it override the official plan.
- `SIGNGUY_SLIM_APP_VERSION_2_CODEX_BUILD_PROMPT.md` — approved Version 2 Slim scope.
- `SignGuy_Slim_Sidebar_Shell_and_Calendar_Implementation_Spec.docx` — Slim shell and calendar implementation standard.
- `SignGuy_Shared_Top_Layout_and_Calendar_Specifications.docx` — shared SignGuy interface standard used by MVP and Slim.

These documents describe what was completed, what each repository is responsible for, or what should be done next. They should be updated or superseded deliberately, never silently discarded.

## Simple update rule

After any major merged batch:

1. Update `DONNELLS_WORKFLOW.md` with Finished, Next, and Important.
2. Update the appropriate technical progress and issue registers.
3. Update the matching owner section outline with a short plain-language completion note.
4. Preserve the branch, pull request, merge commit, tests, and remaining limitations.
5. Replace an outdated owner document only when the new document clearly states what it supersedes.
