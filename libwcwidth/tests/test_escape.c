#include "test_common.h"
#include "wcwidth/escape.h"
#include <limits.h>
#include <string.h>

/*
 * Quick wrapper for tests: classify and return the type.
 * Returns WCWIDTH_ESC_NONE if classify returns false.
 */
static wcwidth_esc_type_t
classify(const char *text, wcwidth_esc_result_t *r)
{
    size_t len = strlen(text);
    if (!wcwidth_escape_classify(text, len, 0, r)) {
        return WCWIDTH_ESC_NONE;
    }
    return r->type;
}

typedef struct
{
    char segments[16][64];
    bool is_escape[16];
    int count;
} iter_capture_t;

static void
iter_capture_fn(const char *segment, size_t seg_len, bool is_escape, void *userdata)
{
    iter_capture_t *cap = (iter_capture_t *) userdata;
    if (cap->count < 16 && seg_len < 64) {
        memcpy(cap->segments[cap->count], segment, seg_len);
        cap->segments[cap->count][seg_len] = '\0';
        cap->is_escape[cap->count] = is_escape;
        cap->count++;
    }
}

TEST(classify_basic)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[1;32;44m";

    ASSERT_EQ(WCWIDTH_ESC_SGR, classify(text, &r));
    ASSERT_EQ((size_t) 7, r.sgr_params_len);
    ASSERT_TRUE(memcmp(r.sgr_params, "1;32;44", 7) == 0);

    ASSERT_EQ(WCWIDTH_ESC_CUF, classify("\x1b[10C", &r));
    ASSERT_EQ(10, r.cursor_n);

    /* OSC 8 hyperlinks are not parsed; they are generic zero-width OSCs. */
    text = "\x1b]8;id=1;https://example.com\x07";
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify(text, &r));
    ASSERT_EQ((size_t) 29, r.length);

    text = "\x1b]66;s=2;hello\x07";
    ASSERT_EQ(WCWIDTH_ESC_OSC66, classify(text, &r));
    ASSERT_EQ((size_t) 5, r.ts_text_len);

    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[2J", &r));
    ASSERT_EQ(WCWIDTH_ESC_UNRECOGNIZED, classify("\x1b", &r));
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b(B", &r));

    /* classify at an offset, and no escape at all */
    text = "abc\x1b[31mxyz";
    ASSERT_TRUE(wcwidth_escape_classify(text, strlen(text), 3, &r));
    ASSERT_EQ(WCWIDTH_ESC_SGR, r.type);
    ASSERT_EQ(text + 3, r.start);
    ASSERT_FALSE(wcwidth_escape_classify("hello", 5, 0, &r));
}

TEST(strip_basic)
{
    char buf[64];
    size_t out_len;
    size_t needed = wcwidth_escape_strip("\x1b[31mred\x1b[0m", 12, buf, sizeof(buf), &out_len);

    ASSERT_EQ((size_t) 3, needed);
    ASSERT_EQ((size_t) 3, out_len);
    buf[out_len] = '\0';
    ASSERT_STREQ("red", buf);

    const char *input = "\x1b]66;s=2;hello\x07";
    needed = wcwidth_escape_strip(input, strlen(input), buf, sizeof(buf), &out_len);
    ASSERT_EQ((size_t) 5, needed);
    buf[out_len] = '\0';
    ASSERT_STREQ("hello", buf);
}

TEST(strip_truncated)
{
    /* C-only: out_cap truncation is reported via the return value */
    char buf[4];
    size_t out_len;
    size_t needed = wcwidth_escape_strip("\x1b[31mred\x1b[0m!!", 15, buf, sizeof(buf), &out_len);
    ASSERT_TRUE(needed > sizeof(buf));
}

TEST(strip_u32_basic)
{
    const uint32_t cps[] = {'r', 'e', 'd', 0x1B, '[', '3', '1', 'm'};
    const uint32_t expect[] = {'r', 'e', 'd'};
    size_t len = 0;
    uint32_t *result = wcwidth_escape_strip_u32(cps, 8, &len);

    ASSERT_NOT_NULL(result);
    ASSERT_EQ((size_t) 3, len);
    ASSERT_EQ(0, memcmp(expect, result, sizeof(expect)));
    free(result);
}

TEST(iter_basic)
{
    iter_capture_t cap;
    memset(&cap, 0, sizeof(cap));
    wcwidth_escape_iter("\x1b[31mred", 8, iter_capture_fn, &cap);

    ASSERT_EQ(2, cap.count);
    ASSERT_STREQ("\x1b[31m", cap.segments[0]);
    ASSERT_TRUE(cap.is_escape[0]);
    ASSERT_STREQ("red", cap.segments[1]);
    ASSERT_FALSE(cap.is_escape[1]);
}

TEST(has_cursor_movement_basic)
{
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("ab\x08"
                                                   "cd",
                                                   5));
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("\x1b[10G", 5));
    ASSERT_FALSE(wcwidth_escape_has_cursor_movement("\x1b[31m", 5));
    ASSERT_FALSE(wcwidth_escape_has_cursor_movement("hello", 5));
}

TEST(osc_unterminated)
{
    /* C-only: an unterminated OSC at the buffer end consumes only ESC ]. */
    wcwidth_esc_result_t r;

    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b]66;", &r));
    ASSERT_EQ((int64_t) 2, (int64_t) r.length);
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b]0;title", &r));
    ASSERT_EQ((int64_t) 2, (int64_t) r.length);
}

TEST(classify_scroll_region_and_bel_terminator)
{
    wcwidth_esc_result_t r;

    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[1;2r", &r));
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[1;2;3r", &r));
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[?r", &r));
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b_apc\x07", &r));
    ASSERT_EQ((int64_t) 6, (int64_t) r.length);
}

TEST(strip_u32_heap)
{
    uint32_t long_text[300];
    uint32_t *result;
    size_t len = 0;
    size_t i;

    for (i = 0; i < sizeof(long_text) / sizeof(long_text[0]); i++)
        long_text[i] = 0x4E2D;
    result = wcwidth_escape_strip_u32(long_text, 300, &len);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ(300, len);
    ASSERT_EQ(0x4E2D, result[0]);
    free(result);
}

TEST(iter_leading_and_trailing_visible)
{
    iter_capture_t cap;
    memset(&cap, 0, sizeof(cap));
    wcwidth_escape_iter("abc\x1b[31m", 8, iter_capture_fn, &cap);

    ASSERT_EQ(2, cap.count);
    ASSERT_STREQ("abc", cap.segments[0]);
    ASSERT_FALSE(cap.is_escape[0]);
    ASSERT_STREQ("\x1b[31m", cap.segments[1]);
    ASSERT_TRUE(cap.is_escape[1]);
}

TEST(classify_param_edges)
{
    wcwidth_esc_result_t r;

    /* 20 digits saturate rather than overflowing the int accumulator. */
    ASSERT_EQ(WCWIDTH_ESC_CUF, classify("\x1b[99999999999999999999C", &r));
    ASSERT_EQ(INT_MAX, (int64_t) r.cursor_n);
    ASSERT_EQ((size_t) 23, r.length);

    /* absent parameter defaults to 1 */
    ASSERT_EQ(WCWIDTH_ESC_HPA, classify("\x1b[G", &r));
    ASSERT_EQ(1, (int64_t) r.cursor_n);

    /* scroll region needs digits on both sides of the semicolon */
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[r", &r));
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[12r", &r));
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[;r", &r));
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[12?r", &r));
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[1;2;r", &r));

    /* alternate screen accepts ?47 as well as ?1049 */
    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[?47h", &r));
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[?104h", &r));
}

TEST(classify_osc66_st_terminator)
{
    wcwidth_esc_result_t r;

    ASSERT_EQ(WCWIDTH_ESC_OSC66, classify("\x1b]66;s=2;hi\x1b\\", &r));
    ASSERT_EQ((size_t) 13, r.length);
    ASSERT_EQ((int64_t) 2, (int64_t) r.ts_text_len);
    ASSERT_EQ(0, memcmp(r.ts_text, "hi", 2));
}

TEST(classify_non_escape)
{
    wcwidth_esc_result_t r;

    ASSERT_FALSE(wcwidth_escape_classify("a", 1, 0, &r));
    ASSERT_FALSE(wcwidth_escape_classify("", 0, 0, &r));
}

TEST(strip_null_out_len)
{
    char buf[8];

    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_escape_strip("abc", 3, buf, sizeof(buf), NULL));
    ASSERT_STREQ("abc", buf);
}

TEST(has_cursor_movement_cr_and_cub)
{
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("a\rb", 3));
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("\x1b[2C", 4));
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("\x1b[2D", 4));
}

int
main(void)
{
    RUN_TEST(classify_basic);
    RUN_TEST(strip_basic);
    RUN_TEST(strip_truncated);
    RUN_TEST(strip_u32_basic);
    RUN_TEST(iter_basic);
    RUN_TEST(has_cursor_movement_basic);
    RUN_TEST(osc_unterminated);
    RUN_TEST(classify_scroll_region_and_bel_terminator);
    RUN_TEST(strip_u32_heap);
    RUN_TEST(iter_leading_and_trailing_visible);
    RUN_TEST(classify_param_edges);
    RUN_TEST(classify_osc66_st_terminator);
    RUN_TEST(classify_non_escape);
    RUN_TEST(strip_null_out_len);
    RUN_TEST(has_cursor_movement_cr_and_cub);
    return test_summary();
}
