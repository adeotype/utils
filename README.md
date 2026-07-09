# Adeotype Python Utils
Useful Python utilities for font generation.

## Metrify.py
Easily copy the metrics from one font to another.

### Dependencies
 - [fonttools](https://github.com/fonttools/fonttools)

### Usage
`python metrify.py source.ttf target.ttf output.ttf`  
Copy and remap **only** the glyph widths. Usecase:
 - You only want the **same characther spacing** as the source font.

`python metrify.py source.ttf target.ttf output.ttf --copy-lsb`  
Copy and remap **only** the left side bearing (the amount of empty space between the glyph's origin and the leftmost edge of the glyph outline). Usecases:
 - The source and target fonts have **matching** or **similar** glyph outlines.
 - You want glyphs positions identically inside their advance widths.
 - You are transferring metrics between builds of the same font family.

`python metrify.py source.ttf target.ttf output.ttf --full-metric`  
Copy and remap widths **and** global font metrics (ascent, descent, etc.) Usecase: 
 - You want the target font to behave like the source font in word processing applications.
 - You want matching line spacing and vertical alignment.
 - You are trying to create a metrically-compatible font.

`python metrify.py source.ttf target.ttf output.ttf --copy-lsb --full-metric`  
Copy and remap **everything**. Usage:
 - You want a **fully** metrically-compatible font.
