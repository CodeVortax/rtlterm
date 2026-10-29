"""Command line:  rtlterm [files]      fix text from files or from a pipe
                 rtlterm --demo      show the same text four ways to see what your terminal needs
"""
import argparse
import sys

from . import __version__, fix, rprint, terminal_width
from .bidi import has_rtl
from .layout import fix_line
from .shaping import shape

SAMPLES = [
    "مسلسل The Mentalist الموسم الثالث الحلقة 17",
    "b24fde4d0  مسلسل The Mentalist الموسم السابع الحلقة 13",
    "مرحباً بالعالم (تجربة) 2026",
    "سلام دنیا، حال شما چطور است؟",
    "שלום עולם 123",
]


def demo(width):
    bar = "-" * min(width or 40, 60)

    def section(title, fn):
        print(f"\n{bar}\n{title}\n{bar}")
        for s in SAMPLES:
            print(fn(s))

    print(f"rtlterm {__version__}: look at the 4 blocks and tell which one reads correctly.")
    section("1. raw (what you see today)", lambda s: s)
    section("2. letters joined only", lambda s: shape(s))
    section("3. joined + reordered  (usual answer for Termux)",
            lambda s: fix_line(s, width=None))
    section("4. joined + reordered + flush right",
            lambda s: fix_line(s, width=width or 40, align="right"))
    print(f"\n{bar}\nlong line wrapped at {min(width or 40, 40)} columns\n{bar}")
    print(fix_line(" ".join(SAMPLES[:1] * 4), width=min(width or 40, 40)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rtlterm", description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*", help="files to fix (default: standard input)")
    ap.add_argument("--demo", action="store_true", help="show sample text in 4 variants")
    ap.add_argument("--width", type=int, help="wrap/align width (default: terminal width)")
    ap.add_argument("--no-wrap", action="store_true", help="never wrap long lines")
    ap.add_argument("--align", choices=["auto", "left", "right", "center"], default="auto")
    ap.add_argument("--base", choices=["smart", "auto", "rtl", "ltr"], default="smart",
                    help="line direction: smart (default) = first word with letters, skipping "
                         "ids and numbers; auto = first letter; rtl / ltr = force")
    ap.add_argument("--default", choices=["ltr", "rtl"], default="ltr",
                    help="direction when a line has no letters (numbers only)")
    ap.add_argument("--marks", choices=["keep", "strip"], default="keep",
                    help="strip removes harakat/tashkeel (some fonts draw them badly)")
    ap.add_argument("--digits", choices=["arabic", "latin"], help="convert digit style")
    ap.add_argument("--no-shape", action="store_true", help="do not join letters")
    ap.add_argument("--no-bidi", action="store_true", help="do not reorder")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)

    width = a.width or terminal_width()
    if a.demo:
        return demo(width)

    opts = dict(width=width, base=a.base, default=a.default, align=a.align, marks=a.marks,
                digits=a.digits, wrap=not a.no_wrap, do_shape=not a.no_shape,
                do_bidi=not a.no_bidi)
    streams = [open(f, encoding="utf-8", errors="replace") for f in a.files] or [sys.stdin]
    try:
        for stream in streams:
            for line in stream:
                end = "\n" if line.endswith("\n") else ""
                sys.stdout.write(fix_line(line.rstrip("\n"), **opts) + end)
                sys.stdout.flush()
    except (BrokenPipeError, KeyboardInterrupt):
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
