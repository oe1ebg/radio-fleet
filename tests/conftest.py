import csv
import io

from radio_fleet.snapshot import COLUMNS

# MCP output has more columns than the snapshot keeps; these stand in for the extra ones.
MCP_EXTRA_COLUMNS = ("offset", "dup", "name_formatted", "distance")


def mcp_row(**values: str) -> dict[str, str]:
    row = {column: "" for column in (*COLUMNS, *MCP_EXTRA_COLUMNS)}
    row.update({flag: "False" for flag in ("fm", "dmr", "c4fm", "dstar", "skip", "loc_exact")})
    row.update(source_id="synthetic-db", source_license="CC BY 4.0")
    row.update(values)
    return row


def mcp_csv(rows: list[dict[str, str]]) -> str:
    """CSV with MCP's CRLF line ends; the extra columns come first, where MCP puts them last, so normalize must reorder."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(MCP_EXTRA_COLUMNS) + list(COLUMNS), lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


FM_REPEATER = mcp_row(callsign="XX0FM", name="Synthetic Hill", band="2m", freq_tx="145.0", freq_rx="145.6",
                      ctcss_tx="88.5", ctcss_rx="88.5", fm="True", offset="0.6", dup="-")
DMR_REPEATER = mcp_row(callsign="XX0DM", name="Synthetic Tower", band="70cm", freq_tx="431.4625", freq_rx="438.9625",
                       dmr="True", dmr_cc="1", dmr_id="999001")
