/*
 * SGR (Select Graphic Rendition) escape sequence state machine.
 */
#include "wcwidth/sgr.h"

#include "wcwidth_assert.h"

#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <limits.h>

/* One semicolon-delimited parameter: an integer or a colon-separated tuple. */
typedef struct
{
    int values[WCWIDTH_SGR_COLOR_MAX];
    int count;
    bool tuple;
} sgr_token_t;

typedef struct
{
    const char *p;
    const char *end;
} sgr_reader_t;

const wcwidth_sgr_state_t WCWIDTH_SGR_STATE_DEFAULT = {0};

static int
parse_int(const char *s, size_t len)
{
    int val = 0;
    size_t i = 0;

    while (i < len && (unsigned char) s[i] >= '0' && (unsigned char) s[i] <= '9') {
        int digit = (int) (s[i] - '0');

        /* Saturate: SGR parameters are attacker-controlled and signed
         * overflow is undefined behaviour.  No real SGR code approaches
         * INT_MAX, so a clamped value is rejected downstream just as the
         * true one would be. */
        if (val > (INT_MAX - digit) / 10) {
            val = INT_MAX;
            while (i < len && (unsigned char) s[i] >= '0' && (unsigned char) s[i] <= '9') {
                i++;
            }
            break;
        }
        val = val * 10 + digit;
        i++;
    }
    return val;
}

static int
parse_colon_tuple(const char *s, size_t len, int *out, int max_out)
{
    int count = 0;
    size_t i = 0;

    while (i < len && count < max_out) {
        size_t part_start = i;

        while (i < len && s[i] != ':') {
            i++;
        }
        out[count++] = parse_int(s + part_start, i - part_start);
        if (i < len && s[i] == ':') {
            i++;
        }
    }
    return count;
}

static void
set_color(int *dst, int *dst_len, const int *src, int src_len)
{
    int i;

    *dst_len = (src_len <= WCWIDTH_SGR_COLOR_MAX) ? src_len : WCWIDTH_SGR_COLOR_MAX;
    for (i = 0; i < *dst_len; i++) {
        dst[i] = src[i];
    }
}

static bool sgr_reader_next(sgr_reader_t *reader, sgr_token_t *token);
static bool sgr_read_extended_color(sgr_reader_t *reader, int base, int *color, int *color_len);

static void
apply_integer_param(wcwidth_sgr_state_t *state, int val)
{
    if (val == 0) {
        *state = WCWIDTH_SGR_STATE_DEFAULT;
    }
    else if (val == 1) {
        state->bold = true;
    }
    else if (val == 2) {
        state->dim = true;
    }
    else if (val == 3) {
        state->italic = true;
    }
    else if (val == 4) {
        state->underline = true;
    }
    else if (val == 5) {
        state->blink = true;
    }
    else if (val == 6) {
        state->rapid_blink = true;
    }
    else if (val == 7) {
        state->inverse = true;
    }
    else if (val == 8) {
        state->hidden = true;
    }
    else if (val == 9) {
        state->strikethrough = true;
    }
    else if (val == 21) {
        state->double_underline = true;
    }
    else if (val == 22) {
        state->bold = false;
        state->dim = false;
    }
    else if (val == 23) {
        state->italic = false;
    }
    else if (val == 24) {
        state->underline = false;
        state->double_underline = false;
    }
    else if (val == 25) {
        state->blink = false;
        state->rapid_blink = false;
    }
    else if (val == 27) {
        state->inverse = false;
    }
    else if (val == 28) {
        state->hidden = false;
    }
    else if (val == 29) {
        state->strikethrough = false;
    }
    else if ((val >= 30 && val <= 37) || (val >= 90 && val <= 97)) {
        state->fg[0] = val;
        state->fg_len = 1;
    }
    else if ((val >= 40 && val <= 47) || (val >= 100 && val <= 107)) {
        state->bg[0] = val;
        state->bg_len = 1;
    }
    else if (val == 39) {
        state->fg_len = 0;
    }
    else if (val == 49) {
        state->bg_len = 0;
    }
}

void
wcwidth_sgr_update(wcwidth_sgr_state_t *state, const char *sgr_params, size_t sgr_params_len)
{
    sgr_reader_t reader;
    sgr_token_t token;

    /* Empty params is equivalent to "0" (reset): \x1b[m. */
    if (sgr_params_len == 0) {
        *state = WCWIDTH_SGR_STATE_DEFAULT;
        return;
    }

    reader.p = sgr_params;
    reader.end = sgr_params + sgr_params_len;

    /* Apply parameters as they are read */
    while (sgr_reader_next(&reader, &token)) {
        if (!token.tuple) {
            int val = token.values[0];

            if (val == 38 || val == 48) {
                int color[WCWIDTH_SGR_COLOR_MAX];
                int color_len = 0;

                if (sgr_read_extended_color(&reader, val, color, &color_len)) {
                    if (val == 38) {
                        set_color(state->fg, &state->fg_len, color, color_len);
                    }
                    else {
                        set_color(state->bg, &state->bg_len, color, color_len);
                    }
                }
            }
            else {
                apply_integer_param(state, val);
            }
        }
        else if (token.count >= 2 && (token.values[0] == 38 || token.values[0] == 48)) {
            if (token.values[0] == 38) {
                set_color(state->fg, &state->fg_len, token.values, token.count);
            }
            else {
                set_color(state->bg, &state->bg_len, token.values, token.count);
            }
        }
    }
}

/*
 * Read the next semicolon-delimited parameter.  Empty parameters are zero.
 * Returns false at the end of the string.
 */
static bool
sgr_reader_next(sgr_reader_t *reader, sgr_token_t *token)
{
    const char *seg_end;
    size_t seg_len;
    size_t i;
    bool has_colon = false;

    if (reader->p >= reader->end) {
        return false;
    }

    seg_end = reader->p;
    while (seg_end < reader->end && *seg_end != ';') {
        seg_end++;
    }
    seg_len = (size_t) (seg_end - reader->p);

    token->count = 1;
    token->tuple = false;
    token->values[0] = 0;

    for (i = 0; i < seg_len; i++) {
        if (reader->p[i] == ':') {
            has_colon = true;
            break;
        }
    }
    if (has_colon) {
        token->tuple = true;
        token->count = parse_colon_tuple(reader->p, seg_len, token->values, WCWIDTH_SGR_COLOR_MAX);
    }
    else if (seg_len > 0) {
        token->values[0] = parse_int(reader->p, seg_len);
    }

    reader->p = seg_end;
    if (reader->p < reader->end && *reader->p == ';') {
        reader->p++;
    }
    return true;
}

/*
 * Read the parameters of an extended color after its 38/48 code.
 *
 * xterm and kitty both accept the base as a separate parameter with a colon group for the mode and
 * components, for example 38;5:196 and 38;2:1:2:3.  See parse_extended_colors() in xterm's
 * charproc.c and _parse_sgr() in kitty's vt-parser.c.
 *
 * Returns true when a complete color was read.  On failure the parameters read are consumed.
 */
static bool
sgr_read_extended_color(sgr_reader_t *reader, int base, int *color, int *color_len)
{
    sgr_token_t token;
    int mode;

    if (!sgr_reader_next(reader, &token)) {
        return false;
    }

    if (token.tuple) {
        mode = token.values[0];
        if (mode == 5 && token.count == 2) {
            color[0] = base;
            color[1] = 5;
            color[2] = token.values[1];
            *color_len = 3;
            return true;
        }
        if (mode == 2 && (token.count == 4 || token.count == 5)) {
            int i;

            color[0] = base;
            color[1] = 2;
            for (i = 1; i < token.count; i++) {
                color[i + 1] = token.values[i];
            }
            *color_len = token.count + 1;
            return true;
        }
        return false;
    }

    mode = token.values[0];
    if (mode == 5) {
        if (!sgr_reader_next(reader, &token) || token.tuple) {
            return false;
        }
        color[0] = base;
        color[1] = 5;
        color[2] = token.values[0];
        *color_len = 3;
        return true;
    }
    if (mode == 2) {
        int i;

        color[0] = base;
        color[1] = 2;
        for (i = 0; i < 3; i++) {
            if (!sgr_reader_next(reader, &token) || token.tuple) {
                return false;
            }
            color[2 + i] = token.values[0];
        }
        *color_len = 5;
        return true;
    }
    return false;
}

bool
wcwidth_sgr_is_active(const wcwidth_sgr_state_t *state)
{
    return (state->bold || state->dim || state->italic || state->underline || state->blink
            || state->rapid_blink || state->inverse || state->hidden || state->strikethrough
            || state->double_underline || state->fg_len > 0 || state->bg_len > 0);
}

/*
 * Append a decimal integer at *offset*, within the *out_cap*-byte buffer.
 *
 * snprintf() returns the length it would have produced, so an unclamped
 * offset runs past out_cap, wraps out_cap - offset to a huge size_t, and
 * writes outside the buffer.  Clamp to out_cap - 1 on truncation.
 */
/*
 * ITU T.416 "38:2:<colour space>:R:G:B" carries an element the legacy
 * "38;2;R;G;B" form has no slot for, so rejoining it with ';' would shift R,
 * G and B one position.  Six elements with mode 2 means the colon form.
 */
static char
sgr_color_separator(const int *color, int len)
{
    return (len > 5 && color[1] == 2) ? ':' : ';';
}

static size_t
sgr_write_int(char *out, size_t out_cap, size_t offset, int value)
{
    int written;

    WCWIDTH_ASSERT(out_cap > 0);
    if (offset >= out_cap) {
        return out_cap - 1;
    }
    written = snprintf(out + offset, out_cap - offset, "%d", value);
    WCWIDTH_ASSERT(written >= 0);
    if ((size_t) written >= out_cap - offset) {
        return out_cap - 1;
    }
    return offset + (size_t) written;
}

size_t
wcwidth_sgr_to_escape(const wcwidth_sgr_state_t *state, char *out, size_t out_cap)
{
    size_t offset = 0;
    int need_sep = 0;
    int i;

    if (out_cap == 0) {
        return 0;
    }
    out[0] = '\0';

    if (!wcwidth_sgr_is_active(state)) {
        return 0;
    }

    if (offset + 2 < out_cap) {
        out[offset++] = '\x1b';
        out[offset++] = '[';
        out[offset] = '\0';
    }

    if (state->bold) {
        offset = sgr_write_int(out, out_cap, offset, 1);
        need_sep = 1;
    }
    if (state->dim) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset = sgr_write_int(out, out_cap, offset, 2);
        need_sep = 1;
    }
    if (state->italic) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset = sgr_write_int(out, out_cap, offset, 3);
        need_sep = 1;
    }
    if (state->underline) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset = sgr_write_int(out, out_cap, offset, 4);
        need_sep = 1;
    }
    if (state->blink) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset = sgr_write_int(out, out_cap, offset, 5);
        need_sep = 1;
    }
    if (state->rapid_blink) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset = sgr_write_int(out, out_cap, offset, 6);
        need_sep = 1;
    }
    if (state->inverse) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset = sgr_write_int(out, out_cap, offset, 7);
        need_sep = 1;
    }
    if (state->hidden) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset = sgr_write_int(out, out_cap, offset, 8);
        need_sep = 1;
    }
    if (state->strikethrough) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset = sgr_write_int(out, out_cap, offset, 9);
        need_sep = 1;
    }
    if (state->double_underline) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset = sgr_write_int(out, out_cap, offset, 21);
        need_sep = 1;
    }

    if (state->fg_len > 0) {
        char inner = sgr_color_separator(state->fg, state->fg_len);
        for (i = 0; i < state->fg_len; i++) {
            if (need_sep && i == 0 && offset < out_cap)
                out[offset++] = ';';
            if (i > 0 && offset < out_cap)
                out[offset++] = inner;
            offset = sgr_write_int(out, out_cap, offset, state->fg[i]);
        }
        need_sep = 1;
    }

    if (state->bg_len > 0) {
        char inner = sgr_color_separator(state->bg, state->bg_len);
        for (i = 0; i < state->bg_len; i++) {
            if (need_sep && i == 0 && offset < out_cap)
                out[offset++] = ';';
            if (i > 0 && offset < out_cap)
                out[offset++] = inner;
            offset = sgr_write_int(out, out_cap, offset, state->bg[i]);
        }
        need_sep = 1;
        (void) need_sep;
    }

    /* Both the 'm' and the terminator must land inside the buffer: writing
     * 'm' at out_cap - 1 would put the NUL at out_cap, one past the end. */
    if (offset + 1 < out_cap) {
        out[offset++] = 'm';
        out[offset] = '\0';
    }
    else if (out_cap > 0) {
        offset = out_cap - 1;
        out[offset] = '\0';
    }

    return offset;
}

/*
 * Extract SGR params from a CSI sequence.
 * line[pos] == '\x1b', line[pos+1] == '['.
 * Returns length consumed, or 0 if not a valid SGR.
 */
static size_t
extract_sgr_params(const char *line, size_t line_len, size_t pos, const char **params,
                   size_t *params_len)
{
    size_t p = pos + 2; /* skip ESC [ */
    size_t params_start = p;

    /* scan parameter bytes: 0x30-0x3F */
    while (p < line_len) {
        unsigned char ch = (unsigned char) line[p];

        if (ch >= 0x30 && ch <= 0x3F) {
            p++;
            continue;
        }
        break;
    }

    /* skip intermediate bytes: 0x20-0x2F */
    while (p < line_len) {
        unsigned char ch = (unsigned char) line[p];

        if (ch >= 0x20 && ch <= 0x2F) {
            p++;
            continue;
        }
        break;
    }

    /* expect final byte 'm' */
    if (p >= line_len || (unsigned char) line[p] != 'm') {
        return 0;
    }
    p++; /* consume 'm' */

    *params = line + params_start;
    *params_len = p - params_start - 1; /* exclude 'm' */
    return p - pos;
}

/*
 * Longest possible state restore: "\x1b[" + ten boolean attributes (two
 * digits and a separator each) + foreground and background (six ints of up to
 * eleven characters, separator included) + 'm'.
 */
#define SGR_PREFIX_MAX                                                                             \
    (2 + 10 * 3 + 2 * (WCWIDTH_SGR_COLOR_MAX * 11 + (WCWIDTH_SGR_COLOR_MAX - 1)) + 1)
_Static_assert(SGR_PREFIX_MAX + (sizeof("\x1b[0m") - 1) + 1 <= WCWIDTH_SGR_PROPAGATE_SPARE,
               "SGR restore prefix and reset must fit WCWIDTH_SGR_PROPAGATE_SPARE");

int
wcwidth_sgr_propagate(char **lines, const size_t *line_lens, size_t *out_lens, size_t nlines)
{
    wcwidth_sgr_state_t state;
    size_t li;

    state = WCWIDTH_SGR_STATE_DEFAULT;

    for (li = 0; li < nlines; li++) {
        char *line = lines[li];
        size_t line_len = line_lens[li];
        char prefix[WCWIDTH_SGR_PROPAGATE_SPARE];
        size_t prefix_len;
        size_t suffix_len;
        const char reset[] = "\x1b[0m";
        size_t pos;

        /* (1) generate restore prefix from carried-over state */
        wcwidth_sgr_to_escape(&state, prefix, sizeof(prefix));
        prefix_len = strlen(prefix);

        /* (2) scan line for SGR sequences, updating state */
        pos = 0;
        while (pos < line_len) {
            if (line[pos] == '\x1b' && pos + 1 < line_len && line[pos + 1] == '[') {
                const char *params;
                size_t params_len;
                size_t consumed;

                consumed = extract_sgr_params(line, line_len, pos, &params, &params_len);
                if (consumed > 0) {
                    wcwidth_sgr_update(&state, params, params_len);
                    pos += consumed;
                    continue;
                }
            }
            pos++;
        }

        /* (3) determine suffix */
        suffix_len = 0;
        if (wcwidth_sgr_is_active(&state)) {
            suffix_len = sizeof(reset) - 1;
        }

        /* (4) insert prefix: shift content right */
        if (prefix_len > 0) {
            memmove(line + prefix_len, line, line_len + 1);
            memcpy(line, prefix, prefix_len);
        }

        /* (5) append suffix */
        if (suffix_len > 0) {
            memcpy(line + line_len + prefix_len, reset, suffix_len + 1);
        }

        if (out_lens != NULL) {
            out_lens[li] = line_len + prefix_len + suffix_len;
        }
    }

    return 0;
}
