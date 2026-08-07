/*
 * Terminal escape sequence classification.
 */
#include "wcwidth/escape.h"
#include "wcwidth/utf8.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define ESC 0x1b
#define BEL 0x07

/* Zero the result fields, leaving only type/start/length to set. */
static void
esc_result_init(wcwidth_esc_result_t *r, wcwidth_esc_type_t type, const char *start, size_t length)
{
    memset(r, 0, sizeof *r);
    r->type = type;
    r->start = start;
    r->length = length;
}

static int
parse_cursor_n(const char *params, size_t params_len)
{
    int n = 0;
    size_t i = 0;

    while (i < params_len && (unsigned char) params[i] >= '0' && (unsigned char) params[i] <= '9') {
        n = n * 10 + (params[i] - '0');
        i++;
    }
    return (i == 0) ? 1 : n;
}

/* True when CSI params match the Python scroll-region pattern '\d+;\d+'. */
static bool
is_scroll_region_params(const char *params, size_t params_len)
{
    size_t i = 0;

    while (i < params_len && params[i] >= '0' && params[i] <= '9')
        i++;
    if (i == 0 || i >= params_len || params[i] != ';')
        return false;
    i++;
    {
        size_t digits = 0;
        while (i < params_len && params[i] >= '0' && params[i] <= '9') {
            digits++;
            i++;
        }
        return digits > 0 && i == params_len;
    }
}

/* True when CSI params select the alternate screen ('?1049' or '?47'). */
static bool
is_alt_screen_params(const char *params, size_t params_len)
{
    return (params_len == 5 && memcmp(params, "?1049", 5) == 0)
           || (params_len == 3 && memcmp(params, "?47", 3) == 0);
}

/*
 * CSI sequence parser.
 * text[offset] == ESC, text[offset+1] == '['.
 * Scans forward to find the final byte and classify.
 */
static bool
parse_csi(const char *text, size_t text_len, size_t offset, wcwidth_esc_result_t *result)
{
    size_t pos = offset + 2; /* skip ESC [ */
    size_t params_start = pos;
    size_t params_end = 0;
    size_t intermed = 0;
    unsigned char ch;

    /* parameter bytes: 0x30-0x3F */
    while (pos < text_len) {
        ch = (unsigned char) text[pos];
        if (ch >= 0x30 && ch <= 0x3F) {
            pos++;
            continue;
        }
        break;
    }
    params_end = pos;

    /* intermediate bytes: 0x20-0x2F */
    while (pos < text_len) {
        ch = (unsigned char) text[pos];
        if (ch >= 0x20 && ch <= 0x2F) {
            intermed = 1;
            pos++;
            continue;
        }
        break;
    }

    /* final byte: 0x40-0x7E */
    if (pos >= text_len) {
        /* truncated -- consume just ESC '[' as a zero-width Fe sequence
         * ('[' is 0x5B, in the Fe range) */
        esc_result_init(result, WCWIDTH_ESC_OTHER, text + offset, 2);
        return true;
    }

    ch = (unsigned char) text[pos];
    if (ch < 0x40 || ch > 0x7E) {
        /* malformed CSI -- consume ESC and '[' as a zero-width sequence */
        esc_result_init(result, WCWIDTH_ESC_OTHER, text + offset, 2);
        return true;
    }

    pos++; /* consume final byte */
    esc_result_init(result, WCWIDTH_ESC_OTHER, text + offset, pos - offset);

    if (intermed) {
        /* CSI with intermediate bytes stays OTHER */
        return true;
    }

    switch (ch) {
        case 'm':
            result->type = WCWIDTH_ESC_SGR;
            result->sgr_params = text + params_start;
            result->sgr_params_len = params_end - params_start;
            break;
        case 'C':
            result->type = WCWIDTH_ESC_CUF;
            result->cursor_n = parse_cursor_n(text + params_start, params_end - params_start);
            break;
        case 'D':
            result->type = WCWIDTH_ESC_CUB;
            result->cursor_n = parse_cursor_n(text + params_start, params_end - params_start);
            break;
        case 'G':
            result->type = WCWIDTH_ESC_HPA;
            result->cursor_n = parse_cursor_n(text + params_start, params_end - params_start);
            break;
        case 'A':
        case 'B':
        case 'H':
        case 'J':
        case 'K':
        case 'L':
        case 'M':
        case 'P':
        case 'S':
        case 'T':
        case 'X':
        case 'd':
        case '@':
            result->type = WCWIDTH_ESC_INDETERMINATE;
            break;
        case 'r':
            /* change_scroll_region: '\x1b[\d+;\d+r' is indeterminate */
            result->type = is_scroll_region_params(text + params_start, params_end - params_start)
                               ? WCWIDTH_ESC_INDETERMINATE
                               : WCWIDTH_ESC_OTHER;
            break;
        case 'h':
        case 'l':
            /* alternate screen buffer: '\x1b[?1049[hl]' and '\x1b[?47[hl]' */
            result->type = is_alt_screen_params(text + params_start, params_end - params_start)
                               ? WCWIDTH_ESC_INDETERMINATE
                               : WCWIDTH_ESC_OTHER;
            break;
        default:
            break;
    }

    return true;
}

/*
 * Parse an OSC sequence: ESC ] ... until BEL or ST.
 * text[offset] == ESC, text[offset+1] == ']'.
 */
static bool
parse_osc(const char *text, size_t text_len, size_t offset, wcwidth_esc_result_t *result)
{
    size_t pos = offset + 2; /* skip ESC ] */
    bool terminated = false;

    esc_result_init(result, WCWIDTH_ESC_OTHER, text + offset, 0);

    while (pos < text_len) {
        unsigned char ch = (unsigned char) text[pos];
        if (ch == BEL) {
            pos++; /* consume BEL */
            terminated = true;
            break;
        }
        if (ch == ESC) {
            /* check for ST (ESC \) */
            if (pos + 1 < text_len && text[pos + 1] == '\\') {
                pos += 2; /* consume ESC \ */
                terminated = true;
                break;
            }
        }
        pos++;
    }

    /* An unterminated OSC is not a recognized OSC; it still consumes the
     * 2-byte ESC ] prefix, matching the Python reference (where \x1b] matches
     * the zero-width Fe branch). */
    if (!terminated) {
        result->length = 2;
        return true;
    }

    result->length = pos - offset;

    /* classify OSC by prefix */
    if (result->length >= 4 && text[offset + 2] == '8' && text[offset + 3] == ';') {
        /* OSC 8:
         * format: ESC ] 8 ; <params> ; <url> ST
         * params and url may be empty.
         * OSC 8;;  (params="" url="") is CLOSE.
         */
        /* content between "8;" prefix and the ST terminator.
         * Prefix is 4 bytes: ESC, ], 8, ; */
        size_t content_start = offset + 4;
        size_t content_len;

        if (result->length >= 2 && text[offset + result->length - 2] == ESC
            && text[offset + result->length - 1] == '\\') {
            /* ST terminator (ESC \) -- 2 bytes */
            content_len = result->length - 4 - 2; /* minus prefix ESC ] 8 ; and ST */
        }
        else {
            /* BEL terminator -- 1 byte */
            content_len = result->length - 4 - 1; /* minus prefix ESC ] 8 ; and BEL */
        }

        if (content_len == 0 || (content_len == 1 && text[content_start] == ';')) {
            /* no params or URL -- OSC 8 close */
            result->type = WCWIDTH_ESC_OSC8_CLOSE;
        }
        else {
            /* split params and url on first semicolon */
            const char *data = text + content_start;
            size_t semi = 0;
            size_t i = 0;
            while (i < content_len) {
                if (data[i] == ';') {
                    semi = i;
                    break;
                }
                i++;
            }
            result->type = WCWIDTH_ESC_OSC8_OPEN;
            result->osc8_params = data;
            result->osc8_params_len = semi;
            result->osc8_url = data + semi + 1;
            result->osc8_url_len = content_len - semi - 1;
        }
        return true;
    }

    if (result->length >= 5 && text[offset + 2] == '6' && text[offset + 3] == '6'
        && text[offset + 4] == ';') {
        /* OSC 66 -- Text Sizing Protocol */
        size_t data_start = offset + 5;
        size_t term_len = 1;
        if (result->length >= 2 && text[offset + result->length - 2] == ESC) {
            term_len = 2;
        }
        size_t data_len = result->length - 5 - term_len;

        /* split on first semicolon: meta;text */
        size_t semi = 0;
        bool found_semi = false;
        size_t i = 0;
        while (i < data_len) {
            if (text[data_start + i] == ';') {
                semi = i;
                found_semi = true;
                break;
            }
            i++;
        }

        if (!found_semi) {
            /* no semicolon: not valid OSC 66 (text is required per spec);
             * leave as WCWIDTH_ESC_OTHER so callers treat it as a generic OSC. */
            return true;
        }
        result->type = WCWIDTH_ESC_OSC66;
        result->ts_terminator = text[offset + result->length - 1];
        result->ts_meta = text + data_start;
        result->ts_meta_len = semi;
        result->ts_text = text + data_start + semi + 1;
        result->ts_text_len = data_len - semi - 1;
        return true;
    }

    /* other OSC stays OTHER */
    return true;
}

/*
 * Parse APC/DCS/PM: ESC _ / ESC P / ESC ^ ... until BEL or ST.
 */
static size_t
scan_until_terminator(const char *text, size_t text_len, size_t pos)
{
    while (pos < text_len) {
        unsigned char ch = (unsigned char) text[pos];
        if (ch == BEL) {
            return pos + 1;
        }
        if (ch == ESC && pos + 1 < text_len && text[pos + 1] == '\\') {
            return pos + 2;
        }
        pos++;
    }
    /* unterminated -- consume to end */
    return pos;
}

/*
 * Parse a character set designation: ESC ( or ESC ) + 1 byte.
 */
static bool
parse_charset(const char *text, size_t text_len, size_t offset, wcwidth_esc_result_t *result)
{
    if (offset + 3 > text_len) {
        /* truncated: ESC + designator with no character to follow; only the
         * ESC is zero-width */
        esc_result_init(result, WCWIDTH_ESC_UNRECOGNIZED, text + offset, 1);
        return true;
    }

    /* ESC + designator + one character (e.g. '\x1b(B') */
    esc_result_init(result, WCWIDTH_ESC_OTHER, text + offset, 3);
    return true;
}

/*
 * Parse nF sequence: ESC + one or more intermediates (0x20-0x2F) + final (0x30-0x7E).
 */
static bool
parse_nf(const char *text, size_t text_len, size_t offset, wcwidth_esc_result_t *result)
{
    size_t pos = offset + 1;
    int intermed_count = 0;

    while (pos < text_len) {
        unsigned char ch = (unsigned char) text[pos];
        if (ch >= 0x20 && ch <= 0x2F) {
            intermed_count++;
            pos++;
            continue;
        }
        if (intermed_count > 0 && ch >= 0x30 && ch <= 0x7E) {
            pos++; /* final byte */
            esc_result_init(result, WCWIDTH_ESC_OTHER, text + offset, pos - offset);
            return true;
        }
        break;
    }

    /* truncated or unrecognized */
    esc_result_init(result, WCWIDTH_ESC_UNRECOGNIZED, text + offset, 1);
    return true;
}

bool
wcwidth_escape_classify(const char *text, size_t text_len, size_t offset,
                        wcwidth_esc_result_t *result)
{
    unsigned char next;

    if (offset >= text_len || text[offset] != ESC) {
        return false;
    }

    if (offset + 1 >= text_len) {
        /* lone ESC at end */
        esc_result_init(result, WCWIDTH_ESC_UNRECOGNIZED, text + offset, 1);
        return true;
    }

    next = (unsigned char) text[offset + 1];

    switch (next) {
        case '[':
            return parse_csi(text, text_len, offset, result);

        case ']':
            return parse_osc(text, text_len, offset, result);

        case '_': /* APC */
        case 'P': /* DCS */
        case '^': /* PM */
        {
            size_t end = scan_until_terminator(text, text_len, offset + 2);
            esc_result_init(result, WCWIDTH_ESC_OTHER, text + offset, end - offset);
            return true;
        }

        case '(':
        case ')':
            return parse_charset(text, text_len, offset, result);

        case 0x20:
        case 0x21:
        case 0x22:
        case 0x23:
        case 0x24:
        case 0x25:
        case 0x26:
        case 0x27:
        case 0x2A:
        case 0x2B:
        case 0x2C:
        case 0x2D:
        case 0x2E:
        case 0x2F:
            /* intermediate byte -- possibly start of nF */
            return parse_nf(text, text_len, offset, result);

        default:
            break;
    }

    /* Fe sequences: ESC + 0x40-0x5F (but '[' was handled above).
     * '\x1bD' (index) and '\x1bM' (reverse index) are indeterminate. */
    if (next >= 0x40 && next <= 0x5F) {
        esc_result_init(
            result, (next == 'D' || next == 'M') ? WCWIDTH_ESC_INDETERMINATE : WCWIDTH_ESC_OTHER,
            text + offset, 2);
        return true;
    }

    /* Fp sequences: ESC + 0x30-0x3F.
     * '\x1b8' (restore cursor) is indeterminate. */
    if (next >= 0x30 && next <= 0x3F) {
        esc_result_init(result, (next == '8') ? WCWIDTH_ESC_INDETERMINATE : WCWIDTH_ESC_OTHER,
                        text + offset, 2);
        return true;
    }

    /* Fs sequences: ESC + 0x60-0x7E.
     * '\x1bc' (RIS full reset) is indeterminate. */
    if (next >= 0x60 && next <= 0x7E) {
        esc_result_init(result, (next == 'c') ? WCWIDTH_ESC_INDETERMINATE : WCWIDTH_ESC_OTHER,
                        text + offset, 2);
        return true;
    }

    /* unrecognized byte after ESC */
    esc_result_init(result, WCWIDTH_ESC_UNRECOGNIZED, text + offset, 1);
    return true;
}

size_t
wcwidth_escape_strip(const char *text, size_t text_len, char *out, size_t out_cap, size_t *out_len)
{
    size_t src = 0;
    size_t written = 0;
    wcwidth_esc_result_t result;

    while (src < text_len) {
        if (text[src] == ESC) {
            if (wcwidth_escape_classify(text, text_len, src, &result)) {
                if (result.type == WCWIDTH_ESC_OSC66) {
                    /* preserve inner text for text sizing sequences */
                    size_t i;
                    for (i = 0; i < result.ts_text_len; i++) {
                        if (written < out_cap) {
                            out[written] = result.ts_text[i];
                        }
                        written++;
                    }
                }
                else if (result.type == WCWIDTH_ESC_UNRECOGNIZED) {
                    /* preserve unknown/incomplete ESC sequences by copying
                     * the ESC byte through */
                    if (written < out_cap) {
                        out[written] = text[src];
                    }
                    written++;
                }
                /* else: strip all other escape sequences */
                src += result.length;
                continue;
            }
        }
        /* visible character -- copy */
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

uint32_t *
wcwidth_escape_strip_u32(const uint32_t *codepoints, size_t n, size_t *out_len)
{
    char enc_stack[512];
    size_t enc_len;
    char *utf8;
    uint32_t *result;

    if (out_len != NULL) {
        *out_len = 0;
    }

    utf8 = wcwidth_encode_u32(codepoints, n, enc_stack, sizeof(enc_stack), &enc_len);
    if (utf8 == NULL) {
        return NULL;
    }
    {
        /* The stripped output is never longer than the input. */
        char strip_stack[256];
        size_t byte_len = 0;
        size_t needed =
            wcwidth_escape_strip(utf8, enc_len, strip_stack, sizeof(strip_stack), &byte_len);
        char *buf = strip_stack;

        if (needed > sizeof(strip_stack)) {
            buf = (char *) malloc(needed + 1);
            if (buf == NULL) {
                if (utf8 != enc_stack) {
                    free(utf8);
                }
                return NULL;
            }
            wcwidth_escape_strip(utf8, enc_len, buf, needed + 1, &byte_len);
        }
        result = wcwidth_decode_u32_heap(buf, byte_len, out_len);
        if (buf != strip_stack) {
            free(buf);
        }
    }
    if (utf8 != enc_stack) {
        free(utf8);
    }
    return result;
}

void
wcwidth_escape_iter(const char *text, size_t text_len, wcwidth_escape_iter_fn fn, void *userdata)
{
    size_t idx = 0;
    size_t seg_start = 0;
    wcwidth_esc_result_t result;

    while (idx < text_len) {
        if (text[idx] == ESC) {
            if (idx > seg_start) {
                fn(text + seg_start, idx - seg_start, false, userdata);
            }

            if (wcwidth_escape_classify(text, text_len, idx, &result)) {
                fn(result.start, result.length, true, userdata);
                idx = result.start - text + result.length;
            }
            else {
                /* shouldn't happen since text[idx] == ESC */
                fn(text + idx, 1, true, userdata);
                idx++;
            }
            seg_start = idx;
        }
        else {
            idx++;
        }
    }

    if (seg_start < text_len) {
        fn(text + seg_start, text_len - seg_start, false, userdata);
    }
}

bool
wcwidth_escape_has_cursor_movement(const char *text, size_t text_len)
{
    size_t i;

    for (i = 0; i < text_len; i++) {
        unsigned char ch = (unsigned char) text[i];

        if (ch == 0x08 || ch == 0x0d) {
            return true;
        }

        if (ch == ESC) {
            wcwidth_esc_result_t result;
            if (wcwidth_escape_classify(text, text_len, i, &result)) {
                if (result.type == WCWIDTH_ESC_CUF || result.type == WCWIDTH_ESC_CUB
                    || result.type == WCWIDTH_ESC_HPA) {
                    return true;
                }
                i += result.length - 1; /* -1 because loop does i++ */
            }
        }
    }

    return false;
}
