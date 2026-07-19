#!/usr/bin/env python3
"""
metrimatch.py

Make one font ("target") COMPLETELY metrically compatible with another
font ("reference"): same units-per-em, ascent/descent/line-gap, OS/2
metrics, hhea metrics, post underline metrics, per-glyph advance widths
(matched by glyph name), glyph outlines rescaled to compensate for any
change in units-per-em, and (optionally) the reference's GPOS/GDEF
kerning & positioning data -- so text set in either font lines up
identically (same line height, same baseline position, same widths and
same kerning for shared glyph names).

Requires: fonttools  (pip install fonttools)

Usage:
    python metrimatch.py TARGET.ttf REFERENCE.ttf OUTPUT.ttf

What "metrically compatible" means here, concretely:
  - head.unitsPerEm                          -> copied from reference
  - all glyph outlines (glyf or CFF)         -> uniformly scaled so they
                                                 stay visually the same
                                                 size at the new unitsPerEm
  - hhea (ascent/descent/lineGap/...)        -> copied from reference
  - OS/2 (sTypo*, usWin*, sxHeight,
           sCapHeight, subscript/superscript,
           strikeout, weight/width class)    -> copied from reference
  - post (underlinePosition/Thickness,
           italicAngle, isFixedPitch)        -> copied from reference
  - hmtx / vmtx advance widths & side
    bearings                                 -> rescaled for the new
                                                 unitsPerEm, then (by
                                                 default) overwritten to
                                                 match the reference
                                                 font's width for any
                                                 glyph name the two fonts
                                                 share (so e.g. "A" in
                                                 the target advances by
                                                 exactly as much as "A"
                                                 in the reference)
  - vhea (vertical metrics), if present      -> copied from reference

Glyph outlines are scaled (not just the numbers in the metrics tables)
so that the visual design does not distort when unitsPerEm changes.
"""

import argparse
import io
import re
import sys
import uuid

from fontTools import agl
from fontTools.ttLib import TTFont
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.subset import Subsetter, Options

try:
    from fontTools.pens.t2CharStringPen import T2CharStringPen
except ImportError:  # very old fontTools
    T2CharStringPen = None


def _get(table, name, default=None):
    return getattr(table, name, default)


def _copy_attrs(src, dst, names):
    for name in names:
        if hasattr(src, name):
            setattr(dst, name, getattr(src, name))


def _agl_name_for_unicode(codepoint):
    name = agl.UV2AGL.get(codepoint)
    if name:
        return name
    if codepoint <= 0xFFFF:
        return "uni%04X" % codepoint
    return "u%04X" % codepoint if codepoint <= 0xFFFFF else "u%06X" % codepoint


def build_unicode_rename_map(font, verbose=True):
    cmap = font.getBestCmap()
    name_to_cp = {}
    for cp, name in cmap.items():
        if name not in name_to_cp or cp < name_to_cp[name]:
            name_to_cp[name] = cp

    candidate = {}
    assigned = set()
    for old_name, cp in sorted(name_to_cp.items(), key=lambda kv: kv[1]):
        new_name = _agl_name_for_unicode(cp)
        if new_name == old_name:
            continue
        if new_name in assigned:
            if verbose:
                print(f"  skipping rename {old_name!r} -> {new_name!r}: "
                      f"that canonical name is already claimed by "
                      f"another glyph in this font")
            continue
        candidate[old_name] = new_name
        assigned.add(new_name)

    # Final safety net: a candidate's canonical name might collide with
    # some *other*, unrelated glyph name that isn't itself being renamed.
    # Seed `seen` with every name that will NOT be renamed FIRST, so an
    # existing, untouched glyph name always wins over a candidate that
    # wants to rename into it -- regardless of glyph order. (Iterating
    # in glyph order and only populating `seen` as you go is not enough:
    # if the colliding candidate appears before the untouched glyph it
    # collides with, the candidate claims the name unopposed, and the
    # later check on the untouched glyph has nothing left to protect --
    # silently producing two glyphs with the same name.)
    glyph_order = font.getGlyphOrder()
    seen = {name for name in glyph_order if name not in candidate}
    safe = {}
    for old_name in glyph_order:
        if old_name not in candidate:
            continue
        new_name = candidate[old_name]
        if new_name in seen:
            if verbose:
                print(f"  skipping rename {old_name!r} -> {new_name!r}: "
                      f"would collide with another glyph")
            continue
        seen.add(new_name)
        safe[old_name] = new_name
    candidate = safe

    return candidate


def rename_glyphs_via_ttx(font, rename_map, verbose=True):
    if not rename_map:
        return font

    if verbose:
        print(f"  renaming {len(rename_map)} glyph(s) to canonical "
              f"Unicode-based names...")

    buf = io.StringIO()
    font.saveXML(buf)
    xml_text = buf.getvalue()

    placeholders = {old: f"__RENAME_{uuid.uuid4().hex}__" for old in rename_map}

    for old_name, placeholder in placeholders.items():
        pattern = re.compile(r'="' + re.escape(old_name) + r'"')
        xml_text, n = pattern.subn(f'="{placeholder}"', xml_text)

    for old_name, placeholder in placeholders.items():
        new_name = rename_map[old_name]
        pattern = re.compile(r'="' + re.escape(placeholder) + r'"')
        xml_text = pattern.sub(f'="{new_name}"', xml_text)

    new_font = TTFont()
    new_font.importXML(io.StringIO(xml_text))
    return new_font


def apply_unicode_renaming(target, reference, verbose=True):
    before_shared = len(set(target.getGlyphOrder()) & set(reference.getGlyphOrder()))

    if verbose:
        print("Renaming target glyphs to canonical Unicode-based names:")
    target_map = build_unicode_rename_map(target, verbose=verbose)
    target = rename_glyphs_via_ttx(target, target_map, verbose=verbose)

    if verbose:
        print("Renaming reference glyphs to canonical Unicode-based names:")
    reference_map = build_unicode_rename_map(reference, verbose=verbose)
    reference = rename_glyphs_via_ttx(reference, reference_map, verbose=verbose)

    after_shared = len(set(target.getGlyphOrder()) & set(reference.getGlyphOrder()))
    if verbose:
        print(f"Shared glyph names: {before_shared} before renaming -> "
              f"{after_shared} after renaming.")

    return target, reference


def scale_glyf_outlines(font, factor):
    glyf = font["glyf"]
    glyph_set = font.getGlyphSet()
    glyph_order = font.getGlyphOrder()

    new_glyphs = {}
    for name in glyph_order:
        glyph = glyph_set[name]
        tt_pen = TTGlyphPen(glyph_set)
        transform_pen = TransformPen(tt_pen, (factor, 0, 0, factor, 0, 0))
        glyph.draw(transform_pen)
        new_glyphs[name] = tt_pen.glyph()

    for name in glyph_order:
        glyf[name] = new_glyphs[name]

    for name in glyph_order:
        glyf[name].recalcBounds(glyf)


def scale_cff_outlines(font, factor):
    if T2CharStringPen is None:
        raise RuntimeError(
            "Installed fontTools is too old to support CFF glyph scaling "
            "(need fontTools.pens.t2CharStringPen.T2CharStringPen)."
        )

    cff_table = font["CFF "]
    cff = cff_table.cff
    top_dict = cff[cff.fontNames[0]]
    charstrings = top_dict.CharStrings
    glyph_set = font.getGlyphSet()
    glyph_order = font.getGlyphOrder()

    charstrings.charStringsIndex.items = list(charstrings.charStringsIndex.items)

    for name in glyph_order:
        glyph = glyph_set[name]
        width = glyph.width if glyph.width is not None else 0
        pen = T2CharStringPen(width * factor, glyph_set)
        transform_pen = TransformPen(pen, (factor, 0, 0, factor, 0, 0))
        glyph.draw(transform_pen)
        new_charstring = pen.getCharString(
            private=top_dict.Private if hasattr(top_dict, "Private") else None,
            globalSubrs=cff.GlobalSubrs,
        )
        charstrings[name].bytecode = None
        charstrings[name].program = new_charstring.program

    if hasattr(top_dict, "FontMatrix"):
        m = top_dict.FontMatrix
        top_dict.FontMatrix = [m[0] / factor, m[1], m[2], m[3] / factor, m[4], m[5]]


def scale_outlines(font, factor):
    if abs(factor - 1.0) < 1e-9:
        return
    if "glyf" in font:
        scale_glyf_outlines(font, factor)
    elif "CFF " in font:
        scale_cff_outlines(font, factor)
    else:
        raise RuntimeError("Font has neither 'glyf' nor 'CFF ' outlines; can't scale.")


def scale_hmtx_vmtx(font, factor):
    if abs(factor - 1.0) > 1e-9:
        if "hmtx" in font:
            hmtx = font["hmtx"]
            for name in font.getGlyphOrder():
                aw, lsb = hmtx[name]
                hmtx[name] = (round(aw * factor), round(lsb * factor))
        if "vmtx" in font:
            vmtx = font["vmtx"]
            for name in font.getGlyphOrder():
                ah, tsb = vmtx[name]
                vmtx[name] = (round(ah * factor), round(tsb * factor))


def match_advance_widths(target, reference):
    t_hmtx = target["hmtx"]
    r_hmtx = reference["hmtx"]
    shared = set(target.getGlyphOrder()) & set(reference.getGlyphOrder())
    for name in shared:
        r_aw, _r_lsb = r_hmtx[name]
        _t_aw, t_lsb = t_hmtx[name]
        t_hmtx[name] = (r_aw, t_lsb)

    if "vmtx" in target and "vmtx" in reference:
        t_vmtx = target["vmtx"]
        r_vmtx = reference["vmtx"]
        for name in shared:
            r_ah, _r_tsb = r_vmtx[name]
            _t_ah, t_tsb = t_vmtx[name]
            t_vmtx[name] = (r_ah, t_tsb)


def copy_head_metrics(target, reference):
    head_t = target["head"]
    head_r = reference["head"]
    _copy_attrs(
        head_r,
        head_t,
        [
            "unitsPerEm",
            "macStyle",
            "lowestRecPPEM",
            "fontDirectionHint",
        ],
    )


def copy_hhea_metrics(target, reference):
    if "hhea" not in target or "hhea" not in reference:
        return
    _copy_attrs(
        reference["hhea"],
        target["hhea"],
        [
            "ascent",
            "descent",
            "lineGap",
            "advanceWidthMax",
            "minLeftSideBearing",
            "minRightSideBearing",
            "xMaxExtent",
            "caretSlopeRise",
            "caretSlopeRun",
            "caretOffset",
        ],
    )


def copy_vhea_metrics(target, reference):
    if "vhea" not in target or "vhea" not in reference:
        return
    _copy_attrs(
        reference["vhea"],
        target["vhea"],
        [
            "ascent",
            "descent",
            "lineGap",
            "advanceHeightMax",
            "minTopSideBearing",
            "minBottomSideBearing",
            "yMaxExtent",
            "caretSlopeRise",
            "caretSlopeRun",
            "caretOffset",
        ],
    )


def copy_os2_metrics(target, reference):
    if "OS/2" not in target or "OS/2" not in reference:
        return
    _copy_attrs(
        reference["OS/2"],
        target["OS/2"],
        [
            "usWeightClass",
            "usWidthClass",
            "fsType",
            "ySubscriptXSize",
            "ySubscriptYSize",
            "ySubscriptXOffset",
            "ySubscriptYOffset",
            "ySuperscriptXSize",
            "ySuperscriptYSize",
            "ySuperscriptXOffset",
            "ySuperscriptYOffset",
            "yStrikeoutSize",
            "yStrikeoutPosition",
            "sTypoAscender",
            "sTypoDescender",
            "sTypoLineGap",
            "usWinAscent",
            "usWinDescent",
            "sxHeight",
            "sCapHeight",
            "usDefaultChar",
            "usBreakChar",
            "usMaxContext",
            "panose",
        ],
    )
    if hasattr(reference["OS/2"], "fsSelection"):
        USE_TYPO_METRICS = 0x80
        r_bit = reference["OS/2"].fsSelection & USE_TYPO_METRICS
        target["OS/2"].fsSelection = (
            target["OS/2"].fsSelection & ~USE_TYPO_METRICS
        ) | r_bit


def copy_post_metrics(target, reference):
    if "post" not in target or "post" not in reference:
        return
    _copy_attrs(
        reference["post"],
        target["post"],
        [
            "underlinePosition",
            "underlineThickness",
            "italicAngle",
            "isFixedPitch",
        ],
    )


def transfer_gpos_data(target, reference, verbose=True):
    if "GPOS" not in reference and "kern" not in reference:
        if verbose:
            print("Reference font has no GPOS or legacy kern table -- "
                  "nothing to transfer.")
        return

    shared = sorted(set(target.getGlyphOrder()) & set(reference.getGlyphOrder()))
    if not shared:
        if verbose:
            print("Target and reference share no glyph names -- "
                  "can't transfer GPOS/kern data.")
        return

    if verbose:
        dropped = len(reference.getGlyphOrder()) - len(shared)
        print(f"Transferring GPOS/GDEF/kern: {len(shared)} glyph names "
              f"shared with reference ({dropped} reference-only glyphs "
              f"will be pruned out of any rules that mention them).")

    ref_buf = io.BytesIO()
    reference.save(ref_buf)
    ref_buf.seek(0)
    ref_copy = TTFont(ref_buf)

    _KEEP_FOR_GPOS_TRANSFER = {
        "GlyphOrder", "head", "hhea", "maxp", "OS/2", "hmtx", "cmap",
        "name", "post", "GDEF", "GPOS", "kern",
    }
    for tag in list(ref_copy.keys()):
        if tag not in _KEEP_FOR_GPOS_TRANSFER:
            del ref_copy[tag]

    options = Options()
    options.layout_features = ["*"]
    options.legacy_kern = True
    options.name_IDs = []
    options.notdef_glyph = False
    options.notdef_outline = False
    options.recalc_bounds = False
    options.recalc_timestamp = False
    options.canonical_order = False
    options.retain_gids = False
    options.hinting = False

    subsetter = Subsetter(options=options)
    subsetter.populate(glyphs=shared)
    try:
        subsetter.subset(ref_copy)
    except Exception as exc:
        raise RuntimeError(
            "Failed to prune the reference font's layout tables down to "
            f"the glyphs shared with the target font: {exc}"
        ) from exc

    if "kern" in ref_copy:
        shared_set = set(shared)
        for kern_subtable in ref_copy["kern"].kernTables:
            if hasattr(kern_subtable, "kernTable"):
                kern_subtable.kernTable = {
                    pair: value
                    for pair, value in kern_subtable.kernTable.items()
                    if pair[0] in shared_set and pair[1] in shared_set
                }
        ref_copy["kern"].kernTables = [
            kt
            for kt in ref_copy["kern"].kernTables
            if not hasattr(kt, "kernTable") or kt.kernTable
        ]
        if not ref_copy["kern"].kernTables:
            del ref_copy["kern"]

    if "GPOS" in ref_copy:
        target["GPOS"] = ref_copy["GPOS"]
        if verbose:
            print("Copied pruned GPOS table (kerning, mark positioning, etc.).")
    elif verbose:
        print("No GPOS rules survived pruning (none involved a shared "
              "glyph) -- nothing to copy.")

    if "GDEF" in ref_copy:
        target["GDEF"] = ref_copy["GDEF"]
        if verbose:
            print("Copied pruned GDEF table (glyph classes / mark "
                  "attachment classes GPOS depends on).")

    if "kern" in ref_copy:
        target["kern"] = ref_copy["kern"]
        if verbose:
            print("Copied pruned legacy 'kern' table.")


def recalc_bounds_and_checksums(font):
    if "glyf" in font:
        font.recalcBBoxes = True
    font.recalcTimestamp = True


def make_metrically_compatible(
    target_path,
    reference_path,
    output_path,
    match_widths=True,
    transfer_gpos=True,
    unicode_rename=True,
    verbose=True,
):
    target = TTFont(target_path)
    reference = TTFont(reference_path)

    if unicode_rename:
        target, reference = apply_unicode_renaming(target, reference, verbose=verbose)

    target_upm = target["head"].unitsPerEm
    reference_upm = reference["head"].unitsPerEm
    factor = reference_upm / target_upm

    if verbose:
        print(f"Target unitsPerEm:    {target_upm}")
        print(f"Reference unitsPerEm: {reference_upm}")
        print(f"Outline/metric scale factor: {factor:.6f}")

    scale_outlines(target, factor)
    scale_hmtx_vmtx(target, factor)
    copy_head_metrics(target, reference)
    copy_hhea_metrics(target, reference)
    copy_vhea_metrics(target, reference)
    copy_os2_metrics(target, reference)
    copy_post_metrics(target, reference)

    if match_widths:
        match_advance_widths(target, reference)

    if transfer_gpos:
        transfer_gpos_data(target, reference, verbose=verbose)

    recalc_bounds_and_checksums(target)

    target.save(output_path)
    if verbose:
        print(f"Saved metrically-compatible font to: {output_path}")

    return target


def main():
    parser = argparse.ArgumentParser(
        description="Make TARGET font metrically compatible with REFERENCE font."
    )
    parser.add_argument("target")
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--no-width-match", action="store_true")
    parser.add_argument("--no-gpos-transfer", action="store_true")
    parser.add_argument("--no-unicode-rename", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()

    try:
        make_metrically_compatible(
            args.target,
            args.reference,
            args.output,
            match_widths=not args.no_width_match,
            transfer_gpos=not args.no_gpos_transfer,
            unicode_rename=not args.no_unicode_rename,
            verbose=not args.quiet,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
