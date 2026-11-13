#include "test_common.h"
#include "wcwidth/textwrap.h"

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

static long alloc_calls;
static long fail_at;

static bool
should_fail(void)
{
    alloc_calls++;
    return fail_at > 0 && alloc_calls == fail_at;
}

void *
wcwidth_test_malloc(size_t n)
{
    return should_fail() ? NULL : malloc(n);
}

void *
wcwidth_test_realloc(void *p, size_t n)
{
    return should_fail() ? NULL : realloc(p, n);
}

void *
wcwidth_test_calloc(size_t n, size_t size)
{
    return should_fail() ? NULL : calloc(n, size);
}

static void
sweep(void (*fn)(void))
{
    long total;
    long k;

    alloc_calls = 0;
    fail_at = 0;
    fn();
    total = alloc_calls;

    for (k = 1; k <= total; k++) {
        alloc_calls = 0;
        fail_at = k;
        fn();
    }
    fail_at = 0;
    alloc_calls = 0;
}

static const char long_word[] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

static void
sc_wrap_lines_offsets(void)
{
    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    char *out = NULL;
    size_t *offsets = NULL;
    size_t len = 0;
    size_t count = 0;

    opts.width = 5;
    wcwidth_wrap_lines_u8("aa bb cc dd ee", 14, &opts, &out, &len, &offsets, &count);
    free(out);
    free(offsets);
}

static void
sc_wrap_grows_lines(void)
{
    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    char *out = NULL;
    size_t len = 0;

    opts.width = 1;
    wcwidth_wrap_u8(long_word, sizeof(long_word) - 1, &opts, &out, &len);
    free(out);
}

static void
sc_wrap_uax14(void)
{
    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    char *out = NULL;
    size_t len = 0;
    const char *text = "ab \xe2\x80\xa8"
                       " cd \x1b[31mef\x1b[0m";

    opts.width = 4;
    opts.replace_whitespace = false;
    wcwidth_wrap_u8(text, strlen(text), &opts, &out, &len);
    free(out);

    out = NULL;
    len = 0;
    wcwidth_wrap_u8("\x1bZ", 2, &opts, &out, &len);
    free(out);
}

TEST(wrap_lines_offsets_baseline)
{
    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    char *out = NULL;
    size_t *offsets = NULL;
    size_t len = 0;
    size_t count = 0;
    int rc;

    opts.width = 5;
    rc = wcwidth_wrap_lines_u8("aa bb cc dd ee", 14, &opts, &out, &len, &offsets, &count);
    ASSERT_EQ(0, rc);
    ASSERT_NOT_NULL(out);
    ASSERT_NOT_NULL(offsets);
    ASSERT_EQ(3, count);
    ASSERT_EQ(0, offsets[0]);
    ASSERT_EQ(6, offsets[1]);
    ASSERT_EQ(12, offsets[2]);
    free(out);
    free(offsets);
}

TEST(wrap_grows_lines_baseline)
{
    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    char *out = NULL;
    size_t len = 0;
    int rc;

    opts.width = 1;
    rc = wcwidth_wrap_u8(long_word, sizeof(long_word) - 1, &opts, &out, &len);
    ASSERT_EQ(0, rc);
    ASSERT_NOT_NULL(out);
    ASSERT_EQ(sizeof(long_word) - 1 + sizeof(long_word) - 2, len);
    free(out);
}

int
main(void)
{
    RUN_TEST(wrap_lines_offsets_baseline);
    RUN_TEST(wrap_grows_lines_baseline);
    sweep(sc_wrap_lines_offsets);
    sweep(sc_wrap_grows_lines);
    sweep(sc_wrap_uax14);
    return test_summary();
}
