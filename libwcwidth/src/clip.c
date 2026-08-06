/*
 * Text truncation with sequence awareness.
 */
#include "wcwidth/clip.h"
#include "wcwidth/escape.h"
#include "wcwidth/grapheme.h"
#include "wcwidth/hyperlink.h"
#include "wcwidth/sgr.h"
#include "wcwidth/text_sizing.h"
#include "wcwidth/wcwidth.h"
#include "wcwidth/utf8.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
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
    int w;

    if (term_program != NULL && term_program[0] != '\0') {
        w = wcstwidth_u8(g, g_len, ambiguous_width, term_program);
    }
    else {
        w = wcswidth_u8(g, g_len, ambiguous_width);
    }
    /* control characters measure -1 via wcswidth, but the pure clip measures
     * them as zero-width (via width()); clamp to match */
    return (w < 0) ? 0 : w;
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
process_hyperlink(const char *text, size_t text_len, size_t v_start, size_t v_end,
                  const char *fillchar, size_t fillchar_len, int tabsize, int ambiguous_width,
                  const char *term_program, wcwidth_control_mode_t control_codes,
                  const wcwidth_hyperlink_params_t *params, size_t match_end, int col,
                  size_t *close_end, int *inner_width, char *open_seq_buf, size_t *open_seq_len,
                  char **clipped_buf, size_t *clipped_buf_cap, size_t *clipped_inner_len,
                  char *close_seq_buf, size_t *close_seq_len, int *clipped_width, int *hl_col_end)
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
        wcwidth_width_opts_t opts = {
            .tabsize = tabsize, .ambiguous_width = ambiguous_width, .term_program = term_program};
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
            int dummy_error = WCWIDTH_ERROR_NONE;
            char *clipped = clip_u8(inner_text, inner_len, inner_clip_start, inner_clip_end_val,
                                    control_codes, tabsize, ambiguous_width, term_program, false,
                                    -1, fillchar, fillchar_len, &dummy_len, &dummy_error);
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
            wcwidth_width_opts_t opts = {.tabsize = tabsize,
                                         .ambiguous_width = ambiguous_width,
                                         .term_program = term_program};
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

/*
 * Emit callback for clipped text-sizing output.  *ctx distinguishes the
 * simple (strbuf) and painter (cell) output paths.
 */
typedef bool (*ts_emit_fn)(void *ctx, const char *s, size_t s_len, int w, int col, bool is_fill);

/*
 * Serialize non-default text-sizing params as 'key=value' joined by ':',
 * as ts_make_sequence does.  Returns bytes written (excluding NUL); the NUL
 * is written when it fits.
 */
static size_t
ts_params_to_str(const wcwidth_ts_params_t *params, char *out, size_t out_cap)
{
    static const char keys[] = {'s', 'w', 'n', 'd', 'v', 'h'};
    static const int defaults[] = {1, 0, 0, 0, 0, 0};
    const int vals[] = {params->scale,       params->width,          params->numerator,
                        params->denominator, params->vertical_align, params->horizontal_align};
    size_t written = 0;
    size_t i;

    for (i = 0; i < sizeof(keys); i++) {
        char num[16];
        int num_len;
        size_t k;

        if (vals[i] == defaults[i])
            continue;
        if (written > 0 && written < out_cap)
            out[written++] = ':';
        if (written < out_cap)
            out[written++] = keys[i];
        if (written < out_cap)
            out[written++] = '=';
        num_len = snprintf(num, sizeof(num), "%d", vals[i]);
        for (k = 0; k < (size_t) num_len && written < out_cap; k++)
            out[written++] = num[k];
    }
    if (written < out_cap)
        out[written] = '\0';
    return written;
}

/* Build an OSC 66 sequence: ESC ] 66 ; params ; text terminator.
 * The terminator is stored as its last byte: BEL (1 byte) or '\\' of the
 * two-byte ST terminator ESC \. */
static size_t
ts_make_sequence(const wcwidth_ts_params_t *params, const char *text, size_t text_len,
                 char terminator, char *out, size_t out_cap)
{
    static const char prefix[] = "\x1b]66;";
    char params_buf[64];
    size_t params_len = ts_params_to_str(params, params_buf, sizeof(params_buf));
    size_t term_len = (terminator == '\\') ? 2 : 1;
    size_t total = sizeof(prefix) - 1 + params_len + 1 + text_len + term_len;

    if (total <= out_cap) {
        memcpy(out, prefix, sizeof(prefix) - 1);
        memcpy(out + sizeof(prefix) - 1, params_buf, params_len);
        out[sizeof(prefix) - 1 + params_len] = ';';
        memcpy(out + sizeof(prefix) - 1 + params_len + 1, text, text_len);
        if (terminator == '\\') {
            out[total - 2] = ESC;
            out[total - 1] = '\\';
        }
        else {
            out[total - 1] = terminator;
        }
        out[total] = '\0';
    }
    return total;
}

/* Emit a rebuilt OSC 66 sequence via *emit*, heap-allocating when needed. */
static void
ts_emit_seq(ts_emit_fn emit, void *ctx, const wcwidth_ts_params_t *params, const char *text,
            size_t text_len, char terminator, int w, int col)
{
    char stack[256];
    char *seq = stack;
    size_t cap = sizeof(stack);
    size_t seq_len = ts_make_sequence(params, text, text_len, terminator, stack, cap);

    if (seq_len > cap) {
        seq = (char *) malloc(seq_len + 1);
        if (seq == NULL)
            return; /* best effort: skip on allocation failure */
        ts_make_sequence(params, text, text_len, terminator, seq, seq_len + 1);
    }
    emit(ctx, seq, seq_len, w, col, false);
    if (seq != stack)
        free(seq);
}

/* One grapheme unit of a text-sizing display: bytes, display width. */
typedef struct
{
    const char *text;
    size_t text_len;
    int width;
} ts_unit_t;

/* Emitter for the simple output path: appends directly to the output buffer. */
typedef struct
{
    strbuf_t *sb;
    const char *fillchar;
    size_t fillchar_len;
} ts_simple_ctx_t;

static bool
ts_emit_simple(void *vctx, const char *s, size_t s_len, int w, int col, bool is_fill)
{
    ts_simple_ctx_t *ctx = (ts_simple_ctx_t *) vctx;

    (void) w;
    (void) col;
    if (is_fill) {
        strbuf_append(ctx->sb, ctx->fillchar, ctx->fillchar_len);
    }
    else {
        strbuf_append(ctx->sb, s, s_len);
    }
    return true;
}

/*
 * Emit a text-sizing (OSC 66) sequence clipped to (v_start, v_end).
 * Fully-visible grapheme units are re-emitted as a rebuilt OSC 66 sequence
 * (with a recalculated w parameter); partially visible units are replaced
 * with fillchar.  Returns the new column.
 */
static int
clip_text_sizing(const wcwidth_text_sizing_t *ts, int col, int v_start, int v_end,
                 int ambiguous_width, const char *term_program, ts_emit_fn emit, void *ctx)
{
    int ts_width;
    int rel_start;
    int rel_end;
    int unit_pos;
    int flush_col_pos;
    ts_unit_t *units = NULL;
    size_t n_units = 0;
    size_t units_cap = 0;
    wcwidth_grapheme_iter_t *iter;
    const char *g;
    size_t g_len;
    int want;
    int scale;
    strbuf_t pending;
    int pending_w = 0;
    int pending_count = 0;
    size_t ui;

    ts_width = wcwidth_ts_display_width(ts, ambiguous_width);

    /* Fully visible: emit the whole sequence. */
    if (col >= v_start && col + ts_width <= v_end) {
        ts_emit_seq(emit, ctx, &ts->params, ts->text, ts->text_len, ts->terminator, ts_width, col);
        return col + ts_width;
    }
    /* Fully outside: just advance the column. */
    if (col >= v_end || col + ts_width <= v_start)
        return col + ts_width;

    /* Partial overlap: decompose into grapheme units. */
    rel_start = (v_start > col) ? (v_start - col) : 0;
    rel_end = (v_end < col + ts_width) ? (v_end - col) : ts_width;
    scale = ts->params.scale;
    want = ts->params.width;

    iter = wcwidth_grapheme_iter_new(ts->text, ts->text_len);
    if (iter == NULL)
        return col + ts_width;

    while (want == 0 || n_units < (size_t) want) {
        size_t new_cap;
        ts_unit_t *nd;

        g = wcwidth_grapheme_next(iter, &g_len);
        if (g == NULL || g_len == 0)
            break;
        if (n_units >= units_cap) {
            new_cap = units_cap ? units_cap * 2 : 8;
            nd = (ts_unit_t *) realloc(units, new_cap * sizeof(ts_unit_t));
            if (nd == NULL)
                break;
            units = nd;
            units_cap = new_cap;
        }
        units[n_units].text = g;
        units[n_units].text_len = g_len;
        if (want > 0) {
            units[n_units].width = scale;
        }
        else {
            units[n_units].width = grapheme_width(g, g_len, ambiguous_width, term_program) * scale;
        }
        n_units++;
    }
    wcwidth_grapheme_iter_free(iter);

    /* Pad to the declared width with empty units. */
    if (want > 0) {
        while (n_units < (size_t) want) {
            size_t new_cap = units_cap ? units_cap * 2 : 8;
            ts_unit_t *nd = (ts_unit_t *) realloc(units, new_cap * sizeof(ts_unit_t));
            if (nd == NULL)
                break;
            units = nd;
            units_cap = new_cap;
            units[n_units].text = "";
            units[n_units].text_len = 0;
            units[n_units].width = scale;
            n_units++;
        }
    }

    strbuf_init(&pending, 64);
    unit_pos = 0;
    flush_col_pos = col;

    for (ui = 0; ui < n_units; ui++) {
        int unit_w = units[ui].width;
        int unit_end = unit_pos + unit_w;
        int overlap;

        if (unit_w == 0) {
            unit_pos = unit_end;
            continue;
        }
        if (unit_end <= rel_start) {
            unit_pos = unit_end;
            continue;
        }
        if (unit_pos >= rel_end)
            break;

        overlap = (unit_end < rel_end ? unit_end : rel_end)
                  - (unit_pos > rel_start ? unit_pos : rel_start);
        if (overlap == unit_w && unit_w > 0) {
            if (pending_count == 0)
                flush_col_pos = col + (unit_pos > rel_start ? unit_pos : rel_start);
            strbuf_append(&pending, units[ui].text, units[ui].text_len);
            pending_w += unit_w;
            pending_count++;
        }
        else {
            int i;

            if (pending_count > 0) {
                wcwidth_ts_params_t new_params;

                new_params.scale = scale;
                new_params.width = (want > 0) ? pending_count : 0;
                new_params.numerator = ts->params.numerator;
                new_params.denominator = ts->params.denominator;
                new_params.vertical_align = ts->params.vertical_align;
                new_params.horizontal_align = ts->params.horizontal_align;
                ts_emit_seq(emit, ctx, &new_params, pending.buf, pending.len, ts->terminator,
                            pending_w, flush_col_pos);
                pending.len = 0;
                pending_w = 0;
                pending_count = 0;
            }
            for (i = 0; i < overlap; i++) {
                emit(ctx, NULL, 0, 1, col + (unit_pos > rel_start ? unit_pos : rel_start) + i,
                     true);
            }
        }
        unit_pos = unit_end;
    }

    /* Final flush of pending units. */
    if (pending_count > 0) {
        wcwidth_ts_params_t new_params;

        new_params.scale = scale;
        new_params.width = (want > 0) ? pending_count : 0;
        new_params.numerator = ts->params.numerator;
        new_params.denominator = ts->params.denominator;
        new_params.vertical_align = ts->params.vertical_align;
        new_params.horizontal_align = ts->params.horizontal_align;
        ts_emit_seq(emit, ctx, &new_params, pending.buf, pending.len, ts->terminator, pending_w,
                    flush_col_pos);
    }

    strbuf_free(&pending);
    free(units);
    return col + ts_width;
}

/* Record the SGR state active at the first visible cell. */
static void
capture_style(bool track_sgr, wcwidth_sgr_state_t current_style,
              wcwidth_sgr_state_t *captured_style, bool *style_captured)
{
    if (track_sgr && !*style_captured) {
        *captured_style = current_style;
        *style_captured = true;
    }
}

typedef struct
{
    int col;
    const char *text;
    size_t text_len;
    int width;
    bool is_hyperlink;
    bool use_fillchar; /* if true, reconstruction uses fillchar instead of text */
    bool owned;        /* text points to a malloc'd copy owned by this cell */
} painter_cell_t;

typedef struct
{
    int col;
    int order;
    const char *text;
    size_t text_len;
    bool owned; /* text points to a malloc'd copy owned by this seq */
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
    size_t i;

    for (i = 0; i < pc->count; i++) {
        if (pc->data[i].owned)
            free((void *) pc->data[i].text);
    }
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
    size_t i;

    for (i = 0; i < ps->count; i++) {
        if (ps->data[i].owned)
            free((void *) ps->data[i].text);
    }
    free(ps->data);
    ps->data = NULL;
    ps->count = 0;
    ps->cap = 0;
}

static bool
painter_write_cells(painter_cells_t *cells, const char *s, size_t s_len, int w, int write_col,
                    bool is_hyperlink, const char *fillchar, size_t fillchar_len,
                    wcwidth_sgr_state_t *current_style, wcwidth_sgr_state_t *captured_style,
                    bool *style_captured, bool track_sgr)
{
    int offset;

    /* s == NULL marks a fill cell: its content is *fillchar. */
    bool text_is_fillchar = (s == NULL);
    if (text_is_fillchar) {
        s = fillchar;
        s_len = fillchar_len;
    }

    for (offset = 0; offset < w; offset++) {
        int src_col = write_col + offset;
        size_t j;

        if (src_col > 0) {
            for (j = 0; j < cells->count; j++) {
                if (cells->data[j].col == src_col - 1 && cells->data[j].width == 2) {
                    if (cells->data[j].owned) {
                        free((void *) cells->data[j].text);
                        cells->data[j].owned = false;
                    }
                    cells->data[j].text = fillchar;
                    cells->data[j].text_len = fillchar_len;
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
                        if (cells->data[k].owned) {
                            free((void *) cells->data[k].text);
                            cells->data[k].owned = false;
                        }
                        cells->data[k].text = fillchar;
                        cells->data[k].text_len = fillchar_len;
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
                    cells->data[cells->count].text = fillchar;
                    cells->data[cells->count].text_len = fillchar_len;
                    cells->data[cells->count].width = 1;
                    cells->data[cells->count].is_hyperlink = false;
                    cells->data[cells->count].use_fillchar = true;
                    cells->data[cells->count].owned = false;
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
                if (cells->data[j].owned) {
                    free((void *) cells->data[j].text);
                }
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
    cells->data[cells->count].width = w;
    cells->data[cells->count].is_hyperlink = is_hyperlink;
    cells->data[cells->count].use_fillchar = text_is_fillchar;
    if (text_is_fillchar) {
        /* fill cells carry a borrowed fillchar pointer; reconstruction uses
         * the fillchar parameter, not this text */
        cells->data[cells->count].text = fillchar;
        cells->data[cells->count].text_len = fillchar_len;
        cells->data[cells->count].owned = false;
    }
    else {
        /* copy: the source text may be a stack buffer or freed heap */
        char *copy = (char *) malloc(s_len + 1);
        if (copy == NULL)
            return false;
        memcpy(copy, s, s_len);
        copy[s_len] = '\0';
        cells->data[cells->count].text = copy;
        cells->data[cells->count].text_len = s_len;
        cells->data[cells->count].owned = true;
    }
    cells->count++;

    capture_style(track_sgr, *current_style, captured_style, style_captured);
    return true;
}

/* Emitter for the painter output path: writes into the cell model. */
typedef struct
{
    painter_cells_t *cells;
    const char *fillchar;
    size_t fillchar_len;
    wcwidth_sgr_state_t *current_style;
    wcwidth_sgr_state_t *captured_style;
    bool *style_captured;
    bool track_sgr;
} ts_painter_ctx_t;

static bool
ts_emit_painter(void *vctx, const char *s, size_t s_len, int w, int col, bool is_fill)
{
    ts_painter_ctx_t *ctx = (ts_painter_ctx_t *) vctx;

    if (is_fill) {
        return painter_write_cells(ctx->cells, NULL, 0, 1, col, false, ctx->fillchar,
                                   ctx->fillchar_len, ctx->current_style, ctx->captured_style,
                                   ctx->style_captured, ctx->track_sgr);
    }
    return painter_write_cells(ctx->cells, s, s_len, w, col, false, ctx->fillchar,
                               ctx->fillchar_len, ctx->current_style, ctx->captured_style,
                               ctx->style_captured, ctx->track_sgr);
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
    /* copy: the source text may be a stack buffer or freed heap */
    {
        char *copy = (char *) malloc(text_len + 1);
        if (copy == NULL)
            return false;
        memcpy(copy, text, text_len);
        copy[text_len] = '\0';
        seqs->data[seqs->count].text = copy;
        seqs->data[seqs->count].owned = true;
    }
    seqs->data[seqs->count].col = col;
    seqs->data[seqs->count].order = (*seq_order)++;
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
                    int v_end, const char *fillchar, size_t fillchar_len, strbuf_t *sb)
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
                    strbuf_append(sb, fillchar, fillchar_len);
                }
                else {
                    strbuf_append(sb, cells->data[ci].text, cells->data[ci].text_len);
                }
                walk_col += cells->data[ci].width;
            }
            else {
                if (v_start <= walk_col && walk_col <= max_c) {
                    strbuf_append(sb, fillchar, fillchar_len);
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

/* Output abstraction shared by the two clip paths: the painter path records
 * overlapping cells and cursor movement into a cell model before
 * reconstruction; the simple path appends directly to the output buffer. */
typedef struct
{
    bool painter;
    strbuf_t *sb;           /* simple output */
    painter_cells_t *cells; /* painter cell model */
    painter_seqs_t *seqs;
    int *seq_order;
    const char *fillchar;
    size_t fillchar_len;
    bool track_sgr;
    wcwidth_sgr_state_t *current_style;
    wcwidth_sgr_state_t *captured_style;
    bool *style_captured;
} clip_out_t;

/* Emit a raw sequence (escape sequence or zero-width text).  The simple path
 * appends it; the painter path records it in the sequence model. */
static bool
clip_out_seq(clip_out_t *o, const char *text, size_t len, int col)
{
    if (o->painter) {
        return painter_add_seq(o->seqs, o->seq_order, col, text, len);
    }
    strbuf_append(o->sb, text, len);
    return true;
}

/* Emit visible grapheme text (width > 0).  The painter path writes it into
 * the cell model; the simple path appends it and captures the active SGR
 * state (the painter captures inside painter_write_cells). */
static bool
clip_out_cells(clip_out_t *o, const char *text, size_t len, int width, int col, bool is_hyperlink)
{
    if (o->painter) {
        return painter_write_cells(o->cells, text, len, width, col, is_hyperlink, o->fillchar,
                                   o->fillchar_len, o->current_style, o->captured_style,
                                   o->style_captured, o->track_sgr);
    }
    strbuf_append(o->sb, text, len);
    capture_style(o->track_sgr, *o->current_style, o->captured_style, o->style_captured);
    return true;
}

/* Fill the visible columns [col, col+count) with fillchar. */
static bool
clip_out_fill(clip_out_t *o, int col, int count)
{
    if (o->painter) {
        int off;
        for (off = col; off < col + count; off++) {
            if (!painter_write_cells(o->cells, NULL, 0, 1, off, false, o->fillchar, o->fillchar_len,
                                     o->current_style, o->captured_style, o->style_captured,
                                     o->track_sgr))
                return false;
        }
        return true;
    }
    while (count-- > 0) {
        strbuf_append(o->sb, o->fillchar, o->fillchar_len);
    }
    capture_style(o->track_sgr, *o->current_style, o->captured_style, o->style_captured);
    return true;
}

/* Expand one tab column: the simple path emits a literal space (not the
 * fillchar), the painter path a fillchar cell. */
static bool
clip_out_tab(clip_out_t *o, int col)
{
    if (o->painter) {
        return painter_write_cells(o->cells, NULL, 0, 1, col, false, o->fillchar, o->fillchar_len,
                                   o->current_style, o->captured_style, o->style_captured,
                                   o->track_sgr);
    }
    strbuf_append_char(o->sb, ' ');
    capture_style(o->track_sgr, *o->current_style, o->captured_style, o->style_captured);
    return true;
}

static bool
clip_run(const char *text, size_t text_len, size_t v_start, size_t v_end, const char *fillchar,
         size_t fillchar_len, int tabsize, int ambiguous_width, const char *term_program,
         wcwidth_control_mode_t control_codes, bool strict, bool propagate_sgr,
         wcwidth_sgr_state_t *captured_style, bool *style_captured, strbuf_t *sb, bool painter_mode,
         int *error)
{
    painter_cells_t cells;
    painter_seqs_t seqs;
    int seq_order = 0;
    clip_out_t out;
    wcwidth_sgr_state_t current_style;
    bool track_sgr;
    int col;
    size_t idx;

    if (painter_mode) {
        painter_cells_init(&cells);
        painter_seqs_init(&seqs);
    }
    track_sgr = propagate_sgr;
    current_style = WCWIDTH_SGR_STATE_DEFAULT;
    *style_captured = false;
    col = 0;
    idx = 0;

    out.painter = painter_mode;
    out.sb = sb;
    out.cells = &cells;
    out.seqs = &seqs;
    out.seq_order = &seq_order;
    out.fillchar = fillchar;
    out.fillchar_len = fillchar_len;
    out.track_sgr = track_sgr;
    out.current_style = &current_style;
    out.captured_style = captured_style;
    out.style_captured = style_captured;

    while (idx < text_len) {
        unsigned char ch = (unsigned char) text[idx];

        /* Early exit past the visible region: the painter stops once the
         * style is captured; the simple path additionally skips plain-text
         * runs without escapes when SGR tracking is disabled. */
        if (col >= (int) v_end) {
            if (painter_mode) {
                if (*style_captured && ch != ESC) {
                    break;
                }
            }
            else if (ch != '\r' && ch != '\x08' && ch != '\t' && ch != ESC) {
                if (*style_captured) {
                    break;
                }
                if (!track_sgr) {
                    const char *next =
                        (const char *) memchr(text + idx + 1, ESC, text_len - idx - 1);
                    if (next == NULL) {
                        break;
                    }
                    idx = (size_t) (next - text);
                    continue;
                }
            }
        }

        if (ch == ESC) {
            wcwidth_esc_result_t result;

            if (!wcwidth_escape_classify(text, text_len, idx, &result)) {
                if (!clip_out_seq(&out, text + idx, 1, col)) {
                    goto fail;
                }
                if (painter_mode) {
                    capture_style(track_sgr, current_style, captured_style, style_captured);
                }
                idx++;
                continue;
            }

            /* SGR: update state, do not emit. */
            if (result.type == WCWIDTH_ESC_SGR && track_sgr) {
                wcwidth_sgr_update(&current_style, result.sgr_params, result.sgr_params_len);
                idx += result.length;
                continue;
            }

            /* OSC 8 hyperlink.  A dangling close is an empty-url open per
             * the reference implementation: process it as a unit so that
             * empty hyperlinks (close without matching open) are dropped. */
            if (result.type == WCWIDTH_ESC_OSC8_OPEN || result.type == WCWIDTH_ESC_OSC8_CLOSE) {
                wcwidth_hyperlink_params_t hl_params;
                if (wcwidth_hyperlink_parse_open(result.start, result.length, &hl_params)) {
                    char open_seq_buf[256], close_seq_buf[256];
                    size_t open_len, close_len, ce, clipped_len;
                    int action, inner_w, clipped_w, hl_end;
                    char *hl_buf = NULL;
                    size_t hl_buf_cap = 0;

                    action = process_hyperlink(
                        text, text_len, v_start, v_end, fillchar, fillchar_len, tabsize,
                        ambiguous_width, term_program, control_codes, &hl_params,
                        idx + result.length, col, &ce, &inner_w, open_seq_buf, &open_len, &hl_buf,
                        &hl_buf_cap, &clipped_len, close_seq_buf, &close_len, &clipped_w, &hl_end);

                    if (action < 0) {
                        free(hl_buf);
                        goto fail;
                    }
                    if (action == 0) {
                        if (!clip_out_seq(&out, result.start, result.length, col)) {
                            free(hl_buf);
                            goto fail;
                        }
                        if (painter_mode) {
                            capture_style(track_sgr, current_style, captured_style, style_captured);
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
                        /* VISIBLE: re-emit open, clipped content, close. */
                        if (!clip_out_seq(&out, open_seq_buf, open_len, col)) {
                            free(hl_buf);
                            goto fail;
                        }
                        capture_style(track_sgr, current_style, captured_style, style_captured);
                        if (!clip_out_cells(&out, hl_buf, clipped_len, clipped_w, col, true)) {
                            free(hl_buf);
                            goto fail;
                        }
                        col += clipped_w;
                        if (!clip_out_seq(&out, close_seq_buf, close_len, col)) {
                            free(hl_buf);
                            goto fail;
                        }
                        col = hl_end;
                        idx = ce;
                    }
                    free(hl_buf);
                }
                else {
                    if (!clip_out_seq(&out, result.start, result.length, col)) {
                        goto fail;
                    }
                    if (painter_mode) {
                        capture_style(track_sgr, current_style, captured_style, style_captured);
                    }
                    idx += result.length;
                }
                continue;
            }

            /* OSC 66 Text Sizing. */
            if (result.type == WCWIDTH_ESC_OSC66) {
                wcwidth_text_sizing_t ts;
                wcwidth_ts_from_esc(&result, &ts);

                if (painter_mode) {
                    ts_painter_ctx_t pctx;

                    pctx.cells = &cells;
                    pctx.fillchar = fillchar;
                    pctx.fillchar_len = fillchar_len;
                    pctx.current_style = &current_style;
                    pctx.captured_style = captured_style;
                    pctx.style_captured = style_captured;
                    pctx.track_sgr = track_sgr;
                    col = clip_text_sizing(&ts, col, (int) v_start, (int) v_end, ambiguous_width,
                                           term_program, ts_emit_painter, &pctx);
                    capture_style(track_sgr, current_style, captured_style, style_captured);
                }
                else {
                    ts_simple_ctx_t sctx;
                    int ts_width = wcwidth_ts_display_width(&ts, ambiguous_width);
                    int prev_col = col;

                    sctx.sb = sb;
                    sctx.fillchar = fillchar;
                    sctx.fillchar_len = fillchar_len;
                    col = clip_text_sizing(&ts, col, (int) v_start, (int) v_end, ambiguous_width,
                                           term_program, ts_emit_simple, &sctx);
                    if ((prev_col >= (int) v_start && prev_col + ts_width <= (int) v_end)
                        || (prev_col < (int) v_end && prev_col + ts_width > (int) v_start)) {
                        capture_style(track_sgr, current_style, captured_style, style_captured);
                    }
                }
                idx += result.length;
                continue;
            }

            /* Indeterminate sequences: error in strict mode. */
            if (strict && is_indeterminate_seq(&result)) {
                *error = WCWIDTH_ERROR_INDETERMINATE;
                goto fail;
            }

            /* Cursor movement: only the painter path resolves these into the
             * cell model; the simple path passes them through as sequences. */
            if (painter_mode) {
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
                            if (!painter_write_cells(&cells, NULL, 0, 1, x, false, fillchar,
                                                     fillchar_len, &current_style, captured_style,
                                                     style_captured, track_sgr))
                                goto fail;
                        }
                    }
                    col = move_end;
                    idx += result.length;
                    continue;
                }

                if (result.type == WCWIDTH_ESC_CUB) {
                    int n_backward = result.cursor_n;
                    if (strict && n_backward > col) {
                        *error = WCWIDTH_ERROR_CURSOR_LEFT_EXCEED;
                        goto fail;
                    }
                    col -= n_backward;
                    if (col < 0) {
                        col = 0;
                    }
                    idx += result.length;
                    continue;
                }
            }

            /* Any other recognized sequence: preserve as-is. */
            if (!clip_out_seq(&out, result.start, result.length, col)) {
                goto fail;
            }
            if (painter_mode) {
                capture_style(track_sgr, current_style, captured_style, style_captured);
            }
            idx += result.length;
            continue;
        }

        /* Carriage return / backspace: movement for the painter path (which
         * only runs in parse/strict modes) and in parse/strict modes;
         * passed through as text otherwise. */
        if (ch == '\r' && (painter_mode || control_codes != WCWIDTH_IGNORE)) {
            col = 0;
            idx++;
            continue;
        }
        if (ch == '\x08' && (painter_mode || control_codes != WCWIDTH_IGNORE)) {
            if (col > 0) {
                col--;
            }
            idx++;
            continue;
        }

        /* Tab expansion. */
        if (ch == '\t') {
            if (tabsize > 0) {
                int next_tab = col + (tabsize - (col % tabsize));
                while (col < next_tab) {
                    if ((int) v_start <= col && col < (int) v_end) {
                        if (!clip_out_tab(&out, col)) {
                            goto fail;
                        }
                    }
                    col++;
                }
            }
            else {
                if (!clip_out_seq(&out, "\t", 1, col)) {
                    goto fail;
                }
                if (painter_mode) {
                    capture_style(track_sgr, current_style, captured_style, style_captured);
                }
            }
            idx++;
            continue;
        }

        /* Grapheme cluster. */
        {
            wcwidth_grapheme_iter_t *giter = wcwidth_grapheme_iter_new(text + idx, text_len - idx);
            const char *grapheme;
            size_t g_len;
            int g_w;

            if (giter == NULL) {
                goto fail;
            }
            grapheme = wcwidth_grapheme_next(giter, &g_len);
            if (grapheme == NULL || g_len == 0) {
                wcwidth_grapheme_iter_free(giter);
                idx++;
                continue;
            }
            g_w = grapheme_width(grapheme, g_len, ambiguous_width, term_program);

            if (g_w == 0) {
                if ((int) v_start <= col && col < (int) v_end) {
                    if (!clip_out_seq(&out, grapheme, g_len, col)) {
                        wcwidth_grapheme_iter_free(giter);
                        goto fail;
                    }
                    if (painter_mode) {
                        capture_style(track_sgr, current_style, captured_style, style_captured);
                    }
                }
            }
            else if (col >= (int) v_start && col + g_w <= (int) v_end) {
                if (!clip_out_cells(&out, grapheme, g_len, g_w, col, false)) {
                    wcwidth_grapheme_iter_free(giter);
                    goto fail;
                }
            }
            else if (col < (int) v_end && col + g_w > (int) v_start) {
                int c_start = ((int) v_start > col) ? (int) v_start : col;
                int c_end = ((int) v_end < col + g_w) ? (int) v_end : col + g_w;
                if (!clip_out_fill(&out, c_start, c_end - c_start)) {
                    wcwidth_grapheme_iter_free(giter);
                    goto fail;
                }
            }

            wcwidth_grapheme_iter_free(giter);
            col += g_w;
            idx += g_len;
        }
    }

    if (painter_mode) {
        reconstruct_painter(&cells, &seqs, (int) v_start, (int) v_end, fillchar, fillchar_len, sb);
        painter_cells_free(&cells);
        painter_seqs_free(&seqs);
    }
    return true;

fail:
    if (painter_mode) {
        painter_cells_free(&cells);
        painter_seqs_free(&seqs);
    }
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
        const char *term_program, bool propagate_sgr, int overtyping, const char *fillchar,
        size_t fillchar_len, size_t *out_len, int *error)
{
    strbuf_t sb;
    wcwidth_sgr_state_t captured_style;
    bool style_captured;
    bool strict;
    bool has_esc;

    if (out_len != NULL)
        *out_len = 0;
    if (error != NULL)
        *error = WCWIDTH_ERROR_NONE;

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

    /* Determine whether painter's algorithm is needed.  Matches the pure
     * implementation: 'ignore' disables it; -1 auto-detects from cursor
     * movement characters; 0/1 force it off/on. */
    if (control_codes == WCWIDTH_IGNORE) {
        overtyping = 0;
    }
    else if (overtyping < 0) {
        overtyping = 0;
        if (memchr(text, '\x08', text_len) != NULL || memchr(text, '\r', text_len) != NULL) {
            overtyping = 1;
        }
        else if (has_esc) {
            overtyping = wcwidth_escape_has_cursor_movement(text, text_len) ? 1 : 0;
        }
    }

    strbuf_init(&sb, 256);
    if (sb.buf == NULL)
        return NULL;

    captured_style = WCWIDTH_SGR_STATE_DEFAULT;
    style_captured = false;

    if (!clip_run(text, text_len, v_start, v_end, fillchar, fillchar_len, tabsize, ambiguous_width,
                  term_program, control_codes, strict, propagate_sgr, &captured_style,
                  &style_captured, &sb, overtyping != 0, error)) {
        strbuf_free(&sb);
        return NULL;
    }

    if (propagate_sgr && style_captured) {
        apply_sgr_wrap(&sb, &captured_style, wcwidth_sgr_is_active(&captured_style));
    }

    return strbuf_detach(&sb, out_len);
}

uint32_t *
clip_u32(const uint32_t *codepoints, size_t n, size_t v_start, size_t v_end,
         wcwidth_control_mode_t control_codes, int tabsize, int ambiguous_width,
         const char *term_program, bool propagate_sgr, int overtyping, const char *fillchar,
         size_t fillchar_len, size_t *out_len, int *error)
{
    char enc_stack[512];
    size_t enc_len;
    char *utf8;
    uint32_t *result;

    if (out_len != NULL) {
        *out_len = 0;
    }
    if (error != NULL) {
        *error = WCWIDTH_ERROR_NONE;
    }

    utf8 = wcwidth_encode_u32(codepoints, n, enc_stack, sizeof(enc_stack), &enc_len);
    if (utf8 == NULL) {
        return NULL;
    }
    {
        size_t byte_len = 0;
        char *bytes = clip_u8(utf8, enc_len, v_start, v_end, control_codes, tabsize,
                              ambiguous_width, term_program, propagate_sgr, overtyping, fillchar,
                              fillchar_len, &byte_len, error);

        if (utf8 != enc_stack) {
            free(utf8);
        }
        if (bytes == NULL) {
            return NULL; /* *error already set by clip_u8 */
        }
        result = wcwidth_decode_u32_heap(bytes, byte_len, out_len);
        free(bytes);
    }
    return result;
}
