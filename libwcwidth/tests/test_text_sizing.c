/*
 * Tests for text_sizing.c (OSC 66 Text Sizing protocol).
 */
#include "test_common.h"
#include "wcwidth/escape.h"
#include "wcwidth/text_sizing.h"

TEST(parse_basic)
{
    wcwidth_ts_params_t params;
    bool ok = wcwidth_ts_parse_params("s=2:w=3", 7, &params);

    ASSERT_TRUE(ok);
    ASSERT_EQ(2, params.scale);
    ASSERT_EQ(3, params.width);
    ASSERT_EQ(0, params.numerator);
    ASSERT_EQ(0, params.denominator);
    ASSERT_EQ(0, params.vertical_align);
    ASSERT_EQ(0, params.horizontal_align);
}

TEST(display_width_basic)
{
    wcwidth_text_sizing_t ts;
    ts.params.scale = 2;
    ts.params.width = 0; /* auto-width */
    ts.params.numerator = 0;
    ts.params.denominator = 0;
    ts.params.vertical_align = 0;
    ts.params.horizontal_align = 0;
    ts.text = "AB";
    ts.text_len = 2;
    ts.terminator = '\x07';

    ASSERT_EQ(4, wcwidth_ts_display_width(&ts, 1));

    ts.params.scale = 1;
    ts.params.width = 3; /* fixed width */
    ts.text = "";
    ts.text_len = 0;
    ASSERT_EQ(3, wcwidth_ts_display_width(&ts, 1));
}

TEST(parse_invalid_and_clamped)
{
    wcwidth_ts_params_t params;

    ASSERT_TRUE(wcwidth_ts_parse_params("z=1", 3, &params));  /* unknown key */
    ASSERT_TRUE(wcwidth_ts_parse_params("s=-5", 4, &params)); /* clamped low */
    ASSERT_TRUE(wcwidth_ts_parse_params("s=", 2, &params));   /* no digits */
    ASSERT_TRUE(wcwidth_ts_parse_params("s=2x", 4, &params)); /* trailing junk */
    ASSERT_TRUE(wcwidth_ts_parse_params("s=99999999999999999999", 22, &params));
    ASSERT_TRUE(params.scale >= 1); /* saturated, then clamped high */
}

TEST(from_esc_meta_and_negative_width)
{
    wcwidth_esc_result_t esc;
    wcwidth_text_sizing_t ts;

    memset(&esc, 0, sizeof(esc));
    esc.ts_meta = "s=2:w=3";
    esc.ts_meta_len = 7;
    esc.ts_text = "";
    esc.ts_text_len = 0;
    esc.ts_terminator = '\x07';
    wcwidth_ts_from_esc(&esc, &ts);
    ASSERT_EQ(2, ts.params.scale);
    ASSERT_EQ(3, ts.params.width);

    ts.params.width = 0;
    ts.params.scale = 1;
    ts.text = "\x01";
    ts.text_len = 1;
    ASSERT_EQ(0, wcwidth_ts_display_width(&ts, 1));

    esc.ts_meta_len = 0;
    wcwidth_ts_from_esc(&esc, &ts);
    ASSERT_EQ(1, ts.params.scale);
}

TEST(from_esc_bel_and_st_terminators)
{
    static const char bel[] = "\x1b]66;s=2:w=3;hello\x07";
    static const char st[] = "\x1b]66;s=2:w=3;hello\x1b\\";
    wcwidth_esc_result_t esc;
    wcwidth_text_sizing_t ts_bel;
    wcwidth_text_sizing_t ts_st;

    ASSERT_TRUE(wcwidth_escape_classify(bel, sizeof(bel) - 1, 0, &esc));
    wcwidth_ts_from_esc(&esc, &ts_bel);
    ASSERT_TRUE(wcwidth_escape_classify(st, sizeof(st) - 1, 0, &esc));
    wcwidth_ts_from_esc(&esc, &ts_st);

    ASSERT_EQ(2, ts_bel.params.scale);
    ASSERT_EQ(2, ts_st.params.scale);
    ASSERT_EQ(3, ts_bel.params.width);
    ASSERT_EQ(3, ts_st.params.width);
    ASSERT_EQ(5, (int64_t) ts_bel.text_len);
    ASSERT_EQ(5, (int64_t) ts_st.text_len);
    ASSERT_EQ(0, memcmp(ts_bel.text, ts_st.text, 5));
    ASSERT_EQ(wcwidth_ts_display_width(&ts_bel, 1), wcwidth_ts_display_width(&ts_st, 1));
    ASSERT_EQ(6, wcwidth_ts_display_width(&ts_st, 1));
    ASSERT_EQ((int64_t) '\x07', (int64_t) ts_bel.terminator);
    ASSERT_EQ((int64_t) '\\', (int64_t) ts_st.terminator);
}

int
main(void)
{
    RUN_TEST(parse_basic);
    RUN_TEST(display_width_basic);
    RUN_TEST(parse_invalid_and_clamped);
    RUN_TEST(from_esc_meta_and_negative_width);
    RUN_TEST(from_esc_bel_and_st_terminators);
    return test_summary();
}
