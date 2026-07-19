#!/usr/bin/env python3
"""
fontnames.py

Export OpenType/TrueType name records and OS/2 vendor ID (achVendID)
to editable TOML and apply them back to a font.

Requires:
    pip install fonttools

Examples:
    python fontnames.py export MyFont.otf
    # edit MyFont.names.toml
    python fontnames.py apply MyFont.otf MyFont.names.toml MyFont-edited.otf

    python fontnames.py show MyFont.otf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from fontTools.ttLib import TTFont, newTable

try:
    import tomllib
except ImportError:
    print("Python 3.11+ is required for tomllib.", file=sys.stderr)
    raise


NAME_IDS = {
    0: "copyright",
    1: "family",
    2: "subfamily",
    3: "unique_id",
    4: "full_name",
    5: "version",
    6: "postscript_name",
    7: "trademark",
    8: "manufacturer",
    9: "designer",
    10: "description",
    11: "vendor_url",
    12: "designer_url",
    13: "license",
    14: "license_url",
    16: "typographic_family",
    17: "typographic_subfamily",
    18: "compatible_full_name",
    19: "sample_text",
    20: "postscript_cid_name",
    21: "wws_family",
    22: "wws_subfamily",
    25: "variations_postscript_prefix",
}


def name_label(name_id: int) -> str:
    return NAME_IDS.get(name_id, f"name_id_{name_id}")


def toml_string(value: str) -> str:
    replacements = {
        "\\": "\\\\",
        '"': '\\"',
        "\b": "\\b",
        "\t": "\\t",
        "\n": "\\n",
        "\f": "\\f",
        "\r": "\\r",
    }

    result = []

    for char in value:
        if char in replacements:
            result.append(replacements[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            result.append(f"\\u{ord(char):04X}")
        else:
            result.append(char)

    return '"' + "".join(result) + '"'


def decode_record(record) -> tuple[str, str | None]:
    try:
        return record.toUnicode(), None
    except Exception as exc:
        return record.toUnicode(errors="replace"), str(exc)


def extract_records(font: TTFont) -> list[dict[str, Any]]:
    if "name" not in font:
        return []

    records = []

    for record in font["name"].names:
        value, error = decode_record(record)

        item = {
            "name_id": record.nameID,
            "label": name_label(record.nameID),
            "platform_id": record.platformID,
            "encoding_id": record.platEncID,
            "language_id": record.langID,
            "value": value,
        }

        if error:
            item["decode_warning"] = error

        records.append(item)

    records.sort(
        key=lambda x: (
            x["name_id"],
            x["platform_id"],
            x["encoding_id"],
            x["language_id"],
        )
    )

    return records


def extract_os2(font: TTFont) -> dict[str, Any]:
    """
    Extract OS/2 table metadata.

    achVendID is stored as a four-byte vendor identifier.
    """

    if "OS/2" not in font:
        return {}

    value = font["OS/2"].achVendID

    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")

    return {
        "achVendID": value.rstrip("\0").strip()
    }


def validate_achVendID(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("achVendID must be a string")

    if len(value) != 4:
        raise ValueError(
            "achVendID must be exactly 4 characters"
        )

    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            "achVendID must contain ASCII characters only"
        )

    return value


def render_toml(
    source: Path,
    records: list[dict[str, Any]],
    os2: dict[str, Any],
) -> str:

    lines = [
        "# Font metadata",
        "#",
        "# Edit values freely.",
        "#",
        "# achVendID is the OS/2 table vendor identifier.",
        "# It must be exactly four ASCII characters.",
        "",
        f"source = {toml_string(source.name)}",
    ]

    if "achVendID" in os2:
        lines.append(
            f"achVendID = {toml_string(os2['achVendID'])}"
        )

    lines.extend([
        "",
        "# Font name table",
        "#",
    ])

    for name_id, label in sorted(NAME_IDS.items()):
        lines.append(
            f"#   {name_id:>2} = {label}"
        )

    lines.append("")

    for record in records:
        lines.append("[[names]]")
        lines.append(
            f"name_id = {record['name_id']}"
        )
        lines.append(
            f"label = {toml_string(record['label'])}"
        )
        lines.append(
            f"platform_id = {record['platform_id']}"
        )
        lines.append(
            f"encoding_id = {record['encoding_id']}"
        )
        lines.append(
            f"language_id = {record['language_id']}"
        )

        if "decode_warning" in record:
            lines.append(
                "# decode_warning = "
                + toml_string(record["decode_warning"])
            )

        lines.append(
            f"value = {toml_string(record['value'])}"
        )

        lines.append("")

    return "\n".join(lines)

def export_font(
    font_path: Path,
    output_path: Path | None,
) -> None:

    font = TTFont(font_path)

    try:
        records = extract_records(font)
        os2 = extract_os2(font)

    finally:
        font.close()

    text = render_toml(
        font_path,
        records,
        os2,
    )

    if output_path is None:
        output_path = font_path.with_suffix(
            ".names.toml"
        )

    output_path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        f"Wrote {len(records)} name records "
        f"to {output_path}"
    )


def show_font(font_path: Path) -> None:

    font = TTFont(font_path)

    try:
        records = extract_records(font)
        os2 = extract_os2(font)

    finally:
        font.close()

    if "achVendID" in os2:
        print(
            f"achVendID: {os2['achVendID']}"
        )

    print()

    for record in records:

        location = (
            f"p{record['platform_id']}/"
            f"e{record['encoding_id']}/"
            f"l0x{record['language_id']:04X}"
        )

        print(
            f"{record['name_id']:>3} "
            f"{record['label']:<30} "
            f"{location:<20} "
            f"{record['value']!r}"
        )


def validate_record(
    record: dict[str, Any],
    index: int,
) -> None:

    required = {
        "name_id",
        "platform_id",
        "encoding_id",
        "language_id",
        "value",
    }

    missing = required - record.keys()

    if missing:
        raise ValueError(
            f"names[{index}] is missing: "
            f"{', '.join(sorted(missing))}"
        )

    for field in (
        "name_id",
        "platform_id",
        "encoding_id",
        "language_id",
    ):

        if not isinstance(record[field], int):
            raise ValueError(
                f"names[{index}].{field} "
                "must be an integer"
            )

    if not isinstance(record["value"], str):
        raise ValueError(
            f"names[{index}].value "
            "must be a string"
        )


def apply_names(
    font_path: Path,
    metadata_path: Path,
    output_path: Path,
) -> None:

    with metadata_path.open("rb") as file:
        metadata = tomllib.load(file)

    records = metadata.get(
        "names",
        [],
    )

    if not isinstance(records, list):
        raise ValueError(
            "'names' must be an array of TOML tables"
        )


    seen = set()

    for index, record in enumerate(records):

        validate_record(
            record,
            index,
        )

        key = (
            record["name_id"],
            record["platform_id"],
            record["encoding_id"],
            record["language_id"],
        )

        if key in seen:
            raise ValueError(
                f"Duplicate name record "
                f"at names[{index}]: {key}"
            )

        seen.add(key)


    if "achVendID" in metadata:
        validate_achVendID(
            metadata["achVendID"]
        )


    font = TTFont(font_path)

    try:

        #
        # Update OS/2 vendor ID
        #
        if (
            "achVendID" in metadata
            and "OS/2" in font
        ):

            font["OS/2"].achVendID = (
                metadata["achVendID"]
            )


        #
        # Rebuild name table
        #
        if "name" not in font:

            font["name"] = newTable(
                "name"
            )

            font["name"].names = []


        name_table = font["name"]

        # TOML is authoritative.
        name_table.names = []


        for record in records:

            name_table.setName(
                record["value"],
                record["name_id"],
                record["platform_id"],
                record["encoding_id"],
                record["language_id"],
            )


        font.save(output_path)


    finally:
        font.close()


    print(
        f"Wrote rebuilt font to {output_path}"
    )


def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        description=(
            "Inspect and edit "
            "OpenType/TrueType font metadata."
        )
    )


    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )


    show_parser = subparsers.add_parser(
        "show",
        help="Print font metadata.",
    )

    show_parser.add_argument(
        "font",
        type=Path,
    )


    export_parser = subparsers.add_parser(
        "export",
        help="Export metadata to TOML.",
    )

    export_parser.add_argument(
        "font",
        type=Path,
    )

    export_parser.add_argument(
        "-o",
        "--output",
        type=Path,
    )


    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply edited TOML.",
    )

    apply_parser.add_argument(
        "font",
        type=Path,
    )

    apply_parser.add_argument(
        "metadata",
        type=Path,
    )

    apply_parser.add_argument(
        "output",
        type=Path,
    )


    return parser


def main() -> int:

    parser = build_parser()

    args = parser.parse_args()


    try:

        if args.command == "show":

            show_font(
                args.font
            )


        elif args.command == "export":

            export_font(
                args.font,
                args.output,
            )


        elif args.command == "apply":

            apply_names(
                args.font,
                args.metadata,
                args.output,
            )


    except Exception as exc:

        print(
            f"error: {exc}",
            file=sys.stderr,
        )

        return 1


    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
    
