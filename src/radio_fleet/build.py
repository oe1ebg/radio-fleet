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
from radio_fleet.hytera_tool import HyteraTool
from radio_fleet.jayt import Jayt, JaytError, MissingCommand
from radio_fleet.mcp import Exporter, McpError
from radio_fleet.render import chirp, ft5d, hytera, qdmr
from radio_fleet.render import jayt as jayt_render
from radio_fleet.render.csvcheck import CsvCheckError
from radio_fleet.selection import Selection
from radio_fleet.sources import Sources

_SUFFIXES = {Renderer.QDMR: "yaml", Renderer.CHIRP: "csv", Renderer.FT5D: "csv"}


class BuildError(RuntimeError):
    pass


def build(
    selection: Selection,
    sources: Sources,
    build_dir: Path,
    dmrconf: Dmrconf,
    mcp: Exporter,
    jayt: Jayt | None = None,
    hytera_tool: HyteraTool | None = None,
) -> Path:
    """Return the path of the checked file."""
    radio = selection.radio
    if radio.renderer is Renderer.JAYT:
        if jayt is None:
            raise BuildError("the jayt renderer needs tools.jayt (path and commit) in the fleet file")
        return _jayt(selection, build_dir / radio.id, jayt)
    if radio.renderer is Renderer.HYTERA:
        return _hytera(selection, sources, build_dir, hytera_tool)
    output = build_dir / radio.id / f"{radio.id}.{_SUFFIXES[radio.renderer]}"
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


def _hytera(selection: Selection, sources: Sources, build_dir: Path, tool: HyteraTool | None) -> Path:
    """Export the base, edit the export, and rebuild the file; the rebuild is the check.

    The export and the edited YAML stay in a temporary directory: they are derived from the base file,
    which never enters a repository (G2), and only the checked `.rcdx` goes to `build/<radio>/`.
    """
    radio = selection.radio
    if radio.base is None or radio.factory is None:
        raise BuildError("the hytera renderer needs a base and a factory in the profile")
    if tool is None:
        raise BuildError("the hytera renderer needs tools.hytera (export and import commands) in the fleet file")
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
