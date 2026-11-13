#include "test_common.h"
#include "wcwidth/align.h"
#include "wcwidth/clip.h"
#include "wcwidth/escape.h"
#include "wcwidth/grapheme.h"
#include "wcwidth/sgr.h"
#include "wcwidth/textwrap.h"
#include "wcwidth/utf8.h"
#include "wcwidth/wcwidth.h"
#include "wcwidth/width.h"

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
                                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

static uint32_t many_cps[600];

static void
fill_many(void)
{
    size_t i;

    for (i = 0; i < sizeof(many_cps) / sizeof(many_cps[0]); i++)
        many_cps[i] = 0x4E2D;
}

static void
sc_align(void)
{
    char fill = ' ';
    wcwidth_align_opts_t opts = WCWIDTH_ALIGN_OPTS_DEFAULT;
    char *s;

    opts.dest_width = 20;
    opts.fillchar = &fill;
    opts.fillchar_len = 1;
    s = wcwidth_ljust_u8("hi", 2, WCWIDTH_PARSE, &opts, NULL, NULL);
    free(s);
    s = wcwidth_rjust_u8("hi", 2, WCWIDTH_PARSE, &opts, NULL, NULL);
    free(s);
    s = wcwidth_center_u8("hi", 2, WCWIDTH_PARSE, &opts, NULL, NULL);
    free(s);
}

static void
sc_align_u32(void)
{
    char fill = ' ';
    wcwidth_align_opts_t opts = WCWIDTH_ALIGN_OPTS_DEFAULT;
    uint32_t *out;
    size_t len;

    fill_many();
    opts.dest_width = 0;
    opts.fillchar = &fill;
    opts.fillchar_len = 1;
    out = wcwidth_ljust_u32(many_cps, 200, WCWIDTH_PARSE, &opts, &len, NULL);
    free(out);
    out = wcwidth_rjust_u32(many_cps, 200, WCWIDTH_PARSE, &opts, &len, NULL);
    free(out);
    out = wcwidth_center_u32(many_cps, 200, WCWIDTH_PARSE, &opts, &len, NULL);
    free(out);
}

static void
sc_clip(void)
{
    static char escaped[512];
    wcwidth_clip_opts_t opts = WCWIDTH_CLIP_OPTS_DEFAULT;
    char fill = ' ';
    char *s;

    memset(escaped, 'a', sizeof(escaped));
    memcpy(escaped, "\x1b[31m", 5);

    opts.v_start = 0;
    opts.v_end = 3;
    opts.fillchar = &fill;
    opts.fillchar_len = 1;
    s = wcwidth_clip_u8("hello", 5, WCWIDTH_PARSE, &opts, NULL, NULL);
    free(s);
    s = wcwidth_clip_u8("\x1b[31mred\x1b[0m", 12, WCWIDTH_PARSE, &opts, NULL, NULL);
    free(s);
    s = wcwidth_clip_u8("\xe4\xb8\xad"
                        "ab",
                        5, WCWIDTH_PARSE, &opts, NULL, NULL);
    free(s);
    opts.v_end = 400;
    s = wcwidth_clip_u8(escaped, sizeof(escaped), WCWIDTH_PARSE, &opts, NULL, NULL);
    free(s);
}

static void
sc_clip_u32(void)
{
    wcwidth_clip_opts_t opts = WCWIDTH_CLIP_OPTS_DEFAULT;
    uint32_t *out;
    size_t len;

    fill_many();
    opts.v_start = 0;
    opts.v_end = 400;
    out = wcwidth_clip_u32(many_cps, 200, WCWIDTH_PARSE, &opts, &len, NULL);
    free(out);
}

static void
sc_escape(void)
{
    uint32_t *out;
    size_t len;

    fill_many();
    out = wcwidth_escape_strip_u32(many_cps, 300, &len);
    free(out);
}

static void
sc_grapheme(void)
{
    wcwidth_grapheme_iter_t *iter;
    size_t len;

    fill_many();
    iter = wcwidth_grapheme_iter_new("\xe4\xb8\xad"
                                     "a\xcc\x81"
                                     "b",
                                     7);
    if (iter != NULL) {
        wcwidth_grapheme_next(iter, &len);
        wcwidth_grapheme_iter_free(iter);
    }
    iter = wcwidth_grapheme_iter_new_u32(many_cps, 4);
    if (iter != NULL) {
        wcwidth_grapheme_next_u32(iter, &len);
        wcwidth_grapheme_iter_free(iter);
    }
    wcwidth_grapheme_boundary_before("\xe4\xb8\xad"
                                     "a\xcc\x81",
                                     6, 6);
    wcwidth_grapheme_boundary_after("\xe4\xb8\xad"
                                    "a\xcc\x81",
                                    6, 0);
}

static void
sc_sgr(void)
{
    static char params[1200];
    wcwidth_sgr_state_t state = WCWIDTH_SGR_STATE_DEFAULT;
    size_t i;

    for (i = 0; i + 1 < sizeof(params); i++)
        params[i] = (i % 2 == 0) ? '1' : ';';
    wcwidth_sgr_update(&state, params, sizeof(params) - 1);

    memset(params, ';', sizeof(params));
    wcwidth_sgr_update(&state, params, sizeof(params));
}

static void
sc_textwrap(void)
{
    static char tabs[32];
    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    char *out;
    size_t len;
    size_t *offsets;
    size_t count;

    memset(tabs, '\t', sizeof(tabs));

    opts.width = 4;
    wcwidth_wrap_u8("aa bb \x1b[31mcc\x1b[0m dd", 20, &opts, &out, &len);
    free(out);

    opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = 10;
    wcwidth_wrap_u8(long_word, sizeof(long_word) - 1, &opts, &out, &len);
    free(out);

    opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = 10;
    opts.expand_tabs = false;
    wcwidth_wrap_u8(long_word, sizeof(long_word) - 1, &opts, &out, &len);
    free(out);

    opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = 5;
    wcwidth_wrap_u8(tabs, sizeof(tabs), &opts, &out, &len);
    free(out);

    opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    wcwidth_wrap_u8("", 0, &opts, &out, &len);
    free(out);

    opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = 1;
    wcwidth_wrap_u8("\x1b[31m\xe4\xb8\xad", 8, &opts, &out, &len);
    free(out);

    opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = 5;
    opts.max_lines = 2;
    opts.placeholder = ".";
    wcwidth_wrap_lines_u8("abc  \x1b[0m ddddd eeeee", 21, &opts, &out, &len, &offsets, &count);
    free(out);
    free(offsets);

    opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = 1;
    wcwidth_wrap_u8("\x1b[31m a\x1b[0m", 11, &opts, &out, &len);
    free(out);

    opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = 2;
    wcwidth_wrap_u8_text("aa bb\ncc", 8, &opts, &out, &len);
    free(out);

    opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = 10;
    wcwidth_wrap_u8_text(long_word, sizeof(long_word) - 1, &opts, &out, &len);
    free(out);

    wcwidth_wrap_u8_text("   ", 3, &WCWIDTH_WRAP_OPTS_DEFAULT, &out, &len);
    free(out);
}

static void
sc_textwrap_u32(void)
{
    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    uint32_t *out;
    size_t len;

    fill_many();
    opts.width = 20;
    opts.max_lines = 1;
    opts.placeholder = ".";
    wcwidth_wrap_u32(many_cps, 200, &opts, &out, &len);
    free(out);
}

static void
sc_utf8(void)
{
    uint32_t stack[2];
    uint32_t *cps;
    char enc_stack[8];
    char *bytes;
    size_t count;
    size_t len;

    cps = wcwidth_decode_u32("abcdef", 6, stack, 2, &count);
    free(cps);

    fill_many();
    bytes = wcwidth_encode_u32(many_cps, 128, enc_stack, sizeof(enc_stack), &len);
    free(bytes);
}

static void
sc_width(void)
{
    static char wide[2800];
    static char escaped[1440];
    uint32_t csi[300];
    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    size_t i;

    memset(wide, 'a', 1400);
    memset(wide + 1400, 0x01, 1400);
    opts.term_program = "kitty";
    wcwidth_width_u8(wide, sizeof(wide), WCWIDTH_IGNORE, &opts, NULL);

    memset(escaped, 'a', sizeof(escaped));
    memcpy(escaped, "\x1b[31m", 5);
    wcwidth_width_u8(escaped, sizeof(escaped), WCWIDTH_IGNORE, &opts, NULL);

    fill_many();
    wcwidth_width_u32(many_cps, 600, WCWIDTH_IGNORE, &opts, NULL);

    csi[0] = 0x1B;
    csi[1] = '[';
    for (i = 2; i < sizeof(csi) / sizeof(csi[0]); i++)
        csi[i] = '1';
    wcwidth_width_u32(csi, sizeof(csi) / sizeof(csi[0]), WCWIDTH_STRICT,
                      &WCWIDTH_WIDTH_OPTS_DEFAULT, NULL);
    wcwidth_width_u32(csi, sizeof(csi) / sizeof(csi[0]), WCWIDTH_IGNORE,
                      &WCWIDTH_WIDTH_OPTS_DEFAULT, NULL);
}

static void
sc_wcswidth(void)
{
    static char text[1800];
    size_t i;

    for (i = 0; i < 600; i++) {
        text[i * 3] = '\xe4';
        text[i * 3 + 1] = '\xb8';
        text[i * 3 + 2] = '\xad';
    }
    wcswidth_u8(text, sizeof(text), 1);
    wcstwidth_u8(text, sizeof(text), 1, "kitty");
}

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
    sweep(sc_align);
    sweep(sc_align_u32);
    sweep(sc_clip);
    sweep(sc_clip_u32);
    sweep(sc_escape);
    sweep(sc_grapheme);
    sweep(sc_sgr);
    sweep(sc_textwrap);
    sweep(sc_textwrap_u32);
    sweep(sc_utf8);
    sweep(sc_width);
    sweep(sc_wcswidth);
    sweep(sc_wrap_lines_offsets);
    sweep(sc_wrap_grows_lines);
    sweep(sc_wrap_uax14);
    return test_summary();
}
