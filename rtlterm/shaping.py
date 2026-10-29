"""Arabic-script shaping: pick the initial / medial / final / isolated form of each letter.

Terminals draw one character per cell and do not join letters. This module replaces each
letter with its "presentation form" so the joined word looks right in a plain grid.

The form table is not typed in by hand: it is read from the Unicode database that ships
with Python (`unicodedata`), where every presentation form lists the letter it stands for.
That covers Arabic, Persian, Urdu, Pashto, Kurdish, Sindhi and friends.
"""
import unicodedata as ud

ISOLATED, FINAL, INITIAL, MEDIAL = "isolated", "final", "initial", "medial"
_TAGS = (ISOLATED, FINAL, INITIAL, MEDIAL)

ALEFS = "آأإا"          # alef madda, hamza above, hamza below, plain
LAM = "ل"
TATWEEL = "ـ"
ZWJ, ZWNJ = "‍", "‌"

# Arabic marks (harakat, dagger alef, Quranic marks): drawn on top of the letter.
_MARK_RANGES = ((0x0610, 0x061A), (0x064B, 0x065F), (0x0670, 0x0670), (0x06D6, 0x06DC),
                (0x06DF, 0x06E4), (0x06E7, 0x06E8), (0x06EA, 0x06ED))

_forms = {}      # letter -> {form: presentation character}
_ligatures = {}  # alef variant -> {form: lam-alef ligature}


def _build():
    # Basic Arabic block first so it wins over the extended forms for shared letters
    # (for instance alef maksura keeps only isolated/final, as in standard Arabic).
    for lo, hi in ((0xFE70, 0xFEFD), (0xFB50, 0xFDFF)):
        seen_here = {}
        for cp in range(lo, hi):
            ch = chr(cp)
            dec = ud.decomposition(ch)
            if not dec.startswith("<"):
                continue
            tag, _, rest = dec.partition("> ")
            tag = tag[1:]
            if tag not in _TAGS:
                continue
            base = [chr(int(x, 16)) for x in rest.split()]
            if len(base) == 1:
                if base[0] in _forms and base[0] not in seen_here:
                    continue                      # already given by an earlier block
                seen_here.setdefault(base[0], True)
                _forms.setdefault(base[0], {})[tag] = ch
            elif len(base) == 2 and base[0] == LAM and base[1] in ALEFS:
                _ligatures.setdefault(base[1], {})[tag] = ch


_build()


def is_presentation_form(ch):
    o = ord(ch)
    return 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFC


def is_arabic_mark(ch):
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in _MARK_RANGES)


def joining(ch):
    """'D' joins both sides, 'R' joins only the letter before it, 'U' does not join,
    'T' is transparent (marks), 'C' is the zero width joiner."""
    if ch == TATWEEL:
        return "D"
    if ch == ZWJ:
        return "C"
    if ch == ZWNJ:
        return "U"
    f = _forms.get(ch)
    if f:
        return "D" if (INITIAL in f and MEDIAL in f) else "R"
    if ud.category(ch) in ("Mn", "Me") or (ud.category(ch) == "Cf" and ch != ZWNJ):
        return "T"
    return "U"


def shape_items(chars, marks="keep"):
    """Shape a list of characters.

    Returns a list of (character, [source indexes]); a lam+alef ligature has two sources,
    dropped characters (joiners, stripped marks) have none and are simply left out.
    marks: 'keep' leaves harakat in place, 'strip' removes them (many terminal fonts draw
    them badly).
    """
    n = len(chars)
    kinds = [joining(c) for c in chars]
    out = []
    prev_joins = False          # does the last base letter reach forward to the next one?
    i = 0
    while i < n:
        c, k = chars[i], kinds[i]
        if k == "T":
            if not (marks == "strip" and is_arabic_mark(c)):
                out.append((c, [i]))
            i += 1
            continue

        j = i + 1
        while j < n and kinds[j] == "T":
            j += 1
        next_kind = kinds[j] if j < n else "U"

        # lam + alef becomes one ligature glyph
        if c == LAM and j < n and chars[j] in _ligatures:
            lig = _ligatures[chars[j]]
            form = FINAL if prev_joins else ISOLATED
            out.append((lig.get(form) or lig[ISOLATED], [i, j]))
            for m in range(i + 1, j):
                if not (marks == "strip" and is_arabic_mark(chars[m])):
                    out.append((chars[m], [m]))
            prev_joins = False
            i = j + 1
            continue

        joins_back = prev_joins and k in ("D", "R", "C")
        joins_next = k in ("D", "C") and next_kind in ("D", "R", "C")
        forms = _forms.get(c)
        if forms:
            if joins_back and joins_next:
                want = MEDIAL
            elif joins_back:
                want = FINAL
            elif joins_next:
                want = INITIAL
            else:
                want = ISOLATED
            out.append((forms.get(want) or forms.get(FINAL if joins_back else ISOLATED) or c, [i]))
        elif c not in (ZWJ, ZWNJ):
            out.append((c, [i]))
        prev_joins = joins_next
        i += 1
    return out


def shape(text, marks="keep"):
    """Shape a string. The result is in logical order, only the letter forms changed."""
    return "".join(ch for ch, _ in shape_items(list(text), marks))
