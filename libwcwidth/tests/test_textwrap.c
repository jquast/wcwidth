#include "test_common.h"
#include "wcwidth/textwrap.h"
#include "wcwidth/utf8.h"
#include <string.h>
#include <stdlib.h>

/*
 * Count '\n'-separated lines in output and extract them into an array.
 * Caller must free each returned string and the array.
 */
static size_t
split_lines(char *buf, size_t len, char ***out)
{
    size_t count = 0, cap = 8, i;
    char *start = buf;
    char **lines = malloc(cap * sizeof(char *));
    if (lines == NULL)
        return 0;

    for (i = 0; i <= len; i++) {
        if (i == len || buf[i] == '\n') {
            if (count >= cap) {
                cap *= 2;
                char **nd = realloc(lines, cap * sizeof(char *));
                if (nd == NULL)
                    goto fail;
                lines = nd;
            }
            lines[count] = malloc((size_t) (buf + i - start) + 1);
            if (lines[count] == NULL)
                goto fail;
            memcpy(lines[count], start, (size_t) (buf + i - start));
            lines[count][buf + i - start] = '\0';
            count++;
            start = buf + i + 1;
        }
    }
    *out = lines;
    return count;

fail:
    for (i = 0; i < count; i++)
        free(lines[i]);
    free(lines);
    return 0;
}

static void
free_lines(char **lines, size_t n)
{
    size_t i;
    for (i = 0; i < n; i++)
        free(lines[i]);
    free(lines);
}

static void
check_lines(char *out, size_t out_len, const char **expected, size_t nexpected)
{
    char **lines = NULL;
    size_t nlines = split_lines(out, out_len, &lines);
    size_t i;
    ASSERT_EQ((int64_t) nexpected, (int64_t) nlines);
    for (i = 0; i < nlines; i++) {
        ASSERT_STREQ(expected[i], lines[i]);
    }
    free_lines(lines, nlines);
}

TEST(wrap_basic)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"hello", "world"};

    o.width = 5;
    ASSERT_EQ(0, wrap_u8("hello world", 11, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 4;
    const char *exp2[] = {"\xe4\xb8\xad\xe6\x96\x87", "\xe5\xad\x97\xe7\xac\xa6"};
    ASSERT_EQ(0, wrap_u8("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97\xe7\xac\xa6", 12, &o, &out, &len));
    check_lines(out, len, exp2, 2);
    free(out);

    ASSERT_EQ(0, wrap_u8("", 0, &WCWIDTH_WRAP_OPTS_DEFAULT, &out, &len));
    ASSERT_EQ((int64_t) 0, (int64_t) len);
    free(out);
}

TEST(wrap_text_basic)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"line one", "", "line two"};

    o.width = 40;
    ASSERT_EQ(0, wrap_u8_text("line one\n\nline two", 18, &o, &out, &len));
    check_lines(out, len, exp, 3);
    free(out);
}

TEST(wrap_embedded_nul)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 5;
    ASSERT_EQ(0, wrap_u8("ab\x00"
                         "cd ef",
                         8, &o, &out, &len));
    ASSERT_EQ((int64_t) 8, (int64_t) len);
    ASSERT_EQ(0, memcmp(out,
                        "ab\x00"
                        "cd\nef",
                        8));
    free(out);
}

TEST(wrap_u32_parity)
{
    char *out8;
    size_t len8;
    uint32_t stack[64];
    size_t count;
    const uint32_t *expect;
    uint32_t *out32;
    size_t len32;
    const uint32_t cps[] = {'h', 0x00E9, 'l', 'l', 'o', ' ', 'w', 0x00F6, 'r', 'l', 'd'};
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 5;
    ASSERT_EQ(0, wrap_u8("h\xc3\xa9llo w\xc3\xb6rld", 13, &o, &out8, &len8));
    ASSERT_EQ(0, wrap_u32(cps, 11, &o, &out32, &len32));
    expect = wcwidth_decode_u32(out8, len8, stack, 64, &count);
    ASSERT_EQ((int64_t) count, (int64_t) len32);
    ASSERT_EQ(0, memcmp(expect, out32, count * sizeof(uint32_t)));
    free(out8);
    free(out32);
}

TEST(wrap_text_u32_parity)
{
    char *out8;
    size_t len8;
    uint32_t stack[64];
    size_t count;
    const uint32_t *expect;
    uint32_t *out32;
    size_t len32;
    const uint32_t cps[] = {'l',  'i', 'n', 'e', ' ', 'o', 'n', 'e', '\n',
                            '\n', 'l', 'i', 'n', 'e', ' ', 't', 'w', 'o'};
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 40;
    ASSERT_EQ(0, wrap_u8_text("line one\n\nline two", 18, &o, &out8, &len8));
    ASSERT_EQ(0, wrap_u32_text(cps, 18, &o, &out32, &len32));
    expect = wcwidth_decode_u32(out8, len8, stack, 64, &count);
    ASSERT_EQ((int64_t) count, (int64_t) len32);
    ASSERT_EQ(0, memcmp(expect, out32, count * sizeof(uint32_t)));
    free(out8);
    free(out32);
}

TEST(wrap_lines_u8)
{
    char *out;
    size_t len;
    size_t *offsets;
    size_t count;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 7;
    o.max_lines = 1;
    o.placeholder = "\n[..]";
    ASSERT_EQ(0, wcwidth_wrap_lines_u8("one two three four", 18, &o, &out, &len, &offsets, &count));
    ASSERT_EQ((int64_t) 1, (int64_t) count);
    /* a line may itself contain '\n' from the placeholder */
    ASSERT_EQ((int64_t) 8, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "one\n[..]", 8));
    ASSERT_EQ((size_t) 0, offsets[0]);
    free(out);
    free(offsets);

    /* placeholder that cannot fit */
    o.placeholder = "xxxxxxxx";
    ASSERT_EQ(-2,
              wcwidth_wrap_lines_u8("one two three four", 18, &o, &out, &len, &offsets, &count));

    /* empty input yields no lines */
    ASSERT_EQ(0, wcwidth_wrap_lines_u8("", 0, &o, &out, &len, &offsets, &count));
    ASSERT_EQ((size_t) 0, count);
    free(out);
}

int
main(void)
{
    RUN_TEST(wrap_basic);
    RUN_TEST(wrap_text_basic);
    RUN_TEST(wrap_embedded_nul);
    RUN_TEST(wrap_u32_parity);
    RUN_TEST(wrap_text_u32_parity);
    RUN_TEST(wrap_lines_u8);
    return test_summary();
}
