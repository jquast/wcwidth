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
    return wcwidth_width_u8(text, strlen(text), WCWIDTH_PARSE, &opts, &error);
}

static int
w_ignore(const char *text)
{
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;
    return wcwidth_width_u8(text, strlen(text), WCWIDTH_IGNORE, &opts, &error);
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
    ASSERT_EQ(0, wcwidth_width_u8(NULL, 0, WCWIDTH_PARSE, &opts, &error));
    ASSERT_EQ(0, wcwidth_width_u8("hello", 0, WCWIDTH_PARSE, &opts, &error));
    ASSERT_EQ(3, wcwidth_width_u8("a\0bc", 4, WCWIDTH_PARSE, &opts, &error));
    /* ZWJ family with a resolved terminal reaches the u8 cluster scan. */
    opts.term_program = "kitty";
    ASSERT_EQ(2, wcwidth_width_u8(
                     "\xF0\x9F\x91\xA8\xE2\x80\x8D\xF0\x9F\x91\xA9\xE2\x80\x8D\xF0\x9F\x91\xA7",
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
    int result = wcwidth_width_u8("\x1b[2J", 4, WCWIDTH_STRICT, &opts, &error);

    ASSERT_EQ(-1, result);
    ASSERT_TRUE(error != 0);
}

TEST(u32_basic)
{
    uint32_t text[] = {0x1B, '[', '3', '1', 'm', 'r', 'e', 'd', 0x1B, '[', '0', 'm'};
    int error = 0;

    ASSERT_EQ(3, wcwidth_width_u32(text, 12, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_EQ(0, error);
    ASSERT_EQ(0, wcwidth_width_u32(NULL, 0, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
}

TEST(u32_ignore)
{
    uint32_t sgr[] = {0x1B, '[', '3', '1', 'm', 'r', 'e', 'd', 0x1B, '[', '0', 'm'};
    uint32_t tab[] = {0x09};
    uint32_t bs[] = {'1', '2', '3', 0x08, '4'};
    uint32_t osc66[] = {0x1B, ']', '6', '6', ';', 's', '=', '2', ';', 'A', 'B', 0x07};
    int error = 0;

    ASSERT_EQ(3, wcwidth_width_u32(sgr, 12, WCWIDTH_IGNORE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_EQ(0, wcwidth_width_u32(tab, 1, WCWIDTH_IGNORE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_EQ(4, wcwidth_width_u32(bs, 5, WCWIDTH_IGNORE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_EQ(2, wcwidth_width_u32(osc66, 12, WCWIDTH_IGNORE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
}

/*
 * wcwidth_width_u8() and wcwidth_width_u32() must agree on identical text, in every control
 * mode.  They are separate implementations (the codepoint path exists to
 * avoid an encode round-trip), so nothing but a test keeps them in step.
 */
TEST(u8_u32_agree)
{
    static const char *const corpus[] = {
        /* well formed */
        "hello",
        "\xe4\xb8\xad\xe6\x96\x87",
        "caf\xc3\xa9",
        "\x1b[31mred\x1b[0m",
        "\x1b]66;w=2;XY\x07",
        "a\tb",
        "\x1b[10Cx",
        "\x1b[5Dx",
        "\x1b[2J",
        /* malformed: unterminated, truncated, stray introducers */
        "X\x1b[31",
        "X\x1b]66;w=2;",
        "X\x1b_apc",
        "X\x1b",
        "X\x1b(",
        "\x1b]0;a\x1b"
        "b\x07Y",
        "\x1b_apc\x1b"
        "X\x07z",
        "\x1bPdcs\x1b"
        "Q\x07z",
        "\x9b"
        "31mY",
        "\x1b^pm\x1b"
        "Y\x07z",
        /* long enough to cross FAST_PATH_MIN_LEN, trailing unterminated CSI */
        "\xe4\xb8\xad"
        "2\xc2\x9b==\x1b^\x0b\x1b^\x1b[31m;\x1b[31",
        "b\xe4\xb8\xad"
        "2\xc2\x9b==\x1b^\x0b\x1b^\x1b[31m;\x1b[31",
        /* mixed non-ASCII inside an OSC 66 payload */
        "\x1b]66;w=2;\xe4\xb8\xad\x07tail",
        "pre\x1b]66;s=2;\xc3\xa9\x1b\\post",
        /* controls *inside* an OSC 66 payload: kept text, dropped controls */
        "\x1b]66;w=2;=\x0b\x1b\\\x1b",
        "\n;b\x1b]66;w=2;\r\x08\x1b\\=\x1b(6",
        "\x1bP\x1b]66;w=2;\x08\x1b\\\x1b]66;w=2;\r\x1b)\xc2\x9b\x0b",
        "\xe2\x9d\xa4\xef\xb8\x8f\xe4\xb8\xad\xef\xb8\x8e\xf0\x9f\x87\xa6\xf0\x9f\x87\xa7"
        "\xf0\x9f\x91\x8d\xf0\x9f\x8f\xbb\xe0\xa4\x95\xe0\xa5\x8d\xe0\xa4\xb7\xe0\xa4\x83",
        "a\x7f"
        "b",
        "\x80\x84\x9c\x9f",
        "\xf0\x9f\x91\xa8\xe2\x80\x8d\xef\xb8\x8f\xe0\xa4\x95\xe0\xa5\x8d\xe0\xa5\x8d\xe0\xa4\xb7",
        "a\x1a"
        "b\x1e",
        /* terminal override and grapheme-cluster arms */
        "\xe0\xa4\x95\xe0\xa5\x8d\xe2\x80\x8d\xe0\xa4\xb7",
        "\xf0\x9f\x91\xa8\xe2\x80\x8d",
        "\xf0\x9f\x91\xa8\xe2\x80\x8d\xf0\x9f\x91\xa6",
        "\xe2\x8c\x9a\xef\xb8\x8e",
        "\xf0\x9f\x8f\xbb",
        "\xe2\x98\x9d",
        "\xc2\xad",
        "\xe0\xa4\x98\xe0\xa5\x8d\xe0\xa4\x82\xe0\xa4\xa4",
        "\xe1\x80\x80\xe1\x80\xb1X",
        "\xe1\x80\x80\xe1\x80\xb1",
        /* a 30+ codepoint cluster overflows the 32-entry lookup cap */
        "a\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz"
        "\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz"
        "\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dzc",
        "a\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz"
        "\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz"
        "\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz\xe0\xa5\x8dz",
    };
    const size_t count = sizeof(corpus) / sizeof(corpus[0]);
    const wcwidth_control_mode_t modes[] = {WCWIDTH_PARSE, WCWIDTH_IGNORE, WCWIDTH_STRICT};
    static const char *const terms[] = {"kitty", "alacritty"};
    size_t i, m, t;

    for (i = 0; i < count; i++) {
        const char *text = corpus[i];
        size_t byte_len = strlen(text);
        uint32_t stack[256];
        size_t cp_count = 0;
        uint32_t *cps = wcwidth_decode_u32(text, byte_len, stack, 256, &cp_count);

        ASSERT_NOT_NULL(cps);
        for (m = 0; m < 3; m++) {
            int e8 = 0, e32 = 0;
            int w8 = wcwidth_width_u8(text, byte_len, modes[m], &WCWIDTH_WIDTH_OPTS_DEFAULT, &e8);
            int w32 = wcwidth_width_u32(cps, cp_count, modes[m], &WCWIDTH_WIDTH_OPTS_DEFAULT, &e32);

            ASSERT_EQ(w8, w32);
            ASSERT_EQ(e8, e32);
        }
        for (t = 0; t < sizeof(terms) / sizeof(terms[0]); t++) {
            wcwidth_width_opts_t k = WCWIDTH_WIDTH_OPTS_DEFAULT;
            k.term_program = terms[t];
            for (m = 0; m < 3; m++) {
                int e8t = 0, e32t = 0;
                int w8t = wcwidth_width_u8(text, byte_len, modes[m], &k, &e8t);
                int w32t = wcwidth_width_u32(cps, cp_count, modes[m], &k, &e32t);

                ASSERT_EQ(w8t, w32t);
                ASSERT_EQ(e8t, e32t);
            }
        }
        if (cps != stack) {
            free(cps);
        }
    }
}

/*
 * A CSI cursor-movement parameter far larger than any real column must
 * saturate at INT_MAX.
 */
TEST(csi_huge_param_saturates)
{
    int error = WCWIDTH_ERROR_NONE;
    static const char *const inputs[] = {
        "\x1b[100000000000000000000C",
        "\x1b[999999999999999999999999999999D",
        "\x1b[99999999999999999999G",
    };
    size_t i;

    for (i = 0; i < sizeof(inputs) / sizeof(inputs[0]); i++) {
        int w = wcwidth_width_u8(inputs[i], strlen(inputs[i]), WCWIDTH_PARSE,
                                 &WCWIDTH_WIDTH_OPTS_DEFAULT, &error);
        ASSERT_TRUE(w >= 0);
    }
}

TEST(u8_ignore_long)
{
    static char big[1100];
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    int error = 0;

    memset(big, 'a', sizeof(big));
    memcpy(big, "\x1b[31m", 5);
    ASSERT_EQ(1095, wcwidth_width_u8(big, sizeof(big), WCWIDTH_IGNORE, &opts, &error));
    opts.term_program = "kitty";
    ASSERT_EQ(1095, wcwidth_width_u8(big, sizeof(big), WCWIDTH_IGNORE, &opts, &error));
}

TEST(u32_illegal_ctrls)
{
    uint32_t text[] = {0x1A, 0x1C, 0x7F, 0x9F, 0xC2};
    int error = 0;

    ASSERT_EQ(1, wcwidth_width_u32(text, 5, WCWIDTH_PARSE, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_EQ(-1, wcwidth_width_u32(text, 5, WCWIDTH_STRICT, &WCWIDTH_WIDTH_OPTS_DEFAULT, &error));
    ASSERT_TRUE(error != 0);
}

int
main(void)
{
    RUN_TEST(u8_parse_basic);
    RUN_TEST(u8_ignore);
    RUN_TEST(u8_ignore_long);
    RUN_TEST(u8_strict);
    RUN_TEST(u32_basic);
    RUN_TEST(u32_ignore);
    RUN_TEST(u8_u32_agree);
    RUN_TEST(u32_illegal_ctrls);
    RUN_TEST(csi_huge_param_saturates);
    return test_summary();
}
