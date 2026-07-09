# Copyright (c) 2026 Adeotype Typesetting Group. All rights reserved.
# Please review the LICENSE file before continuing.

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
