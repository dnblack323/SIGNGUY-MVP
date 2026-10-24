"""Customer execution cannot promote a simulated result into billable delivery."""
import asyncio
import pytest
from app.core.db import db
from app.core.config import get_settings
from app.services import ai_gateway, ai_studio, business_assistant
from app.services.entitlements import _upsert_entitlement_for_tests
from tests.test_ec16_ai_gateway_metering import ctx, _setup_gateway, _client_as
from tests.test_webstores_cir020_ai_actions import cir020_ctx


@pytest.mark.parametrize('provider_key', ['ec17_local_mock', 'ec18_assistant_local'])
@pytest.mark.parametrize('included,purchased', [(10, 5), (0, 9), (0, 0)])
async def test_preexisting_billable_local_provider_is_free_and_idempotent(ctx, provider_key, included, purchased):
    # ctx installs the test executor for paid contracts. Local classification must
    # override even that executor, never reserve, never record supplied expenses.
    key = await _setup_gateway(ctx, included_credits=included, purchased_credits=purchased)
    capability = await db.ai_capabilities.find_one({'capability_key': key})
    model = await db.ai_model_profiles.find_one({'id': capability['allowed_model_profile_ids'][0]})
    # Use a metadata marker to avoid mutating shared global provider identities.
    await db.ai_provider_configs.update_one({'id': model['provider_config_id']}, {'$set': {'metadata': {
        'ec17_local_mock': provider_key == 'ec17_local_mock', 'ec18_local_contract': provider_key == 'ec18_assistant_local'}}})
    request = {'capability_key': key, 'idempotency_key': 'demo-' + ctx['suffix'],
               'input_units': 1000, 'estimated_cost_micros': 5000, 'actual_cost_cents': 99}
    preview = await ai_gateway.preview_gateway_request(ctx['owner'], request)
    assert preview['credit_charge_credits'] == 0 and preview['can_run']
    async with await _client_as(ctx['owner']) as client:
        first = await client.post('/api/ai/gateway/requests', json=request)
        assert first.status_code == 201, first.text
        repeat = await client.post('/api/ai/gateway/requests', json=request)
        assert repeat.json()['id'] == first.json()['id']
    action = first.json()
    assert action['credit_charge_credits'] == 0
    assert action['result_summary'] == 'simulated_nonbillable_demonstration'
    account = await ai_gateway.get_credit_account(ctx['tenant_id'])
    assert (account['included_balance_credits'], account['purchased_balance_credits'], account['reserved_credits']) == (included, purchased, 0)
    assert await db.ai_credit_ledger_entries.count_documents({'tenant_id': ctx['tenant_id'], 'action_request_id': action['id']}) == 0
    assert await db.ai_usage_ledger_entries.count_documents({'tenant_id': ctx['tenant_id'], 'action_request_id': action['id']}) == 1
    cost = await db.ai_provider_cost_ledger_entries.find_one({'tenant_id': ctx['tenant_id'], 'action_request_id': action['id']})
    assert cost['actual_cost_micros'] == cost['estimated_cost_micros'] == 0
    assert cost.get('actual_cost_cents') is None
    unchanged_capability = await db.ai_capabilities.find_one({'capability_key': key})
    assert unchanged_capability['billable'] and unchanged_capability['default_credit_charge'] == 3
    # Cached execution cannot bypass current production policy.
    settings = get_settings()
    prior = settings.env
    settings.env = 'production'
    try:
        async with await _client_as(ctx['owner']) as client:
            blocked = await client.post('/api/ai/gateway/requests', json=request)
            assert blocked.status_code == 409
    finally:
        settings.env = prior
    assert (await ai_gateway.get_credit_account(ctx['tenant_id']))['reserved_credits'] == 0


async def test_unconnected_provider_cannot_use_client_simulation_or_flags(ctx, monkeypatch):
    key = await _setup_gateway(ctx)
    monkeypatch.setattr(ai_gateway, '_provider_executor_for', lambda provider, model: None)
    preview = await ai_gateway.preview_gateway_request(ctx['owner'], {'capability_key': key})
    assert not preview['can_run'] and preview['credit_charge_credits'] == 3
    async with await _client_as(ctx['owner']) as client:
        for flag, value in [('is_demo', True), ('free', True), ('billable', False), ('provider_called', True), ('simulate_result', 'success')]:
            forged = await client.post('/api/ai/gateway/requests', json={'capability_key': key, flag: value})
            assert forged.status_code == 422, forged.text
        unavailable = await client.post('/api/ai/gateway/requests', json={'capability_key': key})
        assert unavailable.status_code == 409
    assert await db.ai_action_requests.count_documents({'tenant_id': ctx['tenant_id']}) == 0


async def test_local_studio_and_assistant_use_same_free_gateway_without_modifying_features(ctx):
    await ai_studio.bootstrap_platform_catalog(ctx['platform_admin'])
    await business_assistant.bootstrap_platform_catalog(ctx['platform_admin'])
    for feature in ['ai_studio', 'business_assistant']:
        await _upsert_entitlement_for_tests(tenant_id=ctx['tenant_id'], feature_key=feature, enabled=True)
    result = await ai_studio.run_tool(ctx['owner'], {'tool_key': 'ai_image_generator', 'mode_key': 'general_text_to_image',
        'inputs': {'prompt': 'Demonstration only'}, 'idempotency_key': 'studio-' + ctx['suffix']})
    assert result['credit_display'] == 'Demonstration · 0 customer credits'
    assert result['provenance']['external_provider_calls'] == 0
    action = await business_assistant._meter_assistant(ctx['owner'], capability_key='assistant.chat',
        conversation_id='demo-conversation', prompt='Local contract', idempotency_key='assistant-' + ctx['suffix'])
    assert action['credit_charge_credits'] == 0
    assert await db.ai_credit_ledger_entries.count_documents({'tenant_id': ctx['tenant_id'], 'entry_type': {'$in': ['reserve', 'commit']}}) == 0


async def test_paid_configured_charge_success_failure_and_tenant_scoped_retry(ctx):
    key = await _setup_gateway(ctx, included_credits=1, purchased_credits=9, default_credit_charge=4)
    preview = await ai_gateway.preview_gateway_request(ctx['owner'], {'capability_key': key})
    assert preview['can_run'] and preview['credit_charge_credits'] == 4 and not preview['simulated']
    async with await _client_as(ctx['owner']) as client:
        success = await client.post('/api/ai/gateway/requests', json={'capability_key': key, 'idempotency_key': 'paid-' + ctx['suffix']})
        assert success.status_code == 201
        again = await client.post('/api/ai/gateway/requests', json={'capability_key': key, 'idempotency_key': 'paid-' + ctx['suffix']})
        assert again.json()['id'] == success.json()['id']
        failed = await client.post('/api/ai/gateway/requests', json={'capability_key': key, 'idempotency_key': 'fail-' + ctx['suffix']})
        assert failed.json()['status'] == 'failed'
    account = await ai_gateway.get_credit_account(ctx['tenant_id'])
    assert (account['included_balance_credits'], account['purchased_balance_credits'], account['reserved_credits']) == (0, 6, 0)
    assert await db.ai_credit_ledger_entries.count_documents({'tenant_id': ctx['tenant_id'], 'entry_type': 'commit'}) == 1
    assert await db.ai_credit_ledger_entries.count_documents({'tenant_id': ctx['tenant_id'], 'entry_type': 'release'}) == 1
    async with await _client_as({**ctx['owner'], 'role': 'staff', 'permissions': []}) as denied:
        assert (await denied.post('/api/ai/gateway/requests', json={'capability_key': key})).status_code == 403
    foreign = {**ctx['owner'], 'id': 'other', 'tenant_id': 'other-' + ctx['suffix']}
    async with await _client_as(foreign) as other:
        assert (await other.post('/api/ai/gateway/requests', json={'capability_key': key, 'idempotency_key': 'paid-' + ctx['suffix']})).status_code == 402


async def test_webstore_zero_credit_preview_execution_and_production_denial_agree(cir020_ctx, monkeypatch):
    ctx = cir020_ctx
    await db.ai_credit_accounts.update_one({'tenant_id': ctx['tenant_id']}, {'$set': {'included_balance_credits': 0}})
    path = f"/api/webstores/{ctx['webstore_id']}/products/{ctx['product_id']}/ai-actions"
    async with await _client_as(ctx['owner']) as client:
        preview = (await client.post(path + '/preview', json={'action': 'product_mockup'})).json()
        assert preview['can_run'] and preview['credit_charge_credits'] == 0 and not preview['insufficient_credits']
        run = await client.post(path, json={'action': 'product_mockup', 'confirmed_credit_charge_credits': 0, 'idempotency_key': 'webstore-demo'})
        assert run.status_code == 201, run.text
        assert run.json()['ai_result']['content_json']['production_ready'] is False
        action_query = {'tenant_id': ctx['tenant_id'], 'id': run.json()['ai_result']['action_request_id']}
        # Represent a legacy charged result in this isolated fixture only.
        await db.ai_action_requests.update_one(action_query, {'$set': {'credit_charge_credits': 1}})
        historical = await db.ai_action_requests.find_one(action_query)
        cached = await client.post(path, json={'action': 'product_mockup', 'confirmed_credit_charge_credits': 0, 'idempotency_key': 'webstore-demo'})
        assert cached.status_code == 409 and 'reconciliation' in cached.json()['detail']
        assert await db.ai_action_requests.find_one(action_query) == historical
        monkeypatch.setattr(get_settings(), 'env', 'production')
        unavailable = (await client.post(path + '/preview', json={'action': 'product_mockup'})).json()
        assert not unavailable['can_run'] and 'production' in unavailable['unavailable_reason']
        direct = await client.post(path, json={'action': 'product_mockup', 'confirmed_credit_charge_credits': 0, 'idempotency_key': 'webstore-demo'})
        assert direct.status_code == 409
        studio = await client.post('/api/ai-studio/runs', json={'tool_key': 'ai_image_generator', 'mode_key': 'general_text_to_image', 'inputs': {'prompt': 'Production denied'}})
        assert studio.status_code == 409
    assert await db.ai_credit_ledger_entries.count_documents({'tenant_id': ctx['tenant_id'], 'entry_type': {'$in': ['reserve', 'commit']}}) == 0


async def test_historical_billable_demo_replay_does_not_rewrite_or_recharge(ctx, monkeypatch):
    key = await _setup_gateway(ctx)
    first = await ai_gateway.create_gateway_request(ctx['owner'], {'capability_key': key, 'idempotency_key': 'old-demo'})
    before = await db.ai_action_requests.find_one({'tenant_id': ctx['tenant_id'], 'id': first['id']})
    capability = await db.ai_capabilities.find_one({'capability_key': key})
    model = await db.ai_model_profiles.find_one({'id': capability['allowed_model_profile_ids'][0]})
    await db.ai_provider_configs.update_one({'id': model['provider_config_id']}, {'$set': {'metadata': {'ec17_local_mock': True}}})
    with pytest.raises(ai_gateway.AIGatewayError, match='historical demonstration'):
        await ai_gateway.create_gateway_request(ctx['owner'], {'capability_key': key, 'idempotency_key': 'old-demo'})
    assert await db.ai_action_requests.find_one({'tenant_id': ctx['tenant_id'], 'id': first['id']}) == before
    assert await db.ai_credit_ledger_entries.count_documents({'tenant_id': ctx['tenant_id'], 'entry_type': 'commit'}) == 1


@pytest.mark.parametrize('reply', [None, 'exception', {'verified_success': True}, {'verified_success': True, 'provider_event_id': 'bad', 'actual_cost_micros': -1}])
async def test_unverified_executor_result_releases_reservation(ctx, monkeypatch, reply):
    key = await _setup_gateway(ctx)
    async def executor(model, fields):
        if reply == 'exception':
            raise RuntimeError('isolated provider failure')
        return reply
    monkeypatch.setattr(ai_gateway, '_provider_executor_for', lambda provider, model: executor)
    action = await ai_gateway.create_gateway_request(ctx['owner'], {'capability_key': key, 'idempotency_key': 'invalid-reply'})
    assert action['status'] == 'failed'
    account = await ai_gateway.get_credit_account(ctx['tenant_id'])
    assert (account['included_balance_credits'], account['purchased_balance_credits'], account['reserved_credits']) == (10, 5, 0)


async def test_local_request_limits_and_concurrent_idempotency_still_apply(ctx):
    key = await _setup_gateway(ctx)
    capability = await db.ai_capabilities.find_one({'capability_key': key})
    model = await db.ai_model_profiles.find_one({'id': capability['allowed_model_profile_ids'][0]})
    await db.ai_provider_configs.update_one({'id': model['provider_config_id']}, {'$set': {'metadata': {'ec17_local_mock': True}}})
    async with await _client_as(ctx['owner']) as client:
        responses = await asyncio.gather(*(client.post('/api/ai/gateway/requests', json={'capability_key': key, 'idempotency_key': 'concurrent-demo'}) for _ in range(3)))
        assert all(response.status_code == 201 for response in responses)
        assert len({response.json()['id'] for response in responses}) == 1
    assert await db.ai_usage_ledger_entries.count_documents({'tenant_id': ctx['tenant_id']}) == 1
    await db.ai_governance_policies.insert_one({'id': 'limit-' + ctx['suffix'], 'status': 'active', 'scope_type': 'capability', 'capability_key': key, 'max_requests_per_day': 1})
    with pytest.raises(ai_gateway.AIGatewayError) as blocked:
        await ai_gateway.create_gateway_request(ctx['owner'], {'capability_key': key, 'idempotency_key': 'new-demo'})
    assert blocked.value.status_code == 429
