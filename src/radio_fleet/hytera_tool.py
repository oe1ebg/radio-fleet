"""Adapter for the Hytera tool, the owner's private CLI for `.rcdx` files (R9, R10).

The repository does not name the tool. `tools.hytera` in the data root's `fleet.yaml` holds its export and
import command lines, with placeholders such as `{base}` for the files, so a later tool replaces the command
lines and nothing else. The commands run in the data root, so their relative paths are relative to it (R13).

The export writes a lossless YAML document of the base file. The import rebuilds the file from the edited
document with the secrets of the base and the defaults of the factory image; it is also the check: it
decodes its result again and fails, naming the field, when a value differs. Both convert files only and
never open a device (G1). A failing command's output is shown to the user as it is, so the tool must name
a field without printing its value: no secret of the base may reach the terminal (R9).
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from radio_fleet.dmrconf import CheckError

# The files each command line must name, as `{name}`.
FILES = {"export": ("base", "document"), "import": ("document", "output", "base", "factory")}
PLACEHOLDER = re.compile(r"\{(\w+)\}")


class HyteraTool(Protocol):
    def export(self, base: Path, document: Path) -> None:
        """Write the lossless YAML of the base file; raise CheckError when the tool fails."""
        ...

    def import_(self, document: Path, output: Path, base: Path, factory: Path) -> None:
        """Rebuild the file from the edited YAML with the base's secrets and the factory image's defaults
        for added records; raise CheckError with the tool's message when the rebuild or its check fails."""
        ...


class HyteraCli:
    def __init__(self, export: Sequence[str], import_: Sequence[str], data_root: Path) -> None:
        self._commands = {"export": tuple(export), "import": tuple(import_)}
        self._data_root = data_root

    def export(self, base: Path, document: Path) -> None:
        self._run("export", base=base, document=document)

    def import_(self, document: Path, output: Path, base: Path, factory: Path) -> None:
        self._run("import", document=document, output=output, base=base, factory=factory)

    def _run(self, command: str, **files: Path) -> None:
        paths = {name: str(path.absolute()) for name, path in files.items()}
        argv = [PLACEHOLDER.sub(lambda match: paths[match[1]], arg) for arg in self._commands[command]]
        try:
            result = subprocess.run(argv, cwd=self._data_root, capture_output=True, text=True)
        except FileNotFoundError:
            raise CheckError(f"the Hytera tool cannot run: {argv[0]} not found") from None
        except (OSError, UnicodeDecodeError) as error:
            raise CheckError(f"the Hytera tool's {command} failed: {error}") from None
        if result.returncode != 0:
            output = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
            raise CheckError(f"the Hytera tool's {command} failed:\n{output}")
