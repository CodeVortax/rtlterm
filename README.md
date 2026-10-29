# rtlterm

Make **Arabic, Persian, Urdu, Pashto, Kurdish and Hebrew** readable in terminals that
cannot join letters or reverse right-to-left text, such as **Termux**.

Pure Python, **no dependencies**, written from scratch. It only uses the Unicode data
that ships with Python (`unicodedata`).

## The problem

A terminal draws one character per cell, left to right, in the order it receives them.
Right-to-left text then shows up with separate letters and backwards words, and Arabic
mixed with English or numbers gets scrambled.

## What it does

1. **Shapes** letters: picks the initial / medial / final / isolated form so words look joined,
   including the lam-alef ligature (لا), Persian and Urdu letters, and marks (harakat) that
   do not break the joining.
2. **Reorders** the line into visual order (a practical subset of Unicode UAX #9): mixed
   Arabic/English/numbers, digits, punctuation, mirrored brackets.
3. **Wraps** long lines by terminal cell width, then reorders each wrapped line, so wrapping
   no longer scrambles the text.
4. **Aligns** right-to-left lines flush right (optional).
5. **Keeps colours**: ANSI colour codes stay on the right words after reversing.

Lines with no right-to-left text pass through untouched, so progress bars and normal output
are not affected. Running it twice on the same text is safe (Arabic).

## Install (Termux)

```bash
pkg install -y python git
git clone https://github.com/CodeVortax/rtlterm
cd rtlterm
pip install .
```

## Try it first

```bash
rtlterm --demo
```

It prints the same sentences four ways (raw, joined only, joined + reordered, flush right).
Pick the block that reads correctly in your terminal.

## Use it

As a filter for any program:

```bash
relink search the mentalist | rtlterm
cat arabic.txt | rtlterm
rtlterm file.txt --width 60 --align right
```

In Python:

```python
from rtlterm import fix, rprint

print(fix("مسلسل The Mentalist الموسم الثالث الحلقة 17"))
rprint("مرحبا بالعالم")                  # print() that fixes right-to-left text first
```

`fix(text, width=None, base="smart", align="auto", marks="keep", digits=None, wrap=True)`

| option | meaning |
|---|---|
| `width` | wrap and align to this many columns (`rprint` uses the terminal width) |
| `base` | `smart` (default): direction of the first word with letters, skipping ids and numbers, so `b24fde4d0  مسلسل ...` is right-to-left. `auto`: first letter (Unicode standard). `rtl` / `ltr`: force |
| `align` | `auto` (right for RTL), `left`, `right`, `center` |
| `marks` | `strip` removes harakat, which many terminal fonts draw badly |
| `digits` | `arabic` (٠١٢) or `latin` (012) |

## Long text

Long lines are wrapped by terminal cell width and every wrapped line is reordered on its
own, so a paragraph of any length stays readable. Measured on a desktop CPU: about
100,000+ characters per second (a 580,000-character paragraph in 4 seconds, 20,000 lines
in 8 seconds), time grows in a straight line with the amount of text, and no wrapped line
is ever wider than the terminal. A phone will be slower but the same shape. A 5,000-letter
word with no spaces is broken into full-width lines.

## Notes and limits

- The output is for **display only**. Do not save or search it: it uses presentation forms.
  Keep the original text and fix it at the moment you print.
- If your terminal already handles Arabic correctly, you do not need this.
- Needs a terminal font that has the Arabic presentation forms (Android's default has them).
- Not implemented: explicit embeddings/isolates (removed) and the bracket-pair rule N0.
- Hebrew uses reordering only (no shaping is needed).

## Tests

```bash
python -m unittest discover -s tests -v
```
