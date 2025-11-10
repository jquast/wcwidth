# std imports
import os

# 3rd party
import pytest

# some tests cannot be done on some builds of python, where the internal
# unicode structure is limited to 0x10000 for memory conservation,
# "ValueError: unichr() arg not in range(0x10000) (narrow Python build)"
try:
    chr(0x2fffe)
    NARROW_ONLY = False
except ValueError:
    NARROW_ONLY = True

# local
import wcwidth


def make_sequence_from_line(line):
    # convert '002A FE0F  ; ..' -> (0x2a, 0xfe0f) -> chr(0x2a) + chr(0xfe0f)
    return ''.join(chr(int(cp, 16)) for cp in line.split(';', 1)[0].strip().split())


@pytest.mark.skipif(NARROW_ONLY, reason="Test cannot verify on python 'narrow' builds")
def emoji_zwj_sequence():
    """
    Emoji zwj sequence of four codepoints is just 2 cells.
    """
    phrase = ("\U0001f469"   # Base, Category So, East Asian Width property 'W' -- WOMAN
              "\U0001f3fb"   # Modifier, Category Sk, East Asian Width property 'W' -- EMOJI MODIFIER FITZPATRICK TYPE-1-2
              "\u200d"       # Joiner, Category Cf, East Asian Width property 'N'  -- ZERO WIDTH JOINER
              "\U0001f4bb")  # Fused, Category So, East Asian Width peroperty 'W' -- PERSONAL COMPUTER
    # This test adapted from https://www.unicode.org/L2/L2023/23107-terminal-suppt.pdf
    expect_length_each = (2, 0, 0, 2)
    expect_length_phrase = 2

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase = wcwidth.wcswidth(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase == expect_length_phrase


@pytest.mark.skipif(NARROW_ONLY, reason="Test cannot verify on python 'narrow' builds")
def test_unfinished_zwj_sequence():
    """
    Ensure index-out-of-bounds does not occur for zero-width joiner without any following character
    """
    phrase = ("\U0001f469"   # Base, Category So, East Asian Width property 'W' -- WOMAN
              "\U0001f3fb"   # Modifier, Category Sk, East Asian Width property 'W' -- EMOJI MODIFIER FITZPATRICK TYPE-1-2
              "\u200d")      # Joiner, Category Cf, East Asian Width property 'N'  -- ZERO WIDTH JOINER
    expect_length_each = (2, 0, 0)
    expect_length_phrase = 2

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase = wcwidth.wcswidth(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase == expect_length_phrase


@pytest.mark.skipif(NARROW_ONLY, reason="Test cannot verify on python 'narrow' builds")
def test_non_recommended_zwj_sequence():
    """
    Verify ZWJ is measured as though successful with characters that cannot be joined, wcwidth does not verify
    """
    phrase = ("\U0001f469"   # Base, Category So, East Asian Width property 'W' -- WOMAN
              "\U0001f3fb"   # Modifier, Category Sk, East Asian Width property 'W' -- EMOJI MODIFIER FITZPATRICK TYPE-1-2
              "\u200d")      # Joiner, Category Cf, East Asian Width property 'N'  -- ZERO WIDTH JOINER
    expect_length_each = (2, 0, 0)
    expect_length_phrase = 2

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase = wcwidth.wcswidth(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase == expect_length_phrase


@pytest.mark.skipif(NARROW_ONLY, reason="Test cannot verify on python 'narrow' builds")
def test_another_emoji_zwj_sequence():
    phrase = (
        "\u26F9"        # PERSON WITH BALL
        "\U0001F3FB"    # EMOJI MODIFIER FITZPATRICK TYPE-1-2
        "\u200D"        # ZERO WIDTH JOINER
        "\u2640"        # FEMALE SIGN
        "\uFE0F")       # VARIATION SELECTOR-16
    expect_length_each = (1, 0, 0, 1, 0)
    expect_length_phrase = 2

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase = wcwidth.wcswidth(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase == expect_length_phrase


@pytest.mark.skipif(NARROW_ONLY, reason="Test cannot verify on python 'narrow' builds")
def test_longer_emoji_zwj_sequence():
    """
    A much longer emoji ZWJ sequence of 10 total codepoints is just 2 cells!

    Also test the same sequence in duplicate, verifying multiple VS-16 sequences
    in a single function call.
    """
    # 'Category Code', 'East Asian Width property' -- 'description'
    phrase = ("\U0001F9D1"   # 'So', 'W' -- ADULT
              "\U0001F3FB"   # 'Sk', 'W' -- EMOJI MODIFIER FITZPATRICK TYPE-1-2
              "\u200d"       # 'Cf', 'N' -- ZERO WIDTH JOINER
              "\u2764"       # 'So', 'N' -- HEAVY BLACK HEART
              "\uFE0F"       # 'Mn', 'A' -- VARIATION SELECTOR-16
              "\u200d"       # 'Cf', 'N' -- ZERO WIDTH JOINER
              "\U0001F48B"   # 'So', 'W' -- KISS MARK
              "\u200d"       # 'Cf', 'N' -- ZERO WIDTH JOINER
              "\U0001F9D1"   # 'So', 'W' -- ADULT
              "\U0001F3FD"   # 'Sk', 'W' -- EMOJI MODIFIER FITZPATRICK TYPE-4
              ) * 2
    # This test adapted from https://www.unicode.org/L2/L2023/23107-terminal-suppt.pdf
    expect_length_each = (2, 0, 0, 1, 0, 0, 2, 0, 2, 0) * 2
    expect_length_phrase = 4

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase = wcwidth.wcswidth(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase == expect_length_phrase


def read_sequences_from_file(filename):
    fp = open(os.path.join(os.path.dirname(__file__), filename), 'r', encoding='utf-8')
    lines = [line.strip()
             for line in fp.readlines()
             if not line.startswith('#') and line.strip()]
    fp.close()
    sequences = [make_sequence_from_line(line) for line in lines]
    return lines, sequences


@pytest.mark.skipif(NARROW_ONLY, reason="Some sequences in text file are not compatible with 'narrow' builds")
def test_recommended_emoji_zwj_sequences():
    """
    Test wcswidth of all of the unicode.org-published emoji-zwj-sequences.txt
    """
    # given,
    lines, sequences = read_sequences_from_file('emoji-zwj-sequences.txt')

    errors = []
    # Exercise, track by zipping with original text file line, a debugging aide
    num = 0
    for sequence, line in zip(sequences, lines):
        num += 1
        measured_width = wcwidth.wcswidth(sequence)
        if measured_width != 2:
            errors.append({
                'expected_width': 2,
                'line': line,
                'measured_width': measured_width,
                'sequence': sequence,
            })

    # verify
    assert errors == []
    assert num >= 1468


@pytest.mark.parametrize('vs_char,expected_width', [
    ('\ufe0f', 2),
    ('\ufe0e', 1),
])
def test_recommended_variation_sequences(vs_char, expected_width):
    """
    Test wcswidth of variation selector sequences from emoji-variation-sequences.txt
    """
    lines, sequences = read_sequences_from_file('emoji-variation-sequences.txt')

    errors = []
    num = 0
    for sequence, line in zip(sequences, lines):
        num += 1
        if vs_char not in sequence:
            continue
        measured_width = wcwidth.wcswidth(sequence)
        if measured_width != expected_width:
            errors.append({
                'expected_width': expected_width,
                'line': line,
                'measured_width': measured_width,
                'sequence': sequence,
            })

    assert errors == []
    assert num >= 742


@pytest.mark.parametrize('unicode_version,base_char,vs_char,base_width,expect_phrase_width', [
    ('9.0', '\u2640', '\uFE0F', 1, 3),
    ('9.0', '\U0001f4da', '\uFE0E', 2, 2),
    ('8.0', '\u2640', '\uFE0F', 1, 2),
    ('8.0', '\U0001f4da', '\uFE0E', 1, 2),
])
def test_variation_selector_unicode_version(unicode_version, base_char, vs_char, base_width, expect_phrase_width):
    """
    Test variation selector behavior across Unicode versions.

    VS-16 and VS-15 should affect width in Unicode 9.0+, but not in 8.0 and earlier.
    """
    phrase = base_char + vs_char + "X" + vs_char
    expect_length_each = (base_width, 0, 1, 0)

    length_each = tuple(wcwidth.wcwidth(w_char, unicode_version=unicode_version) for w_char in phrase)
    length_phrase = wcwidth.wcswidth(phrase, unicode_version=unicode_version)

    assert length_each == expect_length_each
    assert length_phrase == expect_phrase_width


@pytest.mark.parametrize('char,expected_base_width,expected_vs15_width,description', [
    ('\u231A', 2, 1, 'WATCH'),
    ('\u231B', 2, 1, 'HOURGLASS'),
    ('\u2648', 2, 1, 'ARIES'),
    ('\u26A1', 2, 1, 'HIGH VOLTAGE SIGN'),
    ('\U0001F4DA', 2, 1, 'BOOKS'),
    ('\U0001F3E0', 2, 1, 'HOUSE BUILDING'),
    ('\u0023', 1, 1, 'NUMBER SIGN'),
    ('\u002A', 1, 1, 'ASTERISK'),
    ('\u00A9', 1, 1, 'COPYRIGHT SIGN'),
])
def test_vs15_width_effects(char, expected_base_width, expected_vs15_width, description):
    """
    Test VS-15 width effects on various characters.

    Wide chars (2→1): VS-15 converts to narrow text presentation
    Narrow chars (1→1): VS-15 has no effect, already narrow
    """
    width_alone = wcwidth.wcswidth(char, unicode_version='9.0')
    width_with_vs15 = wcwidth.wcswidth(char + '\uFE0E', unicode_version='9.0')

    assert width_alone == expected_base_width
    assert width_with_vs15 == expected_vs15_width


def test_vs15_vs16_symmetry():
    """Verify VS-15 and VS-16 have symmetric opposite effects on dual-presentation chars"""
    watch = '\u231A'

    width_base = wcwidth.wcswidth(watch, unicode_version='9.0')
    width_vs15 = wcwidth.wcswidth(watch + '\uFE0E', unicode_version='9.0')
    width_vs16 = wcwidth.wcswidth(watch + '\uFE0F', unicode_version='9.0')

    assert width_base == 2
    assert width_vs15 == 1
    assert width_vs16 == 2


def test_vs15_multiple_in_sequence():
    """Verify multiple VS-15 applications in a single string"""
    phrase = (
        '\u231A\uFE0E'      # WATCH + VS15 (wide -> narrow)
        'X'                 # ASCII
        '\U0001F4DA\uFE0E'  # BOOKS + VS15 (wide -> narrow)
        'Y'                 # ASCII
        '\u2648\uFE0E'      # ARIES + VS15 (wide -> narrow)
    )

    width = wcwidth.wcswidth(phrase, unicode_version='9.0')
    assert width == 5


def test_vs15_without_preceding_char():
    """Verify VS-15 without a preceding measurable character has width 0"""
    phrase = '\uFE0E'
    width = wcwidth.wcwidth(phrase, unicode_version='9.0')
    assert width == 0
