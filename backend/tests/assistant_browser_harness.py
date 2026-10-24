"""Run the real app in a disposable database, with a strictly local provider substitute.

python -m tests.assistant_browser_harness
No live keys, developer database, authentication override or paid request is used.
"""

import asyncio
import json
from pathlib import Path
import socket
import uuid

from tests import _test_env


async def serve():
    import os
    from app.core.test_isolation import validate_test_target

    validate_test_target(os.environ)
    from app.core.config import get_settings
    from app.core.db import db, ensure_indexes
    from app.core.security import hash_password
    from app.core.time_utils import utc_now
    from app.services import ai_gateway, openai_assistant_provider
    from app.services import business_assistant
    from app.core.assistant_voices import voice_options
    from app.services.entitlements import _upsert_entitlement_for_tests
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from server import app
    import uvicorn

    await ensure_indexes()
    tenant = "assistant-browser"
    user = {
        "id": "assistant-browser-owner",
        "tenant_id": tenant,
        "role": "owner",
        "is_active": True,
        "full_name": "Assistant Browser Owner",
        "email": "assistant-browser@example.com",
        "password_hash": hash_password("disposable-browser-password"),
    }
    await db.tenants.insert_one(
        {"id": tenant, "slug": tenant, "name": "Disposable Assistant Shop"}
    )
    await db.users.insert_one(user)
    await _upsert_entitlement_for_tests(
        tenant_id=tenant, feature_key="business_assistant", enabled=True
    )
    await db.ai_provider_configs.insert_one(
        {"id": "browser-provider", "provider_key": "openai", "status": "active"}
    )
    await db.ai_model_profiles.insert_one(
        {
            "id": "browser-profile",
            "provider_config_id": "browser-provider",
            "provider_key": "openai",
            "model_key": "local-scripted-fixture",
            "status": "active",
            "metadata": {
                "input_usd_per_million_tokens": "1",
                "output_usd_per_million_tokens": "2",
                "pricing_source": "local mock only",
            },
        }
    )
    await db.ai_capabilities.insert_one(
        {
            "id": "browser-chat",
            "capability_key": "assistant.chat",
            "status": "active",
            "feature_key": "business_assistant",
            "billable": True,
            "default_credit_charge": 1,
            "allowed_model_profile_ids": ["browser-profile"],
        }
    )
    await db.ai_governance_policies.insert_one(
        {
            "id": "browser-budget",
            "scope_type": "tenant",
            "scope_key": tenant,
            "tenant_id": tenant,
            "status": "active",
            "max_cost_micros_per_day": 1000000,
        }
    )
    await ai_gateway.grant_credits(
        {**user, "platform_admin": True},
        tenant,
        {"included_credits": 20, "reason": "Disposable browser smoke"},
    )
    await db.invoices.insert_one(
        {
            "id": "browser-invoice",
            "order_id": "browser-order",
            "tenant_id": tenant,
            "number": "B-1001",
            "document_status": "issued",
            "total_cents": 12500,
            "due_date": "2026-01-01",
            "created_at": utc_now().isoformat(),
        }
    )
    await db.customers.insert_one(
        {
            "id": "browser-customer",
            "tenant_id": tenant,
            "name": "Smith Construction",
            "email": "smith@example.test",
            "updated_at": utc_now().isoformat(),
        }
    )
    await db.orders.insert_one(
        {
            "id": "browser-order",
            "tenant_id": tenant,
            "number": "O-B-1001",
            "title": "Smith truck lettering",
            "customer_id": "browser-customer",
            "status": "confirmed",
            "created_at": utc_now().isoformat(),
        }
    )
    await db.quotes.insert_one(
        {
            "id": "browser-quote",
            "tenant_id": tenant,
            "number": "Q-B-1001",
            "customer_id": "browser-customer",
            "status": "sent",
            "updated_at": utc_now().isoformat(),
        }
    )
    settings = get_settings()
    settings.assistant_text_enabled = True
    settings.assistant_text_model_profile_id = "browser-profile"
    settings.openai_api_key = "mock-no-live-key"

    async def respond(payload):
        output = payload["input"][-1]
        prompt = ""
        for item in reversed(payload["input"]):
            if item.get("role") == "user":
                try:
                    prompt = (
                        json.loads(item.get("content", "{}"))
                        .get("user_message", "")
                        .casefold()
                    )
                except (TypeError, ValueError):
                    pass
                if prompt:
                    break
        if output.get("type") != "function_call_output":
            content = [
                {
                    "type": "function_call",
                    "name": "invoices",
                    "arguments": json.dumps({"invoice_filter": "overdue"}),
                    "call_id": uuid.uuid4().hex,
                }
            ]
            kind = (
                "internal_task"
                if "create a task" in prompt
                else (
                    "internal_note"
                    if "add a note" in prompt
                    else "email_draft" if "follow-up email" in prompt else None
                )
            )
            if kind:
                content = [
                    {
                        "type": "function_call",
                        "name": "propose_action",
                        "arguments": json.dumps(
                            {
                                "action_type": kind,
                                "title": (
                                    "Call Smith Construction"
                                    if kind == "internal_task"
                                    else (
                                        "Reflective vinyl request"
                                        if kind == "internal_note"
                                        else "Quote follow-up"
                                    )
                                ),
                                "body": (
                                    "Call about truck lettering"
                                    if kind == "internal_task"
                                    else "Requested reflective vinyl for their next truck"
                                ),
                                "due_when": (
                                    "tomorrow" if kind == "internal_task" else None
                                ),
                                "target_type": (
                                    "quote" if kind == "email_draft" else "customer"
                                ),
                                "target_id": (
                                    "browser-quote"
                                    if kind == "email_draft"
                                    else "browser-customer"
                                ),
                            }
                        ),
                        "call_id": uuid.uuid4().hex,
                    }
                ]
            if "remember" in prompt:
                content = [
                    {
                        "type": "function_call",
                        "name": "propose_memory",
                        "arguments": json.dumps(
                            {
                                "memory_key": "updates",
                                "content_text": "Prefer concise morning updates",
                                "source_type": None,
                                "source_id": None,
                            }
                        ),
                        "call_id": uuid.uuid4().hex,
                    }
                ]
            elif "smith" in prompt and not kind:
                content = [
                    {
                        "type": "function_call",
                        "name": "find_customers",
                        "arguments": json.dumps({"query": "Smith"}),
                        "call_id": uuid.uuid4().hex,
                    }
                ]
        else:
            content = [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Browser fixture: Invoice B-1001 has $125.00 overdue. This is a bounded invoice result; open the source record to review it.",
                        }
                    ],
                }
            ]
            if '"proposal_id"' in output.get("output", ""):
                content[0]["content"][0][
                    "text"
                ] = "Review the exact action preview and destination below. No business record has been created and no email sent. Confirm through the interface when ready."
            if '"memory_preview"' in output.get("output", ""):
                content[0]["content"][0][
                    "text"
                ] = "Review the memory suggestion in the memory editor and approve its exact wording. It has not been saved."
            elif '"Smith Construction"' in output.get(
                "output", ""
            ) and '"proposal_id"' not in output.get("output", ""):
                content[0]["content"][0][
                    "text"
                ] = "Smith Construction is the Customer in the linked application record."
        return {
            "id": uuid.uuid4().hex,
            "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 30},
            "output": content,
        }

    openai_assistant_provider.respond = respond
    voice_script = ""
    if os.environ.get("ASSISTANT_LOCAL_VOICE_MOCK") == "1":
        from tests.assistant_voice_browser import configure, SCRIPT

        await configure(settings, db)
        voice_script = SCRIPT
    if os.environ.get("ASSISTANT_STAGE_F_MOCK") == "1":
        from tests.assistant_stage_f_browser import configure as configure_stage_f

        await configure_stage_f(settings, db)
    build = Path(__file__).resolve().parents[2] / "frontend" / "build"
    app.mount("/static", StaticFiles(directory=build / "static"), name="smoke-static")
    # Optional owner-local review only. Unlicensed public documentation clips
    # are never in public/, a production image or an enabled production catalog.
    local_samples = build.parents[1] / ".cache/stage-c/voice-preview-recordings"
    if (
        os.environ.get("ASSISTANT_LOCAL_PREVIEW_REVIEW") == "1"
        and local_samples.is_dir()
    ):
        business_assistant.voice_options = lambda: voice_options(local_preview=True)
        app.mount(
            "/assistant-voice-samples",
            StaticFiles(directory=local_samples),
            name="smoke-voice-samples",
        )

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def frontend(frontend_path: str):
        if voice_script:
            return HTMLResponse(
                (build / "index.html")
                .read_text(encoding="utf-8")
                .replace("<head>", "<head>" + voice_script)
            )
        return FileResponse(build / "index.html")

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    print(f"DISPOSABLE ASSISTANT SMOKE http://127.0.0.1:{port}/login", flush=True)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    stop_file = Path(os.environ[_test_env.RUN_DIR_VAR]) / "assistant-smoke.stop"
    print(f"STOP_FILE {stop_file}", flush=True)

    async def watch_stop():
        while not server.should_exit:
            if stop_file.exists():
                server.should_exit = True
                return
            await asyncio.sleep(0.5)

    stop_task = asyncio.create_task(watch_stop())
    # Bounded lifetime even if a browser-check session is interrupted.
    asyncio.get_running_loop().call_later(900, setattr, server, "should_exit", True)
    try:
        await server.serve()
    finally:
        stop_task.cancel()
        print(
            "DISPOSABLE RECORD COUNTS "
            + json.dumps(
                {
                    name: await db[name].count_documents({"tenant_id": tenant})
                    for name in (
                        "tasks",
                        "internal_notes",
                        "ai_studio_editable_drafts",
                        "assistant_memory_entries",
                        "email_logs",
                    )
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    _test_env.start_run()
    _test_env.create_worker_database("main")
    try:
        asyncio.run(serve())
    finally:
        _test_env.drop_worker_database()
        _test_env.finish_run()
