/*
 * Text wrapping with ANSI-aware display width measurement.
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

/* How to choose break opportunities. */
typedef enum
{
    WCWIDTH_LINE_BREAK_UNICODE = 0, /* Unicode Standard Annex #14 (default) */
    WCWIDTH_LINE_BREAK_ASCII = 1    /* ASCII whitespace only, like Python textwrap */
} wcwidth_line_break_mode_t;

/* Options for wcwidth_wrap_u8() and wcwidth_wrap_u8_text(). */
typedef struct
{
    int width; /* max line width in display cells */
    wcwidth_control_mode_t control_codes;
    int tabsize; /* tab stop width; <= 0 passes tabs through as-is */
    int ambiguous_width;
    const char *term_program;
    bool expand_tabs;
    bool replace_whitespace;
    bool break_long_words;
    bool break_on_hyphens; /* allow optional breaks after hyphens; default true */
    bool drop_whitespace;
    int max_lines; /* 0 = no limit */
    const char *initial_indent;
    const char *subsequent_indent;
    const char *placeholder;              /* for truncation, default " [...]" */
    wcwidth_line_break_mode_t line_break; /* UAX #14 by default */
} wcwidth_wrap_opts_t;

/* Default options for wrap(). */
extern const wcwidth_wrap_opts_t WCWIDTH_WRAP_OPTS_DEFAULT;

/*
 * Wrap UTF-8 text into lines.
 *
 * Break opportunities follow UAX #14 by default.  With replace_whitespace (the
 * default), '\n' and other ASCII whitespace are replaced with spaces and
 * collapsed; with replace_whitespace=false, hard line breaks are honored.
 * Use wcwidth_wrap_u8_text() to preserve input newlines as paragraph breaks.
 *
 * Returns 0 on success, -1 on allocation error, and -2 when the placeholder
 * does not fit (max_lines truncation).  On success, *out points to a single
 * malloc'd buffer containing all lines, separated by '\n' (no trailing
 * newline), with *out_len its total byte length.  The caller frees *out once.
 */
int wcwidth_wrap_u8(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts, char **out,
                    size_t *out_len);

/*
 * Like wcwidth_wrap_u8(), but also reports the start offset of each line in the
 * output buffer.  Lines are joined by '\n', so a line's byte length is
 * *offsets*[i+1] - *offsets*[i] - 1 (or *out_len* - *offsets*[i] for the
 * last), and a line may itself contain '\n' when the placeholder does.
 *
 * Returns the same codes as wcwidth_wrap_u8().  On success, *offsets* is a malloc'd
 * array of *offset_count* start offsets; the caller does free(*offsets) in
 * addition to free(*out).  Empty output yields *offset_count* == 0.
 */
int wcwidth_wrap_lines_u8(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts,
                          char **out, size_t *out_len, size_t **offsets, size_t *offset_count);

/*
 * Wrap UTF-8 text preserving input newlines as paragraph breaks.
 *
 * Splits text on '\n', wraps each non-empty line individually with wcwidth_wrap_u8(),
 * and preserves empty or whitespace-only lines as paragraph breaks.  Paragraph
 * breaks appear as "\n\n" in the output.
 *
 * Returns 0 on success, -1 on allocation error.
 * On success, *out points to a single malloc'd buffer containing all lines,
 * separated by '\n' (no trailing newline).  *out_len is the total byte length.
 * The caller does a single free(*out) to release memory.
 */
int wcwidth_wrap_u8_text(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts,
                         char **out, size_t *out_len);

/*
 * Codepoint-array variant of wcwidth_wrap_u8(): encodes the codepoints to UTF-8,
 * wraps, and decodes the result back to a codepoint array.  The output is a
 * malloc'd array of *out_len* codepoints and the caller does a single free()
 * of it, exactly as wcwidth_wrap_u8() returns UTF-8 bytes.
 *
 * Returns 0 on success, -1 on allocation error.
 */
int wcwidth_wrap_u32(const uint32_t *codepoints, size_t n, const wcwidth_wrap_opts_t *opts,
                     uint32_t **out, size_t *out_len);

/*
 * Codepoint-array variant of wcwidth_wrap_u8_text().
 */
int wcwidth_wrap_u32_text(const uint32_t *codepoints, size_t n, const wcwidth_wrap_opts_t *opts,
                          uint32_t **out, size_t *out_len);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_TEXTWRAP_H */
