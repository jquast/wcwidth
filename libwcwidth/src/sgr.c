/*
 * SGR (Select Graphic Rendition) escape sequence state machine.
 */
#include "wcwidth/sgr.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>

#define WCWIDTH_SGR_MAX_PARAMS 64

const wcwidth_sgr_state_t WCWIDTH_SGR_STATE_DEFAULT = {0};

static int
parse_int(const char *s, size_t len)
{
    int val = 0;
    size_t i = 0;

    while (i < len && (unsigned char) s[i] >= '0' && (unsigned char) s[i] <= '9') {
        val = val * 10 + (int) (s[i] - '0');
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

void
wcwidth_sgr_update(wcwidth_sgr_state_t *state, const char *sgr_params, size_t sgr_params_len)
{
    int params[WCWIDTH_SGR_MAX_PARAMS];
    int nparams = 0;
    const char *p = sgr_params;
    const char *end = sgr_params + sgr_params_len;
    int i;

    /* Empty params is equivalent to "0" (reset) -- \x1b[m. */
    if (sgr_params_len == 0) {
        *state = WCWIDTH_SGR_STATE_DEFAULT;
        return;
    }

    /* Phase 1: parse all semicolon-separated segments.
     * Colon-separated tuples (ITU T.416 extended colors) are applied
     * immediately.  Plain integers are collected for phase 2. */
    while (p < end && nparams < WCWIDTH_SGR_MAX_PARAMS) {
        const char *seg_end = p;

        while (seg_end < end && *seg_end != ';') {
            seg_end++;
        }
        {
            size_t seg_len = (size_t) (seg_end - p);

            if (seg_len == 0) {
                params[nparams++] = 0;
            }
            else {
                int has_colon = 0;
                size_t j;

                for (j = 0; j < seg_len; j++) {
                    if (p[j] == ':') {
                        has_colon = 1;
                        break;
                    }
                }

                if (has_colon) {
                    int tuple[WCWIDTH_SGR_COLOR_MAX];
                    int n = parse_colon_tuple(p, seg_len, tuple, WCWIDTH_SGR_COLOR_MAX);
                    if (n >= 2 && tuple[0] == 38) {
                        set_color(state->fg, &state->fg_len, tuple, n);
                    }
                    else if (n >= 2 && tuple[0] == 48) {
                        set_color(state->bg, &state->bg_len, tuple, n);
                    }
                }
                else {
                    params[nparams++] = parse_int(p, seg_len);
                }
            }
        }

        p = seg_end;
        if (p < end && *p == ';') {
            p++;
        }
    }

    /* Phase 2: apply integer parameters in order. */
    for (i = 0; i < nparams; i++) {
        int val = params[i];

        if (val == 0) {
            *state = WCWIDTH_SGR_STATE_DEFAULT;
            continue;
        }

        if (val == 1) {
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
        else if (val == 38 && i + 2 < nparams) {
            int mode = params[++i];

            if (mode == 5 && i + 1 < nparams) {
                int n = params[++i];

                state->fg[0] = 38;
                state->fg[1] = 5;
                state->fg[2] = n;
                state->fg_len = 3;
            }
            else if (mode == 2 && i + 3 < nparams) {
                int r = params[++i];
                int g = params[++i];
                int b = params[++i];

                state->fg[0] = 38;
                state->fg[1] = 2;
                state->fg[2] = r;
                state->fg[3] = g;
                state->fg[4] = b;
                state->fg_len = 5;
            }
        }
        else if (val == 48 && i + 2 < nparams) {
            int mode = params[++i];

            if (mode == 5 && i + 1 < nparams) {
                int n = params[++i];

                state->bg[0] = 48;
                state->bg[1] = 5;
                state->bg[2] = n;
                state->bg_len = 3;
            }
            else if (mode == 2 && i + 3 < nparams) {
                int r = params[++i];
                int g = params[++i];
                int b = params[++i];

                state->bg[0] = 48;
                state->bg[1] = 2;
                state->bg[2] = r;
                state->bg[3] = g;
                state->bg[4] = b;
                state->bg_len = 5;
            }
        }
    }
}

bool
wcwidth_sgr_is_active(const wcwidth_sgr_state_t *state)
{
    return (state->bold || state->dim || state->italic || state->underline || state->blink
            || state->rapid_blink || state->inverse || state->hidden || state->strikethrough
            || state->double_underline || state->fg_len > 0 || state->bg_len > 0);
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
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "1");
        need_sep = 1;
    }
    if (state->dim) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "2");
        need_sep = 1;
    }
    if (state->italic) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "3");
        need_sep = 1;
    }
    if (state->underline) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "4");
        need_sep = 1;
    }
    if (state->blink) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "5");
        need_sep = 1;
    }
    if (state->rapid_blink) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "6");
        need_sep = 1;
    }
    if (state->inverse) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "7");
        need_sep = 1;
    }
    if (state->hidden) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "8");
        need_sep = 1;
    }
    if (state->strikethrough) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "9");
        need_sep = 1;
    }
    if (state->double_underline) {
        if (need_sep && offset < out_cap)
            out[offset++] = ';';
        offset += (size_t) snprintf(out + offset, out_cap - offset, "21");
        need_sep = 1;
    }

    if (state->fg_len > 0) {
        for (i = 0; i < state->fg_len; i++) {
            if (need_sep && i == 0 && offset < out_cap)
                out[offset++] = ';';
            if (i > 0 && offset < out_cap)
                out[offset++] = ';';
            offset += (size_t) snprintf(out + offset, out_cap - offset, "%d", state->fg[i]);
        }
        need_sep = 1;
    }

    if (state->bg_len > 0) {
        for (i = 0; i < state->bg_len; i++) {
            if (need_sep && i == 0 && offset < out_cap)
                out[offset++] = ';';
            if (i > 0 && offset < out_cap)
                out[offset++] = ';';
            offset += (size_t) snprintf(out + offset, out_cap - offset, "%d", state->bg[i]);
        }
        need_sep = 1;
        (void) need_sep;
    }

    if (offset < out_cap) {
        out[offset++] = 'm';
        out[offset] = '\0';
    }
    else if (out_cap > 0) {
        out[out_cap - 1] = '\0';
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

        /* (4) heuristic capacity check */
        if (line_len + prefix_len + suffix_len + 1 > line_len + WCWIDTH_SGR_PROPAGATE_SPARE) {
            return -1;
        }

        /* (5) insert prefix: shift content right */
        if (prefix_len > 0) {
            memmove(line + prefix_len, line, line_len + 1);
            memcpy(line, prefix, prefix_len);
        }

        /* (6) append suffix */
        if (suffix_len > 0) {
            memcpy(line + line_len + prefix_len, reset, suffix_len + 1);
        }

        if (out_lens != NULL) {
            out_lens[li] = line_len + prefix_len + suffix_len;
        }
    }

    return 0;
}
