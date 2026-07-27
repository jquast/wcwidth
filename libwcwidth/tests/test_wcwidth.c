#include "test_common.h"
#include "wcwidth/wcwidth.h"

TEST(ascii_printable)
{
    ASSERT_EQ(1, wcwidth_u32(0x20, 1));
    ASSERT_EQ(1, wcwidth_u32(0x7E, 1));
    ASSERT_EQ(1, wcwidth_u32('A', 1));
    ASSERT_EQ(1, wcwidth_u32('z', 1));
    ASSERT_EQ(1, wcwidth_u32('0', 1));
}

TEST(null_codepoint)
{
    ASSERT_EQ(0, wcwidth_u32(0x00, 1));
}

TEST(c0_controls)
{
    ASSERT_EQ(-1, wcwidth_u32(0x01, 1));
    ASSERT_EQ(-1, wcwidth_u32(0x1F, 1));
    ASSERT_EQ(-1, wcwidth_u32(0x08, 1)); /* BS */
    ASSERT_EQ(-1, wcwidth_u32(0x0D, 1)); /* CR */
    ASSERT_EQ(-1, wcwidth_u32(0x0A, 1)); /* LF */
}

TEST(del_control)
{
    ASSERT_EQ(-1, wcwidth_u32(0x7F, 1));
}

TEST(c1_controls)
{
    ASSERT_EQ(-1, wcwidth_u32(0x80, 1));
    ASSERT_EQ(-1, wcwidth_u32(0x9F, 1));
    ASSERT_EQ(-1, wcwidth_u32(0x1B, 1)); /* ESC */
}

TEST(soft_hyphen)
{
    ASSERT_EQ(1, wcwidth_u32(0xAD, 1));
}

TEST(known_wide)
{
    ASSERT_EQ(2, wcwidth_u32(0x4E00, 1)); /* CJK UNIFIED IDEOGRAPH-4E00 */
    ASSERT_EQ(2, wcwidth_u32(0x65E5, 1)); /* CJK UNIFIED IDEOGRAPH-65E5 */
    ASSERT_EQ(2, wcwidth_u32(0x1100, 1)); /* HANGUL CHOSEONG KIYEOK */
    ASSERT_EQ(2, wcwidth_u32(0x3042, 1)); /* HIRAGANA LETTER A */
    ASSERT_EQ(2, wcwidth_u32(0xAC00, 1)); /* HANGUL SYLLABLE GA */
}

TEST(known_zero_width)
{
    ASSERT_EQ(0, wcwidth_u32(0x0300, 1)); /* COMBINING GRAVE ACCENT */
    ASSERT_EQ(0, wcwidth_u32(0x200B, 1)); /* ZERO WIDTH SPACE */
    ASSERT_EQ(0, wcwidth_u32(0x200C, 1)); /* ZERO WIDTH NON-JOINER */
    ASSERT_EQ(0, wcwidth_u32(0x200D, 1)); /* ZERO WIDTH JOINER */
    ASSERT_EQ(0, wcwidth_u32(0xFEFF, 1)); /* ZERO WIDTH NO-BREAK SPACE / BOM */
}

TEST(combining_mark)
{
    ASSERT_EQ(0, wcwidth_u32(0x05BF, 1)); /* HEBREW POINT RAFE */
    ASSERT_EQ(0, wcwidth_u32(0x0301, 1)); /* COMBINING ACUTE ACCENT */
}

TEST(balinese_adeg_adeg)
{
    ASSERT_EQ(0, wcwidth_u32(0x1B44, 1)); /* BALINESE ADEG ADEG (virama, Mc) */
}

TEST(ambiguous_narrow)
{
    ASSERT_EQ(1, wcwidth_u32(0x00A1, 1)); /* INVERTED EXCLAMATION MARK */
    ASSERT_EQ(1, wcwidth_u32(0x00A4, 1)); /* CURRENCY SIGN */
    ASSERT_EQ(1, wcwidth_u32(0x00D7, 1)); /* MULTIPLICATION SIGN */
}

TEST(ambiguous_wide)
{
    ASSERT_EQ(2, wcwidth_u32(0x00A1, 2)); /* INVERTED EXCLAMATION MARK */
    ASSERT_EQ(2, wcwidth_u32(0x00A4, 2)); /* CURRENCY SIGN */
    ASSERT_EQ(2, wcwidth_u32(0x00D7, 2)); /* MULTIPLICATION SIGN */
}

TEST(regional_indicator)
{
    ASSERT_EQ(2, wcwidth_u32(0x1F1E6, 1)); /* REGIONAL INDICATOR SYMBOL LETTER A */
    ASSERT_EQ(2, wcwidth_u32(0x1F1E7, 1)); /* REGIONAL INDICATOR SYMBOL LETTER B */
    ASSERT_EQ(2, wcwidth_u32(0x1F1FF, 1)); /* REGIONAL INDICATOR SYMBOL LETTER Z */
}

TEST(default_width)
{
    ASSERT_EQ(1, wcwidth_u32(0x00E9, 1)); /* LATIN SMALL LETTER E WITH ACUTE */
    ASSERT_EQ(1, wcwidth_u32(0x2200, 1)); /* FOR ALL */
    ASSERT_EQ(1, wcwidth_u32(0x0391, 1)); /* GREEK CAPITAL LETTER ALPHA */
}

TEST(emoji_wide)
{
    ASSERT_EQ(2, wcwidth_u32(0x1F600, 1)); /* GRINNING FACE */
    ASSERT_EQ(2, wcwidth_u32(0x1F680, 1)); /* ROCKET */
}

TEST(prepended_concatenation_mark)
{
    ASSERT_EQ(1, wcwidth_u32(0x0600, 1));  /* ARABIC NUMBER SIGN */
    ASSERT_EQ(1, wcwidth_u32(0x0601, 1));  /* ARABIC SIGN SANAH */
    ASSERT_EQ(1, wcwidth_u32(0x06DD, 1));  /* ARABIC END OF AYAH */
    ASSERT_EQ(1, wcwidth_u32(0x070F, 1));  /* SYRIAC ABBREVIATION MARK */
    ASSERT_EQ(1, wcwidth_u32(0x0890, 1));  /* ARABIC POUND MARK ABOVE */
    ASSERT_EQ(1, wcwidth_u32(0x110BD, 1)); /* KAITHI NUMBER SIGN */
}

int
main(void)
{
    RUN_TEST(ascii_printable);
    RUN_TEST(null_codepoint);
    RUN_TEST(c0_controls);
    RUN_TEST(del_control);
    RUN_TEST(c1_controls);
    RUN_TEST(soft_hyphen);
    RUN_TEST(known_wide);
    RUN_TEST(known_zero_width);
    RUN_TEST(combining_mark);
    RUN_TEST(balinese_adeg_adeg);
    RUN_TEST(ambiguous_narrow);
    RUN_TEST(ambiguous_wide);
    RUN_TEST(regional_indicator);
    RUN_TEST(default_width);
    RUN_TEST(emoji_wide);
    RUN_TEST(prepended_concatenation_mark);
    return test_summary();
}
