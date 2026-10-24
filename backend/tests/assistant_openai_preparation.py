"""Offline evaluation preparation. No live command or provider client is defined here.

From backend: python -m tests.assistant_openai_preparation check-key | verify-project | dry-run
The normal application/Gateway remain authoritative. These test-only instruments
restrict one isolated evaluation; Docker excludes backend/tests and backend/.env.
"""

from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING
from datetime import datetime, timezone
import argparse
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from unittest.mock import patch
import uuid

CONFIG_PATH = Path(__file__).with_name("assistant_openai_evaluation.json")
BACKEND = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND / ".env"
RECEIPT_PATH = BACKEND.parent / ".cache/assistant-evaluation/project-verification.json"


def dedicated_credentials():
    """Only this worktree's file, never process/user/machine credential fallback."""
    from dotenv import dotenv_values

    values = dotenv_values(ENV_PATH, interpolate=False)
    key = values.get("OPENAI_API_KEY") or ""
    reject = values.get("ASSISTANT_EVALUATION_REJECT_KEY_SHA256") or ""
    if not key or not key.startswith("sk-") or any(part.isspace() for part in key):
        raise EvaluationStopped(
            "Install the dedicated project key in the worktree backend .env"
        )
    if not re.fullmatch(r"[a-f0-9]{64}", reject):
        raise EvaluationStopped("Dedicated-credential guard is missing")
    if hashlib.sha256(key.encode()).hexdigest() == reject:
        raise EvaluationStopped("The original shared key is forbidden for evaluation")
    if (
        values.get("ASSISTANT_EVALUATION_PROJECT_NAME")
        != configuration()["project_name"]
    ):
        raise EvaluationStopped("Evaluation project name does not match")
    project = values.get("OPENAI_PROJECT_ID") or ""
    previous = values.get("ASSISTANT_EVALUATION_PREVIOUS_PROJECT_ID") or ""
    if project and (
        not re.fullmatch(r"proj_[A-Za-z0-9_-]{1,160}", project) or project == previous
    ):
        raise EvaluationStopped("Use the dedicated evaluation project ID")
    if any(
        values.get(name, "false").lower() != "false"
        for name in (
            "AI_ENABLED",
            "ASSISTANT_TEXT_ENABLED",
            "ASSISTANT_REALTIME_ENABLED",
            "OPENAI_REALTIME_ENABLED",
        )
    ):
        raise EvaluationStopped(
            "Keep paid execution flags disabled until owner authorization"
        )
    return key, project, previous


def verified_credentials():
    key, expected, previous = dedicated_credentials()
    try:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        elapsed = (
            datetime.now(timezone.utc) - datetime.fromisoformat(receipt["checked_at"])
        ).total_seconds()
        if not (
            0 <= elapsed <= 3600
            and receipt["key_sha256"] == hashlib.sha256(key.encode()).hexdigest()
            and receipt["project_id"] != previous
            and (not expected or receipt["project_id"] == expected)
            and receipt["models"]
            == ["gpt-6-luna", "gpt-realtime-2.1", "gpt-transcribe"]
        ):
            raise ValueError()
    except (OSError, ValueError, KeyError, TypeError):
        raise EvaluationStopped(
            "Run the nonbillable verify-project check after installing or changing the key"
        ) from None
    return key, receipt["project_id"]


def verify_project():
    """Exactly three GETs to OpenAI model metadata; no inference/admin calls."""
    import httpx

    logging.getLogger("httpx").setLevel(logging.WARNING)
    key, expected, previous = dedicated_credentials()
    headers = {"Authorization": "Bearer " + key}
    if expected:
        headers["OpenAI-Project"] = expected
    project_ids = set()
    models = ["gpt-6-luna", "gpt-realtime-2.1", "gpt-transcribe"]
    with httpx.Client(
        base_url="https://api.openai.com",
        headers=headers,
        follow_redirects=False,
        trust_env=False,
        timeout=15,
    ) as client:
        for model in models:
            try:
                response = client.get("/v1/models/" + model)
                if response.status_code != 200 or response.json().get("id") != model:
                    raise EvaluationStopped(
                        "Model metadata access failed; check project/key permissions"
                    )
                project = response.headers.get("openai-project", "")
                if project:
                    if (
                        not re.fullmatch(r"proj_[A-Za-z0-9_-]{1,160}", project)
                        or project == previous
                        or (expected and project != expected)
                    ):
                        raise EvaluationStopped(
                            "Provider project metadata does not match the dedicated evaluation project"
                        )
                    project_ids.add(project)
            except (httpx.HTTPError, ValueError):
                raise EvaluationStopped(
                    "Nonbillable project check failed; no paid request was attempted"
                ) from None
        if not project_ids:
            # Some model responses omit the project header. The authenticated
            # project context can still accompany a read-only management denial;
            # management permission itself is neither requested nor required.
            try:
                context = client.get("/v1/organization/projects")
                project = context.headers.get("openai-project", "")
            except httpx.HTTPError:
                raise EvaluationStopped(
                    "Project identity could not be read; no paid request attempted"
                ) from None
            if (
                not re.fullmatch(r"proj_[A-Za-z0-9_-]{1,160}", project)
                or project == previous
                or (expected and project != expected)
            ):
                raise EvaluationStopped(
                    "Installed key is not verified for the dedicated evaluation project; check its project in the dashboard"
                )
            project_ids.add(project)
    if len(project_ids) != 1:
        raise EvaluationStopped("Inconsistent provider project metadata")
    project = project_ids.pop()
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(
        json.dumps(
            {
                "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
                "project_id": project,
                "models": models,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "metadata_only": True,
            }
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "project_name_owner_confirmed": configuration()["project_name"],
                "project_id": project,
                "model_metadata_access": models,
                "inference_permission_not_exercised": True,
                "billable_requests": 0,
            }
        )
    )
    return 0


@contextmanager
def bind_dedicated_credentials(settings):
    """For the later authorized owned-DB runner; does not enable paid execution."""
    from app.core.test_isolation import validate_test_target

    validate_test_target(os.environ)
    key, project = verified_credentials()
    with patch.dict(os.environ, {"OPENAI_API_KEY": key, "OPENAI_PROJECT_ID": project}):
        apply_limits(settings)
        settings.openai_api_key = key
        try:
            yield project
        finally:
            settings.openai_api_key = None
            settings.assistant_text_enabled = False
            settings.assistant_realtime_enabled = settings.openai_realtime_enabled = (
                False
            )


def configuration():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["spending_authorized"] or config["preview"]["spending_authorized"]:
        raise ValueError("This preparation does not authorize spending")
    if (
        config["text"]["model"],
        config["voice"]["model"],
        config["voice"]["transcription_model"],
    ) != ("gpt-6-luna", "gpt-realtime-2.1", "gpt-transcribe"):
        raise ValueError("Model substitution requires owner review")
    return config


def cost_envelope(config=None):
    """Full uncached envelope in microdollars, including cache-write premium.

    Voice reserves every bounded input at the highest modality rate, including
    the existing 16,000-byte instruction ceiling, rather than estimating speech
    quality/length. Transcription includes the Gateway's flush-rounding reserve.
    This is not a provider bill and excludes unknown account taxes/surcharges.
    """
    c = config or configuration()
    t, v, p = c["text"], c["voice"], c["preview"]
    incoming = max(
        Decimal(t[k])
        for k in (
            "input_usd_per_million_tokens",
            "cached_input_usd_per_million_tokens",
            "cache_write_usd_per_million_tokens",
            "cache_write_12h_usd_per_million_tokens",
        )
    )
    text = (
        t["max_context_bytes"] * incoming
        + t["max_output_tokens"] * Decimal(t["output_usd_per_million_tokens"])
    ) * t["max_calls_total"]
    r = {k: Decimal(value) for k, value in v["realtime_pricing"].items()}
    voice = (
        (v["context_tokens"] + v["max_instruction_bytes"])
        * max(
            r[k] for k in ("input_text", "input_audio", "cached_text", "cached_audio")
        )
        + v["max_output_tokens"] * max(r["output_text"], r["output_audio"])
    ) * v["max_responses"]
    voice += (
        r["transcription_usd_per_minute"]
        * (v["max_seconds"] + v["max_responses"] + 1)
        * 1000000
        / 60
    )
    preview = p["max_requests"] * (
        p["max_input_tokens_per_request"] * r["input_text"]
        + p["max_output_tokens_per_request"] * max(r["output_text"], r["output_audio"])
    )
    ceil = lambda n: int(n.to_integral_value(rounding=ROUND_CEILING))
    result = {
        "text_micros": ceil(text),
        "voice_micros": ceil(voice),
        "evaluation_micros": ceil(text + voice),
        "preview_micros": ceil(preview),
    }
    if (
        result["evaluation_micros"] > c["budget"]["provider_cost_micros"]
        or result["preview_micros"] > p["ceiling_micros"]
    ):
        raise ValueError("Conservative envelope exceeds proposed allowance")
    return result


def apply_limits(settings):
    c = configuration()
    t, v = c["text"], c["voice"]
    settings.ai_enabled = False
    settings.assistant_text_enabled = False
    settings.assistant_realtime_enabled = settings.openai_realtime_enabled = False
    settings.assistant_text_model_profile_id = t["profile_id"]
    settings.assistant_voice_model_profile_id = v["profile_id"]
    for key, value in {
        "assistant_max_history_messages": t["max_history_messages"],
        "assistant_max_context_bytes": t["max_context_bytes"],
        "assistant_max_output_tokens": t["max_output_tokens"],
        "assistant_max_provider_calls": t["max_calls_per_turn"],
        "assistant_voice_max_seconds": v["max_seconds"],
        "assistant_voice_idle_seconds": v["idle_seconds"],
        "assistant_voice_max_responses": v["max_responses"],
        "assistant_voice_max_output_tokens": v["max_output_tokens"],
        "assistant_voice_context_tokens": v["context_tokens"],
        "openai_realtime_model": v["model"],
        "openai_realtime_voice": v["voice"],
        "openai_realtime_rate_limit_sessions": 1,
        "openai_realtime_rate_limit_window_seconds": 86400,
    }.items():
        setattr(settings, key, value)


async def prepare_disposable():
    from app.core.test_isolation import validate_test_target

    validate_test_target(os.environ)
    from app.core.config import get_settings
    from app.core.db import db
    from app.core.security import hash_password
    from app.services import ai_gateway
    from app.services.entitlements import _upsert_entitlement_for_tests

    c = configuration()
    apply_limits(get_settings())
    tenant = "assistant-evaluation-" + uuid.uuid4().hex
    user = {
        "id": uuid.uuid4().hex,
        "tenant_id": tenant,
        "role": "admin",
        "is_active": True,
        "email": "evaluation@example.test",
        "full_name": "Fictional Evaluation Admin",
        "password_hash": hash_password(uuid.uuid4().hex),
    }
    await db.tenants.insert_one(
        {"id": tenant, "slug": tenant, "name": "Fictional Evaluation Shop"}
    )
    await db.users.insert_one(user)
    await _upsert_entitlement_for_tests(
        tenant_id=tenant, feature_key="business_assistant", enabled=True
    )
    provider = "evaluation-provider"
    await db.ai_provider_configs.insert_one(
        {"id": provider, "provider_key": "openai", "status": "active"}
    )
    for kind, capability in (
        ("text", "assistant.chat"),
        ("voice", "assistant.voice_reply"),
    ):
        spec = c[kind]
        metadata = {
            "pricing_source": " ; ".join(c["pricing_sources"]),
            "pricing_checked": c["pricing_checked"],
        }
        if kind == "text":
            metadata.update(
                {key: value for key, value in spec.items() if "usd_per" in key}
            )
            metadata["reasoning_effort"] = spec["reasoning_effort"]
            metadata["service_tier"] = "default"
        else:
            metadata.update(
                realtime_pricing=spec["realtime_pricing"],
                transcription_model=spec["transcription_model"],
                supported_voices=c["preview"]["voices"],
            )
        await db.ai_model_profiles.insert_one(
            {
                "id": spec["profile_id"],
                "provider_config_id": provider,
                "provider_key": "openai",
                "model_key": spec["model"],
                "status": "active",
                "metadata": metadata,
            }
        )
        await db.ai_capabilities.update_one(
            {"capability_key": capability},
            {
                "$set": {
                    "id": "evaluation-" + kind,
                    "capability_key": capability,
                    "status": "active",
                    "feature_key": "business_assistant",
                    "entitlement_feature_key": "business_assistant",
                    "billable": True,
                    "default_credit_charge": 1,
                    "allowed_model_profile_ids": [spec["profile_id"]],
                }
            },
            upsert=True,
        )
    await db.ai_governance_policies.insert_one(
        {
            "id": uuid.uuid4().hex,
            "scope_type": "tenant",
            "scope_key": tenant,
            "tenant_id": tenant,
            "status": "active",
            "max_cost_micros_per_day": c["budget"]["provider_cost_micros"],
        }
    )
    await ai_gateway.grant_credits(
        {**user, "platform_admin": True},
        tenant,
        {
            "included_credits": c["budget"]["included_fixture_credits"],
            "reason": "Disposable evaluation fixture only; no commercial credit policy",
        },
    )
    await db.customers.insert_one(
        {
            "id": "evaluation-customer",
            "tenant_id": tenant,
            "name": "Fictional Sign Customer",
            "email": "fictional@example.test",
        }
    )
    await db.orders.insert_one(
        {
            "id": "evaluation-order",
            "tenant_id": tenant,
            "number": "EVAL-ORDER-1",
            "customer_id": "evaluation-customer",
            "status": "confirmed",
        }
    )
    await db.invoices.insert_one(
        {
            "id": "evaluation-invoice",
            "tenant_id": tenant,
            "order_id": "evaluation-order",
            "customer_id": "evaluation-customer",
            "number": "EVAL-INVOICE-1",
            "document_status": "issued",
            "total_cents": 12500,
            "due_date": "2026-01-01",
        }
    )
    return user


class EvaluationStopped(RuntimeError):
    pass


class EvaluationSupervisor:
    """Local-only instruments; injected transports default to DENY, never live.

    Future authorized evaluation must run in one process, retain this supervisor
    for its entire lifetime, and use normal Gateway/provider services. No resume,
    automatic retry, second session or alternate model is admitted here.
    """

    def __init__(self, user, *, text_transport=None, voice_transport=None):
        self.config = configuration()
        self.user = user
        self.text_transport, self.voice_transport = text_transport, voice_transport
        self.turn = ContextVar("evaluation_text_turn", default=None)
        self.text_turns = self.text_calls = self.voice_sessions = 0
        self.tool_counts = {}
        self.utterances = set()
        self.stopped = False
        self.key_pinned = False

    def require(self, condition):
        if self.stopped or not condition:
            self.stopped = True
            raise EvaluationStopped(
                "Evaluation stopped safely; no retry or additional dispatch"
            )

    def assert_runtime(self):
        from app.core.config import get_settings

        settings = get_settings()
        if self.key_pinned or (
            settings.openai_api_key and settings.openai_api_key.startswith("sk-")
        ):
            key, _ = verified_credentials()
            self.require(settings.openai_api_key == key)
            self.key_pinned = True
        self.require(
            settings.assistant_max_context_bytes <= 16384
            and settings.assistant_max_output_tokens <= 256
            and settings.assistant_max_provider_calls <= 2
            and settings.assistant_voice_max_seconds <= 60
            and settings.assistant_voice_idle_seconds <= 15
            and settings.assistant_voice_max_responses <= 4
            and settings.assistant_voice_max_output_tokens <= 256
            and settings.assistant_voice_context_tokens <= 2048
        )

    @contextmanager
    def instrument(self):
        from app.core.test_isolation import validate_test_target

        validate_test_target(os.environ)
        from app.services import (
            assistant_conversation,
            assistant_tools,
        )
        from app.services.assistant_voice_runtime import VoiceRuntime

        from app.core.config import get_settings

        settings = get_settings()
        self.assert_runtime()

        ask, execute, definitions, handle = (
            assistant_conversation.ask,
            assistant_tools.execute,
            assistant_tools.tool_definitions,
            VoiceRuntime.handle,
        )
        c = self.config

        async def guarded_ask(user, fields):
            self.assert_runtime()
            self.require(
                (user["tenant_id"], user["id"])
                == (self.user["tenant_id"], self.user["id"])
                and self.text_turns < c["text"]["max_turns"]
            )
            self.text_turns += 1
            token = self.turn.set(self.text_turns)
            try:
                return await ask(user, fields)
            finally:
                self.turn.reset(token)

        async def respond(payload):
            self.assert_runtime()
            payload = deepcopy(payload)
            payload["reasoning"] = {"effort": c["text"]["reasoning_effort"]}
            self.require(
                self.turn.get() is not None and self.text_transport is not None
            )
            self.require(
                self.text_calls < c["text"]["max_calls_total"]
                and payload["model"] == c["text"]["model"]
                and payload["max_output_tokens"] <= 256
                and len(json.dumps(payload, ensure_ascii=True).encode())
                <= c["text"]["max_context_bytes"]
            )
            self.text_calls += 1
            try:
                result = await self.text_transport(payload)
            except Exception:
                self.stopped = True
                raise EvaluationStopped(
                    "Text transport failed; evaluation stopped"
                ) from None
            calls = [
                row
                for row in result.get("output", [])
                if row.get("type") == "function_call"
            ]
            self.require(
                len(calls) <= 1
                and all(row.get("name") in c["read_tools"] for row in calls)
            )
            if (
                result.get("status") != "completed"
                or not result.get("usage")
                or not result.get("id")
            ):
                self.stopped = True  # Return evidence to normal accounting; prohibit any next call.
            return result

        async def create_call(offer, session):
            self.assert_runtime()
            self.require(self.voice_transport is not None and self.voice_sessions < 1)
            self.require(
                session["model"] == c["voice"]["model"]
                and session["max_output_tokens"] <= 256
                and session["audio"]["input"]["transcription"]["model"]
                == c["voice"]["transcription_model"]
                and session["truncation"]["token_limits"]["post_instructions"] <= 2048
            )
            self.voice_sessions += 1
            try:
                return await self.voice_transport(offer, session)
            except Exception:
                self.stopped = True
                raise EvaluationStopped(
                    "Voice admission failed; evaluation stopped"
                ) from None

        async def tool(user, name, args, **kwargs):
            self.assert_runtime()
            key = (
                ("text", self.turn.get())
                if self.turn.get() is not None
                else ("voice", kwargs.get("request_key", "").rsplit(":", 1)[0])
            )
            self.require(
                (user["tenant_id"], user["id"])
                == (self.user["tenant_id"], self.user["id"])
                and name in c["read_tools"]
                and self.tool_counts.get(key, 0) < 1
            )
            self.tool_counts[key] = self.tool_counts.get(key, 0) + 1
            return await execute(user, name, args, **kwargs)

        async def event(runtime, value):
            if self.stopped:
                await runtime.close("evaluation_stopped", uncertain=True)
                return
            try:
                self.assert_runtime()
            except EvaluationStopped:
                await runtime.close("evaluation_settings_changed", uncertain=True)
                return
            if value.get("type") in {
                "input_audio_buffer.committed",
                "conversation.item.input_audio_transcription.completed",
            }:
                self.utterances.add(value.get("item_id"))
                if len(self.utterances) > c["voice"]["max_utterances"]:
                    self.stopped = True
                    await runtime.close("evaluation_utterance_limit", uncertain=True)
                    return
            if value.get("type") == "response.done":
                calls = [
                    row
                    for row in value.get("response", {}).get("output", [])
                    if row.get("type") == "function_call"
                ]
                if len(calls) > 1 or any(
                    row.get("name") not in c["read_tools"] for row in calls
                ):
                    self.stopped = True
                    await runtime.close("evaluation_tool_limit", uncertain=True)
                    return
            await handle(runtime, value)
            if runtime.closing:
                self.stopped = True

        with ExitStack() as stack:
            for target, replacement in (
                ("app.services.assistant_conversation.ask", guarded_ask),
                ("app.services.openai_assistant_provider.respond", respond),
                ("app.services.openai_realtime_provider.create_call", create_call),
                ("app.services.assistant_tools.execute", tool),
                (
                    "app.services.assistant_tools.tool_definitions",
                    lambda user: [
                        item
                        for item in definitions(user)
                        if item["name"] in c["read_tools"]
                    ],
                ),
                ("app.services.assistant_voice_runtime.VoiceRuntime.handle", event),
            ):
                stack.enter_context(patch(target, replacement))
            try:
                yield self
            finally:
                settings.assistant_text_enabled = False
                settings.assistant_realtime_enabled = (
                    settings.openai_realtime_enabled
                ) = False


def check_local():
    try:
        dedicated_credentials()
        key_ready = True
        issue = None
    except EvaluationStopped as exc:
        key_ready, issue = False, str(exc)
    try:
        verified_credentials()
        project_ready = True
    except EvaluationStopped:
        project_ready = False
    print(
        json.dumps(
            {
                "backend_env_path": str(ENV_PATH),
                "dedicated_key_ready": key_ready,
                "project_metadata_recently_verified": project_ready,
                "issue": issue,
                "network_requests": 0,
            }
        )
    )
    return 0 if key_ready and project_ready else 1


async def dry_run():
    from app.core.db import ensure_indexes
    from app.core.config import get_settings
    from app.services import business_assistant, assistant_tools

    await ensure_indexes()
    user = await prepare_disposable()
    await business_assistant.assert_assistant_access(user)
    with EvaluationSupervisor(user).instrument():
        result = await assistant_tools.execute(
            user,
            "invoices",
            {"invoice_filter": "overdue"},
            timezone_name="UTC",
            request_key="dry:input:lookup",
        )
        if result["items"][0]["balance_due_cents"] != 12500:
            raise ValueError(
                "Fictional invoice fixture disagrees with canonical service"
            )
    settings = get_settings()
    assert (
        not settings.openai_api_key
        and not settings.assistant_text_enabled
        and not settings.assistant_realtime_enabled
    )
    print(
        json.dumps(
            {
                "prepared": True,
                "disposable_database": True,
                "fictional_invoice_cents": 12500,
                "network_requests": 0,
                "spending_authorized": False,
                "cost_envelope": cost_envelope(),
            }
        )
    )
    from app.core.db import get_client

    get_client().close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("check-key", "verify-project", "dry-run"))
    args = parser.parse_args()
    if args.operation == "check-key":
        return check_local()
    if args.operation == "verify-project":
        return verify_project()
    from tests import _test_env

    _test_env.start_run()
    _test_env.create_worker_database("main")
    os.environ["AUTH_DEV_BYPASS"] = "false"
    try:
        asyncio.run(dry_run())
    finally:
        _test_env.drop_worker_database()
        _test_env.finish_run()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvaluationStopped as exc:
        print(str(exc))
        raise SystemExit(1) from None
