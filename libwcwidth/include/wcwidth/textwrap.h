/*
 * Text wrapping with ANSI-aware display width measurement.
 *
 * Port of wcwidth/_textwrap.py.
 */
#ifndef WCWIDTH_TEXTWRAP_H
#define WCWIDTH_TEXTWRAP_H

#include "width.h"
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct
{
    int width; /* max line width in display cells */
    wcwidth_control_mode_t control_codes;
    int tabsize;
    int ambiguous_width;
    const char *term_program;
    bool expand_tabs;
    bool replace_whitespace;
    bool break_long_words;
    bool break_on_hyphens;
    bool drop_whitespace;
    bool propagate_sgr;
    int max_lines; /* 0 = no limit */
    const char *initial_indent;
    const char *subsequent_indent;
    const char *placeholder; /* for truncation, default " [...]" */
} wcwidth_wrap_opts_t;

extern const wcwidth_wrap_opts_t WCWIDTH_WRAP_OPTS_DEFAULT;

/*
 * Wrap UTF-8 text into lines.
 *
 * Treats all whitespace (including '\n') as inter-word spaces and collapses
 * it.  Use wrap_u8_text() to preserve input newlines as paragraph breaks.
 *
 * Returns 0 on success, -1 on allocation error.
 * On success, *out points to a single malloc'd buffer containing all lines,
 * separated by '\n' (no trailing newline).  *out_len is the total byte length.
 * The caller does a single free(*out) to release memory.
 */
int wrap_u8(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts, char **out,
            size_t *out_len);

/*
 * Wrap UTF-8 text preserving input newlines as paragraph breaks.
 *
 * Splits text on '\n', wraps each non-empty line individually with wrap_u8(),
 * and preserves empty or whitespace-only lines as paragraph breaks.  Paragraph
 * breaks appear as "\n\n" in the output.
 *
 * Returns 0 on success, -1 on allocation error.
 * On success, *out points to a single malloc'd buffer containing all lines,
 * separated by '\n' (no trailing newline).  *out_len is the total byte length.
 * The caller does a single free(*out) to release memory.
 */
int wrap_u8_text(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts,
                 char **out, size_t *out_len);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_TEXTWRAP_H */
