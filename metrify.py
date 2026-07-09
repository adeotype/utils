# Copyright (c) 2026 Adeotype Typesetting Group. All rights reserved.
# Licensed under MIT License. See LICENSE for more information.

#!/usr/bin/env python3
from fontTools.ttLib import TTFont
import argparse,sys

def scale(v,s): return int(round(v*s))

def copy_font_metrics(src,tgt,s):
    if 'hhea' in src and 'hhea' in tgt:
        for f in ('ascent','descent','lineGap'):
            setattr(tgt['hhea'],f,scale(getattr(src['hhea'],f),s))
    if 'OS/2' in src and 'OS/2' in tgt:
        fields=['sTypoAscender','sTypoDescender','sTypoLineGap','usWinAscent','usWinDescent',
        'sxHeight','sCapHeight','ySubscriptXSize','ySubscriptYSize','ySubscriptXOffset',
        'ySubscriptYOffset','ySuperscriptXSize','ySuperscriptYSize','ySuperscriptXOffset',
        'ySuperscriptYOffset','yStrikeoutSize','yStrikeoutPosition']
        for f in fields:
            if hasattr(src['OS/2'],f) and hasattr(tgt['OS/2'],f):
                setattr(tgt['OS/2'],f,scale(getattr(src['OS/2'],f),s))
    if 'post' in src and 'post' in tgt:
        for f in ('underlinePosition','underlineThickness'):
            setattr(tgt['post'],f,scale(getattr(src['post'],f),s))
        if hasattr(src['post'],'isFixedPitch') and hasattr(tgt['post'],'isFixedPitch'):
            tgt['post'].isFixedPitch=src['post'].isFixedPitch
    if 'vhea' in src and 'vhea' in tgt:
        for f in ('ascent','descent','lineGap'):
            setattr(tgt['vhea'],f,scale(getattr(src['vhea'],f),s))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("source");ap.add_argument("target");ap.add_argument("output")
    ap.add_argument("--copy-lsb",action="store_true")
    ap.add_argument("--full-metrics",action="store_true")
    a=ap.parse_args()
    src=TTFont(a.source); tgt=TTFont(a.target)
    s=tgt['head'].unitsPerEm/src['head'].unitsPerEm
    sh=src['hmtx'].metrics; th=tgt['hmtx'].metrics
    sc=src.getBestCmap() or {}; tc=tgt.getBestCmap() or {}
    done=set(); count=0
    for cp,tg in tc.items():
        sg=sc.get(cp)
        if sg in sh:
            w,l=sh[sg]; _,tl=th[tg]
            th[tg]=(scale(w,s), scale(l,s) if a.copy_lsb else tl)
            done.add(tg); count+=1
    for g in tgt.getGlyphOrder():
        if g in done or g not in sh or g not in th: continue
        w,l=sh[g]; _,tl=th[g]
        th[g]=(scale(w,s), scale(l,s) if a.copy_lsb else tl); count+=1
    if a.full_metrics: copy_font_metrics(src,tgt,s)
    tgt.save(a.output)
    print(f"Copied {count} glyph metrics")
    print(f"Scale factor {s:.4f}")
    print(f"Full metrics: {a.full_metrics}")
if __name__=="__main__":
    try: main()
    except Exception as e:
        print(e); sys.exit(1)
