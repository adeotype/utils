# Copyright (c) 2026 Adeotype Typesetting Group. All rights reserved.
# Please review the LICENSE file before continuing.

#!/usr/bin/env python3
import argparse
from pathlib import Path

from fontTools.ttLib import TTFont

def collapse_ranges(codepoints):
    """
    Convert a sorted list of integers into contiguous ranges.

    Example:
        [65,66,67,70,71]
        -> [(65,67), (70,71)]
    """
    if not codepoints:
        return []

    ranges = []
    start = prev = codepoints[0]

    for cp in codepoints[1:]:
        if cp == prev + 1:
            prev = cp
        else:
            ranges.append((start, prev))
            start = prev = cp

    ranges.append((start, prev))
    return ranges


def format_range(start, end):
    if start == end:
        return f"U+{start:04X}"
    return f"U+{start:04X} - U+{end:04X}"


def get_unicode_codepoints(font_path):
    font = TTFont(font_path)

    codepoints = set()

    for table in font["cmap"].tables:
        if table.isUnicode():
            codepoints.update(table.cmap.keys())

    font.close()

    return sorted(codepoints)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Unicode glyph ranges for a font."
    )

    parser.add_argument(
        "font",
        help="Input font (.ttf, .otf, .ttc)"
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output text file (default: <fontname>_ranges.txt)"
    )

    args = parser.parse_args()

    font_path = Path(args.font)

    if not font_path.exists():
        parser.error(f"Font not found: {font_path}")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = font_path.with_name(
            f"{font_path.stem}_ranges.txt"
        )

    codepoints = get_unicode_codepoints(font_path)
    ranges = collapse_ranges(codepoints)

    with output_path.open("w", encoding="utf-8") as f:
        f.write(f"Font: {font_path.name}\n")
        f.write(f"Unicode glyphs: {len(codepoints)}\n")
        f.write(f"Ranges: {len(ranges)}\n")
        f.write("=" * 40 + "\n\n")

        for start, end in ranges:
            f.write(format_range(start, end) + "\n")

    print(f"Processed: {font_path}")
    print(f"Glyphs : {len(codepoints)}")
    print(f"Ranges : {len(ranges)}")
    print(f"Output : {output_path}")
    
if __name__ == "__main__":
    main()


#!/usr/bin/env python3

import os
import sys

try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("Error: fontTools is not installed.")
    print("Install with: pip install fonttools brotli")
    sys.exit(1)


SUPPORTED_FLAVORS = ["ttf", "otf", "woff", "woff2"]


def convert_font(input_path, output_path, flavor):
    """
    Convert a font to the desired flavor.
    """

    try:
        font = TTFont(input_path)

        if flavor in ["woff", "woff2"]:
            font.flavor = flavor
        else:
            font.flavor = None

        font.save(output_path)
        print(f"\n✔ Font successfully saved to: {output_path}")

    except Exception as e:
        print(f"\n✖ Conversion failed: {e}")


def main():
    print("\n=== Python Font Converter ===\n")

    input_path = input("Enter path to input font file: ").strip()

    if not os.path.isfile(input_path):
        print("Error: File does not exist.")
        return

    print("\nAvailable output formats:")
    for i, f in enumerate(SUPPORTED_FLAVORS, 1):
        print(f"{i}. {f}")

    choice = input("\nChoose output format number: ").strip()

    try:
        flavor = SUPPORTED_FLAVORS[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return

    output_path = input("Enter output file name (with extension): ").strip()

    if not output_path:
        print("Invalid output path.")
        return

    convert_font(input_path, output_path, flavor)


if __name__ == "__main__":
    main()
