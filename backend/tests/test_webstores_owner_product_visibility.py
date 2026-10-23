"""Submitted product content, not mutable staff drafts, crosses the owner boundary."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.services.portal_identity import create_portal_identity
from server import app
from tests.test_webstores_stage4b_owner_approval import (
    stage4b_ctx, _client_as, _portal_client, _create_ready_store, _owner_token,
    _approve_product_and_mockup, _submit_product_for_approval,
)
from tests.test_webstores_phase4_product_recommendations import _submission, _template


async def _owner_read(token, store):
    async with await _portal_client(token) as portal:
        response = await portal.get(f"/api/portal/webstores/{store['id']}")
        assert response.status_code == 200, response.text
        return response.json()


@pytest.mark.parametrize('decision', ['approve', 'request_changes', 'reject'])
async def test_hat_submission_edits_return_and_resubmission_keep_last_shared_content(stage4b_ctx, decision):
    ctx = stage4b_ctx
    async with await _client_as(ctx['staff']) as client:
        built = await _create_ready_store(client, ctx)
        store = built['store']
        token = await _owner_token(ctx, built['owner'])
    await _approve_product_and_mockup(ctx, token, store, built['product'], built['mockup'])
    original = (await _owner_read(token, store))['products'][0]
    assert original['approval_status'] == 'approved' and original['approval_history']
    async with await _client_as(ctx['staff']) as client:
        template = await _template(client, 'Hat', 'hat', suggested_selling_price_cents=2800)
        await _submission(ctx, store)
        matches = (await client.get(f"/api/webstores/{store['id']}/product-recommendations")).json()
        assert any(item['template_id'] == template['id'] for item in matches['items'])
        draft = await client.post(f"/api/webstores/{store['id']}/products", json={'source_template_id': template['id']})
        assert draft.status_code == 201, draft.text
        hat = draft.json()
        assert not hat['public'] and hat['approval_status'] == 'not_submitted'
    hidden = await _owner_read(token, store)
    assert [p['id'] for p in hidden['products']] == [original['id']]
    assert hat['id'] not in str(hidden) and 'Hat' not in str(hidden)
    image_path = f"/api/portal/webstores/{store['id']}/products/{hat['id']}/images/primary"
    async with await _portal_client(token) as portal:
        assert (await portal.get(image_path)).status_code == 404
    async with await _client_as(ctx['staff']) as client:
        completed = await client.patch(f"/api/webstores/{store['id']}/products/{hat['id']}", json={
            'expected_revision': hat['revision'], 'name': 'Submitted Hat', 'short_description': 'Navy cap',
            'selling_price_cents': 3200, 'sku': 'HAT-' + ctx['suffix'],
            'customer_images': built['product']['customer_images'], 'status': 'ready',
        })
        assert completed.status_code == 200, completed.text
        hat = completed.json()
    assert hat['id'] not in str(await _owner_read(token, store))
    async with await _client_as(ctx['staff']) as client:
        await _submit_product_for_approval(client, store, hat)
    shared = next(p for p in (await _owner_read(token, store))['products'] if p['id'] == hat['id'])
    assert shared['name'] == 'Submitted Hat' and shared['selling_price_cents'] == 3200
    assert shared['approval_status'] == 'pending_owner_approval'
    assert shared['images'][0]['url'].startswith(image_path)
    assert 'file_id' not in shared['images'][0]
    async with await _portal_client(token) as portal:
        image = await portal.get(image_path)
        assert image.status_code == 200 and image.content == b'stage4b-image'
        response = await portal.post(f"/api/portal/webstores/{store['id']}/products/{hat['id']}/approval",
                                     json={'decision': decision, 'comment': 'Owner review'})
        assert response.status_code == 200, response.text
        history = response.json()['approval_history']
        assert history
    async with await _client_as(ctx['staff']) as client:
        edit = await client.patch(f"/api/webstores/{store['id']}/products/{hat['id']}", json={
            'expected_revision': hat['revision'], 'name': 'PRIVATE unfinished edit',
            'short_description': 'PRIVATE copy', 'selling_price_cents': 9900,
            'customer_images': {'primary': {'url': 'https://example.com/private-unsubmitted.png', 'alt_text': 'PRIVATE image'}},
        })
        assert edit.status_code == 200, edit.text
        updated = edit.json()
    detail = await _owner_read(token, store)
    old = next(p for p in detail['products'] if p['id'] == hat['id'])
    assert old['name'] == 'Submitted Hat' and old['selling_price_cents'] == 3200
    assert 'PRIVATE' not in str(detail) and '9900' not in str(detail)
    assert old['approval_history'] and old['review_notice']
    assert next(p for p in detail['products'] if p['id'] == original['id']) == original
    async with await _portal_client(token) as portal:
        image = await portal.get(image_path)
        assert image.status_code == 200 and image.content == b'stage4b-image'
        assert (await portal.post(f"/api/portal/webstores/{store['id']}/products/{hat['id']}/approval",
                                  json={'decision': 'approve'})).status_code == 409
    # Even a live test store does not make a private/unapproved product eligible.
    await db.webstores.update_one({'tenant_id': ctx['tenant_id'], 'id': store['id']}, {'$set': {'status': 'live'}})
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as public:
        assert (await public.get(image_path)).status_code == 401
        storefront = await public.get(f"/api/public/webstores/{store['public_slug']}")
        assert storefront.status_code == 200, storefront.text
        assert hat['id'] not in str(storefront.json())
    async with await _client_as(ctx['staff']) as client:
        await _submit_product_for_approval(client, store, updated)
        copied = await client.post(f"/api/webstores/{store['id']}/products/{hat['id']}/duplicate",
                                   json={'expected_revision': updated['revision']})
        assert copied.status_code == 201, copied.text
        copy_id = copied.json()['id']
    resubmitted = await _owner_read(token, store)
    fresh = next(p for p in resubmitted['products'] if p['id'] == hat['id'])
    assert fresh['name'] == 'PRIVATE unfinished edit' and fresh['selling_price_cents'] == 9900
    assert fresh['approval_status'] == 'pending_owner_approval' and fresh['approval_history']
    assert 'review_notice' not in fresh and copy_id not in str(resubmitted)


async def test_legacy_approval_snapshot_survives_edits_and_unrecoverable_draft_is_not_guessed(stage4b_ctx):
    ctx = stage4b_ctx
    async with await _client_as(ctx['staff']) as client:
        built = await _create_ready_store(client, ctx)
        store, product = built['store'], built['product']
        token = await _owner_token(ctx, built['owner'])
    await _approve_product_and_mockup(ctx, token, store, product, built['mockup'])
    query = {'tenant_id': ctx['tenant_id'], 'webstore_id': store['id'], 'id': product['id']}
    await db.webstore_products.update_one(query, {'$unset': {'approval_snapshot': ''}})
    # Existing canonical approval contains the old submitted snapshot.
    async with await _client_as(ctx['staff']) as client:
        edit = await client.patch(f"/api/webstores/{store['id']}/products/{product['id']}",
                                  json={'expected_revision': product['revision'], 'name': 'Private legacy edit'})
        assert edit.status_code == 200, edit.text
    detail = await _owner_read(token, store)
    assert detail['products'][0]['name'] == product['name']
    assert detail['products'][0]['approval_history']
    # Read compatibility also works from canonical history if a prior edit
    # predates retention. Without any evidence it fails closed, never uses draft.
    await db.webstore_products.update_one(query, {'$unset': {'approval_snapshot': ''}})
    assert (await _owner_read(token, store))['products'][0]['name'] == product['name']
    await db.approvals.update_many({'tenant_id': ctx['tenant_id'], 'parent_type': 'webstore_product',
                                   'parent_id': product['id']}, {'$unset': {'snapshot': ''}})
    assert (await _owner_read(token, store))['products'] == []


async def test_pending_legacy_submission_is_frozen_before_first_staff_edit(stage4b_ctx):
    ctx = stage4b_ctx
    async with await _client_as(ctx['staff']) as client:
        built = await _create_ready_store(client, ctx)
        store, product = built['store'], built['product']
        token = await _owner_token(ctx, built['owner'])
        submitted = await _submit_product_for_approval(client, store, product)
    query = {'tenant_id': ctx['tenant_id'], 'webstore_id': store['id'], 'id': product['id']}
    await db.webstore_products.update_one(query, {'$unset': {'approval_snapshot': ''}})
    assert (await _owner_read(token, store))['products'][0]['name'] == product['name']
    async with await _client_as(ctx['staff']) as client:
        changed = await client.patch(f"/api/webstores/{store['id']}/products/{product['id']}",
            json={'expected_revision': product['revision'], 'name': 'Pending private edit'})
        assert changed.status_code == 200, changed.text
    old = (await _owner_read(token, store))['products'][0]
    assert old['name'] == product['name'] and old['approval_status'] == 'superseded'
    assert (await db.webstore_products.find_one(query))['approval_snapshot'] == submitted['approval_snapshot']
    async with await _portal_client(token) as portal:
        assert (await portal.post(f"/api/portal/webstores/{store['id']}/products/{product['id']}/approval",
            json={'decision': 'approve'})).status_code == 409


async def test_visibility_respects_tenant_assignment_and_blocks_draft_mockup_response(stage4b_ctx):
    ctx = stage4b_ctx
    async with await _client_as(ctx['staff']) as client:
        built = await _create_ready_store(client, ctx)
        store = built['store']
        token = await _owner_token(ctx, built['owner'])
        assert (await client.post(f"/api/webstores/{store['id']}/mockups/{built['mockup']['id']}/submit-approval", json={})).status_code == 409
    async with await _portal_client(token) as portal:
        assert (await portal.get(f"/api/portal/webstores/{store['id']}")).json()['products'] == []
        denied = await portal.post(f"/api/portal/webstores/{store['id']}/mockups/{built['mockup']['id']}/approval", json={'decision': 'approve'})
        assert denied.status_code == 409 and 'product' not in denied.json()
    foreign = await create_portal_identity(tenant_id=ctx['other_tenant_id'], portal_type='webstore_owner',
        webstore_owner_id=built['owner']['id'], email='foreign-' + ctx['suffix'] + '@example.com', full_name='Foreign')
    foreign_token = create_portal_token(portal_identity_id=foreign['id'], tenant_id=ctx['other_tenant_id'], portal_type='webstore_owner')
    async with await _portal_client(foreign_token) as portal:
        assert (await portal.get(f"/api/portal/webstores/{store['id']}")).status_code in {403, 404}
        assert (await portal.get(f"/api/portal/webstores/{store['id']}/products/{built['product']['id']}/images/primary")).status_code in {403, 404}
    await db.webstore_access_assignments.update_one({'tenant_id': ctx['tenant_id'], 'webstore_id': store['id'],
        'portal_identity_id': built['owner']['portal_identity_id']}, {'$set': {'status': 'revoked'}})
    async with await _portal_client(token) as portal:
        assert (await portal.get(f"/api/portal/webstores/{store['id']}")).status_code == 403
        assert (await portal.get(f"/api/portal/webstores/{store['id']}/products/{built['product']['id']}/images/primary")).status_code == 403
