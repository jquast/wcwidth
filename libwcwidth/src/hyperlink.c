/*
 * OSC 8 Hyperlink protocol parsing and creation.
 */
#include "wcwidth/hyperlink.h"

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdio.h>
#include <time.h>

#define ESC 0x1b
#define BEL 0x07

bool
wcwidth_hyperlink_parse_open(const char *seq, size_t seq_len, wcwidth_hyperlink_params_t *params)
{
    size_t semi_pos, url_start, url_end;
    size_t term_len;
    char term;

    /* Must start with ESC ] 8 ; (4 bytes) */
    if (seq_len < 6 || (unsigned char) seq[0] != ESC || seq[1] != ']' || seq[2] != '8'
        || seq[3] != ';') {
        return false;
    }

    /* Find the params/URL separator semicolon after the prefix. */
    semi_pos = 4;
    while (semi_pos < seq_len && seq[semi_pos] != ';') {
        semi_pos++;
    }
    if (semi_pos >= seq_len) {
        return false; /* no separator found */
    }

    /* Identify terminator at end of sequence. */
    if (seq_len >= 1 && (unsigned char) seq[seq_len - 1] == BEL) {
        term = BEL;
        term_len = 1;
    }
    else if (seq_len >= 2 && (unsigned char) seq[seq_len - 2] == ESC && seq[seq_len - 1] == '\\') {
        term = ESC; /* ST */
        term_len = 2;
    }
    else {
        return false;
    }

    /* URL runs from after the separator to the terminator. */
    url_start = semi_pos + 1;
    url_end = seq_len - term_len;

    if (url_start > url_end) {
        return false; /* no URL content */
    }

    params->params = seq + 4;
    params->params_len = semi_pos - 4;
    params->url = seq + url_start;
    params->url_len = url_end - url_start;
    params->terminator = term;
    return true;
}

size_t
wcwidth_hyperlink_make_open(const wcwidth_hyperlink_params_t *params, char *out, size_t out_cap)
{
    int rv;

    if (params->terminator == BEL) {
        rv = snprintf(out, out_cap, "\x1b]8;%.*s;%.*s%c", (int) params->params_len, params->params,
                      (int) params->url_len, params->url, BEL);
    }
    else {
        rv = snprintf(out, out_cap, "\x1b]8;%.*s;%.*s\x1b\\", (int) params->params_len,
                      params->params, (int) params->url_len, params->url);
    }
    return (size_t) rv;
}

size_t
wcwidth_hyperlink_make_close(char terminator, char *out, size_t out_cap)
{
    int rv;

    if (terminator == BEL) {
        rv = snprintf(out, out_cap, "\x1b]8;;\x07");
    }
    else {
        rv = snprintf(out, out_cap, "\x1b]8;;\x1b\\");
    }
    return (size_t) rv;
}

void
wcwidth_hyperlink_find_close(const char *text, size_t text_len, size_t search_start,
                             size_t *close_start, size_t *close_end)
{
    size_t i;

    for (i = search_start; i + 5 < text_len; i++) {
        if ((unsigned char) text[i] != ESC) {
            continue;
        }
        if (text[i + 1] != ']') {
            continue;
        }
        if (text[i + 2] != '8') {
            continue;
        }
        if (text[i + 3] != ';') {
            continue;
        }
        if (text[i + 4] != ';') {
            continue;
        }
        /* Found ESC ] 8 ; ; -- check terminator */
        if ((unsigned char) text[i + 5] == BEL) {
            *close_start = i;
            *close_end = i + 6;
            return;
        }
        if (i + 6 < text_len && (unsigned char) text[i + 5] == ESC && text[i + 6] == '\\') {
            *close_start = i;
            *close_end = i + 7;
            return;
        }
    }

    *close_start = (size_t) -1;
    *close_end = (size_t) -1;
}

/*
 * Trivial xorshift32 PRNG for non-cryptographic hyperlink id generation.
 * Seeded from time(2) on first call; output is eight hex characters.
 * Not thread-safe (shares a file-scope static seed).
 */
static uint32_t _hyperlink_id_seed;

void
wcwidth_hyperlink_next_id(char *out)
{
    static const char hex[] = "0123456789abcdef";
    uint32_t x;
    int i;

    if (_hyperlink_id_seed == 0) {
        _hyperlink_id_seed = (uint32_t) time(NULL);
    }

    /* xorshift32 */
    x = _hyperlink_id_seed;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    _hyperlink_id_seed = x;

    for (i = 0; i < 8; i++) {
        out[i] = hex[(x >> (28 - (unsigned) i * 4)) & 0xf];
    }
}
