import shutil
from pathlib import Path

import pytest

from radio_fleet import fleet
from radio_fleet.cli import main
from radio_fleet.config import ConfigError
from radio_fleet.dmrconf import CheckError, DmrconfCli

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class FakeDmrconf:
    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def verify(self, radio: str, codeplug: Path) -> None:
        self.calls.append((radio, codeplug.read_text(encoding="utf-8")))
        if self.error is not None:
            raise CheckError(self.error)


@pytest.fixture
def data(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES, tmp_path / "data")
    return tmp_path / "data"


def output_of(data: Path, radio: str) -> Path:
    return data / "build" / radio / f"{radio}.yaml"


def test_build_writes_the_file_that_passed_the_check(data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    check = FakeDmrconf()
    assert main(["build", "--data", str(data), "--radio", "d878uv2plus"], dmrconf=check) == 0
    output = output_of(data, "d878uv2plus")
    assert capsys.readouterr().out == f"d878uv2plus: {output}\n"
    assert check.calls == [("d878uv2", output.read_text(encoding="utf-8"))]
    assert "id: gen_ch1" in check.calls[0][1]


def test_a_failing_check_fails_the_build_names_the_radio_and_removes_its_output(
    data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["build", "--data", str(data), "--radio", "d168uv"], dmrconf=FakeDmrconf()) == 0
    capsys.readouterr()
    check = FakeDmrconf("dmrconf verify failed:\nFrequency 1000MHz is outside of allowed frequency ranges.")
    assert main(["build", "--data", str(data), "--radio", "d168uv"], dmrconf=check) == 1
    assert capsys.readouterr().err == (
        "fleet build: d168uv: dmrconf verify failed:\nFrequency 1000MHz is outside of allowed frequency ranges.\n"
    )
    assert check.calls[0][0] == "d168uv"
    assert not output_of(data, "d168uv").exists()


@pytest.mark.parametrize(
    ("power", "message"),
    [
        ("5W", "no level with watts for the power 5W in power_levels"),
        ("Turbo", "the qdmr renderer takes the power as Max, High, Mid, Low or Min, not 'Turbo'"),
    ],
)
def test_a_power_the_profile_cannot_resolve_fails_with_the_profile(
    data: Path, power: str, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(fleet_file.read_text().replace("power: High\n    naming", f"power: {power}\n    naming", 1))
    assert main(["build", "--data", str(data), "--radio", "d878uv2plus"], dmrconf=FakeDmrconf()) == 1
    assert capsys.readouterr().err == f"fleet build: {fleet_file}: radios.d878uv2plus.power: {message}\n"


@pytest.mark.parametrize("key", ["base: bases/qdmr/d878uv2plus.yaml", "dmrconf_radio: d878uv2"])
def test_a_qdmr_radio_without_a_base_or_dmrconf_radio_fails_the_build(
    data: Path, key: str, capsys: pytest.CaptureFixture[str]
) -> None:
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(fleet_file.read_text().replace(f"    {key}\n", ""))
    assert main(["build", "--data", str(data), "--radio", "d878uv2plus"], dmrconf=FakeDmrconf()) == 1
    assert capsys.readouterr().err == (
        "fleet build: d878uv2plus: the qdmr renderer needs a base and a dmrconf_radio in the profile\n"
    )


def test_only_a_qdmr_radio_takes_a_dmrconf_radio(data: Path) -> None:
    fleet_file = data / "fleet.yaml"
    fleet_file.write_text(
        fleet_file.read_text().replace("renderer: chirp\n", "renderer: chirp\n    dmrconf_radio: x\n", 1)
    )
    with pytest.raises(
        ConfigError, match=r"radios\.uv5r-mini\.dmrconf_radio: only the qdmr renderer takes a dmrconf radio"
    ):
        fleet.load(fleet_file, data)


@pytest.mark.dmrconf
@pytest.mark.parametrize("radio", ["d878uv2plus", "d168uv"])
def test_dmrconf_verify_passes_the_build_of_a_synthetic_base(
    data: Path, radio: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["build", "--data", str(data), "--radio", radio]) == 0, capsys.readouterr().err
    assert "rxOnly: true" in output_of(data, radio).read_text(encoding="utf-8")


@pytest.mark.dmrconf
def test_dmrconf_verify_refuses_a_channel_outside_the_radio_with_its_message(tmp_path: Path) -> None:
    codeplug = tmp_path / "codeplug.yaml"
    base = (EXAMPLES / "bases" / "qdmr" / "d878uv2plus.yaml").read_text(encoding="utf-8")
    codeplug.write_text(base.replace("433.6125 MHz", "1000 MHz"), encoding="utf-8")
    with pytest.raises(CheckError, match="outside of allowed frequency ranges"):
        DmrconfCli().verify("d878uv2", codeplug)
