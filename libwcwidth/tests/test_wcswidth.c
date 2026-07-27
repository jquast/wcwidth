#include "test_common.h"
#include "wcwidth/wcwidth.h"
#include "wcwidth/wcstwidth.h"

TEST(empty_string)
{
    uint32_t empty[1] = {0};
    ASSERT_EQ(0, wcswidth_u32(NULL, 0, 1));
    ASSERT_EQ(0, wcswidth_u32(empty, 0, 1));
    ASSERT_EQ(0, wcswidth_u8("", 0, 1));
}

TEST(ascii_printable)
{
    uint32_t ascii[] = {'h', 'e', 'l', 'l', 'o'};
    ASSERT_EQ(5, wcswidth_u32(ascii, 5, 1));
    ASSERT_EQ(5, wcswidth_u8("hello", 5, 1));
}

TEST(ascii_with_ambiguous)
{
    uint32_t ascii[] = {'h', 'e', 'l', 'l', 'o'};
    ASSERT_EQ(5, wcswidth_u32(ascii, 5, 2));
}

TEST(single_wide)
{
    uint32_t wide[] = {0x4E00};
    ASSERT_EQ(2, wcswidth_u32(wide, 1, 1));
    ASSERT_EQ(2, wcswidth_u8("\xE4\xB8\x80", 3, 1));
}

TEST(cjk_string)
{
    uint32_t cjk[] = {0x4E00, 0x4E8C, 0x4E09};
    ASSERT_EQ(6, wcswidth_u32(cjk, 3, 1));
}

TEST(combining_mark)
{
    uint32_t text[] = {'a', 0x0301};
    ASSERT_EQ(1, wcswidth_u32(text, 2, 1));
}

TEST(c0_control)
{
    uint32_t text[] = {'a', 0x01, 'b'};
    ASSERT_EQ(-1, wcswidth_u32(text, 3, 1));
}

TEST(del_control)
{
    uint32_t text[] = {'a', 0x7F};
    ASSERT_EQ(-1, wcswidth_u32(text, 2, 1));
}

TEST(c1_control)
{
    uint32_t text[] = {'a', 0x9F, 'b'};
    ASSERT_EQ(-1, wcswidth_u32(text, 3, 1));
}

TEST(vs16_emoji_presentation)
{
    uint32_t text[] = {0x00A9, 0xFE0F};
    ASSERT_EQ(2, wcswidth_u32(text, 2, 1));
}

TEST(vs16_unicode_9_support)
{
    uint32_t text[] = {0x2122, 0xFE0F};
    ASSERT_EQ(2, wcswidth_u32(text, 2, 1));
}

TEST(vs16_no_effect_on_already_wide)
{
    uint32_t text[] = {0x1F600, 0xFE0F};
    ASSERT_EQ(2, wcswidth_u32(text, 2, 1));
}

TEST(vs15_text_presentation)
{
    uint32_t text[] = {0xFE0F, 0xFE0E};
    (void) text;
    /* VS15 after non-measured base is a no-op */
}

TEST(regional_indicator_pair)
{
    uint32_t text[] = {0x1F1FA, 0x1F1F8};
    ASSERT_EQ(2, wcswidth_u32(text, 2, 1));
}

TEST(regional_indicator_solo)
{
    uint32_t text[] = {0x1F1FA};
    ASSERT_EQ(2, wcswidth_u32(text, 1, 1));
}

TEST(regional_indicator_triple)
{
    uint32_t text[] = {0x1F1FA, 0x1F1F8, 0x1F1E6};
    ASSERT_EQ(4, wcswidth_u32(text, 3, 1));
}

TEST(zwj_emoji_family)
{
    uint32_t text[] = {0x1F468, 0x200D, 0x1F469, 0x200D, 0x1F467};
    ASSERT_EQ(2, wcswidth_u32(text, 5, 1));
}

TEST(zwj_virama_skip)
{
    uint32_t text[] = {0x0915, 0x094D, 0x200D};
    ASSERT_EQ(1, wcswidth_u32(text, 3, 1));
}

TEST(fitzpatrick_modifier)
{
    uint32_t text[] = {0x1F600, 0x1F3FB};
    ASSERT_EQ(2, wcswidth_u32(text, 2, 1));
}

TEST(virama_consonant)
{
    uint32_t text[] = {0x0915, 0x094D};
    ASSERT_EQ(1, wcswidth_u32(text, 2, 1));
}

TEST(virama_conjunct_cap)
{
    uint32_t text[] = {0x0915, 0x094D, 0x0924};
    ASSERT_EQ(2, wcswidth_u32(text, 3, 1));
}

TEST(mc_spacing_mark)
{
    uint32_t text[] = {0x0A15, 0x0A03};
    ASSERT_EQ(2, wcswidth_u32(text, 2, 1));
}

TEST(mixed_ascii_wide_combining)
{
    uint32_t text[] = {'a', 0x4E00, 'b', 0x0301, 'c'};
    ASSERT_EQ(5, wcswidth_u32(text, 5, 1));
}

TEST(null_codepoint_in_string)
{
    uint32_t text[] = {'a', 0x00, 'b'};
    ASSERT_EQ(2, wcswidth_u32(text, 3, 1));
}

TEST(ambiguous_wide_mode)
{
    uint32_t text[] = {0x00A1, 0x00A4, 0x00D7};
    ASSERT_EQ(3, wcswidth_u32(text, 3, 1));
    ASSERT_EQ(6, wcswidth_u32(text, 3, 2));
}

TEST(zero_width_chars)
{
    uint32_t text[] = {'a', 0x200B, 'b'};
    ASSERT_EQ(2, wcswidth_u32(text, 3, 1));
}

TEST(zwnj)
{
    uint32_t text[] = {'a', 0x200C, 'b'};
    ASSERT_EQ(2, wcswidth_u32(text, 3, 1));
}

TEST(utf8_decode_ascii)
{
    ASSERT_EQ(3, wcswidth_u8("abc", (size_t) -1, 1));
    ASSERT_EQ(3, wcswidth_u8("abc", 3, 1));
}

TEST(utf8_decode_wide)
{
    ASSERT_EQ(2, wcswidth_u8("\xE4\xB8\x80", (size_t) -1, 1));
}

TEST(utf8_decode_emoji)
{
    ASSERT_EQ(2, wcswidth_u8("\xF0\x9F\x98\x80", (size_t) -1, 1));
}

TEST(utf8_decode_combining)
{
    ASSERT_EQ(1, wcswidth_u8("a\xCC\x81", (size_t) -1, 1));
}

TEST(utf8_nul_terminated)
{
    ASSERT_EQ(3, wcswidth_u8("abc", (size_t) -1, 1));
}

TEST(utf8_empty)
{
    ASSERT_EQ(0, wcswidth_u8("", (size_t) -1, 1));
    ASSERT_EQ(0, wcswidth_u8("", 0, 1));
    ASSERT_EQ(0, wcswidth_u8(NULL, 0, 1));
    ASSERT_EQ(0, wcswidth_u8(NULL, (size_t) -1, 1));
}

TEST(utf8_embedded_nul)
{
    ASSERT_EQ(2, wcswidth_u8("a\0b", 3, 1));
}

TEST(utf8_2_byte)
{
    ASSERT_EQ(1, wcswidth_u8("\xC3\xA9", (size_t) -1, 1));
}

TEST(utf8_3_byte)
{
    ASSERT_EQ(1, wcswidth_u8("\xE2\x98\x83", (size_t) -1, 1));
}

TEST(utf8_4_byte)
{
    ASSERT_EQ(2, wcswidth_u8("\xF0\x9F\x98\x82", (size_t) -1, 1));
}

TEST(utf8_invalid_sequence)
{
    int w = wcswidth_u8("\xC0\x80", (size_t) -1, 1);
    ASSERT_TRUE(w >= 0);
}

TEST(wcstwidth_null_term_program)
{
    uint32_t text[] = {'h', 'e', 'l', 'l', 'o'};
    ASSERT_EQ(5, wcstwidth_u32(text, 5, 1, NULL));
    ASSERT_EQ(5, wcstwidth_u8("hello", 5, 1, NULL));
}

TEST(wcstwidth_empty_term_program)
{
    uint32_t text[] = {'h', 'i'};
    ASSERT_EQ(2, wcstwidth_u32(text, 2, 1, ""));
}

TEST(wcstwidth_unknown_terminal)
{
    uint32_t text[] = {'h', 'i'};
    ASSERT_EQ(2, wcstwidth_u32(text, 2, 1, "nonexistent-term"));
}

TEST(wcstwidth_wide)
{
    uint32_t text[] = {0x4E00};
    ASSERT_EQ(2, wcstwidth_u32(text, 1, 1, NULL));
}

TEST(wcstwidth_c0_control)
{
    uint32_t text[] = {'a', 0x01};
    ASSERT_EQ(-1, wcstwidth_u32(text, 2, 1, NULL));
}

TEST(wcstwidth_nul_terminated)
{
    ASSERT_EQ(3, wcstwidth_u8("abc", (size_t) -1, 1, NULL));
}

TEST(wcstwidth_empty)
{
    ASSERT_EQ(0, wcstwidth_u32(NULL, 0, 1, NULL));
    ASSERT_EQ(0, wcstwidth_u8("", 0, 1, NULL));
}

TEST(long_ascii_string)
{
    uint32_t text[200];
    size_t i;
    for (i = 0; i < 200; i++) {
        text[i] = 'x';
    }
    ASSERT_EQ(200, wcswidth_u32(text, 200, 1));
}

TEST(consecutive_variation_selectors)
{
    uint32_t text[] = {0x00A9, 0xFE0F, 0xFE0F};
    ASSERT_EQ(2, wcswidth_u32(text, 3, 1));
}

int
main(void)
{
    RUN_TEST(empty_string);
    RUN_TEST(ascii_printable);
    RUN_TEST(ascii_with_ambiguous);
    RUN_TEST(single_wide);
    RUN_TEST(cjk_string);
    RUN_TEST(combining_mark);
    RUN_TEST(c0_control);
    RUN_TEST(del_control);
    RUN_TEST(c1_control);
    RUN_TEST(vs16_emoji_presentation);
    RUN_TEST(vs16_unicode_9_support);
    RUN_TEST(vs16_no_effect_on_already_wide);
    RUN_TEST(vs15_text_presentation);
    RUN_TEST(regional_indicator_pair);
    RUN_TEST(regional_indicator_solo);
    RUN_TEST(regional_indicator_triple);
    RUN_TEST(zwj_emoji_family);
    RUN_TEST(zwj_virama_skip);
    RUN_TEST(fitzpatrick_modifier);
    RUN_TEST(virama_consonant);
    RUN_TEST(virama_conjunct_cap);
    RUN_TEST(mc_spacing_mark);
    RUN_TEST(mixed_ascii_wide_combining);
    RUN_TEST(null_codepoint_in_string);
    RUN_TEST(ambiguous_wide_mode);
    RUN_TEST(zero_width_chars);
    RUN_TEST(zwnj);
    RUN_TEST(utf8_decode_ascii);
    RUN_TEST(utf8_decode_wide);
    RUN_TEST(utf8_decode_emoji);
    RUN_TEST(utf8_decode_combining);
    RUN_TEST(utf8_nul_terminated);
    RUN_TEST(utf8_empty);
    RUN_TEST(utf8_embedded_nul);
    RUN_TEST(utf8_2_byte);
    RUN_TEST(utf8_3_byte);
    RUN_TEST(utf8_4_byte);
    RUN_TEST(utf8_invalid_sequence);
    RUN_TEST(wcstwidth_null_term_program);
    RUN_TEST(wcstwidth_empty_term_program);
    RUN_TEST(wcstwidth_unknown_terminal);
    RUN_TEST(wcstwidth_wide);
    RUN_TEST(wcstwidth_c0_control);
    RUN_TEST(wcstwidth_nul_terminated);
    RUN_TEST(wcstwidth_empty);
    RUN_TEST(long_ascii_string);
    RUN_TEST(consecutive_variation_selectors);
    return test_summary();
}
