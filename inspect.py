#!/usr/bin/env python3

"""
Variable Font Inspector

Requires:
    pip install fonttools brotli

Usage:
    python inspect.py font.ttf
"""

import json
import sys
from pathlib import Path

from fontTools.ttLib import TTFont


def get_axes(font):
    if "fvar" not in font:
        return []

    axes = []

    for axis in font["fvar"].axes:
        axes.append({
            "tag": axis.axisTag,
            "min": axis.minValue,
            "default": axis.defaultValue,
            "max": axis.maxValue,
            "flags": axis.flags,
            "nameID": axis.axisNameID
        })

    return axes


def get_instances(font):
    if "fvar" not in font:
        return []

    instances = []

    for inst in font["fvar"].instances:
        instances.append({
            "coordinates": dict(inst.coordinates),
            "flags": inst.flags,
            "subfamilyNameID": inst.subfamilyNameID
        })

    return instances


def get_features(font):

    features = []

    for table_name in ("GSUB", "GPOS"):

        if table_name not in font:
            continue

        table = font[table_name].table

        if not hasattr(table, "FeatureList"):
            continue

        feature_records = table.FeatureList.FeatureRecord

        for record in feature_records:

            features.append({
                "table": table_name,
                "tag": record.FeatureTag,
                "lookups": list(record.Feature.LookupListIndex)
            })

    return features


def dump(font_path):

    font = TTFont(font_path)

    data = {
        "font": Path(font_path).name,
        "variable": "fvar" in font,
        "axes": get_axes(font),
        "instances": get_instances(font),
        "features": get_features(font)
    }

    print(json.dumps(data, indent=4))


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage: python inspect.py font.ttf")
        sys.exit(1)

    dump(sys.argv[1])
