/*
 * Text truncation with sequence awareness.
 *
 * This is a simplified C11 implementation.  Differences from the Python
 * clip are documented in docs/libwcwidth.rst.  In particular:
 *   - OSC 66 text sizing is passed through as an opaque sequence rather
 *     than being clipped as a semantic unit.  OSC 8 hyperlinks are not
 *     implemented; they measure as zero-width but are never rewritten,
 *     so a window starting or ending inside a link is left unbalanced.
 *   - Cursor-movement sequences (HPA, CUF, CUB) are passed through
 *     rather than resolved into the column model.
 */
#include "wcwidth/clip.h"
#include "wcwidth/escape.h"
#include "wcwidth/grapheme.h"
#include "wcwidth/sgr.h"
#include "wcwidth/wcwidth.h"
#include "wcwidth/utf8.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define ESC 0x1b

typedef struct
{
    char *buf;
    size_t len;
    size_t cap;
} strbuf_t;

static void
strbuf_init(strbuf_t *sb, size_t initial_cap)
{
    sb->buf = (char *) malloc(initial_cap);
    sb->len = 0;
    sb->cap = (sb->buf != NULL) ? initial_cap : 0;
    if (sb->buf != NULL && sb->cap > 0) {
        sb->buf[0] = '\0';
    }
}

static void
strbuf_grow(strbuf_t *sb, size_t needed)
{
    size_t new_cap;
    char *new_buf;

    if (sb->cap >= needed) {
        return;
    }
    new_cap = sb->cap ? sb->cap * 2 : 256;
    if (new_cap < needed) {
        new_cap = needed + 64;
    }
    new_buf = (char *) realloc(sb->buf, new_cap);
    if (new_buf == NULL) {
        return;
    }
    sb->buf = new_buf;
    sb->cap = new_cap;
}

static void
strbuf_append(strbuf_t *sb, const char *s, size_t len)
{
    if (len == 0) {
        return;
    }
    strbuf_grow(sb, sb->len + len + 1);
    if (sb->buf == NULL || sb->cap < sb->len + len + 1) {
        return;
    }
    memcpy(sb->buf + sb->len, s, len);
    sb->len += len;
    sb->buf[sb->len] = '\0';
}

static void
strbuf_free(strbuf_t *sb)
{
    free(sb->buf);
    sb->buf = NULL;
    sb->len = 0;
    sb->cap = 0;
}

static char *
strbuf_detach(strbuf_t *sb, size_t *out_len)
{
    char *result = sb->buf;

    if (result == NULL) {
        result = (char *) malloc(1);
        if (result != NULL) {
            result[0] = '\0';
        }
        if (out_len != NULL) {
            *out_len = 0;
        }
        sb->buf = NULL;
        sb->len = 0;
        sb->cap = 0;
        return result;
    }

    if (out_len != NULL) {
        *out_len = sb->len;
    }
    sb->buf = NULL;
    sb->len = 0;
    sb->cap = 0;
    return result;
}

static int
grapheme_width(const char *g, size_t g_len, int ambiguous_width, const char *term_program)
{
    int w;

    if (term_program != NULL && term_program[0] != '\0') {
        w = wcstwidth_u8(g, g_len, ambiguous_width, term_program);
    }
    else {
        w = wcswidth_u8(g, g_len, ambiguous_width);
    }
    return (w < 0) ? 0 : w;
}

static void
apply_sgr_wrap(strbuf_t *sb, const wcwidth_sgr_state_t *style, bool active)
{
    /* wcwidth_sgr_to_escape() documents out_cap >= WCWIDTH_SGR_PROPAGATE_SPARE
     * (sgr.h); a full 24-bit fg+bg state does not fit in less. */
    char prefix[WCWIDTH_SGR_PROPAGATE_SPARE];
    size_t prefix_len;

    if (!active)
        return;

    prefix_len = wcwidth_sgr_to_escape(style, prefix, sizeof(prefix));

    if (prefix_len > 0) {
        char *old_buf = sb->buf;
        size_t old_len = sb->len;
        size_t new_cap = old_len + prefix_len + 5;
        char *new_buf = (char *) malloc(new_cap);

        if (new_buf == NULL)
            return;

        memcpy(new_buf, prefix, prefix_len);
        if (old_buf != NULL && old_len > 0) {
            memcpy(new_buf + prefix_len, old_buf, old_len);
        }
        new_buf[prefix_len + old_len] = '\0';

        free(old_buf);
        sb->buf = new_buf;
        sb->len = prefix_len + old_len;
        sb->cap = new_cap;
    }

    if (wcwidth_sgr_is_active(style)) {
        strbuf_append(sb, "\x1b[0m", 4);
    }
}

static bool
clip_run(const char *text, size_t text_len, size_t v_start, size_t v_end,
         const char *fillchar, size_t fillchar_len, int tabsize,
         int ambiguous_width, const char *term_program, bool strict, bool track_sgr,
         wcwidth_sgr_state_t *captured_style, bool *style_captured,
         strbuf_t *sb, int *error)
{
    wcwidth_sgr_state_t current_style;
    int col;
    size_t idx;
    wcwidth_grapheme_iter_t *giter;
    size_t giter_upto;

    current_style = WCWIDTH_SGR_STATE_DEFAULT;
    *style_captured = false;
    col = 0;
    idx = 0;
    giter = NULL;
    giter_upto = 0;

    while (idx < text_len) {
        unsigned char ch = (unsigned char) text[idx];

        if (col >= (int) v_end && ch != ESC) {
            if (*style_captured) {
                break;
            }
            if (!track_sgr) {
                const char *next =
                    (const char *) memchr(text + idx + 1, ESC, text_len - idx - 1);
                if (next == NULL) {
                    break;
                }
                idx = (size_t) (next - text);
                continue;
            }
        }

        if (ch == ESC) {
            wcwidth_esc_result_t result;

            if (!wcwidth_escape_classify(text, text_len, idx, &result)) {
                if ((int) v_start <= col && col < (int) v_end)
                    strbuf_append(sb, text + idx, 1);
                idx++;
                continue;
            }

            if (result.type == WCWIDTH_ESC_SGR && track_sgr) {
                wcwidth_sgr_update(&current_style, result.sgr_params,
                                   result.sgr_params_len);
                idx += result.length;
                continue;
            }

            if (strict && result.type == WCWIDTH_ESC_INDETERMINATE) {
                *error = WCWIDTH_ERROR_INDETERMINATE;
                goto fail;
            }

            if ((int) v_start <= col && col < (int) v_end)
                strbuf_append(sb, result.start, result.length);
            idx += result.length;
            continue;
        }

        if (ch == '\t') {
            if (tabsize > 0) {
                int next_tab = col + (tabsize - (col % tabsize));
                while (col < next_tab) {
                    if ((int) v_start <= col && col < (int) v_end)
                        strbuf_append(sb, " ", 1);
                    col++;
                }
            }
            else {
                if ((int) v_start <= col && col < (int) v_end)
                    strbuf_append(sb, "\t", 1);
            }
            idx++;
            continue;
        }

        {
            const char *grapheme;
            size_t g_len;
            int g_w;

            if (giter == NULL || giter_upto != idx) {
                wcwidth_grapheme_iter_free(giter);
                giter = wcwidth_grapheme_iter_new(text + idx, text_len - idx);
                giter_upto = idx;
                if (giter == NULL) {
                    goto fail;
                }
            }
            grapheme = wcwidth_grapheme_next(giter, &g_len);
            if (grapheme == NULL || g_len == 0) {
                wcwidth_grapheme_iter_free(giter);
                giter = NULL;
                idx++;
                continue;
            }
            g_w = grapheme_width(grapheme, g_len, ambiguous_width, term_program);

            if (g_w == 0) {
                if ((int) v_start <= col && col < (int) v_end)
                    strbuf_append(sb, grapheme, g_len);
            }
            else if (col >= (int) v_start && col + g_w <= (int) v_end) {
                strbuf_append(sb, grapheme, g_len);
                if (track_sgr && !*style_captured) {
                    *captured_style = current_style;
                    *style_captured = true;
                }
            }
            else if (col < (int) v_end && col + g_w > (int) v_start) {
                int c_start = ((int) v_start > col) ? (int) v_start : col;
                int c_end = ((int) v_end < col + g_w) ? (int) v_end : col + g_w;
                int n;
                for (n = c_start; n < c_end; n++)
                    strbuf_append(sb, fillchar, fillchar_len);
                if (track_sgr && !*style_captured) {
                    *captured_style = current_style;
                    *style_captured = true;
                }
            }

            col += g_w;
            idx += g_len;
            giter_upto = idx;
        }
    }

    wcwidth_grapheme_iter_free(giter);
    return true;

fail:
    wcwidth_grapheme_iter_free(giter);
    return false;
}

char *
clip_u8(const char *text, size_t text_len, size_t v_start, size_t v_end,
        wcwidth_control_mode_t control_codes, int tabsize, int ambiguous_width,
        const char *term_program, bool propagate_sgr, const char *fillchar,
        size_t fillchar_len, size_t *out_len, int *error)
{
    strbuf_t sb;
    wcwidth_sgr_state_t captured_style;
    bool style_captured;
    bool strict;
    bool has_esc;
    bool track_sgr;

    if (out_len != NULL)
        *out_len = 0;
    if (error != NULL)
        *error = WCWIDTH_ERROR_NONE;

    if (v_end <= v_start) {
        char *empty = (char *) malloc(1);
        if (empty != NULL)
            empty[0] = '\0';
        return empty;
    }

    {
        size_t i;
        bool all_ascii = true;
        size_t scan_len = text_len;
        for (i = 0; i < scan_len; i++) {
            unsigned char ub = (unsigned char) text[i];
            if (ub < 0x20 || ub >= 0x7f) {
                all_ascii = false;
                break;
            }
        }
        if (all_ascii) {
            size_t result_len;
            char *result;

            if (v_start >= text_len) {
                result = (char *) malloc(1);
                if (result != NULL)
                    result[0] = '\0';
                return result;
            }
            result_len =
                (text_len - v_start < v_end - v_start)
                    ? (text_len - v_start) : (v_end - v_start);
            result = (char *) malloc(result_len + 1);
            if (result == NULL)
                return NULL;
            memcpy(result, text + v_start, result_len);
            result[result_len] = '\0';
            if (out_len != NULL)
                *out_len = result_len;
            return result;
        }
    }

    has_esc = (memchr(text, ESC, text_len) != NULL);

    track_sgr = propagate_sgr && has_esc;
    strict = (control_codes == WCWIDTH_STRICT);

    strbuf_init(&sb, 256);
    if (sb.buf == NULL)
        return NULL;

    captured_style = WCWIDTH_SGR_STATE_DEFAULT;
    style_captured = false;

    if (!clip_run(text, text_len, v_start, v_end, fillchar, fillchar_len, tabsize,
                  ambiguous_width, term_program, strict, track_sgr,
                  &captured_style, &style_captured, &sb, error)) {
        strbuf_free(&sb);
        return NULL;
    }

    if (track_sgr && style_captured) {
        apply_sgr_wrap(&sb, &captured_style, wcwidth_sgr_is_active(&captured_style));
    }

    return strbuf_detach(&sb, out_len);
}

uint32_t *
clip_u32(const uint32_t *codepoints, size_t n, size_t v_start, size_t v_end,
         wcwidth_control_mode_t control_codes, int tabsize, int ambiguous_width,
         const char *term_program, bool propagate_sgr, const char *fillchar,
         size_t fillchar_len, size_t *out_len, int *error)
{
    char enc_stack[512];
    size_t enc_len;
    char *utf8;
    uint32_t *result;

    if (out_len != NULL) {
        *out_len = 0;
    }
    if (error != NULL) {
        *error = WCWIDTH_ERROR_NONE;
    }

    utf8 = wcwidth_encode_u32(codepoints, n, enc_stack, sizeof(enc_stack), &enc_len);
    if (utf8 == NULL) {
        return NULL;
    }
    {
        size_t byte_len = 0;
        char *bytes = clip_u8(utf8, enc_len, v_start, v_end, control_codes, tabsize,
                              ambiguous_width, term_program, propagate_sgr, fillchar,
                              fillchar_len, &byte_len, error);

        if (utf8 != enc_stack) {
            free(utf8);
        }
        if (bytes == NULL) {
            return NULL;
        }
        result = wcwidth_decode_u32_heap(bytes, byte_len, out_len);
        free(bytes);
    }
    return result;
}
