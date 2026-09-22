/*
 * The generated grapheme class table must agree with the chain of binary searches
 * it replaced, for every codepoint.
 */
#include "test_common.h"

#include "wcwidth/tables.h"
#include "wcwidth/table_types.h"

#define UNICODE_MAX 0x10FFFF

/* gcb_of()'s original search chain, kept as the reference. */
static unsigned
gcb_class_reference(uint32_t ucs)
{
    if (ucs == 0x000D) {
        return WCWIDTH_GCB_CR;
    }
    if (ucs == 0x000A) {
        return WCWIDTH_GCB_LF;
    }
    if (ucs == 0x200D) {
        return WCWIDTH_GCB_ZWJ;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_CONTROL, WCWIDTH_GRAPHEME_CONTROL_LEN)) {
        return WCWIDTH_GCB_CONTROL;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_EXTEND, WCWIDTH_GRAPHEME_EXTEND_LEN)) {
        return WCWIDTH_GCB_EXTEND;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_REGIONAL_INDICATOR,
                         WCWIDTH_GRAPHEME_REGIONAL_INDICATOR_LEN)) {
        return WCWIDTH_GCB_REGIONAL_INDICATOR;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_PREPEND, WCWIDTH_GRAPHEME_PREPEND_LEN)) {
        return WCWIDTH_GCB_PREPEND;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_SPACINGMARK, WCWIDTH_GRAPHEME_SPACINGMARK_LEN)) {
        return WCWIDTH_GCB_SPACINGMARK;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_L, WCWIDTH_GRAPHEME_L_LEN)) {
        return WCWIDTH_GCB_L;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_V, WCWIDTH_GRAPHEME_V_LEN)) {
        return WCWIDTH_GCB_V;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_T, WCWIDTH_GRAPHEME_T_LEN)) {
        return WCWIDTH_GCB_T;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_LV, WCWIDTH_GRAPHEME_LV_LEN)) {
        return WCWIDTH_GCB_LV;
    }
    if (wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_LVT, WCWIDTH_GRAPHEME_LVT_LEN)) {
        return WCWIDTH_GCB_LVT;
    }
    return WCWIDTH_GCB_OTHER;
}

TEST(gcb_class_matches_the_search_chain)
{
    uint32_t ucs;
    int mismatches = 0;

    for (ucs = 0; ucs <= UNICODE_MAX; ucs++) {
        unsigned expected = gcb_class_reference(ucs);
        unsigned actual = wcwidth_gcb_class(ucs);

        if (expected != actual) {
            if (mismatches == 0) {
                fprintf(stderr, "  GCB: U+%04X chain=%u table=%u\n", ucs, expected, actual);
            }
            mismatches++;
        }
    }
    ASSERT_EQ(0, mismatches);
}

/*
 * terminal_override.c resolves Extend through the class table.  The two agree
 * only while nothing ahead of Extend in precedence appears in that table.
 */
TEST(gcb_extend_class_matches_the_extend_table)
{
    uint32_t ucs;
    int mismatches = 0;

    for (ucs = 0; ucs <= UNICODE_MAX; ucs++) {
        int in_table =
            wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_EXTEND, WCWIDTH_GRAPHEME_EXTEND_LEN) != 0;
        int is_extend = wcwidth_gcb_class(ucs) == WCWIDTH_GCB_EXTEND;

        if (in_table != is_extend) {
            if (mismatches == 0) {
                fprintf(stderr, "  U+%04X in Extend table=%d, class says=%d\n", ucs, in_table,
                        is_extend);
            }
            mismatches++;
        }
    }
    ASSERT_EQ(0, mismatches);
}

TEST(out_of_range_codepoints_are_absent)
{
    ASSERT_EQ(WCWIDTH_GCB_OTHER, wcwidth_gcb_class(WCWIDTH_GCB_CLASS_MAX + 1));
    ASSERT_EQ(WCWIDTH_GCB_OTHER, wcwidth_gcb_class(UNICODE_MAX));
}

int
main(void)
{
    RUN_TEST(gcb_class_matches_the_search_chain);
    RUN_TEST(gcb_extend_class_matches_the_extend_table);
    RUN_TEST(out_of_range_codepoints_are_absent);
    return test_summary();
}
