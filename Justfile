# Checks CI and the Archon workflow run. Data-free: no network, no radio data.
ci:
    uv sync --locked
    uv run ruff check
    uv run ruff format --check
    uv run mypy
    uv run zizmor --offline .github/workflows
    uv run pytest -q

test:
    uv run pytest -q

# Tests that need dmrconf (qdmr 0.15); fails instead of skipping when dmrconf is missing.
test-dmrconf:
    FLEET_REQUIRE_DMRCONF=1 uv run pytest -q -m dmrconf

# Replays the fleet-step fixtures (needs the archon CLI; local only, not in CI).
workflow-test:
    archon workflow test .archon/workflows/radio-fleet
