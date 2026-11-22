import shutil
import sys
from pathlib import Path

import pytest

from radio_fleet.cli import main
from radio_fleet.dmrconf import CheckError, DmrconfCli

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
QDMR_RADIOS = [("d878uv2plus", "d878uv2"), ("d168uv", "d168uv")]


class FakeDmrconf:
    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[Path, str]] = []

    def verify(self, codeplug: Path, radio: str) -> list[str]:
        assert codeplug.is_file()
        self.calls.append((codeplug, radio))
        if self.failure is not None:
            raise CheckError(self.failure)
        return ["Warn: synthetic warning"]


@pytest.fixture
def data(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES, tmp_path / "data")
    return tmp_path / "data"


@pytest.mark.parametrize(("radio", "dmrconf_radio"), QDMR_RADIOS)
def test_build_writes_the_radio_file_and_checks_it(
    data: Path, capsys: pytest.CaptureFixture[str], radio: str, dmrconf_radio: str
) -> None:
    dmrconf = FakeDmrconf()
    assert main(["build", "--data", str(data), "--radio", radio], verifier=dmrconf) == 0
    out = data / "build" / radio / f"{radio}.yaml"
    assert dmrconf.calls == [(out, dmrconf_radio)]
    captured = capsys.readouterr()
    assert f"{radio}: dmrconf: Warn: synthetic warning\n" in captured.err
    assert captured.out == f"{radio}: 8 channels, 4 zones, 4 drops in {out}; dmrconf verify -R {dmrconf_radio} passed\n"
    assert "gen_ch8" in out.read_text()


def test_a_failing_check_fails_the_build_names_the_radio_and_leaves_no_file(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dmrconf = FakeDmrconf(failure="Cannot link reference to 'nope'")
    assert main(["build", "--data", str(data), "--radio", "d878uv2plus"], verifier=dmrconf) == 1
    err = capsys.readouterr().err
    assert err == "fleet build: d878uv2plus: dmrconf verify failed:\nCannot link reference to 'nope'\n"
    assert not (data / "build" / "d878uv2plus" / "d878uv2plus.yaml").exists()


def test_a_radio_without_a_built_renderer_is_refused(data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["build", "--data", str(data), "--radio", "uv5r-mini"], verifier=FakeDmrconf()) == 1
    assert "uv5r-mini: the chirp renderer is not built yet" in capsys.readouterr().err


def fake_dmrconf(tmp_path: Path, stderr: str, status: int) -> DmrconfCli:
    script = tmp_path / "dmrconf.py"
    script.write_text(f"import sys\nsys.stderr.write({stderr!r})\nsys.exit({status})\n")
    return DmrconfCli([sys.executable, str(script)])


def test_dmrconf_messages_are_returned_without_colours(tmp_path: Path) -> None:
    dmrconf = fake_dmrconf(tmp_path, "\x1b[33mWarning: Warn: synthetic\n\x1b[39m", 0)
    assert dmrconf.verify(tmp_path / "codeplug.yaml", "d878uv2") == ["Warning: Warn: synthetic"]


def test_a_dmrconf_exit_status_fails_with_its_message(tmp_path: Path) -> None:
    dmrconf = fake_dmrconf(tmp_path, "\x1b[31mERROR: Cannot read codeplug file\n\x1b[39m", 255)
    with pytest.raises(CheckError, match=r"^ERROR: Cannot read codeplug file$"):
        dmrconf.verify(tmp_path / "codeplug.yaml", "d878uv2")


def test_a_missing_dmrconf_fails_the_check(tmp_path: Path) -> None:
    with pytest.raises(CheckError, match="dmrconf is not installed"):
        DmrconfCli([str(tmp_path / "no-dmrconf")]).verify(tmp_path / "codeplug.yaml", "d878uv2")


@pytest.mark.dmrconf
@pytest.mark.parametrize(("radio", "dmrconf_radio"), QDMR_RADIOS)
def test_dmrconf_verify_passes_on_the_synthetic_base(
    data: Path, capsys: pytest.CaptureFixture[str], radio: str, dmrconf_radio: str
) -> None:
    assert main(["build", "--data", str(data), "--radio", radio]) == 0, capsys.readouterr().err
    assert capsys.readouterr().out.endswith(f"dmrconf verify -R {dmrconf_radio} passed\n")


@pytest.mark.dmrconf
def test_dmrconf_verify_fails_on_a_broken_codeplug(tmp_path: Path) -> None:
    codeplug = tmp_path / "broken.yaml"
    codeplug.write_text(
        "version: 0.12.0\nchannels:\n"
        "  - dmr: {id: ch1, name: Broken, rxFrequency: 433.45 MHz, txFrequency: 433.45 MHz, contact: nope}\n"
    )
    with pytest.raises(CheckError, match="Cannot link reference to 'nope'"):
        DmrconfCli().verify(codeplug, "d878uv2")
