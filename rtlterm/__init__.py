"""rtlterm: make Arabic, Persian, Urdu and Hebrew readable in terminals that cannot
join letters or reverse right-to-left text (like Termux). Pure Python, no dependencies.

    from rtlterm import fix, rprint
    print(fix("مسلسل The Mentalist الحلقة 17"))
    rprint("مرحبا بالعالم")
"""
import shutil
import sys

from .bidi import has_rtl, reorder
from .layout import fix, fix_line
from .shaping import shape
from .width import cell_width, display_width

__version__ = "0.1.0"
__all__ = ["fix", "fix_line", "shape", "reorder", "has_rtl", "rprint",
           "cell_width", "display_width", "terminal_width"]


def terminal_width(default=None):
    """Columns of the terminal, or `default` when output is not a terminal."""
    try:
        if sys.stdout.isatty():
            return shutil.get_terminal_size().columns
    except (OSError, ValueError, AttributeError):
        pass
    return default


def rprint(*args, sep=" ", end="\n", file=None, flush=False, **options):
    """print() that fixes right-to-left text first. Options go to fix()."""
    out = file or sys.stdout
    options.setdefault("width", terminal_width() if out is sys.stdout else None)
    text = fix(sep.join(str(a) for a in args), **options)
    print(text, end=end, file=out, flush=flush)
