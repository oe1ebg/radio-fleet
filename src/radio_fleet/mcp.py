"""Adapter for memory-channels-processor (MCP), the reader of the upstream sources."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class FetchError(RuntimeError):
    pass


class Fetcher(Protocol):
    def fetch_csv(self, source: str) -> str:
        """Return MCP's CSV output for one source."""
        ...


class McpCli:
    """Runs MCP as a subprocess.

    MCP 0.2.5's JSON output fails with the installed pandas, so the CSV output is used.
    The request cache is disabled because MCP would otherwise write it into the working directory.
    """

    def __init__(self, command: Sequence[str] = (sys.executable, "-m", "memory_channels_processor")) -> None:
        self._command = tuple(command)

    def fetch_csv(self, source: str) -> str:
        with tempfile.TemporaryDirectory(prefix="fleet-mcp-") as tmp:
            out = Path(tmp) / f"{source}.csv"
            args = ["--source", source, "--output-format", "csv", "--output-file", str(out), "--no-cache"]
            try:
                result = subprocess.run([*self._command, *args], capture_output=True, text=True, cwd=tmp)
            except FileNotFoundError:
                raise FetchError(f"memory-channels-processor is not installed: {self._command[0]} not found") from None
            if result.returncode != 0 or not out.exists():
                message = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
                raise FetchError(f"memory-channels-processor failed for source {source!r}: {message}")
            return out.read_text(encoding="utf-8")
