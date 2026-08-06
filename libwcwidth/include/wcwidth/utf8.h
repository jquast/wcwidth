/*
 * UTF-8 decoding and encoding.
 */
#ifndef WCWIDTH_UTF8_H
#define WCWIDTH_UTF8_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Decode one UTF-8 codepoint from *s* (at most *len* bytes).  Returns the
 * number of bytes consumed (1-4).  On error or truncation, *cp_out* is set to
 * U+FFFD and the return value is the number of bytes to skip (1 for a bad
 * leading byte, the remaining length for a truncated sequence, or 0 when
 * *len* is 0).
 */
size_t wcwidth_utf8_decode_single(const char *s, size_t len, uint32_t *cp_out);

/*
 * Decode *utf8* into a codepoint array.  The caller provides *stack* (up to
 * *stack_cap* entries) as scratch space; when the result fits it is returned
 * in *stack* (no allocation), otherwise a heap buffer is allocated.  The
 * caller must free() the result only when it is not *stack*; freeing *stack*
 * is undefined behavior.  Sets *count* and returns NULL on allocation
 * failure.
 */
const uint32_t *wcwidth_decode_u32(const char *utf8, size_t n, uint32_t *stack, size_t stack_cap,
                                   size_t *count);

/*
 * Decode *utf8* into a malloc'd codepoint array (one free()).  Returns the
 * array and sets *count*, or NULL on allocation failure.
 */
uint32_t *wcwidth_decode_u32_heap(const char *utf8, size_t n, size_t *count);

/*
 * Encode *codepoints* (n entries) to UTF-8.  The caller provides *stack* (up
 * to *stack_cap* bytes) as scratch space; when the result fits it is returned
 * in *stack* (no allocation), otherwise a heap buffer is allocated.  The
 * caller must free() the result only when it is not *stack*; freeing *stack*
 * is undefined behavior.  Sets *out_len* and returns NULL on allocation
 * failure.
 *
 * The result is not NUL-terminated.  Invalid codepoints (lone surrogates and
 * values above U+10FFFF) are encoded as U+FFFD.
 */
char *wcwidth_encode_u32(const uint32_t *codepoints, size_t n, char *stack, size_t stack_cap,
                         size_t *out_len);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_UTF8_H */
