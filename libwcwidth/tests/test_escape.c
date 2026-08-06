#include "test_common.h"
#include "wcwidth/escape.h"
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

    text = "\x1b]8;id=1;https://example.com\x07";
    ASSERT_EQ(WCWIDTH_ESC_OSC8_OPEN, classify(text, &r));
    ASSERT_EQ((size_t) 4, r.osc8_params_len);
    ASSERT_EQ((size_t) 19, r.osc8_url_len);

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
    return test_summary();
}
