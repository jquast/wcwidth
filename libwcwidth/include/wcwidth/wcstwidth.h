/*
 * Terminal-aware string display width.
 *
 * Port of wcwidth/_wcstwidth.py.
 */
#ifndef WCWIDTH_WCSTWIDTH_H
#define WCWIDTH_WCSTWIDTH_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int wcstwidth_u32(const uint32_t *codepoints, size_t n, int ambiguous_width,
                  const char *term_program);
int wcstwidth_u8(const char *utf8, size_t n, int ambiguous_width, const char *term_program);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_WCSTWIDTH_H */
