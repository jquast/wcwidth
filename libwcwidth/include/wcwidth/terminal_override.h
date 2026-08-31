/*
 * Terminal override lookup.
 *
 * Shared by wcstwidth.c and width.c: resolves a terminal identifier to its
 * generated override table and looks up grapheme cluster overrides.
 */
#ifndef WCWIDTH_TERMINAL_OVERRIDE_H
#define WCWIDTH_TERMINAL_OVERRIDE_H

#include <stddef.h>
#include <stdint.h>

#include "wcwidth/table_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Resolve a terminal identifier to its generated override table.
 *
 * *term_program* is a TERM_PROGRAM/TERM value, alias, or canonical terminal
 * name (case-insensitive, surrounding whitespace ignored).  Returns NULL when
 * it is NULL/empty or does not name a known terminal; in that case no
 * overrides apply.
 */
const wcwidth_terminal_override_t *wcwidth_resolve_terminal(const char *term_program);

/*
 * Look up a grapheme cluster (a codepoint sequence) in *term*'s override
 * table.  Returns the terminal-measured width, or -1 when the cluster is not
 * overridden.
 */
int wcwidth_grapheme_override_lookup(const wcwidth_terminal_override_t *term,
                                     const uint32_t *cps, size_t len);

/*
 * Scan forward from *start* (a base character) to the end of a ZWJ grapheme
 * cluster, following UAX #29 GB11 (ExtPict Extend* ZWJ x ExtPict, chained).
 * Returns the index just past the cluster.
 */
size_t wcwidth_scan_zwj_cluster_end(const uint32_t *cp, size_t n, size_t start);

/* UTF-8 variant; *start* is a byte offset and the returned index is a byte offset. */
size_t wcwidth_scan_zwj_cluster_end_u8(const char *utf8, size_t n, size_t start);

/*
 * Decode the UTF-8 bytes in utf8[lo..hi) into *cps*, up to *cap* codepoints.
 * Returns the number decoded; when the range holds more than *cap* codepoints
 * the caller must treat the cluster as unmatched (no override key can be that
 * long).
 */
size_t wcwidth_decode_cluster(const char *utf8, size_t lo, size_t hi,
                              uint32_t *cps, size_t cap);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_TERMINAL_OVERRIDE_H */
