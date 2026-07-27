/*
 * Text truncation with sequence awareness.
 *
 * Port of wcwidth/_clip.py clip().
 */
#include "wcwidth/clip.h"
#include "wcwidth/escape.h"
#include "wcwidth/grapheme.h"
#include "wcwidth/hyperlink.h"
#include "wcwidth/sgr.h"
#include "wcwidth/text_sizing.h"
#include "wcwidth/wcwidth.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define ESC 0x1b
#define BEL 0x07

typedef struct
{
    char *buf;
    size_t len;
    size_t cap;
} strbuf_t;

static void
strbuf_init(strbuf_t *sb, size_t initial_cap)
{
    sb->buf = (char *) malloc(initial_cap);
    sb->len = 0;
    sb->cap = (sb->buf != NULL) ? initial_cap : 0;
    if (sb->buf != NULL && sb->cap > 0) {
        sb->buf[0] = '\0';
    }
}

static void
strbuf_grow(strbuf_t *sb, size_t needed)
{
    size_t new_cap;
    char *new_buf;

    if (sb->cap >= needed) {
        return;
    }
    new_cap = sb->cap ? sb->cap * 2 : 256;
    if (new_cap < needed) {
        new_cap = needed + 64;
    }
    new_buf = (char *) realloc(sb->buf, new_cap);
    if (new_buf == NULL) {
        return;
    }
    sb->buf = new_buf;
    sb->cap = new_cap;
}

static void
strbuf_append(strbuf_t *sb, const char *s, size_t len)
{
    if (len == 0) {
        return;
    }
    strbuf_grow(sb, sb->len + len + 1);
    if (sb->buf == NULL || sb->cap < sb->len + len + 1) {
        return;
    }
    memcpy(sb->buf + sb->len, s, len);
    sb->len += len;
    sb->buf[sb->len] = '\0';
}

static void
strbuf_append_char(strbuf_t *sb, char c)
{
    strbuf_append(sb, &c, 1);
}

static void
strbuf_append_repeat(strbuf_t *sb, char c, size_t count)
{
    strbuf_grow(sb, sb->len + count + 1);
    if (sb->buf == NULL || sb->cap < sb->len + count + 1) {
        return;
    }
    memset(sb->buf + sb->len, c, count);
    sb->len += count;
    sb->buf[sb->len] = '\0';
}

static void
strbuf_free(strbuf_t *sb)
{
    free(sb->buf);
    sb->buf = NULL;
    sb->len = 0;
    sb->cap = 0;
}

/*
 * Detach the buffer: return the malloc'd string and clear sb.
 * Caller owns the returned pointer and must free() it.
 */
static char *
strbuf_detach(strbuf_t *sb, size_t *out_len)
{
    char *result = sb->buf;

    if (result == NULL) {
        /* Empty -- return a valid empty string. */
        result = (char *) malloc(1);
        if (result != NULL) {
            result[0] = '\0';
        }
        if (out_len != NULL) {
            *out_len = 0;
        }
        sb->buf = NULL;
        sb->len = 0;
        sb->cap = 0;
        return result;
    }

    if (out_len != NULL) {
        *out_len = sb->len;
    }
    sb->buf = NULL;
    sb->len = 0;
    sb->cap = 0;
    return result;
}

static int
grapheme_width(const char *g, size_t g_len, int ambiguous_width, const char *term_program)
{
    if (term_program != NULL && term_program[0] != '\0') {
        return wcstwidth_u8(g, g_len, ambiguous_width, term_program);
    }
    return wcswidth_u8(g, g_len, ambiguous_width);
}

static bool
is_indeterminate_seq(const wcwidth_esc_result_t *result)
{
    return result->type == WCWIDTH_ESC_INDETERMINATE;
}

/*
 * Process an OSC 8 hyperlink within clip.
 *
 * Returns: 0=NO_CLOSE, 1=EMPTY, 2=OUTSIDE, 3=VISIBLE, -1=ALLOC_FAIL
 *
 * On VISIBLE: fills *open_seq_buf, *clipped_buf (realloc'd), etc.
 * *clipped_buf may be realloc'd; caller must free it.
 */
static int
process_hyperlink(const char *text, size_t text_len, size_t v_start, size_t v_end, char fillchar,
                  int tabsize, int ambiguous_width, const char *term_program,
                  wcwidth_control_mode_t control_codes, const wcwidth_hyperlink_params_t *params,
                  size_t match_end, int col, size_t *close_end, int *inner_width,
                  char *open_seq_buf, size_t *open_seq_len, char **clipped_buf,
                  size_t *clipped_buf_cap, size_t *clipped_inner_len, char *close_seq_buf,
                  size_t *close_seq_len, int *clipped_width, int *hl_col_end)
{
    size_t cs, ce;
    int iw;

    wcwidth_hyperlink_find_close(text, text_len, match_end, &cs, &ce);
    if (cs == (size_t) -1) {
        *close_end = 0;
        return 0; /* NO_CLOSE */
    }

    /* Measure inner text width. */
    {
        const char *inner_text = text + match_end;
        size_t inner_len = cs - match_end;
        int error2 = 0;
        wcwidth_width_opts_t opts;
        opts.tabsize = tabsize;
        opts.ambiguous_width = ambiguous_width;
        opts.term_program = term_program;
        iw = width_u8(inner_text, inner_len, control_codes, &opts, &error2);
        if (iw < 0) {
            iw = 0;
        }
    }
    *inner_width = iw;

    if (iw == 0) {
        *close_end = ce;
        return 1; /* EMPTY */
    }

    {
        int hl_end = col + iw;
        *hl_col_end = hl_end;

        if (hl_end <= (int) v_start || col >= (int) v_end) {
            *close_end = ce;
            return 2; /* OUTSIDE */
        }
    }

    /* VISIBLE: clip inner text. */
    {
        const char *inner_text = text + match_end;
        size_t inner_len = cs - match_end;
        size_t inner_clip_start = ((size_t) col < v_start) ? (v_start - (size_t) col) : 0;
        size_t inner_clip_end_val =
            ((size_t) col + (size_t) iw > v_end) ? (v_end - (size_t) col) : (size_t) iw;
        size_t need = inner_len * 4 + 256;

        if (*clipped_buf_cap < need) {
            char *new_buf = (char *) realloc(*clipped_buf, need);
            if (new_buf == NULL) {
                return -1;
            }
            *clipped_buf = new_buf;
            *clipped_buf_cap = need;
        }

        {
            size_t dummy_len = 0;
            char *clipped =
                clip_u8(inner_text, inner_len, inner_clip_start, inner_clip_end_val, control_codes,
                        tabsize, ambiguous_width, term_program, false, fillchar, &dummy_len);
            if (clipped == NULL) {
                return -1;
            }
            if (dummy_len >= *clipped_buf_cap) {
                char *new_buf = (char *) realloc(*clipped_buf, dummy_len + 1);
                if (new_buf == NULL) {
                    free(clipped);
                    return -1;
                }
                *clipped_buf = new_buf;
                *clipped_buf_cap = dummy_len + 1;
            }
            memcpy(*clipped_buf, clipped, dummy_len);
            (*clipped_buf)[dummy_len] = '\0';
            *clipped_inner_len = dummy_len;
            free(clipped);
        }

        /* Measure clipped inner width. */
        {
            int error2 = 0;
            wcwidth_width_opts_t opts;
            opts.tabsize = tabsize;
            opts.ambiguous_width = ambiguous_width;
            opts.term_program = term_program;
            *clipped_width =
                width_u8(*clipped_buf, *clipped_inner_len, control_codes, &opts, &error2);
            if (*clipped_width < 0) {
                *clipped_width = 0;
            }
        }

        *open_seq_len = wcwidth_hyperlink_make_open(params, open_seq_buf, 256);
        *close_seq_len = wcwidth_hyperlink_make_close(params->terminator, close_seq_buf, 256);
        *close_end = ce;
        return 3; /* VISIBLE */
    }
}

static bool
clip_simple(const char *text, size_t text_len, size_t v_start, size_t v_end, char fillchar,
            int tabsize, int ambiguous_width, const char *term_program,
            wcwidth_control_mode_t control_codes, bool strict, bool propagate_sgr,
            wcwidth_sgr_state_t *captured_style, bool *style_captured, strbuf_t *sb)
{
    wcwidth_sgr_state_t current_style;
    bool track_sgr;
    size_t idx;
    int col;

    track_sgr = propagate_sgr;
    current_style = WCWIDTH_SGR_STATE_DEFAULT;
    *style_captured = false;
    col = 0;
    idx = 0;

    while (idx < text_len) {
        unsigned char ch = (unsigned char) text[idx];

        /* Early exit: past visible region. */
        if (col >= (int) v_end && ch != '\r' && ch != '\x08' && ch != '\t' && ch != ESC) {
            if (*style_captured) {
                break;
            }
            if (!track_sgr) {
                const char *next = (const char *) memchr(text + idx + 1, ESC, text_len - idx - 1);
                if (next == NULL) {
                    break;
                }
                idx = (size_t) (next - text);
                continue;
            }
        }

        if (ch == ESC) {
            wcwidth_esc_result_t result;

            if (!wcwidth_escape_classify(text, text_len, idx, &result)) {
                strbuf_append_char(sb, ESC);
                idx++;
                continue;
            }

            /* SGR: update state, do not emit. */
            if (result.type == WCWIDTH_ESC_SGR && track_sgr) {
                wcwidth_sgr_update(&current_style, result.sgr_params, result.sgr_params_len);
                idx += result.length;
                continue;
            }

            /* OSC 8 hyperlink. */
            if (result.type == WCWIDTH_ESC_OSC8_OPEN) {
                wcwidth_hyperlink_params_t hl_params;
                if (wcwidth_hyperlink_parse_open(result.start, result.length, &hl_params)) {
                    char open_seq_buf[256], close_seq_buf[256];
                    size_t open_len, close_len, ce, clipped_len;
                    int action, inner_w, clipped_w, hl_end;
                    char *hl_buf = NULL;
                    size_t hl_buf_cap = 0;

                    action = process_hyperlink(
                        text, text_len, v_start, v_end, fillchar, tabsize, ambiguous_width,
                        term_program, control_codes, &hl_params, idx + result.length, col, &ce,
                        &inner_w, open_seq_buf, &open_len, &hl_buf, &hl_buf_cap, &clipped_len,
                        close_seq_buf, &close_len, &clipped_w, &hl_end);

                    if (action < 0) {
                        free(hl_buf);
                        return false;
                    }
                    if (action == 0) {
                        strbuf_append(sb, result.start, result.length);
                        idx += result.length;
                    }
                    else if (action == 1) {
                        idx = ce;
                    }
                    else if (action == 2) {
                        col += inner_w;
                        idx = ce;
                    }
                    else {
                        strbuf_append(sb, open_seq_buf, open_len);
                        strbuf_append(sb, hl_buf, clipped_len);
                        strbuf_append(sb, close_seq_buf, close_len);
                        if (track_sgr && !*style_captured) {
                            *captured_style = current_style;
                            *style_captured = true;
                        }
                        col += inner_w;
                        idx = ce;
                    }
                    free(hl_buf);
                }
                else {
                    strbuf_append(sb, result.start, result.length);
                    idx += result.length;
                }
                continue;
            }

            /* OSC 66 Text Sizing. */
            if (result.type == WCWIDTH_ESC_OSC66) {
                wcwidth_text_sizing_t ts;
                char meta_buf[64];
                int ts_width;

                ts.params.scale = 1;
                ts.params.width = 0;
                ts.params.numerator = 0;
                ts.params.denominator = 0;
                ts.params.vertical_align = 0;
                ts.params.horizontal_align = 0;
                ts.text = result.ts_text;
                ts.text_len = result.ts_text_len;
                ts.terminator = result.ts_terminator;

                if (result.ts_meta_len > 0 && result.ts_meta_len < sizeof(meta_buf)) {
                    memcpy(meta_buf, result.ts_meta, result.ts_meta_len);
                    meta_buf[result.ts_meta_len] = '\0';
                    wcwidth_ts_parse_params(meta_buf, result.ts_meta_len, &ts.params);
                }
                ts_width = wcwidth_ts_display_width(&ts, ambiguous_width);

                if (col >= (int) v_start && col + ts_width <= (int) v_end) {
                    strbuf_append(sb, result.start, result.length);
                    if (track_sgr && !*style_captured) {
                        *captured_style = current_style;
                        *style_captured = true;
                    }
                    col += ts_width;
                }
                else if (col < (int) v_end && col + ts_width > (int) v_start) {
                    int clip_start = (v_start > (size_t) col) ? (int) v_start : col;
                    int clip_end = ((int) v_end < col + ts_width) ? (int) v_end : col + ts_width;
                    int fill_count = clip_end - clip_start;
                    if (fill_count > 0) {
                        strbuf_append_repeat(sb, fillchar, (size_t) fill_count);
                    }
                    if (track_sgr && !*style_captured) {
                        *captured_style = current_style;
                        *style_captured = true;
                    }
                    col += ts_width;
                }
                else {
                    col += ts_width;
                }
                idx += result.length;
                continue;
            }

            /* Indeterminate sequences: error in strict mode. */
            if (strict && is_indeterminate_seq(&result)) {
                return false;
            }

            /* Any other recognized sequence: preserve as-is. */
            strbuf_append(sb, result.start, result.length);
            idx += result.length;
            continue;
        }

        /* Tab expansion. */
        if (ch == '\t') {
            if (tabsize > 0) {
                int next_tab = col + (tabsize - (col % tabsize));
                while (col < next_tab) {
                    if ((int) v_start <= col && col < (int) v_end) {
                        strbuf_append_char(sb, ' ');
                        if (track_sgr && !*style_captured) {
                            *captured_style = current_style;
                            *style_captured = true;
                        }
                    }
                    col++;
                }
            }
            else {
                strbuf_append_char(sb, '\t');
            }
            idx++;
            continue;
        }

        /* Carriage return / backspace. */
        if (ch == '\r' && control_codes != WCWIDTH_IGNORE) {
            col = 0;
            idx++;
            continue;
        }
        if (ch == '\x08' && control_codes != WCWIDTH_IGNORE) {
            if (col > 0)
                col--;
            idx++;
            continue;
        }

        /* Grapheme cluster. */
        {
            wcwidth_grapheme_iter_t *giter;
            const char *grapheme;
            size_t g_len;
            int g_w;

            giter = wcwidth_grapheme_iter_new(text + idx, text_len - idx);
            if (giter == NULL)
                return false;
            grapheme = wcwidth_grapheme_next(giter, &g_len);
            if (grapheme == NULL || g_len == 0) {
                wcwidth_grapheme_iter_free(giter);
                idx++;
                continue;
            }
            g_w = grapheme_width(grapheme, g_len, ambiguous_width, term_program);

            if (g_w == 0) {
                if ((int) v_start <= col && col < (int) v_end) {
                    strbuf_append(sb, grapheme, g_len);
                }
            }
            else if (col >= (int) v_start && col + g_w <= (int) v_end) {
                strbuf_append(sb, grapheme, g_len);
                if (track_sgr && !*style_captured) {
                    *captured_style = current_style;
                    *style_captured = true;
                }
            }
            else if (col < (int) v_end && col + g_w > (int) v_start) {
                int clip_start = (v_start > (size_t) col) ? (int) v_start : col;
                int clip_end = ((int) v_end < col + g_w) ? (int) v_end : col + g_w;
                int fill_count = clip_end - clip_start;
                if (fill_count > 0) {
                    strbuf_append_repeat(sb, fillchar, (size_t) fill_count);
                }
                if (track_sgr && !*style_captured) {
                    *captured_style = current_style;
                    *style_captured = true;
                }
            }

            col += g_w;
            idx += g_len;
            wcwidth_grapheme_iter_free(giter);
        }
    }

    return true;
}

typedef struct
{
    int col;
    const char *text;
    size_t text_len;
    int width;
    bool is_hyperlink;
    bool use_fillchar; /* if true, reconstruction uses fillchar instead of text */
} painter_cell_t;

typedef struct
{
    int col;
    int order;
    const char *text;
    size_t text_len;
} painter_seq_t;

typedef struct
{
    painter_cell_t *data;
    size_t count;
    size_t cap;
} painter_cells_t;

typedef struct
{
    painter_seq_t *data;
    size_t count;
    size_t cap;
} painter_seqs_t;

static void
painter_cells_init(painter_cells_t *pc)
{
    pc->data = NULL;
    pc->count = 0;
    pc->cap = 0;
}

static void
painter_cells_free(painter_cells_t *pc)
{
    free(pc->data);
    pc->data = NULL;
    pc->count = 0;
    pc->cap = 0;
}

static void
painter_seqs_init(painter_seqs_t *ps)
{
    ps->data = NULL;
    ps->count = 0;
    ps->cap = 0;
}

static void
painter_seqs_free(painter_seqs_t *ps)
{
    free(ps->data);
    ps->data = NULL;
    ps->count = 0;
    ps->cap = 0;
}

static bool
painter_write_cells(painter_cells_t *cells, const char *s, size_t s_len, int w, int write_col,
                    bool is_hyperlink, bool text_is_fillchar, char fillchar,
                    wcwidth_sgr_state_t *current_style, wcwidth_sgr_state_t *captured_style,
                    bool *style_captured, bool track_sgr)
{
    int offset;

    for (offset = 0; offset < w; offset++) {
        int src_col = write_col + offset;
        size_t j;

        if (src_col > 0) {
            for (j = 0; j < cells->count; j++) {
                if (cells->data[j].col == src_col - 1 && cells->data[j].width == 2) {
                    cells->data[j].text = &fillchar;
                    cells->data[j].text_len = 1;
                    cells->data[j].width = 1;
                    cells->data[j].is_hyperlink = false;
                    cells->data[j].use_fillchar = true;
                    break;
                }
            }
        }
        for (j = 0; j < cells->count; j++) {
            if (cells->data[j].col == src_col && cells->data[j].width == 2) {
                size_t k;
                bool found = false;
                for (k = 0; k < cells->count; k++) {
                    if (cells->data[k].col == src_col + 1) {
                        cells->data[k].text = &fillchar;
                        cells->data[k].text_len = 1;
                        cells->data[k].width = 1;
                        cells->data[k].is_hyperlink = false;
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    size_t nc = cells->cap ? cells->cap * 2 : 16;
                    painter_cell_t *nd =
                        (painter_cell_t *) realloc(cells->data, nc * sizeof(painter_cell_t));
                    if (nd == NULL)
                        return false;
                    cells->data = nd;
                    cells->cap = nc;
                    cells->data[cells->count].col = src_col + 1;
                    cells->data[cells->count].text = &fillchar;
                    cells->data[cells->count].text_len = 1;
                    cells->data[cells->count].width = 1;
                    cells->data[cells->count].is_hyperlink = false;
                    cells->data[cells->count].use_fillchar = true;
                    cells->count++;
                }
                break;
            }
        }
    }

    /* Remove existing cells in [write_col, write_col + w). */
    {
        size_t j = 0;
        while (j < cells->count) {
            if (cells->data[j].col >= write_col && cells->data[j].col < write_col + w) {
                cells->data[j] = cells->data[cells->count - 1];
                cells->count--;
            }
            else {
                j++;
            }
        }
    }

    /* Add new cell. */
    if (cells->cap < cells->count + 1) {
        size_t nc = cells->cap ? cells->cap * 2 : 16;
        painter_cell_t *nd = (painter_cell_t *) realloc(cells->data, nc * sizeof(painter_cell_t));
        if (nd == NULL)
            return false;
        cells->data = nd;
        cells->cap = nc;
    }
    cells->data[cells->count].col = write_col;
    cells->data[cells->count].text = s;
    cells->data[cells->count].text_len = s_len;
    cells->data[cells->count].width = w;
    cells->data[cells->count].is_hyperlink = is_hyperlink;
    cells->data[cells->count].use_fillchar = text_is_fillchar;
    cells->count++;

    if (track_sgr && !*style_captured) {
        *captured_style = *current_style;
        *style_captured = true;
    }
    return true;
}

static bool
painter_add_seq(painter_seqs_t *seqs, int *seq_order, int col, const char *text, size_t text_len)
{
    if (seqs->cap < seqs->count + 1) {
        size_t nc = seqs->cap ? seqs->cap * 2 : 16;
        painter_seq_t *nd = (painter_seq_t *) realloc(seqs->data, nc * sizeof(painter_seq_t));
        if (nd == NULL)
            return false;
        seqs->data = nd;
        seqs->cap = nc;
    }
    seqs->data[seqs->count].col = col;
    seqs->data[seqs->count].order = (*seq_order)++;
    seqs->data[seqs->count].text = text;
    seqs->data[seqs->count].text_len = text_len;
    seqs->count++;
    return true;
}

static int
max_cell_col(const painter_cells_t *cells)
{
    size_t i;
    int mc = -1;
    for (i = 0; i < cells->count; i++) {
        if (cells->data[i].col > mc)
            mc = cells->data[i].col;
    }
    return mc;
}

static int
max_seq_col(const painter_seqs_t *seqs)
{
    size_t i;
    int ms = -1;
    for (i = 0; i < seqs->count; i++) {
        if (seqs->data[i].col > ms)
            ms = seqs->data[i].col;
    }
    return ms;
}

static size_t
find_cell_at(const painter_cells_t *cells, int col)
{
    size_t i;
    for (i = 0; i < cells->count; i++) {
        if (cells->data[i].col == col)
            return i;
    }
    return (size_t) -1;
}

static size_t
find_seqs_at(const painter_seqs_t *seqs, int col, size_t *indices, size_t idx_cap)
{
    size_t i, cnt = 0;
    for (i = 0; i < seqs->count && cnt < idx_cap; i++) {
        if (seqs->data[i].col == col)
            indices[cnt++] = i;
    }
    return cnt;
}

static void
reconstruct_painter(const painter_cells_t *cells, const painter_seqs_t *seqs, int v_start,
                    int v_end, char fillchar, strbuf_t *sb)
{
    int max_c = max_cell_col(cells);
    int max_s = max_seq_col(seqs);
    int max_col = (max_c > max_s) ? max_c : max_s;
    int col_limit = (max_col < v_end) ? max_col : v_end;
    int walk_col = 0;
    size_t sib[32];
    size_t sc, ki;

    while (walk_col <= col_limit) {
        sc = find_seqs_at(seqs, walk_col, sib, 32);
        /* Insertion sort by order. */
        for (ki = 1; ki < sc; ki++) {
            size_t key = sib[ki];
            size_t j = ki;
            while (j > 0 && seqs->data[sib[j - 1]].order > seqs->data[key].order) {
                sib[j] = sib[j - 1];
                j--;
            }
            sib[j] = key;
        }
        for (ki = 0; ki < sc; ki++) {
            strbuf_append(sb, seqs->data[sib[ki]].text, seqs->data[sib[ki]].text_len);
        }

        if (walk_col >= v_end) {
            walk_col++;
            continue;
        }

        {
            size_t ci = find_cell_at(cells, walk_col);
            if (ci != (size_t) -1) {
                if (cells->data[ci].use_fillchar) {
                    strbuf_append_char(sb, fillchar);
                }
                else {
                    strbuf_append(sb, cells->data[ci].text, cells->data[ci].text_len);
                }
                walk_col += cells->data[ci].width;
            }
            else {
                if (v_start <= walk_col && walk_col <= max_c) {
                    strbuf_append_char(sb, fillchar);
                }
                walk_col++;
            }
        }
    }

    /* Emit sequences beyond col_limit, sorted by (col, order). */
    if (seqs->count > 0) {
        size_t *all = (size_t *) malloc(seqs->count * sizeof(size_t));
        if (all == NULL)
            return;
        {
            size_t i;
            for (i = 0; i < seqs->count; i++)
                all[i] = i;
        }
        {
            size_t a, b;
            for (a = 0; a < seqs->count; a++) {
                for (b = a + 1; b < seqs->count; b++) {
                    const painter_seq_t *sa = &seqs->data[all[a]];
                    const painter_seq_t *sb2 = &seqs->data[all[b]];
                    if (sb2->col < sa->col || (sb2->col == sa->col && sb2->order < sa->order)) {
                        size_t tmp = all[a];
                        all[a] = all[b];
                        all[b] = tmp;
                    }
                }
            }
        }
        {
            size_t i;
            for (i = 0; i < seqs->count; i++) {
                const painter_seq_t *ps = &seqs->data[all[i]];
                if (ps->col > col_limit) {
                    strbuf_append(sb, ps->text, ps->text_len);
                }
            }
        }
        free(all);
    }
}

static bool
clip_painter(const char *text, size_t text_len, size_t v_start, size_t v_end, char fillchar,
             int tabsize, int ambiguous_width, const char *term_program,
             wcwidth_control_mode_t control_codes, bool strict, bool propagate_sgr,
             wcwidth_sgr_state_t *captured_style, bool *style_captured, strbuf_t *sb)
{
    painter_cells_t cells;
    painter_seqs_t seqs;
    int seq_order = 0;
    wcwidth_sgr_state_t current_style;
    bool track_sgr;
    int col;
    size_t idx;

    painter_cells_init(&cells);
    painter_seqs_init(&seqs);

    track_sgr = propagate_sgr;
    current_style = WCWIDTH_SGR_STATE_DEFAULT;
    *style_captured = false;
    col = 0;
    idx = 0;

    while (idx < text_len) {
        unsigned char ch = (unsigned char) text[idx];

        if (col >= (int) v_end && *style_captured && ch != ESC)
            break;

        if (ch == ESC) {
            wcwidth_esc_result_t result;

            if (!wcwidth_escape_classify(text, text_len, idx, &result)) {
                if (!painter_add_seq(&seqs, &seq_order, col, text + idx, 1))
                    goto alloc_fail;
                if (track_sgr && !*style_captured) {
                    *captured_style = current_style;
                    *style_captured = true;
                }
                idx++;
                continue;
            }

            if (result.type == WCWIDTH_ESC_SGR && track_sgr) {
                wcwidth_sgr_update(&current_style, result.sgr_params, result.sgr_params_len);
                idx += result.length;
                continue;
            }

            if (result.type == WCWIDTH_ESC_OSC8_OPEN) {
                wcwidth_hyperlink_params_t hl_params;
                if (wcwidth_hyperlink_parse_open(result.start, result.length, &hl_params)) {
                    char open_seq_buf[256], close_seq_buf[256];
                    size_t open_len, close_len, ce, clipped_len;
                    int action, inner_w, clipped_w, hl_end;
                    char *hl_buf = NULL;
                    size_t hl_buf_cap = 0;

                    action = process_hyperlink(
                        text, text_len, v_start, v_end, fillchar, tabsize, ambiguous_width,
                        term_program, control_codes, &hl_params, idx + result.length, col, &ce,
                        &inner_w, open_seq_buf, &open_len, &hl_buf, &hl_buf_cap, &clipped_len,
                        close_seq_buf, &close_len, &clipped_w, &hl_end);

                    if (action < 0) {
                        free(hl_buf);
                        goto alloc_fail;
                    }
                    if (action == 0) {
                        if (!painter_add_seq(&seqs, &seq_order, col, result.start, result.length)) {
                            free(hl_buf);
                            goto alloc_fail;
                        }
                        if (track_sgr && !*style_captured) {
                            *captured_style = current_style;
                            *style_captured = true;
                        }
                        idx += result.length;
                    }
                    else if (action == 1) {
                        idx = ce;
                    }
                    else if (action == 2) {
                        col += inner_w;
                        idx = ce;
                    }
                    else {
                        if (!painter_add_seq(&seqs, &seq_order, col, open_seq_buf, open_len)) {
                            free(hl_buf);
                            goto alloc_fail;
                        }
                        if (track_sgr && !*style_captured) {
                            *captured_style = current_style;
                            *style_captured = true;
                        }
                        if (!painter_write_cells(&cells, hl_buf, clipped_len, clipped_w, col, true,
                                                 false, fillchar, &current_style, captured_style,
                                                 style_captured, track_sgr)) {
                            free(hl_buf);
                            goto alloc_fail;
                        }
                        col += clipped_w;
                        if (!painter_add_seq(&seqs, &seq_order, col, close_seq_buf, close_len)) {
                            free(hl_buf);
                            goto alloc_fail;
                        }
                        col = hl_end;
                        idx = ce;
                    }
                    free(hl_buf);
                }
                else {
                    if (!painter_add_seq(&seqs, &seq_order, col, result.start, result.length))
                        goto alloc_fail;
                    if (track_sgr && !*style_captured) {
                        *captured_style = current_style;
                        *style_captured = true;
                    }
                    idx += result.length;
                }
                continue;
            }

            if (result.type == WCWIDTH_ESC_OSC66) {
                wcwidth_text_sizing_t ts;
                char meta_buf[64];
                int ts_width;

                ts.params.scale = 1;
                ts.params.width = 0;
                ts.params.numerator = 0;
                ts.params.denominator = 0;
                ts.params.vertical_align = 0;
                ts.params.horizontal_align = 0;
                ts.text = result.ts_text;
                ts.text_len = result.ts_text_len;
                ts.terminator = result.ts_terminator;

                if (result.ts_meta_len > 0 && result.ts_meta_len < sizeof(meta_buf)) {
                    memcpy(meta_buf, result.ts_meta, result.ts_meta_len);
                    meta_buf[result.ts_meta_len] = '\0';
                    wcwidth_ts_parse_params(meta_buf, result.ts_meta_len, &ts.params);
                }
                ts_width = wcwidth_ts_display_width(&ts, ambiguous_width);

                if (col >= (int) v_start && col + ts_width <= (int) v_end) {
                    if (!painter_write_cells(&cells, result.start, result.length, ts_width, col,
                                             false, false, fillchar, &current_style, captured_style,
                                             style_captured, track_sgr))
                        goto alloc_fail;
                    col += ts_width;
                }
                else if (col < (int) v_end && col + ts_width > (int) v_start) {
                    int c_start = ((int) v_start > col) ? (int) v_start : col;
                    int c_end = ((int) v_end < col + ts_width) ? (int) v_end : col + ts_width;
                    int off;
                    for (off = c_start; off < c_end; off++) {
                        if (!painter_write_cells(&cells, &fillchar, 1, 1, off, false, true,
                                                 fillchar, &current_style, captured_style,
                                                 style_captured, track_sgr))
                            goto alloc_fail;
                    }
                    col += ts_width;
                }
                else {
                    col += ts_width;
                }
                idx += result.length;
                continue;
            }

            if (strict && is_indeterminate_seq(&result))
                goto fail_return;

            if (result.type == WCWIDTH_ESC_HPA) {
                col = result.cursor_n - 1;
                idx += result.length;
                continue;
            }

            if (result.type == WCWIDTH_ESC_CUF) {
                int n_forward = result.cursor_n;
                int move_end = col + n_forward;
                if (col < (int) v_end && move_end > (int) v_start) {
                    int x;
                    for (x = (col > (int) v_start ? col : (int) v_start);
                         x < (move_end < (int) v_end ? move_end : (int) v_end); x++) {
                        if (!painter_write_cells(&cells, &fillchar, 1, 1, x, false, true, fillchar,
                                                 &current_style, captured_style, style_captured,
                                                 track_sgr))
                            goto alloc_fail;
                    }
                }
                col = move_end;
                idx += result.length;
                continue;
            }

            if (result.type == WCWIDTH_ESC_CUB) {
                int n_backward = result.cursor_n;
                if (strict && n_backward > col)
                    goto fail_return;
                col -= n_backward;
                if (col < 0)
                    col = 0;
                idx += result.length;
                continue;
            }

            /* Any other sequence. */
            if (!painter_add_seq(&seqs, &seq_order, col, result.start, result.length))
                goto alloc_fail;
            if (track_sgr && !*style_captured) {
                *captured_style = current_style;
                *style_captured = true;
            }
            idx += result.length;
            continue;
        }

        if (ch == '\r') {
            col = 0;
            idx++;
            continue;
        }
        if (ch == '\x08') {
            if (col > 0)
                col--;
            idx++;
            continue;
        }

        if (ch == '\t') {
            if (tabsize > 0) {
                int next_tab = col + (tabsize - (col % tabsize));
                while (col < next_tab) {
                    if ((int) v_start <= col && col < (int) v_end) {
                        if (!painter_write_cells(&cells, &fillchar, 1, 1, col, false, true,
                                                 fillchar, &current_style, captured_style,
                                                 style_captured, track_sgr))
                            goto alloc_fail;
                    }
                    col++;
                }
            }
            else {
                if (!painter_add_seq(&seqs, &seq_order, col, "\t", 1))
                    goto alloc_fail;
                if (track_sgr && !*style_captured) {
                    *captured_style = current_style;
                    *style_captured = true;
                }
            }
            idx++;
            continue;
        }

        /* Grapheme cluster. */
        {
            wcwidth_grapheme_iter_t *giter;
            const char *grapheme;
            size_t g_len;
            int g_w;

            giter = wcwidth_grapheme_iter_new(text + idx, text_len - idx);
            if (giter == NULL)
                goto alloc_fail;
            grapheme = wcwidth_grapheme_next(giter, &g_len);
            if (grapheme == NULL || g_len == 0) {
                wcwidth_grapheme_iter_free(giter);
                idx++;
                continue;
            }
            g_w = grapheme_width(grapheme, g_len, ambiguous_width, term_program);

            if (g_w == 0) {
                if ((int) v_start <= col && col < (int) v_end) {
                    if (!painter_add_seq(&seqs, &seq_order, col, grapheme, g_len)) {
                        wcwidth_grapheme_iter_free(giter);
                        goto alloc_fail;
                    }
                    if (track_sgr && !*style_captured) {
                        *captured_style = current_style;
                        *style_captured = true;
                    }
                }
            }
            else if (col >= (int) v_start && col + g_w <= (int) v_end) {
                if (!painter_write_cells(&cells, grapheme, g_len, g_w, col, false, false, fillchar,
                                         &current_style, captured_style, style_captured,
                                         track_sgr)) {
                    wcwidth_grapheme_iter_free(giter);
                    goto alloc_fail;
                }
            }
            else if (col < (int) v_end && col + g_w > (int) v_start) {
                int c_start = ((int) v_start > col) ? (int) v_start : col;
                int c_end = ((int) v_end < col + g_w) ? (int) v_end : col + g_w;
                int off;
                for (off = c_start; off < c_end; off++) {
                    if (!painter_write_cells(&cells, &fillchar, 1, 1, off, false, true, fillchar,
                                             &current_style, captured_style, style_captured,
                                             track_sgr)) {
                        wcwidth_grapheme_iter_free(giter);
                        goto alloc_fail;
                    }
                }
            }

            col += g_w;
            idx += g_len;
            wcwidth_grapheme_iter_free(giter);
        }
    }

    reconstruct_painter(&cells, &seqs, (int) v_start, (int) v_end, fillchar, sb);

    painter_cells_free(&cells);
    painter_seqs_free(&seqs);
    return true;

alloc_fail:
fail_return:
    painter_cells_free(&cells);
    painter_seqs_free(&seqs);
    return false;
}

static void
apply_sgr_wrap(strbuf_t *sb, const wcwidth_sgr_state_t *style, bool active)
{
    char prefix[64];
    size_t prefix_len;

    if (!active)
        return;

    prefix_len = wcwidth_sgr_to_escape(style, prefix, sizeof(prefix));

    if (prefix_len > 0) {
        char *old_buf = sb->buf;
        size_t old_len = sb->len;
        size_t new_cap = old_len + prefix_len + 5;
        char *new_buf = (char *) malloc(new_cap);

        if (new_buf == NULL)
            return;

        memcpy(new_buf, prefix, prefix_len);
        if (old_buf != NULL && old_len > 0) {
            memcpy(new_buf + prefix_len, old_buf, old_len);
        }
        new_buf[prefix_len + old_len] = '\0';

        free(old_buf);
        sb->buf = new_buf;
        sb->len = prefix_len + old_len;
        sb->cap = new_cap;
    }

    if (wcwidth_sgr_is_active(style)) {
        strbuf_append(sb, "\x1b[0m", 4);
    }
}

char *
clip_u8(const char *text, size_t text_len, size_t v_start, size_t v_end,
        wcwidth_control_mode_t control_codes, int tabsize, int ambiguous_width,
        const char *term_program, bool propagate_sgr, char fillchar, size_t *out_len)
{
    strbuf_t sb;
    wcwidth_sgr_state_t captured_style;
    bool style_captured;
    bool strict;
    bool overtyping;
    bool has_esc;

    if (out_len != NULL)
        *out_len = 0;

    /* Boundary: empty range. */
    if (v_end <= v_start) {
        char *empty = (char *) malloc(1);
        if (empty != NULL)
            empty[0] = '\0';
        return empty;
    }

    /* Fast path: pure printable ASCII. */
    {
        size_t i;
        bool all_ascii = true;
        size_t scan_len = text_len;
        for (i = 0; i < scan_len; i++) {
            unsigned char ub = (unsigned char) text[i];
            if (ub < 0x20 || ub >= 0x7f) {
                all_ascii = false;
                break;
            }
        }
        if (all_ascii) {
            size_t result_len;
            char *result;

            if (v_start >= text_len) {
                result = (char *) malloc(1);
                if (result != NULL)
                    result[0] = '\0';
                return result;
            }
            result_len =
                (text_len - v_start < v_end - v_start) ? (text_len - v_start) : (v_end - v_start);
            result = (char *) malloc(result_len + 1);
            if (result == NULL)
                return NULL;
            memcpy(result, text + v_start, result_len);
            result[result_len] = '\0';
            if (out_len != NULL)
                *out_len = result_len;
            return result;
        }
    }

    has_esc = (memchr(text, ESC, text_len) != NULL);

    if (propagate_sgr && !has_esc) {
        propagate_sgr = false;
    }

    strict = (control_codes == WCWIDTH_STRICT);

    /* Determine whether painter's algorithm is needed. */
    overtyping = false;
    if (control_codes != WCWIDTH_IGNORE) {
        if (memchr(text, '\x08', text_len) != NULL || memchr(text, '\r', text_len) != NULL) {
            overtyping = true;
        }
        else if (has_esc) {
            overtyping = wcwidth_escape_has_cursor_movement(text, text_len);
        }
    }

    strbuf_init(&sb, 256);
    if (sb.buf == NULL)
        return NULL;

    captured_style = WCWIDTH_SGR_STATE_DEFAULT;
    style_captured = false;

    if (overtyping) {
        if (!clip_painter(text, text_len, v_start, v_end, fillchar, tabsize, ambiguous_width,
                          term_program, control_codes, strict, propagate_sgr, &captured_style,
                          &style_captured, &sb)) {
            strbuf_free(&sb);
            return NULL;
        }
    }
    else {
        if (!clip_simple(text, text_len, v_start, v_end, fillchar, tabsize, ambiguous_width,
                         term_program, control_codes, strict, propagate_sgr, &captured_style,
                         &style_captured, &sb)) {
            strbuf_free(&sb);
            return NULL;
        }
    }

    if (propagate_sgr && style_captured) {
        apply_sgr_wrap(&sb, &captured_style, wcwidth_sgr_is_active(&captured_style));
    }

    return strbuf_detach(&sb, out_len);
}
