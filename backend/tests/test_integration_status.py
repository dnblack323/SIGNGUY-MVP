"""EC2 — Integration status tests."""
from __future__ import annotations

from app.services.integration_status import integration_status


def test_status_shape_and_no_secret_values():
    status = integration_status()
    assert "env" in status
    assert isinstance(status["integrations"], list)
    for intg in status["integrations"]:
        assert set(intg.keys()) == {"name", "enabled", "configured", "missing_secrets", "ok"}
        # No secret VALUES are ever exposed — only names of missing env vars.
        for missing in intg["missing_secrets"]:
            assert missing.isupper()  # env-var name style
            assert "=" not in missing


def test_status_reports_disabled_integrations_as_ok():
    """Disabled integration should be reported ok=True (no missing secret pressure)."""
    from app.core import config as cfg

    s = cfg.get_settings()
    orig_stripe = s.stripe_webhook_enabled
    orig_secret = s.stripe_webhook_secret
    s.stripe_webhook_enabled = False
    s.stripe_webhook_secret = None
    try:
        status = integration_status()
        stripe = next(i for i in status["integrations"] if i["name"] == "stripe_webhook")
        assert stripe["enabled"] is False
        assert stripe["ok"] is True
        assert stripe["missing_secrets"] == []
    finally:
        s.stripe_webhook_enabled = orig_stripe
        s.stripe_webhook_secret = orig_secret


def test_status_reports_enabled_missing_secret_as_not_ok():
    from app.core import config as cfg

    s = cfg.get_settings()
    orig_enabled = s.sendgrid_webhook_enabled
    orig_secret = s.sendgrid_webhook_secret
    s.sendgrid_webhook_enabled = True
    s.sendgrid_webhook_secret = None
    try:
        status = integration_status()
        sg = next(i for i in status["integrations"] if i["name"] == "sendgrid_webhook")
        assert sg["enabled"] is True
        assert sg["ok"] is False
        assert "SENDGRID_WEBHOOK_SECRET" in sg["missing_secrets"]
    finally:
        s.sendgrid_webhook_enabled = orig_enabled
        s.sendgrid_webhook_secret = orig_secret
