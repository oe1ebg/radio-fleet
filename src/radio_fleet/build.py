"""`fleet build` (R10): render one radio's file and check it with the radio's tool.

The file is checked before it enters `build/<radio>/`, so that directory never holds a file that failed
its check; a failed build also removes the radio's earlier output.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from radio_fleet.dmrconf import CheckError, Dmrconf
from radio_fleet.fleet import Renderer
from radio_fleet.mcp import Exporter, McpError
from radio_fleet.render import chirp, ft5d, qdmr
from radio_fleet.render.csvcheck import CsvCheckError
from radio_fleet.selection import Selection
from radio_fleet.sources import Sources

_SUFFIXES = {Renderer.QDMR: "yaml", Renderer.CHIRP: "csv", Renderer.FT5D: "csv"}


class BuildError(RuntimeError):
    pass


def build(selection: Selection, sources: Sources, build_dir: Path, dmrconf: Dmrconf, mcp: Exporter) -> Path:
    """Return the path of the checked file."""
    radio = selection.radio
    suffix = _SUFFIXES.get(radio.renderer)
    if suffix is None:
        raise BuildError(f"the {radio.renderer} renderer is not implemented yet")
    output = build_dir / radio.id / f"{radio.id}.{suffix}"
    output.unlink(missing_ok=True)
    capability = radio.capability
    try:
        if radio.renderer is Renderer.CHIRP:
            text = chirp.render(selection)
            chirp.check(text, capability)
        elif radio.renderer is Renderer.FT5D:
            text = ft5d.render(selection, mcp)
            ft5d.check(text, capability)
        else:
            text = _qdmr(selection, sources, dmrconf)
    except (chirp.RenderError, ft5d.RenderError, McpError) as error:
        raise BuildError(str(error)) from None
    except CsvCheckError as error:
        raise BuildError(f"the CSV check failed: {error}") from None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def _qdmr(selection: Selection, sources: Sources, dmrconf: Dmrconf) -> str:
    radio = selection.radio
    if radio.base is None or radio.dmrconf_radio is None:
        raise BuildError("the qdmr renderer needs a base and a dmrconf_radio in the profile")
    try:
        text = qdmr.render(selection, sources, radio.base.read_text(encoding="utf-8"))
    except qdmr.RenderError as error:
        raise BuildError(f"{radio.base}: {error}") from None
    with tempfile.TemporaryDirectory(prefix="fleet-build-") as tmp:
        candidate = Path(tmp) / f"{radio.id}.yaml"
        candidate.write_text(text, encoding="utf-8")
        try:
            dmrconf.verify(radio.dmrconf_radio, candidate)
        except CheckError as error:
            raise BuildError(str(error)) from None
    return text
