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
