/*
 * Clip text to a visible column range [v_start, v_end).
 *
 * Port of wcwidth/_clip.py.
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
 * Returns a malloc'd string on success, NULL on error.
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
 *   fillchar:       fill character for partially visible graphemes (width 1).
 *   out_len:        output: byte length of result (excluding NUL).
 */
char *clip_u8(const char *text, size_t text_len, size_t v_start, size_t v_end,
              wcwidth_control_mode_t control_codes, int tabsize, int ambiguous_width,
              const char *term_program, bool propagate_sgr, char fillchar, size_t *out_len);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_CLIP_H */
