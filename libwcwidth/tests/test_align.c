#include "test_common.h"
#include "wcwidth/align.h"
#include <stdlib.h>
#include <string.h>

static char *
call_ljust(const char *text, size_t dest_width, char fillchar, size_t *out_len)
{
    int error = WCWIDTH_ERROR_NONE;
    return ljust_u8(text, strlen(text), dest_width, &fillchar, 1, WCWIDTH_PARSE, 1, NULL, out_len,
                    &error);
}

static char *
call_rjust(const char *text, size_t dest_width, char fillchar, size_t *out_len)
{
    int error = WCWIDTH_ERROR_NONE;
    return rjust_u8(text, strlen(text), dest_width, &fillchar, 1, WCWIDTH_PARSE, 1, NULL, out_len,
                    &error);
}

static char *
call_center(const char *text, size_t dest_width, char fillchar, size_t *out_len)
{
    int error = WCWIDTH_ERROR_NONE;
    return center_u8(text, strlen(text), dest_width, &fillchar, 1, WCWIDTH_PARSE, 1, NULL, out_len,
                     &error);
}

TEST(ljust_basic)
{
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
    result = ljust_u8("hi", 2, 5, " ", 1, WCWIDTH_PARSE, 1, NULL, NULL, &error);
    ASSERT_STREQ("hi   ", result);
    free(result);

    /* C-only: NULL error is allowed */
    result = ljust_u8("hi", 2, 5, " ", 1, WCWIDTH_PARSE, 1, NULL, NULL, NULL);
    ASSERT_STREQ("hi   ", result);
    free(result);
}

TEST(rjust_basic)
{
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

    result = rjust_u8("hi", 2, 5, " ", 1, WCWIDTH_PARSE, 1, NULL, NULL, &error);
    ASSERT_STREQ("   hi", result);
    free(result);

    result = rjust_u8("hi", 2, 5, " ", 1, WCWIDTH_PARSE, 1, NULL, NULL, NULL);
    ASSERT_STREQ("   hi", result);
    free(result);
}

TEST(center_basic)
{
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

    result = center_u8("hi", 2, 6, " ", 1, WCWIDTH_PARSE, 1, NULL, NULL, &error);
    ASSERT_STREQ("  hi  ", result);
    free(result);

    result = center_u8("hi", 2, 6, " ", 1, WCWIDTH_PARSE, 1, NULL, NULL, NULL);
    ASSERT_STREQ("  hi  ", result);
    free(result);
}

TEST(ljust_u32_basic)
{
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    const uint32_t cps[] = {'h', 'i'};
    const uint32_t expect[] = {'h', 'i', ' ', ' ', ' '};
    uint32_t *result = ljust_u32(cps, 2, 5, " ", 1, WCWIDTH_PARSE, 1, NULL, &len, &error);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ((size_t) 5, len);
    ASSERT_EQ(0, memcmp(expect, result, sizeof(expect)));
    free(result);

    /* U+4E2D ("中") = display width 2, padded to 4 cells with 2 spaces */
    {
        const uint32_t zhong[] = {0x4E2D};
        const uint32_t exp2[] = {0x4E2D, ' ', ' '};

        result = ljust_u32(zhong, 1, 4, " ", 1, WCWIDTH_PARSE, 1, NULL, &len, &error);
        ASSERT_NOT_NULL(result);
        ASSERT_EQ((size_t) 3, len);
        ASSERT_EQ(0, memcmp(exp2, result, sizeof(exp2)));
        free(result);
    }
}

TEST(rjust_u32_basic)
{
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    const uint32_t cps[] = {'h', 'i'};
    const uint32_t expect[] = {' ', ' ', ' ', 'h', 'i'};
    uint32_t *result = rjust_u32(cps, 2, 5, " ", 1, WCWIDTH_PARSE, 1, NULL, &len, &error);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ((size_t) 5, len);
    ASSERT_EQ(0, memcmp(expect, result, sizeof(expect)));
    free(result);
}

TEST(center_u32_basic)
{
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    const uint32_t cps[] = {'h', 'i'};
    const uint32_t expect[] = {' ', ' ', 'h', 'i', ' ', ' '};
    uint32_t *result = center_u32(cps, 2, 6, " ", 1, WCWIDTH_PARSE, 1, NULL, &len, &error);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ((size_t) 6, len);
    ASSERT_EQ(0, memcmp(expect, result, sizeof(expect)));
    free(result);
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
    return test_summary();
}
