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
    ASSERT_EQ(0, wcwidth_wrap_u8("hello world", 11, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 4;
    const char *exp2[] = {"\xe4\xb8\xad\xe6\x96\x87", "\xe5\xad\x97\xe7\xac\xa6"};
    ASSERT_EQ(
        0, wcwidth_wrap_u8("\xe4\xb8\xad\xe6\x96\x87\xe5\xad\x97\xe7\xac\xa6", 12, &o, &out, &len));
    check_lines(out, len, exp2, 2);
    free(out);

    ASSERT_EQ(0, wcwidth_wrap_u8("", 0, &WCWIDTH_WRAP_OPTS_DEFAULT, &out, &len));
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
    ASSERT_EQ(0, wcwidth_wrap_u8_text("line one\n\nline two", 18, &o, &out, &len));
    check_lines(out, len, exp, 3);
    free(out);
}

TEST(wrap_embedded_nul)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 5;
    ASSERT_EQ(0, wcwidth_wrap_u8("ab\x00"
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
    ASSERT_EQ(0, wcwidth_wrap_u8("h\xc3\xa9llo w\xc3\xb6rld", 13, &o, &out8, &len8));
    ASSERT_EQ(0, wcwidth_wrap_u32(cps, 11, &o, &out32, &len32));
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
    ASSERT_EQ(0, wcwidth_wrap_u8_text("line one\n\nline two", 18, &o, &out8, &len8));
    ASSERT_EQ(0, wcwidth_wrap_u32_text(cps, 18, &o, &out32, &len32));
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

/*
 * tabsize <= 0 is documented to pass tabs through unchanged; disabling
 * replace_whitespace isolates that from the whitespace-normalization pass.
 */
TEST(wrap_tabsize_zero)
{
    char *out = NULL;
    size_t len = 0;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 3;
    o.tabsize = 0;
    o.replace_whitespace = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("a\tb", 3, &o, &out, &len));
    ASSERT_EQ(3, len);
    ASSERT_EQ(0, memcmp(out, "a\tb", 3));
    free(out);
}

/*
 * A run of UTF-8 continuation bytes reaching the start of the buffer must
 * not read before it while backing up to find a lead byte.
 */
TEST(wrap_lone_continuation_bytes)
{
    static const char *const inputs[] = {"\xBF", "\x80", "\xBF\xBF\xBF"};
    size_t i;

    for (i = 0; i < sizeof(inputs) / sizeof(inputs[0]); i++) {
        char *out = NULL;
        size_t len = 0;
        wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
        size_t in_len = strlen(inputs[i]);

        o.width = 3;
        int rv = wcwidth_wrap_u8(inputs[i], in_len, &o, &out, &len);
        ASSERT_EQ(0, rv);
        free(out);
    }
}

TEST(wrap_unknown_escape)
{
    static const char *const inputs[] = {"\x1b", "\x1bZ", "\x1b[", "a\x1bZb"};
    size_t i;

    for (i = 0; i < sizeof(inputs) / sizeof(inputs[0]); i++) {
        char *out = NULL;
        size_t len = 0;
        wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
        size_t in_len = strlen(inputs[i]);

        o.width = 2;
        ASSERT_EQ(0, wcwidth_wrap_u8(inputs[i], in_len, &o, &out, &len));
        ASSERT_EQ((int64_t) in_len, (int64_t) len);
        ASSERT_EQ(0, memcmp(out, inputs[i], in_len));
        free(out);
    }
}

TEST(wrap_sequence_only_whitespace_line)
{
    char *out = NULL;
    size_t len = 0;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"a"};

    o.width = 1;
    ASSERT_EQ(0, wcwidth_wrap_u8("a \x1b  \x1b", 6, &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(wrap_trailing_escape_after_dropped_space)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"a\x1b[0m"};

    o.width = 5;
    ASSERT_EQ(0, wcwidth_wrap_u8("a  \x1b[0m", 7, &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(wrap_escape_appended_to_last_chunk)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"a b\x1b[0m"};

    o.width = 5;
    ASSERT_EQ(0, wcwidth_wrap_u8("a b  \x1b[0m", 9, &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(wrap_escape_only_tail_dropped)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"\x1b[31ma"};

    o.width = 2;
    ASSERT_EQ(0, wcwidth_wrap_u8("\x1b[31ma  \x1b[0m", 12, &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(wrap_whitespace_only_with_escapes)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 4;
    ASSERT_EQ(0, wcwidth_wrap_u8("   \x1b[31m   \x1b[0m", 15, &o, &out, &len));
    ASSERT_EQ((int64_t) 0, (int64_t) len);
    free(out);
}

TEST(wrap_escape_moves_to_next_line)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"a", "\x1b[0mb"};

    o.width = 3;
    ASSERT_EQ(0, wcwidth_wrap_u8("a  \x1b[0m b", 9, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(wrap_sgr_long_word)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"\x1b[31mabc", "def\x1b[0m"};

    o.width = 3;
    ASSERT_EQ(0, wcwidth_wrap_u8("\x1b[31mabcdef\x1b[0m", 16, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(wrap_trailing_word_with_escape)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"aa", "\x1b[31mbb"};

    o.width = 3;
    ASSERT_EQ(0, wcwidth_wrap_u8("aa \x1b[31mbb", 10, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(wrap_wide_first_grapheme)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 1;
    ASSERT_EQ(0, wcwidth_wrap_u8("\xe4\xb8\xad", 3, &o, &out, &len));
    ASSERT_EQ((int64_t) 3, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "\xe4\xb8\xad", 3));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 1;
    ASSERT_EQ(0, wcwidth_wrap_u8("\x1b[31m\xe4\xb8\xad", 8, &o, &out, &len));
    ASSERT_EQ(0, memcmp(out, "\x1b[31m\xe4\xb8\xad", 8));
    free(out);
}

TEST(wrap_unicode_whitespace)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 2;
    ASSERT_EQ(0, wcwidth_wrap_u8("ab\xc2\xa0", 4, &o, &out, &len));
    ASSERT_EQ((int64_t) 2, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "ab", 2));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 2;
    ASSERT_EQ(0, wcwidth_wrap_u8("ab\xe2\x80\x83", 5, &o, &out, &len));
    ASSERT_EQ((int64_t) 2, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "ab", 2));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 2;
    ASSERT_EQ(0, wcwidth_wrap_u8("ab\xe1\x9a\x80", 5, &o, &out, &len));
    ASSERT_EQ((int64_t) 2, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "ab", 2));
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("ab\xe2\x80\x80", 5, &o, &out, &len));
    ASSERT_EQ((int64_t) 2, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "ab", 2));
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("ab\xe2\x80\x8a", 5, &o, &out, &len));
    ASSERT_EQ((int64_t) 2, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "ab", 2));
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("ab\xe3\x80\x80", 5, &o, &out, &len));
    ASSERT_EQ((int64_t) 2, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "ab", 2));
    free(out);

    ASSERT_EQ(0, wcwidth_wrap_u8("a\xc2", 2, &o, &out, &len));
    ASSERT_EQ((int64_t) 2, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "a\xc2", 2));
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("a\xe2\x80", 3, &o, &out, &len));
    ASSERT_EQ((int64_t) 3, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "a\xe2\x80", 3));
    free(out);
}

TEST(wrap_expands_tabs_and_resets_at_newline)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 20;
    ASSERT_EQ(0, wcwidth_wrap_u8("a\tb", 3, &o, &out, &len));
    ASSERT_EQ((int64_t) 9, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "a       b", 9));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 5;
    ASSERT_EQ(0, wcwidth_wrap_u8("a\nb", 3, &o, &out, &len));
    ASSERT_EQ((int64_t) 3, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "a b", 3));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    ASSERT_EQ(0, wcwidth_wrap_u8("a\vb\fc", 5, &o, &out, &len));
    ASSERT_EQ((int64_t) 5, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "a b c", 5));
    free(out);

    ASSERT_EQ(0, wcwidth_wrap_u8("a\rb", 3, &o, &out, &len));
    ASSERT_EQ((int64_t) 3, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "a b", 3));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    o.expand_tabs = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("a\tb", 3, &o, &out, &len));
    ASSERT_EQ((int64_t) 3, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "a b", 3));
    free(out);
}

TEST(wrap_multibyte_word_split)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"\xc3\xa9", "\xc3\xa9", "\xc3\xa9"};

    o.width = 1;
    ASSERT_EQ(0, wcwidth_wrap_u8("\xc3\xa9\xc3\xa9\xc3\xa9", 6, &o, &out, &len));
    check_lines(out, len, exp, 3);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    o.replace_whitespace = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("\xe2ZZ", 3, &o, &out, &len));
    ASSERT_EQ((int64_t) 3, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "\xe2ZZ", 3));
    free(out);
}

TEST(wrap_whitespace_only)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    o.width = 1;
    ASSERT_EQ(0, wcwidth_wrap_u8("  ", 2, &o, &out, &len));
    ASSERT_EQ((int64_t) 0, (int64_t) len);
    free(out);

    ASSERT_EQ(0, wcwidth_wrap_u8_text("   ", 3, &WCWIDTH_WRAP_OPTS_DEFAULT, &out, &len));
    ASSERT_EQ((int64_t) 0, (int64_t) len);
    free(out);
}

TEST(wrap_text_wraps_segment)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"aa", "bb", "cc"};

    o.width = 2;
    ASSERT_EQ(0, wcwidth_wrap_u8_text("aa bb\ncc", 8, &o, &out, &len));
    check_lines(out, len, exp, 3);
    free(out);
}

TEST(wrap_u32_encode_and_errors)
{
    uint32_t long_text[200];
    uint32_t *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    size_t i;

    for (i = 0; i < sizeof(long_text) / sizeof(long_text[0]); i++)
        long_text[i] = 0x4E2D;
    o.width = 40;
    ASSERT_EQ(0, wcwidth_wrap_u32(long_text, 200, &o, &out, &len));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 1;
    o.max_lines = 1;
    o.placeholder = "xxxx";
    ASSERT_EQ(-1, wcwidth_wrap_u32(long_text, 200, &o, &out, &len));
}

TEST(wrap_max_lines_trims_previous_line)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"abc."};

    o.width = 5;
    o.max_lines = 2;
    o.placeholder = ".";
    ASSERT_EQ(0, wcwidth_wrap_u8("abc  \x1b[0m ddddd eeeee", 21, &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);
}

TEST(wrap_max_lines_placeholder)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"aa bb [...]"};

    o.width = 11;
    o.max_lines = 1;
    ASSERT_EQ(0, wcwidth_wrap_u8("aa bb cccccccc", 14, &o, &out, &len));
    check_lines(out, len, exp, 1);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 4;
    o.max_lines = 1;
    ASSERT_EQ(-2, wcwidth_wrap_u8("aaaa bbbb", 9, &o, &out, &len));

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 6;
    o.max_lines = 1;
    ASSERT_EQ(0, wcwidth_wrap_u8("aa bbbb", 7, &o, &out, &len));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 6;
    o.max_lines = 2;
    ASSERT_EQ(0, wcwidth_wrap_u8("aa bb cc dd ee", 14, &o, &out, &len));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 11;
    o.max_lines = 2;
    ASSERT_EQ(0, wcwidth_wrap_u8("aa bb ccccccccc dd", 18, &o, &out, &len));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 3;
    o.expand_tabs = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("a\tb", 3, &o, &out, &len));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 2;
    o.break_long_words = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("abcdef", 6, &o, &out, &len));
    free(out);
}

TEST(wrap_max_lines_placeholder_escapes)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"\x1b[31maa bb", "[...]"};
    const char *exp_escape_tail[] = {"aa bb \x1b[31m ", "[...]"};

    o.width = 5;
    o.max_lines = 2;
    ASSERT_EQ(0, wcwidth_wrap_u8("\x1b[31maa bb cc dd ee ff\x1b[0m", 28, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 7;
    o.max_lines = 2;
    o.drop_whitespace = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("aa bb \x1b[31m cc dd ee", 20, &o, &out, &len));
    check_lines(out, len, exp_escape_tail, 2);
    free(out);
}

TEST(wrap_drops_leading_whitespace_only_line)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"h", "e", "l", "l", "o"};
    const char *exp_ws[] = {" ", "h", "e", "l", "l", "o"};

    o.width = 1;
    ASSERT_EQ(0, wcwidth_wrap_u8(" hello", 6, &o, &out, &len));
    check_lines(out, len, exp, 5);
    free(out);

    o.width = 1;
    o.drop_whitespace = false;
    ASSERT_EQ(0, wcwidth_wrap_u8(" hello", 6, &o, &out, &len));
    check_lines(out, len, exp_ws, 6);
    free(out);
}

TEST(wrap_preserves_color_after_dropped_leading_space)
{
    const char *inputs[] = {"\x1b[31m a\x1b[0m", "\x1b[31m a-b\x1b[0m", " \x1b[31ma-b\x1b[0m"};
    const char *one[] = {"\x1b[31ma\x1b[0m"};
    const char *three[] = {"\x1b[31ma", "-", "b\x1b[0m"};
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    size_t i;
    o.width = 1;
    for (i = 0; i < 3; i++) {
        char *out;
        size_t len;
        ASSERT_EQ(0, wcwidth_wrap_u8(inputs[i], strlen(inputs[i]), &o, &out, &len));
        check_lines(out, len, i == 0 ? one : three, i == 0 ? 1 : 3);
        free(out);
    }
}

TEST(wrap_uax14_break_opportunities)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *zwsp[] = {"foo\xe2\x80\x8b", "bar"};
    const char *ideographic[] = {"aaa", "bbb"};

    o.width = 4;
    ASSERT_EQ(0, wcwidth_wrap_u8("foo\xe2\x80\x8b"
                                 "bar",
                                 9, &o, &out, &len));
    check_lines(out, len, zwsp, 2);
    free(out);

    ASSERT_EQ(0, wcwidth_wrap_u8("aaa\xe3\x80\x80"
                                 "bbb",
                                 9, &o, &out, &len));
    check_lines(out, len, ideographic, 2);
    free(out);
}

TEST(wrap_uax14_no_break)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *nbsp[] = {"aaa\xc2\xa0"
                          "bbb"};
    const char *word_joiner[] = {"aaa\xe2\x81\xa0"
                                 "bbb"};

    o.width = 4;
    o.break_long_words = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("aaa\xc2\xa0"
                                 "bbb",
                                 8, &o, &out, &len));
    check_lines(out, len, nbsp, 1);
    free(out);

    ASSERT_EQ(0, wcwidth_wrap_u8("aaa\xe2\x81\xa0"
                                 "bbb",
                                 9, &o, &out, &len));
    check_lines(out, len, word_joiner, 1);
    free(out);
}

TEST(wrap_soft_hyphen)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"aaa\xc2\xad", "bbb"};

    o.width = 4;
    ASSERT_EQ(0, wcwidth_wrap_u8("aaa\xc2\xad"
                                 "bbb",
                                 8, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(wrap_break_on_hyphens)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *hyphen_break[] = {"a-", "bcdef"};
    const char *plain_break[] = {"a-bcd", "ef"};
    const char *leading_break[] = {"-ab", "cde", "f"};
    const char *sgr_break[] = {"\x1b[31m-abc", "def\x1b[0m"};

    o.width = 5;
    ASSERT_EQ(0, wcwidth_wrap_u8("a-bcdef", 7, &o, &out, &len));
    check_lines(out, len, hyphen_break, 2);
    free(out);

    o.break_on_hyphens = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("a-bcdef", 7, &o, &out, &len));
    check_lines(out, len, plain_break, 2);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 5;
    o.line_break = WCWIDTH_LINE_BREAK_ASCII;
    ASSERT_EQ(0, wcwidth_wrap_u8("a-bcdef", 7, &o, &out, &len));
    check_lines(out, len, hyphen_break, 2);
    free(out);

    o.break_on_hyphens = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("a-bcdef", 7, &o, &out, &len));
    check_lines(out, len, plain_break, 2);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 3;
    ASSERT_EQ(0, wcwidth_wrap_u8("-abcdef", 7, &o, &out, &len));
    check_lines(out, len, leading_break, 3);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 4;
    ASSERT_EQ(0, wcwidth_wrap_u8("\x1b[31m-abcdef\x1b[0m", 16, &o, &out, &len));
    check_lines(out, len, sgr_break, 2);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 3;
    {
        const char *unknown[] = {"\x1bZ-ab", "cde", "f"};

        ASSERT_EQ(0, wcwidth_wrap_u8("\x1bZ-abcdef", 10, &o, &out, &len));
        check_lines(out, len, unknown, 3);
        free(out);
    }
}

/* An empty line leaves the line buffer NULL; zero-length copies must not touch it. */
TEST(wrap_empty_line)
{
    char *out = NULL;
    size_t len = 0;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *text = " \n ";

    o.width = 1;
    o.break_long_words = false;
    o.replace_whitespace = false;
    ASSERT_EQ(0, wcwidth_wrap_u8(text, 3, &o, &out, &len));
    ASSERT_EQ((int64_t) 0, (int64_t) len);
    free(out);

    o.drop_whitespace = false;
    ASSERT_EQ(0, wcwidth_wrap_u8(text, 3, &o, &out, &len));
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 1;
    o.break_long_words = false;
    o.replace_whitespace = false;
    o.max_lines = 1;
    ASSERT_EQ(-2, wcwidth_wrap_u8(text, 3, &o, &out, &len));
    free(out);
}

TEST(wrap_mandatory_breaks)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"a", "b"};

    o.width = 10;
    o.replace_whitespace = false;
    ASSERT_EQ(0, wcwidth_wrap_u8("a\nb", 3, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);

    ASSERT_EQ(0, wcwidth_wrap_u8("a\r\nb", 4, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    const char *collapsed[] = {"a b"};
    ASSERT_EQ(0, wcwidth_wrap_u8("a\xc2\x85"
                                 "b",
                                 4, &o, &out, &len));
    check_lines(out, len, collapsed, 1);
    free(out);

    ASSERT_EQ(0, wcwidth_wrap_u8("a\xe2\x80\xa8"
                                 "b",
                                 5, &o, &out, &len));
    check_lines(out, len, collapsed, 1);
    free(out);

    ASSERT_EQ(0, wcwidth_wrap_u8("a\xe2\x80\xa9"
                                 "b",
                                 5, &o, &out, &len));
    check_lines(out, len, collapsed, 1);
    free(out);

    o = WCWIDTH_WRAP_OPTS_DEFAULT;
    o.width = 10;
    o.replace_whitespace = false;
    {
        const char *joined[] = {"ab"};

        ASSERT_EQ(0, wcwidth_wrap_u8("\nab", 3, &o, &out, &len));
        check_lines(out, len, joined, 1);
        free(out);
        ASSERT_EQ(0, wcwidth_wrap_u8("\r\nab", 4, &o, &out, &len));
        check_lines(out, len, joined, 1);
        free(out);
    }
    ASSERT_EQ(0, wcwidth_wrap_u8("a\vb", 3, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("a\fb", 3, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("a\rb", 3, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("a\xc2\x85"
                                 "b",
                                 4, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("a\xe2\x80\xa8"
                                 "b",
                                 5, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("a\xe2\x80\xa9"
                                 "b",
                                 5, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("\n", 1, &o, &out, &len));
    ASSERT_EQ((int64_t) 0, (int64_t) len);
    free(out);
    ASSERT_EQ(0, wcwidth_wrap_u8("\r\n", 2, &o, &out, &len));
    ASSERT_EQ((int64_t) 0, (int64_t) len);
    free(out);
}

TEST(wrap_ascii_mode)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"foo\xe2\x80\x8b"
                         "b",
                         "ar"};

    o.width = 4;
    o.line_break = WCWIDTH_LINE_BREAK_ASCII;
    ASSERT_EQ(0, wcwidth_wrap_u8("foo\xe2\x80\x8b"
                                 "bar",
                                 9, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(wrap_ascii_mode_spaces_and_escapes)
{
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;
    const char *exp[] = {"aa bb", "\x1b[31mcc"};

    o.width = 5;
    o.line_break = WCWIDTH_LINE_BREAK_ASCII;
    ASSERT_EQ(0, wcwidth_wrap_u8("aa bb \x1b[31mcc", 13, &o, &out, &len));
    check_lines(out, len, exp, 2);
    free(out);
}

TEST(wrap_drops_every_python_whitespace)
{
    /* Tab, information separators, NEL, NBSP, ogham, en quad..hair space,
     * narrow no-break, medium math, and ideographic space. */
    const char *ws = "\x09\x1c\xc2\x85\xc2\xa0\xe1\x9a\x80\xe2\x80\x80\xe2\x80\xa8"
                     "\xe2\x80\xa9\xe2\x80\xaf\xe2\x81\x9f\xe3\x80\x80";
    char text[128];
    char *out;
    size_t len;
    wcwidth_wrap_opts_t o = WCWIDTH_WRAP_OPTS_DEFAULT;

    snprintf(text, sizeof text, "x%s", ws);
    o.width = 80;
    ASSERT_EQ(0, wcwidth_wrap_u8(text, strlen(text), &o, &out, &len));
    ASSERT_EQ((int64_t) 'x', (int64_t) out[len - 1]);
    free(out);
}

int
main(void)
{
    RUN_TEST(wrap_preserves_color_after_dropped_leading_space);
    RUN_TEST(wrap_basic);
    RUN_TEST(wrap_text_basic);
    RUN_TEST(wrap_embedded_nul);
    RUN_TEST(wrap_u32_parity);
    RUN_TEST(wrap_text_u32_parity);
    RUN_TEST(wrap_lines_u8);
    RUN_TEST(wrap_tabsize_zero);
    RUN_TEST(wrap_lone_continuation_bytes);
    RUN_TEST(wrap_unknown_escape);
    RUN_TEST(wrap_sequence_only_whitespace_line);
    RUN_TEST(wrap_trailing_escape_after_dropped_space);
    RUN_TEST(wrap_escape_appended_to_last_chunk);
    RUN_TEST(wrap_escape_only_tail_dropped);
    RUN_TEST(wrap_whitespace_only_with_escapes);
    RUN_TEST(wrap_escape_moves_to_next_line);
    RUN_TEST(wrap_max_lines_placeholder);
    RUN_TEST(wrap_max_lines_placeholder_escapes);
    RUN_TEST(wrap_drops_leading_whitespace_only_line);
    RUN_TEST(wrap_sgr_long_word);
    RUN_TEST(wrap_trailing_word_with_escape);
    RUN_TEST(wrap_wide_first_grapheme);
    RUN_TEST(wrap_unicode_whitespace);
    RUN_TEST(wrap_expands_tabs_and_resets_at_newline);
    RUN_TEST(wrap_multibyte_word_split);
    RUN_TEST(wrap_whitespace_only);
    RUN_TEST(wrap_text_wraps_segment);
    RUN_TEST(wrap_u32_encode_and_errors);
    RUN_TEST(wrap_max_lines_trims_previous_line);
    RUN_TEST(wrap_uax14_break_opportunities);
    RUN_TEST(wrap_uax14_no_break);
    RUN_TEST(wrap_soft_hyphen);
    RUN_TEST(wrap_break_on_hyphens);
    RUN_TEST(wrap_empty_line);
    RUN_TEST(wrap_mandatory_breaks);
    RUN_TEST(wrap_ascii_mode);
    RUN_TEST(wrap_ascii_mode_spaces_and_escapes);
    RUN_TEST(wrap_drops_every_python_whitespace);
    return test_summary();
}
