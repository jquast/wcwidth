#include "test_common.h"
#include "wcwidth/clip.h"
#include "wcwidth/width.h"
#include "wcwidth/wcwidth.h"
#include <string.h>
#include <stdlib.h>

static size_t
c_opts(const char *text, size_t start, size_t end, wcwidth_control_mode_t mode, int tabsize,
       int ambiguous_width, const char *term_program, bool propagate_sgr, char fillchar)
{
    size_t len = 0;
    char *result = clip_u8(text, strlen(text), start, end, mode, tabsize, ambiguous_width,
                           term_program, propagate_sgr, fillchar, &len);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ(len, strlen(result));
    free(result);
    return len;
}

static size_t
c(const char *text, size_t start, size_t end)
{
    return c_opts(text, start, end, WCWIDTH_PARSE, 8, 1, NULL, true, ' ');
}

static const char *
cs_opts(const char *text, size_t start, size_t end, wcwidth_control_mode_t mode, int tabsize,
        int ambiguous_width, const char *term_program, bool propagate_sgr, char fillchar)
{
    static char *last = NULL;
    size_t len = 0;

    free(last);
    last = clip_u8(text, strlen(text), start, end, mode, tabsize, ambiguous_width, term_program,
                   propagate_sgr, fillchar, &len);
    ASSERT_NOT_NULL(last);
    ASSERT_EQ(len, strlen(last));
    return last;
}

static const char *
cs(const char *text, size_t start, size_t end)
{
    return cs_opts(text, start, end, WCWIDTH_PARSE, 8, 1, NULL, true, ' ');
}

static int
w_parse(const char *text)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    return width_u8(text, strlen(text), WCWIDTH_PARSE, &opts, &error);
}

TEST(basic_empty)
{
    ASSERT_STREQ("", cs("", 0, 5));
    ASSERT_STREQ("", cs("", 0, 0));
    ASSERT_EQ(0U, c("", 0, 5));
}

TEST(basic_zero_range)
{
    ASSERT_STREQ("", cs("hello", 0, 0));
    ASSERT_STREQ("", cs("hello", 5, 5));
    ASSERT_STREQ("", cs("hello", 5, 3));
}

TEST(basic_ascii)
{
    ASSERT_STREQ("hello", cs("hello", 0, 5));
    ASSERT_STREQ("hel", cs("hello", 0, 3));
    ASSERT_STREQ("llo", cs("hello", 2, 5));
    ASSERT_STREQ("ell", cs("hello", 1, 4));
}

TEST(basic_sentences)
{
    ASSERT_STREQ("hello", cs("hello world", 0, 5));
    ASSERT_STREQ("world", cs("hello world", 6, 11));
    ASSERT_STREQ("hello world", cs("hello world", 0, 11));
}

TEST(basic_oob)
{
    ASSERT_STREQ("hi", cs("hi", 0, 100));
    ASSERT_STREQ("", cs("hi", 100, 200));
}

TEST(cjk_full)
{
    ASSERT_STREQ("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97",
                 cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 0, 6));
}

TEST(cjk_partial)
{
    ASSERT_STREQ("\xe4\xb8\xad\xe6\x96\x87", cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 0, 4));
    ASSERT_STREQ("\xe4\xb8\xad", cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 0, 2));
    ASSERT_STREQ("\xe6\x96\x87", cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 2, 4));
}

TEST(cjk_fillchar)
{
    ASSERT_STREQ("\xe4\xb8\xad ", cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 0, 3));
    ASSERT_STREQ(" \xe6\x96\x87\xe5\xad\x97", cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 1, 6));
    ASSERT_STREQ(" \xe6\x96\x87 ", cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 1, 5));
}

TEST(cjk_mixed)
{
    ASSERT_STREQ("A\xe4\xb8\xad"
                 "B",
                 cs("A\xe4\xb8\xad"
                    "B",
                    0, 4));
    ASSERT_STREQ("A\xe4\xb8\xad", cs("A\xe4\xb8\xad"
                                     "B",
                                     0, 3));
    ASSERT_STREQ("\xe4\xb8\xad"
                 "B",
                 cs("A\xe4\xb8\xad"
                    "B",
                    1, 4));
    ASSERT_STREQ("\xe4\xb8\xad", cs("A\xe4\xb8\xad"
                                    "B",
                                    1, 3));
    ASSERT_STREQ(" "
                 "B",
                 cs("A\xe4\xb8\xad"
                    "B",
                    2, 4));
}

TEST(cjk_single)
{
    ASSERT_STREQ("\xe4\xb8\xad", cs("\xe4\xb8\xad", 0, 2));
    ASSERT_STREQ(" ", cs("\xe4\xb8\xad", 0, 1));
    ASSERT_STREQ(" ", cs("\xe4\xb8\xad", 1, 2));
}

TEST(cjk_custom_fillchar)
{
    ASSERT_STREQ(".\xe6\x96\x87.", cs_opts("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 1, 5,
                                           WCWIDTH_PARSE, 8, 1, NULL, true, '.'));
}

TEST(sgr_preserve)
{
    ASSERT_STREQ("\x1b[31mred\x1b[0m", cs("\x1b[31mred\x1b[0m", 0, 3));
}

TEST(sgr_before_start)
{
    ASSERT_STREQ("\x1b[31mtext\x1b[0m", cs("\x1b[31mred text\x1b[0m", 4, 8));
}

TEST(sgr_multiple)
{
    ASSERT_STREQ("\x1b[1;31mbold\x1b[0m", cs("\x1b[1m\x1b[31mbold red\x1b[0m", 0, 4));
}

TEST(sgr_no_propagate)
{
    ASSERT_STREQ("\x1b[1m\x1b[31mbold\x1b[0m", cs_opts("\x1b[1m\x1b[31mbold red\x1b[0m", 0, 4,
                                                       WCWIDTH_PARSE, 8, 1, NULL, false, ' '));
}

TEST(sgr_only)
{
    ASSERT_STREQ("", cs("\x1b[31m\x1b[0m", 0, 10));
}

TEST(sgr_only_no_propagate)
{
    ASSERT_STREQ("\x1b[31m\x1b[0m",
                 cs_opts("\x1b[31m\x1b[0m", 0, 10, WCWIDTH_PARSE, 8, 1, NULL, false, ' '));
}

TEST(sgr_cjk)
{
    ASSERT_STREQ("\x1b[31m\xe4\xb8\xad \x1b[0m",
                 cs("\x1b[31m\xe4\xb8\xad\xe6\x96\x87\x1b[0m", 0, 3));
    ASSERT_STREQ("\x1b[31m \xe6\x96\x87\x1b[0m",
                 cs("\x1b[31m\xe4\xb8\xad\xe6\x96\x87\x1b[0m", 1, 4));
}

TEST(sgr_between_chars)
{
    ASSERT_STREQ("\x1b[31m"
                 "b"
                 "\x1b[0m",
                 cs("a\x1b[31m"
                    "b"
                    "\x1b[0mc",
                    1, 2));
}

TEST(sgr_lone_esc)
{
    ASSERT_STREQ("a"
                 "\x1b"
                 "b",
                 cs("a"
                    "\x1b"
                    "b",
                    0, 2));
}

TEST(emoji_smiley)
{
    ASSERT_STREQ("\xf0\x9f\x98\x80", cs("\xf0\x9f\x98\x80", 0, 2));
    ASSERT_STREQ(" ", cs("\xf0\x9f\x98\x80", 0, 1));
    ASSERT_EQ(2, w_parse("\xf0\x9f\x98\x80"));
}

TEST(emoji_with_sgr)
{
    ASSERT_STREQ("\x1b[1m\xf0\x9f\x98\x80\x1b[0m", cs("\x1b[1m\xf0\x9f\x98\x80\x1b[0m", 0, 2));
}

TEST(combining_accent)
{
    ASSERT_STREQ("caf\x65\xcc\x81", cs("caf\x65\xcc\x81", 0, 4));
    ASSERT_STREQ("caf", cs("caf\x65\xcc\x81", 0, 3));
}

TEST(combining_multiple)
{
    ASSERT_STREQ("\x65\xcc\x81\xcc\xa7", cs("\x65\xcc\x81\xcc\xa7", 0, 1));
}

TEST(combining_position)
{
    ASSERT_STREQ("ell", cs("\xcc\x81hello", 1, 4));
    ASSERT_STREQ("hel", cs("hello\xcc\x81", 0, 3));
    ASSERT_STREQ("h\x65\xcc\x81ll", cs("h\x65\xcc\x81llo", 0, 4));
}

TEST(ambiguous_width1)
{
    ASSERT_STREQ("\xc2\xb1te", cs_opts("\xc2\xb1test", 0, 3, WCWIDTH_PARSE, 8, 1, NULL, true, ' '));
}

TEST(ambiguous_width2)
{
    ASSERT_STREQ("\xc2\xb1t", cs_opts("\xc2\xb1test", 0, 3, WCWIDTH_PARSE, 8, 2, NULL, true, ' '));
}

TEST(tab_basic)
{
    ASSERT_STREQ("a       b", cs_opts("a\tb", 0, 10, WCWIDTH_PARSE, 8, 1, NULL, true, ' '));
    ASSERT_STREQ("a   ", cs_opts("a\tb", 0, 4, WCWIDTH_PARSE, 8, 1, NULL, true, ' '));
}

TEST(tab_tabsize4)
{
    ASSERT_STREQ("a   b", cs_opts("a\tb", 0, 10, WCWIDTH_PARSE, 4, 1, NULL, true, ' '));
    ASSERT_STREQ("    b", cs_opts("a\tb", 4, 10, WCWIDTH_PARSE, 8, 1, NULL, true, ' '));
}

TEST(tab_cjk)
{
    ASSERT_STREQ("\xe4\xb8\xad  b",
                 cs_opts("\xe4\xb8\xad\tb", 0, 10, WCWIDTH_PARSE, 4, 1, NULL, true, ' '));
}

TEST(tab_zero)
{
    ASSERT_STREQ("a\tb", cs_opts("a\tb", 0, 5, WCWIDTH_PARSE, 0, 1, NULL, true, ' '));
}

TEST(tab_with_sgr)
{
    ASSERT_STREQ("\x1b[31mab  c\x1b[0m",
                 cs_opts("\x1b[31mab\tc\x1b[0m", 0, 12, WCWIDTH_PARSE, 4, 1, NULL, true, ' '));
}

TEST(hyperlink_full)
{
    const char *t = "\x1b]8;;http://example.com\x07"
                    "link\x1b]8;;\x07";
    ASSERT_STREQ(t, cs(t, 0, 4));
}

TEST(hyperlink_clip_middle)
{
    ASSERT_STREQ("\x1b]8;;http://example.com\x07"
                 "This\x1b]8;;\x07",
                 cs("\x1b]8;;http://example.com\x07"
                    "Click This link\x1b]8;;\x07",
                    6, 10));
}

TEST(hyperlink_clip_start)
{
    ASSERT_STREQ("\x1b]8;;http://example.com\x07"
                 "Click\x1b]8;;\x07",
                 cs("\x1b]8;;http://example.com\x07"
                    "Click This\x1b]8;;\x07",
                    0, 5));
}

TEST(hyperlink_clip_end)
{
    ASSERT_STREQ("\x1b]8;;http://example.com\x07"
                 "This\x1b]8;;\x07",
                 cs("\x1b]8;;http://example.com\x07"
                    "Click This\x1b]8;;\x07",
                    6, 10));
}

TEST(hyperlink_before_window)
{
    ASSERT_STREQ("\x1b]8;;http://example.com\x07"
                 "link\x1b]8;;\x07",
                 cs("\x1b]8;;http://example.com\x07"
                    "link\x1b]8;;\x07"
                    "world",
                    0, 4));
}

TEST(hyperlink_after_window)
{
    ASSERT_STREQ("hello", cs("hello\x1b]8;;http://example.com\x07"
                             "link\x1b]8;;\x07",
                             0, 5));
}

TEST(hyperlink_empty_inner)
{
    ASSERT_STREQ("beforeafter", cs("before\x1b]8;;http://example.com\x07\x1b]8;;\x07"
                                   "after",
                                   0, 11));
}

TEST(hyperlink_cjk_clip)
{
    ASSERT_STREQ("\x1b]8;;http://example.com\x07"
                 "\xe4\xb8\xad\xe6\x96\x87\x1b]8;;\x07",
                 cs("\x1b]8;;http://example.com\x07"
                    "\xe4\xb8\xad\xe6\x96\x87\xe6\x96\x87\xe5\xad\x97\x1b]8;;\x07",
                    0, 4));
}

TEST(hyperlink_no_close)
{
    const char *t = "\x1b]8;;http://example.com\x07"
                    "link";
    ASSERT_STREQ(t, cs(t, 0, 4));
}

TEST(ctrl_zero_width)
{
    ASSERT_STREQ("ab"
                 "\x07"
                 "cd",
                 cs("ab"
                    "\x07"
                    "cd",
                    0, 4));
    ASSERT_STREQ("ab\x00"
                 "cd",
                 cs("ab\x00"
                    "cd",
                    0, 4));
}

TEST(strict_indeterminate_raises)
{
    size_t len = 0;
    char *result =
        clip_u8("hello\x1b[Hworld", 12, 0, 10, WCWIDTH_STRICT, 8, 1, NULL, true, ' ', &len);
    ASSERT_NULL(result);
    ASSERT_EQ(0U, len);
}

TEST(strict_cursor_left_raises)
{
    size_t len = 0;
    char *result = clip_u8("a\x1b[5D"
                           "a",
                           6, 0, 1, WCWIDTH_STRICT, 8, 1, NULL, true, ' ', &len);
    ASSERT_NULL(result);
}

TEST(painter_cursor_right)
{
    ASSERT_STREQ("hello     ", cs("hello\x1b[10Cworld", 0, 10));
    ASSERT_STREQ("hello", cs("hello\x1b[10Cworld", 0, 5));
}

TEST(painter_cursor_left_overwrite)
{
    ASSERT_STREQ("helXY", cs("hello\x1b[2DXY", 0, 5));
    ASSERT_STREQ("XYc", cs("abc\x1b[3DXY", 0, 5));
}

TEST(painter_cursor_left_at_zero)
{
    ASSERT_STREQ("hi", cs("\x1b[2Dhi", 0, 2));
}

TEST(painter_cursor_left_past_zero)
{
    ASSERT_STREQ("cd", cs("ab\x1b[99Dcd", 0, 4));
}

TEST(painter_cr)
{
    ASSERT_STREQ("xxx", cs("aaa\r\r\rxxx", 0, 4));
    ASSERT_STREQ("XYc", cs("abc\rXY", 0, 5));
    ASSERT_STREQ("world", cs("hello\rworld", 0, 5));
}

TEST(painter_cr_within_window)
{
    ASSERT_STREQ("ec", cs("abc\rde", 1, 3));
}

TEST(painter_bs)
{
    ASSERT_STREQ("abde", cs("abc\bde", 0, 5));
    ASSERT_STREQ("aXY", cs("abc\b\bXY", 0, 5));
    ASSERT_STREQ("XY", cs("ab\b\b\bXY", 0, 4));
}

TEST(painter_hpa)
{
    ASSERT_STREQ("XYc", cs("abc\x1b[GXY", 0, 5));
    ASSERT_STREQ("aXY", cs("abc\x1b[2GXY", 0, 5));
    ASSERT_STREQ("abc XY", cs("abc\x1b[5GXY", 0, 7));
    ASSERT_STREQ("abc X", cs("abc\x1b[5GXY", 0, 5));
}

TEST(painter_sgr_and_cursor)
{
    ASSERT_STREQ("\x1b[31mcd\x1b[0m", cs("\x1b[31mab\x1b[2Dcd", 0, 4));
}

TEST(painter_sgr_no_propagate)
{
    ASSERT_STREQ("cd", cs_opts("ab\x1b[2Dcd", 0, 4, WCWIDTH_PARSE, 8, 1, NULL, false, ' '));
}

TEST(painter_wide_overwritten)
{
    ASSERT_STREQ("a b", cs("a\xe4\xb8\xad\x1b[Db", 0, 4));
}

TEST(painter_wide_partial)
{
    ASSERT_STREQ(" "
                 "d",
                 cs("ab\x1b[2D\xe4\xb8\xad"
                    "d",
                    1, 4));
}

TEST(painter_gap_fillchar)
{
    ASSERT_STREQ("     hi", cs("\x1b[5Chi", 0, 7));
}

TEST(painter_tab_zero)
{
    ASSERT_STREQ("\tcd", cs_opts("ab\x1b[2D\tcd", 0, 4, WCWIDTH_PARSE, 0, 1, NULL, true, ' '));
}

TEST(painter_lone_esc)
{
    ASSERT_STREQ("c"
                 "\x1b"
                 "b",
                 cs("a"
                    "\x1b"
                    "b\x1b[2Dc",
                    0, 3));
}

TEST(painter_strict_cursor_left_raises)
{
    size_t len = 0;
    char *result = clip_u8("\x1b[2Dab", 4, 0, 2, WCWIDTH_STRICT, 8, 1, NULL, true, ' ', &len);
    ASSERT_NULL(result);
}

TEST(painter_strict_indeterminate)
{
    size_t len = 0;
    char *result = clip_u8("a\x1b[D\x1b[Hb", 8, 0, 3, WCWIDTH_STRICT, 8, 1, NULL, true, ' ', &len);
    ASSERT_NULL(result);
}

TEST(painter_ignore_mode_no_movement)
{
    ASSERT_STREQ("ab\x08"
                 "cd",
                 cs_opts("ab\x08"
                         "cd",
                         0, 4, WCWIDTH_IGNORE, 8, 1, NULL, true, ' '));
}

TEST(width_consistency)
{
    const char *result;
    int w;

    result = cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 0, 6);
    w = w_parse(result);
    ASSERT_EQ(6, w);

    result = cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 0, 3);
    w = w_parse(result);
    ASSERT_EQ(3, w);

    result = cs("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 1, 6);
    w = w_parse(result);
    ASSERT_EQ(5, w);
}

int
main(void)
{
    RUN_TEST(basic_empty);
    RUN_TEST(basic_zero_range);
    RUN_TEST(basic_ascii);
    RUN_TEST(basic_sentences);
    RUN_TEST(basic_oob);
    RUN_TEST(cjk_full);
    RUN_TEST(cjk_partial);
    RUN_TEST(cjk_fillchar);
    RUN_TEST(cjk_mixed);
    RUN_TEST(cjk_single);
    RUN_TEST(cjk_custom_fillchar);
    RUN_TEST(sgr_preserve);
    RUN_TEST(sgr_before_start);
    RUN_TEST(sgr_multiple);
    RUN_TEST(sgr_no_propagate);
    RUN_TEST(sgr_only);
    RUN_TEST(sgr_only_no_propagate);
    RUN_TEST(sgr_cjk);
    RUN_TEST(sgr_between_chars);
    RUN_TEST(sgr_lone_esc);
    RUN_TEST(emoji_smiley);
    RUN_TEST(emoji_with_sgr);
    RUN_TEST(combining_accent);
    RUN_TEST(combining_multiple);
    RUN_TEST(combining_position);
    RUN_TEST(ambiguous_width1);
    RUN_TEST(ambiguous_width2);
    RUN_TEST(tab_basic);
    RUN_TEST(tab_tabsize4);
    RUN_TEST(tab_cjk);
    RUN_TEST(tab_zero);
    RUN_TEST(tab_with_sgr);
    RUN_TEST(hyperlink_full);
    RUN_TEST(hyperlink_clip_middle);
    RUN_TEST(hyperlink_clip_start);
    RUN_TEST(hyperlink_clip_end);
    RUN_TEST(hyperlink_before_window);
    RUN_TEST(hyperlink_after_window);
    RUN_TEST(hyperlink_empty_inner);
    RUN_TEST(hyperlink_cjk_clip);
    RUN_TEST(hyperlink_no_close);
    RUN_TEST(ctrl_zero_width);
    RUN_TEST(strict_indeterminate_raises);
    RUN_TEST(strict_cursor_left_raises);
    RUN_TEST(painter_cursor_right);
    RUN_TEST(painter_cursor_left_overwrite);
    RUN_TEST(painter_cursor_left_at_zero);
    RUN_TEST(painter_cursor_left_past_zero);
    RUN_TEST(painter_cr);
    RUN_TEST(painter_cr_within_window);
    RUN_TEST(painter_bs);
    RUN_TEST(painter_hpa);
    RUN_TEST(painter_sgr_and_cursor);
    RUN_TEST(painter_sgr_no_propagate);
    RUN_TEST(painter_wide_overwritten);
    RUN_TEST(painter_wide_partial);
    RUN_TEST(painter_gap_fillchar);
    RUN_TEST(painter_tab_zero);
    RUN_TEST(painter_lone_esc);
    RUN_TEST(painter_strict_cursor_left_raises);
    RUN_TEST(painter_strict_indeterminate);
    RUN_TEST(painter_ignore_mode_no_movement);
    RUN_TEST(width_consistency);
    return test_summary();
}
