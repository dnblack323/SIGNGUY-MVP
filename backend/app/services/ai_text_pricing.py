"""Profile-sourced Responses pricing. Dollar rates per million yield microdollars."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation

INPUT = "input_usd_per_million_tokens"
OUTPUT = "output_usd_per_million_tokens"
CACHED = "cached_input_usd_per_million_tokens"
WRITE = "cache_write_usd_per_million_tokens"
WRITE12 = "cache_write_12h_usd_per_million_tokens"
RATE_KEYS = (INPUT, OUTPUT, CACHED, WRITE, WRITE12)


def rate(values, key):
    try:
        value = Decimal(str(values[key]))
        if (
            not value.is_finite()
            or value < 0
            or (key in (INPUT, OUTPUT) and value == 0)
        ):
            raise ValueError()
        return value
    except (KeyError, InvalidOperation, TypeError):
        raise ValueError("Missing or invalid sourced token rate") from None


def tier_key(value):
    return "priority" if value == "fast" else value


def profile_rates(profile, tier="default", *, long_context=False):
    metadata = profile.get("metadata") or {}
    if not metadata.get("pricing_source"):
        raise ValueError("Sourced pricing is required")
    tier = tier_key(tier)
    tiers = metadata.get("processing_tiers") or {}
    if not isinstance(tiers, dict):
        raise ValueError("Invalid processing-tier profile")
    values = metadata if tier == "default" else tiers.get(tier)
    if not isinstance(values, dict):
        raise ValueError("Unpriced processing tier")
    if long_context:
        values = values.get("long_context_pricing")
        if not isinstance(values, dict):
            raise ValueError("Unpriced long context")
    rate(values, INPUT)
    rate(values, OUTPUT)
    return values


def request_options(profile):
    metadata = profile.get("metadata") or {}
    tier = tier_key(metadata.get("service_tier", "default"))
    # Batch is a separate API workflow, not a Responses service tier. Auto could
    # silently inherit a project setting and is deliberately not dispatched.
    if tier not in {"default", "flex", "priority"}:
        raise ValueError("Unsupported Assistant processing tier")
    profile_rates(profile, tier)
    return {"service_tier": tier}


def reserve(profile, max_input, max_output):
    """Full uncached/write envelope, including any explicitly priced fallback tier."""
    metadata = profile.get("metadata") or {}
    request_options(profile)
    values = [profile_rates(profile)]
    for tier in metadata.get("processing_tiers") or {}:
        values.append(profile_rates(profile, tier))
    threshold = metadata.get("long_context_threshold_tokens")
    if threshold is not None and (type(threshold) is not int or threshold <= 0):
        raise ValueError("Invalid long-context threshold")
    if threshold is not None and max_input > threshold:
        values += [
            profile_rates(profile, tier, long_context=True)
            for tier in ("default", *(metadata.get("processing_tiers") or {}))
        ]
    # New-model cache premiums must be configured, never inferred from a name.
    if profile.get("model_key", "").startswith(("gpt-6", "gpt-5.6")):
        for item in values:
            for key in (CACHED, WRITE, WRITE12):
                rate(item, key)
    incoming = max(
        rate(item, key)
        for item in values
        for key in (INPUT, CACHED, WRITE, WRITE12)
        if key in item
    )
    outgoing = max(rate(item, OUTPUT) for item in values)
    return incoming * max_input + outgoing * max_output


def cost(profile, response):
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("Missing usage")

    def count(data, key, default=None):
        n = data.get(key, default)
        if type(n) is not int or n < 0:
            raise ValueError("Invalid token count")
        return n

    incoming, outgoing = count(usage, "input_tokens"), count(usage, "output_tokens")
    if "total_tokens" in usage and count(usage, "total_tokens") != incoming + outgoing:
        raise ValueError("Inconsistent usage totals")
    details = usage.get("input_tokens_details")
    if details is None:
        details = {}
    if not isinstance(details, dict):
        raise ValueError("Invalid input details")
    cached = count(details, "cached_tokens", 0)
    written = count(details, "cache_write_tokens", 0)
    lifetime = details.get("cache_write_tokens_details")
    if lifetime is None:
        write30, write12 = written, 0  # Existing default automatic 30-minute policy.
    else:
        if not isinstance(lifetime, dict) or set(lifetime) - {
            "ttl_30m_tokens",
            "ttl_12h_tokens",
        }:
            raise ValueError("Unknown cache lifetime")
        write30 = count(lifetime, "ttl_30m_tokens")
        write12 = count(lifetime, "ttl_12h_tokens")
        if write30 + write12 != written:
            raise ValueError("Inconsistent cache-write totals")
    ordinary = incoming - cached - written
    if ordinary < 0:
        raise ValueError("Overlapping input categories")
    metadata = profile.get("metadata") or {}
    if response.get("model") and response["model"] not in {
        profile["model_key"],
        *metadata.get("accepted_response_models", []),
    }:
        raise ValueError("Unpriced response model")
    tier = tier_key(
        response.get("service_tier") or metadata.get("service_tier", "default")
    )
    threshold = metadata.get("long_context_threshold_tokens")
    values = profile_rates(
        profile, tier, long_context=threshold is not None and incoming > threshold
    )
    breakdown = {
        INPUT: ordinary,
        CACHED: cached,
        WRITE: write30,
        WRITE12: write12,
        OUTPUT: outgoing,
    }
    amount = sum(
        (rate(values, key) * n for key, n in breakdown.items() if n), Decimal(0)
    )
    return amount, {
        "provider_usage": deepcopy(usage),
        "service_tier": tier,
        "ordinary_input_tokens": ordinary,
        "cached_input_tokens": cached,
        "cache_write_30m_tokens": write30,
        "cache_write_12h_tokens": write12,
        "output_tokens": outgoing,
    }
