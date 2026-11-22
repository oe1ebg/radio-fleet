"""Shared test setup.

Tests that need the dmrconf CLI carry `@pytest.mark.dmrconf`. They skip when
dmrconf is not installed. With FLEET_REQUIRE_DMRCONF=1 (the CI dmrconf job), a
missing dmrconf fails them instead, so that job cannot pass by skipping.
"""

from __future__ import annotations

import os
import shutil

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if shutil.which("dmrconf"):
        return
    if os.environ.get("FLEET_REQUIRE_DMRCONF") == "1":
        raise pytest.UsageError("FLEET_REQUIRE_DMRCONF=1, but dmrconf is not on PATH")
    skip = pytest.mark.skip(reason="dmrconf is not installed")
    for item in items:
        if "dmrconf" in item.keywords:
            item.add_marker(skip)
