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

TEST(sgr_simple)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[31m";
    ASSERT_EQ(WCWIDTH_ESC_SGR, classify(text, &r));
    ASSERT_EQ((size_t) 5, r.length);
    ASSERT_EQ((size_t) 2, r.sgr_params_len);
    ASSERT_TRUE(memcmp(r.sgr_params, "31", 2) == 0);
}

TEST(sgr_multi_params)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[1;32;44m";
    ASSERT_EQ(WCWIDTH_ESC_SGR, classify(text, &r));
    ASSERT_EQ((size_t) 10, r.length);
    ASSERT_EQ((size_t) 7, r.sgr_params_len);
    ASSERT_TRUE(memcmp(r.sgr_params, "1;32;44", 7) == 0);
}

TEST(sgr_extended_color)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[38;5;196m";
    ASSERT_EQ(WCWIDTH_ESC_SGR, classify(text, &r));
    ASSERT_EQ((size_t) 11, r.length);
    ASSERT_EQ((size_t) 8, r.sgr_params_len);
    ASSERT_TRUE(memcmp(r.sgr_params, "38;5;196", 8) == 0);
}

TEST(sgr_reset)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[0m";
    ASSERT_EQ(WCWIDTH_ESC_SGR, classify(text, &r));
    ASSERT_EQ((size_t) 4, r.length);
    ASSERT_EQ((size_t) 1, r.sgr_params_len);
    ASSERT_TRUE(memcmp(r.sgr_params, "0", 1) == 0);
}

TEST(sgr_empty_params)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[m";
    ASSERT_EQ(WCWIDTH_ESC_SGR, classify(text, &r));
    ASSERT_EQ((size_t) 3, r.length);
    ASSERT_EQ((size_t) 0, r.sgr_params_len);
}

TEST(cuf_default)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[C";
    ASSERT_EQ(WCWIDTH_ESC_CUF, classify(text, &r));
    ASSERT_EQ(1, r.cursor_n);
}

TEST(cuf_with_n)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[10C";
    ASSERT_EQ(WCWIDTH_ESC_CUF, classify(text, &r));
    ASSERT_EQ(10, r.cursor_n);
}

TEST(cub_default)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[D";
    ASSERT_EQ(WCWIDTH_ESC_CUB, classify(text, &r));
    ASSERT_EQ(1, r.cursor_n);
}

TEST(cub_with_n)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[5D";
    ASSERT_EQ(WCWIDTH_ESC_CUB, classify(text, &r));
    ASSERT_EQ(5, r.cursor_n);
}

TEST(hpa_default)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[G";
    ASSERT_EQ(WCWIDTH_ESC_HPA, classify(text, &r));
    ASSERT_EQ(1, r.cursor_n);
}

TEST(hpa_with_n)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b[20G";
    ASSERT_EQ(WCWIDTH_ESC_HPA, classify(text, &r));
    ASSERT_EQ(20, r.cursor_n);
}

TEST(osc8_open_bel)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b]8;id=1;https://example.com\x07";
    ASSERT_EQ(WCWIDTH_ESC_OSC8_OPEN, classify(text, &r));
    ASSERT_EQ((size_t) 4, r.osc8_params_len);
    ASSERT_TRUE(memcmp(r.osc8_params, "id=1", 4) == 0);
    ASSERT_EQ((size_t) 19, r.osc8_url_len);
    ASSERT_TRUE(memcmp(r.osc8_url, "https://example.com", 19) == 0);
}

TEST(osc8_close_bel)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b]8;;\x07";
    ASSERT_EQ(WCWIDTH_ESC_OSC8_CLOSE, classify(text, &r));
}

TEST(osc8_open_st)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b]8;id=1;https://example.com\x1b\\";
    ASSERT_EQ(WCWIDTH_ESC_OSC8_OPEN, classify(text, &r));
    ASSERT_EQ((size_t) 4, r.osc8_params_len);
    ASSERT_TRUE(memcmp(r.osc8_params, "id=1", 4) == 0);
    ASSERT_EQ((size_t) 19, r.osc8_url_len);
    ASSERT_TRUE(memcmp(r.osc8_url, "https://example.com", 19) == 0);
}

TEST(osc66_bel)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b]66;s=2;hello\x07";
    ASSERT_EQ(WCWIDTH_ESC_OSC66, classify(text, &r));
    ASSERT_EQ((size_t) 3, r.ts_meta_len);
    ASSERT_TRUE(memcmp(r.ts_meta, "s=2", 3) == 0);
    ASSERT_EQ((size_t) 5, r.ts_text_len);
    ASSERT_TRUE(memcmp(r.ts_text, "hello", 5) == 0);
    ASSERT_EQ('\x07', r.ts_terminator);
}

TEST(indeterminate_erase_display)
{
    wcwidth_esc_result_t r;
    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[2J", &r));
}

TEST(indeterminate_cursor_pos)
{
    wcwidth_esc_result_t r;
    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[1;1H", &r));
}

TEST(indeterminate_erase_line)
{
    wcwidth_esc_result_t r;
    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[K", &r));
}

TEST(indeterminate_cursor_up)
{
    wcwidth_esc_result_t r;
    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[A", &r));
}

TEST(indeterminate_cursor_down)
{
    wcwidth_esc_result_t r;
    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[B", &r));
}

TEST(indeterminate_delete_char)
{
    wcwidth_esc_result_t r;
    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[P", &r));
}

TEST(indeterminate_scroll_up)
{
    wcwidth_esc_result_t r;
    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[S", &r));
}

TEST(indeterminate_scroll_down)
{
    wcwidth_esc_result_t r;
    ASSERT_EQ(WCWIDTH_ESC_INDETERMINATE, classify("\x1b[T", &r));
}

TEST(lone_esc_at_end)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b";
    ASSERT_EQ(WCWIDTH_ESC_UNRECOGNIZED, classify(text, &r));
    ASSERT_EQ((size_t) 1, r.length);
}

TEST(charset_designation)
{
    wcwidth_esc_result_t r;
    const char *text = "\x1b(B";
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify(text, &r));
    ASSERT_EQ((size_t) 2, r.length);
}

TEST(other_csi_private_mode_set)
{
    wcwidth_esc_result_t r;
    /* alternate screen: CSI ? 1049 h */
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[?1049h", &r));
}

TEST(other_csi_cursor_hide)
{
    wcwidth_esc_result_t r;
    /* DECTCEM: CSI ? 25 l */
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b[?25l", &r));
}

TEST(other_fe_sequence)
{
    wcwidth_esc_result_t r;
    /* ESC D = scroll forward (index) */
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b"
                                          "D",
                                          &r));
}

TEST(other_fp_sequence)
{
    wcwidth_esc_result_t r;
    /* ESC 7 = save cursor */
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b"
                                          "7",
                                          &r));
}

TEST(other_fs_sequence)
{
    wcwidth_esc_result_t r;
    /* ESC ` = unknown Fs */
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b`", &r));
}

TEST(other_osc)
{
    wcwidth_esc_result_t r;
    /* generic OSC sequence */
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b]0;title\x07", &r));
}

TEST(nf_sequence)
{
    wcwidth_esc_result_t r;
    /* ESC space F = nF sequence */
    ASSERT_EQ(WCWIDTH_ESC_OTHER, classify("\x1b F", &r));
    ASSERT_EQ((size_t) 3, r.length);
}

TEST(classify_with_offset)
{
    wcwidth_esc_result_t r;
    const char *text = "abc\x1b[31mxyz";
    bool ok = wcwidth_escape_classify(text, strlen(text), 3, &r);
    ASSERT_TRUE(ok);
    ASSERT_EQ(WCWIDTH_ESC_SGR, r.type);
    ASSERT_EQ(text + 3, r.start);
    ASSERT_EQ((size_t) 5, r.length);
}

TEST(classify_no_esc)
{
    wcwidth_esc_result_t r;
    bool ok = wcwidth_escape_classify("hello", 5, 0, &r);
    ASSERT_FALSE(ok);
}

TEST(strip_sgr)
{
    char buf[64];
    size_t out_len;
    size_t needed = wcwidth_escape_strip("\x1b[31mred\x1b[0m", 12, buf, sizeof(buf), &out_len);
    ASSERT_EQ((size_t) 3, needed);
    ASSERT_EQ((size_t) 3, out_len);
    buf[out_len] = '\0';
    ASSERT_STREQ("red", buf);
}

TEST(strip_plain_text)
{
    char buf[64];
    size_t out_len;
    size_t needed = wcwidth_escape_strip("hello", 5, buf, sizeof(buf), &out_len);
    ASSERT_EQ((size_t) 5, needed);
    ASSERT_EQ((size_t) 5, out_len);
    buf[out_len] = '\0';
    ASSERT_STREQ("hello", buf);
}

TEST(strip_preserves_osc66_text)
{
    char buf[64];
    size_t out_len;
    const char *input = "\x1b]66;s=2;hello\x07";
    size_t needed = wcwidth_escape_strip(input, strlen(input), buf, sizeof(buf), &out_len);
    ASSERT_EQ((size_t) 5, needed);
    ASSERT_EQ((size_t) 5, out_len);
    buf[out_len] = '\0';
    ASSERT_STREQ("hello", buf);
}

TEST(strip_osc8_with_text)
{
    char buf[64];
    size_t out_len;
    const char *input = "\x1b]8;id=34;https://example.com\x1b\\[view]\x1b]8;;\x1b\\";
    size_t needed = wcwidth_escape_strip(input, strlen(input), buf, sizeof(buf), &out_len);
    ASSERT_EQ((size_t) 6, needed);
    ASSERT_EQ((size_t) 6, out_len);
    buf[out_len] = '\0';
    ASSERT_STREQ("[view]", buf);
}

TEST(strip_empty_input)
{
    char buf[16];
    size_t out_len;
    size_t needed = wcwidth_escape_strip("", 0, buf, sizeof(buf), &out_len);
    ASSERT_EQ((size_t) 0, needed);
    ASSERT_EQ((size_t) 0, out_len);
}

TEST(strip_truncated)
{
    char buf[4];
    size_t out_len;
    /* "red" fits but "d" gets cut off at capacity */
    size_t needed = wcwidth_escape_strip("\x1b[31mred\x1b[0m!!", 15, buf, sizeof(buf), &out_len);
    ASSERT_TRUE(needed > sizeof(buf));
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

TEST(iter_simple_text)
{
    iter_capture_t cap;
    memset(&cap, 0, sizeof(cap));
    wcwidth_escape_iter("hello", 5, iter_capture_fn, &cap);

    ASSERT_EQ(1, cap.count);
    ASSERT_STREQ("hello", cap.segments[0]);
    ASSERT_FALSE(cap.is_escape[0]);
}

TEST(iter_sgr_and_text)
{
    iter_capture_t cap;
    memset(&cap, 0, sizeof(cap));
    const char *input = "\x1b[31mred";
    wcwidth_escape_iter(input, strlen(input), iter_capture_fn, &cap);

    ASSERT_EQ(2, cap.count);
    ASSERT_STREQ("\x1b[31m", cap.segments[0]);
    ASSERT_TRUE(cap.is_escape[0]);
    ASSERT_STREQ("red", cap.segments[1]);
    ASSERT_FALSE(cap.is_escape[1]);
}

TEST(iter_consecutive_escapes)
{
    iter_capture_t cap;
    memset(&cap, 0, sizeof(cap));
    const char *input = "\x1b[1m\x1b[31m";
    wcwidth_escape_iter(input, strlen(input), iter_capture_fn, &cap);

    ASSERT_EQ(2, cap.count);
    ASSERT_STREQ("\x1b[1m", cap.segments[0]);
    ASSERT_TRUE(cap.is_escape[0]);
    ASSERT_STREQ("\x1b[31m", cap.segments[1]);
    ASSERT_TRUE(cap.is_escape[1]);
}

TEST(iter_empty)
{
    iter_capture_t cap;
    memset(&cap, 0, sizeof(cap));
    wcwidth_escape_iter("", 0, iter_capture_fn, &cap);
    ASSERT_EQ(0, cap.count);
}

TEST(iter_osc66_and_text)
{
    iter_capture_t cap;
    memset(&cap, 0, sizeof(cap));
    const char *input = "\x1b]66;s=2;hello\x07world";
    wcwidth_escape_iter(input, strlen(input), iter_capture_fn, &cap);

    ASSERT_EQ(2, cap.count);
    ASSERT_TRUE(cap.is_escape[0]);
    ASSERT_FALSE(cap.is_escape[1]);
    ASSERT_STREQ("world", cap.segments[1]);
}

TEST(has_cursor_movement_bs)
{
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("ab\x08"
                                                   "cd",
                                                   5));
}

TEST(has_cursor_movement_cr)
{
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("ab\rc", 4));
}

TEST(has_cursor_movement_cuf)
{
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("\x1b[C", 3));
}

TEST(has_cursor_movement_cub)
{
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("\x1b[D", 3));
}

TEST(has_cursor_movement_hpa)
{
    ASSERT_TRUE(wcwidth_escape_has_cursor_movement("\x1b[10G", 5));
}

TEST(has_cursor_movement_none)
{
    ASSERT_FALSE(wcwidth_escape_has_cursor_movement("hello", 5));
}

TEST(has_cursor_movement_only_sgr)
{
    ASSERT_FALSE(wcwidth_escape_has_cursor_movement("\x1b[31m", 5));
}

int
main(void)
{
    /* SGR */
    RUN_TEST(sgr_simple);
    RUN_TEST(sgr_multi_params);
    RUN_TEST(sgr_extended_color);
    RUN_TEST(sgr_reset);
    RUN_TEST(sgr_empty_params);

    /* CUF */
    RUN_TEST(cuf_default);
    RUN_TEST(cuf_with_n);

    /* CUB */
    RUN_TEST(cub_default);
    RUN_TEST(cub_with_n);

    /* HPA */
    RUN_TEST(hpa_default);
    RUN_TEST(hpa_with_n);

    /* OSC 8 */
    RUN_TEST(osc8_open_bel);
    RUN_TEST(osc8_close_bel);
    RUN_TEST(osc8_open_st);

    /* OSC 66 */
    RUN_TEST(osc66_bel);

    /* Indeterminate */
    RUN_TEST(indeterminate_erase_display);
    RUN_TEST(indeterminate_cursor_pos);
    RUN_TEST(indeterminate_erase_line);
    RUN_TEST(indeterminate_cursor_up);
    RUN_TEST(indeterminate_cursor_down);
    RUN_TEST(indeterminate_delete_char);
    RUN_TEST(indeterminate_scroll_up);
    RUN_TEST(indeterminate_scroll_down);

    /* Lone ESC */
    RUN_TEST(lone_esc_at_end);

    /* Character set */
    RUN_TEST(charset_designation);

    /* Zero-width OTHER */
    RUN_TEST(other_csi_private_mode_set);
    RUN_TEST(other_csi_cursor_hide);
    RUN_TEST(other_fe_sequence);
    RUN_TEST(other_fp_sequence);
    RUN_TEST(other_fs_sequence);
    RUN_TEST(other_osc);
    RUN_TEST(nf_sequence);

    /* classify with offset / no-esc */
    RUN_TEST(classify_with_offset);
    RUN_TEST(classify_no_esc);

    /* escape_strip */
    RUN_TEST(strip_sgr);
    RUN_TEST(strip_plain_text);
    RUN_TEST(strip_preserves_osc66_text);
    RUN_TEST(strip_osc8_with_text);
    RUN_TEST(strip_empty_input);
    RUN_TEST(strip_truncated);

    /* escape_iter */
    RUN_TEST(iter_simple_text);
    RUN_TEST(iter_sgr_and_text);
    RUN_TEST(iter_consecutive_escapes);
    RUN_TEST(iter_empty);
    RUN_TEST(iter_osc66_and_text);

    /* escape_has_cursor_movement */
    RUN_TEST(has_cursor_movement_bs);
    RUN_TEST(has_cursor_movement_cr);
    RUN_TEST(has_cursor_movement_cuf);
    RUN_TEST(has_cursor_movement_cub);
    RUN_TEST(has_cursor_movement_hpa);
    RUN_TEST(has_cursor_movement_none);
    RUN_TEST(has_cursor_movement_only_sgr);

    return test_summary();
}
