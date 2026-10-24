/*
 * Display width of a single Unicode codepoint.
 */
#include "wcwidth/wcwidth.h"
#include "wcwidth/table_types.h"
#include "wcwidth/tables.h"
#include "wcwidth/bitset_tables.h"

int
wcwidth_u32(uint32_t ucs, int ambiguous_width)
{
    /* printable ASCII: fast path (~40% faster for mostly-ASCII text) */
    if (ucs >= 32 && ucs < 0x7f) {
        return 1;
    }

    /* C0 / C1 control characters → non-printable */
    if (ucs != 0 && (ucs < 32 || (ucs >= 0x7f && ucs < 0xa0))) {
        return -1;
    }

    /* Zero-width codepoints (combining marks, ZWJ, format chars, etc.) */
    if (wcwidth_bitset_get(ucs, WCWIDTH_ZERO_WIDTH_MIN, WCWIDTH_ZERO_WIDTH_MAX,
                           WCWIDTH_ZERO_WIDTH_INDEX, WCWIDTH_ZERO_WIDTH_POOL)) {
        return 0;
    }

    /* Wide East Asian characters (F and W categories) */
    if (wcwidth_bitset_get(ucs, WCWIDTH_WIDE_EASTASIAN_MIN, WCWIDTH_WIDE_EASTASIAN_MAX,
                           WCWIDTH_WIDE_EASTASIAN_INDEX, WCWIDTH_WIDE_EASTASIAN_POOL)) {
        return 2;
    }

    /* Ambiguous East Asian (A category): wide only in CJK context */
    if (ambiguous_width == 2
        && wcwidth_bitset_get(ucs, WCWIDTH_AMBIGUOUS_EASTASIAN_MIN,
                              WCWIDTH_AMBIGUOUS_EASTASIAN_MAX,
                              WCWIDTH_AMBIGUOUS_EASTASIAN_INDEX,
                              WCWIDTH_AMBIGUOUS_EASTASIAN_POOL)) {
        return 2;
    }

    return 1;
}
