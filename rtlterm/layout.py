"""Put it together: shape, wrap to the terminal width, reorder, align, keep colours.

Colour codes (ANSI escapes) are understood: every visible character remembers the colour
it had, so colours stay on the right letters after the text is reversed.
"""
import re
import unicodedata as ud

from . import bidi, shaping
from .width import cell_width

_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")
_DIGITS_ARABIC = {ord(str(i)): chr(0x0660 + i) for i in range(10)}
_DIGITS_LATIN = {**{0x0660 + i: str(i) for i in range(10)}, **{0x06F0 + i: str(i) for i in range(10)}}


class Item:
    """One visible character with the colour and other escapes that belong to it."""
    __slots__ = ("ch", "style", "pre")

    def __init__(self, ch, style="", pre=""):
        self.ch, self.style, self.pre = ch, style, pre


def has_escapes(text):
    return "\x1b" in text


def _sgr_update(state, params):
    parts = params.split(";") if params else [""]
    i = 0
    while i < len(parts):
        p = parts[i]
        if p in ("", "0"):
            state = []
        else:
            take = 1
            if p in ("38", "48") and i + 1 < len(parts):
                take = 3 if parts[i + 1] == "5" else 5 if parts[i + 1] == "2" else 1
            state = state + [";".join(parts[i:i + take])]
            i += take - 1
        i += 1
    return state


def tokenize(line):
    """Split a line into Items and a tail of escapes that follow the last character."""
    items, state, pending, pos = [], [], "", 0
    style = ""
    for m in _ANSI.finditer(line):
        for ch in line[pos:m.start()]:
            items.append(Item(ch, style, pending))
            pending = ""
        pos = m.end()
        seq = m.group(0)
        if seq.startswith("\x1b[") and seq.endswith("m"):
            state = _sgr_update(state, seq[2:-1])
            style = ";".join(state)
        else:
            pending += seq
    for ch in line[pos:]:
        items.append(Item(ch, style, pending))
        pending = ""
    return items, pending


def _shape(items, marks):
    """Shape the characters. Returns (new items, escapes that lost their character)."""
    shaped = shaping.shape_items([it.ch for it in items], marks)
    if not any(it.pre for it in items):           # common case: no stray escapes to track
        return [Item(ch, items[src[0]].style) for ch, src in shaped], ""
    out, firsts, used = [], [], set()
    for ch, src in shaped:
        out.append(Item(ch, items[src[0]].style, "".join(items[k].pre for k in src)))
        firsts.append(src[0])
        used.update(src)
    tail = ""
    for k in reversed(range(len(items))):         # characters dropped by shaping (joiners,
        if k in used or not items[k].pre:         # stripped marks) hand their escapes on
            continue
        for idx, first in enumerate(firsts):
            if first > k:
                out[idx].pre = items[k].pre + out[idx].pre
                break
        else:
            tail = items[k].pre + tail
    return out, tail


def _drop_removed(items):
    """Remove invisible formatting characters, keeping their escapes."""
    out, carry = [], ""
    for it in items:
        if bidi.is_removed(ud.bidirectional(it.ch)):
            carry += it.pre
            continue
        if carry:
            it.pre = carry + it.pre
            carry = ""
        out.append(it)
    return out, carry


def wrap_ranges(items, width):
    """Greedy word wrap on logical order. Returns [(start, end)] item ranges."""
    n = len(items)
    if not width or width <= 0:
        return [(0, n)]
    widths = [cell_width(it.ch) for it in items]
    ranges, start, i = [], 0, 0
    line_w = 0
    last_break = None                             # index after the last space on this line
    while i < n:
        w = widths[i]
        if line_w + w > width and i > start:
            if last_break is not None and last_break > start:
                ranges.append((start, last_break))
                start = last_break
            else:
                ranges.append((start, i))
                start = i
            # restart the width count for the new line
            line_w = sum(widths[start:i])
            last_break = None
            continue
        line_w += w
        i += 1
        if items[i - 1].ch == " ":
            last_break = i
    ranges.append((start, n))
    return ranges


def _emit(order_items, tail=""):
    out, cur = [], ""
    for it in order_items:
        if it.style != cur:
            if cur:
                out.append("\x1b[0m")
            if it.style:
                out.append("\x1b[%sm" % it.style)
            cur = it.style
        out.append(it.pre)
        if it.ch not in bidi.INVISIBLE:
            out.append(it.ch)
    if cur:
        out.append("\x1b[0m")
    out.append(tail)
    return "".join(out)


def fix_line(line, *, width=None, base="smart", default="ltr", align="auto",
             marks="keep", digits=None, wrap=True, do_shape=True, do_bidi=True):
    """Fix one logical line. Returns one or more output lines joined by newlines."""
    if "\r" in line:
        return "\r".join(fix_line(p, width=width, base=base, default=default, align=align,
                                  marks=marks, digits=digits, wrap=wrap, do_shape=do_shape,
                                  do_bidi=do_bidi) for p in line.split("\r"))
    if not any(bidi.has_rtl(c) for c in line if ord(c) > 0x590):
        return line                               # nothing right-to-left here: leave as is
    if do_shape and any(shaping.is_presentation_form(c) for c in line):
        do_shape = False                          # already shaped (running twice is safe)
        if do_bidi and base in ("auto", "smart"):
            return line

    line = line.expandtabs(8)
    if digits == "arabic":
        line = line.translate(_DIGITS_ARABIC)
    elif digits == "latin":
        line = line.translate(_DIGITS_LATIN)

    items, tail = tokenize(line)
    if do_shape:
        items, lost = _shape(items, marks)
        tail = lost + tail
    items, carry = _drop_removed(items)
    tail = carry + tail

    cls = bidi.classes([it.ch for it in items])
    para = bidi.paragraph_level(cls, base, default) if do_bidi else 0
    levels = bidi.resolve_levels(cls, para) if do_bidi else [0] * len(items)

    chars = [it.ch for it in items]               # built once: used for every wrapped line
    ranges = wrap_ranges(items, width if wrap else None)
    lines = []
    for k, (s, e) in enumerate(ranges):
        while e - s > 1 and items[e - 1].ch == " " and k < len(ranges) - 1:
            e -= 1                                # drop the space where the line was cut
        if do_bidi:
            order = bidi.marks_after_base(
                bidi.visual_order(s, e, levels, cls, para), chars)
        else:
            order = list(range(s, e))
        shown = []
        for idx in order:
            it = items[idx]
            if levels[idx] % 2 and do_bidi:
                it = Item(bidi.mirror(it.ch), it.style, it.pre)
            shown.append(it)
        text = _emit(shown, tail if k == len(ranges) - 1 else "")
        used = sum(cell_width(it.ch) for it in shown)
        pad = 0
        if width and width > used:
            want = align
            if want == "auto":
                want = "right" if para % 2 else "left"
            pad = {"right": width - used, "center": (width - used) // 2}.get(want, 0)
        lines.append(" " * pad + text)
    return "\n".join(lines)


def fix(text, **kw):
    """Fix a whole text, line by line. A trailing newline is kept."""
    parts = text.split("\n")
    return "\n".join(fix_line(p, **kw) for p in parts)
