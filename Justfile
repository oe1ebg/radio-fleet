# Checks CI and the Archon workflow run. Data-free: no network, no radio data.
ci:
    uv sync --locked
    uv run pytest -q

test:
    uv run pytest -q
