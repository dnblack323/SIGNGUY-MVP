# Business Assistant V1 — minimal live-provider verification proposal

**Prepared only. NOT AUTHORIZED TO RUN.** Stage E authorization does not permit paid activation. Owner must separately approve this exact evaluation and a **$5 maximum total spend**. The six own-account voice previews remain a separate pending **$1** proposal in the Stage D report; they are excluded from this evaluation.

## Smallest evaluation

Use the existing Assistant/Gateway in a disposable shop, one temporary staff identity with only Assistant use and relevant read permissions, and clearly fictitious Customer/Order/invoice records. No production data, business writes, email sends, media retention, new models or public deployment. Existing private saved context may be pre-seeded locally to check continuity. API key stays backend-only and is removed from the test process after closure.

| Check | Exact cap | Evidence |
|---|---|---|
| One text conversation + follow-up | Two user turns, maximum two provider responses/turn; four total. Max 256 output tokens/response, 16-KiB complete request/context bound. | Actual provider response IDs, correct follow-up reference, authoritative record link, no invented financial amount. |
| One spoken conversation | One Realtime session, maximum 60 seconds, 15 seconds idle, three committed utterances and four model responses total. Max 256 output tokens/response, 2,048 post-instruction context tokens. No reconnect or automatic retry. | Successful unified SDP/sideband/audio, saved provider-observed input/output transcripts and shared conversation. |
| One read-only record lookup | Include in one of the above conversations; at most one application read tool call/turn. No separate evaluation request. | Compare one fixture balance/status directly with canonical application result. |
| One interruption | Interrupt one spoken response using the interface or speaking; counts within that session. | Audio stops, generated/unplayed transcript is marked, context remains consistent. |
| Basic usage/cleanup | No additional model calls. | Compare provider token/cache/modality and separate transcription usage with one Gateway accounting record/event; confirm hangup and release/reconciliation state. Dollar cost remains estimated until compared with actual provider billing. |

Maximum **eight model responses**, **two text turns**, **one voice session**, **three spoken utterances**. No previews, retries, second model or second session. A setup/provider failure consumes this attempt and stops the evaluation; a fresh attempt requires owner approval.

## Spending enforcement and estimate

Before any paid dispatch, verify the exact approved text profile, `gpt-realtime-2.1` and duration-priced input-transcription profile against official account-access and pricing information. Record the actual sourced rates; never replace them with remembered or fixture rates. Use a fresh disposable tenant's existing Gateway policy with a **$4.50 maximum provider-cost reservation**, leaving $0.50 contingency within the $5 owner ceiling, plus credits and request/session caps above. Compute and record conservative full-run liability from the enforced input/output/session bounds **before enabling the process**. If it cannot fit below $4.50, do not start; reduce limits in a revised owner-approved proposal. No other process may use this evaluation's provider budget/account credentials while it runs.

At the currently documented Realtime rates ($32/million input audio tokens, $64/million output audio tokens; text $4 input/$24 output), normal short useful exchanges are expected to cost substantially less than $5. This is a rate-based estimate, not verified billing. Realtime charges per response, and input transcription is billed separately. API project budget alerts alone are not a hard stop: the application must reserve the worst allowed session/request costs and stop using the existing server controls. Recheck rates, account-specific terms/tax treatment and the complete reservation calculation at authorization time; if a strict inclusive $5 bound cannot be established, do not run.

Official sources reviewed: [model rates](https://developers.openai.com/api/docs/models/gpt-realtime-2.1), [API pricing](https://developers.openai.com/api/docs/pricing), [Realtime usage and transcription costs](https://developers.openai.com/api/docs/guides/voice-latency-cost?voice-api=realtime).

## Immediate stopping conditions

Stop on the first unsupported protocol/model/voice/transcription format, missing usage, unsafe or unauthorized tool request, wrong fixture fact, unexpected provider response/request, privacy leak, failure to interrupt/hang up, budget/rate discrepancy, or inability to reconcile a previous request. Never release an uncertain cost allowance and continue spending. Close microphone, browser media, sideband and provider session; preserve redacted IDs/counts and existing ledger evidence for review. No silent model fallback or automatic paid retry.

Report each check as passed/failed/not reached, measured latency/quality separately, exact request/session counts, observed usage, estimated cost, and provider-verified monetary cost only if actually available. Owner decides any further live evaluation, preview generation or commercial activation. This proposal does not authorize Stage F, merge or deployment.
