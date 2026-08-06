#include "test_common.h"
#include "wcwidth/clip.h"
#include "wcwidth/width.h"
#include <string.h>
#include <stdlib.h>

static void
cs_assert(const char *text, size_t start, size_t end, const char *expected)
{
    size_t len = 0;
    int error = WCWIDTH_ERROR_NONE;
    char fillchar = ' ';
    char *last = clip_u8(text, strlen(text), start, end, WCWIDTH_PARSE, 8, 1, NULL, true, -1,
                         &fillchar, 1, &len, &error);
    ASSERT_NOT_NULL(last);
    ASSERT_EQ(WCWIDTH_ERROR_NONE, error);
    ASSERT_EQ(len, strlen(last));
    ASSERT_STREQ(expected, last);
    free(last);
}

TEST(basic)
{
    cs_assert("hello", 0, 5, "hello");
    cs_assert("hello", 1, 4, "ell");
    cs_assert("hello", 5, 3, "");  /* zero-width window */
    cs_assert("hi", 0, 100, "hi"); /* out of bounds */
    cs_assert("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 0, 4, "\xe4\xb8\xad\xe6\x96\x87");
    cs_assert("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97", 0, 3, "\xe4\xb8\xad "); /* fillchar */
    cs_assert("\x1b[31mred\x1b[0m", 0, 3, "\x1b[31mred\x1b[0m");
}

TEST(clip_u32_basic)
{
    size_t len;
    int error = WCWIDTH_ERROR_NONE;
    char fillchar = ' ';
    const uint32_t cps[] = {'h', 'e', 'l', 'l', 'o'};
    const uint32_t expect[] = {'e', 'l', 'l'};
    uint32_t *result =
        clip_u32(cps, 5, 1, 4, WCWIDTH_PARSE, 8, 1, NULL, true, -1, &fillchar, 1, &len, &error);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ(WCWIDTH_ERROR_NONE, error);
    ASSERT_EQ((size_t) 3, len);
    ASSERT_EQ(0, memcmp(expect, result, sizeof(expect)));
    free(result);

    /* U+4E2D U+6587: 4 display cells; partial grapheme gets fillchar */
    {
        const uint32_t zwhw[] = {0x4E2D, 0x6587};
        const uint32_t exp2[] = {0x4E2D, ' '};

        result = clip_u32(zwhw, 2, 0, 3, WCWIDTH_PARSE, 8, 1, NULL, true, -1, &fillchar, 1, &len,
                          &error);
        ASSERT_NOT_NULL(result);
        ASSERT_EQ(WCWIDTH_ERROR_NONE, error);
        ASSERT_EQ((size_t) 2, len);
        ASSERT_EQ(0, memcmp(exp2, result, sizeof(exp2)));
        free(result);
    }
}

int
main(void)
{
    RUN_TEST(basic);
    RUN_TEST(clip_u32_basic);
    return test_summary();
}
