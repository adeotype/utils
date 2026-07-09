# Adeotype Python Utils
Useful Python utilities for font generation.


## Converter.py
Quickly convert fonts from one file type to another.

### Dependencies
 - [fonttools](https://github.com/fonttools/fonttools)
 - [brotli](https://github.com/google/brotli)

### Usage
1. Run the script.
2. Enter the path to the font you wish to convert.
3. Choose an output format (1-4).
4. Enter the output font name.


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


## Ranger.py
Generate a plaintext file with the unicode ranges of the inputted font.

### Dependencies
 - [fonttools](https://github.com/fonttools/fonttools)

### Usage
`python ranger.py source.ttf`  
Will output `source_ranges.txt` file with all necessary information.
