/*
 * Display width of a single Unicode codepoint.
 */
#include "wcwidth/wcwidth.h"
#include "wcwidth/tables.h"
#include "wcwidth/generated_tables.h"

int
wcwidth_u32(uint32_t ucs, int ambiguous_width)
{
    /* printable ASCII -- fast path (~40% perf boost for mostly-ASCII text) */
    if (ucs >= 32 && ucs < 0x7f) {
        return 1;
    }

    /* C0 / C1 control characters → non-printable */
    if (ucs != 0 && (ucs < 32 || (ucs >= 0x7f && ucs < 0xa0))) {
        return -1;
    }

    /* Zero-width codepoints (combining marks, ZWJ, format chars, etc.) */
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_ZERO, WCWIDTH_TABLE_ZERO_LEN)) {
        return 0;
    }

    /* Wide East Asian characters (F and W categories) */
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_WIDE, WCWIDTH_TABLE_WIDE_LEN)) {
        return 2;
    }

    /* Ambiguous East Asian (A category) -- only wide in CJK context */
    if (ambiguous_width == 2
        && wcwidth_bisearch(ucs, WCWIDTH_TABLE_AMBIGUOUS, WCWIDTH_TABLE_AMBIGUOUS_LEN)) {
        return 2;
    }

    return 1;
}
