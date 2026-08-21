/*
 * OSC 66 Text Sizing protocol parsing and measurement.
 */
#ifndef WCWIDTH_TEXT_SIZING_H
#define WCWIDTH_TEXT_SIZING_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "escape.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Parsed OSC 66 Text Sizing parameters. */
typedef struct
{
    int scale;            /* repeat count, default 1 */
    int width;            /* 0 = auto-width from text, >0 = fixed width */
    int numerator;        /* fraction numerator (0 = don't care) */
    int denominator;      /* fraction denominator (0 = don't care) */
    int vertical_align;   /* 0=top, 1=bottom, 2=center */
    int horizontal_align; /* 0=left, 1=right, 2=center */
} wcwidth_ts_params_t;

/* A parsed OSC 66 Text Sizing sequence. */
typedef struct
{
    wcwidth_ts_params_t params;
    const char *text; /* pointer into original buffer */
    size_t text_len;
    char terminator; /* '\x07' or '\x1b' */
} wcwidth_text_sizing_t;

/* Parse OSC 66 parameters from the colon-separated meta string.
 * meta: parameter string, e.g. "s=2:w=3:n=1:d=2:v=1:h=1"
 * meta_len: length of meta string.  Exactly meta_len bytes are read; *meta*
 *           need not be NUL-terminated.
 * Returns true on success.
 */
bool wcwidth_ts_parse_params(const char *meta, size_t meta_len, wcwidth_ts_params_t *params);

/* Build a text sizing struct from a classified OSC 66 escape result,
 * applying default parameters. */
void wcwidth_ts_from_esc(const wcwidth_esc_result_t *esc, wcwidth_text_sizing_t *ts);

/* Compute the display width of a text sizing sequence.
 * ambiguous_width: 1 or 2 (see wcwidth.h)
 * Uses wcswidth_u8 internally for width measurement.
 */
int wcwidth_ts_display_width(const wcwidth_text_sizing_t *ts, int ambiguous_width);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_TEXT_SIZING_H */
