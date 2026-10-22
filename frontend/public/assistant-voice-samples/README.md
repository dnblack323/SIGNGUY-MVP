# Prerecorded voice previews

Public OpenAI documentation recordings downloaded October 21, 2026, without
credentials, speech generation or paid API calls. `sources.json` records each
exact source URL, original SHA-256 and bundled SHA-256. PCM audio is unchanged;
WAV headers are normalized to actual frame lengths for reliable browser seeking.

The official text-to-speech guide embeds the Alloy sample at this CDN location:
https://developers.openai.com/api/docs/guides/text-to-speech

This bounded catalog includes six voices with available samples and documented
Realtime support: Alloy, Ash, Coral, Echo, Sage and Shimmer. Ballad, Verse, Marin
and Cedar are documented Realtime voices but matching files at this public
sample location returned 404; do not fabricate their previews or silently use a
different voice. Revisit availability in Stage D. No personality is demonstrated
by these fixed recordings and no future model sound/latency is certified.

Realtime voice compatibility source:
https://developers.openai.com/api/docs/guides/realtime-conversations#voice-options
