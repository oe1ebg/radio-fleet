"""Adapter for hytera_reverse, the tool of the Hytera renderer (R9, R10).

Only its file converters are called: `rcdx_yaml.py --lossless` exports a base `.rcdx` to YAML, and
`rcdx_import.py` rebuilds a `.rcdx` from the edited YAML. The import is also the check: it decodes the
rebuilt file again and fails, naming the path, when a value differs. Neither tool opens a device (G1).
The export is never asked for secrets; the import takes them from the base file and prints none.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from radio_fleet.dmrconf import CheckError


class HyteraTool(Protocol):
    def export(self, base: Path, document: Path) -> None:
        """Write the lossless YAML of the base file; raise CheckError when the tool fails."""
        ...

    def import_(self, document: Path, output: Path, base: Path, factory: Path) -> None:
        """Rebuild the file from the edited YAML with the base's secrets and the factory image's defaults
        for added records; raise CheckError with the tool's message when the rebuild or its check fails."""
        ...


class HyteraReverseCli:
    def __init__(self, project: Path, python: Sequence[str] | None = None) -> None:
        self._project = project
        self._python = tuple(python) if python is not None else ("uv", "run", "--project", str(project), "python")

    def export(self, base: Path, document: Path) -> None:
        self._run("rcdx_yaml.py", [str(base), "--lossless", "-o", str(document)])

    def import_(self, document: Path, output: Path, base: Path, factory: Path) -> None:
        self._run(
            "rcdx_import.py",
            [str(document), "-o", str(output), "--secrets-from", str(base), "--defaults-from", str(factory)],
        )

    def _run(self, script: str, args: list[str]) -> None:
        try:
            result = subprocess.run(
                [*self._python, str(self._project / "src" / script), *args], capture_output=True, text=True
            )
        except FileNotFoundError:
            raise CheckError(f"hytera_reverse cannot run: {self._python[0]} not found") from None
        except (OSError, UnicodeDecodeError) as error:
            raise CheckError(f"{script} failed: {error}") from None
        if result.returncode != 0:
            output = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
            raise CheckError(f"{script} failed:\n{output}")
