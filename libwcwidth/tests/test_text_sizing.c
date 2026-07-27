/*
 * Tests for text_sizing.c (OSC 66 Text Sizing protocol).
 */
#include "test_common.h"
#include "wcwidth/text_sizing.h"
#include "wcwidth/wcwidth.h"

TEST(test_parse_empty)
{
    wcwidth_ts_params_t params;
    bool ok = wcwidth_ts_parse_params("", 0, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(1, params.scale);
    ASSERT_EQ(0, params.width);
    ASSERT_EQ(0, params.numerator);
    ASSERT_EQ(0, params.denominator);
    ASSERT_EQ(0, params.vertical_align);
    ASSERT_EQ(0, params.horizontal_align);
}

TEST(test_parse_basic)
{
    wcwidth_ts_params_t params;
    bool ok = wcwidth_ts_parse_params("s=2:w=3", 7, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(2, params.scale);
    ASSERT_EQ(3, params.width);
    /* remaining fields stay at defaults */
    ASSERT_EQ(0, params.numerator);
    ASSERT_EQ(0, params.denominator);
    ASSERT_EQ(0, params.vertical_align);
    ASSERT_EQ(0, params.horizontal_align);
}

TEST(test_parse_single_key)
{
    wcwidth_ts_params_t params;
    bool ok;

    ok = wcwidth_ts_parse_params("s=3", 3, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(3, params.scale);
    ASSERT_EQ(0, params.width);

    ok = wcwidth_ts_parse_params("w=5", 3, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(1, params.scale);
    ASSERT_EQ(5, params.width);

    ok = wcwidth_ts_parse_params("v=1", 3, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(1, params.vertical_align);

    ok = wcwidth_ts_parse_params("h=2", 3, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(2, params.horizontal_align);
}

TEST(test_parse_all_fields)
{
    wcwidth_ts_params_t params;
    bool ok;

    ok = wcwidth_ts_parse_params("s=2:w=3:n=4:d=5:v=1:h=2", 23, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(2, params.scale);
    ASSERT_EQ(3, params.width);
    ASSERT_EQ(4, params.numerator);
    ASSERT_EQ(5, params.denominator);
    ASSERT_EQ(1, params.vertical_align);
    ASSERT_EQ(2, params.horizontal_align);
}

TEST(test_parse_clamp_low)
{
    wcwidth_ts_params_t params;
    bool ok;

    ok = wcwidth_ts_parse_params("s=0", 3, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(1, params.scale);

    ok = wcwidth_ts_parse_params("w=-1", 4, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(0, params.width);

    ok = wcwidth_ts_parse_params("v=-1", 4, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(0, params.vertical_align);
}

TEST(test_parse_clamp_high)
{
    wcwidth_ts_params_t params;
    bool ok;

    ok = wcwidth_ts_parse_params("s=99", 4, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(7, params.scale);

    ok = wcwidth_ts_parse_params("w=99", 4, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(7, params.width);

    ok = wcwidth_ts_parse_params("n=99", 4, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(15, params.numerator);

    ok = wcwidth_ts_parse_params("d=99", 4, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(15, params.denominator);

    ok = wcwidth_ts_parse_params("v=99", 4, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(2, params.vertical_align);

    ok = wcwidth_ts_parse_params("h=99", 4, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(2, params.horizontal_align);
}

TEST(test_parse_unknown_key_ignored)
{
    wcwidth_ts_params_t params;
    bool ok;

    ok = wcwidth_ts_parse_params("x=5", 3, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(1, params.scale);
    ASSERT_EQ(0, params.width);

    ok = wcwidth_ts_parse_params("s=2:x=5:w=3", 11, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(2, params.scale);
    ASSERT_EQ(3, params.width);
}

TEST(test_parse_no_equals)
{
    wcwidth_ts_params_t params;
    bool ok;

    ok = wcwidth_ts_parse_params("foo", 3, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(1, params.scale);
    ASSERT_EQ(0, params.width);

    ok = wcwidth_ts_parse_params("s=2:foo:w=3", 12, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(2, params.scale);
    ASSERT_EQ(3, params.width);
}

TEST(test_parse_non_integer)
{
    wcwidth_ts_params_t params;
    bool ok;

    ok = wcwidth_ts_parse_params("s=abc", 5, &params);
    ASSERT_TRUE(ok);
    ASSERT_EQ(1, params.scale);
}

TEST(test_display_width_fixed)
{
    wcwidth_text_sizing_t ts;
    ts.params.scale = 2;
    ts.params.width = 3;
    ts.params.numerator = 0;
    ts.params.denominator = 0;
    ts.params.vertical_align = 0;
    ts.params.horizontal_align = 0;
    ts.text = "";
    ts.text_len = 0;
    ts.terminator = '\x07';

    ASSERT_EQ(6, wcwidth_ts_display_width(&ts, 1));
}

TEST(test_display_width_fixed_scale_1)
{
    wcwidth_text_sizing_t ts;
    ts.params.scale = 1;
    ts.params.width = 7;
    ts.params.numerator = 0;
    ts.params.denominator = 0;
    ts.params.vertical_align = 0;
    ts.params.horizontal_align = 0;
    ts.text = "";
    ts.text_len = 0;
    ts.terminator = '\x07';

    ASSERT_EQ(7, wcwidth_ts_display_width(&ts, 1));
}

TEST(test_display_width_auto)
{
    wcwidth_text_sizing_t ts;
    ts.params.scale = 1;
    ts.params.width = 0;
    ts.params.numerator = 0;
    ts.params.denominator = 0;
    ts.params.vertical_align = 0;
    ts.params.horizontal_align = 0;
    ts.text = "Hello";
    ts.text_len = 5;
    ts.terminator = '\x07';

    ASSERT_EQ(5, wcwidth_ts_display_width(&ts, 1));
}

TEST(test_display_width_auto_scaled)
{
    wcwidth_text_sizing_t ts;
    ts.params.scale = 2;
    ts.params.width = 0;
    ts.params.numerator = 0;
    ts.params.denominator = 0;
    ts.params.vertical_align = 0;
    ts.params.horizontal_align = 0;
    ts.text = "AB";
    ts.text_len = 2;
    ts.terminator = '\x07';

    ASSERT_EQ(4, wcwidth_ts_display_width(&ts, 1));
}

TEST(test_display_width_auto_empty_text)
{
    wcwidth_text_sizing_t ts;
    ts.params.scale = 3;
    ts.params.width = 0;
    ts.params.numerator = 0;
    ts.params.denominator = 0;
    ts.params.vertical_align = 0;
    ts.params.horizontal_align = 0;
    ts.text = "";
    ts.text_len = 0;
    ts.terminator = '\x07';

    ASSERT_EQ(0, wcwidth_ts_display_width(&ts, 1));
}

TEST(test_display_width_fixed_width_zero_scale)
{
    wcwidth_text_sizing_t ts;
    ts.params.scale = 1;
    ts.params.width = 0;
    ts.params.numerator = 0;
    ts.params.denominator = 0;
    ts.params.vertical_align = 0;
    ts.params.horizontal_align = 0;
    ts.text = "Hello";
    ts.text_len = 5;
    ts.terminator = '\x07';

    ASSERT_EQ(5, wcwidth_ts_display_width(&ts, 1));
}

int
main(void)
{
    RUN_TEST(test_parse_empty);
    RUN_TEST(test_parse_basic);
    RUN_TEST(test_parse_single_key);
    RUN_TEST(test_parse_all_fields);
    RUN_TEST(test_parse_clamp_low);
    RUN_TEST(test_parse_clamp_high);
    RUN_TEST(test_parse_unknown_key_ignored);
    RUN_TEST(test_parse_no_equals);
    RUN_TEST(test_parse_non_integer);
    RUN_TEST(test_display_width_fixed);
    RUN_TEST(test_display_width_fixed_scale_1);
    RUN_TEST(test_display_width_auto);
    RUN_TEST(test_display_width_auto_scaled);
    RUN_TEST(test_display_width_auto_empty_text);
    RUN_TEST(test_display_width_fixed_width_zero_scale);
    return test_summary();
}
