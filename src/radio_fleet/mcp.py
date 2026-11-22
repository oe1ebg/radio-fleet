"""Adapter for memory-channels-processor (MCP): it reads the upstream sources and writes MCP's radio formats."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class FetchError(RuntimeError):
    pass


class ConvertError(RuntimeError):
    pass


class Fetcher(Protocol):
    def fetch_csv(self, source: str) -> str:
        """Return MCP's CSV output for one source."""
        ...


class Converter(Protocol):
    def convert(self, channels_csv: str, output_format: str, options: Sequence[str]) -> str:
        """Return MCP's `output_format` output for channels in MCP's CSV columns, read through MCP's csv source."""
        ...


class McpCli:
    """Runs MCP as a subprocess, in a temporary working directory.

    MCP 0.2.5's JSON output fails with the installed pandas, so the CSV output is used.
    The request cache is disabled because MCP would otherwise write it into the working directory.
    """

    def __init__(self, command: Sequence[str] = (sys.executable, "-m", "memory_channels_processor")) -> None:
        self._command = tuple(command)

    def fetch_csv(self, source: str) -> str:
        what = f"source {source!r}"
        args = ["--source", source, "--output-format", "csv", "--no-cache"]
        return self._run(args, f"{source}.csv", None, what, FetchError)

    def convert(self, channels_csv: str, output_format: str, options: Sequence[str]) -> str:
        what = f"output format {output_format!r}"
        args = ["--source", "csv", "--csv-input-file", "channels.csv", "--output-format", output_format, *options]
        return self._run(args, "output.csv", channels_csv, what, ConvertError)

    def _run(
        self, args: list[str], output_name: str, channels_csv: str | None, what: str, error: type[RuntimeError]
    ) -> str:
        with tempfile.TemporaryDirectory(prefix="fleet-mcp-") as tmp:
            out = Path(tmp) / output_name
            if channels_csv is not None:
                (Path(tmp) / "channels.csv").write_text(channels_csv, encoding="utf-8")
            command = [*self._command, *args, "--output-file", str(out)]
            try:
                result = subprocess.run(command, capture_output=True, text=True, cwd=tmp)
            except FileNotFoundError:
                raise error(f"memory-channels-processor is not installed: {self._command[0]} not found") from None
            except (OSError, UnicodeDecodeError) as exc:
                raise error(f"memory-channels-processor failed for {what}: {exc}") from None
            if result.returncode != 0 or not out.exists():
                message = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
                raise error(f"memory-channels-processor failed for {what}: {message}")
            try:
                return out.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise error(f"memory-channels-processor output for {what} is unreadable: {exc}") from None
