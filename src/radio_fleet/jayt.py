"""Adapter for jayt, the owner's Yaesu tool (R8, R10).

Only `export`, `import` and `check` are called: they convert and check files and never open a port (G1).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Protocol


class JaytError(RuntimeError):
    """A jayt command failed; the message is the tool's own."""


class MissingCommand(JaytError):
    """This jayt has no such command or option."""


class Jayt(Protocol):
    def export(self, file: Path, document: Path) -> None:
        """Write the radio document of `file` as YAML to `document`."""
        ...

    def import_(self, document: Path, output: Path, template: Path) -> None:
        """Build `output` from `document`; `template` supplies what the document lacks."""
        ...

    def check(self, file: Path) -> None:
        """Raise JaytError when jayt refuses the file."""
        ...


# clap's usage errors: this build of jayt does not know the command or one of its options.
_USAGE = re.compile(r"^error: (unrecognized subcommand|unexpected argument)", re.MULTILINE)


class JaytCli:
    def __init__(self, executable: Path, commit: str) -> None:
        self._executable = executable
        self._name = f"jayt {commit}"

    def export(self, file: Path, document: Path) -> None:
        self._run("export", str(file), "--format", "yaml", "-o", str(document))

    def import_(self, document: Path, output: Path, template: Path) -> None:
        self._run("import", str(document), "-o", str(output), "--template", str(template))

    def check(self, file: Path) -> None:
        self._run("check", str(file))

    def _run(self, command: str, *args: str) -> None:
        try:
            result = subprocess.run([str(self._executable), command, *args], capture_output=True, text=True)
        except FileNotFoundError:
            raise JaytError(f"{self._name} is not installed: no file {self._executable}") from None
        except (OSError, UnicodeDecodeError) as error:
            raise JaytError(f"{self._name} {command} failed: {error}") from None
        if result.returncode == 0:
            return
        output = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
        if result.returncode == 2 and _USAGE.search(result.stderr):
            raise MissingCommand(f"{self._name} lacks `jayt {command}` as called:\n{output}")
        raise JaytError(f"{self._name} {command} failed:\n{output}")
