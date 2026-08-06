/*
 * Main entry-points for string display width: width_u32 / width_u8.
 */
#ifndef WCWIDTH_WIDTH_H
#define WCWIDTH_WIDTH_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* How width_u32() and width_u8() treat control characters and sequences. */
typedef enum
{
    WCWIDTH_PARSE = 0, /* track horizontal cursor movement */
    WCWIDTH_STRICT,    /* raise errors on indeterminate sequences */
    WCWIDTH_IGNORE,    /* strip all control codes and sequences */
} wcwidth_control_mode_t;

/* Error codes written to the *error out-param of width_u32/width_u8 (and the
 * string-measuring functions of clip.h/align.h).  Distinct codes let callers
 * distinguish the failure cause. */
typedef enum
{
    WCWIDTH_ERROR_NONE = 0,         /* no error */
    WCWIDTH_ERROR_INDETERMINATE,        /* indeterminate terminal sequence */
    WCWIDTH_ERROR_ILLEGAL_CTRL,         /* illegal C0/C1 control character */
    WCWIDTH_ERROR_VERTICAL_CTRL,        /* vertical movement control character */
    WCWIDTH_ERROR_CURSOR_LEFT_EXCEED,   /* CUB/backspace moves before column 0 */
    WCWIDTH_ERROR_CURSOR_LEFT_ABSOLUTE, /* HPA to an indeterminate column */
    WCWIDTH_ERROR_HORIZONTAL_MOVEMENT,  /* CR with indeterminate starting column */
} wcwidth_error_t;

/* Measurement options for width_u32() and width_u8(). */
typedef struct
{
    int tabsize;              /* tab stop width (default 8) */
    int ambiguous_width;      /* 1 or 2 */
    const char *term_program; /* NULL or terminal name */
} wcwidth_width_opts_t;

/* Default options for width_u32() and width_u8(). */
extern const wcwidth_width_opts_t WCWIDTH_WIDTH_OPTS_DEFAULT;

/*
 * Measure the visible width of text, including terminal control sequences
 * such as colors, bold, tabstops, cursor movement, OSC 8 hyperlinks, and
 * OSC 66 Text Sizing.  width_u32() encodes its codepoints to UTF-8 and
 * measures as width_u8().
 *
 * mode:  how control characters and sequences are treated (WCWIDTH_PARSE,
 *        WCWIDTH_STRICT, or WCWIDTH_IGNORE).
 * opts:  measurement options, or NULL for defaults.
 * error: written with a wcwidth_error_t code when mode is WCWIDTH_STRICT and
 *        the input is indeterminate; may be NULL.
 *
 * Returns the width in display cells, or -1 on error.
 */
int width_u32(const uint32_t *codepoints, size_t n, wcwidth_control_mode_t mode,
              const wcwidth_width_opts_t *opts, int *error);

/* UTF-8 variant of width_u32(). */
int width_u8(const char *utf8, size_t n, wcwidth_control_mode_t mode,
             const wcwidth_width_opts_t *opts, int *error);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_WIDTH_H */
