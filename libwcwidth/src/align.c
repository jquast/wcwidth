/*
 * Terminal-aware text alignment: ljust, rjust, center.
 *
 * Port of wcwidth/align.py.
 */
#include "wcwidth/align.h"

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
              int ambiguous_width, const char *term_program)
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
        int error = 0;
        int w = width_u8(text, text_len, control_codes, &opts, &error);
        if (w < 0) {
            return -1;
        }
        return w;
    }
}

char *
ljust_u8(const char *text, size_t text_len, size_t dest_width, char fillchar,
         wcwidth_control_mode_t control_codes, int ambiguous_width, const char *term_program,
         size_t *out_len)
{
    int text_width;
    size_t padding;
    size_t total;
    char *result;

    text_width = measure_width(text, text_len, control_codes, ambiguous_width, term_program);
    if (text_width < 0) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    padding = ((size_t) text_width < dest_width) ? (dest_width - (size_t) text_width) : 0;
    total = text_len + padding;

    result = (char *) malloc(total + 1);
    if (result == NULL) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    memcpy(result, text, text_len);
    memset(result + text_len, (int) (unsigned char) fillchar, padding);
    result[total] = '\0';

    if (out_len != NULL) {
        *out_len = total;
    }
    return result;
}

char *
rjust_u8(const char *text, size_t text_len, size_t dest_width, char fillchar,
         wcwidth_control_mode_t control_codes, int ambiguous_width, const char *term_program,
         size_t *out_len)
{
    int text_width;
    size_t padding;
    size_t total;
    char *result;

    text_width = measure_width(text, text_len, control_codes, ambiguous_width, term_program);
    if (text_width < 0) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    padding = ((size_t) text_width < dest_width) ? (dest_width - (size_t) text_width) : 0;
    total = padding + text_len;

    result = (char *) malloc(total + 1);
    if (result == NULL) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    memset(result, (int) (unsigned char) fillchar, padding);
    memcpy(result + padding, text, text_len);
    result[total] = '\0';

    if (out_len != NULL) {
        *out_len = total;
    }
    return result;
}

char *
center_u8(const char *text, size_t text_len, size_t dest_width, char fillchar,
          wcwidth_control_mode_t control_codes, int ambiguous_width, const char *term_program,
          size_t *out_len)
{
    int text_width;
    size_t total_padding;
    size_t left_pad;
    size_t right_pad;
    size_t total;
    char *result;

    text_width = measure_width(text, text_len, control_codes, ambiguous_width, term_program);
    if (text_width < 0) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    total_padding = ((size_t) text_width < dest_width) ? (dest_width - (size_t) text_width) : 0;

    /*
     * Matching Python str.center eccentric behavior:
     * When dest_width is odd, extra padding goes on the left;
     * when dest_width is even, extra padding goes on the right.
     * See https://jazcap53.github.io/pythons-eccentric-strcenter.html
     */
    left_pad = (total_padding / 2) + (total_padding & dest_width & 1);
    right_pad = total_padding - left_pad;

    total = left_pad + text_len + right_pad;

    result = (char *) malloc(total + 1);
    if (result == NULL) {
        if (out_len != NULL) {
            *out_len = 0;
        }
        return NULL;
    }

    memset(result, (int) (unsigned char) fillchar, left_pad);
    memcpy(result + left_pad, text, text_len);
    memset(result + left_pad + text_len, (int) (unsigned char) fillchar, right_pad);
    result[total] = '\0';

    if (out_len != NULL) {
        *out_len = total;
    }
    return result;
}
