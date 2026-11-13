/*
 * Text wrapping for terminal text, derived from Python's textwrap.  Break opportunities follow
 * UAX #14 by default, with an option to split on ASCII space only.  docs/libwcwidth.rst lists the
 * differences from the Python stdlib, including the absent fix_sentence_endings and propagate_sgr
 * options and OSC 8 handling.
 */
#include "wcwidth/textwrap.h"
#include "wcwidth/width.h"
#include "wcwidth/escape.h"
#include "wcwidth/grapheme.h"
#include "wcwidth/utf8.h"
#include "wcwidth/linebreak.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

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
    .max_lines = 0,
    .initial_indent = "",
    .subsequent_indent = "",
    .placeholder = " [...]",
    .line_break = WCWIDTH_LINE_BREAK_UNICODE,
};

typedef struct
{
    char *data;
    size_t len;
    size_t cap;
    /*
     * Sticky allocation-failure flag.  Most sbuf_append() call sites in this
     * file drop the return value; without this, a failed grow leaves data
     * NULL and the next terminator write dereferences it.  Once set, appends
     * become no-ops and the buffer stays consistent, so callers can check
     * once at the point they consume the result.
     */
    bool oom;
} sbuf_t;

static void
sbuf_init(sbuf_t *b)
{
    b->data = NULL;
    b->len = 0;
    b->cap = 0;
    b->oom = false;
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
    if (b->oom)
        return false;
    if (n == 0)
        return true;
    if (b->len + n > b->cap && !sbuf_grow(b, n)) {
        b->oom = true;
        return false;
    }
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
    b->oom = false;
}

static int
chunk_width(const char *data, size_t len, const wcwidth_wrap_opts_t *opts)
{
    wcwidth_width_opts_t wopts = {.tabsize = opts->tabsize,
                                  .ambiguous_width = opts->ambiguous_width,
                                  .term_program = opts->term_program};
    int error = 0;
    int w;

    w = wcwidth_width_u8(data, len, opts->control_codes, &wopts, &error);
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
split_seqs(const char *text, size_t len, sbuf_t *visible, sbuf_t *escapes)
{
    size_t idx = 0;
    wcwidth_esc_result_t r;

    sbuf_init(visible);
    sbuf_init(escapes);
    while (idx < len) {
        if (text[idx] == ESC && wcwidth_escape_classify(text, len, idx, &r)) {
            sbuf_append(escapes, r.start, r.length);
            idx += r.length;
        }
        else {
            sbuf_append(visible, text + idx, 1);
            idx++;
        }
    }
}

static uint32_t
utf8_decode(const char *s, size_t len, size_t *seq_len)
{
    unsigned char c;
    uint32_t ucs;
    size_t sl;

    if (len == 0) {
        *seq_len = 1;
        return 0;
    }
    c = (unsigned char) s[0];

    if (c < 0x80) {
        *seq_len = 1;
        return c;
    }
    if ((c & 0xE0) == 0xC0) {
        sl = 2;
        ucs = (uint32_t) (c & 0x1F);
    }
    else if ((c & 0xF0) == 0xE0) {
        sl = 3;
        ucs = (uint32_t) (c & 0x0F);
    }
    else {
        sl = 4;
        ucs = (uint32_t) (c & 0x07);
    }
    if (sl > len)
        sl = len;
    {
        size_t k;
        for (k = 1; k < sl; k++)
            ucs = (ucs << 6) | ((unsigned char) s[k] & 0x3F);
    }
    *seq_len = sl;
    return ucs;
}

static bool
is_py_ws(uint32_t ucs)
{
    if (ucs == 0x20 || (ucs >= 0x09 && ucs <= 0x0D) || (ucs >= 0x1C && ucs <= 0x1F))
        return true;
    if (ucs == 0x85 || ucs == 0xA0 || ucs == 0x1680)
        return true;
    if (ucs >= 0x2000 && ucs <= 0x200A)
        return true;
    return ucs == 0x2028 || ucs == 0x2029 || ucs == 0x202F || ucs == 0x205F || ucs == 0x3000;
}

static size_t
lstrip_len(const char *s, size_t len)
{
    size_t i = 0;
    while (i < len) {
        size_t sl;
        if (!is_py_ws(utf8_decode(s + i, len - i, &sl)))
            break;
        i += sl;
    }
    return i;
}

static size_t
rstrip_len(const char *s, size_t len)
{
    while (len > 0) {
        size_t start = len;
        while (start > 0 && ((unsigned char) s[start - 1] & 0xC0) == 0x80)
            start--;
        size_t sl;
        if (start == 0) {
            /*
             * The run of continuation bytes reaches the start of the buffer,
             * so there is no lead byte to decode.  Reading s[start - 1] here
             * would be s[-1]; a bare continuation byte is not whitespace, so
             * there is nothing left to strip.  Malformed UTF-8 reaches this
             * from any wrap_*() call on bytes read from a terminal or pipe.
             */
            break;
        }
        if (!is_py_ws(utf8_decode(s + start - 1, len - (start - 1), &sl)))
            break;
        len = start - 1;
    }
    return len;
}

static bool
is_all_ws(const char *data, size_t len)
{
    size_t i = 0;
    while (i < len) {
        size_t sl;
        if (!is_py_ws(utf8_decode(data + i, len - i, &sl)))
            return false;
        i += sl;
    }
    return true;
}

static bool
expand_tabs_to(const char *text, size_t len, int ts, sbuf_t *out)
{
    size_t col = 0, i;

    sbuf_init(out);
    for (i = 0; i < len; i++) {
        unsigned char b = (unsigned char) text[i];
        if (b == '\t' && ts > 0) {
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
            if (b == '\n' || b == '\r') {
                col = 0;
            }
            else if ((b & 0xC0) != 0x80) {
                col++;
            }
        }
    }
    return true;
}

static bool
replace_ws_to(const char *text, size_t len, bool unicode_breaks, sbuf_t *out)
{
    size_t i;
    sbuf_init(out);
    for (i = 0; i < len; i++) {
        unsigned char ch = (unsigned char) text[i];
        char c;
        if (unicode_breaks && ch == 0xC2 && i + 1 < len && (unsigned char) text[i + 1] == 0x85) {
            c = ' ';
            i++;
        }
        else if (unicode_breaks && ch == 0xE2 && i + 2 < len && (unsigned char) text[i + 1] == 0x80
                 && ((unsigned char) text[i + 2] == 0xA8 || (unsigned char) text[i + 2] == 0xA9)) {
            c = ' ';
            i += 2;
        }
        else {
            c = (ch == '\n' || ch == '\r' || ch == '\v' || ch == '\f' || ch == '\t') ? ' '
                                                                                     : (char) ch;
        }
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
    if (len > 0)
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

/* Space characters split into their own chunk, as the Python splitter and textwrap do. */
static bool
is_breaking_space(uint32_t cp)
{
    return cp == ' ' || cp == 0x1680 || (cp >= 0x2000 && cp <= 0x200A) || cp == 0x3000;
}

/*
 * Split processed text at UAX #14 break opportunities.
 *
 * Escape sequences are outside the break analysis and stay attached to the following character,
 * as in the ASCII splitter.  Mandatory breaks (LB4, LB5) become their own chunk so
 * _wrap_chunks() can flush the line.
 */
static bool
_split_uax14(const char *text, size_t len, chunklist_t *out, const wcwidth_wrap_opts_t *opts)
{
    uint32_t *cps = NULL;
    size_t *char_end = NULL;
    size_t *breaks = NULL;
    uint8_t *mandatory = NULL;
    size_t nvis = 0;
    size_t nbreaks;
    size_t i = 0;
    size_t b;
    bool ok = false;

    cps = malloc((len + 1) * sizeof(*cps));
    char_end = malloc((len + 1) * sizeof(*char_end));
    if (cps == NULL)
        goto done;
    if (char_end == NULL)
        goto done;

    while (i < len) {
        wcwidth_esc_result_t r;
        uint32_t cp;
        size_t slen;

        if (text[i] == ESC) {
            wcwidth_escape_classify(text, len, i, &r);
            i += r.length;
            continue;
        }
        cp = utf8_decode(text + i, len - i, &slen);
        i += slen;
        cps[nvis] = cp;
        char_end[nvis] = i;
        nvis++;
    }

    breaks = malloc((nvis + 1) * sizeof(*breaks));
    mandatory = malloc((nvis + 1) * sizeof(*mandatory));
    if (breaks == NULL)
        goto done;
    if (mandatory == NULL)
        goto done;
    nbreaks = wcwidth_linebreak_breaks_u32(cps, nvis, breaks, mandatory, nvis + 1,
                                           opts->break_on_hyphens);
    if (nbreaks == (size_t) -1)
        goto done;

    {
        size_t start = 0;
        for (b = 0; b < nbreaks; b++) {
            size_t k = breaks[b];
            size_t end;
            end = (b + 1 < nbreaks) ? char_end[k - 1] : len;
            if (mandatory[b]) {
                size_t marker = (k >= 2) ? char_end[k - 2] : start;
                if (cps[k - 1] == '\n' && k >= 2 && cps[k - 2] == '\r')
                    marker = (k >= 3) ? char_end[k - 3] : start;
                if (marker > start) {
                    if (!cl_push(out, text + start, marker - start))
                        goto done;
                }
                if (!cl_push(out, text + marker, end - marker))
                    goto done;
            }
            else {
                size_t split = k;
                while (split > 0 && is_breaking_space(cps[split - 1]))
                    split--;
                if (split > 0 && split < k) {
                    size_t split_byte = char_end[split - 1];
                    if (!cl_push(out, text + start, split_byte - start))
                        goto done;
                    if (!cl_push(out, text + split_byte, end - split_byte))
                        goto done;
                }
                else if (!cl_push(out, text + start, end - start)) {
                    goto done;
                }
            }
            start = end;
        }
        if (start < len) {
            if (!cl_push(out, text + start, len - start))
                goto done;
        }
    }
    ok = true;

done:
    free(cps);
    free(char_end);
    free(breaks);
    free(mandatory);
    return ok;
}

/*
 * Split processed text into word and whitespace chunks.  By this point the text is tab expanded
 * and whitespace replaced when those options are set.  WCWIDTH_LINE_BREAK_ASCII splits on ASCII
 * space; the default WCWIDTH_LINE_BREAK_UNICODE uses UAX #14 opportunities.  Escape sequences
 * stay attached to adjacent words, and consecutive spaces form one chunk.
 */
static bool
_split(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts, chunklist_t *out)
{
    sbuf_t proc;
    sbuf_t word;
    size_t i;

    cl_init(out);

    if (opts->expand_tabs) {
        if (!expand_tabs_to(text, text_len, opts->tabsize, &proc))
            return false;
    }
    else {
        sbuf_init(&proc);
        if (!sbuf_append(&proc, text, text_len))
            return false;
    }

    if (opts->replace_whitespace) {
        sbuf_t tmp;
        if (!replace_ws_to(proc.data, proc.len, opts->line_break == WCWIDTH_LINE_BREAK_UNICODE,
                           &tmp)) {
            sbuf_free(&proc);
            return false;
        }
        sbuf_free(&proc);
        proc = tmp;
    }

    if (opts->line_break == WCWIDTH_LINE_BREAK_UNICODE) {
        bool split_ok = _split_uax14(proc.data, proc.len, out, opts);
        sbuf_free(&proc);
        return split_ok;
    }

    sbuf_init(&word);
    i = 0;
    while (i < proc.len) {
        if (proc.data[i] == ' ') {
            if (word.len > 0) {
                cl_push(out, word.data, word.len);
                word.len = 0;
            }
            /* group consecutive spaces */
            {
                size_t sp_start = i;
                while (i < proc.len && proc.data[i] == ' ')
                    i++;
                cl_push(out, proc.data + sp_start, i - sp_start);
            }
        }
        else if (proc.data[i] == ESC) {
            wcwidth_esc_result_t r;
            if (wcwidth_escape_classify(proc.data, proc.len, i, &r)) {
                sbuf_append(&word, r.start, r.length);
                i += r.length;
            }
            else {
                sbuf_append(&word, proc.data + i, 1);
                i++;
            }
        }
        else {
            sbuf_append(&word, proc.data + i, 1);
            i++;
        }
    }
    if (word.len > 0)
        cl_push(out, word.data, word.len);

    sbuf_free(&word);
    sbuf_free(&proc);
    return true;
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
        size_t glen = 1;

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

/* Byte offset just after the last hyphen in text[:limit] that has text before it, or 0.  Escape
 * sequences are skipped, matching Python's _handle_long_word(). */
static size_t
find_hyphen_break(const char *text, size_t len, size_t limit)
{
    size_t idx = 0;
    size_t hyphen = 0;
    bool seen_text = false;
    wcwidth_esc_result_t r;

    while (idx < limit) {
        uint32_t cp;
        size_t slen;

        if (text[idx] == ESC) {
            wcwidth_escape_classify(text, len, idx, &r);
            idx += r.length;
            continue;
        }
        cp = utf8_decode(text + idx, len - idx, &slen);
        if (cp == '-') {
            if (seen_text)
                hyphen = idx + slen;
        }
        else {
            seen_text = true;
        }
        idx += slen;
    }
    return hyphen;
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
        size_t glen = 1;
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

    bp = find_break_pos(c->data, c->len, sp_left, opts);
    if (opts->break_on_hyphens) {
        size_t hyphen = find_hyphen_break(c->data, c->len, bp);
        if (hyphen > 0)
            bp = hyphen;
    }
    if (cur_line->count == 0 && (bp == 0 || (bp < c->len && chunk_width(c->data, bp, opts) == 0))) {
        bp = find_first_vis(c->data, c->len);
    }
    if (bp > c->len)
        bp = c->len;

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
    size_t *lens;
    size_t count;
    size_t cap;
} lines_t;

static void
lines_init(lines_t *ll)
{
    ll->data = NULL;
    ll->lens = NULL;
    ll->count = 0;
    ll->cap = 0;
}

static bool
lines_push(lines_t *ll, const char *s, size_t n)
{
    if (ll->count >= ll->cap) {
        size_t nc = ll->cap ? ll->cap * 2 : 16;
        char **nd = realloc(ll->data, nc * sizeof(char *));
        size_t *nl;

        if (nd == NULL)
            return false;
        ll->data = nd;
        nl = realloc(ll->lens, nc * sizeof(size_t));
        if (nl == NULL)
            return false;
        ll->lens = nl;
        ll->cap = nc;
    }
    ll->data[ll->count] = malloc(n + 1);
    if (ll->data[ll->count] == NULL)
        return false;
    if (n > 0)
        memcpy(ll->data[ll->count], s, n);
    ll->data[ll->count][n] = '\0';
    ll->lens[ll->count] = n;
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
    free(ll->lens);
    ll->data = NULL;
    ll->lens = NULL;
    ll->count = 0;
    ll->cap = 0;
}

static bool
is_mandatory_break_chunk(const chunk_t *c, const wcwidth_wrap_opts_t *opts)
{
    if (opts->line_break != WCWIDTH_LINE_BREAK_UNICODE)
        return false;
    if (c->len == 1
        && (c->data[0] == '\n' || c->data[0] == '\r' || c->data[0] == '\v' || c->data[0] == '\f'))
        return true;
    if (c->len == 2 && c->data[0] == '\r')
        return true;
    if (c->len == 2 && c->data[0] == '\xc2' && c->data[1] == '\x85')
        return true;
    if (c->len == 3 && c->data[0] == '\xe2' && c->data[1] == '\x80'
        && (c->data[2] == '\xa8' || c->data[2] == '\xa9'))
        return true;
    return false;
}

static int
_wrap_chunks(chunklist_t *chunks, const wcwidth_wrap_opts_t *opts, lines_t *lines)
{
    bool first = true;

    lines_init(lines);
    cl_reverse(chunks);

    if (opts->max_lines > 0) {
        const char *ind = (opts->max_lines > 1) ? opts->subsequent_indent : opts->initial_indent;
        size_t pl = lstrip_len(opts->placeholder, strlen(opts->placeholder));
        const char *ps = opts->placeholder + pl;
        if (str_width(ind, opts) + chunk_width(ps, strlen(ps), opts) > opts->width)
            return -2;
    }

    while (chunks->count > 0) {
        chunklist_t cur;
        int cur_w = 0;
        bool dropped_whitespace = false;
        const char *indent = first ? opts->initial_indent : opts->subsequent_indent;
        int indent_w = str_width(indent, opts);
        int line_w = opts->width - indent_w;

        while (chunks->count > 0 && is_mandatory_break_chunk(cl_last(chunks), opts))
            cl_pop(chunks);
        if (chunks->count == 0)
            break;

        cl_init(&cur);

        if (opts->drop_whitespace && lines->count > 0 && chunks->count > 0) {
            chunk_t *c = cl_last(chunks);
            sbuf_t st, sq;
            split_seqs(c->data, c->len, &st, &sq);
            bool ws = (st.len > 0 && is_all_ws(st.data, st.len));
            if (ws) {
                cl_pop(chunks);
                if (sq.len > 0 && chunks->count > 0)
                    cl_prepend_last(chunks, sq.data, sq.len);
            }
            sbuf_free(&st);
            sbuf_free(&sq);
        }

        while (chunks->count > 0) {
            chunk_t *c = cl_last(chunks);
            int cw;
            if (is_mandatory_break_chunk(c, opts))
                break;
            cw = chunk_width(c->data, c->len, opts);
            if (cur_w + cw <= line_w) {
                cl_move(chunks, &cur);
                cur_w += cw;
            }
            else {
                break;
            }
        }

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

        if (opts->drop_whitespace && cur.count > 0) {
            chunk_t *c = &cur.chunks[cur.count - 1];
            sbuf_t st, sq;
            split_seqs(c->data, c->len, &st, &sq);
            bool ws = (st.len > 0 && is_all_ws(st.data, st.len));
            if (ws) {
                dropped_whitespace = true;
                cur_w -= chunk_width(c->data, c->len, opts);
                cl_pop(&cur);
                if (sq.len > 0 && cur.count > 0)
                    cl_append_last(&cur, sq.data, sq.len);
                else if (sq.len > 0 && chunks->count > 0)
                    cl_prepend_last(chunks, sq.data, sq.len);
            }
            sbuf_free(&st);
            sbuf_free(&sq);
        }

        if (cur.count == 0) {
            cl_free(&cur);
            continue;
        }

        sbuf_t lc;
        {
            size_t ci;
            sbuf_init(&lc);
            for (ci = 0; ci < cur.count; ci++)
                sbuf_append(&lc, cur.chunks[ci].data, cur.chunks[ci].len);
        }

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
                if (opts->drop_whitespace) {
                    if (lc.len > 0 && memchr(lc.data, ESC, lc.len) != NULL) {
                        sbuf_t st, sq;
                        split_seqs(lc.data, lc.len, &st, &sq);
                        bool ws = (st.len > 0 && is_all_ws(st.data, st.len))
                                  || (st.len == 0 && dropped_whitespace);
                        if (ws && sq.len > 0 && chunks->count > 0)
                            cl_prepend_last(chunks, sq.data, sq.len);
                        sbuf_free(&st);
                        sbuf_free(&sq);
                        if (ws) {
                            sbuf_free(&lc);
                            cl_free(&cur);
                            continue;
                        }
                    }
                    lc.len = rstrip_len(lc.data, lc.len);
                    if (lc.data != NULL)
                        lc.data[lc.len] = '\0';
                    if (lc.len == 0) {
                        /*
                         * The line held only whitespace, which dropping has now emptied.  Skip
                         * it and leave `first` unchanged so initial_indent still applies to the
                         * first line with content, as stdlib textwrap and wcwidth.textwrap do.
                         */
                        sbuf_free(&lc);
                        cl_free(&cur);
                        continue;
                    }
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
                        size_t prl = lines->lens[lines->count - 1];
                        size_t cut = 0, i = 0;
                        wcwidth_esc_result_t er;
                        while (i < prl) {
                            if (pr[i] == ESC && wcwidth_escape_classify(pr, prl, i, &er)) {
                                i += er.length;
                                continue;
                            }
                            size_t seg_end = i;
                            while (seg_end < prl && pr[seg_end] != ESC)
                                seg_end++;
                            size_t vis_end = i + rstrip_len(pr + i, seg_end - i);
                            if (vis_end > i)
                                cut = vis_end;
                            i = seg_end;
                        }
                        sbuf_t prev;
                        sbuf_init(&prev);
                        sbuf_append(&prev, pr, cut);
                        i = cut;
                        while (i < prl) {
                            if (pr[i] == ESC && wcwidth_escape_classify(pr, prl, i, &er)) {
                                sbuf_append(&prev, pr + i, er.length);
                                i += er.length;
                            }
                            else {
                                i++;
                            }
                        }
                        bool fits = chunk_width(prev.data, prev.len, opts) + pw <= opts->width;
                        if (fits) {
                            char *np = malloc(prev.len + strlen(opts->placeholder) + 1);
                            if (np != NULL) {
                                memcpy(np, prev.data, prev.len);
                                strcpy(np + prev.len, opts->placeholder);
                                free(pr);
                                lines->data[lines->count - 1] = np;
                                lines->lens[lines->count - 1] =
                                    prev.len + strlen(opts->placeholder);
                                ok = true;
                            }
                        }
                        sbuf_free(&prev);
                    }
                    if (!ok) {
                        size_t pl = lstrip_len(opts->placeholder, strlen(opts->placeholder));
                        sbuf_t fl;
                        sbuf_init(&fl);
                        sbuf_append_str(&fl, indent);
                        sbuf_append(&fl, opts->placeholder + pl, strlen(opts->placeholder) - pl);
                        lines_push(lines, fl.data, fl.len);
                        sbuf_free(&fl);
                    }
                }

                sbuf_free(&lc);
                cl_free(&cur);
                break;
            }
        }

        sbuf_free(&lc);
        cl_free(&cur);
    }

    return 0;
}

static int
_emit_empty(char **out, size_t *out_len, size_t **offsets, size_t *offset_count)
{
    *out = malloc(1);
    if (*out == NULL)
        return -1;
    (*out)[0] = '\0';
    *out_len = 0;
    if (offsets != NULL) {
        *offsets = NULL;
        *offset_count = 0;
    }
    return 0;
}

static int
_wrap_to_buffer(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts, char **out,
                size_t *out_len, size_t **offsets, size_t *offset_count)
{
    chunklist_t chunks;
    lines_t lines;
    size_t total = 0;
    size_t i;
    int rc;

    *out = NULL;
    *out_len = 0;
    if (offsets != NULL) {
        *offsets = NULL;
        *offset_count = 0;
    }

    if (text_len == 0)
        return _emit_empty(out, out_len, offsets, offset_count);

    cl_init(&chunks);

    if (!_split(text, text_len, opts, &chunks))
        return -1;

    if (chunks.count == 0) {
        cl_free(&chunks);
        return _emit_empty(out, out_len, offsets, offset_count);
    }

    rc = _wrap_chunks(&chunks, opts, &lines);
    cl_free(&chunks);
    if (rc != 0)
        return rc;

    for (i = 0; i < lines.count; i++)
        total += lines.lens[i];
    if (lines.count > 1)
        total += lines.count - 1;

    *out = malloc(total + 1);
    if (*out == NULL) {
        lines_free(&lines);
        return -1;
    }
    if (offsets != NULL) {
        *offsets = malloc(lines.count * sizeof(size_t));
        if (*offsets == NULL) {
            free(*out);
            *out = NULL;
            lines_free(&lines);
            return -1;
        }
        *offset_count = lines.count;
    }

    {
        char *p = *out;
        for (i = 0; i < lines.count; i++) {
            if (offsets != NULL)
                (*offsets)[i] = (size_t) (p - *out);
            size_t n = lines.lens[i];
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

int
wcwidth_wrap_u8(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts, char **out,
                size_t *out_len)
{
    return _wrap_to_buffer(text, text_len, opts, out, out_len, NULL, NULL);
}

int
wcwidth_wrap_lines_u8(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts,
                      char **out, size_t *out_len, size_t **offsets, size_t *offset_count)
{
    return _wrap_to_buffer(text, text_len, opts, out, out_len, offsets, offset_count);
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
wcwidth_wrap_u8_text(const char *text, size_t text_len, const wcwidth_wrap_opts_t *opts, char **out,
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

            if (wcwidth_wrap_u8(p, seg_len, opts, &wrapped, &wrapped_len) != 0) {
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

    {
        size_t total = 0;
        for (i = 0; i < lines.count; i++)
            total += lines.lens[i];
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
                size_t n = lines.lens[i];
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

typedef int (*wrap_fn)(const char *, size_t, const wcwidth_wrap_opts_t *, char **, size_t *);

static int
wrap_u32_common(const uint32_t *codepoints, size_t n, const wcwidth_wrap_opts_t *opts,
                uint32_t **out, size_t *out_len, wrap_fn wrap)
{
    char enc_stack[512];
    size_t enc_len;
    char *utf8;
    int result;

    *out = NULL;
    *out_len = 0;

    utf8 = wcwidth_encode_u32(codepoints, n, enc_stack, sizeof(enc_stack), &enc_len);
    if (utf8 == NULL) {
        return -1;
    }
    {
        char *bytes = NULL;
        size_t byte_len = 0;
        uint32_t *decoded;

        result = wrap(utf8, enc_len, opts, &bytes, &byte_len);
        if (utf8 != enc_stack) {
            free(utf8);
        }
        if (result < 0) {
            free(bytes);
            return -1;
        }
        decoded = wcwidth_decode_u32_heap(bytes, byte_len, out_len);
        free(bytes);
        if (decoded == NULL) {
            return -1;
        }
        *out = decoded;
    }
    return 0;
}

int
wcwidth_wrap_u32(const uint32_t *codepoints, size_t n, const wcwidth_wrap_opts_t *opts,
                 uint32_t **out, size_t *out_len)
{
    return wrap_u32_common(codepoints, n, opts, out, out_len, wcwidth_wrap_u8);
}

int
wcwidth_wrap_u32_text(const uint32_t *codepoints, size_t n, const wcwidth_wrap_opts_t *opts,
                      uint32_t **out, size_t *out_len)
{
    return wrap_u32_common(codepoints, n, opts, out, out_len, wcwidth_wrap_u8_text);
}
