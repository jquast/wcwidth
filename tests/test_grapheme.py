"""Tests for grapheme cluster segmentation."""
import os

import pytest

import wcwidth
from wcwidth.grapheme import iter_graphemes


try:
    chr(0x2fffe)
    NARROW_ONLY = False
except ValueError:
    NARROW_ONLY = True


def parse_grapheme_break_test_line(line):
    """
    Parse a line from GraphemeBreakTest.txt.

    Format: ÷ 0020 × 0308 ÷ # comment
    Where ÷ means break and × means no break.
    """
    data, _, comment = line.partition('#')
    data = data.strip()
    if not data:
        return None, None

    # Split by ÷ (break) and × (no break) markers
    # The line starts and ends with ÷
    parts = []
    current_cluster = []
    in_cluster = False

    tokens = data.split()
    for token in tokens:
        if token == '÷':
            if current_cluster:
                parts.append(current_cluster)
                current_cluster = []
        elif token == '×':
            pass  # Continue building current cluster
        else:
            # Hex codepoint
            try:
                current_cluster.append(int(token, 16))
            except ValueError:
                continue

    if current_cluster:
        parts.append(current_cluster)

    # Convert to string and expected clusters
    all_codepoints = []
    expected_clusters = []
    for cluster in parts:
        cluster_str = ''.join(chr(cp) for cp in cluster)
        expected_clusters.append(cluster_str)
        all_codepoints.extend(cluster)

    if not all_codepoints:
        return None, None

    input_str = ''.join(chr(cp) for cp in all_codepoints)
    return input_str, expected_clusters


def read_grapheme_break_test():
    """Read and parse GraphemeBreakTest.txt."""
    test_file = os.path.join(os.path.dirname(__file__), 'GraphemeBreakTest.txt')
    if not os.path.exists(test_file):
        pytest.skip("GraphemeBreakTest.txt not found. Run 'tox -e update' first.")

    test_cases = []
    with open(test_file, encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            input_str, expected = parse_grapheme_break_test_line(line)
            if input_str is not None:
                test_cases.append((line_num, line, input_str, expected))

    return test_cases


def test_core_grapheme():
    """Basic grapheme cluster segmentation."""
    assert list(iter_graphemes('')) == []
    assert list(iter_graphemes('a')) == ['a']
    assert list(iter_graphemes('abc')) == ['a', 'b', 'c']
    # 'cafe' + COMBINING ACUTE ACCENT, accent combines with 'e'
    assert list(iter_graphemes('cafe\u0301')) == ['c', 'a', 'f', 'e\u0301']
    # CARRIAGE RETURN + LINE FEED, forms single grapheme cluster
    assert list(iter_graphemes('\r\n')) == ['\r\n']
    assert list(iter_graphemes('ok\r\nok')) == ['o', 'k', '\r\n', 'o', 'k']
    # CARRIAGE RETURN alone
    assert list(iter_graphemes('\r')) == ['\r']
    assert list(iter_graphemes('ok\rok')) == ['o', 'k', '\r', 'o', 'k']
    # LINE FEED alone
    assert list(iter_graphemes('\n')) == ['\n']
    assert list(iter_graphemes('ok\nok')) == ['o', 'k', '\n', 'o', 'k']
    # two CARRIAGE RETURNs do not combine
    assert list(iter_graphemes('\r\r')) == ['\r', '\r']
    assert list(iter_graphemes('ok\r\rok')) == ['o', 'k', '\r', '\r', 'o', 'k']
    assert list(iter_graphemes('abcdef', start=2)) == ['c', 'd', 'e', 'f']
    assert list(iter_graphemes('abcdef', end=4)) == ['a', 'b', 'c', 'd']
    assert list(iter_graphemes('abcdef', start=1, end=4)) == ['b', 'c', 'd']
    assert list(iter_graphemes('abc', start=10)) == []
    assert list(iter_graphemes('abc', end=10)) == ['a', 'b', 'c']


@pytest.mark.skipif(NARROW_ONLY, reason="Test requires wide Unicode support")
def test_wide_unicode_graphemes():
    """Grapheme segmentation for wide Unicode characters."""
    # HANGUL CHOSEONG KIYEOK (L) + HANGUL JUNGSEONG A (V)
    hangul_lv = ('\u1100'    # HANGUL CHOSEONG KIYEOK (L)
                 '\u1161')   # HANGUL JUNGSEONG A (V)
    assert list(iter_graphemes(hangul_lv)) == [hangul_lv]
    assert list(iter_graphemes('ok' + hangul_lv + 'ok')) == ['o', 'k', hangul_lv, 'o', 'k']
    # HANGUL SYLLABLE GA (LV) + HANGUL JONGSEONG KIYEOK (T)
    hangul_lvt = ('\uAC00'   # HANGUL SYLLABLE GA (LV)
                  '\u11A8')  # HANGUL JONGSEONG KIYEOK (T)
    assert list(iter_graphemes(hangul_lvt)) == [hangul_lvt]
    assert list(iter_graphemes('ok' + hangul_lvt + 'ok')) == ['o', 'k', hangul_lvt, 'o', 'k']
    # Regional indicators pair to form flag: US
    flag_us = ('\U0001F1FA'   # REGIONAL INDICATOR SYMBOL LETTER U
               '\U0001F1F8')  # REGIONAL INDICATOR SYMBOL LETTER S
    assert list(iter_graphemes(flag_us)) == [flag_us]
    assert list(iter_graphemes('ok' + flag_us + 'ok')) == ['o', 'k', flag_us, 'o', 'k']
    # Three regional indicators: US + A (odd one out)
    flag_us_a = ('\U0001F1FA'   # REGIONAL INDICATOR SYMBOL LETTER U
                 '\U0001F1F8'   # REGIONAL INDICATOR SYMBOL LETTER S
                 '\U0001F1E6')  # REGIONAL INDICATOR SYMBOL LETTER A
    assert list(iter_graphemes(flag_us_a)) == [flag_us, '\U0001F1E6']
    assert list(iter_graphemes('ok' + flag_us_a + 'ok')) == [
        'o', 'k', flag_us, '\U0001F1E6', 'o', 'k']
    # Four regional indicators: US + AU (two flags)
    flag_au = ('\U0001F1E6'   # REGIONAL INDICATOR SYMBOL LETTER A
               '\U0001F1FA')  # REGIONAL INDICATOR SYMBOL LETTER U
    assert list(iter_graphemes(flag_us + flag_au)) == [flag_us, flag_au]
    assert list(iter_graphemes('ok' + flag_us + flag_au + 'ok')) == [
        'o', 'k', flag_us, flag_au, 'o', 'k']
    # ZWJ sequence: MAN + ZWJ + WOMAN + ZWJ + GIRL (family emoji)
    family = ('\U0001F468'   # MAN
              '\u200D'       # ZERO WIDTH JOINER
              '\U0001F469'   # WOMAN
              '\u200D'       # ZERO WIDTH JOINER
              '\U0001F467')  # GIRL
    assert list(iter_graphemes(family)) == [family]
    assert list(iter_graphemes('ok' + family + 'ok')) == ['o', 'k', family, 'o', 'k']
    # Emoji with skin tone modifier: WAVING HAND + FITZPATRICK TYPE-1-2
    wave_skin = ('\U0001F44B'   # WAVING HAND SIGN
                 '\U0001F3FB')  # EMOJI MODIFIER FITZPATRICK TYPE-1-2
    assert list(iter_graphemes(wave_skin)) == [wave_skin]
    assert list(iter_graphemes('ok' + wave_skin + 'ok')) == ['o', 'k', wave_skin, 'o', 'k']
    # Emoji with presentation selector: HEAVY BLACK HEART + VS-16
    heart_emoji = ('\u2764'   # HEAVY BLACK HEART
                   '\uFE0F')  # VARIATION SELECTOR-16
    assert list(iter_graphemes(heart_emoji)) == [heart_emoji]
    assert list(iter_graphemes('ok' + heart_emoji + 'ok')) == ['o', 'k', heart_emoji, 'o', 'k']


@pytest.mark.skipif(NARROW_ONLY, reason="Test requires wide Unicode support")
def test_unicode_grapheme_break_test():
    """Validate against official Unicode GraphemeBreakTest.txt."""
    test_cases = read_grapheme_break_test()
    if not test_cases:
        pytest.skip("No test cases found in GraphemeBreakTest.txt")

    errors = []
    for line_num, line, input_str, expected in test_cases:
        try:
            result = list(iter_graphemes(input_str))
            if result != expected:
                errors.append({
                    'line': line_num,
                    'test': line[:80],
                    'expected': expected,
                    'got': result,
                })
        except Exception as e:
            errors.append({
                'line': line_num,
                'test': line[:80],
                'error': str(e),
            })

    assert errors == [], f"Failed {len(errors)} of {len(test_cases)} tests"
