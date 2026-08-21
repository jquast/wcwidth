/*
 * Terminal-aware string width measurement.
 *
 * Applies per-terminal correction tables (single-codepoint override intervals
 * and grapheme cluster overrides) on top of the grapheme-clustering loop
 * shared with wcswidth_u32().
 */
#include "wcwidth/wcwidth.h"
#include "wcwidth/table_types.h"
#include "wcwidth/tables.h"
#include "wcwidth/terminal_override.h"
#include "wcwidth/unicode.h"
#include "wcwidth/utf8.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>

int
wcstwidth_u32(const uint32_t *cp, size_t n, int ambiguous_width, const char *term_program)
{
    const wcwidth_terminal_override_t *term = wcwidth_resolve_terminal(term_program);
    const wcwidth_interval_t *narrower = NULL;
    size_t narrower_len = 0;
    const wcwidth_interval_t *vs16_narrower = NULL;
    size_t vs16_narrower_len = 0;
    const wcwidth_interval_t *vs15_wider = NULL;
    size_t vs15_wider_len = 0;
    const wcwidth_interval_t *zeroer = NULL;
    size_t zeroer_len = 0;
    const wcwidth_interval_t *narrow_wider = NULL;
    size_t narrow_wider_len = 0;
    const wcwidth_interval_t *narrow_zeroer = NULL;
    size_t narrow_zeroer_len = 0;
    bool has_graphemes = false;
    size_t idx;
    int total_width;
    int cluster_width;
    int last_measured_idx;
    uint32_t last_measured_ucs;
    int last_measured_w;
    bool prev_was_virama;
    int cluster_start;
    int total_before_cluster;

    if (term != NULL) {
        narrower = term->set->narrower;
        narrower_len = term->set->narrower_len;
        vs16_narrower = term->set->vs16_narrower;
        vs16_narrower_len = term->set->vs16_narrower_len;
        vs15_wider = term->set->vs15_wider;
        vs15_wider_len = term->set->vs15_wider_len;
        zeroer = term->set->zeroer;
        zeroer_len = term->set->zeroer_len;
        narrow_wider = term->set->narrow_wider;
        narrow_wider_len = term->set->narrow_wider_len;
        narrow_zeroer = term->set->narrow_zeroer;
        narrow_zeroer_len = term->set->narrow_zeroer_len;
        has_graphemes = term->grapheme_entries_len > 0;
    }
    bool has_cp_overrides = narrower_len > 0 || zeroer_len > 0
                            || narrow_wider_len > 0 || narrow_zeroer_len > 0;

    /* Empty input */
    if (n == 0 || cp == NULL) {
        return 0;
    }

    /* Fast path: printable ASCII is always width == length. */
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
    cluster_start = -1;
    total_before_cluster = 0;

    while (idx < n) {
        uint32_t ucs = cp[idx];

        /* 5. ZWJ (U+200D): consumed without contributing width. */
        if (ucs == 0x200D) {
            if (prev_was_virama) {
                idx += 1;
            }
            else if (idx + 1 < n) {
                /* Check for a terminal grapheme override when the base char
                 * is ExtPict/RI. */
                if (has_graphemes && last_measured_idx >= 0
                    && wcwidth_is_emoji_zwj_set(last_measured_ucs)) {
                    size_t cluster_end =
                        wcwidth_scan_zwj_cluster_end(cp, n, (size_t) last_measured_idx);
                    int override_w = wcwidth_grapheme_override_lookup(
                        term, cp + last_measured_idx, cluster_end - (size_t) last_measured_idx);
                    if (override_w >= 0) {
                        total_width += override_w - last_measured_w;
                        last_measured_idx = -2;
                        last_measured_ucs = 0;
                        last_measured_w = 0;
                        prev_was_virama = false;
                        cluster_start = -1;
                        idx = cluster_end;
                        continue;
                    }
                }
                /* No override; ZWJ breaks VS16/VS15 adjacency. */
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
            if (!wcwidth_bisearch(last_measured_ucs, vs16_narrower, vs16_narrower_len)
                && wcwidth_bisearch(last_measured_ucs, WCWIDTH_TABLE_VS16,
                                    WCWIDTH_TABLE_VS16_LEN)) {
                cluster_width = 2;
            }
            last_measured_idx = -2; /* prevent double application */
            idx += 1;
            continue;
        }

        /* VS15 (U+FE0E): text variation selector, requests narrow presentation. */
        if (ucs == 0xFE0E && last_measured_idx >= 0) {
            bool vs15_narrow =
                wcwidth_bisearch(last_measured_ucs, WCWIDTH_TABLE_VS15, WCWIDTH_TABLE_VS15_LEN)
                != 0;
            if (wcwidth_bisearch(last_measured_ucs, vs15_wider, vs15_wider_len)) {
                vs15_narrow = false;
            }
            if (vs15_narrow && last_measured_w == 2) {
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
            /* Apply single-codepoint terminal overrides (pre-merged sets). */
            if (has_cp_overrides) {
                if (w == 2 && wcwidth_bisearch(ucs, narrower, narrower_len)) {
                    w = 1;
                }
                else if (w == 2 && wcwidth_bisearch(ucs, zeroer, zeroer_len)) {
                    w = 0;
                }
                if (w == 1 && wcwidth_bisearch(ucs, narrow_wider, narrow_wider_len)) {
                    w = 2;
                }
                else if (w == 1 && wcwidth_bisearch(ucs, narrow_zeroer, narrow_zeroer_len)) {
                    w = 0;
                }
            }
            if (w > 0) {
                /* virama+consonant extends the current cluster; otherwise
                 * flush the previous cluster, checking grapheme overrides. */
                if (prev_was_virama) {
                    cluster_width = 2;
                }
                else if (cluster_width) {
                    bool flushed = false;
                    if (has_graphemes && cluster_start >= 0) {
                        /* Two-phase: the candidate (cluster + current char)
                         * matches clusters ending at this char; the cluster
                         * alone matches C+Mc overrides stored without the
                         * trailing Mc.  Only the candidate match flushes; the
                         * cluster match continues with the current char. */
                        int override_w = wcwidth_grapheme_override_lookup(
                            term, cp + cluster_start, (size_t) idx - (size_t) cluster_start + 1);
                        if (override_w >= 0) {
                            total_width = total_before_cluster + override_w;
                            flushed = true;
                            cluster_width = 0;
                        }
                        else {
                            int cluster_w = wcwidth_grapheme_override_lookup(
                                term, cp + cluster_start, (size_t) idx - (size_t) cluster_start);
                            if (cluster_w >= 0) {
                                total_width = total_before_cluster + cluster_w;
                            }
                            else {
                                total_width += cluster_width;
                            }
                        }
                    }
                    else {
                        total_width += cluster_width;
                    }
                    if (!flushed) {
                        cluster_width = w;
                        cluster_start = (int) idx;
                        total_before_cluster = total_width;
                    }
                }
                else {
                    cluster_width = w;
                    cluster_start = (int) idx;
                    total_before_cluster = total_width;
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
                /* Spacing Combining Mark (Mc) following a base character. */
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
        if (has_graphemes && cluster_start >= 0) {
            int override_w = wcwidth_grapheme_override_lookup(term, cp + cluster_start,
                                                              n - (size_t) cluster_start);
            if (override_w >= 0) {
                total_width = total_before_cluster + override_w;
            }
            else {
                total_width += cluster_width;
            }
        }
        else {
            total_width += cluster_width;
        }
    }
    return total_width;
}

int
wcstwidth_u8(const char *utf8, size_t n, int ambiguous_width, const char *term_program)
{
    uint32_t stack[512];
    uint32_t *cps;
    size_t count;
    int result;

    if (utf8 == NULL) {
        return 0;
    }

    if (n == 0) {
        return 0;
    }

    /* The whole string is decoded and measured as a single sequence: grapheme
     * clusters (RI pairs, ZWJ chains, virama conjuncts) may span any chunk
     * boundary. */
    cps = wcwidth_decode_u32(utf8, n, stack, sizeof stack / sizeof stack[0], &count);
    if (cps == NULL) {
        return -1;
    }
    result = wcstwidth_u32(cps, count, ambiguous_width, term_program);
    if (cps != stack) {
        free(cps);
    }
    return result;
}
