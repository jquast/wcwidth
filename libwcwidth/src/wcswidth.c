/*
 * String display width with inline grapheme cluster tracking.
 */
#include "wcwidth/wcwidth.h"
#include "wcwidth/tables.h"
#include "wcwidth/generated_tables.h"
#include "wcwidth/unicode.h"
#include "wcwidth/utf8.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

int
wcswidth_u32(const uint32_t *cp, size_t n, int ambiguous_width)
{
    size_t idx;
    int total_width;
    int cluster_width;
    int last_measured_idx;
    uint32_t last_measured_ucs;
    int last_measured_w;
    bool prev_was_virama;

    /* Empty input */
    if (n == 0 || cp == NULL) {
        return 0;
    }

    /* Fast path: pure ASCII printable strings are always width == length */
    {
        size_t i;
        bool all_ascii = true;
        for (i = 0; i < n; i++) {
            if (cp[i] < 32 || cp[i] >= 0x7f) {
                all_ascii = false;
                break;
            }
        }
        if (all_ascii) {
            return (int) n;
        }
    }

    total_width = 0;
    cluster_width = 0;
    idx = 0;
    last_measured_idx = -2;
    last_measured_ucs = 0;
    last_measured_w = 0;
    prev_was_virama = false;

    while (idx < n) {
        uint32_t ucs = cp[idx];

        /* 5. ZWJ (U+200D): consumed without contributing width. */
        if (ucs == 0x200D) {
            if (prev_was_virama) {
                idx += 1;
            }
            else if (idx + 1 < n) {
                last_measured_w = 0;
                prev_was_virama = false;
                idx += 2;
            }
            else {
                prev_was_virama = false;
                idx += 1;
            }
            continue;
        }

        /* 6. VS16 (U+FE0F): converts preceding narrow character to wide. */
        if (ucs == 0xFE0F && last_measured_idx >= 0) {
            if (wcwidth_bisearch(last_measured_ucs, WCWIDTH_TABLE_VS16, WCWIDTH_TABLE_VS16_LEN)) {
                cluster_width = 2;
            }
            last_measured_idx = -2;
            idx += 1;
            continue;
        }

        if (ucs == 0xFE0E && last_measured_idx >= 0) {
            if (wcwidth_bisearch(last_measured_ucs, WCWIDTH_TABLE_VS15, WCWIDTH_TABLE_VS15_LEN)
                && last_measured_w == 2) {
                total_width -= 1;
            }
            idx += 1;
            continue;
        }

        /* 7. Regional Indicator & Fitzpatrick (both above BMP) */
        if (ucs > 0xFFFF) {
            if (wcwidth_is_regional_indicator(ucs)) {
                int ri_before = 0;
                size_t j = idx;
                while (j > 0) {
                    j--;
                    if (wcwidth_is_regional_indicator(cp[j])) {
                        ri_before++;
                    }
                    else {
                        break;
                    }
                }
                if (ri_before % 2 == 1) {
                    last_measured_ucs = ucs;
                    idx += 1;
                    continue;
                }
            }
            else if (wcwidth_is_fitzpatrick(ucs) && last_measured_ucs != 0
                     && wcwidth_is_emoji_zwj_set(last_measured_ucs)) {
                idx += 1;
                continue;
            }
        }

        /* 8. Normal character: measure with wcwidth. */
        {
            int w = wcwidth_u32(ucs, ambiguous_width);
            if (w < 0) {
                return -1;
            }
            if (w > 0) {
                if (prev_was_virama) {
                    cluster_width = 2;
                }
                else if (cluster_width) {
                    total_width += cluster_width;
                    cluster_width = w;
                }
                else {
                    cluster_width = w;
                }
                last_measured_idx = (int) idx;
                last_measured_ucs = ucs;
                last_measured_w = w;
                prev_was_virama = false;
            }
            else if (wcwidth_is_virama(ucs)) {
                prev_was_virama = true;
            }
            else if (last_measured_idx >= 0
                     && wcwidth_bisearch(ucs, WCWIDTH_TABLE_MC, WCWIDTH_TABLE_MC_LEN)) {
                cluster_width = 2;
                last_measured_idx = -2;
                prev_was_virama = false;
            }
            else {
                prev_was_virama = false;
            }
        }
        idx += 1;
    }

    if (cluster_width) {
        total_width += cluster_width;
    }
    return total_width;
}

int
wcswidth_u8(const char *utf8, size_t n, int ambiguous_width)
{
    uint32_t stack[512];
    const uint32_t *cps;
    size_t count;
    int result;

    if (utf8 == NULL) {
        return 0;
    }

    if (n == (size_t) -1) {
        n = strlen(utf8);
    }

    if (n == 0) {
        return 0;
    }

    /* The whole string is decoded and measured as a single sequence: grapheme
     * clusters (virama conjuncts, Mc spacing marks, ZWJ sequences, RI pairs)
     * may span any chunk boundary. */
    cps = wcwidth_decode_u32(utf8, n, stack, sizeof stack / sizeof stack[0], &count);
    if (cps == NULL) {
        return -1;
    }
    result = wcswidth_u32(cps, count, ambiguous_width);
    if (cps != stack) {
        free((void *) cps);
    }
    return result;
}
