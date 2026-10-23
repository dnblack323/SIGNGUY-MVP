"""One transport-independent, proposal-only model tool. No execution authority."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..core.db import db
from . import assistant_actions, assistant_tools


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_type: Literal["internal_task", "internal_note", "email_draft"]
    title: str = Field(max_length=160)
    body: str = Field(max_length=8000)
    subject: str | None = Field(default=None, max_length=160)
    due_when: str | None = Field(default=None, max_length=80)
    priority: Literal["low", "normal", "high", "rush"] = "normal"
    target_type: Literal["customer", "order", "quote"] | None = None
    target_id: str | None = Field(default=None, max_length=160)


def definition(user):
    from .business_assistant import ACTION_PERMISSIONS

    allowed = [
        k
        for k in sorted(assistant_actions.CONTROLLED)
        if all(assistant_tools.has_perm(user, p) for p in ACTION_PERMISSIONS[k])
    ]
    if not allowed:
        return []
    schema = Args.model_json_schema()
    schema["properties"]["action_type"]["enum"] = allowed
    schema["required"] = list(schema["properties"])
    return [
        {
            "type": "function",
            "name": "propose_action",
            "description": "Prepare a preview ONLY when user explicitly requests one internal task, Customer/Order note or professional Customer/Quote email draft. Discussing an action is not requesting it. Resolve exact record IDs with read tools; clarify ambiguous customers or missing note text. due_when accepts today/tomorrow or ISO date/time in the canonical shop timezone; date-only means 9am. Email uses a neutral record-based template, not body/personality; choose a Quote for quote follow-up. Returns pending proposal, never success or a sent email. User must review/edit/confirm in interface. No model confirmation/execution tool exists.",
            "parameters": schema,
            "strict": True,
        }
    ]


async def execute(user, raw, *, conversation_id, request_key, mode="owner"):
    from . import business_assistant as svc

    if not conversation_id:
        raise assistant_tools.ToolError(
            "An owned conversation is required for action previews"
        )
    args = Args.model_validate(raw)
    fields = {
        "conversation_id": conversation_id,
        "mode": mode,
        "action_type": args.action_type,
        "title": args.title,
        "body": args.body,
        "subject": args.subject or args.title,
        "due_at": args.due_when,
        "priority": args.priority,
        "idempotency_key": assistant_actions.digest(request_key or raw),
    }
    refs = []
    if args.target_type or args.target_id:
        if not args.target_type or not args.target_id:
            raise assistant_tools.ToolError(
                "Resolve the exact target before proposing this action"
            )
        refs.append({"type": args.target_type, "id": args.target_id})
    # Validate source access before deriving even a name for a customer draft.
    await assistant_actions.targets(user, refs, args.action_type)
    if args.action_type == "email_draft":
        if args.target_type not in {"customer", "quote"}:
            raise assistant_tools.ToolError(
                "Select the Customer or relevant Quote for the draft"
            )
        customer_id = args.target_id
        quote = None
        if args.target_type == "quote":
            quote = await db.quotes.find_one(
                {"tenant_id": user["tenant_id"], "id": args.target_id}, {"_id": 0}
            )
            customer_id = quote.get("customer_id")
            refs.append({"type": "customer", "id": customer_id})
            await assistant_actions.targets(user, refs, args.action_type)
        customer = await db.customers.find_one(
            {"tenant_id": user["tenant_id"], "id": customer_id}, {"_id": 0}
        )
        if not customer:
            raise assistant_tools.ToolError(
                "Choose an accessible Customer for this quote"
            )
        tenant = await db.tenants.find_one(
            {"id": user["tenant_id"]}, {"_id": 0, "name": 1}
        )
        topic = (
            f"quote {quote.get('number') or 'for your project'}"
            if quote
            else "your project"
        )
        fields["subject"] = f"Following up on {topic}"
        fields["body"] = (
            f"Hello {customer.get('name') or customer.get('company') or 'there'},\n\nI'm following up on {topic}. Please let us know if you have any questions or would like to discuss the next steps. We'd be happy to help.\n\nThank you,\n{(tenant or {}).get('name') or 'Your sign shop team'}"
        )
    fields["target_refs"] = refs
    # Repeated provider tool calls within one user turn share a proposal; a new
    # spoken/text turn may intentionally request a new action.
    turn_key = (
        request_key.rsplit(":", 1)[0]
        if request_key and ":" in request_key
        else request_key
    )
    fields["idempotency_key"] = assistant_actions.digest(
        {
            "turn": turn_key,
            "content": {k: v for k, v in fields.items() if k != "idempotency_key"},
        }
    )
    try:
        proposal = await svc.propose_action(user, fields)
    except svc.BusinessAssistantError as exc:
        raise assistant_tools.ToolError(exc.detail) from exc
    return {
        "proposal_id": proposal["id"],
        "status": "awaiting_interface_confirmation",
        "preview": proposal["editable_payload"],
        "destinations": proposal["target_refs"],
        "sources": [
            assistant_tools.reference(
                ref["type"], {"id": ref["id"], "name": ref["label"]}
            )
            for ref in proposal["target_refs"]
        ],
        "notice": "Only a proposal exists. Nothing created or sent; review/edit/confirm in the interface.",
    }
