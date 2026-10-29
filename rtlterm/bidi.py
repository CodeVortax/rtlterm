"""Bidirectional text (a practical subset of Unicode UAX #9), written from scratch.

A terminal prints characters left to right in the order it receives them. Arabic and
Hebrew read right to left, so before printing we turn the text from logical order (the
order you type and read it) into visual order (the order the characters must appear on
screen from left to right).

Implemented: paragraph direction, weak types (rules W1-W7), neutrals (N1-N2), implicit
levels (I1-I2), line rules L1 and L2, and mirroring of brackets (L4).
Not implemented: explicit embeddings/overrides/isolates (they are removed) and the
bracket-pair rule N0. Both are rare in terminal text.
"""
import unicodedata as ud

_REMOVED = {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI", "BN"}
_NI = {"B", "S", "WS", "ON"}
_STRONG = {"L", "R", "AL"}

_MIRROR_PAIRS = ("()", "[]", "{}", "<>", "«»", "‹›", "⟨⟩",
                 "⟪⟫", "≤≥", "≪≫", "∈∋",
                 "⊂⊃", "⌈⌉", "⌊⌋", "〈〉",
                 "〈〉", "《》", "「」", "『』",
                 "【】", "〔〕", "⦅⦆", "⁅⁆")
MIRROR = {}
for _a, _b in _MIRROR_PAIRS:
    MIRROR[_a], MIRROR[_b] = _b, _a

# characters with no width that only steer direction; they are dropped when printing
INVISIBLE = {"‎", "‏", "؜"}


def classes(chars):
    """Bidi class of each character (unassigned characters count as L)."""
    return [ud.bidirectional(c) or "L" for c in chars]


def is_removed(cls):
    return cls in _REMOVED


def has_rtl(text):
    return any(ud.bidirectional(c) in ("R", "AL") for c in text)


def paragraph_level(cls, base="auto", default="ltr"):
    """0 for a left-to-right paragraph, 1 for right-to-left."""
    if base == "ltr":
        return 0
    if base == "rtl":
        return 1
    for c in cls:
        if c == "L":
            return 0
        if c in ("R", "AL"):
            return 1
    return 1 if default == "rtl" else 0


def resolve_levels(cls, para):
    """Embedding level of every character of one paragraph (rules W1-W7, N1-N2, I1-I2)."""
    n = len(cls)
    sos = "R" if para % 2 else "L"
    t = list(cls)

    prev = sos                                           # W1: marks follow the letter before
    for i in range(n):
        if t[i] == "NSM":
            t[i] = prev
        prev = t[i]

    last = sos                                           # W2: European digits after Arabic
    for i in range(n):                                   #     letters become Arabic digits
        if t[i] in _STRONG:
            last = t[i]
        elif t[i] == "EN" and last == "AL":
            t[i] = "AN"

    t = ["R" if c == "AL" else c for c in t]             # W3

    for i in range(1, n - 1):                            # W4: 1,2  or  1.2 inside numbers
        if t[i] == "ES" and t[i - 1] == "EN" and t[i + 1] == "EN":
            t[i] = "EN"
        elif t[i] == "CS" and t[i - 1] in ("EN", "AN") and t[i + 1] == t[i - 1]:
            t[i] = t[i - 1]

    i = 0                                                # W5: $ and % next to digits
    while i < n:
        if t[i] == "ET":
            j = i
            while j < n and t[j] == "ET":
                j += 1
            if (i > 0 and t[i - 1] == "EN") or (j < n and t[j] == "EN"):
                for k in range(i, j):
                    t[k] = "EN"
            i = j
        else:
            i += 1

    t = ["ON" if c in ("ES", "ET", "CS") else c for c in t]   # W6

    last = sos                                           # W7: digits after Latin stay Latin
    for i in range(n):
        if t[i] in ("L", "R"):
            last = t[i]
        elif t[i] == "EN" and last == "L":
            t[i] = "L"

    emb = "R" if para % 2 else "L"                       # N1, N2
    i = 0
    while i < n:
        if t[i] in _NI:
            j = i
            while j < n and t[j] in _NI:
                j += 1
            lead = sos if i == 0 else ("L" if t[i - 1] == "L" else "R")
            trail = sos if j == n else ("L" if t[j] == "L" else "R")
            new = lead if lead == trail else emb
            for k in range(i, j):
                t[k] = new
            i = j
        else:
            i += 1

    levels = []                                          # I1, I2
    for c in t:
        if para % 2 == 0:
            levels.append(0 if c == "L" else 1 if c == "R" else 2)
        else:
            levels.append(1 if c == "R" else 2)
    return levels


def visual_order(start, end, levels, orig_cls, para):
    """Indexes start..end-1 in the order they appear on screen (rules L1 and L2)."""
    lv = list(levels[start:end])
    reset = True                                         # L1: trailing spaces and separators
    for i in range(end - 1, start - 1, -1):              #     go back to the paragraph level
        c = orig_cls[i]
        if c in ("S", "B"):
            lv[i - start] = para
            reset = True
        elif c == "WS" and reset:
            lv[i - start] = para
        else:
            reset = False
    order = list(range(start, end))
    if not order:
        return order
    top = max(lv)
    low_odd = min((x for x in lv if x % 2), default=None)
    if low_odd is None:
        return order
    for level in range(top, low_odd - 1, -1):            # L2: reverse runs, highest first
        i = 0
        while i < len(order):
            if lv[order[i] - start] >= level:
                j = i
                while j < len(order) and lv[order[j] - start] >= level:
                    j += 1
                order[i:j] = order[i:j][::-1]
                i = j
            else:
                i += 1
    return order


def marks_after_base(order, chars):
    """Reversing a right-to-left run puts combining marks (harakat) before their letter.
    A terminal attaches a combining mark to the character on its left, so move each mark
    back to the right of its letter."""
    out, p, n = [], 0, len(order)
    while p < n:
        q = p
        while q < n and ud.category(chars[order[q]]) in ("Mn", "Me"):
            q += 1
        if q > p and q < n and order[q] < min(order[p:q]):
            out.append(order[q])
            out.extend(sorted(order[p:q]))
            p = q + 1
        else:
            out.append(order[p])
            p += 1
    return out


def mirror(ch):
    return MIRROR.get(ch, ch)


def reorder(text, base="auto", default="ltr"):
    """Visual-order version of one line of text (no shaping, no wrapping)."""
    chars = [c for c in text]
    cls = classes(chars)
    keep = [i for i, c in enumerate(cls) if not is_removed(c)]
    chars, cls = [chars[i] for i in keep], [cls[i] for i in keep]
    para = paragraph_level(cls, base, default)
    levels = resolve_levels(cls, para)
    out = []
    order = marks_after_base(visual_order(0, len(chars), levels, cls, para), chars)
    for i in order:
        ch = chars[i]
        if levels[i] % 2:
            ch = mirror(ch)
        if ch not in INVISIBLE:
            out.append(ch)
    return "".join(out)
