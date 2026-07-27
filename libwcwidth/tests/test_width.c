#include "test_common.h"
#include "wcwidth/width.h"
#include <string.h>

static int
w(const char *text, wcwidth_control_mode_t mode)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    int result = width_u8(text, (size_t) -1, mode, &opts, &error);
    if (result < 0) {
        return -1;
    }
    return result;
}

static int
w_parse(const char *text)
{
    return w(text, WCWIDTH_PARSE);
}

static int
w_ignore(const char *text)
{
    return w(text, WCWIDTH_IGNORE);
}

static int
w_strict(const char *text)
{
    return w(text, WCWIDTH_STRICT);
}

TEST(ascii_plain)
{
    ASSERT_EQ(5, w_parse("hello"));
}

TEST(ascii_empty)
{
    ASSERT_EQ(0, w_parse(""));
}

TEST(ascii_single)
{
    ASSERT_EQ(1, w_parse("x"));
}

TEST(sgr_zero_width)
{
    ASSERT_EQ(0, w_parse("\x1b[31m"));
}

TEST(sgr_around_text)
{
    ASSERT_EQ(3, w_parse("\x1b[31mred\x1b[0m"));
}

TEST(sgr_multiple)
{
    ASSERT_EQ(4, w_parse("\x1b[1m\x1b[32mblue\x1b[0m"));
}

TEST(sgr_and_text)
{
    ASSERT_EQ(6, w_parse("\x1b[33myellow\x1b[0m"));
}

TEST(tab_basic)
{
    ASSERT_EQ(8, w_parse("\t"));
}

TEST(tab_after_text)
{
    ASSERT_EQ(8, w_parse("abc\t"));
}

TEST(tab_mid_text)
{
    ASSERT_EQ(11, w_parse("abc\tdef"));
}

TEST(tab_multiple)
{
    ASSERT_EQ(17, w_parse("a\tb\tc"));
}

TEST(tab_at_stop)
{
    ASSERT_EQ(16, w_parse("abcdefgh\t"));
}

TEST(bs_basic)
{
    ASSERT_EQ(3, w_parse("123\b4"));
}

TEST(bs_at_start)
{
    ASSERT_EQ(1, w_parse("\ba"));
}

TEST(cr_basic)
{
    ASSERT_EQ(5, w_parse("hello\rworld"));
}

TEST(cr_followed)
{
    ASSERT_EQ(3, w_parse("abc\rxy"));
}

TEST(cuf_default)
{
    ASSERT_EQ(1, w_parse("\x1b[C"));
}

TEST(cuf_with_n)
{
    ASSERT_EQ(11, w_parse("1\x1b[10C"));
}

TEST(cub_basic)
{
    ASSERT_EQ(4, w_parse("abcd\x1b[2D"));
}

TEST(cub_past_start)
{
    ASSERT_EQ(2, w_parse("ab\x1b[10D"));
}

TEST(hpa_basic)
{
    ASSERT_EQ(10, w_parse("\x1b[10Gx"));
}

TEST(cursor_max_extent)
{
    ASSERT_EQ(19, w_parse("hello\x1b[DDDDDworld123456"));
}

TEST(cursor_forward_back)
{
    ASSERT_EQ(3, w_parse("abc\x1b[3Dxy"));
}

TEST(ignore_sgr)
{
    ASSERT_EQ(3, w_ignore("\x1b[31mred\x1b[0m"));
}

TEST(ignore_tab)
{
    ASSERT_EQ(0, w_ignore("\t"));
}

TEST(ignore_bs)
{
    /* IGNORE mode strips BS, leaving "1234" with width 4. */
    ASSERT_EQ(4, w_ignore("123\b4"));
}

TEST(ignore_osc8)
{
    ASSERT_EQ(6, w_ignore("\x1b]8;id=1;https://x.com\x1b\\[view]\x1b]8;;\x1b\\"));
}

TEST(ignore_plain)
{
    ASSERT_EQ(5, w_ignore("hello"));
}

TEST(strict_indeterminate)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    int result = width_u8("\x1b[2J", (size_t) -1, WCWIDTH_STRICT, &opts, &error);
    ASSERT_EQ(-1, result);
    ASSERT_TRUE(error != 0);
}

TEST(strict_cursor_left_exceed)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    int result = width_u8("\x1b[5D", (size_t) -1, WCWIDTH_STRICT, &opts, &error);
    ASSERT_EQ(-1, result);
    ASSERT_TRUE(error != 0);
}

TEST(strict_vertical)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    int result = width_u8("a\nb", 3, WCWIDTH_STRICT, &opts, &error);
    ASSERT_EQ(-1, result);
    ASSERT_TRUE(error != 0);
}

TEST(strict_illegal_ctrl)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    int result = width_u8("\x01", 1, WCWIDTH_STRICT, &opts, &error);
    ASSERT_EQ(-1, result);
    ASSERT_TRUE(error != 0);
}

TEST(strict_hpa)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    int result = width_u8("\x1b[10G", (size_t) -1, WCWIDTH_STRICT, &opts, &error);
    ASSERT_EQ(-1, result);
    ASSERT_TRUE(error != 0);
}

TEST(strict_cr)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    int result = width_u8("\r", 1, WCWIDTH_STRICT, &opts, &error);
    ASSERT_EQ(-1, result);
    ASSERT_TRUE(error != 0);
}

TEST(strict_ok_sgr)
{
    ASSERT_EQ(3, w_strict("\x1b[31mred\x1b[0m"));
}

TEST(strict_ok_cursor_forward)
{
    ASSERT_EQ(11, w_strict("1\x1b[10C"));
}

TEST(strict_ok_cursor_back)
{
    ASSERT_EQ(5, w_strict("hello\x1b[2D"));
}

TEST(osc8_hyperlink)
{
    ASSERT_EQ(6, w_parse("\x1b]8;id=1;https://x.com\x1b\\[view]\x1b]8;;\x1b\\"));
}

TEST(osc8_open_only)
{
    ASSERT_EQ(6, w_parse("\x1b]8;id=1;https://x.com\x1b\\[view]"));
}

TEST(ctrl_nul)
{
    /* Embedded NUL: use explicit length, strlen stops at NUL. */
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    int result = width_u8("a\0bc", 4, WCWIDTH_PARSE, &opts, &error);
    ASSERT_EQ(3, result);
}

TEST(ctrl_bel)
{
    ASSERT_EQ(3, w_parse("a\x07"
                         "bc"));
}

TEST(ctrl_so_si)
{
    ASSERT_EQ(3, w_parse("a\x0e\x0f"
                         "bc"));
}

TEST(ctrl_del)
{
    ASSERT_EQ(3, w_parse("ab\x7f"
                         "c"));
}

TEST(ctrl_illegal_parse)
{
    ASSERT_EQ(3, w_parse("ab\x01"
                         "c"));
}

TEST(ctrl_vt_parse)
{
    ASSERT_EQ(3, w_parse("a\x0b"
                         "bc"));
}

TEST(mixed_sgr_and_tab)
{
    ASSERT_EQ(9, w_parse("\x1b[31ma\x1b[0m\tb"));
}

TEST(mixed_cursor_and_sgr)
{
    ASSERT_EQ(5, w_parse("\x1b[31mab\x1b[3C\x1b[0m"));
}

TEST(wide_chars)
{
    ASSERT_EQ(10, w_parse("\xe3\x82\xb3\xe3\x83\xb3\xe3\x83\x8b\xe3\x83\x81\xe3\x83\x8f"));
}

TEST(wide_chars_with_sgr)
{
    /* "コンニチハ" = 5 wide chars × 2 cells each = 10 */
    ASSERT_EQ(
        10, w_parse("\x1b[31m\xe3\x82\xb3\xe3\x83\xb3\xe3\x83\x8b\xe3\x83\x81\xe3\x83\x8f\x1b[0m"));
}

TEST(u32_ascii)
{
    uint32_t text[] = {'h', 'e', 'l', 'l', 'o'};
    int error = 0;
    int result = width_u32(text, 5, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error);
    ASSERT_EQ(5, result);
    ASSERT_EQ(0, error);
}

TEST(u32_tab)
{
    uint32_t text[] = {'a', 'b', '\t'};
    int error = 0;
    int result = width_u32(text, 3, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error);
    ASSERT_EQ(8, result);
}

TEST(u32_sgr)
{
    uint32_t text[] = {0x1B, '[', '3', '1', 'm', 'r', 'e', 'd', 0x1B, '[', '0', 'm'};
    int error = 0;
    int result = width_u32(text, 12, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error);
    ASSERT_EQ(3, result);
}

TEST(u32_ignore)
{
    uint32_t text[] = {0x1B, '[', '3', '1', 'm', 'r', 'e', 'd', 0x1B, '[', '0', 'm'};
    int error = 0;
    int result = width_u32(text, 12, WCWIDTH_IGNORE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error);
    ASSERT_EQ(3, result);
}

TEST(u32_wide)
{
    uint32_t text[] = {0x30B3, 0x30F3, 0x30CB, 0x30C1, 0x30CF};
    int error = 0;
    int result = width_u32(text, 5, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error);
    ASSERT_EQ(10, result);
}

TEST(null_input)
{
    int error = 0;
    int result = width_u8(NULL, 0, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error);
    ASSERT_EQ(0, result);
}

TEST(null_codepoints)
{
    int error = 0;
    int result = width_u32(NULL, 0, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error);
    ASSERT_EQ(0, result);
}

TEST(zero_length)
{
    int error = 0;
    int result = width_u8("hello", 0, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error);
    ASSERT_EQ(0, result);
}

TEST(fast_path_long_ascii)
{
    ASSERT_EQ(42, w_parse("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOP"));
}

TEST(fast_path_long_sgr_only)
{
    ASSERT_EQ(26, w_parse("\x1b[31mabcdefghijklmnopqrstuvwxyz\x1b[0m"));
}

TEST(fast_path_long_with_tab)
{
    ASSERT_EQ(37, w_parse("abcdefghijklmnopqrstuvwxyz\t12345"));
}

TEST(osc66_display_width)
{
    ASSERT_EQ(5, w_parse("\x1b]66;s=1;hello\x07"));
}

TEST(osc66_with_scale)
{
    ASSERT_EQ(10, w_parse("\x1b]66;s=2;hello\x07"));
}

TEST(osc66_with_sgr)
{
    ASSERT_EQ(5, w_parse("abc\x1b]66;s=1;xy\x07"));
}

TEST(combining_mark)
{
    /* "e" + combining acute accent = width 1 */
    ASSERT_EQ(1, w_parse("e\xcc\x81"));
}

TEST(vs16_makes_wide)
{
    /* U+2702 (scissors, narrow=1) + VS16 → wide=2 */
    ASSERT_EQ(2, w_parse("\xe2\x9c\x82\xef\xb8\x8f"));
}

TEST(indeterminate_parse)
{
    ASSERT_EQ(0, w_parse("\x1b[2J"));
}

TEST(indeterminate_parse_with_text)
{
    ASSERT_EQ(5, w_parse("\x1b[2Jhello"));
}

int
main(void)
{
    RUN_TEST(ascii_plain);
    RUN_TEST(ascii_empty);
    RUN_TEST(ascii_single);

    RUN_TEST(sgr_zero_width);
    RUN_TEST(sgr_around_text);
    RUN_TEST(sgr_multiple);
    RUN_TEST(sgr_and_text);

    RUN_TEST(tab_basic);
    RUN_TEST(tab_after_text);
    RUN_TEST(tab_mid_text);
    RUN_TEST(tab_multiple);
    RUN_TEST(tab_at_stop);

    RUN_TEST(bs_basic);
    RUN_TEST(bs_at_start);

    RUN_TEST(cr_basic);
    RUN_TEST(cr_followed);

    RUN_TEST(cuf_default);
    RUN_TEST(cuf_with_n);

    RUN_TEST(cub_basic);
    RUN_TEST(cub_past_start);

    RUN_TEST(hpa_basic);

    RUN_TEST(cursor_max_extent);
    RUN_TEST(cursor_forward_back);

    RUN_TEST(ignore_sgr);
    RUN_TEST(ignore_tab);
    RUN_TEST(ignore_bs);
    RUN_TEST(ignore_osc8);
    RUN_TEST(ignore_plain);

    RUN_TEST(strict_indeterminate);
    RUN_TEST(strict_cursor_left_exceed);
    RUN_TEST(strict_vertical);
    RUN_TEST(strict_illegal_ctrl);
    RUN_TEST(strict_hpa);
    RUN_TEST(strict_cr);

    RUN_TEST(strict_ok_sgr);
    RUN_TEST(strict_ok_cursor_forward);
    RUN_TEST(strict_ok_cursor_back);

    RUN_TEST(osc8_hyperlink);
    RUN_TEST(osc8_open_only);

    RUN_TEST(ctrl_nul);
    RUN_TEST(ctrl_bel);
    RUN_TEST(ctrl_so_si);
    RUN_TEST(ctrl_del);
    RUN_TEST(ctrl_illegal_parse);
    RUN_TEST(ctrl_vt_parse);

    RUN_TEST(mixed_sgr_and_tab);
    RUN_TEST(mixed_cursor_and_sgr);

    RUN_TEST(wide_chars);
    RUN_TEST(wide_chars_with_sgr);

    RUN_TEST(u32_ascii);
    RUN_TEST(u32_tab);
    RUN_TEST(u32_sgr);
    RUN_TEST(u32_ignore);
    RUN_TEST(u32_wide);

    RUN_TEST(null_input);
    RUN_TEST(null_codepoints);
    RUN_TEST(zero_length);

    RUN_TEST(fast_path_long_ascii);
    RUN_TEST(fast_path_long_sgr_only);
    RUN_TEST(fast_path_long_with_tab);

    RUN_TEST(osc66_display_width);
    RUN_TEST(osc66_with_scale);
    RUN_TEST(osc66_with_sgr);

    RUN_TEST(combining_mark);
    RUN_TEST(vs16_makes_wide);

    RUN_TEST(indeterminate_parse);
    RUN_TEST(indeterminate_parse_with_text);

    return test_summary();
}
