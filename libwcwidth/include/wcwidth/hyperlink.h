/*
 * OSC 8 Hyperlink protocol parsing and creation.
 *
 * Port of wcwidth/_hyperlink.py.
 */
#ifndef WCWIDTH_HYPERLINK_H
#define WCWIDTH_HYPERLINK_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Parsed OSC 8 hyperlink parameters. */
typedef struct
{
    const char *url;
    size_t url_len;
    const char *params;
    size_t params_len;
    char terminator; /* '\x07' or '\x1b' (ST) */
} wcwidth_hyperlink_params_t;

/* Try to parse an OSC 8 open sequence.
 * seq: pointer to the escape sequence text
 * seq_len: length of sequence
 * Returns true if this is a valid OSC 8 open sequence, filling *params.
 * Pointers in params point into seq.
 */
bool wcwidth_hyperlink_parse_open(const char *seq, size_t seq_len,
                                  wcwidth_hyperlink_params_t *params);

/* Generate an OSC 8 open sequence into *out*.
 * Returns bytes written (excluding NUL terminator if any).
 * out_cap must be large enough: 6 + params_len + url_len + terminator.
 */
size_t wcwidth_hyperlink_make_open(const wcwidth_hyperlink_params_t *params, char *out,
                                   size_t out_cap);

/* Generate an OSC 8 close sequence into *out*.
 * terminator: '\x07' or '\x1b' (ST)
 * Returns bytes written (excluding NUL).
 */
size_t wcwidth_hyperlink_make_close(char terminator, char *out, size_t out_cap);

/* Find the matching OSC 8 close sequence in *text* starting at *search_start*.
 * Fills *close_start and *close_end with byte offsets, or sets both to (size_t)-1.
 */
void wcwidth_hyperlink_find_close(const char *text, size_t text_len, size_t search_start,
                                  size_t *close_start, size_t *close_end);

/* Generate a unique hyperlink id as 8 hex chars.
 * Writes exactly 8 bytes to *out* (no NUL).
 */
void wcwidth_hyperlink_next_id(char *out);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_HYPERLINK_H */
