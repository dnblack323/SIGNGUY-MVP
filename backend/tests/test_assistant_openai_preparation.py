"""No live providers: exact evaluation profiles, isolation and admission bounds."""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from types import SimpleNamespace
import uuid

import pytest
import httpx

from app.core.config import get_settings
from app.core.db import db
from app.services import (
    ai_gateway,
    ai_gateway_execution,
    assistant_conversation,
    assistant_tools,
    business_assistant,
    openai_assistant_provider,
    openai_realtime_provider,
)
from tests.assistant_openai_preparation import (
    EvaluationStopped,
    EvaluationSupervisor,
    apply_limits,
    configuration,
    cost_envelope,
    check_local,
    prepare_disposable,
    dedicated_credentials,
    verified_credentials,
    bind_dedicated_credentials,
    verify_project,
)
from tests import assistant_openai_preparation as preparation
from tests.test_assistant_stage_b import ctx  # noqa: F401
from tests.test_assistant_stage_d import v, start, utterance, answer  # noqa: F401


@pytest.fixture(autouse=True)
def restore_process_settings():
    settings = get_settings()
    prior = vars(settings).copy()
    yield
    vars(settings).clear()
    vars(settings).update(prior)


def test_exact_model_rates_limits_and_full_cost_envelope():
    c = configuration()
    assert not c["spending_authorized"] and not c["preview"]["spending_authorized"]
    assert c["text"]["model"] == "gpt-6-luna"
    assert c["voice"]["model"] == "gpt-realtime-2.1"
    assert c["voice"]["transcription_model"] == "gpt-transcribe"
    assert c["text"]["reasoning_effort"] == "none"
    assert cost_envelope() == {
        "text_micros": 16896,
        "voice_micros": 2380555,
        "evaluation_micros": 2397451,
        "preview_micros": 201408,
    }
    c["budget"]["provider_cost_micros"] = 1
    with pytest.raises(ValueError, match="envelope"):
        cost_envelope(c)
    settings = SimpleNamespace()
    apply_limits(settings)
    assert not settings.assistant_text_enabled and not settings.openai_realtime_enabled
    assert settings.assistant_max_context_bytes == 16384
    assert settings.assistant_max_provider_calls == 2
    assert settings.assistant_voice_context_tokens == 2048


@pytest.fixture
def dedicated_file(tmp_path, monkeypatch):
    # Synthetic credentials only; actual worktree .env is never read by tests.
    marker = "sk-test-not-a-real-openai-credential"
    path = tmp_path / ".env"
    receipt = tmp_path / "verification.json"
    path.write_text(
        "OPENAI_API_KEY=" + marker + "\nOPENAI_PROJECT_ID=proj_test_evaluation\n"
        "ASSISTANT_EVALUATION_PROJECT_NAME=SignGuy-MVP-Evaluation\n"
        "ASSISTANT_EVALUATION_PREVIOUS_PROJECT_ID=proj_old\n"
        "ASSISTANT_EVALUATION_REJECT_KEY_SHA256="
        + hashlib.sha256(b"old-shared-key").hexdigest()
        + "\n",
        encoding="utf-8",
    )
    receipt.write_text(
        json.dumps(
            {
                "key_sha256": hashlib.sha256(marker.encode()).hexdigest(),
                "project_id": "proj_test_evaluation",
                "models": ["gpt-6-luna", "gpt-realtime-2.1", "gpt-transcribe"],
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(preparation, "ENV_PATH", path)
    monkeypatch.setattr(preparation, "RECEIPT_PATH", receipt)
    return marker, path, receipt


def test_key_check_never_displays_key_or_inherited_credentials(
    dedicated_file, monkeypatch, capsys
):
    marker, _, _ = dedicated_file
    monkeypatch.setenv("OPENAI_API_KEY", "inherited-other-app-key")
    assert check_local() == 0
    output = capsys.readouterr().out
    assert marker not in output
    assert "inherited-other-app-key" not in output
    assert '"dedicated_key_ready": true' in output
    assert '"network_requests": 0' in output


def test_key_rotation_project_mismatch_and_stale_receipt_require_reverification(
    dedicated_file,
):
    _, path, receipt = dedicated_file
    assert verified_credentials()[1] == "proj_test_evaluation"
    initial = receipt.read_text()
    data = json.loads(initial)
    data["checked_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    receipt.write_text(json.dumps(data))
    with pytest.raises(EvaluationStopped):
        verified_credentials()
    receipt.write_text(initial)
    original = path.read_text()
    path.write_text(original.replace("proj_test_evaluation", "proj_other"))
    with pytest.raises(EvaluationStopped):
        verified_credentials()
    path.write_text(
        original.replace(
            "OPENAI_API_KEY=sk-test-not-a-real-openai-credential",
            "OPENAI_API_KEY=old-shared-key",
        )
    )
    with pytest.raises(EvaluationStopped):
        dedicated_credentials()


def test_dedicated_binding_overrides_inherited_settings_and_clears_afterward(
    dedicated_file, monkeypatch
):
    marker, _, _ = dedicated_file
    settings = get_settings()
    monkeypatch.setenv("OPENAI_API_KEY", "inherited-other-app-key")
    settings.openai_api_key = "inherited-other-app-key"
    settings.assistant_voice_max_seconds = 600
    settings.assistant_max_provider_calls = 30
    settings.ai_enabled = True
    with bind_dedicated_credentials(settings):
        assert settings.openai_api_key == marker
        assert settings.assistant_voice_max_seconds == 60
        assert settings.assistant_max_provider_calls == 2
        assert not settings.ai_enabled and not settings.assistant_text_enabled
    assert settings.openai_api_key is None
    assert not settings.openai_realtime_enabled


def test_project_verification_get_only_models_and_management_403_context(
    dedicated_file, monkeypatch, capsys
):
    marker, _, _ = dedicated_file
    requests = []
    original_client = httpx.Client

    def route(request):
        requests.append(request)
        assert request.method == "GET"
        if request.url.path == "/v1/organization/projects":
            return httpx.Response(
                403,
                headers={"openai-project": "proj_test_evaluation"},
                json={"error": "Management permission absent"},
            )
        return httpx.Response(200, json={"id": request.url.path.rsplit("/", 1)[-1]})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(route), **kwargs
        ),
    )
    assert verify_project() == 0
    assert len(requests) == 4
    assert verified_credentials()[1] == "proj_test_evaluation"
    assert marker not in capsys.readouterr().out


async def test_runtime_configuration_drift_blocks_provider_dispatch(ctx):
    settings = get_settings()
    apply_limits(settings)
    calls = []

    async def transport(payload):
        calls.append(payload)

    with EvaluationSupervisor(
        ctx["user"], text_transport=transport
    ).instrument() as supervisor:
        supervisor.turn.set(1)
        settings.assistant_voice_max_seconds = 600
        with pytest.raises(EvaluationStopped):
            await openai_assistant_provider.respond(
                {"model": "gpt-6-luna", "max_output_tokens": 256}
            )
    assert not calls


async def test_disposable_gateway_profiles_permissions_credits_and_budget():
    user = await prepare_disposable()
    c = configuration()
    await business_assistant.assert_assistant_access(user)
    staff = {**user, "role": "staff", "permissions": []}
    with pytest.raises(Exception):
        await business_assistant.assert_assistant_access(staff)
    assert not get_settings().openai_api_key  # pytest never reads the local key
    assert not get_settings().assistant_text_enabled
    result = await assistant_tools.execute(user, "invoices", {}, timezone_name="UTC")
    assert result["items"][0]["balance_due_cents"] == 12500
    credit = await ai_gateway.get_credit_account(user["tenant_id"])
    assert credit["available_credits"] == 3
    t, voice = c["text"], c["voice"]
    for capability, profile in (
        ("assistant.chat", t),
        ("assistant.voice_reply", voice),
    ):
        cap = await db.ai_capabilities.find_one({"capability_key": capability})
        assert cap["allowed_model_profile_ids"] == [profile["profile_id"]]

    async def admit(key, **updates):
        fields = dict(
            key=key,
            fingerprint=key,
            conversation_id="eval-convo",
            profile_id=t["profile_id"],
            max_input=16384,
            max_output=256,
            max_calls=2,
        )
        fields.update(updates)
        return await ai_gateway_execution.begin(user, **fields)

    action, profile, created = await admit("first")
    assert created
    repeated, _, created = await admit("first")
    assert not created and repeated["id"] == action["id"]
    with pytest.raises(ai_gateway.AIGatewayError):
        await admit("wrong-model", profile_id=voice["profile_id"])
    await db.ai_governance_policies.update_one(
        {"tenant_id": user["tenant_id"]}, {"$set": {"max_cost_micros_per_day": 1}}
    )
    with pytest.raises(ai_gateway.AIGatewayError, match="cost limit"):
        await admit("budget-exceeded")
    await db.ai_governance_policies.update_one(
        {"tenant_id": user["tenant_id"]}, {"$set": {"max_cost_micros_per_day": 4500000}}
    )
    await admit("second")
    await admit(
        "voice",
        profile_id=voice["profile_id"],
        capability_key="assistant.voice_reply",
        max_input=18048,
        max_output=256,
        max_calls=4,
        voice_seconds=60,
    )
    with pytest.raises(ai_gateway.AIGatewayError):
        await admit("no-credit")
    ledger = await db.ai_provider_cost_ledger_entries.find_one(
        {"action_request_id": action["id"]}
    )
    assert ledger["actual_cost_micros"] is None
    assert ledger["reconciliation_status"] == "reserved_maximum"
    assert (
        await db.ai_action_requests.count_documents(
            {"tenant_id": user["tenant_id"], "status": "executing"}
        )
        == 3
    )
    rejected = await db.ai_action_requests.find_one(
        {
            "tenant_id": user["tenant_id"],
            "idempotency_key": f"assistant:{user['id']}:no-credit",
        }
    )
    assert rejected["status"] == "blocked"
    assert (await ai_gateway.get_credit_account(user["tenant_id"]))[
        "reserved_credits"
    ] == 3


async def test_text_instructions_read_tool_followup_and_two_turn_limit(
    ctx, monkeypatch
):
    settings = get_settings()
    apply_limits(settings)
    settings.assistant_text_enabled = True
    settings.assistant_text_model_profile_id = ctx["profile"]["id"]
    await db.ai_model_profiles.update_one(
        {"id": ctx["profile"]["id"]},
        {
            "$set": {
                "model_key": "gpt-6-luna",
                "metadata.cached_input_usd_per_million_tokens": "0.01",
                "metadata.cache_write_usd_per_million_tokens": "0.125",
                "metadata.cache_write_12h_usd_per_million_tokens": "0.25",
            }
        },
    )
    payloads = []

    async def mocked(payload):
        payloads.append(payload)
        assert payload["model"] == "gpt-6-luna"
        assert payload["reasoning"] == {"effort": "none"}
        assert payload["max_output_tokens"] == 256
        assert [row["name"] for row in payload["tools"]] == ["invoices"]
        output = [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Fictional balance from the record.",
                    }
                ],
            }
        ]
        if len(payloads) == 1:
            output = [
                {
                    "type": "function_call",
                    "name": "invoices",
                    "arguments": "{}",
                    "call_id": "invoice-read",
                }
            ]
        return {
            "id": uuid.uuid4().hex,
            "status": "completed",
            "usage": {"input_tokens": 20, "output_tokens": 10},
            "output": output,
        }

    supervisor = EvaluationSupervisor(ctx["user"], text_transport=mocked)
    with supervisor.instrument():
        first = await assistant_conversation.ask(
            ctx["user"],
            {"message": "What is unpaid?", "idempotency_key": "evaluation-1"},
        )
        await assistant_conversation.ask(
            ctx["user"],
            {
                "message": "Which record supports that?",
                "conversation_id": first["conversation"]["id"],
                "idempotency_key": "evaluation-2",
            },
        )
        with pytest.raises(EvaluationStopped):
            await assistant_conversation.ask(
                ctx["user"],
                {"message": "Another question", "idempotency_key": "evaluation-3"},
            )
    assert len(payloads) == 3
    assert not settings.assistant_text_enabled


async def test_missing_transport_and_wrong_identity_cannot_dispatch(ctx):
    settings = get_settings()
    apply_limits(settings)
    with EvaluationSupervisor(ctx["user"]).instrument():
        with pytest.raises(EvaluationStopped):
            await openai_assistant_provider.respond(
                {"model": "gpt-6-luna", "max_output_tokens": 256}
            )
    with EvaluationSupervisor(ctx["user"]).instrument():
        with pytest.raises(EvaluationStopped):
            await assistant_tools.execute(
                {**ctx["user"], "tenant_id": "foreign"},
                "invoices",
                {},
                timezone_name="UTC",
            )


async def test_more_than_one_read_per_turn_fails_closed(ctx):
    apply_limits(get_settings())
    with EvaluationSupervisor(ctx["user"]).instrument():
        await assistant_tools.execute(
            ctx["user"],
            "invoices",
            {},
            timezone_name="UTC",
            request_key="action:utterance:one",
        )
        with pytest.raises(EvaluationStopped):
            await assistant_tools.execute(
                ctx["user"],
                "invoices",
                {},
                timezone_name="UTC",
                request_key="action:utterance:two",
            )


async def test_total_dispatch_cap_and_provider_failure_stop_without_retry(ctx):
    apply_limits(get_settings())
    calls = []

    async def mocked(payload):
        calls.append(payload)
        return {
            "id": uuid.uuid4().hex,
            "status": "completed",
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "output": [],
        }

    supervisor = EvaluationSupervisor(ctx["user"], text_transport=mocked)
    with supervisor.instrument():
        supervisor.turn.set(1)
        payload = {"model": "gpt-6-luna", "max_output_tokens": 256, "input": []}
        for _ in range(4):
            await openai_assistant_provider.respond(payload)
        with pytest.raises(EvaluationStopped):
            await openai_assistant_provider.respond(payload)
    assert len(calls) == 4

    async def unavailable(payload):
        raise RuntimeError("Provider unavailable")

    supervisor = EvaluationSupervisor(ctx["user"], text_transport=unavailable)
    with supervisor.instrument():
        supervisor.turn.set(1)
        for _ in range(2):
            with pytest.raises(EvaluationStopped):
                await openai_assistant_provider.respond(payload)
    assert supervisor.text_calls == 1


async def test_voice_profile_three_utterances_and_no_second_session(v):
    settings = get_settings()
    apply_limits(settings)
    settings.assistant_realtime_enabled = settings.openai_realtime_enabled = True
    settings.assistant_voice_model_profile_id = v["profile"]["id"]
    await db.ai_model_profiles.update_one(
        {"id": v["profile"]["id"]},
        {"$set": {"metadata.transcription_model": "gpt-transcribe"}},
    )
    transport = openai_realtime_provider.create_call  # Existing fixture's mock
    supervisor = EvaluationSupervisor(v["user"], voice_transport=transport)
    with supervisor.instrument():
        result, runtime, _ = await start(v)
        for number in range(3):
            await utterance(runtime, item=f"input-{number}")
            await answer(runtime, response=f"response-{number}")
        await utterance(runtime, item="input-3")
        assert runtime.closing and supervisor.stopped
        assert runtime.responses == 3
        assert len(supervisor.utterances) == 4
        with pytest.raises(EvaluationStopped):
            await openai_realtime_provider.create_call("v=0", {})
    assert supervisor.voice_sessions == 1
    assert not settings.assistant_realtime_enabled
