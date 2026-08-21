/*
 * Binary search in Unicode interval tables.
 */
#include "wcwidth/table_types.h"

int
wcwidth_bisearch(uint32_t ucs, const wcwidth_interval_t *table, size_t table_len)
{
    size_t lo;
    size_t hi;

    if (table_len == 0) {
        return 0;
    }

    if (ucs < table[0].start || ucs > table[table_len - 1].end) {
        return 0;
    }

    lo = 0;
    hi = table_len;

    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;

        if (ucs > table[mid].end) {
            lo = mid + 1;
        }
        else if (ucs < table[mid].start) {
            hi = mid;
        }
        else {
            return 1;
        }
    }

    return 0;
}
