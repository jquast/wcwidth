/*
 * SGR (Select Graphic Rendition) escape sequence state management.
 *
 * Port of wcwidth/_sgr.py.
 */
#ifndef WCWIDTH_SGR_H
#define WCWIDTH_SGR_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Maximum number of color components stored (e.g. (38, 5, N) or (38, 2, R, G, B)). */
#define WCWIDTH_SGR_COLOR_MAX 6

/* SGR state tracking: boolean attributes + foreground/background color. */
typedef struct
{
    bool bold, dim, italic, underline, blink, rapid_blink;
    bool inverse, hidden, strikethrough, double_underline;

    /* Foreground color: first element is 38 or 0; 0 = default/unset. */
    int fg[WCWIDTH_SGR_COLOR_MAX];
    int fg_len;

    /* Background color: first element is 48 or 0; 0 = default/unset. */
    int bg[WCWIDTH_SGR_COLOR_MAX];
    int bg_len;
} wcwidth_sgr_state_t;

/* Default state (no attributes, no colors). */
extern const wcwidth_sgr_state_t WCWIDTH_SGR_STATE_DEFAULT;

/* Parse an SGR escape sequence and update *state*.
 * sgr_params: the parameter string (between '[' and 'm'), e.g. "1;31;44"
 * sgr_params_len: length of parameter string
 * state: current state, updated in-place
 */
void wcwidth_sgr_update(wcwidth_sgr_state_t *state, const char *sgr_params, size_t sgr_params_len);

/* Check if any attributes or colors are set (non-default). */
bool wcwidth_sgr_is_active(const wcwidth_sgr_state_t *state);

/* Generate the minimal SGR escape sequence needed to restore *state* from reset.
 * Writes to *out* (caller buffer). Returns bytes written (excluding NUL).
 * out_cap must be at least 64 bytes.
 */
size_t wcwidth_sgr_to_escape(const wcwidth_sgr_state_t *state, char *out, size_t out_cap);

/* Propagate SGR codes across an array of wrapped lines.
 * Each line is NUL-terminated. *nlines* lines in the array.
 * Modifies lines in-place (reallocates/resizes as needed).
 *
 * Writes results to *out_lines* pre-allocated array of *nlines* char* buffers.
 * Each buffer must be large enough for the expanded line (original + 32 bytes margin).
 * Returns 0 on success, -1 if any buffer too small.
 */
int wcwidth_sgr_propagate(char **lines, size_t nlines);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_SGR_H */
