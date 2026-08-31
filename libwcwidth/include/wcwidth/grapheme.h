/*
 * Grapheme cluster segmentation for UTF-8 text.
 */
#ifndef WCWIDTH_GRAPHEME_H
#define WCWIDTH_GRAPHEME_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Opaque iterator for grapheme cluster segmentation. */
typedef struct wcwidth_grapheme_iter_t wcwidth_grapheme_iter_t;

/* Initialize an iterator over grapheme clusters in a UTF-8 string.
 * Returns NULL if allocation fails (malloc for iterator state).
 */
wcwidth_grapheme_iter_t *wcwidth_grapheme_iter_new(const char *utf8, size_t len);

/* Return the next grapheme cluster, or NULL when exhausted.
 * *out_len* receives the byte length of the cluster.
 * The returned pointer is into the original text buffer.
 */
const char *wcwidth_grapheme_next(wcwidth_grapheme_iter_t *iter, size_t *out_len);

/* Free the iterator. */
void wcwidth_grapheme_iter_free(wcwidth_grapheme_iter_t *iter);

/* Find the grapheme cluster boundary immediately before *pos*.
 * Returns the byte offset of the cluster start.
 */
size_t wcwidth_grapheme_boundary_before(const char *utf8, size_t len, size_t pos);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_GRAPHEME_H */
