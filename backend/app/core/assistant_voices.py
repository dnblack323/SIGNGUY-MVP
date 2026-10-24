"""Shared documented Realtime voice catalog.

No provider call is required to list, select or preview these voices. Extend the
catalog only with a compatible voice and a commercially cleared preview asset.
Local test recordings are not licensed production assets.
"""

VOICE_KEYS = ("alloy", "ash", "coral", "echo", "sage", "shimmer")
DOCUMENTATION = (
    "https://developers.openai.com/api/docs/guides/realtime-conversations#voice-options"
)


def voice_options(*, local_preview: bool = False) -> list[dict]:
    return [
        {
            "key": key,
            "name": key.title(),
            "preview_path": (
                f"/assistant-voice-samples/{key}.wav" if local_preview else None
            ),
            "preview_kind": "local_review_only" if local_preview else "unavailable",
            "preview_available": local_preview,
        }
        for key in VOICE_KEYS
    ]


def voice_policy() -> dict:
    # Deliberately fail closed until D provides shared session/tool control and
    # trustworthy server-side usage/reservations. An API key alone is not consent.
    return {
        "stage": "selection_preview",
        "interactions_available": False,
        "paid_preview_available": False,
        "preview_provider_requests": 0,
        "preview_credit_charge": 0,
        "commercial_preview_available": False,
        "preview_unavailable_reason": "Voice previews need recordings cleared for commercial use. No paid preview is generated.",
        "message": "Live voice conversations are not available yet. Use text while voice integration is completed.",
    }
