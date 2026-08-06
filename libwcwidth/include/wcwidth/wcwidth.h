/*
 * Unicode character display width: wcwidth, wcswidth, wcstwidth.
 */
#ifndef WCWIDTH_H
#define WCWIDTH_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Return the display width of a single Unicode codepoint.
 *
 * *ambiguous_width*: width for East Asian Ambiguous (A) characters.
 *    1 = narrow (default), 2 = wide (CJK context).
 *
 * Returns:
 *   1 or 2  -- display cells occupied
 *   0       -- zero-width codepoint (combining marks, ZWJ, etc.)
 *  -1       -- non-printable control character
 */
int wcwidth_u32(uint32_t codepoint, int ambiguous_width);

/*
 * Return the display width of a string of Unicode codepoints.
 *
 * *n*: number of codepoints in the array.
 *
 * This function handles grapheme clusters (ZWJ, VS16, virama, RI pairs, etc.).
 */
int wcswidth_u32(const uint32_t *codepoints, size_t n, int ambiguous_width);

/*
 * UTF-8 variant of wcswidth_u32().
 *
 * *n*: maximum number of UTF-8 bytes to process (use (size_t)-1 for NUL-terminated).
 * If *n* is not (size_t)-1, exactly *n* bytes are read; embedded NULs are allowed.
 * If *n* is (size_t)-1, the string must be NUL-terminated.
 */
int wcswidth_u8(const char *utf8, size_t n, int ambiguous_width);

/*
 * Terminal-aware variant of wcswidth_u32().
 *
 * *term_program*: canonical terminal name for override tables (e.g. "kitty",
 * "xterm", "ghostty"). Use NULL for no terminal overrides.
 */
int wcstwidth_u32(const uint32_t *codepoints, size_t n, int ambiguous_width,
                  const char *term_program);

/*
 * Terminal-aware variant of wcswidth_u8().
 */
int wcstwidth_u8(const char *utf8, size_t n, int ambiguous_width, const char *term_program);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_H */
