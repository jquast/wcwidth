/*
 * Terminal-aware text alignment: ljust, rjust, center.
 */
#include "wcwidth/align.h"
#include "wcwidth/utf8.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

static bool
is_ascii_printable(const char *text, size_t text_len)
{
    size_t i;

    for (i = 0; i < text_len; i++) {
        unsigned char ch = (unsigned char) text[i];
        if (ch < 0x20 || ch > 0x7E) {
            return false;
        }
    }
    return true;
}

static int
measure_width(const char *text, size_t text_len, wcwidth_control_mode_t control_codes,
              int ambiguous_width, const char *term_program, int *error)
{
    if (is_ascii_printable(text, text_len)) {
        return (int) text_len;
    }

    {
        wcwidth_width_opts_t opts = {
            .tabsize = 8,
            .ambiguous_width = ambiguous_width,
            .term_program = term_program,
        };
        int w = width_u8(text, text_len, control_codes, &opts, error);
        if (w < 0) {
            return -1;
        }
        return w;
    }
}

/*
 * Add *pad_cells* * *fillchar_len* bytes to *total*, refusing to overflow.
 *
 * dest_width is caller-supplied and may be enormous (it often comes from
 * terminal geometry or untrusted layout arithmetic), while fillchar_len is
 * up to 4 for a non-ASCII fill character.  Computing the product with
 * wrapping size_t arithmetic would size the allocation from a truncated
 * value and let fill_repeat() run past the end of it, so every caller
 * accumulates through here and treats false as an allocation failure.
 */
static bool
add_fill_bytes(size_t *total, size_t pad_cells, size_t fillchar_len)
{
    size_t bytes;

    if (fillchar_len != 0 && pad_cells > SIZE_MAX / fillchar_len) {
        return false;
    }
    bytes = pad_cells * fillchar_len;
    /* Leave room for the NUL terminator the callers append. */
    if (bytes > SIZE_MAX - 1 - *total) {
        return false;
    }
    *total += bytes;
    return true;
}

/* Append *fillchar* *count* times to *dst*; returns the advanced pointer. */
static char *
fill_repeat(char *dst, const char *fillchar, size_t fillchar_len, size_t count)
{
    size_t i;

    for (i = 0; i < count; i++) {
        memcpy(dst, fillchar, fillchar_len);
        dst += fillchar_len;
    }
    return dst;
}

char *
ljust_u8(const char *text, size_t text_len, size_t dest_width, const char *fillchar,
         size_t fillchar_len, wcwidth_control_mode_t control_codes, int ambiguous_width,
         const char *term_program, size_t *out_len, int *error)
{
    int text_width;
    size_t padding;
    size_t total;
    char *result;

    if (error != NULL) {
        *error = WCWIDTH_ERROR_NONE;
    }

    text_width = measure_width(text, text_len, control_codes, ambiguous_width, term_program, error);
    if (text_width < 0 || (error != NULL && *error != WCWIDTH_ERROR_NONE)) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    padding = ((size_t) text_width < dest_width) ? (dest_width - (size_t) text_width) : 0;
    total = text_len;
    if (!add_fill_bytes(&total, padding, fillchar_len)) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    result = (char *) malloc(total + 1);
    if (result == NULL) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    memcpy(result, text, text_len);
    fill_repeat(result + text_len, fillchar, fillchar_len, padding);
    result[total] = '\0';

    if (out_len != NULL) {
        *out_len = total;
    }
    return result;
}

char *
rjust_u8(const char *text, size_t text_len, size_t dest_width, const char *fillchar,
         size_t fillchar_len, wcwidth_control_mode_t control_codes, int ambiguous_width,
         const char *term_program, size_t *out_len, int *error)
{
    int text_width;
    size_t padding;
    size_t total;
    char *result;

    if (error != NULL) {
        *error = WCWIDTH_ERROR_NONE;
    }

    text_width = measure_width(text, text_len, control_codes, ambiguous_width, term_program, error);
    if (text_width < 0 || (error != NULL && *error != WCWIDTH_ERROR_NONE)) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    padding = ((size_t) text_width < dest_width) ? (dest_width - (size_t) text_width) : 0;
    total = text_len;
    if (!add_fill_bytes(&total, padding, fillchar_len)) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    result = (char *) malloc(total + 1);
    if (result == NULL) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    fill_repeat(result, fillchar, fillchar_len, padding);
    /* add_fill_bytes() above already proved this product cannot wrap. */
    memcpy(result + padding * fillchar_len, text, text_len);
    result[total] = '\0';

    if (out_len != NULL) {
        *out_len = total;
    }
    return result;
}

char *
center_u8(const char *text, size_t text_len, size_t dest_width, const char *fillchar,
          size_t fillchar_len, wcwidth_control_mode_t control_codes, int ambiguous_width,
          const char *term_program, size_t *out_len, int *error)
{
    int text_width;
    size_t total_padding;
    size_t left_pad;
    size_t right_pad;
    size_t total;
    char *result;

    if (error != NULL) {
        *error = WCWIDTH_ERROR_NONE;
    }

    text_width = measure_width(text, text_len, control_codes, ambiguous_width, term_program, error);
    if (text_width < 0 || (error != NULL && *error != WCWIDTH_ERROR_NONE)) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    total_padding = ((size_t) text_width < dest_width) ? (dest_width - (size_t) text_width) : 0;

    /*
     * str.center eccentricity: odd dest_width puts the extra padding on the
     * left, even on the right.
     * See https://jazcap53.github.io/pythons-eccentric-strcenter.html
     */
    left_pad = (total_padding / 2) + (total_padding & dest_width & 1);
    right_pad = total_padding - left_pad;

    total = text_len;
    if (!add_fill_bytes(&total, left_pad, fillchar_len)
        || !add_fill_bytes(&total, right_pad, fillchar_len)) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    result = (char *) malloc(total + 1);
    if (result == NULL) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    {
        char *dst = fill_repeat(result, fillchar, fillchar_len, left_pad);
        memcpy(dst, text, text_len);
        fill_repeat(dst + text_len, fillchar, fillchar_len, right_pad);
    }
    result[total] = '\0';

    if (out_len != NULL) {
        *out_len = total;
    }
    return result;
}

/* Signature shared by ljust_u8(), rjust_u8(), and center_u8(). */
typedef char *(*justify_fn)(const char *, size_t, size_t, const char *, size_t,
                            wcwidth_control_mode_t, int, const char *, size_t *, int *);

/*
 * Encode a codepoint array to UTF-8, run a justification function, and decode
 * the result back to a malloc'd codepoint array.  Returns NULL on error, with
 * *error set as for the _u8() forms (WCWIDTH_ERROR_NONE = allocation failure).
 */
static uint32_t *
justify_u32(const uint32_t *codepoints, size_t n, size_t dest_width, const char *fillchar,
            size_t fillchar_len, wcwidth_control_mode_t control_codes, int ambiguous_width,
            const char *term_program, size_t *out_len, int *error, justify_fn justify)
{
    char enc_stack[512];
    size_t enc_len;
    char *utf8;
    uint32_t *result;

    if (error != NULL) {
        *error = WCWIDTH_ERROR_NONE;
    }
    if (out_len != NULL) {
        *out_len = 0;
    }

    utf8 = wcwidth_encode_u32(codepoints, n, enc_stack, sizeof(enc_stack), &enc_len);
    if (utf8 == NULL) {
        return NULL;
    }
    {
        size_t byte_len = 0;
        char *bytes = justify(utf8, enc_len, dest_width, fillchar, fillchar_len, control_codes,
                              ambiguous_width, term_program, &byte_len, error);

        if (utf8 != enc_stack) {
            free(utf8);
        }
        if (bytes == NULL) {
            return NULL; /* *error already set by justify */
        }
        result = wcwidth_decode_u32_heap(bytes, byte_len, out_len);
        free(bytes);
    }
    return result;
}

uint32_t *
ljust_u32(const uint32_t *codepoints, size_t n, size_t dest_width, const char *fillchar,
          size_t fillchar_len, wcwidth_control_mode_t control_codes, int ambiguous_width,
          const char *term_program, size_t *out_len, int *error)
{
    return justify_u32(codepoints, n, dest_width, fillchar, fillchar_len, control_codes,
                       ambiguous_width, term_program, out_len, error, ljust_u8);
}

uint32_t *
rjust_u32(const uint32_t *codepoints, size_t n, size_t dest_width, const char *fillchar,
          size_t fillchar_len, wcwidth_control_mode_t control_codes, int ambiguous_width,
          const char *term_program, size_t *out_len, int *error)
{
    return justify_u32(codepoints, n, dest_width, fillchar, fillchar_len, control_codes,
                       ambiguous_width, term_program, out_len, error, rjust_u8);
}

uint32_t *
center_u32(const uint32_t *codepoints, size_t n, size_t dest_width, const char *fillchar,
           size_t fillchar_len, wcwidth_control_mode_t control_codes, int ambiguous_width,
           const char *term_program, size_t *out_len, int *error)
{
    return justify_u32(codepoints, n, dest_width, fillchar, fillchar_len, control_codes,
                       ambiguous_width, term_program, out_len, error, center_u8);
}
