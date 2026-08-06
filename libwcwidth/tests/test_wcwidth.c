#include "test_common.h"
#include "wcwidth/wcwidth.h"

TEST(basic)
{
    ASSERT_EQ(1, wcwidth_u32('A', 1));
    ASSERT_EQ(-1, wcwidth_u32(0x01, 1));  /* C0 control */
    ASSERT_EQ(-1, wcwidth_u32(0x7F, 1));  /* DEL */
    ASSERT_EQ(2, wcwidth_u32(0x4E00, 1)); /* CJK UNIFIED IDEOGRAPH-4E00 */
    ASSERT_EQ(0, wcwidth_u32(0x0301, 1)); /* COMBINING ACUTE ACCENT */
    ASSERT_EQ(0, wcwidth_u32(0x00, 1));   /* NUL */
    ASSERT_EQ(1, wcwidth_u32(0x00A1, 1)); /* ambiguous, narrow */
    ASSERT_EQ(2, wcwidth_u32(0x00A1, 2)); /* ambiguous, wide */
}

int
main(void)
{
    RUN_TEST(basic);
    return test_summary();
}
