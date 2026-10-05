"""Build the web fonts in /fonts from Source Serif 4 (SIL OFL 1.1).

    uv run --with fonttools --with brotli tools/subset-fonts.py

Downloads the variable TTFs from google/fonts, pins the optical size (17 for
text, 28 for the intro), keeps only the weights the site uses, subsets to
Latin-1 plus Turkish, and writes WOFF2. Source Serif carries the Reserved
Font Name "Source", so the modified files are renamed; the copyright and
license records are kept.
"""

import io
import pathlib
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://github.com/google/fonts/raw/main/ofl/sourceserif4/"
ROMAN = "SourceSerif4%5Bopsz,wght%5D.ttf"
ITALIC = "SourceSerif4-Italic%5Bopsz,wght%5D.ttf"

TURKISH = [0xC7, 0xE7, 0x011E, 0x011F, 0x0130, 0x0131, 0xD6, 0xF6, 0x015E, 0x015F, 0xDC, 0xFC]
PUNCTUATION = [0xA0, 0x2009, 0x200A, 0x202F, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026]

# Text: ASCII, Western European and Turkish letters, typographic punctuation,
# and the few symbols numbers need (× − ≈ ≤ ≥ → ‰ ′ ″).
TEXT_UNICODES = sorted(set(
    list(range(0x20, 0x7F))
    + [ord(c) for c in "¡©«®°±²³´µ·¹»¼½¾¿×÷ÀÁÂÄÅÆÈÉÊËÍÎÏÑÓÔÕØÚÛßàáâäåæèéêëíîïñóôõøúûÿ"]
    + TURKISH
    + PUNCTUATION
    + list(range(0x2010, 0x2028))
    + [0x2030, 0x2032, 0x2033, 0x2039, 0x203A, 0x2044, 0x20AC, 0x2122]
    + [0x2190, 0x2191, 0x2192, 0x2193, 0x2212, 0x2248, 0x2260, 0x2264, 0x2265]
))

# Display: only the intro paragraph uses it.
DISPLAY_UNICODES = sorted(set(list(range(0x20, 0x7F)) + TURKISH + PUNCTUATION + [0xE9]))

BASE_FEATURES = ["kern", "liga", "ccmp", "locl", "mark", "mkmk", "case"]
FIGURES = ["onum", "lnum", "pnum", "tnum"]

CUTS = [
    # output file, source, axis limits, glyph set, OpenType features, family, style
    ("text-roman", ROMAN, {"wght": (400, 600), "opsz": 17}, TEXT_UNICODES,
     BASE_FEATURES + FIGURES, "AC Text", "Regular"),
    ("text-italic", ITALIC, {"wght": 400, "opsz": 17}, TEXT_UNICODES,
     BASE_FEATURES + FIGURES, "AC Text", "Italic"),
    ("display-roman", ROMAN, {"wght": 400, "opsz": 28}, DISPLAY_UNICODES,
     BASE_FEATURES, "AC Display", "Regular"),
]


def rename(font: TTFont, family: str, style: str) -> None:
    names = font["name"]
    for record in list(names.names):
        if record.nameID != 0 and "Source" in record.toUnicode():
            names.removeNames(nameID=record.nameID)
    postscript = f"{family.replace(' ', '')}-{style}"
    for name_id, value in {
        1: family,
        2: style,
        3: f"{postscript}; derived from Source Serif 4",
        4: f"{family} {style}",
        6: postscript,
        16: family,
        17: style,
    }.items():
        names.setName(value, name_id, 3, 1, 0x409)
    if "fvar" in font:
        names.setName(family.replace(" ", ""), 25, 3, 1, 0x409)


def build(out, source, limits, unicodes, features, family, style, sources) -> None:
    font = TTFont(io.BytesIO(sources[source]))

    # Subset before instancing: the instancer leaves a lazily loaded gvar
    # that the subsetter cannot walk.
    options = subset.Options()
    options.layout_features = features
    options.hinting = False
    options.name_IDs = ["*"]
    options.name_languages = [0x409]
    options.notdef_outline = True
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)

    font = instancer.instantiateVariableFont(font, limits)
    rename(font, family, style)
    path = ROOT / "fonts" / f"{out}.woff2"
    font.flavor = "woff2"
    font.save(path)
    print(f"{path.relative_to(ROOT)}: {path.stat().st_size / 1024:.1f} KB")


def main() -> None:
    (ROOT / "fonts").mkdir(exist_ok=True)
    sources = {name: urllib.request.urlopen(BASE + name).read() for name in (ROMAN, ITALIC)}
    for cut in CUTS:
        build(*cut, sources)
    license_text = urllib.request.urlopen(BASE + "OFL.txt").read()
    (ROOT / "fonts" / "OFL.txt").write_bytes(license_text)


if __name__ == "__main__":
    main()
