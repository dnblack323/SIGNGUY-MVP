# Claude Code instructions for SIGNGUY-MVP

@AGENTS.md

## Claude Code specifics

- `AGENTS.md` (imported above) is the single source of operating rules, including the RTK command guidance. Do not duplicate or contradict it here.
- The current work item is the feature marked **CURRENT** in `docs/MVP_COMMERCIAL_V1_LAUNCH_PLAN.md`. If none is marked, stop and ask the owner which approved feature to start.
- Binding locked rules: `memory/AGENT_INSTRUCTIONS.md`; precedence and holds: `memory/documentation_authority_register.md`, `memory/owner_specification_hold_register.md`.
- Optional read-only subagents live in `.claude/agents/` (`token-optimizer`, `test-gatekeeper`, `review-gatekeeper`). Use one only when it clearly saves effort; never dispatch all three automatically.
- Do not repeat the completed audits. Do not modify Price Lab's working tree; read its `origin/main` only.
