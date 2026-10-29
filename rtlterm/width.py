"""How many terminal cells a character takes (a small wcwidth)."""
import unicodedata as ud
from functools import lru_cache


@lru_cache(maxsize=8192)
def cell_width(ch):
    o = ord(ch)
    if o < 32 or 0x7F <= o < 0xA0:
        return 0
    if ud.category(ch) in ("Mn", "Me", "Cf"):
        return 0                       # combining marks, joiners, direction marks
    if ud.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def display_width(text):
    return sum(cell_width(c) for c in text)
