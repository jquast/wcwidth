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
 * Clip text to the visible column range [v_start, v_end).
 *
 * Returns a malloc'd string on success, NULL on error.  When NULL is
 * returned and *error is set to a nonzero wcwidth_error_t (from width.h),
 * the failure is a WCWIDTH_STRICT violation; otherwise it is an
 * allocation failure.  *error is always written on return.
 * On success, *out_len receives the byte length of the result
 * (excluding NUL terminator, which is always present).
 * The caller must free the returned pointer with a single free() call.
 *
 * Parameters:
 *   text:           UTF-8 encoded input string.
 *   text_len:       length of text in bytes (NOT NUL-terminated).
 *   v_start:        starting column (inclusive, 0-indexed).
 *   v_end:          ending column (exclusive).
 *   control_codes:  how to handle control characters and sequences.
 *   tabsize:        tab stop width (0 = pass tabs through as-is).
 *   ambiguous_width:width for East Asian Ambiguous (A) characters (1 or 2).
 *   term_program:   terminal name for override tables (NULL = none).
 *   propagate_sgr:  if true, wrap result with SGR state at first visible char.
 *   overtyping:     painter's algorithm: -1 auto-detect, 0 disabled,
 *                   1 forced.  Ignored when control_codes=WCWIDTH_IGNORE.
 *   fillchar:       fill UTF-8 bytes for partially visible graphemes
 *                   (display width 1).
 *   fillchar_len:   byte length of fillchar.
 *   out_len:        output: byte length of result (excluding NUL).
 *   error:          output: wcwidth_error_t, WCWIDTH_ERROR_NONE on success.
 */
char *clip_u8(const char *text, size_t text_len, size_t v_start, size_t v_end,
              wcwidth_control_mode_t control_codes, int tabsize, int ambiguous_width,
              const char *term_program, bool propagate_sgr, int overtyping, const char *fillchar,
              size_t fillchar_len, size_t *out_len, int *error);

/*
 * Codepoint-array variant of clip_u8(): encodes the codepoints to UTF-8,
 * clips, and decodes the result back to a codepoint array.  The returned
 * array is *out_len* codepoints and the caller does a single free() of it.
 * Error and ownership semantics are as for clip_u8(): on NULL return, *error*
 * is a nonzero wcwidth_error_t for a WCWIDTH_STRICT violation, or
 * WCWIDTH_ERROR_NONE for an allocation failure.  *fillchar* stays UTF-8
 * bytes.
 */
uint32_t *clip_u32(const uint32_t *codepoints, size_t n, size_t v_start, size_t v_end,
                   wcwidth_control_mode_t control_codes, int tabsize, int ambiguous_width,
                   const char *term_program, bool propagate_sgr, int overtyping,
                   const char *fillchar, size_t fillchar_len, size_t *out_len, int *error);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_CLIP_H */
