/*
 * Terminal-aware string width with escape sequence parsing and cursor tracking.
 */
#include "wcwidth/width.h"
#include "wcwidth/escape.h"
#include "wcwidth/text_sizing.h"
#include "wcwidth/table_types.h"
#include "wcwidth/tables.h"
#include "wcwidth/unicode.h"
#include "wcwidth/utf8.h"
#include "wcwidth/wcwidth.h"
#include "wcwidth/terminal_override.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

#define ESC 0x1b

/* Threshold for fast-path downgrade: strings longer than this are checked
 * for cursor-movement controls; when absent, mode downgrades to 'ignore'. */
#define FAST_PATH_MIN_LEN 20

/*
 * Scratch size for the strip passes in _width_ignore()/_width_ignore_u32().
 *
 * Both functions already fall back to malloc for longer input, so this only
 * decides where that fallback starts.  It is deliberately modest: two of
 * these live in one _width_ignore() frame, and musl's default thread stack
 * is 128 KiB -- the configuration most Python container images run on.  A
 * kilobyte still covers any realistic terminal line.
 */
#define WCWIDTH_STRIP_SCRATCH 1024
#define WCWIDTH_STRIP_SCRATCH_U32 512

/* Printable-ASCII fast path.
 *
 * Every codepoint in U+0020..U+007E measures 1 cell: none appears in the
 * wide, zero-width, or ambiguous tables, and no terminal override set
 * touches that range.  Such text also contains no escape sequence, no
 * control code, and no grapheme cluster spanning more than one codepoint,
 * so its width is exactly the number of codepoints in every control mode
 * -- including WCWIDTH_STRICT, which has nothing to reject.
 *
 * Both scans stop at the first byte/codepoint outside the range, so text
 * that does not qualify pays only for the prefix it shares with it. */
static bool
_all_printable_ascii_u8(const char *text, size_t n)
{
    size_t i;
    for (i = 0; i < n; i++) {
        unsigned char ch = (unsigned char) text[i];
        if (ch < 0x20 || ch >= 0x7f) {
            return false;
        }
    }
    return true;
}

static bool
_all_printable_ascii_u32(const uint32_t *cp, size_t n)
{
    size_t i;
    for (i = 0; i < n; i++) {
        if (cp[i] < 0x20 || cp[i] >= 0x7f) {
            return false;
        }
    }
    return true;
}

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

/*
 * Codepoint-array variant of _needs_cursor_tracking().
 * Returns true when *cp* contains BS, TAB, CR, CUF, CUB, HPA, or OSC 66.
 */
static bool
_needs_cursor_tracking_u32(const uint32_t *cp, size_t n)
{
    size_t i;

    for (i = 0; i < n; i++) {
        if (cp[i] == 0x08 || cp[i] == 0x09 || cp[i] == 0x0D) {
            return true;
        }
        if (cp[i] == ESC && i + 1 < n) {
            uint32_t next = cp[i + 1];
            if (next == '[') {
                size_t j;
                for (j = i + 2; j < n; j++) {
                    uint32_t c = cp[j];
                    if (c >= 0x40 && c <= 0x7E) {
                        if (c == 'C' || c == 'D' || c == 'G') {
                            return true;
                        }
                        break;
                    }
                    if (c < 0x30 || c > 0x3F) {
                        break;
                    }
                }
            }
            else if (next == ']' && i + 4 < n
                     && cp[i + 2] == '6' && cp[i + 3] == '6' && cp[i + 4] == ';') {
                return true;
            }
        }
    }

    return false;
}

/* Number of codepoints in *text*, mirroring the Python implementation's
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
        /* On truncation the last byte holds the NUL, so only out_cap - 1
         * bytes of text are usable -- as in wcwidth_escape_strip(). */
        *out_len = (written < out_cap) ? written : (out_cap > 0 ? out_cap - 1 : 0);
    }

    return written;
}

static int
_width_ignore(const char *text, size_t n, int ambiguous_width, const char *term_program, int *error)
{
    char stripped[WCWIDTH_STRIP_SCRATCH];
    size_t stripped_len = 0;
    size_t needed;
    int result;

    (void) error;

    /* Strip escape sequences first (preserves OSC 66 inner text). */
    needed = wcwidth_escape_strip(text, n, stripped, sizeof(stripped), &stripped_len);

    if (needed >= sizeof(stripped)) {
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
            if (ctrl_needed >= sizeof(stripped)) {
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
        char ctrl_stripped[WCWIDTH_STRIP_SCRATCH];
        size_t ctrl_stripped_len;
        size_t ctrl_needed = strip_controls(stripped, stripped_len, ctrl_stripped,
                                            sizeof(ctrl_stripped), &ctrl_stripped_len);
        if (ctrl_needed >= sizeof(ctrl_stripped)) {
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


/*
 * Scan an OSC/APC/DCS/PM body on the codepoint path, from *start* (the first
 * byte after the two-codepoint introducer).
 *
 * These payloads may hold codepoints outside ASCII, so they cannot go through
 * the byte classifier over an encoded ASCII run.  Both the width parser and
 * the ignore-mode stripper call this, so the termination rule -- BEL, ST, or
 * a bare ESC ending the body unterminated, matching parse_osc() in escape.c
 * and the Python parser's [^\x07\x1b]* body -- exists once.
 *
 * Returns true when terminated, filling *term_start (first codepoint of the
 * terminator) and *term_end (one past it).
 */
static bool
scan_osc_body_u32(const uint32_t *cp, size_t n, size_t start, size_t *term_start,
                  size_t *term_end)
{
    size_t pos = start;

    *term_start = 0;
    *term_end = 0;
    while (pos < n) {
        if (cp[pos] == 0x07) {
            *term_start = pos;
            *term_end = pos + 1;
            return true;
        }
        if (cp[pos] == ESC) {
            if (pos + 1 < n && cp[pos + 1] == '\\') {
                *term_start = pos;
                *term_end = pos + 2;
                return true;
            }
            return false;
        }
        pos++;
    }
    return false;
}

/*
 * Number of codepoints spanned by a non-OSC escape at cp[idx].
 *
 * CSI, nF, Fe and the rest are ASCII-only, so an encoded copy of the ASCII
 * run can go straight to the byte classifier and its byte length is the
 * codepoint count.  Delegating keeps rules like "an unterminated CSI consumes
 * only ESC [" in one place; a second hand-written copy of that rule is what
 * previously made IGNORE mode disagree with the byte path.
 *
 * ESC ( / ESC ) designate a single character that may itself be non-ASCII, so
 * they are counted directly rather than through the ASCII run.
 */
static size_t
escape_span_u32(const uint32_t *cp, size_t n, size_t idx)
{
    char buf[64];
    size_t cap = 16;
    wcwidth_esc_result_t result;

    if (idx + 1 < n && (cp[idx + 1] == '(' || cp[idx + 1] == ')')) {
        /* ESC, the designator, and the designated character.  With no
         * character to designate the sequence is truncated and only the ESC
         * is zero-width, as parse_charset() has it. */
        return (idx + 2 < n) ? 3 : 1;
    }

    /*
     * Copy in two steps.  Nearly every sequence here is under 16 codepoints,
     * and copying the full 64 for each one dominated the cost on SGR-dense
     * text.  A classification that consumed the whole copy may have been
     * truncated by it, so only then is the wider copy needed.
     */
    for (;;) {
        size_t j = 0;

        while (j < cap && idx + j < n && cp[idx + j] < 0x80) {
            buf[j] = (char) cp[idx + j];
            j++;
        }
        if (j == 0 || !wcwidth_escape_classify(buf, j, 0, &result) || result.length == 0) {
            return 1;
        }
        if (result.length < j || idx + j >= n || cap == sizeof(buf)) {
            return result.length;
        }
        cap = sizeof(buf);
    }
}

/*
 * Strip escape sequences and C0/C1 controls from a codepoint array, writing
 * the survivors to *out*.  Returns the count that would be written if out_cap
 * were large enough, mirroring wcwidth_escape_strip().
 */
static size_t
strip_ignore_u32(const uint32_t *cp, size_t n, uint32_t *out, size_t out_cap)
{
    size_t idx = 0;
    size_t written = 0;

    while (idx < n) {
        uint32_t ucs = cp[idx];

        if (ucs == ESC) {
            if (idx + 1 < n
                && (cp[idx + 1] == ']' || cp[idx + 1] == '_' || cp[idx + 1] == 'P'
                    || cp[idx + 1] == '^')) {
                size_t term_start, term_end;
                bool terminated = scan_osc_body_u32(cp, n, idx + 2, &term_start, &term_end);

                if (!terminated) {
                    idx += 2; /* introducer only, as parse_osc() does */
                    continue;
                }
                /* OSC 66 keeps its display text; every other OSC-family
                 * sequence is dropped whole. */
                if (cp[idx + 1] == ']' && idx + 4 < n && cp[idx + 2] == '6'
                    && cp[idx + 3] == '6' && cp[idx + 4] == ';') {
                    size_t semi = idx + 5;
                    size_t k;

                    while (semi < term_start && cp[semi] != ';') {
                        semi++;
                    }
                    if (semi < term_start) {
                        for (k = semi + 1; k < term_start; k++) {
                            uint32_t t = cp[k];

                            /* The display text is kept, but controls inside it
                             * are still dropped: the byte path reaches the
                             * same result by running strip_controls() over
                             * wcwidth_escape_strip()'s output, and a control
                             * left here would make wcswidth_u32() return -1. */
                            if (t < 0x20 || t == 0x7f || (t >= 0x80 && t <= 0x9f)) {
                                continue;
                            }
                            if (written < out_cap) {
                                out[written] = t;
                            }
                            written++;
                        }
                    }
                }
                idx = term_end;
                continue;
            }
            idx += escape_span_u32(cp, n, idx);
            continue;
        }

        /* Drop C0 and C1 controls, keep everything else. */
        if (ucs >= 0x20 && ucs != 0x7f && !(ucs >= 0x80 && ucs <= 0x9f)) {
            if (written < out_cap) {
                out[written] = ucs;
            }
            written++;
        }
        idx++;
    }
    return written;
}

static int
_width_ignore_u32(const uint32_t *cp, size_t n, int ambiguous_width, const char *term_program,
                  int *error)
{
    uint32_t stack[WCWIDTH_STRIP_SCRATCH_U32];
    uint32_t *out = stack;
    size_t cap = sizeof(stack) / sizeof(stack[0]);
    size_t needed;
    int result;

    (void) error;

    needed = strip_ignore_u32(cp, n, stack, cap);
    if (needed > cap) {
        out = (uint32_t *) malloc(needed * sizeof(uint32_t));
        if (out == NULL) {
            return -1;
        }
        strip_ignore_u32(cp, n, out, needed);
    }

    if (term_program != NULL && term_program[0] != '\0') {
        result = wcstwidth_u32(out, needed, ambiguous_width, term_program);
    }
    else {
        result = wcswidth_u32(out, needed, ambiguous_width);
    }

    if (out != stack) {
        free(out);
    }
    return result;
}

/* Commit a pending grapheme cluster to the running column total. */
/*
 * Add to a column counter without overflowing.
 *
 * Cursor-forward parameters saturate at INT_MAX in escape.c, but once
 * current_col sits at INT_MAX any further advance -- a visible character, a
 * tab stop, an OSC 66 width -- is signed overflow, which is undefined
 * behaviour and would defeat that clamp.  Every column advance goes through
 * here.
 */
static int
col_add(int col, int delta)
{
    /* Done in 64-bit so the guard itself cannot overflow: computing
     * INT_MAX - col first is undefined when col is negative, which a
     * cursor-back sequence can produce in non-strict mode. */
    int64_t sum = (int64_t) col + (int64_t) delta;

    if (sum > INT_MAX) {
        return INT_MAX;
    }
    if (sum < INT_MIN) {
        return INT_MIN;
    }
    return (int) sum;
}

static void
flush_cluster(int *current_col, int *max_extent, int *cluster_width)
{
    if (*cluster_width) {
        *current_col = col_add(*current_col, *cluster_width);
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
    bool has_cp_overrides = narrower_len > 0 || zeroer_len > 0
                            || narrow_wider_len > 0 || narrow_zeroer_len > 0;

    /* Printable-ASCII input is handled by the fast path in width_u8(). */

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
                            /* Zero-width sequences. */
                            break;

                        case WCWIDTH_ESC_CUF:
                            current_col = (result.cursor_n > INT_MAX - current_col)
                                          ? INT_MAX : current_col + result.cursor_n;
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
                            current_col = col_add(current_col, wcwidth_ts_display_width(&ts, ambiguous_width));
                            break;
                        }

                        case WCWIDTH_ESC_NONE:
                            break;
                    }

                    idx += result.length;
                }
            }

            /* Escape sequences break VS16/VS15 adjacency.  prev_was_virama
             * survives (as in the Python reference): control characters and
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
                        current_col = col_add(current_col, tabsize - (current_col % tabsize));
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
                                current_col = col_add(current_col, override_w - last_measured_w);
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
                                            current_col = col_add(current_col, cluster_width);
                                        }
                                    }
                                    else {
                                        current_col = col_add(current_col, cluster_width);
                                    }
                                }
                            }
                            else {
                                current_col = col_add(current_col, cluster_width);
                            }
                        }
                        else {
                            current_col = col_add(current_col, cluster_width);
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
                    current_col = col_add(current_col, cluster_width);
                }
            }
            else {
                current_col = col_add(current_col, cluster_width);
            }
        }
        else {
            current_col = col_add(current_col, cluster_width);
        }
        if (current_col > max_extent) {
            max_extent = current_col;
        }
    }

    return max_extent;
}

/*
 * Codepoint-array variant of _width_parse(): same semantics but operates on a
 * pre-decoded uint32_t array instead of raw UTF-8 bytes.  This avoids the
 * encode->decode round-trip that width_u32 otherwise imposes.
 *
 * Escape sequences consist entirely of ASCII-range codepoints, so we encode
 * the region around each ESC into a small stack buffer to reuse the byte-based
 * wcwidth_escape_classify.
 */
static int
_width_parse_u32(const uint32_t *cp, size_t n, bool strict, int tabsize, int ambiguous_width,
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
    bool has_cp_overrides = narrower_len > 0 || zeroer_len > 0
                            || narrow_wider_len > 0 || narrow_zeroer_len > 0;

    /* Printable-ASCII input is handled by the fast path in width_u32(). */

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
        uint32_t ucs = cp[idx];

        /* Lone surrogates (U+D800-U+DFFF) are not valid Unicode and cannot
         * be encoded in UTF-8.  The old width_u32 path normalized them to
         * U+FFFD via its encode-decode round-trip; preserve that contract. */
        if (ucs >= 0xD800 && ucs <= 0xDFFF) {
            ucs = 0xFFFD;
        }

        if (ucs == ESC) {
            flush_cluster(&current_col, &max_extent, &cluster_width);

            /* Charset designation (ESC ( X / ESC ) X): one full codepoint
             * follows, so the ASCII-region classifier cannot see non-ASCII. */
            if (idx + 1 < n && (cp[idx + 1] == '(' || cp[idx + 1] == ')')) {
                idx += (idx + 2 < n) ? 3 : 1;
                last_measured_idx = -2;
                last_measured_ucs = 0;
                cluster_start = -1;
                if (current_col > max_extent) {
                    max_extent = current_col;
                }
                continue;
            }

            /* OSC / APC / DCS / PM: payloads run until BEL or ST and may hold
             * codepoints outside ASCII, so scan natively rather than through
             * the ASCII-region classifier. */
            if (idx + 1 < n
                && (cp[idx + 1] == ']' || cp[idx + 1] == '_' || cp[idx + 1] == 'P'
                    || cp[idx + 1] == '^')) {
                size_t pos = idx + 2;
                size_t term_start = 0;
                size_t term_end = 0;
                bool terminated = false;

                while (pos < n) {
                    if (cp[pos] == 0x07) {
                        terminated = true;
                        term_start = pos;
                        term_end = pos + 1;
                        break;
                    }
                    if (cp[pos] == ESC) {
                        if (pos + 1 < n && cp[pos + 1] == '\\') {
                            terminated = true;
                            term_start = pos;
                            term_end = pos + 2;
                        }
                        /* Any other ESC ends the body unterminated -- the same
                         * rule parse_osc() applies in escape.c, and the same
                         * [^\x07\x1b]* body the Python parser matches. */
                        break;
                    }
                    pos++;
                }

                if (cp[idx + 1] == ']') {
                    if (!terminated) {
                        /* Unterminated OSC consumes only ESC ']'. */
                        idx += 2;
                    }
                    else if (idx + 4 < n && cp[idx + 2] == '6' && cp[idx + 3] == '6'
                             && cp[idx + 4] == ';') {
                        /* OSC 66: ESC ] 6 6 ; <meta> [ ; <text> ] <term>. */
                        size_t semi = idx + 5;
                        size_t meta_len;
                        size_t text_start;
                        size_t text_len;

                        while (semi < term_start && cp[semi] != ';') {
                            semi++;
                        }
                        if (semi < term_start) {
                            meta_len = semi - (idx + 5);
                            text_start = semi + 1;
                            text_len = term_start - semi - 1;
                        }
                        else {
                            /* No text: the whole data is meta. */
                            meta_len = term_start - (idx + 5);
                            text_start = term_start;
                            text_len = 0;
                        }

                        {
                            wcwidth_ts_params_t params;
                            char meta_buf[64];

                            if (meta_len > 0 && meta_len < sizeof(meta_buf)) {
                                size_t k;
                                for (k = 0; k < meta_len; k++) {
                                    meta_buf[k] = (char) cp[idx + 5 + k];
                                }
                                meta_buf[meta_len] = '\0';
                                wcwidth_ts_parse_params(meta_buf, meta_len, &params);
                            }
                            else {
                                wcwidth_ts_parse_params("", 0, &params);
                            }

                            if (params.width > 0) {
                                current_col = col_add(current_col, params.scale * params.width);
                            }
                            else {
                                int text_width =
                                    wcswidth_u32(cp + text_start, text_len, ambiguous_width);
                                if (text_width < 0) {
                                    text_width = 0;
                                }
                                current_col = col_add(current_col, params.scale * text_width);
                            }
                        }
                        idx = term_end;
                    }
                    else {
                        /* OSC 8 or generic OSC: zero-width. */
                        idx = term_end;
                    }
                }
                else {
                    /* APC / DCS / PM: zero-width.  An unterminated body (one
                     * holding a bare ESC, or running off the end) consumes
                     * only the introducer, as in escape.c's parse path. */
                    idx = terminated ? term_end : idx + 2;
                }

                last_measured_idx = -2;
                last_measured_ucs = 0;
                cluster_start = -1;
                if (current_col > max_extent) {
                    max_extent = current_col;
                }
                continue;
            }

            {
                char esc_buf[256];
                size_t esc_len = 0;
                size_t j;
                for (j = 0; j < sizeof(esc_buf) && idx + j < n; j++) {
                    if (cp[idx + j] > 127) {
                        break;
                    }
                    esc_buf[j] = (char) cp[idx + j];
                    esc_len = j + 1;
                }
                bool esc_truncated = (j == sizeof(esc_buf) && idx + j < n);

                wcwidth_esc_result_t result;
                if (!wcwidth_escape_classify(esc_buf, esc_len, 0, &result)) {
                    idx++;
                }
                else {
                    /* When the stack buffer is full and the sequence was
                     * classified as a generic OTHER (which includes truncated
                     * OSCs and CSIs), the full escape may extend past the
                     * buffer.  Fall back to the byte-based classifier on an
                     * encoded copy of the remaining codepoints. */
                    bool need_fallback =
                        esc_truncated && result.type == WCWIDTH_ESC_OTHER;
                    if (need_fallback) {
                        char *rest_buf = NULL;
                        size_t rest_len = 0;
                        /* See above: refuse rather than wrap the size. */
                        size_t rest_cap = (n - idx > SIZE_MAX / 4) ? 0 : (n - idx) * 4;
                        rest_buf = rest_cap ? (char *) malloc(rest_cap) : NULL;
                        if (rest_buf != NULL) {
                            size_t k;
                            for (k = 0; k < n - idx; k++) {
                                char tmp[4];
                                size_t enc_len = utf8_encode_single(cp[idx + k], tmp);
                                memcpy(rest_buf + rest_len, tmp, enc_len);
                                rest_len += enc_len;
                            }
                            if (wcwidth_escape_classify(rest_buf, rest_len, 0, &result)) {
                                need_fallback = false;
                            }
                            free(rest_buf);
                        }
                    }
                    if (need_fallback) {
                        /* Could not classify; skip ESC as unrecognized. */
                        idx++;
                    }
                    else {
                        switch (result.type) {
                            case WCWIDTH_ESC_SGR:
                            case WCWIDTH_ESC_OTHER:
                            case WCWIDTH_ESC_UNRECOGNIZED:
                                break;

                            case WCWIDTH_ESC_CUF:
                                current_col = (result.cursor_n > INT_MAX - current_col)
                                              ? INT_MAX : current_col + result.cursor_n;
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
                                current_col = col_add(current_col, wcwidth_ts_display_width(&ts, ambiguous_width));
                                break;
                            }

                            case WCWIDTH_ESC_NONE:
                                break;
                        }

                        /* result.length is in bytes; for ASCII-only escape
                         * sequences, byte count == codepoint count. */
                        idx += result.length;
                    }
                }
            }

            last_measured_idx = -2;
            last_measured_ucs = 0;
            cluster_start = -1;

            if (current_col > max_extent) {
                max_extent = current_col;
            }
            continue;
        }

        if (ucs < 0x20) {
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
                        current_col = col_add(current_col, tabsize - (current_col % tabsize));
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

            if (current_col > max_extent) {
                max_extent = current_col;
            }

            idx++;
            last_measured_idx = -2;
            last_measured_ucs = 0;
            cluster_start = -1;
            continue;
        }

        if (ucs == 0x7F) {
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

        if (ucs >= 0x80 && ucs < 0xA0) {
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

        /* 5. Inline grapheme-clustering: ZWJ, Virama, VS16, Regional
         * Indicators, Fitzpatrick, Mc, wcwidth */
        if (ucs == 0x200D) {
            if (prev_was_virama) {
                idx++;
            }
            else if (idx + 1 < n) {
                if (has_graphemes && last_measured_idx >= 0
                    && wcwidth_is_emoji_zwj_set(last_measured_ucs)) {
                    size_t cluster_end =
                        wcwidth_scan_zwj_cluster_end(cp, n, (size_t) last_measured_idx);
                    size_t cluster_cps_len = cluster_end - (size_t) last_measured_idx;
                    if (cluster_cps_len < 32) {
                        uint32_t cluster_cps[32];
                        memcpy(cluster_cps, cp + last_measured_idx,
                               cluster_cps_len * sizeof(uint32_t));
                        int override_w =
                            wcwidth_grapheme_override_lookup(term, cluster_cps, cluster_cps_len);
                        if (override_w >= 0) {
                            current_col = col_add(current_col, override_w - last_measured_w);
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
                /* No override; ZWJ breaks VS16/VS15 adjacency.  ZWJ + next
                 * codepoint form a zero-width unit. */
                last_measured_w = 0;
                prev_was_virama = false;
                idx += 2;
            }
            else {
                prev_was_virama = false;
                idx++;
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
            idx++;
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
                current_col -= 1;
            }
            idx++;
            continue;
        }

        /* 7. Regional Indicator & Fitzpatrick (both above BMP) */
        if (ucs > 0xFFFF) {
            if (wcwidth_is_regional_indicator(ucs)) {
                int ri_before = 0;
                size_t j = idx;
                while (j > 0) {
                    j--;
                    if (!wcwidth_is_regional_indicator(cp[j])) {
                        break;
                    }
                    ri_before++;
                }
                if (ri_before % 2 == 1) {
                    last_measured_ucs = ucs;
                    idx++;
                    continue;
                }
            }
            else if (wcwidth_is_fitzpatrick(ucs) && last_measured_ucs != 0
                     && wcwidth_is_emoji_zwj_set(last_measured_ucs)) {
                idx++;
                continue;
            }
        }

        /* 8. Normal character: measure with wcwidth. */
        {
            int w = wcwidth_u32(ucs, ambiguous_width);
            if (w < 0) {
                idx++;
                continue;
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
                if (prev_was_virama) {
                    cluster_width = 2;
                }
                else if (cluster_width) {
                    bool flushed = false;
                    if (has_graphemes && cluster_start >= 0) {
                        size_t candidate_len = (size_t) idx - (size_t) cluster_start + 1;
                        if (candidate_len < 32) {
                            uint32_t candidate_cps[32];
                            memcpy(candidate_cps, cp + cluster_start,
                                   candidate_len * sizeof(uint32_t));
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
                                size_t cluster_len = (size_t) idx - (size_t) cluster_start;
                                if (cluster_len < 32) {
                                    uint32_t cluster_cps[32];
                                    memcpy(cluster_cps, cp + cluster_start,
                                           cluster_len * sizeof(uint32_t));
                                    int cluster_w = wcwidth_grapheme_override_lookup(
                                        term, cluster_cps, cluster_len);
                                    if (cluster_w >= 0) {
                                        current_col = col_before_cluster + cluster_w;
                                        if (current_col > max_extent) {
                                            max_extent = current_col;
                                        }
                                    }
                                    else {
                                        current_col = col_add(current_col, cluster_width);
                                    }
                                }
                                else {
                                    current_col = col_add(current_col, cluster_width);
                                }
                            }
                        }
                        else {
                            current_col = col_add(current_col, cluster_width);
                        }
                    }
                    else {
                        current_col = col_add(current_col, cluster_width);
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
                cluster_width = 2;
                last_measured_idx = -2;
                prev_was_virama = false;
            }
            else {
                prev_was_virama = false;
            }
        }

        idx++;
    }

    /* Flush final pending cluster. */
    if (cluster_width) {
        if (has_graphemes && cluster_start >= 0) {
            size_t cluster_len = n - (size_t) cluster_start;
            if (cluster_len < 32) {
                uint32_t cluster_cps[32];
                memcpy(cluster_cps, cp + cluster_start, cluster_len * sizeof(uint32_t));
                int override_w =
                    wcwidth_grapheme_override_lookup(term, cluster_cps, cluster_len);
                if (override_w >= 0) {
                    current_col = col_before_cluster + override_w;
                }
                else {
                    current_col = col_add(current_col, cluster_width);
                }
            }
            else {
                current_col = col_add(current_col, cluster_width);
            }
        }
        else {
            current_col = col_add(current_col, cluster_width);
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

    if (n == 0) {
        return 0;
    }

    /* Printable-ASCII fast path: width is the byte count, in every mode. */
    if (_all_printable_ascii_u8(utf8, n)) {
        return (int) n;
    }

    effective_mode = mode;

    /* Fast-path downgrade: in PARSE mode, if text has no cursor movement,
     * downgrade to IGNORE for performance.  The threshold counts codepoints
     * like the Python implementation's len(), not bytes. */
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
    int tabsize;
    int ambiguous_width;
    const char *term_program;
    wcwidth_control_mode_t effective_mode;

    if (error != NULL) {
        *error = WCWIDTH_ERROR_NONE;
    }

    if (codepoints == NULL || n == 0) {
        return 0;
    }

    if (opts == NULL) {
        opts = &WCWIDTH_WIDTH_OPTS_DEFAULT;
    }

    tabsize = opts->tabsize;
    ambiguous_width = opts->ambiguous_width;
    term_program = opts->term_program;

    /* Printable-ASCII fast path: width is the codepoint count, in every mode. */
    if (_all_printable_ascii_u32(codepoints, n)) {
        return (int) n;
    }

    effective_mode = mode;

    /* Fast-path downgrade: in PARSE mode, if text has no cursor movement,
     * downgrade to IGNORE for performance. */
    if (effective_mode == WCWIDTH_PARSE && n > FAST_PATH_MIN_LEN) {
        if (!_needs_cursor_tracking_u32(codepoints, n)) {
            effective_mode = WCWIDTH_IGNORE;
        }
    }

    if (effective_mode == WCWIDTH_IGNORE) {
        return _width_ignore_u32(codepoints, n, ambiguous_width, term_program, error);
    }

    /* PARSE (with cursor movement) or STRICT: direct codepoint path, no
     * encode/decode round-trip. */
    return _width_parse_u32(codepoints, n, effective_mode == WCWIDTH_STRICT, tabsize,
                            ambiguous_width, term_program, error);
}
