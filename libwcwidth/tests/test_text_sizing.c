/*
 * Tests for text_sizing.c (OSC 66 Text Sizing protocol).
 */
#include "test_common.h"
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

int
main(void)
{
    RUN_TEST(parse_basic);
    RUN_TEST(display_width_basic);
    return test_summary();
}
