"""Existing configuration contracts work through submission and public validation."""
import pytest

from app.core.db import db
from app.services.webstore_public_cart import _validate_personalization
from app.services.webstore_shared import WebstoreError
from tests.test_webstores_stage4b_owner_approval import (
    stage4b_ctx, _client_as, _portal_client, _create_ready_store,
    _owner_token, _submit_product_for_approval,
)
from tests.test_webstores_owner_product_visibility import _owner_read
from tests.test_webstores_stage6_public_storefront_cart import _seed_store, _public_client


FIELDS = [
    {'key': 'player_name', 'label': 'Player Name', 'type': 'text', 'required': False, 'max_length': 20},
    {'key': 'graduation_year', 'label': 'Graduation Year', 'type': 'select', 'required': True, 'choices': ['2026', '2027', '2028']},
]
VARIANTS = [
    {'id': 'navy-m', 'color': 'Navy', 'size': 'M', 'sku': 'HOODIE-N-M', 'status': 'active', 'available': True, 'selling_price_cents': 4200},
    {'id': 'navy-l', 'color': 'Navy', 'size': 'L', 'sku': 'HOODIE-N-L', 'status': 'active', 'available': False, 'selling_price_cents': 4200},
    {'id': 'white-m', 'color': 'White', 'size': 'M', 'sku': 'HOODIE-W-M', 'status': 'inactive', 'available': True, 'selling_price_cents': 4200},
]


@pytest.mark.parametrize('values,code', [
    ({'graduation_year': '2026'}, None),
    ({'player_name': 'Alex', 'graduation_year': '2028'}, None),
    ({'player_name': 'A' * 20, 'graduation_year': '2027'}, None),
    ({'player_name': 'A' * 21, 'graduation_year': '2027'}, 'personalization_too_long'),
    ({'graduation_year': '2099'}, 'personalization_invalid'),
    ({'graduation_year': ''}, 'personalization_required'),
    ({}, 'personalization_required'),
    ({'unknown': 'value', 'graduation_year': '2026'}, 'personalization_invalid'),
])
def test_canonical_configuration_validation(values, code):
    product = {'personalization_enabled': True, 'personalization_fields': FIELDS}
    if code:
        with pytest.raises(WebstoreError) as caught:
            _validate_personalization(product, values)
        assert caught.value.code == code
    else:
        _validate_personalization(product, values)


@pytest.mark.parametrize('options', [['2026'], [{'value': '2026'}], [{'id': '2026'}], [{'label': '2026'}]])
def test_legacy_select_options_remain_readable(options):
    product = {'personalization_enabled': True, 'personalization_fields': [{'key': 'year', 'type': 'select', 'options': options}]}
    _validate_personalization(product, {'year': '2026'})
    with pytest.raises(WebstoreError):
        _validate_personalization(product, {'year': '2099'})
    product['personalization_fields'][0]['choices'] = ['2027']
    _validate_personalization(product, {'year': '2027'})
    with pytest.raises(WebstoreError):
        _validate_personalization(product, {'year': '2026'})


async def test_hoodie_configuration_is_private_then_frozen_for_owner_review(stage4b_ctx):
    ctx = stage4b_ctx
    async with await _client_as(ctx['staff']) as staff:
        built = await _create_ready_store(staff, ctx)
        store, product = built['store'], built['product']
        token = await _owner_token(ctx, built['owner'])
        path = f"/api/webstores/{store['id']}/products/{product['id']}"
        for invalid, code in [
            ({'personalization_enabled': True, 'personalization_fields': [{**FIELDS[1], 'choices': []}]}, 'Select personalization prompts require at least one choice'),
            ({'variants': [VARIANTS[0], {**VARIANTS[0], 'id': 'duplicate'}]}, 'Each size/color/options variant combination must be unique'),
            ({'personalization_fields': [{**FIELDS[0], 'max_length': 0}]}, None),
        ]:
            response = await staff.patch(path, json={'expected_revision': product['revision'], **invalid})
            assert response.status_code in {400, 409}, response.text
            if code:
                assert response.json()['detail'] == code
        saved = await staff.patch(path, json={'expected_revision': product['revision'], 'name': 'School Hoodie',
            'selling_price_cents': 4200, 'variants': VARIANTS, 'personalization_enabled': True, 'personalization_fields': FIELDS})
        assert saved.status_code == 200, saved.text
        product = saved.json()
        assert product['personalization_fields'] == FIELDS
    assert (await _owner_read(token, store))['products'] == []
    async with await _client_as(ctx['staff']) as staff:
        await _submit_product_for_approval(staff, store, product)
    shared = (await _owner_read(token, store))['products'][0]
    assert shared['personalization_fields'] == FIELDS
    assert [(v['status'], v['available']) for v in shared['variants']] == [('active', True), ('active', False), ('inactive', True)]
    async with await _portal_client(token) as owner:
        approved = await owner.post(f"/api/portal/webstores/{store['id']}/products/{product['id']}/approval", json={'decision': 'approve', 'comment': 'Hoodie configuration approved'})
        assert approved.status_code == 200, approved.text
        assert (await owner.patch(path, json={'name': 'Owner edit'})).status_code in {401, 403}
    approved_snapshot = (await _owner_read(token, store))['products'][0]
    async with await _client_as(ctx['staff']) as staff:
        changed = await staff.patch(path, json={'expected_revision': product['revision'],
            'personalization_fields': [{**FIELDS[0], 'max_length': 10}, {**FIELDS[1], 'choices': ['PRIVATE']}],
            'variants': [{**VARIANTS[0], 'color': 'PRIVATE'}]})
        assert changed.status_code == 200, changed.text
    old = (await _owner_read(token, store))['products'][0]
    assert old['personalization_fields'] == FIELDS
    assert old['variants'] == approved_snapshot['variants']
    # Editing supersedes the approval's current status, preserving its decision,
    # actor, original revision, reason, and snapshot hash in canonical history.
    for before, after in zip(approved_snapshot['approval_history'], old['approval_history'], strict=True):
        assert {key: after[key] for key in ('id', 'action', 'reason', 'parent_version', 'snapshot_hash')} == {
            key: before[key] for key in ('id', 'action', 'reason', 'parent_version', 'snapshot_hash')}
        assert after['status'] == 'superseded'
    assert 'PRIVATE' not in str(old)
    async with await _client_as(ctx['other_staff']) as foreign:
        assert (await foreign.patch(path, json={'expected_revision': changed.json()['revision'], 'name': 'Cross tenant'})).status_code == 404
    async with await _client_as(ctx['staff']) as staff:
        await _submit_product_for_approval(staff, store, changed.json())
    assert (await _owner_read(token, store))['products'][0]['personalization_fields'][1]['choices'] == ['PRIVATE']


async def test_public_cart_enforces_saved_choices_and_manual_variant_availability():
    store, product = await _seed_store()
    await db.webstore_products.update_one({'tenant_id': store['tenant_id'], 'id': product['id']}, {'$set': {
        'name': 'School Hoodie', 'variants': VARIANTS, 'personalization_enabled': True, 'personalization_fields': FIELDS,
    }})
    async with await _public_client() as public:
        path = f"/api/public/webstores/{store['public_slug']}/cart-quote"
        for variant, values, status in [
            ('navy-m', {'graduation_year': '2026'}, 200),
            ('navy-m', {'graduation_year': '2099'}, 400),
            ('navy-m', {'graduation_year': '2026', 'player_name': 'A' * 21}, 400),
            ('navy-m', {}, 400), ('navy-l', {'graduation_year': '2026'}, 409),
            ('white-m', {'graduation_year': '2026'}, 409),
        ]:
            response = await public.post(path, json={'line_items': [{'product_id': product['id'], 'quantity': 1,
                'variant': {'id': variant}, 'personalization': values}]})
            assert response.status_code == status, response.text
