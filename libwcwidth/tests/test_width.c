#include "test_common.h"
#include "wcwidth/width.h"
#include <string.h>

static int
w_parse(const char *text)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    return width_u8(text, (size_t) -1, WCWIDTH_PARSE, &opts, &error);
}

static int
w_ignore(const char *text)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    return width_u8(text, (size_t) -1, WCWIDTH_IGNORE, &opts, &error);
}

TEST(u8_parse_basic)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;

    ASSERT_EQ(5, w_parse("hello"));
    ASSERT_EQ(3, w_parse("\x1b[31mred\x1b[0m"));
    ASSERT_EQ(11, w_parse("abc\tdef"));
    ASSERT_EQ(3, w_parse("123\b4"));
    ASSERT_EQ(5, w_parse("hello\rworld"));
    ASSERT_EQ(10, w_parse("\x1b[10Gx"));
    /* C-only: NULL input, zero length, embedded NUL */
    ASSERT_EQ(0, width_u8(NULL, 0, WCWIDTH_PARSE, &opts, &error));
    ASSERT_EQ(0, width_u8("hello", 0, WCWIDTH_PARSE, &opts, &error));
    ASSERT_EQ(3, width_u8("a\0bc", 4, WCWIDTH_PARSE, &opts, &error));
    /* ZWJ family with a resolved terminal reaches the u8 cluster scan. */
    opts.term_program = "kitty";
    ASSERT_EQ(2,
              width_u8("\xF0\x9F\x91\xA8\xE2\x80\x8D\xF0\x9F\x91\xA9\xE2\x80\x8D\xF0\x9F\x91\xA7",
                       (size_t) 18, WCWIDTH_PARSE, &opts, &error));
}

TEST(u8_ignore)
{
    ASSERT_EQ(3, w_ignore("\x1b[31mred\x1b[0m"));
    ASSERT_EQ(0, w_ignore("\t"));
    ASSERT_EQ(4, w_ignore("123\b4"));
}

TEST(u8_strict)
{
    /* strict mode routes to the Python implementation */
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    int result = width_u8("\x1b[2J", (size_t) -1, WCWIDTH_STRICT, &opts, &error);

    ASSERT_EQ(-1, result);
    ASSERT_TRUE(error != 0);
}

TEST(u32_basic)
{
    uint32_t text[] = {0x1B, '[', '3', '1', 'm', 'r', 'e', 'd', 0x1B, '[', '0', 'm'};
    int error = 0;

    ASSERT_EQ(3, width_u32(text, 12, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_EQ(0, error);
    ASSERT_EQ(0, width_u32(NULL, 0, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
}

int
main(void)
{
    RUN_TEST(u8_parse_basic);
    RUN_TEST(u8_ignore);
    RUN_TEST(u8_strict);
    RUN_TEST(u32_basic);
    return test_summary();
}
