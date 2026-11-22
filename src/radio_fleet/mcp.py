"""Adapter for memory-channels-processor (MCP): the reader of the upstream sources (R1) and the writer of the
formats it supports, such as the Yaesu FT5D's ADMS CSV (R7)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class McpError(RuntimeError):
    pass


class FetchError(McpError):
    pass


class ExportError(McpError):
    pass


class Fetcher(Protocol):
    def fetch_csv(self, source: str) -> str:
        """Return MCP's CSV output for one source."""
        ...


class Exporter(Protocol):
    def export(self, channels_csv: str, output_format: str, options: Sequence[str]) -> str:
        """Return MCP's output in `output_format` for channels given as MCP CSV, with the format's options."""
        ...


class McpCli:
    """Runs MCP as a subprocess.

    MCP 0.2.5's JSON output fails with the installed pandas, so the CSV output is used.
    The request cache is disabled because MCP would otherwise write it into the working directory.
    """

    def __init__(self, command: Sequence[str] = (sys.executable, "-m", "memory_channels_processor")) -> None:
        self._command = tuple(command)

    def fetch_csv(self, source: str) -> str:
        args = ["--source", source, "--output-format", "csv"]
        return self._run(args, f"{source}.csv", FetchError, f"source {source!r}")

    def export(self, channels_csv: str, output_format: str, options: Sequence[str]) -> str:
        args = ["--source", "csv", "--csv-input-file", "channels.csv", "--offline", "--output-format", output_format]
        return self._run([*args, *options], "output.csv", ExportError, f"the {output_format} output", channels_csv)

    def _run(self, args: list[str], name: str, error: type[McpError], what: str, channels_csv: str = "") -> str:
        """Run MCP in an empty directory, with `channels_csv` as its file `channels.csv`."""
        with tempfile.TemporaryDirectory(prefix="fleet-mcp-") as tmp:
            out = Path(tmp) / name
            if channels_csv:
                (Path(tmp) / "channels.csv").write_text(channels_csv, encoding="utf-8")
            command = [*self._command, *args, "--output-file", str(out), "--no-cache"]
            try:
                result = subprocess.run(command, capture_output=True, text=True, cwd=tmp)
            except FileNotFoundError:
                raise error(f"memory-channels-processor is not installed: {self._command[0]} not found") from None
            except (OSError, UnicodeDecodeError) as failure:
                raise error(f"memory-channels-processor failed for {what}: {failure}") from None
            if result.returncode != 0 or not out.exists():
                message = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
                raise error(f"memory-channels-processor failed for {what}: {message}")
            try:
                return out.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as failure:
                raise error(f"memory-channels-processor output for {what} is unreadable: {failure}") from None
