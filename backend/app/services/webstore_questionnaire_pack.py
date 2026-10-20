"""Webstore Starter questionnaire pack: the single questionnaire template authority chain.

Platform pack (central Template platform, versioned source records)
    -> one installed Form Maker copy per shop and store type (shops edit these)
    -> bound to a Webstore when setup starts
    -> frozen into each submission's template snapshot.

Installed copies are never overwritten, so shop customisations survive pack
updates. Each copy records ``source_template_id`` + ``source_template_version``;
an "update available" flow can be added later from those fields.
"""
from __future__ import annotations

from typing import Any

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.forms import FormTemplate
from ..models.template_definition import TemplateDefinition, TemplatePack
from ..models.webstore import WEBSTORE_TYPES
from .template_service import PLATFORM_TENANT_ID
from .webstore_questionnaire_content import QUESTIONNAIRE_CONTENT_VERSION, STARTER_QUESTIONNAIRE_SECTIONS
from .webstore_setup_contracts import SAFE_ANSWER_MAPPING, WEBSTORE_FORM_ADAPTER

WEBSTORE_STARTER_PACK_ID = "webstore_starter"
WEBSTORE_STARTER_PACK_VERSION = QUESTIONNAIRE_CONTENT_VERSION
# Employee/Company is a preset inside the B2B questionnaire, not a store type.
QUESTIONNAIRE_STORE_TYPES = ("base", *WEBSTORE_TYPES)


def _source_template_id(store_type: str) -> str:
    return f"{WEBSTORE_STARTER_PACK_ID}_questionnaire_{store_type}"


def _questionnaire_title(store_type: str) -> str:
    if store_type == "base":
        return "Base Webstore Intake"
    return f"{store_type.replace('_', ' ').title()} Webstore Intake"


async def ensure_platform_webstore_pack() -> dict[str, Any]:
    """Create or upgrade the platform source records. Never touches shop copies."""
    ids: list[str] = []
    for store_type in QUESTIONNAIRE_STORE_TYPES:
        source_id = _source_template_id(store_type)
        ids.append(source_id)
        existing = await db.template_definitions.find_one(
            {"id": source_id, "tenant_id": PLATFORM_TENANT_ID}, {"_id": 0, "version": 1}
        )
        if existing and int(existing.get("version") or 0) >= WEBSTORE_STARTER_PACK_VERSION:
            continue
        body = {"store_type": store_type, "sections": STARTER_QUESTIONNAIRE_SECTIONS[store_type]}
        if existing:
            await db.template_definitions.update_one(
                {"id": source_id, "tenant_id": PLATFORM_TENANT_ID},
                {"$set": prepare_for_mongo({"body": body, "version": WEBSTORE_STARTER_PACK_VERSION, "updated_at": utc_now()})},
            )
            continue
        doc = TemplateDefinition(
            id=source_id,
            tenant_id=PLATFORM_TENANT_ID,
            owner_scope="platform",
            name=_questionnaire_title(store_type),
            template_type="questionnaire",
            description="Webstore Starter questionnaire. Shops edit their installed copy in Form Maker.",
            body=body,
            version=WEBSTORE_STARTER_PACK_VERSION,
            source_status="active",
            starter_template=True,
            pack_id=WEBSTORE_STARTER_PACK_ID,
            pack_type="starter",
            # Not listed in the Templates library: these install into Form Maker,
            # not as library copies, so they can never be applied to customer intakes.
            platform_managed=False,
            created_by_user_id="system",
            updated_by_user_id="system",
        ).model_dump()
        try:
            await db.template_definitions.insert_one(prepare_for_mongo(dict(doc)))
        except DuplicateKeyError:
            pass
    pack = TemplatePack(
        id=WEBSTORE_STARTER_PACK_ID,
        name="Webstore Starter",
        description="Webstore setup questionnaires installed into each shop's Form Maker.",
        pack_type="starter",
        version=WEBSTORE_STARTER_PACK_VERSION,
        # Questionnaires plus the information-packet emails (webstore_information_packet).
        included_template_ids=[*ids, *(f"{WEBSTORE_STARTER_PACK_ID}_packet_{t}" for t in WEBSTORE_TYPES)],
        starter_pack=True,
    ).model_dump()
    created_at = pack.pop("created_at", utc_now())
    await db.template_packs.update_one(
        {"id": WEBSTORE_STARTER_PACK_ID},
        {"$set": prepare_for_mongo({**pack, "updated_at": utc_now()}), "$setOnInsert": {"created_at": created_at}},
        upsert=True,
    )
    return serialize_doc(await db.template_packs.find_one({"id": WEBSTORE_STARTER_PACK_ID}, {"_id": 0}))


async def install_webstore_questionnaires(tenant_id: str, actor_user_id: str | None = None) -> int:
    """Idempotently give the shop one Form Maker questionnaire per store type.

    A store type that already has any Webstore form (installed, customised,
    archived or shop-built) is left alone. Returns the number of copies created.
    """
    await ensure_platform_webstore_pack()
    created = 0
    for store_type in QUESTIONNAIRE_STORE_TYPES:
        has_form = await db.form_templates.find_one(
            {"tenant_id": tenant_id, "module": "webstores", "private_config.store_type": store_type}, {"_id": 1}
        )
        if has_form:
            continue
        source = await db.template_definitions.find_one(
            {"id": _source_template_id(store_type), "tenant_id": PLATFORM_TENANT_ID}, {"_id": 0}
        )
        doc = FormTemplate(
            # Deterministic id: concurrent installs for the same shop cannot duplicate.
            id=f"{_source_template_id(store_type)}__{tenant_id}",
            tenant_id=tenant_id,
            name=source["name"],
            module="webstores",
            context_type="webstore",
            description=source.get("description"),
            status="published",
            sections=(source.get("body") or {}).get("sections") or [],
            mapping_config={"safe_answer_mapping": SAFE_ANSWER_MAPPING},
            private_config={"adapter": WEBSTORE_FORM_ADAPTER, "store_type": store_type, "pack_id": WEBSTORE_STARTER_PACK_ID},
            source_template_id=source["id"],
            source_template_version=int(source.get("version") or 1),
            created_by_user_id=actor_user_id,
        ).model_dump()
        try:
            await db.form_templates.insert_one(prepare_for_mongo(doc))
            created += 1
        except DuplicateKeyError:
            pass
    return created


def questionnaire_view(form: dict[str, Any]) -> dict[str, Any]:
    """Shape a Form Maker template for the Webstore questionnaire and its snapshot."""
    private_config = form.get("private_config") or {}
    return {
        "id": form["id"],
        "title": form.get("name") or "Webstore Questionnaire",
        "sections": form.get("sections") or [],
        "version": int(form.get("version") or 1),
        "store_type": private_config.get("store_type") or "all",
        "source_template_id": form.get("source_template_id"),
        "source_template_version": form.get("source_template_version"),
    }


async def questionnaires_for_store_type(tenant_id: str, store_type: str) -> list[dict[str, Any]]:
    """Published Webstore questionnaires for a store type: base first, then the type, then "all types"."""
    await install_webstore_questionnaires(tenant_id)
    forms = [
        serialize_doc(d)
        async for d in db.form_templates.find(
            {
                "tenant_id": tenant_id,
                "module": "webstores",
                "context_type": "webstore",
                "status": "published",
                "private_config.adapter": {"$in": [None, WEBSTORE_FORM_ADAPTER]},
                "$or": [
                    {"private_config.store_type": {"$in": ["base", store_type]}},
                    {"private_config.store_type": {"$exists": False}},
                ],
            },
            {"_id": 0},
        ).sort([("created_at", 1)])
    ]
    order = {"base": 0, store_type: 1}
    forms.sort(key=lambda f: order.get((f.get("private_config") or {}).get("store_type"), 2))
    return [questionnaire_view(f) for f in forms]


async def questionnaires_by_ids(tenant_id: str, ids: list[str]) -> list[dict[str, Any]]:
    """Bound questionnaires still published in Form Maker, in bound order."""
    forms = {
        d["id"]: serialize_doc(d)
        async for d in db.form_templates.find(
            {"tenant_id": tenant_id, "module": "webstores", "status": "published", "id": {"$in": ids}}, {"_id": 0}
        )
    }
    return [questionnaire_view(forms[i]) for i in ids if i in forms]
