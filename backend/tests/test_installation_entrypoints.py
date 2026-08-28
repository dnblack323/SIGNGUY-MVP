"""Static guards for reproducible private pricing-engine installation paths."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_emergent_bootstrap_installs_all_dependency_sets():
    script = _read("scripts/setup_emergent.sh")

    assert "backend/requirements.txt" in script
    assert "backend/scripts/install_pricing_engine.py" in script
    assert "yarn install --frozen-lockfile" in script


def test_docker_build_uses_ephemeral_pricing_engine_secret():
    dockerfile = _read("backend/Dockerfile")
    compose = _read("docker-compose.yml")

    assert "--mount=type=secret,id=pricing_engine_read_token,required=true" in dockerfile
    assert 'PRICING_ENGINE_READ_TOKEN="$(cat /run/secrets/pricing_engine_read_token)"' in dockerfile
    assert "python scripts/install_pricing_engine.py" in dockerfile
    assert "environment: PRICING_ENGINE_READ_TOKEN" in compose


def test_example_environment_never_contains_a_token_value():
    example = _read(".env.example")
    token_lines = [
        line for line in example.splitlines() if line.startswith("PRICING_ENGINE_READ_TOKEN=")
    ]

    assert token_lines == ["PRICING_ENGINE_READ_TOKEN="]
