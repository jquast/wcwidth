/*
 * Clip text to a visible column range [v_start, v_end).
 */
#ifndef WCWIDTH_CLIP_H
#define WCWIDTH_CLIP_H

#include "width.h"
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Options for wcwidth_clip_u32() and wcwidth_clip_u8().
 *
 * Initialize from WCWIDTH_CLIP_OPTS_DEFAULT and set only what differs; a
 * NULL opts argument uses the defaults unchanged.
 */
typedef struct
{
    size_t v_start;           /* starting column, inclusive (default 0) */
    size_t v_end;             /* ending column, exclusive.  SIZE_MAX (the
                               * default) clips through the final column of
                               * text, as the -1 default of Python's clip()
                               * does.  Clamped to INT_MAX with v_start. */
    int tabsize;              /* tab stop width, 0 passes tabs through (default 8) */
    int ambiguous_width;      /* 1 or 2 */
    const char *term_program; /* NULL or terminal name */
    bool propagate_sgr;       /* wrap result with the SGR state at the first
                               * visible character (default true) */
    const char *fillchar;     /* UTF-8 fill for a partially visible grapheme,
                               * display width 1 (default " ") */
    size_t fillchar_len;      /* byte length of fillchar */
} wcwidth_clip_opts_t;

/* Default options for wcwidth_clip_u32() and wcwidth_clip_u8(). */
extern const wcwidth_clip_opts_t WCWIDTH_CLIP_OPTS_DEFAULT;

/*
 * Clip text to the visible column range [opts->v_start, opts->v_end).
 *
 * Returns a malloc'd string on success, NULL on error.  When NULL is
 * returned, *error (from width.h) is WCWIDTH_ERROR_UNSUPPORTED for a
 * terminal sequence this function does not support, another nonzero
 * wcwidth_error_t for a WCWIDTH_STRICT violation, and WCWIDTH_ERROR_NONE
 * for an allocation failure.  *error is always written on return.
 *
 * Unsupported: horizontal cursor movement (BS, CR, CUF, CUB, HPA), OSC 8
 * hyperlinks and OSC 66 text sizing.
 * On success, *out_len receives the byte length of the result
 * (excluding NUL terminator, which is always present).
 * The caller must free the returned pointer with a single free() call.
 *
 *   text:     UTF-8 encoded input string, NOT NUL-terminated.
 *   text_len: length of text in bytes.
 *   mode:     how control characters and sequences are treated.
 *             WCWIDTH_STRICT raises on indeterminate sequences.
 *   opts:     clipping options, or NULL for defaults.
 *   out_len:  output: byte length of result (excluding NUL); may be NULL.
 *   error:    output: wcwidth_error_t, WCWIDTH_ERROR_NONE on success.
 */
char *wcwidth_clip_u8(const char *text, size_t text_len, wcwidth_control_mode_t mode,
                      const wcwidth_clip_opts_t *opts, size_t *out_len, int *error);

/*
 * Codepoint-array variant of wcwidth_clip_u8(): encodes the codepoints to UTF-8,
 * clips, and decodes the result back to a codepoint array.  The returned
 * array is *out_len* codepoints and the caller does a single free() of it.
 * Error and ownership semantics are as for wcwidth_clip_u8(), including
 * WCWIDTH_ERROR_UNSUPPORTED.  opts->fillchar stays UTF-8 bytes.
 */
uint32_t *wcwidth_clip_u32(const uint32_t *codepoints, size_t n, wcwidth_control_mode_t mode,
                           const wcwidth_clip_opts_t *opts, size_t *out_len, int *error);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_CLIP_H */
