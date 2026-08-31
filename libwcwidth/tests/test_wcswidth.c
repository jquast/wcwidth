#include "test_common.h"
#include "wcwidth/wcwidth.h"
#include "wcwidth/wcstwidth.h"

TEST(wcswidth_u32_basic)
{
    uint32_t ascii[] = {'h', 'e', 'l', 'l', 'o'};
    uint32_t wide[] = {0x4E00, 0x0301};
    uint32_t ctrl[] = {'a', 0x01};

    ASSERT_EQ(5, wcswidth_u32(ascii, 5, 1));
    ASSERT_EQ(2, wcswidth_u32(wide, 2, 1)); /* wide + combining mark */
    ASSERT_EQ(-1, wcswidth_u32(ctrl, 2, 1));
    ASSERT_EQ(0, wcswidth_u32(NULL, 0, 1));
}

TEST(wcswidth_u8_basic)
{
    ASSERT_EQ(3, wcswidth_u8("abc", 3, 1));
    ASSERT_EQ(2, wcswidth_u8("\xE4\xB8\x80", 3, 1)); /* U+4E00 */
    ASSERT_EQ(1, wcswidth_u8("a\xCC\x81", 3, 1));    /* a + acute */
    ASSERT_EQ(2, wcswidth_u8("a\0b", 3, 1));                   /* embedded NUL */
}

TEST(wcstwidth_u32_basic)
{
    uint32_t ascii[] = {'h', 'i'};
    uint32_t wide[] = {0x4E00};
    uint32_t ctrl[] = {'a', 0x01};

    ASSERT_EQ(2, wcstwidth_u32(ascii, 2, 1, NULL));
    ASSERT_EQ(2, wcstwidth_u32(wide, 1, 1, NULL));
    ASSERT_EQ(-1, wcstwidth_u32(ctrl, 2, 1, NULL));
    ASSERT_EQ(0, wcstwidth_u32(NULL, 0, 1, NULL));
}

TEST(wcstwidth_u8_basic)
{
    ASSERT_EQ(3, wcstwidth_u8("abc", 3, 1, NULL));
    ASSERT_EQ(0, wcstwidth_u8("", 0, 1, NULL));
}

TEST(wcstwidth_u8_long)
{
    /* A cluster spanning the 512-codepoint chunk boundary must measure the
     * same as the whole-string u32 path (RI pair split across chunks). */
    char text[2048];
    uint32_t cps[2048];
    size_t n = 0, count = 0;
    int i;

    for (i = 0; i < 511; i++) {
        text[n++] = 'a';
        cps[count++] = 'a';
    }
    text[n++] = (char) 0xF0;
    text[n++] = (char) 0x9F;
    text[n++] = (char) 0x87;
    text[n++] = (char) 0xA6; /* U+1F1E6 */
    text[n++] = (char) 0xF0;
    text[n++] = (char) 0x9F;
    text[n++] = (char) 0x87;
    text[n++] = (char) 0xA7; /* U+1F1E7 */
    text[n++] = 'b';
    cps[count++] = 0x1F1E6;
    cps[count++] = 0x1F1E7;
    cps[count++] = 'b';

    ASSERT_EQ(wcstwidth_u32(cps, count, 1, NULL), wcstwidth_u8(text, n, 1, NULL));
}

TEST(wcstwidth_terminal_overrides)
{
    uint32_t fitzpatrick[] = {0x1F3FB};  /* emoji modifier, wide standalone */
    uint32_t jv_ka[] = {0xA98F, 0xA9C0}; /* Javanese KA + PANGKON conjunct */
    uint32_t family[] = {0x1F468, 0x200D, 0x1F469, 0x200D, 0x1F467}; /* ZWJ family */

    /* kitty zeroes the Fitzpatrick modifiers; no terminal narrows them. */
    ASSERT_EQ(2, wcstwidth_u32(fitzpatrick, 1, 1, NULL));
    ASSERT_EQ(0, wcstwidth_u32(fitzpatrick, 1, 1, "kitty"));
    /* Alias resolution: xterm-kitty is a TERM alias for kitty. */
    ASSERT_EQ(0, wcstwidth_u32(fitzpatrick, 1, 1, "xterm-kitty"));
    /* Unrecognized identifiers get no overrides. */
    ASSERT_EQ(2, wcstwidth_u32(fitzpatrick, 1, 1, "not-a-terminal"));
    /* ghostty measures the Javanese conjunct at 2 cells. */
    ASSERT_EQ(1, wcstwidth_u32(jv_ka, 2, 1, NULL));
    ASSERT_EQ(2, wcstwidth_u32(jv_ka, 2, 1, "ghostty"));
    /* ZWJ family reaches the cluster scan; kitty has no override, measures 2. */
    ASSERT_EQ(2, wcstwidth_u32(family, 5, 1, "kitty"));
}

int
main(void)
{
    RUN_TEST(wcswidth_u32_basic);
    RUN_TEST(wcswidth_u8_basic);
    RUN_TEST(wcstwidth_u32_basic);
    RUN_TEST(wcstwidth_u8_basic);
    RUN_TEST(wcstwidth_u8_long);
    RUN_TEST(wcstwidth_terminal_overrides);
    return test_summary();
}
