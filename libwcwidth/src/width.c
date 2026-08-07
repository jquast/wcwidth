/*
 * Terminal-aware string width with escape sequence parsing and cursor tracking.
 */
#include "wcwidth/width.h"
#include "wcwidth/escape.h"
#include "wcwidth/text_sizing.h"
#include "wcwidth/tables.h"
#include "wcwidth/generated_tables.h"
#include "wcwidth/unicode.h"
#include "wcwidth/utf8.h"
#include "wcwidth/wcwidth.h"
#include "wcwidth/terminal_override.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define ESC 0x1b

/* Maximum stack buffer for UTF-8 encoding in width_u32().
 * Each codepoint encodes to at most 4 UTF-8 bytes. */
#define U32_TO_UTF8_MAX_LEN 4096

/* Threshold for fast-path downgrade: strings longer than this are checked
 * for cursor-movement controls; when absent, mode downgrades to 'ignore'. */
#define FAST_PATH_MIN_LEN 20

const wcwidth_width_opts_t WCWIDTH_WIDTH_OPTS_DEFAULT = {
    .tabsize = 8,
    .ambiguous_width = 1,
    .term_program = NULL,
};

static bool
is_illegal_ctrl(uint32_t ucs)
{
    if (ucs >= 1 && ucs <= 6) {
        return true; /* SOH, STX, ETX, EOT, ENQ, ACK */
    }
    if (ucs >= 16 && ucs <= 26) {
        return true; /* DLE through SUB */
    }
    if (ucs >= 28 && ucs <= 31) {
        return true; /* FS, GS, RS, US */
    }
    if (ucs == 0x7F) {
        return true; /* DEL */
    }
    if (ucs >= 0x80 && ucs <= 0x9F) {
        return true; /* C1 control characters */
    }
    return false;
}

static bool
is_vertical_ctrl(uint32_t ucs)
{
    return ucs == 0x0A || ucs == 0x0B || ucs == 0x0C;
}

static bool
is_horizontal_ctrl(uint32_t ucs)
{
    return ucs == 0x08 || ucs == 0x09 || ucs == 0x0D;
}

/*
 * Decode the codepoint immediately preceding byte position pos.  Returns its
 * starting offset, or (size_t) -1 at the start of the string.
 */
static size_t
prev_codepoint(const char *text, size_t pos, uint32_t *cp_out)
{
    size_t j = pos;
    if (j == 0) {
        return (size_t) -1;
    }
    do {
        j--;
    } while (j > 0 && ((unsigned char) text[j] & 0xC0) == 0x80);
    wcwidth_utf8_decode_single(text + j, pos - j, cp_out);
    return j;
}

static size_t
utf8_encode_single(uint32_t ucs, char *out)
{
    if (ucs < 0x80) {
        out[0] = (char) ucs;
        return 1;
    }
    if (ucs < 0x800) {
        out[0] = (char) (0xC0 | (ucs >> 6));
        out[1] = (char) (0x80 | (ucs & 0x3F));
        return 2;
    }
    if (ucs < 0x10000) {
        out[0] = (char) (0xE0 | (ucs >> 12));
        out[1] = (char) (0x80 | ((ucs >> 6) & 0x3F));
        out[2] = (char) (0x80 | (ucs & 0x3F));
        return 3;
    }
    out[0] = (char) (0xF0 | (ucs >> 18));
    out[1] = (char) (0x80 | ((ucs >> 12) & 0x3F));
    out[2] = (char) (0x80 | ((ucs >> 6) & 0x3F));
    out[3] = (char) (0x80 | (ucs & 0x3F));
    return 4;
}

static bool
_needs_cursor_tracking(const char *text, size_t n)
{
    size_t i;

    for (i = 0; i < n; i++) {
        unsigned char ch = (unsigned char) text[i];

        if (ch == 0x08 || ch == 0x09 || ch == 0x0D) {
            return true; /* BS, TAB, CR */
        }

        if (ch == ESC) {
            wcwidth_esc_result_t result;
            if (wcwidth_escape_classify(text, n, i, &result)) {
                if (result.type == WCWIDTH_ESC_CUF || result.type == WCWIDTH_ESC_CUB
                    || result.type == WCWIDTH_ESC_HPA || result.type == WCWIDTH_ESC_OSC66) {
                    return true;
                }
                i += result.length - 1; /* -1 because loop does i++ */
            }
        }
    }

    return false;
}

/* Number of codepoints in *text*, mirroring the pure implementation's
 * len() used for the parse-to-ignore fast-path threshold. */
static size_t
utf8_char_count(const char *text, size_t n)
{
    size_t count = 0, i = 0;

    while (i < n) {
        uint32_t cp;
        i += wcwidth_utf8_decode_single(text + i, n - i, &cp);
        count++;
    }
    return count;
}

static size_t
strip_controls(const char *text, size_t text_len, char *out, size_t out_cap, size_t *out_len)
{
    size_t src = 0;
    size_t written = 0;

    while (src < text_len) {
        unsigned char b = (unsigned char) text[src];

        /* C0 control (including DEL) or C1 lead byte */
        if (b < 0x20 || b == 0x7F) {
            src++;
            continue;
        }

        /* C1 control (U+0080-U+009F): 2-byte UTF-8 sequence starting with C2 */
        if (b == 0xC2 && src + 1 < text_len) {
            unsigned char b2 = (unsigned char) text[src + 1];
            if (b2 >= 0x80 && b2 <= 0x9F) {
                src += 2;
                continue;
            }
        }

        /* Copy visible character */
        if (written < out_cap) {
            out[written] = text[src];
        }
        written++;
        src++;
    }

    if (out_cap > 0) {
        size_t term_pos = (written < out_cap) ? written : (out_cap - 1);
        out[term_pos] = '\0';
    }

    if (out_len != NULL) {
        *out_len = (written < out_cap) ? written : out_cap;
    }

    return written;
}

static int
_width_ignore(const char *text, size_t n, int ambiguous_width, const char *term_program, int *error)
{
    char stripped[4096];
    size_t stripped_len = 0;
    size_t needed;
    int result;

    (void) error;

    /* Strip escape sequences first (preserves OSC 66 inner text). */
    needed = wcwidth_escape_strip(text, n, stripped, sizeof(stripped), &stripped_len);

    if (needed > sizeof(stripped)) {
        /* Buffer too small -- strip in two passes. */
        char *buf = (char *) malloc(needed + 1);
        if (buf == NULL) {
            return -1;
        }
        wcwidth_escape_strip(text, n, buf, needed + 1, &stripped_len);
        /* Now strip control characters */
        {
            size_t ctrl_stripped_len;
            size_t ctrl_needed =
                strip_controls(buf, stripped_len, stripped, sizeof(stripped), &ctrl_stripped_len);
            if (ctrl_needed > sizeof(stripped)) {
                char *buf2 = (char *) malloc(ctrl_needed + 1);
                if (buf2 == NULL) {
                    free(buf);
                    return -1;
                }
                strip_controls(buf, stripped_len, buf2, ctrl_needed + 1, &ctrl_stripped_len);
                if (term_program != NULL && term_program[0] != '\0') {
                    result = wcstwidth_u8(buf2, ctrl_stripped_len, ambiguous_width, term_program);
                }
                else {
                    result = wcswidth_u8(buf2, ctrl_stripped_len, ambiguous_width);
                }
                free(buf2);
                free(buf);
                return result;
            }
            if (term_program != NULL && term_program[0] != '\0') {
                result = wcstwidth_u8(stripped, ctrl_stripped_len, ambiguous_width, term_program);
            }
            else {
                result = wcswidth_u8(stripped, ctrl_stripped_len, ambiguous_width);
            }
            free(buf);
            return result;
        }
    }

    /* Strip control characters from escape-stripped text. */
    {
        char ctrl_stripped[4096];
        size_t ctrl_stripped_len;
        size_t ctrl_needed = strip_controls(stripped, stripped_len, ctrl_stripped,
                                            sizeof(ctrl_stripped), &ctrl_stripped_len);
        if (ctrl_needed > sizeof(ctrl_stripped)) {
            char *buf = (char *) malloc(ctrl_needed + 1);
            if (buf == NULL) {
                return -1;
            }
            strip_controls(stripped, stripped_len, buf, ctrl_needed + 1, &ctrl_stripped_len);
            if (term_program != NULL && term_program[0] != '\0') {
                result = wcstwidth_u8(buf, ctrl_stripped_len, ambiguous_width, term_program);
            }
            else {
                result = wcswidth_u8(buf, ctrl_stripped_len, ambiguous_width);
            }
            free(buf);
            return result;
        }
        if (term_program != NULL && term_program[0] != '\0') {
            return wcstwidth_u8(ctrl_stripped, ctrl_stripped_len, ambiguous_width, term_program);
        }
        return wcswidth_u8(ctrl_stripped, ctrl_stripped_len, ambiguous_width);
    }
}

/* Commit a pending grapheme cluster to the running column total. */
static void
flush_cluster(int *current_col, int *max_extent, int *cluster_width)
{
    if (*cluster_width) {
        *current_col += *cluster_width;
        if (*current_col > *max_extent) {
            *max_extent = *current_col;
        }
        *cluster_width = 0;
    }
}

static int
_width_parse(const char *text, size_t n, bool strict, int tabsize, int ambiguous_width,
             const char *term_program, int *error)
{
    size_t idx;
    int current_col;
    int max_extent;
    int cluster_width;
    int last_measured_idx;
    uint32_t last_measured_ucs;
    int last_measured_w;
    bool prev_was_virama;
    const wcwidth_terminal_override_t *term;
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
    int cluster_start;
    int col_before_cluster;

    term = wcwidth_resolve_terminal(term_program);
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

    /* Fast path: pure ASCII printable (no control chars, no high bytes). */
    {
        size_t i;
        bool all_ascii = true;
        for (i = 0; i < n; i++) {
            unsigned char ch = (unsigned char) text[i];
            if (ch < 32 || ch >= 0x7f) {
                all_ascii = false;
                break;
            }
        }
        if (all_ascii) {
            return (int) n;
        }
    }

    current_col = 0;
    max_extent = 0;
    idx = 0;
    cluster_width = 0;
    last_measured_idx = -2;
    last_measured_ucs = 0;
    last_measured_w = 0;
    prev_was_virama = false;
    cluster_start = -1;
    col_before_cluster = 0;

    while (idx < n) {
        unsigned char b = (unsigned char) text[idx];

        if (b == ESC) {
            flush_cluster(&current_col, &max_extent, &cluster_width);

            {
                wcwidth_esc_result_t result;
                if (!wcwidth_escape_classify(text, n, idx, &result)) {
                    /* Should not happen since text[idx] == ESC. */
                    idx++;
                }
                else {
                    switch (result.type) {
                        case WCWIDTH_ESC_SGR:
                        case WCWIDTH_ESC_OTHER:
                        case WCWIDTH_ESC_UNRECOGNIZED:
                        case WCWIDTH_ESC_OSC8_OPEN:
                        case WCWIDTH_ESC_OSC8_CLOSE:
                            /* Zero-width sequences. */
                            break;

                        case WCWIDTH_ESC_CUF:
                            current_col += result.cursor_n;
                            break;

                        case WCWIDTH_ESC_CUB:
                            if (strict && result.cursor_n > current_col) {
                                *error = WCWIDTH_ERROR_CURSOR_LEFT_EXCEED;
                                return -1;
                            }
                            current_col -= result.cursor_n;
                            if (current_col < 0) {
                                current_col = 0;
                            }
                            break;

                        case WCWIDTH_ESC_HPA:
                            if (strict) {
                                *error = WCWIDTH_ERROR_CURSOR_LEFT_ABSOLUTE;
                                return -1;
                            }
                            current_col = result.cursor_n - 1;
                            break;

                        case WCWIDTH_ESC_INDETERMINATE:
                            if (strict) {
                                *error = WCWIDTH_ERROR_INDETERMINATE;
                                return -1;
                            }
                            break;

                        case WCWIDTH_ESC_OSC66: {
                            wcwidth_text_sizing_t ts;
                            wcwidth_ts_from_esc(&result, &ts);
                            current_col += wcwidth_ts_display_width(&ts, ambiguous_width);
                            break;
                        }

                        case WCWIDTH_ESC_NONE:
                            break;
                    }

                    idx += result.length;
                }
            }

            /* Escape sequences break VS16/VS15 adjacency.  prev_was_virama
             * survives (as in the pure reference): control characters and
             * escapes do not end a pending virama conjunct. */
            last_measured_idx = -2;
            last_measured_ucs = 0;
            cluster_start = -1;

            if (current_col > max_extent) {
                max_extent = current_col;
            }
            continue;
        }

        if (b < 0x20) {
            uint32_t ucs = b;

            flush_cluster(&current_col, &max_extent, &cluster_width);

            if (is_illegal_ctrl(ucs)) {
                if (strict) {
                    *error = WCWIDTH_ERROR_ILLEGAL_CTRL;
                    return -1;
                }
            }
            else if (is_vertical_ctrl(ucs)) {
                if (strict) {
                    *error = WCWIDTH_ERROR_VERTICAL_CTRL;
                    return -1;
                }
            }
            else if (is_horizontal_ctrl(ucs)) {
                if (ucs == 0x09) {
                    if (tabsize > 0) {
                        current_col += tabsize - (current_col % tabsize);
                    }
                }
                else if (ucs == 0x08) {
                    if (current_col > 0) {
                        current_col -= 1;
                    }
                }
                else {
                    if (strict) {
                        *error = WCWIDTH_ERROR_HORIZONTAL_MOVEMENT;
                        return -1;
                    }
                    current_col = 0;
                }
            }
            /* ZERO_WIDTH_CTRL: NUL(0), BEL(7), SO(0x0E), SI(0x0F) -- no column change. */

            if (current_col > max_extent) {
                max_extent = current_col;
            }

            idx++;
            last_measured_idx = -2;
            last_measured_ucs = 0;
            cluster_start = -1;
            continue;
        }

        if (b == 0x7F) {
            flush_cluster(&current_col, &max_extent, &cluster_width);
            if (strict) {
                *error = WCWIDTH_ERROR_ILLEGAL_CTRL;
                return -1;
            }
            idx++;
            last_measured_idx = -2;
            last_measured_ucs = 0;
            cluster_start = -1;
            continue;
        }

        {
            uint32_t ucs;
            size_t consumed = wcwidth_utf8_decode_single(text + idx, n - idx, &ucs);

            if (ucs >= 0x80 && ucs < 0xA0) {
                flush_cluster(&current_col, &max_extent, &cluster_width);
                if (strict) {
                    *error = WCWIDTH_ERROR_ILLEGAL_CTRL;
                    return -1;
                }
                idx += consumed;
                last_measured_idx = -2;
                last_measured_ucs = 0;
                cluster_start = -1;
                continue;
            }

            /* 5. Inline grapheme-clustering: ZWJ, Virama, VS16, Regional
             * Indicators, Fitzpatrick, Mc, wcwidth */
            if (ucs == 0x200D) {
                if (prev_was_virama) {
                    idx += consumed;
                }
                else if (idx + consumed < n) {
                    /* Check for a terminal grapheme override when the base
                     * char is ExtPict/RI. */
                    if (has_graphemes && last_measured_idx >= 0
                        && wcwidth_is_emoji_zwj_set(last_measured_ucs)) {
                        size_t cluster_end =
                            wcwidth_scan_zwj_cluster_end_u8(text, n, (size_t) last_measured_idx);
                        uint32_t cluster_cps[32];
                        size_t cluster_cps_len = wcwidth_decode_cluster(
                            text, (size_t) last_measured_idx, cluster_end, cluster_cps, 32);
                        if (cluster_cps_len < 32) {
                            int override_w = wcwidth_grapheme_override_lookup(term, cluster_cps,
                                                                              cluster_cps_len);
                            if (override_w >= 0) {
                                current_col += override_w - last_measured_w;
                                if (current_col > max_extent) {
                                    max_extent = current_col;
                                }
                                last_measured_idx = -2;
                                last_measured_ucs = 0;
                                last_measured_w = 0;
                                prev_was_virama = false;
                                cluster_start = -1;
                                idx = cluster_end;
                                continue;
                            }
                        }
                    }
                    /* No override; ZWJ breaks VS16/VS15 adjacency. */
                    last_measured_w = 0;
                    prev_was_virama = false;
                    idx += consumed;
                    {
                        /* Skip the next codepoint (they form a zero-width unit). */
                        uint32_t next_ucs;
                        size_t next_consumed =
                            wcwidth_utf8_decode_single(text + idx, n - idx, &next_ucs);
                        idx += next_consumed;
                    }
                }
                else {
                    prev_was_virama = false;
                    idx += consumed;
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
                last_measured_idx = -2;
                idx += consumed;
                continue;
            }

            if (ucs == 0xFE0E && last_measured_idx >= 0) {
                bool vs15_narrow =
                    wcwidth_bisearch(last_measured_ucs, WCWIDTH_TABLE_VS15, WCWIDTH_TABLE_VS15_LEN)
                    != 0;
                if (wcwidth_bisearch(last_measured_ucs, vs15_wider, vs15_wider_len)) {
                    vs15_narrow = false;
                }
                if (vs15_narrow && last_measured_w == 2) {
                    /* Not clamped: the pending cluster's width is added on
                     * flush, so a negative column here yields the narrowed
                     * width. */
                    current_col -= 1;
                }
                idx += consumed;
                continue;
            }

            /* 7. Regional Indicator & Fitzpatrick (both above BMP) */
            if (ucs > 0xFFFF) {
                if (wcwidth_is_regional_indicator(ucs)) {
                    /* Count consecutive preceding Regional Indicators; an odd
                     * count pairs this one with the previous (zero-width). */
                    int ri_before = 0;
                    size_t j = idx;
                    for (;;) {
                        uint32_t prev_ucs;
                        j = prev_codepoint(text, j, &prev_ucs);
                        if (j == (size_t) -1 || !wcwidth_is_regional_indicator(prev_ucs)) {
                            break;
                        }
                        ri_before++;
                    }
                    if (ri_before % 2 == 1) {
                        last_measured_ucs = ucs;
                        idx += consumed;
                        continue;
                    }
                }
                else if (wcwidth_is_fitzpatrick(ucs) && last_measured_ucs != 0
                         && wcwidth_is_emoji_zwj_set(last_measured_ucs)) {
                    idx += consumed;
                    continue;
                }
            }

            /* 8. Normal character: measure with wcwidth. */
            {
                int w = wcwidth_u32(ucs, ambiguous_width);
                if (w < 0) {
                    /* Non-printable: shouldn't happen after our C0/C1 checks,
                     * but handle gracefully. */
                    idx += consumed;
                    continue;
                }
                /* Apply single-codepoint terminal overrides (pre-merged sets). */
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
                if (w > 0) {
                    /* virama+consonant extends the current cluster; otherwise
                     * flush the previous cluster, checking grapheme overrides. */
                    if (prev_was_virama) {
                        cluster_width = 2;
                    }
                    else if (cluster_width) {
                        bool flushed = false;
                        if (has_graphemes && cluster_start >= 0) {
                            uint32_t candidate_cps[32];
                            size_t candidate_len = wcwidth_decode_cluster(
                                text, (size_t) cluster_start, idx + consumed, candidate_cps, 32);
                            if (candidate_len < 32) {
                                /* Two-phase: the candidate (cluster + current
                                 * char) matches clusters ending at this char;
                                 * the cluster alone matches C+Mc overrides
                                 * stored without the trailing Mc.  Only the
                                 * candidate match flushes; the cluster match
                                 * continues with the current char. */
                                int override_w = wcwidth_grapheme_override_lookup(
                                    term, candidate_cps, candidate_len);
                                if (override_w >= 0) {
                                    current_col = col_before_cluster + override_w;
                                    if (current_col > max_extent) {
                                        max_extent = current_col;
                                    }
                                    flushed = true;
                                    cluster_width = 0;
                                }
                                else {
                                    uint32_t cluster_cps[32];
                                    size_t cluster_len = wcwidth_decode_cluster(
                                        text, (size_t) cluster_start, idx, cluster_cps, 32);
                                    if (cluster_len < 32) {
                                        int cluster_w = wcwidth_grapheme_override_lookup(
                                            term, cluster_cps, cluster_len);
                                        if (cluster_w >= 0) {
                                            current_col = col_before_cluster + cluster_w;
                                            if (current_col > max_extent) {
                                                max_extent = current_col;
                                            }
                                        }
                                        else {
                                            current_col += cluster_width;
                                        }
                                    }
                                    else {
                                        current_col += cluster_width;
                                    }
                                }
                            }
                            else {
                                current_col += cluster_width;
                            }
                        }
                        else {
                            current_col += cluster_width;
                        }
                        if (current_col > max_extent) {
                            max_extent = current_col;
                        }
                        if (!flushed) {
                            cluster_width = w;
                            cluster_start = (int) idx;
                            col_before_cluster = current_col;
                        }
                    }
                    else {
                        cluster_width = w;
                        cluster_start = (int) idx;
                        col_before_cluster = current_col;
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
                    /* Spacing Combining Mark (Mc) -- extends cluster to width 2. */
                    cluster_width = 2;
                    last_measured_idx = -2;
                    prev_was_virama = false;
                }
                else {
                    prev_was_virama = false;
                }
            }

            idx += consumed;
        }
    }

    /* Flush final pending cluster. */
    if (cluster_width) {
        if (has_graphemes && cluster_start >= 0) {
            uint32_t cluster_cps[32];
            size_t cluster_len =
                wcwidth_decode_cluster(text, (size_t) cluster_start, n, cluster_cps, 32);
            if (cluster_len < 32) {
                int override_w = wcwidth_grapheme_override_lookup(term, cluster_cps, cluster_len);
                if (override_w >= 0) {
                    current_col = col_before_cluster + override_w;
                }
                else {
                    current_col += cluster_width;
                }
            }
            else {
                current_col += cluster_width;
            }
        }
        else {
            current_col += cluster_width;
        }
        if (current_col > max_extent) {
            max_extent = current_col;
        }
    }

    return max_extent;
}

int
width_u8(const char *utf8, size_t n, wcwidth_control_mode_t mode, const wcwidth_width_opts_t *opts,
         int *error)
{
    int tabsize;
    int ambiguous_width;
    const char *term_program;
    wcwidth_control_mode_t effective_mode;

    if (opts == NULL) {
        opts = &WCWIDTH_WIDTH_OPTS_DEFAULT;
    }

    tabsize = opts->tabsize;
    ambiguous_width = opts->ambiguous_width;
    term_program = opts->term_program;

    if (error != NULL) {
        *error = WCWIDTH_ERROR_NONE;
    }

    if (utf8 == NULL) {
        return 0;
    }

    /* Determine byte length. */
    if (n == (size_t) -1) {
        n = strlen(utf8);
    }

    if (n == 0) {
        return 0;
    }

    effective_mode = mode;

    /* Fast-path downgrade: in PARSE mode, if text has no cursor movement,
     * downgrade to IGNORE for performance.  The threshold counts codepoints
     * like the pure implementation's len(), not bytes. */
    if (effective_mode == WCWIDTH_PARSE && utf8_char_count(utf8, n) > FAST_PATH_MIN_LEN) {
        if (!_needs_cursor_tracking(utf8, n)) {
            effective_mode = WCWIDTH_IGNORE;
        }
    }

    if (effective_mode == WCWIDTH_IGNORE) {
        return _width_ignore(utf8, n, ambiguous_width, term_program, error);
    }

    return _width_parse(utf8, n, effective_mode == WCWIDTH_STRICT, tabsize, ambiguous_width,
                        term_program, error);
}

int
width_u32(const uint32_t *codepoints, size_t n, wcwidth_control_mode_t mode,
          const wcwidth_width_opts_t *opts, int *error)
{
    char buf[U32_TO_UTF8_MAX_LEN];
    size_t buf_used;
    size_t i;
    size_t needed;

    if (error != NULL) {
        *error = WCWIDTH_ERROR_NONE;
    }

    if (codepoints == NULL || n == 0) {
        return 0;
    }

    /* Encode u32 array to UTF-8. */
    buf_used = 0;
    needed = 0;
    for (i = 0; i < n; i++) {
        char tmp[4];
        size_t enc_len = utf8_encode_single(codepoints[i], tmp);
        needed += enc_len;
        if (buf_used + enc_len <= sizeof(buf)) {
            memcpy(buf + buf_used, tmp, enc_len);
            buf_used += enc_len;
        }
    }

    if (needed <= sizeof(buf)) {
        return width_u8(buf, buf_used, mode, opts, error);
    }

    /* Stack buffer too small -- allocate heap buffer. */
    {
        char *heap_buf = (char *) malloc(needed);
        int result;

        if (heap_buf == NULL) {
            if (error != NULL) {
                *error = WCWIDTH_ERROR_INDETERMINATE;
            }
            return -1;
        }

        buf_used = 0;
        for (i = 0; i < n; i++) {
            size_t enc_len = utf8_encode_single(codepoints[i], heap_buf + buf_used);
            buf_used += enc_len;
        }

        result = width_u8(heap_buf, buf_used, mode, opts, error);
        free(heap_buf);
        return result;
    }
}
