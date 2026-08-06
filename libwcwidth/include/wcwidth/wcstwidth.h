/*
 * Terminal-aware string display width.
 */
#ifndef WCWIDTH_WCSTWIDTH_H
#define WCWIDTH_WCSTWIDTH_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Terminal-aware variant of wcswidth_u32().
 *
 * *term_program*: canonical terminal name for override tables (e.g. "kitty",
 * "xterm", "ghostty"). Use NULL for no terminal overrides.
 */
int wcstwidth_u32(const uint32_t *codepoints, size_t n, int ambiguous_width,
                  const char *term_program);

/* UTF-8 variant of wcstwidth_u32(). */
int wcstwidth_u8(const char *utf8, size_t n, int ambiguous_width, const char *term_program);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_WCSTWIDTH_H */
