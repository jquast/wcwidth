#include "test_common.h"
#include "wcwidth/align.h"
#include <stdlib.h>
#include <string.h>

static char *
call_ljust(const char *text, size_t dest_width, char fillchar, size_t *out_len)
{
    return ljust_u8(text, strlen(text), dest_width, fillchar, WCWIDTH_PARSE, 1, NULL, out_len);
}

static char *
call_rjust(const char *text, size_t dest_width, char fillchar, size_t *out_len)
{
    return rjust_u8(text, strlen(text), dest_width, fillchar, WCWIDTH_PARSE, 1, NULL, out_len);
}

static char *
call_center(const char *text, size_t dest_width, char fillchar, size_t *out_len)
{
    return center_u8(text, strlen(text), dest_width, fillchar, WCWIDTH_PARSE, 1, NULL, out_len);
}

TEST(ljust_ascii)
{
    size_t len;
    char *result = call_ljust("hi", 5, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("hi   ", result);
    free(result);
}

TEST(ljust_wide)
{
    /* U+4E2D ("中") = 3 UTF-8 bytes, display width 2 */
    size_t len;
    char *result = call_ljust("\xe4\xb8\xad", 4, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("\xe4\xb8\xad  ", result);
    free(result);
}

TEST(ljust_already_wider)
{
    size_t len;
    char *result = call_ljust("hello", 3, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("hello", result);
    free(result);
}

TEST(ljust_empty_text)
{
    size_t len;
    char *result = call_ljust("", 5, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("     ", result);
    free(result);
}

TEST(rjust_ascii)
{
    size_t len;
    char *result = call_rjust("hi", 5, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("   hi", result);
    free(result);
}

TEST(rjust_wide)
{
    /* U+4E2D ("中") = 3 UTF-8 bytes, display width 2 */
    size_t len;
    char *result = call_rjust("\xe4\xb8\xad", 4, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("  \xe4\xb8\xad", result);
    free(result);
}

TEST(rjust_already_wider)
{
    size_t len;
    char *result = call_rjust("hello", 3, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("hello", result);
    free(result);
}

TEST(rjust_empty_text)
{
    size_t len;
    char *result = call_rjust("", 5, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("     ", result);
    free(result);
}

TEST(center_even_width)
{
    /* dest_width=6, text_width=2, total_padding=4, left=2, right=2 */
    size_t len;
    char *result = call_center("hi", 6, ' ', &len);
    ASSERT_EQ(6, len);
    ASSERT_STREQ("  hi  ", result);
    free(result);
}

TEST(center_odd_width_dest_even)
{
    /*
     * dest_width=5, text_width=2, total_padding=3
     * left = 3/2 + (3 & 5 & 1) = 1 + (3 & 1) = 1 + 1 = 2
     * right = 3 - 2 = 1
     */
    size_t len;
    char *result = call_center("hi", 5, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("  hi ", result);
    free(result);
}

TEST(center_odd_width_dest_odd)
{
    /*
     * dest_width=3, text_width=1, total_padding=2
     * left = 2/2 + (2 & 3 & 1) = 1 + (2 & 1) = 1 + 0 = 1
     * right = 2 - 1 = 1
     */
    size_t len;
    char *result = call_center("a", 3, ' ', &len);
    ASSERT_EQ(3, len);
    ASSERT_STREQ(" a ", result);
    free(result);
}

TEST(center_two_char_dest_odd)
{
    /*
     * dest_width=3, text_width=2, total_padding=1
     * left = 1/2 + (1 & 3 & 1) = 0 + (1 & 1) = 1
     * right = 1 - 1 = 0
     */
    size_t len;
    char *result = call_center("ab", 3, ' ', &len);
    ASSERT_EQ(3, len);
    ASSERT_STREQ(" ab", result);
    free(result);
}

TEST(center_already_wider)
{
    size_t len;
    char *result = call_center("hello", 3, ' ', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("hello", result);
    free(result);
}

TEST(center_empty_text)
{
    size_t len;
    char *result = call_center("", 4, ' ', &len);
    ASSERT_EQ(4, len);
    ASSERT_STREQ("    ", result);
    free(result);
}

TEST(ljust_custom_fill)
{
    size_t len;
    char *result = call_ljust("hi", 5, '.', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("hi...", result);
    free(result);
}

TEST(rjust_custom_fill)
{
    size_t len;
    char *result = call_rjust("hi", 5, '.', &len);
    ASSERT_EQ(5, len);
    ASSERT_STREQ("...hi", result);
    free(result);
}

TEST(center_custom_fill)
{
    size_t len;
    char *result = call_center("hi", 6, '-', &len);
    ASSERT_EQ(6, len);
    ASSERT_STREQ("--hi--", result);
    free(result);
}

TEST(ljust_sgr)
{
    /* "\x1b[31mhi\x1b[0m" has display width 2, text_len 11 */
    size_t len;
    char *result = call_ljust("\x1b[31mhi\x1b[0m", 5, ' ', &len);
    ASSERT_EQ(14, len);
    ASSERT_STREQ("\x1b[31mhi\x1b[0m   ", result);
    free(result);
}

TEST(rjust_sgr)
{
    size_t len;
    char *result = call_rjust("\x1b[31mhi\x1b[0m", 5, ' ', &len);
    ASSERT_EQ(14, len);
    ASSERT_STREQ("   \x1b[31mhi\x1b[0m", result);
    free(result);
}

TEST(center_sgr)
{
    size_t len;
    char *result = call_center("\x1b[31mhi\x1b[0m", 6, ' ', &len);
    ASSERT_EQ(15, len);
    ASSERT_STREQ("  \x1b[31mhi\x1b[0m  ", result);
    free(result);
}

TEST(ljust_null_out_len)
{
    char *result = ljust_u8("hi", 2, 5, ' ', WCWIDTH_PARSE, 1, NULL, NULL);
    ASSERT_TRUE(result != NULL);
    ASSERT_STREQ("hi   ", result);
    free(result);
}

TEST(rjust_null_out_len)
{
    char *result = rjust_u8("hi", 2, 5, ' ', WCWIDTH_PARSE, 1, NULL, NULL);
    ASSERT_TRUE(result != NULL);
    ASSERT_STREQ("   hi", result);
    free(result);
}

TEST(center_null_out_len)
{
    char *result = center_u8("hi", 2, 6, ' ', WCWIDTH_PARSE, 1, NULL, NULL);
    ASSERT_TRUE(result != NULL);
    ASSERT_STREQ("  hi  ", result);
    free(result);
}

int
main(void)
{
    RUN_TEST(ljust_ascii);
    RUN_TEST(ljust_wide);
    RUN_TEST(ljust_already_wider);
    RUN_TEST(ljust_empty_text);
    RUN_TEST(ljust_custom_fill);
    RUN_TEST(ljust_sgr);
    RUN_TEST(ljust_null_out_len);

    RUN_TEST(rjust_ascii);
    RUN_TEST(rjust_wide);
    RUN_TEST(rjust_already_wider);
    RUN_TEST(rjust_empty_text);
    RUN_TEST(rjust_custom_fill);
    RUN_TEST(rjust_sgr);
    RUN_TEST(rjust_null_out_len);

    RUN_TEST(center_even_width);
    RUN_TEST(center_odd_width_dest_even);
    RUN_TEST(center_odd_width_dest_odd);
    RUN_TEST(center_two_char_dest_odd);
    RUN_TEST(center_already_wider);
    RUN_TEST(center_empty_text);
    RUN_TEST(center_custom_fill);
    RUN_TEST(center_sgr);
    RUN_TEST(center_null_out_len);

    return test_summary();
}
