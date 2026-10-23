"""Phase 4 selection uses existing records without pricing or AI side effects."""
from copy import deepcopy

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.services.portal_identity import create_portal_identity
from app.services.webstore_questionnaire_content import BASE_SECTIONS
from tests.test_webstores_stage4a_product_foundation import stage4a_ctx, _client_as, _create_store, _portal_client  # noqa: F401
from tests.webstore_questionnaire_answers import complete_answers


async def _template(client, name, product_type, **extra):
    response = await client.post('/api/webstores/product-templates', json={
        'template_name': name, 'product_category': 'apparel', 'product_type': product_type, **extra,
    })
    assert response.status_code == 201, response.text
    return response.json()


async def _submission(ctx, store, **changes):
    answers = complete_answers('fundraiser', products_wanted=['hats', 'yard_signs'], product_notes='Navy and youth sizes')
    doc = {'id': 'selection-' + ctx['suffix'], 'tenant_id': ctx['tenant_id'], 'webstore_id': store['id'],
           'revision': 1, 'status': 'submitted', 'answers': {'products_wanted': ['tshirts']},
           'submitted_snapshot': {'answers': answers, 'template_snapshot': {'templates': [{'sections': deepcopy(BASE_SECTIONS)}]}},
           **changes}
    await db.webstore_questionnaire_submissions.insert_one(doc)
    return doc


async def test_shortlist_matches_frozen_requests_and_declared_store_types_only(stage4a_ctx):
    ctx = stage4a_ctx
    async with await _client_as(ctx['staff']) as client:
        store = await _create_store(client, ctx['suffix'], store_type='fundraiser')
        hat = await _template(client, 'Requested cap', 'cap', suggested_production_cost_cents=12345,
                              suggested_selling_price_cents=2500, internal_notes='Private supplier notes')
        hoodie = await _template(client, 'Campaign hoodie', 'hoodie', best_store_types=['fundraiser'])
        await _template(client, 'Other event', 'banner', best_store_types=['event'])
        await _template(client, 'Archived cap', 'cap', status='archived')
        await _submission(ctx, store)
        before = await db.webstores.find_one({'tenant_id': ctx['tenant_id'], 'id': store['id']})
        response = await client.get(f"/api/webstores/{store['id']}/product-recommendations")
        assert response.status_code == 200, response.text
        data = response.json()
        assert [i['template_id'] for i in data['items']] == [hat['id'], hoodie['id']]
        assert data['items'][0]['reasons'] == ['Requested in questionnaire: Hats.']
        assert data['unmatched_requests'] == ['Yard signs']
        assert any(i['value'] == 'Navy and youth sizes' for i in data['context'])
        assert 'Private supplier notes' not in response.text and '12345' not in response.text
        assert 'selling_price_cents' not in response.text and 'production_cost_cents' not in response.text
        assert 'contact_email' not in response.text
        assert (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).json() == data
        assert await db.webstores.find_one({'tenant_id': ctx['tenant_id'], 'id': store['id']}) == before
        assert await db.webstore_products.count_documents({'tenant_id': ctx['tenant_id'], 'webstore_id': store['id']}) == 0
        assert await db.webstore_ai_usage_events.count_documents({'tenant_id': ctx['tenant_id']}) == 0


async def test_declined_extras_and_existing_draft_reuse_normal_product_records(stage4a_ctx):
    ctx = stage4a_ctx
    async with await _client_as(ctx['staff']) as client:
        store = await _create_store(client, ctx['suffix'], store_type='fundraiser')
        hat = await _template(client, 'Cap', 'hat')
        await _template(client, 'Extra', 'hoodie', best_store_types=['fundraiser'])
        doc = await _submission(ctx, store)
        await db.webstore_questionnaire_submissions.update_one({'tenant_id': ctx['tenant_id'], 'id': doc['id']},
            {'$set': {'submitted_snapshot.answers.open_to_suggestions': 'no'}})
        response = (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).json()
        assert [i['template_id'] for i in response['items']] == [hat['id']]
        assert response['extra_suggestions_declined'] is True and not response['items'][0]['already_selected']
        product = await client.post(f"/api/webstores/{store['id']}/products", json={
            'source_template_id': hat['id'], 'idempotency_key': 'selection-' + ctx['suffix'],
        })
        assert product.status_code == 201, product.text
        assert product.json()['public'] is False and product.json()['approval_status'] != 'approved'
        assert (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).json()['items'][0]['already_selected'] is True
        assert await db.webstore_products.count_documents({'tenant_id': ctx['tenant_id'], 'webstore_id': store['id']}) == 1


async def test_draft_returned_and_hidden_answers_do_not_drive_recommendations(stage4a_ctx):
    ctx = stage4a_ctx
    async with await _client_as(ctx['staff']) as client:
        store = await _create_store(client, ctx['suffix'], store_type='fundraiser')
        await _template(client, 'Cap', 'hat')
        doc = await _submission(ctx, store)
        # Existing conditional Form Maker semantics, rather than a second rule parser.
        await db.webstore_questionnaire_submissions.update_one({'tenant_id': ctx['tenant_id'], 'id': doc['id']},
            {'$set': {'submitted_snapshot.template_snapshot.templates': [{'sections': [{'id': 'optional',
                'questions': [{'key': 'products_wanted', 'type': 'checkbox', 'options': [],
                    'conditional': {'depends_on': 'show_products', 'operator': 'equals', 'value': 'yes'}}]}]}]}})
        assert (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).json()['items'] == []
        for state in ('draft', 'returned_for_changes'):
            await db.webstore_questionnaire_submissions.update_one({'tenant_id': ctx['tenant_id'], 'id': doc['id']},
                {'$set': {'status': state, 'submitted_snapshot.template_snapshot.templates': [{'sections': deepcopy(BASE_SECTIONS)}]}})
            data = (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).json()
            assert data['items'] == [] and data['context'] == [] and data['submission_id'] is None


async def test_shortlist_respects_tenant_platform_staff_assignment_and_portal_boundaries(stage4a_ctx):
    ctx = stage4a_ctx
    async with await _client_as(ctx['staff']) as client:
        store = await _create_store(client, ctx['suffix'], store_type='fundraiser')
        await _submission(ctx, store)
    async with await _client_as(ctx['other_staff']) as client:
        await _template(client, 'Foreign cap', 'cap')
        assert (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).status_code == 404
    async with await _client_as(ctx['platform_creator']) as client:
        platform = await _template(client, 'Shared cap ' + ctx['suffix'], 'hat', scope='platform')
        result = (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).json()
        assert [i['template_id'] for i in result['items']] == [platform['id']]
    async with await _client_as({**ctx['staff'], 'role': 'staff'}) as client:
        assert (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).status_code == 403
    async with await _client_as({**ctx['staff'], 'webstore_ids': ['different-store']}) as client:
        assert (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).status_code == 403
    identity = await create_portal_identity(tenant_id=ctx['tenant_id'], portal_type='webstore_owner',
        webstore_owner_id=store['owner']['id'], email=f"selection-{ctx['suffix']}@example.com", full_name='Owner')
    token = create_portal_token(portal_identity_id=identity['id'], tenant_id=ctx['tenant_id'], portal_type='webstore_owner')
    async with await _portal_client(token) as portal:
        assert (await portal.get(f"/api/webstores/{store['id']}/product-recommendations")).status_code == 401
