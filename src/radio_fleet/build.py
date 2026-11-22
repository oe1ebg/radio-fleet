"""`fleet build` (R10): render one radio's file and check it with the radio's tool.

The file is checked before it enters `build/<radio>/`, so that directory never holds a file that failed
its check; a failed build also removes the radio's earlier output.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from radio_fleet.dmrconf import CheckError, Dmrconf
from radio_fleet.fleet import Renderer
from radio_fleet.mcp import Converter, ConvertError
from radio_fleet.model import Channel
from radio_fleet.render import chirp, ft5d, qdmr
from radio_fleet.selection import Selection, without
from radio_fleet.sources import Sources


class BuildError(RuntimeError):
    pass


_UNFIT: dict[Renderer, Callable[[Channel], str | None]] = {Renderer.CHIRP: chirp.unfit, Renderer.FT5D: ft5d.unfit}


def fit(selection: Selection) -> Selection:
    """The selection without the channels the radio's output cannot carry, which it drops with the reason (R4)."""
    unfit = _UNFIT.get(selection.radio.renderer)
    return selection if unfit is None else without(selection, unfit)


def build(selection: Selection, sources: Sources, build_dir: Path, dmrconf: Dmrconf, mcp: Converter) -> Path:
    """Return the path of the checked file."""
    radio = selection.radio
    suffix, render, check = _output(selection, sources, dmrconf, mcp)
    output = build_dir / radio.id / f"{radio.id}{suffix}"
    output.unlink(missing_ok=True)
    try:
        text = render()
    except (chirp.RenderError, ft5d.RenderError, ConvertError) as error:
        raise BuildError(str(error)) from None
    with tempfile.TemporaryDirectory(prefix="fleet-build-") as tmp:
        candidate = Path(tmp) / output.name
        candidate.write_text(text, encoding="utf-8")
        try:
            check(candidate)
        except CheckError as error:
            raise BuildError(str(error)) from None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def _output(
    selection: Selection, sources: Sources, dmrconf: Dmrconf, mcp: Converter
) -> tuple[str, Callable[[], str], Callable[[Path], None]]:
    """The file suffix, the renderer and the check of the radio's output."""
    radio = selection.radio
    if radio.renderer is Renderer.QDMR:
        base, dmrconf_radio = radio.base, radio.dmrconf_radio
        if base is None or dmrconf_radio is None:
            raise BuildError("the qdmr renderer needs a base and a dmrconf_radio in the profile")

        def render_qdmr() -> str:
            try:
                return qdmr.render(selection, sources, base.read_text(encoding="utf-8"))
            except qdmr.RenderError as error:
                raise BuildError(f"{base}: {error}") from None

        return ".yaml", render_qdmr, lambda path: dmrconf.verify(dmrconf_radio, path)
    if radio.renderer is Renderer.CHIRP:
        return ".csv", lambda: chirp.render(selection), lambda path: chirp.check(_read(path), selection)
    if radio.renderer is Renderer.FT5D:
        return ".csv", lambda: ft5d.render(selection, mcp), lambda path: ft5d.check(_read(path), selection)
    raise BuildError(f"the {radio.renderer} renderer is not implemented yet")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
