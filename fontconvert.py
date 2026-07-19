#!/usr/bin/env python3

"""
fontconvert.py

Convert fonts between TTF, OTF, WOFF, and WOFF2 containers.

Dependencies:
    pip install fonttools brotli

Examples:
    python fontconvert.py font.ttf font.otf
    python fontconvert.py font.ttf font.woff2
    python fontconvert.py font.woff2 font.ttf
    python fontconvert.py font.woff font.woff2

    # Explicit format
    python fontconvert.py font.ttf output --format woff2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fontTools.ttLib import TTFont, TTLibError


SUPPORTED_FORMATS = {"ttf", "otf", "woff", "woff2"}


class FontConversionError(Exception):
    """Raised when a font cannot be converted."""


def detect_output_format(output: Path, explicit_format: str | None) -> str:
    if explicit_format:
        return explicit_format.lower()

    suffix = output.suffix.lower().lstrip(".")

    if suffix not in SUPPORTED_FORMATS:
        raise FontConversionError(
            f"Cannot determine output format from '{output}'. "
            f"Use --format with one of: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    return suffix


def convert_font(source: Path, destination: Path, output_format: str) -> None:
    try:
        font = TTFont(source, recalcBBoxes=False, recalcTimestamp=False)
    except TTLibError as exc:
        raise FontConversionError(
            f"Unable to read font '{source}': {exc}"
        ) from exc

    try:
        # WOFF and WOFF2 are SFNT flavors.
        if output_format in {"woff", "woff2"}:
            font.flavor = output_format
        else:
            font.flavor = None

        # NOTE:
        # Changing .ttf to .otf does not magically convert TrueType
        # 'glyf' outlines into CFF/PostScript outlines. Likewise, an OTF
        # containing CFF data remains CFF when saved with a .ttf extension.
        #
        # TTF and OTF describe font technologies, not merely containers.
        # fontTools safely handles container/flavor conversion, but genuine
        # glyf <-> CFF outline conversion requires a dedicated outline
        # conversion pipeline.

        destination.parent.mkdir(parents=True, exist_ok=True)
        font.save(destination)

    except Exception as exc:
        raise FontConversionError(
            f"Failed to save '{destination}': {exc}"
        ) from exc
    finally:
        font.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fontconvert",
        description="Convert fonts between TTF, OTF, WOFF, and WOFF2.",
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Input font file",
    )

    parser.add_argument(
        "output",
        type=Path,
        help="Output font file",
    )

    parser.add_argument(
        "-f",
        "--format",
        choices=sorted(SUPPORTED_FORMATS),
        help="Explicit output format; otherwise inferred from output extension",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source: Path = args.input
    destination: Path = args.output

    if not source.is_file():
        parser.error(f"Input file does not exist: {source}")

    if destination.exists() and not args.overwrite:
        parser.error(
            f"Output file already exists: {destination} "
            "(use --overwrite to replace it)"
        )

    try:
        output_format = detect_output_format(destination, args.format)
        convert_font(source, destination, output_format)
    except FontConversionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Converted {source} -> {destination} ({output_format.upper()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
