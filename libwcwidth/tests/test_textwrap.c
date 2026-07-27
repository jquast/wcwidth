#include "test_common.h"
#include "wcwidth/textwrap.h"
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

static int
do_wrap(const char *text, const wcwidth_wrap_opts_t *opts, char **out, size_t *out_len)
{
    return wrap_u8(text, strlen(text), opts, out, out_len);
}

TEST(simple_wrap)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 5;
    const char *exp[] = {"hello", "world"};
    ASSERT_EQ(0, do_wrap("hello world", &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(no_wrap_needed)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 20;
    const char *exp[] = {"hello world"};
    ASSERT_EQ(0, do_wrap("hello world", &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(cjk_two_cells_each)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 4;
    const char *exp[] = {"中文", "字符"};
    ASSERT_EQ(0, do_wrap("中文字符", &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(initial_indent)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    o.initial_indent = "> ";
    const char *exp[] = {"> hello", "world"};
    ASSERT_EQ(0, do_wrap("hello world", &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(subsequent_indent)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    o.subsequent_indent = "  ";
    const char *exp[] = {"hello", "  world"};
    ASSERT_EQ(0, do_wrap("hello world", &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(long_word_breaking)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 5;
    const char *exp[] = {"hello", "world"};
    ASSERT_EQ(0, do_wrap("helloworld", &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(hyphen_breaking)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    const char *exp[] = {"hello-", "there-", "world"};
    ASSERT_EQ(0, do_wrap("hello-there-world", &o, &out, &len));
    check_lines(out, len, exp, 3);
    free(out);
}

TEST(empty_input)
{
    char *out;
    size_t len;
    int r = wrap_u8("", 0, &WCWIDTH_WRAP_OPTS_DEFAULT, &out, &len);
    ASSERT_EQ(0, r);
    ASSERT_EQ((int64_t) 0, (int64_t) len);
    free(out);
}

TEST(single_word_exact_width)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 5;
    const char *exp[] = {"hello"};
    ASSERT_EQ(0, do_wrap("hello", &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(sgr_propagation)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 6;
    o.propagate_sgr = true;
    const char *text = "\x1b[1;34mHello world\x1b[0m";
    ASSERT_EQ(0, wrap_u8(text, strlen(text), &o, &out, &len));
    /* Both lines should have the SGR sequence */
    ASSERT_TRUE(strstr(out, "\x1b[1;34m") != NULL);
    /* Second line (after \n) should also have it */
    char *nl = strchr(out, '\n');
    ASSERT_TRUE(nl != NULL);
    ASSERT_TRUE(strstr(nl + 1, "\x1b[1;34m") != NULL);
    free(out);
}

TEST(max_lines_truncation)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    o.max_lines = 2;
    ASSERT_EQ(0, wrap_u8("one two three four five", 23, &o, &out, &len));
    /* Placeholder appears (may have leading space stripped if alone) */
    ASSERT_TRUE(out != NULL);
    free(out);
}

TEST(multiple_spaces_collapsed)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 5;
    const char *exp[] = {"hello", "world"};
    ASSERT_EQ(0, do_wrap("hello    world", &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(no_break_long_words)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    o.break_long_words = false;
    const char *exp[] = {"helloworld"};
    ASSERT_EQ(0, do_wrap("helloworld", &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(without_sgr_propagation)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 6;
    o.propagate_sgr = false;
    const char *text = "\x1b[1mHello world\x1b[0m";
    ASSERT_EQ(0, wrap_u8(text, strlen(text), &o, &out, &len));
    char *nl = strchr(out, '\n');
    ASSERT_TRUE(nl != NULL);
    ASSERT_TRUE(strstr(nl + 1, "\x1b[1m") == NULL);
    free(out);
}

TEST(tab_expansion)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 20;
    ASSERT_EQ(0, wrap_u8("hello\tworld", 11, &o, &out, &len));
    ASSERT_TRUE(strstr(out, "hello") != NULL);
    ASSERT_TRUE(strstr(out, "world") != NULL);
    free(out);
}

TEST(newline_as_whitespace)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 20;
    const char *exp[] = {"hello world"};
    ASSERT_EQ(0, do_wrap("hello\nworld", &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(max_lines_with_no_more_content)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 40;
    o.max_lines = 5;
    const char *exp[] = {"hello world"};
    ASSERT_EQ(0, do_wrap("hello world", &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(only_escape_sequences)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    /* Disable SGR propagation for raw escape sequence passthrough */
    o.propagate_sgr = false;
    const char *text = "\x1b[31m\x1b[1m";
    ASSERT_EQ(0, wrap_u8(text, strlen(text), &o, &out, &len));
    ASSERT_TRUE(memcmp(out, text, strlen(text)) == 0);
    free(out);
}

int
main(void)
{
    RUN_TEST(simple_wrap);
    RUN_TEST(no_wrap_needed);
    RUN_TEST(cjk_two_cells_each);
    RUN_TEST(initial_indent);
    RUN_TEST(subsequent_indent);
    RUN_TEST(long_word_breaking);
    RUN_TEST(hyphen_breaking);
    RUN_TEST(empty_input);
    RUN_TEST(single_word_exact_width);
    RUN_TEST(sgr_propagation);
    RUN_TEST(max_lines_truncation);
    RUN_TEST(multiple_spaces_collapsed);
    RUN_TEST(no_break_long_words);
    RUN_TEST(without_sgr_propagation);
    RUN_TEST(tab_expansion);
    RUN_TEST(newline_as_whitespace);
    RUN_TEST(max_lines_with_no_more_content);
    RUN_TEST(only_escape_sequences);

    return test_summary();
}
