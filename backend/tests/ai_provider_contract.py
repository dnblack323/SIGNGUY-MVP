"""In-process executor for EC16 accounting contracts; never installed by app code."""
from app.services import ai_gateway


def install_provider_contract(monkeypatch):
    async def execute(model, fields):
        return {
            'verified_success': not str(fields.get('idempotency_key', '')).startswith('fail-'),
            'provider_event_id': 'test-' + str(fields.get('idempotency_key')),
            'input_units': fields.get('input_units', 0), 'output_units': fields.get('output_units', 0),
            'actual_cost_micros': ai_gateway._estimate_cost(model, fields),
        }
    monkeypatch.setattr(ai_gateway, '_provider_executor_for', lambda provider, model: execute)
