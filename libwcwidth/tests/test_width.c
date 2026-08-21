#include "test_common.h"
#include "wcwidth/width.h"
#include "wcwidth/utf8.h"
#include <stdlib.h>
#include <string.h>

static int
w_parse(const char *text)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    return width_u8(text, strlen(text), WCWIDTH_PARSE, &opts, &error);
}

static int
w_ignore(const char *text)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    return width_u8(text, strlen(text), WCWIDTH_IGNORE, &opts, &error);
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
    int result = width_u8("\x1b[2J", 4, WCWIDTH_STRICT, &opts, &error);

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

TEST(u32_ignore)
{
    uint32_t sgr[] = {0x1B, '[', '3', '1', 'm', 'r', 'e', 'd', 0x1B, '[', '0', 'm'};
    uint32_t tab[] = {0x09};
    uint32_t bs[] = {'1', '2', '3', 0x08, '4'};
    uint32_t osc66[] = {0x1B, ']', '6', '6', ';', 's', '=', '2', ';', 'A', 'B', 0x07};
    int error = 0;

    ASSERT_EQ(3, width_u32(sgr, 12, WCWIDTH_IGNORE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_EQ(0, width_u32(tab, 1, WCWIDTH_IGNORE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_EQ(4, width_u32(bs, 5, WCWIDTH_IGNORE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_EQ(2, width_u32(osc66, 12, WCWIDTH_IGNORE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
}


/*
 * width_u8() and width_u32() must agree on identical text, in every control
 * mode.  They are separate implementations -- the codepoint path exists to
 * avoid an encode round-trip -- so nothing but a test keeps them in step.
 *
 * A previous divergence here was silent: the codepoint escape stripper
 * disagreed with wcwidth_escape_strip() about where an unterminated CSI ends,
 * so IGNORE mode answered differently on the two paths, and the
 * PARSE->IGNORE downgrade at FAST_PATH_MIN_LEN meant a string one codepoint
 * longer could pick up the wrong answer.
 */
TEST(u8_u32_agree)
{
    static const char *const corpus[] = {
        /* well formed */
        "hello", "\xe4\xb8\xad\xe6\x96\x87", "caf\xc3\xa9",
        "\x1b[31mred\x1b[0m", "\x1b]66;w=2;XY\x07", "a\tb",
        "\x1b[10Cx", "\x1b[5Dx", "\x1b[2J",
        /* malformed: unterminated, truncated, stray introducers */
        "X\x1b[31", "X\x1b]66;w=2;", "X\x1b_apc", "X\x1b", "X\x1b(",
        "\x1b]0;a\x1b" "b\x07Y", "\x1b_apc\x1b" "X\x07z", "\x1bPdcs\x1b" "Q\x07z",
        "\x9b" "31mY", "\x1b^pm\x1b" "Y\x07z",
        /* the exact shape that was wrong before: long enough to cross
         * FAST_PATH_MIN_LEN, with a trailing unterminated CSI */
        "\xe4\xb8\xad" "2\xc2\x9b==\x1b^\x0b\x1b^\x1b[31m;\x1b[31",
        "b\xe4\xb8\xad" "2\xc2\x9b==\x1b^\x0b\x1b^\x1b[31m;\x1b[31",
        /* mixed non-ASCII inside an OSC 66 payload */
        "\x1b]66;w=2;\xe4\xb8\xad\x07tail",
        "pre\x1b]66;s=2;\xc3\xa9\x1b\\post",
        /* controls *inside* an OSC 66 payload: kept text, dropped controls */
        "\x1b]66;w=2;=\x0b\x1b\\\x1b",
        "\n;b\x1b]66;w=2;\r\x08\x1b\\=\x1b(6",
        "\x1bP\x1b]66;w=2;\x08\x1b\\\x1b]66;w=2;\r\x1b)\xc2\x9b\x0b",
    };
    const size_t count = sizeof(corpus) / sizeof(corpus[0]);
    const wcwidth_control_mode_t modes[] = {WCWIDTH_PARSE, WCWIDTH_IGNORE, WCWIDTH_STRICT};
    size_t i, m;

    for (i = 0; i < count; i++) {
        const char *text = corpus[i];
        size_t byte_len = strlen(text);
        uint32_t stack[256];
        size_t cp_count = 0;
        uint32_t *cps = wcwidth_decode_u32(text, byte_len, stack, 256, &cp_count);

        ASSERT_NOT_NULL(cps);
        for (m = 0; m < 3; m++) {
            int e8 = 0, e32 = 0;
            int w8 = width_u8(text, byte_len, modes[m], &WCWIDTH_WIDTH_OPTS_DEFAULT, &e8);
            int w32 = width_u32(cps, cp_count, modes[m], &WCWIDTH_WIDTH_OPTS_DEFAULT, &e32);

            ASSERT_EQ(w8, w32);
            ASSERT_EQ(e8, e32);
        }
        if (cps != stack) {
            free(cps);
        }
    }
}

int
main(void)
{
    RUN_TEST(u8_parse_basic);
    RUN_TEST(u8_ignore);
    RUN_TEST(u8_strict);
    RUN_TEST(u32_basic);
    RUN_TEST(u32_ignore);
    RUN_TEST(u8_u32_agree);
    return test_summary();
}
