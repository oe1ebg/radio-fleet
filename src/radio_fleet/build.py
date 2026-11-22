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
from radio_fleet.hytera_reverse import HyteraTool
from radio_fleet.render import hytera, qdmr
from radio_fleet.selection import Selection
from radio_fleet.sources import Sources


class BuildError(RuntimeError):
    pass


def build(
    selection: Selection, sources: Sources, build_dir: Path, dmrconf: Dmrconf, hytera: HyteraTool | None = None
) -> Path:
    """Return the path of the checked file. `hytera` is None when the fleet file names no hytera_reverse."""
    radio = selection.radio
    if radio.renderer is Renderer.QDMR:
        return _qdmr(selection, sources, build_dir, dmrconf)
    if radio.renderer is Renderer.HYTERA:
        return _hytera(selection, sources, build_dir, hytera)
    raise BuildError(f"the {radio.renderer} renderer is not implemented yet")


def _qdmr(selection: Selection, sources: Sources, build_dir: Path, dmrconf: Dmrconf) -> Path:
    radio = selection.radio
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


def _hytera(selection: Selection, sources: Sources, build_dir: Path, tool: HyteraTool | None) -> Path:
    """Export the base, edit the export, and rebuild the file; the rebuild is the check.

    The export and the edited YAML stay in a temporary directory: they are derived from the base file,
    which never enters a repository (G2), and only the checked `.rcdx` goes to `build/<radio>/`.
    """
    radio = selection.radio
    if radio.base is None or radio.factory is None:
        raise BuildError("the hytera renderer needs a base and a factory in the profile")
    if tool is None:
        raise BuildError("the hytera renderer needs the hytera_reverse path in the fleet file")
    output = build_dir / radio.id / f"{radio.id}.rcdx"
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="fleet-build-") as tmp:
        exported, edited, candidate = (Path(tmp) / name for name in ("base.yaml", "edited.yaml", output.name))
        try:
            tool.export(radio.base, exported)
            try:
                text = hytera.render(selection, sources, exported.read_text(encoding="utf-8"))
            except hytera.RenderError as error:
                raise BuildError(f"the export of the base: {error}") from None
            edited.write_text(text, encoding="utf-8")
            tool.import_(edited, candidate, radio.base, radio.factory)
        except CheckError as error:
            raise BuildError(str(error)) from None
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate, output)
    return output
