#include "test_common.h"
#include "wcwidth/align.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>

/* Options for the common case: default everything but width and fill. */
static wcwidth_align_opts_t
opts_of(size_t dest_width, const char *fillchar, size_t fillchar_len)
{
    wcwidth_align_opts_t opts = WCWIDTH_ALIGN_OPTS_DEFAULT;

    opts.dest_width = dest_width;
    opts.fillchar = fillchar;
    opts.fillchar_len = fillchar_len;
    return opts;
}

static char *
call_ljust(const char *text, size_t dest_width, char fillchar, size_t *out_len)
{
    int error = WCWIDTH_ERROR_NONE;
    wcwidth_align_opts_t opts = opts_of(dest_width, &fillchar, 1);
    return wcwidth_ljust_u8(text, strlen(text), WCWIDTH_PARSE, &opts, out_len, &error);
}

static char *
call_rjust(const char *text, size_t dest_width, char fillchar, size_t *out_len)
{
    int error = WCWIDTH_ERROR_NONE;
    wcwidth_align_opts_t opts = opts_of(dest_width, &fillchar, 1);
    return wcwidth_rjust_u8(text, strlen(text), WCWIDTH_PARSE, &opts, out_len, &error);
}

static char *
call_center(const char *text, size_t dest_width, char fillchar, size_t *out_len)
{
    int error = WCWIDTH_ERROR_NONE;
    wcwidth_align_opts_t opts = opts_of(dest_width, &fillchar, 1);
    return wcwidth_center_u8(text, strlen(text), WCWIDTH_PARSE, &opts, out_len, &error);
}

TEST(ljust_basic)
{
    wcwidth_align_opts_t opts1 = opts_of(5, " ", 1);
    wcwidth_align_opts_t opts2 = opts_of(5, " ", 1);
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    char *result = call_ljust("hi", 5, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("hi   ", result);
    free(result);

    /* U+4E2D ("中") = 3 UTF-8 bytes, display width 2 */
    result = call_ljust("\xe4\xb8\xad", 4, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("\xe4\xb8\xad  ", result);
    free(result);

    /* C-only: NULL out_len is allowed */
    result = wcwidth_ljust_u8("hi", 2, WCWIDTH_PARSE, &opts1, NULL, &error);
    ASSERT_STREQ("hi   ", result);
    free(result);

    /* C-only: NULL error is allowed */
    result = wcwidth_ljust_u8("hi", 2, WCWIDTH_PARSE, &opts2, NULL, NULL);
    ASSERT_STREQ("hi   ", result);
    free(result);
}

TEST(rjust_basic)
{
    wcwidth_align_opts_t opts1 = opts_of(5, " ", 1);
    wcwidth_align_opts_t opts2 = opts_of(5, " ", 1);
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    char *result = call_rjust("hi", 5, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("   hi", result);
    free(result);

    result = call_rjust("\xe4\xb8\xad", 4, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("  \xe4\xb8\xad", result);
    free(result);

    result = wcwidth_rjust_u8("hi", 2, WCWIDTH_PARSE, &opts1, NULL, &error);
    ASSERT_STREQ("   hi", result);
    free(result);

    result = wcwidth_rjust_u8("hi", 2, WCWIDTH_PARSE, &opts2, NULL, NULL);
    ASSERT_STREQ("   hi", result);
    free(result);
}

TEST(center_basic)
{
    wcwidth_align_opts_t opts1 = opts_of(6, " ", 1);
    wcwidth_align_opts_t opts2 = opts_of(6, " ", 1);
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    char *result = call_center("hi", 6, ' ', &len);
    ASSERT_EQ(6, len);
    ASSERT_STREQ("  hi  ", result);
    free(result);

    result = call_center("\xe4\xb8\xad", 4, '-', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("-\xe4\xb8\xad-", result);
    free(result);

    result = wcwidth_center_u8("hi", 2, WCWIDTH_PARSE, &opts1, NULL, &error);
    ASSERT_STREQ("  hi  ", result);
    free(result);

    result = wcwidth_center_u8("hi", 2, WCWIDTH_PARSE, &opts2, NULL, NULL);
    ASSERT_STREQ("  hi  ", result);
    free(result);
}

TEST(ljust_u32_basic)
{
    wcwidth_align_opts_t opts1 = opts_of(5, " ", 1);
    wcwidth_align_opts_t opts2 = opts_of(4, " ", 1);
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    const uint32_t cps[] = {'h', 'i'};
    const uint32_t expect[] = {'h', 'i', ' ', ' ', ' '};
    uint32_t *result = wcwidth_ljust_u32(cps, 2, WCWIDTH_PARSE, &opts1, &len, &error);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ((size_t) 5, len);
    ASSERT_EQ(0, memcmp(expect, result, sizeof(expect)));
    free(result);

    /* U+4E2D ("中") = display width 2, padded to 4 cells with 2 spaces */
    {
        const uint32_t zhong[] = {0x4E2D};
        const uint32_t exp2[] = {0x4E2D, ' ', ' '};

        result = wcwidth_ljust_u32(zhong, 1, WCWIDTH_PARSE, &opts2, &len, &error);
        ASSERT_NOT_NULL(result);
        ASSERT_EQ((size_t) 3, len);
        ASSERT_EQ(0, memcmp(exp2, result, sizeof(exp2)));
        free(result);
    }
}

TEST(rjust_u32_basic)
{
    wcwidth_align_opts_t opts1 = opts_of(5, " ", 1);
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    const uint32_t cps[] = {'h', 'i'};
    const uint32_t expect[] = {' ', ' ', ' ', 'h', 'i'};
    uint32_t *result = wcwidth_rjust_u32(cps, 2, WCWIDTH_PARSE, &opts1, &len, &error);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ((size_t) 5, len);
    ASSERT_EQ(0, memcmp(expect, result, sizeof(expect)));
    free(result);
}

TEST(center_u32_basic)
{
    wcwidth_align_opts_t opts1 = opts_of(6, " ", 1);
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    const uint32_t cps[] = {'h', 'i'};
    const uint32_t expect[] = {' ', ' ', 'h', 'i', ' ', ' '};
    uint32_t *result = wcwidth_center_u32(cps, 2, WCWIDTH_PARSE, &opts1, &len, &error);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ((size_t) 6, len);
    ASSERT_EQ(0, memcmp(expect, result, sizeof(expect)));
    free(result);
}

/*
 * dest_width * fillchar_len must be refused when it exceeds SIZE_MAX, for
 * both the single-byte and multi-byte fillchar paths (padding_cells *
 * fillchar_len is the multiplication in question).
 */
TEST(ljust_huge_dest_width)
{
    wcwidth_align_opts_t opts1 = opts_of((size_t) -1 - 2, "\xf0\x9f\x98\x80", 4);
    int error = WCWIDTH_ERROR_NONE;
    size_t out_len = 12345;
    char *result = wcwidth_ljust_u8("hi", 2, WCWIDTH_PARSE, &opts1, &out_len, &error);
    ASSERT_NULL(result);
}

TEST(rjust_huge_dest_width_multibyte_fill)
{
    size_t huge = (SIZE_MAX / 3) + 2;
    wcwidth_align_opts_t opts1 = opts_of(huge, "\xe4\xbd\xa0", 3);
    int error = WCWIDTH_ERROR_NONE;
    size_t out_len = 12345;
    char *result = wcwidth_rjust_u8("hi", 2, WCWIDTH_PARSE, &opts1, &out_len, &error);
    ASSERT_NULL(result);
}

TEST(center_huge_dest_width)
{
    wcwidth_align_opts_t opts1 = opts_of((size_t) -1 - 2, "\xf0\x9f\x98\x80", 4);
    int error = WCWIDTH_ERROR_NONE;
    size_t out_len = 12345;
    char *result = wcwidth_center_u8("hi", 2, WCWIDTH_PARSE, &opts1, &out_len, &error);
    ASSERT_NULL(result);
}

/*
 * "\x01" (SOH) is an illegal C0 control character under
 * control_codes='strict': WCWIDTH_ERROR_ILLEGAL_CTRL.
 */
TEST(align_control_codes_strict)
{
    wcwidth_align_opts_t opts1 = opts_of(10, " ", 1);
    wcwidth_align_opts_t opts2 = opts_of(10, " ", 1);
    wcwidth_align_opts_t opts3 = opts_of(10, " ", 1);
    int error;
    char *result;

    error = WCWIDTH_ERROR_NONE;
    result = wcwidth_ljust_u8("\x01x", 2, WCWIDTH_STRICT, &opts1, NULL, &error);
    ASSERT_NULL(result);
    ASSERT_EQ(WCWIDTH_ERROR_ILLEGAL_CTRL, error);

    error = WCWIDTH_ERROR_NONE;
    result = wcwidth_rjust_u8("\x01x", 2, WCWIDTH_STRICT, &opts2, NULL, &error);
    ASSERT_NULL(result);
    ASSERT_EQ(WCWIDTH_ERROR_ILLEGAL_CTRL, error);

    error = WCWIDTH_ERROR_NONE;
    result = wcwidth_center_u8("\x01x", 2, WCWIDTH_STRICT, &opts3, NULL, &error);
    ASSERT_NULL(result);
    ASSERT_EQ(WCWIDTH_ERROR_ILLEGAL_CTRL, error);
}

TEST(null_opts_defaults)
{
    uint32_t cps[] = {'h', 'i'};
    size_t len = 0;
    int error = WCWIDTH_ERROR_NONE;
    char *s;
    uint32_t *u;

    s = wcwidth_ljust_u8("hi", 2, WCWIDTH_PARSE, NULL, &len, &error);
    ASSERT_EQ(2, len);
    free(s);
    s = wcwidth_rjust_u8("hi", 2, WCWIDTH_PARSE, NULL, &len, &error);
    ASSERT_EQ(2, len);
    free(s);
    s = wcwidth_center_u8("hi", 2, WCWIDTH_PARSE, NULL, &len, &error);
    ASSERT_EQ(2, len);
    free(s);
    u = wcwidth_ljust_u32(cps, 2, WCWIDTH_PARSE, NULL, &len, &error);
    ASSERT_EQ(2, len);
    free(u);
    u = wcwidth_rjust_u32(cps, 2, WCWIDTH_PARSE, NULL, &len, &error);
    ASSERT_EQ(2, len);
    free(u);
    u = wcwidth_center_u32(cps, 2, WCWIDTH_PARSE, NULL, &len, &error);
    ASSERT_EQ(2, len);
    free(u);
}

int
main(void)
{
    RUN_TEST(ljust_basic);
    RUN_TEST(rjust_basic);
    RUN_TEST(center_basic);
    RUN_TEST(ljust_u32_basic);
    RUN_TEST(rjust_u32_basic);
    RUN_TEST(center_u32_basic);
    RUN_TEST(ljust_huge_dest_width);
    RUN_TEST(rjust_huge_dest_width_multibyte_fill);
    RUN_TEST(center_huge_dest_width);
    RUN_TEST(align_control_codes_strict);
    RUN_TEST(null_opts_defaults);
    return test_summary();
}
