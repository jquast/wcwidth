/*
 * Text alignment: ljust, rjust, center.
 *
 * Port of wcwidth/align.py.
 */
#ifndef WCWIDTH_ALIGN_H
#define WCWIDTH_ALIGN_H

#include "width.h"
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

char *ljust_u8(const char *text, size_t text_len, size_t dest_width, char fillchar,
               wcwidth_control_mode_t control_codes, int ambiguous_width, const char *term_program,
               size_t *out_len);

char *rjust_u8(const char *text, size_t text_len, size_t dest_width, char fillchar,
               wcwidth_control_mode_t control_codes, int ambiguous_width, const char *term_program,
               size_t *out_len);

char *center_u8(const char *text, size_t text_len, size_t dest_width, char fillchar,
                wcwidth_control_mode_t control_codes, int ambiguous_width, const char *term_program,
                size_t *out_len);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_ALIGN_H */
