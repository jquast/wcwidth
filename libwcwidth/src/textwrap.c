/*
 * Text wrapping for terminal text, with unicode, CJK, emoji, and terminal sequence support.
 * 
 * This is a port of Python's TextWrapper and extended for unicode and terminal sequence support,
 * and so it shares the same behavior and options as wcwidth_wrap_opts_t
 */
#include "wcwidth/textwrap.h"
#include "wcwidth/width.h"
#include "wcwidth/escape.h"
#include "wcwidth/grapheme.h"
#include "wcwidth/hyperlink.h"
#include "wcwidth/sgr.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#define ESC 0x1b

const wcwidth_wrap_opts_t WCWIDTH_WRAP_OPTS_DEFAULT = {
    .width = 70,
    .control_codes = WCWIDTH_PARSE,
    .tabsize = 8,
    .ambiguous_width = 1,
    .term_program = NULL,
    .expand_tabs = true,
    .replace_whitespace = true,
    .break_long_words = true,
    .break_on_hyphens = true,
    .drop_whitespace = true,
    .propagate_sgr = true,
    .max_lines = 0,
    .initial_indent = "",
    .subsequent_indent = "",
    .placeholder = " [...]",
};

typedef struct
{
    char *data;
    size_t len;
    size_t cap;
} sbuf_t;

static void
sbuf_init(sbuf_t *b)
{
    b->data = NULL;
    b->len = 0;
    b->cap = 0;
}

static bool
sbuf_grow(sbuf_t *b, size_t need)
{
    size_t nc = b->cap ? b->cap : 64;
    while (nc < b->len + need) {
        nc *= 2;
    }
    char *nd = realloc(b->data, nc + 1);
    if (nd == NULL)
        return false;
    b->data = nd;
    b->cap = nc;
    return true;
}

static bool
sbuf_append(sbuf_t *b, const char *s, size_t n)
{
    if (n == 0)
        return true;
    if (b->len + n > b->cap && !sbuf_grow(b, n))
        return false;
    memcpy(b->data + b->len, s, n);
    b->len += n;
    b->data[b->len] = '\0';
    return true;
}

static bool
sbuf_append_str(sbuf_t *b, const char *s)
{
    return sbuf_append(b, s, strlen(s));
}

static void
sbuf_free(sbuf_t *b)
{
    free(b->data);
    b->data = NULL;
    b->len = 0;
    b->cap = 0;
}

static int
chunk_width(const char *data, size_t len, const wcwidth_wrap_opts_t *opts)
{
    wcwidth_width_opts_t wopts;
    int error = 0;
    int w;

    wopts.tabsize = opts->tabsize;
    wopts.ambiguous_width = opts->ambiguous_width;
    wopts.term_program = opts->term_program;

    w = width_u8(data, len, opts->control_codes, &wopts, &error);
    return (w < 0) ? 0 : w;
}

static int
str_width(const char *s, const wcwidth_wrap_opts_t *opts)
{
    return chunk_width(s, strlen(s), opts);
}

static void
strip_seqs_to(const char *text, size_t len, sbuf_t *out)
{
    size_t idx = 0;
    wcwidth_esc_result_t r;

    sbuf_init(out);
    while (idx < len) {
        if (text[idx] == ESC && wcwidth_escape_classify(text, len, idx, &r)) {
            idx += r.length;
        }
        else {
            sbuf_append(out, text + idx, 1);
            idx++;
        }
    }
}

static void
extract_seqs_to(const char *text, size_t len, sbuf_t *out)
{
    size_t idx = 0;
    wcwidth_esc_result_t r;

    sbuf_init(out);
    while (idx < len) {
        if (text[idx] == ESC && wcwidth_escape_classify(text, len, idx, &r)) {
            sbuf_append(out, r.start, r.length);
            idx += r.length;
        }
        else {
            idx++;
        }
    }
}

static bool
is_all_ws(const char *data, size_t len)
{
    size_t i;
    for (i = 0; i < len; i++) {
        if (data[i] != ' ')
            return false;
    }
    return true;
}

static bool
expand_tabs_to(const char *text, size_t len, int ts, sbuf_t *out)
{
    size_t col = 0, i;

    sbuf_init(out);
    for (i = 0; i < len; i++) {
        if ((unsigned char) text[i] == '\t') {
            int n = ts - (int) (col % (size_t) ts);
            int j;
            for (j = 0; j < n; j++) {
                if (!sbuf_append(out, " ", 1)) {
                    sbuf_free(out);
                    return false;
                }
            }
            col += (size_t) n;
        }
        else {
            if (!sbuf_append(out, text + i, 1)) {
                sbuf_free(out);
                return false;
            }
            col++;
        }
    }
    return true;
}

static bool
replace_ws_to(const char *text, size_t len, sbuf_t *out)
{
    size_t i;
    sbuf_init(out);
    for (i = 0; i < len; i++) {
        unsigned char ch = (unsigned char) text[i];
        char c =
            (ch == '\n' || ch == '\r' || ch == '\v' || ch == '\f' || ch == '\t') ? ' ' : (char) ch;
        if (!sbuf_append(out, &c, 1)) {
            sbuf_free(out);
            return false;
        }
    }
    return true;
}

typedef struct
{
    char *data;
    size_t len;
} chunk_t;

typedef struct
{
    chunk_t *chunks;
    size_t count;
    size_t cap;
} chunklist_t;

static void
cl_init(chunklist_t *cl)
{
    cl->chunks = NULL;
    cl->count = 0;
    cl->cap = 0;
}

static bool
cl_push(chunklist_t *cl, const char *data, size_t len)
{
    if (cl->count >= cl->cap) {
        size_t nc = cl->cap ? cl->cap * 2 : 16;
        chunk_t *nd = realloc(cl->chunks, nc * sizeof(chunk_t));
        if (nd == NULL)
            return false;
        cl->chunks = nd;
        cl->cap = nc;
    }
    cl->chunks[cl->count].data = malloc(len + 1);
    if (cl->chunks[cl->count].data == NULL)
        return false;
    memcpy(cl->chunks[cl->count].data, data, len);
    cl->chunks[cl->count].data[len] = '\0';
    cl->chunks[cl->count].len = len;
    cl->count++;
    return true;
}

static bool
cl_prepend_last(chunklist_t *cl, const char *s, size_t n)
{
    chunk_t *c;
    char *nd;
    if (cl->count == 0)
        return false;
    c = &cl->chunks[cl->count - 1];
    nd = malloc(n + c->len + 1);
    if (nd == NULL)
        return false;
    memcpy(nd, s, n);
    memcpy(nd + n, c->data, c->len);
    nd[n + c->len] = '\0';
    free(c->data);
    c->data = nd;
    c->len = n + c->len;
    return true;
}

static bool
cl_append_last(chunklist_t *cl, const char *s, size_t n)
{
    chunk_t *c;
    char *nd;
    if (cl->count == 0)
        return false;
    c = &cl->chunks[cl->count - 1];
    nd = realloc(c->data, c->len + n + 1);
    if (nd == NULL)
        return false;
    memcpy(nd + c->len, s, n);
    nd[c->len + n] = '\0';
    c->data = nd;
    c->len = c->len + n;
    return true;
}

static void
cl_pop(chunklist_t *cl)
{
    if (cl->count == 0)
        return;
    cl->count--;
    free(cl->chunks[cl->count].data);
    cl->chunks[cl->count].data = NULL;
    cl->chunks[cl->count].len = 0;
}

static chunk_t *
cl_last(chunklist_t *cl)
{
    return (cl->count == 0) ? NULL : &cl->chunks[cl->count - 1];
}

static void
cl_free(chunklist_t *cl)
{
    while (cl->count > 0)
        cl_pop(cl);
    free(cl->chunks);
    cl->chunks = NULL;
    cl->cap = 0;
}

/* Pop from chunks and push to dest (moves ownership) */
static void
cl_move(chunklist_t *src, chunklist_t *dst)
{
    if (src->count == 0)
        return;
    chunk_t *c = &src->chunks[src->count - 1];
    src->count--;
    cl_push(dst, c->data, c->len);
    free(c->data);
}

/* Reverse the chunklist in place */
static void
cl_reverse(chunklist_t *cl)
{
    size_t n = cl->count, i;
    for (i = 0; i < n / 2; i++) {
        chunk_t tmp = cl->chunks[i];
        cl->chunks[i] = cl->chunks[n - 1 - i];
        cl->chunks[n - 1 - i] = tmp;
    }
}

/*
 * Build char_end[]:
 *   char_end[i] = byte offset in processed text just after the i-th
 *   stripped character.  stripped accumulates visible chars only.
 */
struct split_map
{
    size_t *char_end;
    size_t char_end_len;
    size_t char_end_cap;
    sbuf_t stripped;
};

static bool
sm_init(struct split_map *sm, const char *text, size_t len)
{
    size_t idx = 0, orig_pos = 0;
    bool prev_close = false;
    wcwidth_esc_result_t r;

    memset(sm, 0, sizeof(*sm));
    sbuf_init(&sm->stripped);
    sm->char_end_cap = 64;
    sm->char_end = malloc(sm->char_end_cap * sizeof(size_t));
    if (sm->char_end == NULL)
        return false;

    while (idx < len) {
        if (text[idx] == ESC && wcwidth_escape_classify(text, len, idx, &r)) {
            bool is_close = (r.type == WCWIDTH_ESC_OSC8_CLOSE);
            bool is_osc = (r.type == WCWIDTH_ESC_OSC8_OPEN || r.type == WCWIDTH_ESC_OSC8_CLOSE);

            /* Insert space before OSC (not before close) */
            if (is_osc && sm->stripped.len > 0 && sm->stripped.data[sm->stripped.len - 1] != ' ') {
                if (!is_close) {
                    if (!sbuf_append(&sm->stripped, " ", 1))
                        goto fail;
                    if (sm->char_end_len >= sm->char_end_cap) {
                        sm->char_end_cap *= 2;
                        size_t *nd = realloc(sm->char_end, sm->char_end_cap * sizeof(size_t));
                        if (nd == NULL)
                            goto fail;
                        sm->char_end = nd;
                    }
                    sm->char_end[sm->char_end_len++] = orig_pos;
                }
            }

            orig_pos += r.length;
            idx += r.length;
            prev_close = is_close;
        }
        else {
            unsigned char ch = (unsigned char) text[idx];
            size_t cp_len = 1;

            /* Insert space after hyperlink close */
            if (prev_close && ch != ' ') {
                if (!sbuf_append(&sm->stripped, " ", 1))
                    goto fail;
                if (sm->char_end_len >= sm->char_end_cap) {
                    sm->char_end_cap *= 2;
                    size_t *nd = realloc(sm->char_end, sm->char_end_cap * sizeof(size_t));
                    if (nd == NULL)
                        goto fail;
                    sm->char_end = nd;
                }
                sm->char_end[sm->char_end_len++] = orig_pos;
            }
            prev_close = false;

            if (ch >= 0xC0) {
                if (ch < 0xE0)
                    cp_len = 2;
                else if (ch < 0xF0)
                    cp_len = 3;
                else if (ch < 0xF8)
                    cp_len = 4;
                if (idx + cp_len > len)
                    cp_len = 1;
            }

            /* Add one char_end entry per byte of visible text */
            {
                size_t k;
                for (k = 0; k < cp_len && idx + k < len; k++) {
                    orig_pos++;
                    if (sm->char_end_len >= sm->char_end_cap) {
                        sm->char_end_cap *= 2;
                        size_t *nd = realloc(sm->char_end, sm->char_end_cap * sizeof(size_t));
                        if (nd == NULL)
                            goto fail;
                        sm->char_end = nd;
                    }
                    sm->char_end[sm->char_end_len++] = orig_pos;
                    sbuf_append(&sm->stripped, text + idx + k, 1);
                }
            }
            idx += cp_len;
        }
    }

    /* Sentinel */
    if (sm->char_end_len >= sm->char_end_cap) {
        sm->char_end_cap *= 2;
        size_t *nd = realloc(sm->char_end, sm->char_end_cap * sizeof(size_t));
        if (nd == NULL)
            goto fail;
        sm->char_end = nd;
    }
    sm->char_end[sm->char_end_len++] = orig_pos;
    return true;

fail:
    free(sm->char_end);
    sbuf_free(&sm->stripped);
    memset(sm, 0, sizeof(*sm));
    return false;
}

static void
sm_free(struct split_map *sm)
{
    free(sm->char_end);
    sbuf_free(&sm->stripped);
}

struct wrange
{
    size_t start, end;
};

static bool
split_words_on_ws(const char *s, size_t slen, bool drop_ws, struct wrange **out, size_t *n_out)
{
    size_t i = 0, cnt = 0, cap = 16;
    struct wrange *rng = malloc(cap * sizeof(*rng));
    if (rng == NULL)
        return false;

    while (i < slen) {
        if (drop_ws) {
            while (i < slen && s[i] == ' ')
                i++;
            if (i >= slen)
                break;
        }
        size_t start = i;
        while (i < slen && s[i] != ' ')
            i++;
        size_t end = i;

        if (cnt >= cap) {
            cap *= 2;
            struct wrange *nd = realloc(rng, cap * sizeof(*nd));
            if (nd == NULL) {
                free(rng);
                return false;
            }
            rng = nd;
        }
        rng[cnt].start = start;
        rng[cnt].end = end;
        cnt++;

        if (!drop_ws) {
            start = i;
            while (i < slen && s[i] == ' ')
                i++;
            if (i > start) {
                if (cnt >= cap) {
                    cap *= 2;
                    struct wrange *nd = realloc(rng, cap * sizeof(*nd));
                    if (nd == NULL) {
                        free(rng);
                        return false;
                    }
                    rng = nd;
                }
                rng[cnt].start = start;
                rng[cnt].end = i;
                cnt++;
            }
        }
    }

    *out = rng;
    *n_out = cnt;
    return true;
}

static bool
_split(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts, chunklist_t *out)
{
    sbuf_t proc;
    struct split_map sm;
    struct wrange *rng = NULL;
    size_t n_rng = 0, ri;

    cl_init(out);

    /* 1. Expand tabs */
    if (opts->expand_tabs) {
        if (!expand_tabs_to(text, text_len, opts->tabsize, &proc))
            return false;
    }
    else {
        if (!sbuf_append(&proc, text, text_len))
            return false;
    }

    /* 2. Replace whitespace */
    if (opts->replace_whitespace) {
        sbuf_t tmp;
        if (!replace_ws_to(proc.data, proc.len, &tmp)) {
            sbuf_free(&proc);
            return false;
        }
        sbuf_free(&proc);
        proc = tmp;
    }

    /* 3. Build char_end mapping */
    if (!sm_init(&sm, proc.data, proc.len)) {
        sbuf_free(&proc);
        return false;
    }

    /* Sequences-only text */
    if (sm.stripped.len == 0 && proc.len > 0) {
        cl_push(out, proc.data, proc.len);
        sm_free(&sm);
        sbuf_free(&proc);
        return true;
    }

    /* 4. Split stripped text */
    {
        bool ext_drop = opts->drop_whitespace;
        if (!split_words_on_ws(sm.stripped.data, sm.stripped.len, false, &rng, &n_rng)) {
            sm_free(&sm);
            sbuf_free(&proc);
            return false;
        }

        /* If drop_whitespace, merge whitespace into preceding word chunks
         * by extending each word range to include trailing whitespace. */
        if (ext_drop) {
            size_t ri = 0, wi = 0;
            struct wrange *merged = malloc(n_rng * sizeof(*merged));
            if (merged == NULL) {
                free(rng);
                sm_free(&sm);
                sbuf_free(&proc);
                return false;
            }
            while (ri < n_rng) {
                size_t st = rng[ri].start;
                /* this range is a word */
                ri++;
                /* Extend to include trailing whitespace */
                if (ri < n_rng) {
                    /* Next range is whitespace -- absorb it */
                    merged[wi].start = st;
                    merged[wi].end = rng[ri].end;
                    ri++;
                }
                else {
                    merged[wi].start = st;
                    merged[wi].end = rng[ri - 1].end;
                }
                wi++;
            }
            free(rng);
            rng = merged;
            n_rng = wi;
        }
    }

    /* 5. Map back */
    {
        for (ri = 0; ri < n_rng; ri++) {
            size_t st = rng[ri].start;
            size_t en = rng[ri].end;
            size_t cs = en - st;
            size_t start_orig, end_orig;
            if (cs == 0)
                continue;
            start_orig = (st == 0) ? 0 : sm.char_end[st - 1];
            end_orig = sm.char_end[en - 1];
            if (start_orig < end_orig && end_orig <= proc.len)
                cl_push(out, proc.data + start_orig, end_orig - start_orig);
        }
    }

    free(rng);
    sm_free(&sm);
    sbuf_free(&proc);
    return true;
}

typedef struct
{
    char *url;
    size_t url_len;
    char *params;
    size_t params_len;
    char term;
} hl_t;

static void
hl_free(hl_t *s)
{
    if (s != NULL) {
        free(s->url);
        free(s->params);
        free(s);
    }
}

static hl_t *
hl_copy(const hl_t *src)
{
    hl_t *s;
    if (src == NULL)
        return NULL;
    s = malloc(sizeof(hl_t));
    if (s == NULL)
        return NULL;
    s->url = malloc(src->url_len + 1);
    s->params = malloc(src->params_len + 1);
    if (s->url == NULL || s->params == NULL) {
        free(s->url);
        free(s->params);
        free(s);
        return NULL;
    }
    memcpy(s->url, src->url, src->url_len);
    s->url[src->url_len] = '\0';
    memcpy(s->params, src->params, src->params_len);
    s->params[src->params_len] = '\0';
    s->url_len = src->url_len;
    s->params_len = src->params_len;
    s->term = src->term;
    return s;
}

static hl_t *
hl_from_esc(const wcwidth_esc_result_t *r)
{
    wcwidth_hyperlink_params_t hp;
    hl_t *s;
    if (!wcwidth_hyperlink_parse_open(r->start, r->length, &hp))
        return NULL;
    if (hp.url_len == 0)
        return NULL;
    s = malloc(sizeof(hl_t));
    if (s == NULL)
        return NULL;
    s->url = malloc(hp.url_len + 1);
    s->params = malloc(hp.params_len + 1);
    if (s->url == NULL || s->params == NULL) {
        free(s->url);
        free(s->params);
        free(s);
        return NULL;
    }
    memcpy(s->url, hp.url, hp.url_len);
    s->url[hp.url_len] = '\0';
    memcpy(s->params, hp.params, hp.params_len);
    s->params[hp.params_len] = '\0';
    s->url_len = hp.url_len;
    s->params_len = hp.params_len;
    s->term = hp.terminator;
    return s;
}

static hl_t *
hl_track(const char *text, size_t len, hl_t *initial)
{
    hl_t *state = hl_copy(initial);
    size_t idx = 0;
    wcwidth_esc_result_t r;

    while (idx < len) {
        if (text[idx] == ESC && wcwidth_escape_classify(text, len, idx, &r)) {
            if (r.type == WCWIDTH_ESC_OSC8_OPEN) {
                hl_t *ns = hl_from_esc(&r);
                if (ns != NULL) {
                    hl_free(state);
                    state = ns;
                }
            }
            else if (r.type == WCWIDTH_ESC_OSC8_CLOSE) {
                hl_free(state);
                state = NULL;
            }
            idx += r.length;
        }
        else {
            idx++;
        }
    }
    return state;
}

static size_t
find_break_pos(const char *text, size_t len, int max_w, const wcwidth_wrap_opts_t *opts)
{
    size_t idx = 0;
    int w = 0;
    wcwidth_esc_result_t r;

    while (idx < len) {
        if (text[idx] == ESC && wcwidth_escape_classify(text, len, idx, &r)) {
            idx += r.length;
            continue;
        }
        wcwidth_grapheme_iter_t *gi;
        const char *gc;
        size_t glen;

        gi = wcwidth_grapheme_iter_new(text + idx, len - idx);
        if (gi == NULL)
            return idx;
        gc = wcwidth_grapheme_next(gi, &glen);
        wcwidth_grapheme_iter_free(gi);
        if (gc == NULL)
            return idx;

        {
            int gw = chunk_width(gc, glen, opts);
            if (w + gw > max_w)
                return idx;
            w += gw;
            idx += glen;
        }
    }
    return idx;
}

static size_t
find_first_vis(const char *text, size_t len)
{
    size_t idx = 0;
    wcwidth_esc_result_t r;

    while (idx < len && text[idx] == ESC && wcwidth_escape_classify(text, len, idx, &r)) {
        idx += r.length;
    }
    if (idx < len) {
        wcwidth_grapheme_iter_t *gi;
        size_t glen;
        gi = wcwidth_grapheme_iter_new(text + idx, len - idx);
        if (gi != NULL) {
            wcwidth_grapheme_next(gi, &glen);
            wcwidth_grapheme_iter_free(gi);
            idx += glen;
        }
        else {
            idx++;
        }
    }
    return idx;
}

static size_t
find_hyphen(const char *text, size_t len, int max_w)
{
    size_t idx = 0, last = 0;
    int w = 0;
    wcwidth_esc_result_t r;

    while (idx < len && w < max_w) {
        if (text[idx] == ESC && wcwidth_escape_classify(text, len, idx, &r)) {
            idx += r.length;
            continue;
        }
        if (text[idx] == '-')
            last = idx + 1;
        idx++;
        w++;
    }
    if (last > 0) {
        size_t j;
        for (j = 0; j < last - 1; j++)
            if (text[j] != '-')
                return last;
    }
    return 0;
}

static void
handle_long(chunklist_t *chunks, chunklist_t *cur_line, int cur_w, int line_w,
            const wcwidth_wrap_opts_t *opts)
{
    chunk_t *c;
    int sp_left;
    size_t bp;

    if (chunks->count == 0)
        return;
    c = cl_last(chunks);
    sp_left = (line_w < 1) ? 1 : line_w - cur_w;

    if (!opts->break_long_words) {
        if (cur_line->count == 0)
            cl_move(chunks, cur_line);
        return;
    }

    bp = 0;
    if (opts->break_on_hyphens) {
        int cw = chunk_width(c->data, c->len, opts);
        if (cw > sp_left)
            bp = find_hyphen(c->data, c->len, sp_left);
    }

    if (bp == 0) {
        bp = find_break_pos(c->data, c->len, sp_left, opts);
        if (cur_line->count == 0
            && (bp == 0 || (bp < c->len && chunk_width(c->data, bp, opts) == 0))) {
            bp = find_first_vis(c->data, c->len);
        }
    }
    if (bp == 0 || bp > c->len)
        bp = (c->len > 0) ? 1 : 0;

    cl_push(cur_line, c->data, bp);

    {
        size_t rest = c->len - bp;
        if (rest == 0) {
            cl_pop(chunks);
        }
        else {
            char *nd = malloc(rest + 1);
            if (nd != NULL) {
                memcpy(nd, c->data + bp, rest);
                nd[rest] = '\0';
                free(c->data);
                c->data = nd;
                c->len = rest;
            }
        }
    }

    while (chunks->count > 0 && cl_last(chunks)->len == 0)
        cl_pop(chunks);
}

typedef struct
{
    char **data;
    size_t count;
    size_t cap;
} lines_t;

static void
lines_init(lines_t *ll)
{
    ll->data = NULL;
    ll->count = 0;
    ll->cap = 0;
}

static bool
lines_push(lines_t *ll, const char *s, size_t n)
{
    if (ll->count >= ll->cap) {
        size_t nc = ll->cap ? ll->cap * 2 : 16;
        char **nd = realloc(ll->data, nc * sizeof(char *));
        if (nd == NULL)
            return false;
        ll->data = nd;
        ll->cap = nc;
    }
    /* Allocate 128 extra bytes for potential SGR propagation expansion. */
    ll->data[ll->count] = malloc(n + 129);
    if (ll->data[ll->count] == NULL)
        return false;
    memcpy(ll->data[ll->count], s, n);
    ll->data[ll->count][n] = '\0';
    ll->count++;
    return true;
}

static void
lines_free(lines_t *ll)
{
    size_t i;
    for (i = 0; i < ll->count; i++)
        free(ll->data[i]);
    free(ll->data);
    ll->data = NULL;
    ll->count = 0;
    ll->cap = 0;
}

static bool
_wrap_chunks(chunklist_t *chunks, const wcwidth_wrap_opts_t *opts, lines_t *lines)
{
    bool first = true;
    hl_t *hl = NULL;
    char hl_id[128] = "";
    bool has_id = false;

    lines_init(lines);
    cl_reverse(chunks);

    /* Check placeholder fits */
    if (opts->max_lines > 1) {
        const char *si = opts->subsequent_indent;
        const char *ps = opts->placeholder;
        while (*ps == ' ')
            ps++;
        if (str_width(si, opts) + str_width(ps, opts) > opts->width)
            return false;
    }

    while (chunks->count > 0) {
        chunklist_t cur;
        int cur_w = 0;
        const char *indent = first ? opts->initial_indent : opts->subsequent_indent;
        int indent_w = str_width(indent, opts);
        int line_w = opts->width - indent_w;

        cl_init(&cur);

        /* Prepend hyperlink open */
        if (hl != NULL) {
            char ob[256];
            wcwidth_hyperlink_params_t hp;
            hp.url = hl->url;
            hp.url_len = hl->url_len;
            hp.params = hl->params;
            hp.params_len = hl->params_len;
            hp.terminator = hl->term;
            size_t ol = wcwidth_hyperlink_make_open(&hp, ob, sizeof(ob));
            cl_prepend_last(chunks, ob, ol);
        }

        /* Drop leading whitespace */
        while (opts->drop_whitespace && lines->count > 0 && chunks->count > 0) {
            chunk_t *c = cl_last(chunks);
            sbuf_t st;
            strip_seqs_to(c->data, c->len, &st);
            bool ws = (st.len > 0 && is_all_ws(st.data, st.len));
            if (!ws) {
                sbuf_free(&st);
                break;
            }
            sbuf_t sq;
            extract_seqs_to(c->data, c->len, &sq);
            cl_pop(chunks);
            if (sq.len > 0 && chunks->count > 0)
                cl_prepend_last(chunks, sq.data, sq.len);
            sbuf_free(&st);
            sbuf_free(&sq);
        }

        /* Greedy fill */
        while (chunks->count > 0) {
            chunk_t *c = cl_last(chunks);
            int cw = chunk_width(c->data, c->len, opts);
            if (cur_w + cw <= line_w) {
                cl_move(chunks, &cur);
                cur_w += cw;
            }
            else {
                break;
            }
        }

        /* Handle long word */
        if (chunks->count > 0) {
            chunk_t *c = cl_last(chunks);
            if (chunk_width(c->data, c->len, opts) > line_w) {
                handle_long(chunks, &cur, cur_w, line_w, opts);
                cur_w = 0;
                {
                    size_t ci;
                    for (ci = 0; ci < cur.count; ci++)
                        cur_w += chunk_width(cur.chunks[ci].data, cur.chunks[ci].len, opts);
                }
            }
        }

        /* Drop trailing whitespace */
        while (opts->drop_whitespace && cur.count > 0) {
            chunk_t *c = &cur.chunks[cur.count - 1];
            sbuf_t st;
            strip_seqs_to(c->data, c->len, &st);
            bool ws = (st.len > 0 && is_all_ws(st.data, st.len));
            if (!ws) {
                sbuf_free(&st);
                break;
            }
            sbuf_t sq;
            extract_seqs_to(c->data, c->len, &sq);
            cur_w -= chunk_width(c->data, c->len, opts);
            cl_pop(&cur);
            if (sq.len > 0 && cur.count > 0)
                cl_append_last(&cur, sq.data, sq.len);
            sbuf_free(&st);
            sbuf_free(&sq);
        }

        if (cur.count == 0) {
            cl_free(&cur);
            continue;
        }

        /* Build line content */
        sbuf_t lc;
        {
            size_t ci;
            sbuf_init(&lc);
            for (ci = 0; ci < cur.count; ci++)
                sbuf_append(&lc, cur.chunks[ci].data, cur.chunks[ci].len);
        }

        /* Track hyperlink state */
        hl_t *new_hl = hl_track(lc.data, lc.len, hl);

        if (new_hl != NULL) {
            if (!has_id) {
                if (new_hl->params_len > 0) {
                    const char *p = strstr(new_hl->params, "id=");
                    if (p != NULL) {
                        const char *v = p + 3;
                        size_t vl = 0;
                        while (v[vl] && v[vl] != ':')
                            vl++;
                        if (vl < sizeof(hl_id) - 1) {
                            memcpy(hl_id, v, vl);
                            hl_id[vl] = '\0';
                            has_id = true;
                        }
                    }
                }
                if (!has_id) {
                    char hex[9];
                    wcwidth_hyperlink_next_id(hex);
                    hex[8] = '\0';
                    snprintf(hl_id, sizeof(hl_id), "id=%.8s", hex);
                    has_id = true;
                }
            }

            /* Append close */
            char cb[16];
            size_t cl = wcwidth_hyperlink_make_close(new_hl->term, cb, sizeof(cb));
            sbuf_append(&lc, cb, cl);

            /* Inject id if missing */
            if (!strstr(new_hl->params, "id=")) {
                wcwidth_hyperlink_params_t ohp, nhp;
                char oo[256], no[256];
                size_t ool, nol;

                ohp.url = new_hl->url;
                ohp.url_len = new_hl->url_len;
                ohp.params = new_hl->params;
                ohp.params_len = new_hl->params_len;
                ohp.terminator = new_hl->term;

                nhp.url = new_hl->url;
                nhp.url_len = new_hl->url_len;
                nhp.params = hl_id;
                nhp.params_len = strlen(hl_id);
                nhp.terminator = new_hl->term;

                ool = wcwidth_hyperlink_make_open(&ohp, oo, sizeof(oo));
                nol = wcwidth_hyperlink_make_open(&nhp, no, sizeof(no));

                if (ool > 0) {
                    char *pos = strstr(lc.data, oo);
                    if (pos != NULL) {
                        size_t off = (size_t) (pos - lc.data);
                        sbuf_t tmp;
                        sbuf_init(&tmp);
                        sbuf_append(&tmp, lc.data, off);
                        sbuf_append(&tmp, no, nol);
                        sbuf_append(&tmp, lc.data + off + ool, lc.len - off - ool);
                        sbuf_free(&lc);
                        lc = tmp;
                    }
                }
            }

            /* Next state with id */
            {
                hl_t *ns = malloc(sizeof(hl_t));
                if (ns != NULL) {
                    ns->url = malloc(new_hl->url_len + 1);
                    ns->params = malloc(strlen(hl_id) + 1);
                    if (ns->url != NULL && ns->params != NULL) {
                        memcpy(ns->url, new_hl->url, new_hl->url_len);
                        ns->url[new_hl->url_len] = '\0';
                        memcpy(ns->params, hl_id, strlen(hl_id) + 1);
                        ns->url_len = new_hl->url_len;
                        ns->params_len = strlen(hl_id);
                        ns->term = new_hl->term;
                        hl_free(hl);
                        hl = ns;
                    }
                    else {
                        free(ns->url);
                        free(ns->params);
                        free(ns);
                        hl_free(hl);
                        hl = NULL;
                    }
                }
            }
            hl_free(new_hl);
        }
        else {
            hl_free(hl);
            hl = NULL;
            has_id = false;
            hl_id[0] = '\0';
        }

        /* max_lines handling */
        {
            bool no_more = (chunks->count == 0);
            if (!no_more && opts->drop_whitespace && chunks->count == 1) {
                chunk_t *c = cl_last(chunks);
                sbuf_t st;
                strip_seqs_to(c->data, c->len, &st);
                no_more = is_all_ws(st.data, st.len);
                sbuf_free(&st);
            }

            if (opts->max_lines <= 0 || lines->count + 1 < (size_t) opts->max_lines
                || (no_more && cur_w <= line_w)) {
                /* Normal append */
                if (opts->drop_whitespace) {
                    while (lc.len > 0 && lc.data[lc.len - 1] == ' ')
                        lc.len--;
                    lc.data[lc.len] = '\0';
                }
                sbuf_t fl;
                sbuf_init(&fl);
                sbuf_append_str(&fl, indent);
                sbuf_append(&fl, lc.data, lc.len);
                lines_push(lines, fl.data, fl.len);
                sbuf_free(&fl);
                first = false;
            }
            else {
                /* Truncate */
                int pw = str_width(opts->placeholder, opts);
                bool ok = false;

                while (cur.count > 0) {
                    chunk_t *cl2 = &cur.chunks[cur.count - 1];
                    sbuf_t st;
                    strip_seqs_to(cl2->data, cl2->len, &st);
                    bool has_vis = !is_all_ws(st.data, st.len);
                    sbuf_free(&st);
                    if (has_vis && cur_w + pw <= line_w) {
                        sbuf_free(&lc);
                        {
                            size_t ci;
                            sbuf_init(&lc);
                            for (ci = 0; ci < cur.count; ci++)
                                sbuf_append(&lc, cur.chunks[ci].data, cur.chunks[ci].len);
                        }
                        /* Close hyperlink */
                        {
                            hl_t *ns = hl_track(lc.data, lc.len, hl);
                            if (ns != NULL) {
                                char cb[16];
                                size_t cl2_len =
                                    wcwidth_hyperlink_make_close(ns->term, cb, sizeof(cb));
                                sbuf_append(&lc, cb, cl2_len);
                                hl_free(ns);
                            }
                        }
                        sbuf_t fl;
                        sbuf_init(&fl);
                        sbuf_append_str(&fl, indent);
                        sbuf_append(&fl, lc.data, lc.len);
                        sbuf_append_str(&fl, opts->placeholder);
                        lines_push(lines, fl.data, fl.len);
                        sbuf_free(&fl);
                        ok = true;
                        break;
                    }
                    cur_w -= chunk_width(cl2->data, cl2->len, opts);
                    cl_pop(&cur);
                }

                if (!ok) {
                    if (lines->count > 0) {
                        char *pr = lines->data[lines->count - 1];
                        size_t prl = strlen(pr);
                        size_t rp = prl;
                        while (rp > 0 && pr[rp - 1] == ' ')
                            rp--;
                        if (chunk_width(pr, rp, opts) + pw <= opts->width) {
                            char *np = malloc(rp + strlen(opts->placeholder) + 1);
                            if (np != NULL) {
                                memcpy(np, pr, rp);
                                strcpy(np + rp, opts->placeholder);
                                free(pr);
                                lines->data[lines->count - 1] = np;
                                ok = true;
                            }
                        }
                    }
                    if (!ok) {
                        const char *ps = opts->placeholder;
                        while (*ps == ' ')
                            ps++;
                        lines_push(lines, ps, strlen(ps));
                    }
                }

                sbuf_free(&lc);
                cl_free(&cur);
                hl_free(hl);
                hl = NULL;
                break;
            }
        }

        sbuf_free(&lc);
        cl_free(&cur);
    }

    hl_free(hl);
    return true;
}

int
wrap_u8(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts, char **out,
        size_t *out_len)
{
    chunklist_t chunks;
    lines_t lines;
    size_t total = 0;
    size_t i;

    *out = NULL;
    *out_len = 0;

    if (text_len == 0) {
        *out = malloc(1);
        if (*out == NULL)
            return -1;
        (*out)[0] = '\0';
        return 0;
    }

    cl_init(&chunks);

    if (!_split(text, text_len, opts, &chunks))
        return -1;

    if (chunks.count == 0) {
        cl_free(&chunks);
        *out = malloc(1);
        if (*out == NULL)
            return -1;
        (*out)[0] = '\0';
        return 0;
    }

    if (!_wrap_chunks(&chunks, opts, &lines)) {
        cl_free(&chunks);
        return -1;
    }

    cl_free(&chunks);

    if (opts->propagate_sgr && lines.count > 0)
        wcwidth_sgr_propagate(lines.data, lines.count);

    /* Compute total output size: sum of line lengths + '\n' separators */
    for (i = 0; i < lines.count; i++)
        total += strlen(lines.data[i]);
    if (lines.count > 1)
        total += lines.count - 1; /* '\n' separators */

    *out = malloc(total + 1);
    if (*out == NULL) {
        lines_free(&lines);
        return -1;
    }

    {
        char *p = *out;
        for (i = 0; i < lines.count; i++) {
            size_t n = strlen(lines.data[i]);
            memcpy(p, lines.data[i], n);
            p += n;
            if (i + 1 < lines.count) {
                *p = '\n';
                p++;
            }
        }
        *p = '\0';
    }

    *out_len = total;
    lines_free(&lines);
    return 0;
}

static bool
is_all_whitespace_or_empty(const char *s, size_t len)
{
    size_t i;
    if (len == 0)
        return true;
    for (i = 0; i < len; i++) {
        char ch = s[i];
        if (ch != ' ' && ch != '\t' && ch != '\r')
            return false;
    }
    return true;
}

int
wrap_u8_text(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts, char **out,
             size_t *out_len)
{
    lines_t lines;
    const char *p = text;
    const char *end = text + text_len;
    size_t i;

    *out = NULL;
    *out_len = 0;

    lines_init(&lines);

    while (p < end) {
        const char *nl = memchr(p, '\n', (size_t) (end - p));
        size_t seg_len = nl ? (size_t) (nl - p) : (size_t) (end - p);

        if (is_all_whitespace_or_empty(p, seg_len)) {
            if (!lines_push(&lines, "", 0)) {
                lines_free(&lines);
                return -1;
            }
        }
        else {
            char *wrapped = NULL;
            size_t wrapped_len = 0;

            if (wrap_u8(p, seg_len, opts, &wrapped, &wrapped_len) != 0) {
                lines_free(&lines);
                return -1;
            }

            if (wrapped_len > 0) {
                const char *wp = wrapped;
                const char *we = wrapped + wrapped_len;
                while (wp < we) {
                    const char *wnl = memchr(wp, '\n', (size_t) (we - wp));
                    size_t wl = wnl ? (size_t) (wnl - wp) : (size_t) (we - wp);
                    if (!lines_push(&lines, wp, wl)) {
                        free(wrapped);
                        lines_free(&lines);
                        return -1;
                    }
                    wp += wl;
                    if (wnl)
                        wp++;
                }
            }

            free(wrapped);
        }

        p += seg_len;
        if (nl)
            p++;
    }

    /* Compute total output size */
    {
        size_t total = 0;
        for (i = 0; i < lines.count; i++)
            total += strlen(lines.data[i]);
        if (lines.count > 1)
            total += lines.count - 1;

        *out = malloc(total + 1);
        if (*out == NULL) {
            lines_free(&lines);
            return -1;
        }

        {
            char *dp = *out;
            for (i = 0; i < lines.count; i++) {
                size_t n = strlen(lines.data[i]);
                memcpy(dp, lines.data[i], n);
                dp += n;
                if (i + 1 < lines.count) {
                    *dp = '\n';
                    dp++;
                }
            }
            *dp = '\0';
        }
        *out_len = total;
    }

    lines_free(&lines);
    return 0;
}
