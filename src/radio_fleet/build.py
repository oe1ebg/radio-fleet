"""`fleet build` (R10): render one radio's file and check it with the radio's tool.

The file is checked before it enters `build/<radio>/`, so that directory never holds a file that failed
its check; a failed build also removes the radio's earlier output.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from radio_fleet.dmrconf import CheckError, Dmrconf
from radio_fleet.fleet import Renderer
from radio_fleet.render import qdmr
from radio_fleet.selection import Selection
from radio_fleet.sources import Sources


class BuildError(RuntimeError):
    pass


def build(selection: Selection, sources: Sources, build_dir: Path, dmrconf: Dmrconf) -> Path:
    """Return the path of the checked file."""
    radio = selection.radio
    if radio.renderer is not Renderer.QDMR:
        raise BuildError(f"the {radio.renderer} renderer is not implemented yet")
    if radio.base is None or radio.dmrconf_radio is None:
        raise BuildError("the qdmr renderer needs a base and a dmrconf_radio in the profile")
    output = build_dir / radio.id / f"{radio.id}.yaml"
    output.unlink(missing_ok=True)
    try:
        text = qdmr.render(selection, sources, radio.base.read_text(encoding="utf-8"))
    except qdmr.RenderError as error:
        raise BuildError(f"{radio.base}: {error}") from None
    with tempfile.TemporaryDirectory(prefix="fleet-build-") as tmp:
        candidate = Path(tmp) / output.name
        candidate.write_text(text, encoding="utf-8")
        try:
            dmrconf.verify(radio.dmrconf_radio, candidate)
        except CheckError as error:
            raise BuildError(str(error)) from None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output
