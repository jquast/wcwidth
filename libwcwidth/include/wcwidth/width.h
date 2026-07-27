/*
 * Main entry-points for string display width: width_u32 / width_u8.
 *
 * Port of wcwidth/_width.py.
 */
#ifndef WCWIDTH_WIDTH_H
#define WCWIDTH_WIDTH_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum
{
    WCWIDTH_PARSE = 0, /* track horizontal cursor movement */
    WCWIDTH_STRICT,    /* raise errors on indeterminate sequences */
    WCWIDTH_IGNORE,    /* strip all control codes and sequences */
} wcwidth_control_mode_t;

typedef struct
{
    int tabsize;              /* tab stop width (default 8) */
    int ambiguous_width;      /* 1 or 2 */
    const char *term_program; /* NULL or terminal name */
} wcwidth_width_opts_t;

/* Default options for width(). */
extern const wcwidth_width_opts_t WCWIDTH_WIDTH_OPTS_DEFAULT;

int width_u32(const uint32_t *codepoints, size_t n, wcwidth_control_mode_t mode,
              const wcwidth_width_opts_t *opts, int *error);
int width_u8(const char *utf8, size_t n, wcwidth_control_mode_t mode,
             const wcwidth_width_opts_t *opts, int *error);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_WIDTH_H */
