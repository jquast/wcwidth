#include "test_common.h"
#include "wcwidth/sgr.h"
#include <string.h>

/*
 * Parse a full SGR escape sequence and apply it to a fresh default state.
 * For convenience in tests: "\x1b[1;31m" is parsed, params extracted, and
 * the state updated.
 */
static wcwidth_sgr_state_t
make_state(const char *sgr_esc)
{
    wcwidth_sgr_state_t s = WCWIDTH_SGR_STATE_DEFAULT;
    const char *start = strchr(sgr_esc, '[');
    const char *end = strchr(sgr_esc, 'm');

    if (start != NULL && end != NULL && end > start) {
        wcwidth_sgr_update(&s, start + 1, (size_t) (end - start - 1));
    }
    return s;
}

TEST(parse_bold)
{
    wcwidth_sgr_state_t s = make_state("\x1b[1m");
    ASSERT_TRUE(s.bold);
    ASSERT_FALSE(s.dim);
}

TEST(parse_dim)
{
    wcwidth_sgr_state_t s = make_state("\x1b[2m");
    ASSERT_TRUE(s.dim);
}

TEST(parse_italic)
{
    wcwidth_sgr_state_t s = make_state("\x1b[3m");
    ASSERT_TRUE(s.italic);
}

TEST(parse_underline)
{
    wcwidth_sgr_state_t s = make_state("\x1b[4m");
    ASSERT_TRUE(s.underline);
}

TEST(parse_blink)
{
    wcwidth_sgr_state_t s = make_state("\x1b[5m");
    ASSERT_TRUE(s.blink);
}

TEST(parse_rapid_blink)
{
    wcwidth_sgr_state_t s = make_state("\x1b[6m");
    ASSERT_TRUE(s.rapid_blink);
}

TEST(parse_inverse)
{
    wcwidth_sgr_state_t s = make_state("\x1b[7m");
    ASSERT_TRUE(s.inverse);
}

TEST(parse_hidden)
{
    wcwidth_sgr_state_t s = make_state("\x1b[8m");
    ASSERT_TRUE(s.hidden);
}

TEST(parse_strikethrough)
{
    wcwidth_sgr_state_t s = make_state("\x1b[9m");
    ASSERT_TRUE(s.strikethrough);
}

TEST(parse_double_underline)
{
    wcwidth_sgr_state_t s = make_state("\x1b[21m");
    ASSERT_TRUE(s.double_underline);
}

TEST(parse_italic_off)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.italic = true;
    wcwidth_sgr_update(&s, "23", 2);
    ASSERT_FALSE(s.italic);
}

TEST(parse_inverse_off)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.inverse = true;
    wcwidth_sgr_update(&s, "27", 2);
    ASSERT_FALSE(s.inverse);
}

TEST(parse_hidden_off)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.hidden = true;
    wcwidth_sgr_update(&s, "28", 2);
    ASSERT_FALSE(s.hidden);
}

TEST(parse_strikethrough_off)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.strikethrough = true;
    wcwidth_sgr_update(&s, "29", 2);
    ASSERT_FALSE(s.strikethrough);
}

TEST(parse_bold_dim_off)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bold = true;
    s.dim = true;
    wcwidth_sgr_update(&s, "22", 2);
    ASSERT_FALSE(s.bold);
    ASSERT_FALSE(s.dim);
}

TEST(parse_underline_off)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.underline = true;
    s.double_underline = true;
    wcwidth_sgr_update(&s, "24", 2);
    ASSERT_FALSE(s.underline);
    ASSERT_FALSE(s.double_underline);
}

TEST(parse_blink_off)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.blink = true;
    s.rapid_blink = true;
    wcwidth_sgr_update(&s, "25", 2);
    ASSERT_FALSE(s.blink);
    ASSERT_FALSE(s.rapid_blink);
}

TEST(parse_fg_standard)
{
    wcwidth_sgr_state_t s = make_state("\x1b[31m");

    ASSERT_EQ(1, s.fg_len);
    ASSERT_EQ(31, s.fg[0]);
}

TEST(parse_bg_standard)
{
    wcwidth_sgr_state_t s = make_state("\x1b[41m");

    ASSERT_EQ(1, s.bg_len);
    ASSERT_EQ(41, s.bg[0]);
}

TEST(parse_fg_bright)
{
    wcwidth_sgr_state_t s = make_state("\x1b[91m");

    ASSERT_EQ(1, s.fg_len);
    ASSERT_EQ(91, s.fg[0]);
}

TEST(parse_bg_bright)
{
    wcwidth_sgr_state_t s = make_state("\x1b[101m");

    ASSERT_EQ(1, s.bg_len);
    ASSERT_EQ(101, s.bg[0]);
}

TEST(parse_fg_256_semicolon)
{
    wcwidth_sgr_state_t s = make_state("\x1b[38;5;208m");

    ASSERT_EQ(3, s.fg_len);
    ASSERT_EQ(38, s.fg[0]);
    ASSERT_EQ(5, s.fg[1]);
    ASSERT_EQ(208, s.fg[2]);
}

TEST(parse_bg_256_semicolon)
{
    wcwidth_sgr_state_t s = make_state("\x1b[48;5;208m");

    ASSERT_EQ(3, s.bg_len);
    ASSERT_EQ(48, s.bg[0]);
    ASSERT_EQ(5, s.bg[1]);
    ASSERT_EQ(208, s.bg[2]);
}

TEST(parse_fg_rgb_semicolon)
{
    wcwidth_sgr_state_t s = make_state("\x1b[38;2;255;128;0m");

    ASSERT_EQ(5, s.fg_len);
    ASSERT_EQ(38, s.fg[0]);
    ASSERT_EQ(2, s.fg[1]);
    ASSERT_EQ(255, s.fg[2]);
    ASSERT_EQ(128, s.fg[3]);
    ASSERT_EQ(0, s.fg[4]);
}

TEST(parse_bg_rgb_semicolon)
{
    wcwidth_sgr_state_t s = make_state("\x1b[48;2;255;128;0m");

    ASSERT_EQ(5, s.bg_len);
    ASSERT_EQ(48, s.bg[0]);
    ASSERT_EQ(2, s.bg[1]);
    ASSERT_EQ(255, s.bg[2]);
    ASSERT_EQ(128, s.bg[3]);
    ASSERT_EQ(0, s.bg[4]);
}

TEST(parse_fg_256_colon)
{
    wcwidth_sgr_state_t s = make_state("\x1b[38:5:208m");

    ASSERT_EQ(3, s.fg_len);
    ASSERT_EQ(38, s.fg[0]);
    ASSERT_EQ(5, s.fg[1]);
    ASSERT_EQ(208, s.fg[2]);
}

TEST(parse_bg_256_colon)
{
    wcwidth_sgr_state_t s = make_state("\x1b[48:5:208m");

    ASSERT_EQ(3, s.bg_len);
    ASSERT_EQ(48, s.bg[0]);
    ASSERT_EQ(5, s.bg[1]);
    ASSERT_EQ(208, s.bg[2]);
}

TEST(parse_fg_rgb_colon_empty_cs)
{
    wcwidth_sgr_state_t s = make_state("\x1b[38:2::255:128:0m");

    ASSERT_EQ(6, s.fg_len);
    ASSERT_EQ(38, s.fg[0]);
    ASSERT_EQ(2, s.fg[1]);
    ASSERT_EQ(0, s.fg[2]);
    ASSERT_EQ(255, s.fg[3]);
    ASSERT_EQ(128, s.fg[4]);
    ASSERT_EQ(0, s.fg[5]);
}

TEST(parse_bg_rgb_colon_empty_cs)
{
    wcwidth_sgr_state_t s = make_state("\x1b[48:2::255:128:0m");

    ASSERT_EQ(6, s.bg_len);
    ASSERT_EQ(48, s.bg[0]);
    ASSERT_EQ(2, s.bg[1]);
    ASSERT_EQ(0, s.bg[2]);
    ASSERT_EQ(255, s.bg[3]);
    ASSERT_EQ(128, s.bg[4]);
    ASSERT_EQ(0, s.bg[5]);
}

TEST(parse_fg_rgb_colon_with_cs)
{
    wcwidth_sgr_state_t s = make_state("\x1b[38:2:1:255:128:0m");

    ASSERT_EQ(6, s.fg_len);
    ASSERT_EQ(38, s.fg[0]);
    ASSERT_EQ(2, s.fg[1]);
    ASSERT_EQ(1, s.fg[2]);
}

TEST(parse_mixed_colon_and_semicolon)
{
    wcwidth_sgr_state_t s = make_state("\x1b[1;38:2::255:0:0;4m");

    ASSERT_TRUE(s.bold);
    ASSERT_TRUE(s.underline);
    ASSERT_EQ(6, s.fg_len);
    ASSERT_EQ(38, s.fg[0]);
    ASSERT_EQ(2, s.fg[1]);
    ASSERT_EQ(0, s.fg[2]);
    ASSERT_EQ(255, s.fg[3]);
    ASSERT_EQ(0, s.fg[4]);
    ASSERT_EQ(0, s.fg[5]);
}

TEST(parse_fg_default)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.fg[0] = 31;
    s.fg_len = 1;
    wcwidth_sgr_update(&s, "39", 2);
    ASSERT_EQ(0, s.fg_len);
}

TEST(parse_bg_default)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bg[0] = 41;
    s.bg_len = 1;
    wcwidth_sgr_update(&s, "49", 2);
    ASSERT_EQ(0, s.bg_len);
}

TEST(parse_compound)
{
    wcwidth_sgr_state_t s = make_state("\x1b[1;34;3m");

    ASSERT_TRUE(s.bold);
    ASSERT_TRUE(s.italic);
    ASSERT_EQ(1, s.fg_len);
    ASSERT_EQ(34, s.fg[0]);
}

TEST(parse_reset)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bold = true;
    s.fg[0] = 31;
    s.fg_len = 1;
    wcwidth_sgr_update(&s, "0", 1);
    ASSERT_FALSE(s.bold);
    ASSERT_EQ(0, s.fg_len);
}

TEST(parse_empty_is_reset)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bold = true;
    wcwidth_sgr_update(&s, "", 0);
    ASSERT_FALSE(s.bold);
}

TEST(parse_empty_in_compound)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bold = true;
    wcwidth_sgr_update(&s, ";1", 2);
    ASSERT_TRUE(s.bold);
}

TEST(color_override)
{
    wcwidth_sgr_state_t s;

    s = make_state("\x1b[38;5;208m");
    ASSERT_EQ(3, s.fg_len);
    ASSERT_EQ(208, s.fg[2]);

    wcwidth_sgr_update(&s, "31", 2);
    ASSERT_EQ(1, s.fg_len);
    ASSERT_EQ(31, s.fg[0]);

    wcwidth_sgr_update(&s, "38;2;0;255;0", 12);
    ASSERT_EQ(5, s.fg_len);
    ASSERT_EQ(0, s.fg[2]);
    ASSERT_EQ(255, s.fg[3]);
    ASSERT_EQ(0, s.fg[4]);

    wcwidth_sgr_update(&s, "38;5;99", 7);
    ASSERT_EQ(3, s.fg_len);
    ASSERT_EQ(99, s.fg[2]);
}

TEST(malformed_extended_fg_missing_n)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "38;5", 4);
    ASSERT_EQ(0, s.fg_len);
}

TEST(malformed_extended_fg_missing_rgb)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "38;2;255", 8);
    ASSERT_EQ(0, s.fg_len);
}

TEST(malformed_extended_bg_missing_n)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "48;5", 4);
    ASSERT_EQ(0, s.bg_len);
}

TEST(malformed_extended_bg_missing_rgb)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "48;2;255", 8);
    ASSERT_EQ(0, s.bg_len);
}

TEST(malformed_bad_mode)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "38;3;128", 8);
    ASSERT_EQ(0, s.fg_len);

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "48;3;128", 8);
    ASSERT_EQ(0, s.bg_len);
}

TEST(malformed_unknown_code)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "999", 3);
    ASSERT_FALSE(wcwidth_sgr_is_active(&s));
}

TEST(malformed_colon_unknown_base)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "99:2:255:0:0", 12);
    ASSERT_FALSE(wcwidth_sgr_is_active(&s));
}

TEST(malformed_mixed_semicolon_colon_edge)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    /* 38 seen as int, next segment "48:2:255:0:0" parsed as colon tuple */
    wcwidth_sgr_update(&s, "38;48:2:255:0:0", 17);
    ASSERT_EQ(0, s.fg_len);
}

TEST(malformed_extended_with_colon_tuple_as_mode)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "38;5;48:5:99", 12);
    ASSERT_EQ(0, s.fg_len);
}

TEST(malformed_extended_rgb_with_colon_tuple_as_b)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    wcwidth_sgr_update(&s, "38;2;255;128;48:2:0:0:0", 21);
    ASSERT_EQ(0, s.fg_len);
}

TEST(is_active_default)
{
    wcwidth_sgr_state_t s = WCWIDTH_SGR_STATE_DEFAULT;

    ASSERT_FALSE(wcwidth_sgr_is_active(&s));
}

TEST(is_active_with_attr)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bold = true;
    ASSERT_TRUE(wcwidth_sgr_is_active(&s));
}

TEST(is_active_with_color)
{
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.fg[0] = 31;
    s.fg_len = 1;
    ASSERT_TRUE(wcwidth_sgr_is_active(&s));
}

TEST(to_escape_default)
{
    char buf[64];

    wcwidth_sgr_to_escape(&WCWIDTH_SGR_STATE_DEFAULT, buf, sizeof(buf));
    ASSERT_STREQ("", buf);
}

TEST(to_escape_bold)
{
    char buf[64];
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bold = true;
    wcwidth_sgr_to_escape(&s, buf, sizeof(buf));
    ASSERT_STREQ("\x1b[1m", buf);
}

TEST(to_escape_rapid_blink)
{
    char buf[64];
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.rapid_blink = true;
    wcwidth_sgr_to_escape(&s, buf, sizeof(buf));
    ASSERT_STREQ("\x1b[6m", buf);
}

TEST(to_escape_double_underline)
{
    char buf[64];
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.double_underline = true;
    wcwidth_sgr_to_escape(&s, buf, sizeof(buf));
    ASSERT_STREQ("\x1b[21m", buf);
}

TEST(to_escape_fg_standard)
{
    char buf[64];
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.fg[0] = 31;
    s.fg_len = 1;
    wcwidth_sgr_to_escape(&s, buf, sizeof(buf));
    ASSERT_STREQ("\x1b[31m", buf);
}

TEST(to_escape_fg_256)
{
    char buf[64];
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.fg[0] = 38;
    s.fg[1] = 5;
    s.fg[2] = 208;
    s.fg_len = 3;
    wcwidth_sgr_to_escape(&s, buf, sizeof(buf));
    ASSERT_STREQ("\x1b[38;5;208m", buf);
}

TEST(to_escape_fg_rgb)
{
    char buf[64];
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.fg[0] = 38;
    s.fg[1] = 2;
    s.fg[2] = 255;
    s.fg[3] = 128;
    s.fg[4] = 0;
    s.fg_len = 5;
    wcwidth_sgr_to_escape(&s, buf, sizeof(buf));
    ASSERT_STREQ("\x1b[38;2;255;128;0m", buf);
}

TEST(to_escape_compound)
{
    char buf[64];
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bold = true;
    s.italic = true;
    s.fg[0] = 34;
    s.fg_len = 1;
    wcwidth_sgr_to_escape(&s, buf, sizeof(buf));
    ASSERT_STREQ("\x1b[1;3;34m", buf);
}

TEST(to_escape_with_bg)
{
    char buf[64];
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bold = true;
    s.italic = true;
    s.underline = true;
    s.inverse = true;
    s.fg[0] = 31;
    s.fg_len = 1;
    s.bg[0] = 44;
    s.bg_len = 1;
    wcwidth_sgr_to_escape(&s, buf, sizeof(buf));
    ASSERT_TRUE(strstr(buf, "1") != NULL);
    ASSERT_TRUE(strstr(buf, "3") != NULL);
    ASSERT_TRUE(strstr(buf, "4") != NULL);
    ASSERT_TRUE(strstr(buf, "7") != NULL);
    ASSERT_TRUE(strstr(buf, "31") != NULL);
    ASSERT_TRUE(strstr(buf, "44") != NULL);
}

TEST(propagate_empty)
{
    char *lines[] = {NULL};
    int rc = wcwidth_sgr_propagate(NULL, 0);

    ASSERT_EQ(0, rc);
    (void) lines;
}

TEST(propagate_no_sgr)
{
    char line1[] = "hello";
    char line2[] = "world";
    char *lines[] = {line1, line2};

    wcwidth_sgr_propagate(lines, 2);
    ASSERT_STREQ("hello", lines[0]);
    ASSERT_STREQ("world", lines[1]);
}

TEST(propagate_single_line)
{
    char buf[256] = "\x1b[31mhello\x1b[0m";
    char *lines[] = {buf};

    wcwidth_sgr_propagate(lines, 1);
    ASSERT_STREQ("\x1b[31mhello\x1b[0m", lines[0]);
}

TEST(propagate_two_lines)
{
    char line1[256] = "\x1b[31mhello";
    char line2[256] = "world\x1b[0m";
    char *lines[] = {line1, line2};

    wcwidth_sgr_propagate(lines, 2);
    ASSERT_STREQ("\x1b[31mhello\x1b[0m", lines[0]);
    ASSERT_STREQ("\x1b[31mworld\x1b[0m", lines[1]);
}

TEST(propagate_reset_between)
{
    char line1[256] = "\x1b[31mred\x1b[0m";
    char line2[256] = "plain";
    char *lines[] = {line1, line2};

    wcwidth_sgr_propagate(lines, 2);
    ASSERT_STREQ("\x1b[31mred\x1b[0m", lines[0]);
    ASSERT_STREQ("plain", lines[1]);
}

TEST(propagate_empty_line)
{
    char line1[256] = "\x1b[31mred";
    char line2[256] = "";
    char line3[256] = "text\x1b[0m";
    char *lines[] = {line1, line2, line3};

    wcwidth_sgr_propagate(lines, 3);
    ASSERT_STREQ("\x1b[31mred\x1b[0m", lines[0]);
    ASSERT_STREQ("\x1b[31m\x1b[0m", lines[1]);
    ASSERT_STREQ("\x1b[31mtext\x1b[0m", lines[2]);
}

int
main(void)
{
    RUN_TEST(parse_bold);
    RUN_TEST(parse_dim);
    RUN_TEST(parse_italic);
    RUN_TEST(parse_underline);
    RUN_TEST(parse_blink);
    RUN_TEST(parse_rapid_blink);
    RUN_TEST(parse_inverse);
    RUN_TEST(parse_hidden);
    RUN_TEST(parse_strikethrough);
    RUN_TEST(parse_double_underline);

    RUN_TEST(parse_italic_off);
    RUN_TEST(parse_inverse_off);
    RUN_TEST(parse_hidden_off);
    RUN_TEST(parse_strikethrough_off);
    RUN_TEST(parse_bold_dim_off);
    RUN_TEST(parse_underline_off);
    RUN_TEST(parse_blink_off);

    RUN_TEST(parse_fg_standard);
    RUN_TEST(parse_bg_standard);
    RUN_TEST(parse_fg_bright);
    RUN_TEST(parse_bg_bright);
    RUN_TEST(parse_fg_256_semicolon);
    RUN_TEST(parse_bg_256_semicolon);
    RUN_TEST(parse_fg_rgb_semicolon);
    RUN_TEST(parse_bg_rgb_semicolon);

    RUN_TEST(parse_fg_256_colon);
    RUN_TEST(parse_bg_256_colon);
    RUN_TEST(parse_fg_rgb_colon_empty_cs);
    RUN_TEST(parse_bg_rgb_colon_empty_cs);
    RUN_TEST(parse_fg_rgb_colon_with_cs);
    RUN_TEST(parse_mixed_colon_and_semicolon);

    RUN_TEST(parse_fg_default);
    RUN_TEST(parse_bg_default);

    RUN_TEST(parse_compound);
    RUN_TEST(parse_reset);
    RUN_TEST(parse_empty_is_reset);
    RUN_TEST(parse_empty_in_compound);

    RUN_TEST(color_override);

    RUN_TEST(malformed_extended_fg_missing_n);
    RUN_TEST(malformed_extended_fg_missing_rgb);
    RUN_TEST(malformed_extended_bg_missing_n);
    RUN_TEST(malformed_extended_bg_missing_rgb);
    RUN_TEST(malformed_bad_mode);
    RUN_TEST(malformed_unknown_code);
    RUN_TEST(malformed_colon_unknown_base);
    RUN_TEST(malformed_mixed_semicolon_colon_edge);
    RUN_TEST(malformed_extended_with_colon_tuple_as_mode);
    RUN_TEST(malformed_extended_rgb_with_colon_tuple_as_b);

    RUN_TEST(is_active_default);
    RUN_TEST(is_active_with_attr);
    RUN_TEST(is_active_with_color);

    RUN_TEST(to_escape_default);
    RUN_TEST(to_escape_bold);
    RUN_TEST(to_escape_rapid_blink);
    RUN_TEST(to_escape_double_underline);
    RUN_TEST(to_escape_fg_standard);
    RUN_TEST(to_escape_fg_256);
    RUN_TEST(to_escape_fg_rgb);
    RUN_TEST(to_escape_compound);
    RUN_TEST(to_escape_with_bg);

    RUN_TEST(propagate_empty);
    RUN_TEST(propagate_no_sgr);
    RUN_TEST(propagate_single_line);
    RUN_TEST(propagate_two_lines);
    RUN_TEST(propagate_reset_between);
    RUN_TEST(propagate_empty_line);

    return test_summary();
}
