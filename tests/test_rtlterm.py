"""Run:  python -m unittest discover -s tests -v"""
import random
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rtlterm  # noqa: E402
from rtlterm import bidi, shaping  # noqa: E402
from rtlterm.layout import fix_line  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def cps(s):
    return [ord(c) for c in s]


class Shaping(unittest.TestCase):
    def test_initial_medial_final(self):
        # beh, jeem, alef: alef joins only backwards
        self.assertEqual(cps(shaping.shape("ابج")), [0xFE8D, 0xFE91, 0xFE9E])
        self.assertEqual(cps(shaping.shape("بيت")), [0xFE91, 0xFEF4, 0xFE96])

    def test_isolated_and_right_joiners(self):
        self.assertEqual(cps(shaping.shape("ب")), [0xFE8F])
        # dal and reh join the letter before but not the one after
        self.assertEqual(cps(shaping.shape("عدد")), [0xFECB, 0xFEAA, 0xFEA9])

    def test_lam_alef_ligature(self):
        self.assertEqual(cps(shaping.shape("لا")), [0xFEFB])
        self.assertEqual(cps(shaping.shape("بلا")), [0xFE91, 0xFEFC])
        self.assertEqual(cps(shaping.shape("لأ")), [0xFEF7])
        self.assertEqual(cps(shaping.shape("الله")), [0xFE8D, 0xFEDF, 0xFEE0, 0xFEEA])

    def test_words_are_separated_by_space(self):
        self.assertEqual(cps(shaping.shape("با با")), [0xFE91, 0xFE8E, 0x20, 0xFE91, 0xFE8E])

    def test_persian_and_urdu_letters(self):
        self.assertEqual(cps(shaping.shape("پ")), [0xFB56])
        self.assertEqual(cps(shaping.shape("گ")), [0xFB92])
        self.assertEqual(cps(shaping.shape("ٹ")), [0xFB66])
        # farsi yeh in the middle of a word
        self.assertEqual(cps(shaping.shape("دنیا"))[2], 0xFBFF)

    def test_alef_maksura_has_no_initial_form(self):
        self.assertEqual(cps(shaping.shape("على")), [0xFECB, 0xFEE0, 0xFEF0])
        self.assertEqual(cps(shaping.shape("ى")), [0xFEEF])
        self.assertEqual(cps(shaping.shape("ىب")), [0xFEEF, 0xFE8F])
        self.assertEqual(shaping.joining("ى"), "R")

    def test_marks_do_not_break_joining(self):
        out = shaping.shape("مُحَمَّد")
        self.assertEqual(cps(out), [0xFEE3, 0x64F, 0xFEA4, 0x64E, 0xFEE4, 0x64E, 0x651, 0xFEAA])

    def test_strip_marks(self):
        self.assertEqual(cps(shaping.shape("مُحَمَّد", marks="strip")), [0xFEE3, 0xFEA4, 0xFEE4, 0xFEAA])

    def test_tatweel_and_zwj(self):
        self.assertEqual(cps(shaping.shape("بـب")), [0xFE91, 0x640, 0xFE90])
        self.assertEqual(cps(shaping.shape("ب‍ب")), [0xFE91, 0xFE90])
        self.assertEqual(cps(shaping.shape("ب‌ب")), [0xFE8F, 0xFE8F])

    def test_non_arabic_untouched(self):
        self.assertEqual(shaping.shape("abc 123 שלום"), "abc 123 שלום")


class Bidi(unittest.TestCase):
    def test_latin_unchanged(self):
        self.assertEqual(bidi.reorder("hello world 123"), "hello world 123")

    def test_hebrew_reversed(self):
        self.assertEqual(bidi.reorder("שלום"), "םולש")

    def test_hebrew_with_number(self):
        self.assertEqual(bidi.reorder("שלום 123"), "123 םולש")

    def test_ltr_paragraph_with_rtl_word(self):
        self.assertEqual(bidi.reorder("abc שלום def"), "abc םולש def")

    def test_rtl_paragraph_with_latin_word(self):
        self.assertEqual(bidi.reorder("שלום abc שלום"), "םולש abc םולש")

    def test_two_latin_words_in_rtl_paragraph_keep_their_order(self):
        self.assertEqual(bidi.reorder("שלום one two"), "one two םולש")

    def test_brackets_mirror(self):
        self.assertEqual(bidi.reorder("(שלום)"), "(םולש)")
        self.assertEqual(bidi.reorder("[א]"), "[א]")

    def test_number_with_separators(self):
        self.assertEqual(bidi.reorder("א 1,234.5 ב"), "ב 1,234.5 א")

    def test_arabic_digits_stay_left_to_right(self):
        self.assertEqual(bidi.reorder("ا ١٢٣"), "١٢٣ ا")

    def test_forced_direction(self):
        self.assertEqual(bidi.reorder("abc", base="rtl"), "abc")
        self.assertEqual(bidi.reorder("abc def", base="rtl"), "abc def")
        self.assertEqual(bidi.reorder("אב", base="ltr"), "בא")

    def test_trailing_space_stays_at_the_end(self):
        self.assertEqual(bidi.reorder("שלום "), " םולש")          # RTL: end of line is the left
        self.assertTrue(bidi.reorder("abc שלום  ").endswith("  "))

    def test_marks_follow_their_letter(self):
        out = rtlterm.fix("بَا")
        # visual: alef final, then beh with its fatha right after it
        i = out.index("َ")
        self.assertEqual(cps(out[i - 1]), [0xFE91])


class Layout(unittest.TestCase):
    def test_example_title(self):
        out = rtlterm.fix("مسلسل The Mentalist الموسم الثالث الحلقة 17")
        parts = out.split(" ")
        self.assertEqual(parts[0], "17")
        self.assertEqual(parts[-1], shaping.shape("مسلسل")[::-1])
        self.assertIn("The Mentalist", out)

    def test_number_goes_left_of_word(self):
        self.assertEqual(rtlterm.fix("عدد 123"), "123 " + shaping.shape("عدد")[::-1])

    def test_parentheses(self):
        self.assertEqual(rtlterm.fix("(ا)"), "(" + chr(0xFE8D) + ")")

    def test_plain_ascii_line_is_left_alone(self):
        self.assertEqual(rtlterm.fix("progress 45% [####   ]", width=10), "progress 45% [####   ]")

    def test_running_twice_is_safe(self):
        once = rtlterm.fix("مرحبا بالعالم")
        self.assertEqual(rtlterm.fix(once), once)

    def test_wrap_respects_width(self):
        text = " ".join(["مرحبا بالعالم الجميل"] * 8)
        out = rtlterm.fix(text, width=24, align="left")
        for line in out.split("\n"):
            self.assertLessEqual(rtlterm.display_width(line), 24, line)
        self.assertGreater(len(out.split("\n")), 3)

    def test_wrapped_lines_keep_word_order_per_line(self):
        out = rtlterm.fix("واحد اثنان ثلاثة أربعة", width=14, align="left").split("\n")
        # first logical words end up on the first line, reading right to left
        self.assertIn(shaping.shape("واحد")[::-1], out[0])
        self.assertIn(shaping.shape("أربعة")[::-1], out[-1])

    def test_right_align(self):
        out = rtlterm.fix("عدد", width=10)
        self.assertEqual(rtlterm.display_width(out), 10)
        self.assertTrue(out.startswith(" " * 7))
        self.assertEqual(rtlterm.fix("عدد", width=10, align="left"), shaping.shape("عدد")[::-1])
        self.assertEqual(rtlterm.display_width(rtlterm.fix("عدد", width=11, align="center")), 7)

    def test_long_word_is_hard_broken(self):
        out = rtlterm.fix("ب" * 30, width=10, align="left").split("\n")
        self.assertEqual(len(out), 3)
        self.assertTrue(all(rtlterm.display_width(x) <= 10 for x in out))

    def test_digits_option(self):
        self.assertEqual(rtlterm.fix("عدد 12", digits="arabic").split(" ")[0], "١٢")
        self.assertEqual(rtlterm.fix("عدد ١٢", digits="latin").split(" ")[0], "12")

    def test_carriage_return_progress_line(self):
        out = fix_line("a\rعدد 1")
        self.assertTrue(out.startswith("a\r"))

    def test_colors_stay_on_their_words(self):
        red = "\x1b[31m"
        text = f"{red}مرحبا\x1b[0m and"
        out = rtlterm.fix(text, width=None)
        plain = ANSI.sub("", out)
        self.assertEqual(plain, rtlterm.fix("مرحبا and"))
        # the red word comes after "and" on screen and ends with a reset
        self.assertLess(out.index("and"), out.index(red))
        self.assertTrue(out.endswith("\x1b[0m"))
        # "and" is not red
        self.assertEqual(out.split(red)[0].count("\x1b"), 0)

    def test_other_escapes_survive(self):
        out = rtlterm.fix("\x1b[2Kمرحبا")
        self.assertIn("\x1b[2K", out)

    def test_marks_strip(self):
        self.assertNotIn("َ", rtlterm.fix("بَا", marks="strip"))

    def test_hebrew_only_bidi(self):
        self.assertEqual(rtlterm.fix("שלום עולם"), "םלוע םולש")

    def test_display_width(self):
        self.assertEqual(rtlterm.display_width("abc"), 3)
        self.assertEqual(rtlterm.display_width("日本"), 4)
        self.assertEqual(rtlterm.display_width("بَ"), 1)


class Direction(unittest.TestCase):
    """The default 'smart' rule: an id or number in front does not decide the direction."""

    def lvl(self, text, base="smart"):
        cls = bidi.classes(list(text))
        return bidi.paragraph_level(cls, base)

    def test_id_before_arabic_is_rtl(self):
        self.assertEqual(self.lvl("b24fde4d0  مسلسل The Mentalist"), 1)
        self.assertEqual(self.lvl("b24fde4d0  مسلسل The Mentalist", "auto"), 0)

    def test_numbers_and_times_before_arabic(self):
        self.assertEqual(self.lvl("12:00 عملية"), 1)
        self.assertEqual(self.lvl("v2.1 العربية"), 1)

    def test_plain_english_first_stays_ltr(self):
        self.assertEqual(self.lvl("[INFO] عملية"), 0)
        self.assertEqual(self.lvl("Season مسلسل"), 0)

    def test_arabic_first_is_rtl_even_with_english_after(self):
        self.assertEqual(self.lvl("مسلسل The Mentalist season 3 episode 17"), 1)

    def test_only_codes_falls_back_to_first_letter(self):
        self.assertEqual(self.lvl("b24 ا"), 1)
        self.assertEqual(self.lvl("b24 c25"), 0)

    def test_forced(self):
        self.assertEqual(self.lvl("abc", "rtl"), 1)
        self.assertEqual(self.lvl("ابج", "ltr"), 0)

    def test_search_line_ends_flush_right_with_title_and_id(self):
        out = rtlterm.fix("b24fde4d0  مسلسل The Mentalist الحلقة 13", width=60)
        self.assertEqual(rtlterm.display_width(out), 60)          # flush right
        self.assertTrue(out.endswith("b24fde4d0"))                 # id first = rightmost
        self.assertIn("The Mentalist", out)


class BigText(unittest.TestCase):
    """A lot of text: nothing lost, never wider than the screen, time grows in a straight line."""

    LETTERS = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"

    def words(self, n, seed=5):
        rnd = random.Random(seed)
        return " ".join(
            "".join(rnd.choice(self.LETTERS) for _ in range(rnd.randint(2, 8)))
            if rnd.random() < 0.85 else rnd.choice(["The", "Mentalist", "17", "(ok)", "2026"])
            for _ in range(n))

    def test_20000_chars_one_line(self):
        text = self.words(3500)
        out = rtlterm.fix(text, width=60, align="left")
        lines = out.split("\n")
        self.assertGreater(len(lines), 300)
        self.assertTrue(all(rtlterm.display_width(x) <= 60 for x in lines))
        keep = lambda t: sorted(c for c in t if c not in " \n")  # noqa: E731
        fold = lambda t: sorted(min(c, bidi.MIRROR.get(c, c)) for c in keep(t))  # noqa: E731
        self.assertEqual(fold(out), fold(rtlterm.shape(text)))

    def test_many_lines(self):
        lines = [self.words(12, seed=i) for i in range(3000)]
        out = [fix_line(x, width=50) for x in lines]
        self.assertEqual(len(out), 3000)

    def test_time_is_linear_not_quadratic(self):
        import time
        small, big = self.words(2000), self.words(16000)
        t0 = time.perf_counter()
        rtlterm.fix(small, width=60)
        t1 = time.perf_counter()
        rtlterm.fix(big, width=60)
        t2 = time.perf_counter()
        # 8x the text should cost about 8x; a quadratic bug would cost about 64x
        self.assertLess(t2 - t1, 25 * max(t1 - t0, 0.01))

    def test_huge_word_and_many_colours(self):
        out = rtlterm.fix("ب" * 5000, width=40, align="left").split("\n")
        self.assertEqual(len(out), 125)
        coloured = " ".join(f"\x1b[3{i % 7 + 1}m{w}\x1b[0m" for i, w in enumerate(self.words(1500).split()))
        res = rtlterm.fix(coloured, width=40, align="left")
        self.assertTrue(all(rtlterm.display_width(ANSI.sub("", x)) <= 40 for x in res.split("\n")))


class Properties(unittest.TestCase):
    """Random text: nothing is lost, nothing is added, lines never exceed the width."""

    ALPHABET = list("ابتثجحخدذرزسشصضطظعغفقكلمنهويةىءأإآؤئ") + list("abcXYZ") + list("0123456789") + \
        list("  ,.()-:") + list("אבגדה") + ["َ", "ُ", "ّ"]

    def test_random_lines(self):
        rnd = random.Random(7)
        for _ in range(400):
            s = "".join(rnd.choice(self.ALPHABET) for _ in range(rnd.randint(1, 60)))
            width = rnd.choice([None, 12, 20, 40])
            out = rtlterm.fix(s, width=width, align="left")
            shown = ANSI.sub("", out).replace("\n", "")
            want = rtlterm.shape(s)
            fold = lambda c: min(c, bidi.MIRROR.get(c, c))  # noqa: E731  ( and ) count as one
            norm = lambda t: sorted(fold(c) for c in t.replace(" ", ""))  # noqa: E731
            self.assertEqual(norm(shown), norm(want), repr(s))
            if width:
                for line in out.split("\n"):
                    self.assertLessEqual(rtlterm.display_width(line), width, repr(s))

    def test_pure_arabic_is_a_plain_reversal(self):
        rnd = random.Random(3)
        letters = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"
        for _ in range(200):
            words = ["".join(rnd.choice(letters) for _ in range(rnd.randint(1, 6)))
                     for _ in range(rnd.randint(1, 6))]
            s = " ".join(words)
            self.assertEqual(rtlterm.fix(s), rtlterm.shape(s)[::-1], s)

    def test_idempotent_for_arabic(self):
        rnd = random.Random(11)
        for _ in range(100):
            s = "".join(rnd.choice(self.ALPHABET) for _ in range(rnd.randint(1, 40)))
            once = rtlterm.fix(s, width=None)
            self.assertEqual(rtlterm.fix(once, width=None), once, repr(s))


if __name__ == "__main__":
    unittest.main()
