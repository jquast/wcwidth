/*
 * Grapheme cluster segmentation for UTF-8 text.
 *
 * Implements the UAX #29 grapheme cluster boundary algorithm using pre-computed
 * Unicode interval tables.
 */
#include "wcwidth/grapheme.h"
#include "wcwidth/table_types.h"
#include "wcwidth/tables.h"
#include "wcwidth/unicode.h"
#include "wcwidth/utf8.h"

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdlib.h>

typedef enum
{
    GCB_OTHER = 0,
    GCB_CR = 1,
    GCB_LF = 2,
    GCB_CONTROL = 3,
    GCB_EXTEND = 4,
    GCB_ZWJ = 5,
    GCB_REGIONAL_INDICATOR = 6,
    GCB_PREPEND = 7,
    GCB_SPACING_MARK = 8,
    GCB_L = 9,
    GCB_V = 10,
    GCB_T = 11,
    GCB_LV = 12,
    GCB_LVT = 13,
} gcb_t;

#define MAX_GRAPHEME_SCAN 32

struct wcwidth_grapheme_iter_t
{
    const char *text;         /* original UTF-8 text buffer */
    size_t text_len;          /* original byte length */
    size_t cp_count;          /* number of pre-decoded codepoints */
    uint32_t *cp;             /* pre-decoded codepoints (malloc'd) */
    size_t *cp_offsets;       /* byte offset of each codepoint (malloc'd) */
    size_t cp_idx;            /* current codepoint index */
    size_t cluster_start_idx; /* codepoint index where current cluster starts */
    int prev_gcb;             /* GCB property of previous codepoint */
    int ri_count;             /* RI pair counter, 0 or 1 */
    bool exhausted;
};

static gcb_t gcb_of(uint32_t ucs);
static bool is_incb_linker(uint32_t ucs);
static bool is_incb_consonant(uint32_t ucs);
static bool is_incb_extend(uint32_t ucs);
static bool should_break(const uint32_t *cp, size_t cp_idx, gcb_t prev_gcb, gcb_t curr_gcb,
                         int *ri_count_out);

/*
 * Pre-decode *text* of length *len* into arrays of codepoints and byte offsets.
 * Sets *cp_out, *offsets_out, *count_out. The caller must free both arrays.
 * Returns true on success, false on allocation failure.
 */
static bool
predecode(const char *text, size_t len, uint32_t **cp_out, size_t **offsets_out, size_t *count_out)
{
    size_t cap = len; /* Each byte is at most one codepoint */
    uint32_t *cp;
    size_t *offsets;
    size_t pos = 0;
    size_t count = 0;

    cp = malloc(cap * sizeof(uint32_t));
    offsets = malloc(cap * sizeof(size_t));
    if (cp == NULL || offsets == NULL) {
        free(cp);
        free(offsets);
        return false;
    }

    while (pos < len) {
        uint32_t ucs;
        size_t blen;

        blen = wcwidth_utf8_decode_single(text + pos, len - pos, &ucs);
        if (ucs == 0xFFFD && (blen < 3 || (unsigned char) text[pos] != 0xEF)) {
            /* Malformed input: consume one byte as the raw value, matching
             * the pre-decode contract for invalid sequences. */
            ucs = (unsigned char) text[pos];
            blen = 1;
        }

        cp[count] = ucs;
        offsets[count] = pos;
        count++;
        pos += blen;
    }

    *cp_out = cp;
    *offsets_out = offsets;
    *count_out = count;
    return true;
}

static gcb_t
gcb_of(uint32_t ucs)
{
    /* Single codepoint matches */
    if (ucs == 0x000D)
        return GCB_CR;
    if (ucs == 0x000A)
        return GCB_LF;
    if (ucs == 0x200D)
        return GCB_ZWJ;

    /* Range checks via binary search */
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_CONTROL, WCWIDTH_TABLE_GRAPHEME_CONTROL_LEN))
        return GCB_CONTROL;
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_EXTEND, WCWIDTH_TABLE_GRAPHEME_EXTEND_LEN))
        return GCB_EXTEND;
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_REGIONAL_INDICATOR,
                         WCWIDTH_TABLE_GRAPHEME_REGIONAL_INDICATOR_LEN))
        return GCB_REGIONAL_INDICATOR;
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_PREPEND, WCWIDTH_TABLE_GRAPHEME_PREPEND_LEN))
        return GCB_PREPEND;
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_SPACINGMARK,
                         WCWIDTH_TABLE_GRAPHEME_SPACINGMARK_LEN))
        return GCB_SPACING_MARK;
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_L, WCWIDTH_TABLE_GRAPHEME_L_LEN))
        return GCB_L;
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_V, WCWIDTH_TABLE_GRAPHEME_V_LEN))
        return GCB_V;
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_T, WCWIDTH_TABLE_GRAPHEME_T_LEN))
        return GCB_T;
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_LV, WCWIDTH_TABLE_GRAPHEME_LV_LEN))
        return GCB_LV;
    if (wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_LVT, WCWIDTH_TABLE_GRAPHEME_LVT_LEN))
        return GCB_LVT;

    return GCB_OTHER;
}

static bool
is_incb_linker(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, WCWIDTH_TABLE_INCB_LINKER, WCWIDTH_TABLE_INCB_LINKER_LEN) != 0;
}

static bool
is_incb_consonant(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, WCWIDTH_TABLE_INCB_CONSONANT, WCWIDTH_TABLE_INCB_CONSONANT_LEN)
           != 0;
}

static bool
is_incb_extend(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, WCWIDTH_TABLE_INCB_EXTEND, WCWIDTH_TABLE_INCB_EXTEND_LEN) != 0;
}

/*
 * UAX #29 Grapheme Cluster Boundary Rules (GB3-GB999).
 *
 * *cp*: pre-decoded codepoint array
 * *cp_idx*: index of the *current* codepoint (the one AFTER the potential break)
 * *prev_gcb*: GCB property of the codepoint at cp_idx-1
 * *curr_gcb*: GCB property of the codepoint at cp_idx
 * *ri_count_out*: updated RI pair counter
 *
 * Returns true if a break should occur *before* cp[cp_idx].
 */
static bool
should_break(const uint32_t *cp, size_t cp_idx, gcb_t prev_gcb, gcb_t curr_gcb, int *ri_count_out)
{
    /* GB3: CR x LF */
    if (prev_gcb == GCB_CR && curr_gcb == GCB_LF) {
        *ri_count_out = 0;
        return false;
    }

    /* GB4: (Control|CR|LF) / */
    if (prev_gcb == GCB_CONTROL || prev_gcb == GCB_CR || prev_gcb == GCB_LF) {
        *ri_count_out = 0;
        return true;
    }

    /* GB5: / (Control|CR|LF) */
    if (curr_gcb == GCB_CONTROL || curr_gcb == GCB_CR || curr_gcb == GCB_LF) {
        *ri_count_out = 0;
        return true;
    }

    /* GB6: L x (L|V|LV|LVT) */
    if (prev_gcb == GCB_L
        && (curr_gcb == GCB_L || curr_gcb == GCB_V || curr_gcb == GCB_LV || curr_gcb == GCB_LVT)) {
        *ri_count_out = 0;
        return false;
    }

    /* GB7: (LV|V) x (V|T) */
    if ((prev_gcb == GCB_LV || prev_gcb == GCB_V) && (curr_gcb == GCB_V || curr_gcb == GCB_T)) {
        *ri_count_out = 0;
        return false;
    }

    /* GB8: (LVT|T) x T */
    if ((prev_gcb == GCB_LVT || prev_gcb == GCB_T) && curr_gcb == GCB_T) {
        *ri_count_out = 0;
        return false;
    }

    /* GB9: x (Extend|ZWJ) */
    if (curr_gcb == GCB_EXTEND) {
        *ri_count_out = 0;
        return false;
    }
    if (curr_gcb == GCB_ZWJ) {
        *ri_count_out = 0;
        return false;
    }

    /* GB9a: x SpacingMark */
    if (curr_gcb == GCB_SPACING_MARK) {
        *ri_count_out = 0;
        return false;
    }

    /* GB9b: Prepend x */
    if (prev_gcb == GCB_PREPEND) {
        *ri_count_out = 0;
        return false;
    }

    /* GB9c: Indic conjunct cluster
     * \p{InCB=Consonant} [\p{InCB=Extend}\p{InCB=Linker}]*
     *     \p{InCB=Linker} [\p{InCB=Extend}\p{InCB=Linker}]*
     *     x \p{InCB=Consonant}
     */
    if (cp_idx > 0 && is_incb_consonant(cp[cp_idx])) {
        bool has_linker = false;
        size_t i = cp_idx;

        while (i > 0) {
            i--;
            uint32_t prev_cp = cp[i];

            if (is_incb_linker(prev_cp)) {
                has_linker = true;
            }
            else if (is_incb_extend(prev_cp)) {
                /* continue scanning */
            }
            else if (is_incb_consonant(prev_cp)) {
                if (has_linker) {
                    *ri_count_out = 0;
                    return false;
                }
                break;
            }
            else {
                break;
            }
        }
    }

    /* GB11: ExtPict Extend* ZWJ x ExtPict */
    if (prev_gcb == GCB_ZWJ && cp_idx > 0) {
        uint32_t curr_ucs = cp[cp_idx];

        if (wcwidth_is_extended_pictographic(curr_ucs)) {
            size_t i = cp_idx;
            /* skip the ZWJ at cp_idx - 1 */
            if (i > 1) {
                i -= 2; /* point to codepoint before ZWJ */
                while (true) {
                    uint32_t prev_cp = cp[i];
                    gcb_t prev_prop = gcb_of(prev_cp);

                    if (prev_prop == GCB_EXTEND) {
                        if (i == 0)
                            break;
                        i--;
                    }
                    else if (wcwidth_is_extended_pictographic(prev_cp)) {
                        *ri_count_out = 0;
                        return false;
                    }
                    else {
                        break;
                    }
                }
            }
        }
    }

    /* GB12/GB13: RI x RI (pair matching) */
    if (prev_gcb == GCB_REGIONAL_INDICATOR && curr_gcb == GCB_REGIONAL_INDICATOR) {
        if (*ri_count_out % 2 == 1) {
            *ri_count_out = *ri_count_out + 1;
            return false;
        }
        *ri_count_out = 1;
        return true;
    }

    /* GB999: Any / Any */
    *ri_count_out = (curr_gcb == GCB_REGIONAL_INDICATOR) ? 1 : 0;
    return true;
}

wcwidth_grapheme_iter_t *
wcwidth_grapheme_iter_new(const char *utf8, size_t len)
{
    wcwidth_grapheme_iter_t *iter;

    iter = malloc(sizeof(wcwidth_grapheme_iter_t));
    if (iter == NULL) {
        return NULL;
    }

    iter->text = utf8;
    iter->text_len = len;

    if (len == 0) {
        iter->cp = NULL;
        iter->cp_offsets = NULL;
        iter->cp_count = 0;
        iter->cp_idx = 0;
        iter->cluster_start_idx = 0;
        iter->prev_gcb = GCB_OTHER;
        iter->ri_count = 0;
        iter->exhausted = true;
        return iter;
    }

    if (!predecode(utf8, len, &iter->cp, &iter->cp_offsets, &iter->cp_count)) {
        free(iter);
        return NULL;
    }

    /* Initialize with first codepoint's GCB */
    iter->cp_idx = 0;
    iter->cluster_start_idx = 0;
    iter->prev_gcb = gcb_of(iter->cp[0]);
    iter->ri_count = (iter->prev_gcb == GCB_REGIONAL_INDICATOR) ? 1 : 0;
    iter->exhausted = false;

    return iter;
}

void
wcwidth_grapheme_iter_free(wcwidth_grapheme_iter_t *iter)
{
    if (iter == NULL)
        return;
    free(iter->cp);
    free(iter->cp_offsets);
    free(iter);
}

const char *
wcwidth_grapheme_next(wcwidth_grapheme_iter_t *iter, size_t *out_len)
{
    const char *result;

    if (iter == NULL || iter->exhausted) {
        return NULL;
    }

    /* Empty input */
    if (iter->cp_count == 0) {
        iter->exhausted = true;
        return NULL;
    }

    /* Single codepoint input -- yield it immediately */
    if (iter->cp_count == 1) {
        iter->exhausted = true;
        if (out_len != NULL) {
            *out_len = iter->text_len;
        }
        return iter->text;
    }

    /* Advance past the first codepoint (already loaded in prev_gcb) */
    if (iter->cp_idx == 0) {
        iter->cp_idx = 1;
    }

    /* Scan forward, applying break rules */
    while (iter->cp_idx < iter->cp_count) {
        gcb_t curr_gcb = gcb_of(iter->cp[iter->cp_idx]);
        int new_ri = iter->ri_count;

        if (should_break(iter->cp, iter->cp_idx, (gcb_t) iter->prev_gcb, curr_gcb, &new_ri)) {
            /* Break before cp_idx -- yield current cluster */
            size_t start_off = iter->cp_offsets[iter->cluster_start_idx];
            size_t end_off = iter->cp_offsets[iter->cp_idx];

            result = iter->text + start_off;
            if (out_len != NULL) {
                *out_len = end_off - start_off;
            }

            iter->cluster_start_idx = iter->cp_idx;
            iter->prev_gcb = curr_gcb;
            iter->ri_count = new_ri;
            iter->cp_idx++;
            return result;
        }

        iter->ri_count = new_ri;
        iter->prev_gcb = curr_gcb;
        iter->cp_idx++;
    }

    /* Yield the final cluster */
    iter->exhausted = true;

    {
        size_t start_off = iter->cp_offsets[iter->cluster_start_idx];
        result = iter->text + start_off;
        if (out_len != NULL) {
            *out_len = iter->text_len - start_off;
        }
    }

    return result;
}

size_t
wcwidth_grapheme_boundary_before(const char *utf8, size_t len, size_t pos)
{
    uint32_t *cp = NULL;
    size_t *offsets = NULL;
    size_t cp_count = 0;
    size_t cp_pos;
    size_t safe_start;
    size_t cluster_start;
    gcb_t left_gcb;
    int ri_count;
    size_t i;

    if (pos == 0 || len == 0) {
        return 0;
    }

    /* Clamp pos to len */
    if (pos > len) {
        pos = len;
    }

    /* Pre-decode the UTF-8 text */
    if (!predecode(utf8, len, &cp, &offsets, &cp_count)) {
        return 0;
    }

    if (cp_count == 0) {
        free(cp);
        free(offsets);
        return 0;
    }

    /* Find the codepoint index corresponding to byte position *pos*.
     * We want the codepoint whose byte range covers (pos - 1), i.e. the
     * codepoint just before the break we're looking for.
     *
     * offsets[i] is the byte start of codepoint i.
     * Find the largest i such that offsets[i] < pos.
     */
    cp_pos = 0;
    for (i = 1; i < cp_count; i++) {
        if (offsets[i] >= pos) {
            break;
        }
        cp_pos = i;
    }
    /* cp_pos is now the codepoint index containing the byte at pos-1 */

    {
        uint32_t target_cp = cp[cp_pos];

        /* GB3: CR x LF -- LF after CR is part of same cluster */
        if (target_cp == 0x0A && cp_pos > 0 && cp[cp_pos - 1] == 0x0D) {
            size_t result = offsets[cp_pos - 1];
            free(cp);
            free(offsets);
            return result;
        }

        /* Fast path: ASCII (except LF) starts its own cluster */
        if (target_cp < 0x80) {
            size_t result = offsets[cp_pos];

            /* GB9b: Check for preceding PREPEND */
            if (cp_pos > 0 && target_cp >= 0x20) {
                uint32_t prev_cp_val = cp[cp_pos - 1];
                if (prev_cp_val >= 0x80 && gcb_of(prev_cp_val) == GCB_PREPEND) {
                    /* Recurse to find the PREPEND's own cluster start */
                    size_t prepend_off = offsets[cp_pos - 1];
                    result = wcwidth_grapheme_boundary_before(utf8, len, prepend_off);
                }
            }
            free(cp);
            free(offsets);
            return result;
        }
    }

    /* Scan backward from cp_pos to find a safe starting point */
    safe_start = cp_pos;
    while (safe_start > 0 && (cp_pos - safe_start) < MAX_GRAPHEME_SCAN) {
        uint32_t scp = cp[safe_start];
        if (0x20 <= scp && scp < 0x80) { /* ASCII always starts a cluster */
            break;
        }
        if (gcb_of(scp) == GCB_CONTROL) { /* GB4 */
            break;
        }
        safe_start--;
    }

    /* Verify forward to find the actual cluster boundary */
    cluster_start = safe_start;
    left_gcb = gcb_of(cp[safe_start]);
    ri_count = (left_gcb == GCB_REGIONAL_INDICATOR) ? 1 : 0;

    for (i = safe_start + 1; i <= cp_pos; i++) {
        gcb_t right_gcb = gcb_of(cp[i]);
        int new_ri = ri_count;

        if (should_break(cp, i, left_gcb, right_gcb, &new_ri)) {
            cluster_start = i;
        }
        ri_count = new_ri;
        left_gcb = right_gcb;
    }

    {
        size_t result = offsets[cluster_start];
        free(cp);
        free(offsets);
        return result;
    }
}
