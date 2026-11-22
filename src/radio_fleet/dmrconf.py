"""Adapter for dmrconf (qdmr), the check of the qdmr renderer's output (R5, R10).

Only `dmrconf verify -R <radio>` is called: it checks a codeplug file against the limits of the named
radio and never opens a device (G1).
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class CheckError(RuntimeError):
    """A check failed; the message is the tool's own."""


class Dmrconf(Protocol):
    def verify(self, radio: str, codeplug: Path) -> None:
        """Raise CheckError when dmrconf refuses the codeplug for this radio."""
        ...


class DmrconfCli:
    def __init__(self, command: Sequence[str] = ("dmrconf",)) -> None:
        self._command = tuple(command)

    def verify(self, radio: str, codeplug: Path) -> None:
        try:
            result = subprocess.run(
                [*self._command, "verify", "--radio", radio, str(codeplug)], capture_output=True, text=True
            )
        except FileNotFoundError:
            raise CheckError(f"dmrconf is not installed: {self._command[0]} not found") from None
        except (OSError, UnicodeDecodeError) as error:
            raise CheckError(f"dmrconf verify failed: {error}") from None
        if result.returncode != 0:
            output = _plain(result.stderr) or _plain(result.stdout) or f"exit status {result.returncode}"
            raise CheckError(f"dmrconf verify failed:\n{output}")


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    return _ANSI.sub("", text).strip()
