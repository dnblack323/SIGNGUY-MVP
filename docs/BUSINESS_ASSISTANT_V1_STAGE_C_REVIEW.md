# Business Assistant V1 — Stage C boundary and review

October 21, 2026. The owner accepted Stage B and authorized Stage C implementation. This restores the original C/D split: **C = independent saved voice, existing sample playback and microphone/interface readiness; D = complete Realtime integration**. The earlier note combining Realtime into C is superseded. No paid generation, Stage D–F, merge or deployment is authorized.

Scoped code-quality assessment before implementation:

| Boundary | Assessment | Stage C change |
|---|---|---|
| Canonical User preferences and shared Assistant state | Keep | Validate compatible voice keys; extend the existing preferences response and settings. Preserve personality and conversation records. |
| Existing settings and full-page/floating panel | Needs bounded cleanup | Reuse the panel and media playback; add sample comparison and safe microphone readiness with cleanup, cancellation and text fallback. |
| Existing Realtime path | Incomplete for commercial activation | Preserve for D, fail closed before any paid session creation during C. Do not extend its separate prompts/tools or browser-derived usage. |
| Gateway credits, budgets and accounting | Keep | No generated preview endpoint or new ledger. Static samples and local microphone checks incur no provider usage. Full voice reservation, observation and enforced sessions remain D. |

Use only voices documented for Realtime and with a verified public prerecorded sample. Bundle samples with source attribution, fetched from the public documentation CDN without API credentials. Play only after a click; never synthesize a fallback. These samples demonstrate the voice, not a selected personality or future live quality. If samples cannot be obtained, disclose the unavailable preview rather than substituting another voice.

Verification: per-user/shop persistence, invalid voice rejection, all voice/personality combinations, no provider dispatch from selection/preview/readiness, local media start/stop/denial/cancellation/unmount, affected Stage B tests and production build. Live voice quality/latency is explicitly unverified.
