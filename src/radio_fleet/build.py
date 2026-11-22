"""`fleet build` (R10): render one radio's file and check it with the radio's tool.

The file is checked before it enters `build/<radio>/`, so that directory never holds a file that failed
its check; a failed build also removes the radio's earlier output.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from radio_fleet.dmrconf import CheckError, Dmrconf
from radio_fleet.fleet import Renderer
from radio_fleet.jayt import Jayt, JaytError, MissingCommand
from radio_fleet.render import jayt as jayt_render
from radio_fleet.render import qdmr
from radio_fleet.selection import Selection
from radio_fleet.sources import Sources


class BuildError(RuntimeError):
    pass


def build(selection: Selection, sources: Sources, build_dir: Path, dmrconf: Dmrconf, jayt: Jayt | None = None) -> Path:
    """Return the path of the checked file."""
    radio = selection.radio
    output_dir = build_dir / radio.id
    if radio.renderer is Renderer.QDMR:
        return _qdmr(selection, sources, output_dir, dmrconf)
    if radio.renderer is Renderer.JAYT:
        if jayt is None:
            raise BuildError("the jayt renderer needs tools.jayt (path and commit) in the fleet file")
        return _jayt(selection, output_dir, jayt)
    raise BuildError(f"the {radio.renderer} renderer is not implemented yet")


def _qdmr(selection: Selection, sources: Sources, output_dir: Path, dmrconf: Dmrconf) -> Path:
    radio = selection.radio
    if radio.base is None or radio.dmrconf_radio is None:
        raise BuildError("the qdmr renderer needs a base and a dmrconf_radio in the profile")
    output = output_dir / f"{radio.id}.yaml"
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
    output_dir.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def _jayt(selection: Selection, output_dir: Path, jayt: Jayt) -> Path:
    """Export the base, replace its channels, import with the base as template, check the result.

    The output is the radio file in the base's format and the radio document it was built from. When jayt
    lacks the import or check the build needs, only the document is written, and the error names the gap.
    """
    radio = selection.radio
    if radio.base is None:
        raise BuildError("the jayt renderer needs a base (the radio file) in the profile")
    document = output_dir / f"{radio.id}.jayt.yaml"
    output = output_dir / f"{radio.id}{radio.base.suffix}"
    document.unlink(missing_ok=True)
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="fleet-build-") as tmp:
        exported, edited, candidate = Path(tmp) / "base.yaml", Path(tmp) / document.name, Path(tmp) / output.name
        try:
            jayt.export(radio.base, exported)
            text = jayt_render.render(selection, exported.read_text(encoding="utf-8"))
        except jayt_render.RenderError as error:
            raise BuildError(f"{radio.base}: {error}") from None
        except JaytError as error:
            raise BuildError(str(error)) from None
        edited.write_text(text, encoding="utf-8")
        try:
            jayt.import_(edited, candidate, radio.base)
            jayt.check(candidate)
        except MissingCommand as error:
            output_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(edited, document)
            raise BuildError(f"{error}\nthe radio document is written to {document}") from None
        except JaytError as error:
            raise BuildError(str(error)) from None
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(edited, document)
        shutil.copyfile(candidate, output)
    return output
