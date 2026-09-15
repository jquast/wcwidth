/*
 * Text alignment: ljust, rjust, center.
 */
#ifndef WCWIDTH_ALIGN_H
#define WCWIDTH_ALIGN_H

#include "width.h"
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Options for the justify functions.
 *
 * Initialize from WCWIDTH_ALIGN_OPTS_DEFAULT and set only what differs; a
 * NULL opts argument uses the defaults unchanged, justifying to width 0.
 */
typedef struct
{
    size_t dest_width;        /* target display width in cells */
    const char *fillchar;     /* UTF-8 padding, repeated once per padding
                               * cell (default " ") */
    size_t fillchar_len;      /* byte length of fillchar */
    int ambiguous_width;      /* 1 or 2 */
    const char *term_program; /* NULL or terminal name */
} wcwidth_align_opts_t;

/* Default options for the justify functions. */
extern const wcwidth_align_opts_t WCWIDTH_ALIGN_OPTS_DEFAULT;

/*
 * Left/right/center justify text to opts->dest_width display cells.
 *
 * Each returns a malloc'd NUL-terminated string on success, or NULL on
 * error.  When NULL is returned and *error is set to a nonzero
 * wcwidth_error_t, the failure is a WCWIDTH_STRICT violation; otherwise it
 * is an allocation failure.  *error may be NULL, in which case errors are
 * signaled only by the NULL return.  On success, *out_len receives the byte
 * length (excluding NUL) when non-NULL; the caller must free() the result.
 *
 *   text:     UTF-8 input, NOT NUL-terminated.
 *   text_len: byte length of text.
 *   mode:     how control characters and sequences are treated, as for
 *             width_u8().
 *   opts:     alignment options, or NULL for defaults.
 *   out_len:  output: byte length of result (excluding NUL); may be NULL.
 *   error:    output: wcwidth_error_t, WCWIDTH_ERROR_NONE on success.
 */
char *ljust_u8(const char *text, size_t text_len, wcwidth_control_mode_t mode,
               const wcwidth_align_opts_t *opts, size_t *out_len, int *error);

char *rjust_u8(const char *text, size_t text_len, wcwidth_control_mode_t mode,
               const wcwidth_align_opts_t *opts, size_t *out_len, int *error);

char *center_u8(const char *text, size_t text_len, wcwidth_control_mode_t mode,
                const wcwidth_align_opts_t *opts, size_t *out_len, int *error);

/*
 * Codepoint-array variants of ljust_u8()/rjust_u8()/center_u8(): encode the
 * codepoints to UTF-8, justify, and decode the result back to a codepoint
 * array.  The returned array is *out_len* codepoints and the caller does a
 * single free() of it.  Error and ownership semantics are as for the _u8()
 * forms: on NULL return, *error* is a nonzero wcwidth_error_t for a
 * WCWIDTH_STRICT violation, or WCWIDTH_ERROR_NONE for an allocation failure.
 * opts->fillchar stays UTF-8 bytes.
 */
uint32_t *ljust_u32(const uint32_t *codepoints, size_t n, wcwidth_control_mode_t mode,
                    const wcwidth_align_opts_t *opts, size_t *out_len, int *error);

uint32_t *rjust_u32(const uint32_t *codepoints, size_t n, wcwidth_control_mode_t mode,
                    const wcwidth_align_opts_t *opts, size_t *out_len, int *error);

uint32_t *center_u32(const uint32_t *codepoints, size_t n, wcwidth_control_mode_t mode,
                     const wcwidth_align_opts_t *opts, size_t *out_len, int *error);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_ALIGN_H */
