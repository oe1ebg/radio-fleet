"""Adapter for dmrconf (qdmr), the check of the qdmr codeplugs (R10). It only verifies files (G1)."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class CheckError(RuntimeError):
    pass


class Verifier(Protocol):
    def verify(self, codeplug: Path, radio: str) -> list[str]:
        """Check a qdmr YAML codeplug for one dmrconf radio key; return the tool's messages, such as warnings.

        Raises CheckError with the tool's message when the codeplug fails.
        """
        ...


class DmrconfCli:
    """Runs `dmrconf verify`. Its exit status is the verdict: qdmr 0.15 reports limits and frequency
    ranges as warnings, and warns about every AnyTone APRS system, so its messages are passed on, not failed."""

    def __init__(self, command: Sequence[str] = ("dmrconf",)) -> None:
        self._command = tuple(command)

    def verify(self, codeplug: Path, radio: str) -> list[str]:
        try:
            result = subprocess.run(
                [*self._command, "verify", "--yaml", "--radio", radio, str(codeplug)], capture_output=True, text=True
            )
        except FileNotFoundError:
            raise CheckError(f"dmrconf is not installed: {self._command[0]} not found") from None
        except (OSError, UnicodeDecodeError) as error:
            raise CheckError(f"dmrconf verify failed: {error}") from None
        lines = [line.strip() for line in _ANSI.sub("", result.stderr + result.stdout).splitlines() if line.strip()]
        if result.returncode != 0:
            raise CheckError("\n".join(lines) or f"dmrconf verify: exit status {result.returncode}")
        return lines
