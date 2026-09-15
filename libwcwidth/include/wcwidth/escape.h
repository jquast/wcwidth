/*
 * Terminal escape sequence classification.
 */
#ifndef WCWIDTH_ESCAPE_H
#define WCWIDTH_ESCAPE_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Types of escape sequences the parser can classify. */
typedef enum
{
    WCWIDTH_ESC_NONE = 0,      /* not an escape sequence */
    WCWIDTH_ESC_UNRECOGNIZED,  /* lone ESC or malformed */
    WCWIDTH_ESC_SGR,           /* CSI ... m (Select Graphic Rendition) */
    WCWIDTH_ESC_CUF,           /* CSI n C (Cursor Forward) */
    WCWIDTH_ESC_CUB,           /* CSI n D (Cursor Backward) */
    WCWIDTH_ESC_HPA,           /* CSI n G (Horizontal Position Absolute) */
    WCWIDTH_ESC_OSC66,         /* OSC 66;... (Text Sizing) */
    WCWIDTH_ESC_INDETERMINATE, /* clear, scroll, cursor up/down, etc. */
    WCWIDTH_ESC_OTHER,         /* any other recognized zero-width sequence */
} wcwidth_esc_type_t;

/* Parsed parameters from a classified escape sequence. */
typedef struct
{
    wcwidth_esc_type_t type;
    const char *start; /* pointer to start of sequence in original text */
    size_t length;     /* total length of sequence in bytes */

    /* For SGR: pointer to parameter string (after CSI, before 'm'), length */
    const char *sgr_params;
    size_t sgr_params_len;

    /* For CUF/CUB/HPA: parsed numeric parameter (defaults to 1 if absent) */
    int cursor_n;

    /* For OSC 66: pointers to meta, text, and terminator parts */
    const char *ts_meta;
    size_t ts_meta_len;
    const char *ts_text;
    size_t ts_text_len;
    char ts_terminator; /* '\x07' or '\x1b' (ST) */
} wcwidth_esc_result_t;

/* Classify the escape sequence starting at *text[offset]*.
 * Returns false if no escape sequence is found (text[offset] != ESC).
 * On success, fills *result with parsed data and returns true.
 *
 * *text*: full input text
 * *text_len*: total length of text
 * *offset*: position of the ESC character
 * *result*: output, filled on success
 */
bool wcwidth_escape_classify(const char *text, size_t text_len, size_t offset,
                             wcwidth_esc_result_t *result);

/* Strip all terminal escape sequences from text.
 * OSC 66 inner display text is preserved as visible output.
 * Writes result to *out* (caller-provided buffer).
 * *out_cap*: capacity of out buffer.
 * *out_len*: filled with actual bytes written (excluding NUL terminator if any).
 *
 * Returns the byte length of the stripped text, excluding the NUL terminator,
 * so *out* must have capacity for the return value plus one.  Output was
 * truncated when the return value is >= out_cap; pass an out_cap of 0 to
 * measure without writing.
 */
size_t wcwidth_escape_strip(const char *text, size_t text_len, char *out, size_t out_cap,
                            size_t *out_len);

/*
 * Codepoint-array variant of wcwidth_escape_strip(): encodes the codepoints
 * to UTF-8, strips, and decodes the result back to a codepoint array.  The
 * returned array is *out_len* codepoints and the caller does a single free()
 * of it; returns NULL on allocation failure.
 */
uint32_t *wcwidth_escape_strip_u32(const uint32_t *codepoints, size_t n, size_t *out_len);

/* Callback for iterating over text segments.
 * segment: text segment
 * seg_len: length of segment
 * is_escape: true if this segment is an escape sequence, false if visible text
 * userdata: caller-provided pointer
 */
typedef void (*wcwidth_escape_iter_fn)(const char *segment, size_t seg_len, bool is_escape,
                                       void *userdata);

/* Iterate over text, calling *fn* for each segment (escape or visible text),
 * without allocating. */
void wcwidth_escape_iter(const char *text, size_t text_len, wcwidth_escape_iter_fn fn,
                         void *userdata);

/* Check if text contains any horizontal cursor movement:
 *   BS (0x08), CR (0x0d), or CSI n C/D/G
 * Returns true if found.
 */
bool wcwidth_escape_has_cursor_movement(const char *text, size_t text_len);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_ESCAPE_H */
