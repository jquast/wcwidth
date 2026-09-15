/*
 * SGR (Select Graphic Rendition) escape sequence state management.
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

/* Spare capacity, in bytes, that each line passed to wcwidth_sgr_propagate
 * must have beyond its NUL terminator: the carried-over SGR state can expand
 * to this many bytes of prefix plus a reset suffix. */
#define WCWIDTH_SGR_PROPAGATE_SPARE 256

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
 * out_cap must be at least WCWIDTH_SGR_PROPAGATE_SPARE bytes.
 */
size_t wcwidth_sgr_to_escape(const wcwidth_sgr_state_t *state, char *out, size_t out_cap);

/* Propagate SGR codes across an array of wrapped lines.
 * Modifies lines in-place.  Each line is NUL-terminated and must have at
 * least WCWIDTH_SGR_PROPAGATE_SPARE bytes of spare capacity beyond *line_lens[i]*.
 * *line_lens* carries the actual byte length of each line (may include
 * embedded NULs); *out_lens* receives the new byte length after SGR
 * prefix/suffix insertion (may be NULL).
 * Returns 0 on success, -1 if any buffer is too small.
 */
int wcwidth_sgr_propagate(char **lines, const size_t *line_lens, size_t *out_lens,
                          size_t nlines);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_SGR_H */
