/*
 * textwrap -- wrap UTF-8 text to a given display width.
 *
 * Usage:
 *   textwrap [-v] [width] [file]
 *
 * Reads UTF-8 text from file (or stdin), wraps it to width columns
 * (default $COLUMNS or 80), and writes to stdout.
 *
 * Options:
 *   -v, --verbose    Visualize line breaks: append a red carriage-return
 *                    arrow (U+21A9) to each wrapped line. Uses width-1
 *                    to account for the marker.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "wcwidth/textwrap.h"
#include "wcwidth/wcwidth_config.h"

#define DEFAULT_WIDTH 80

static void
usage(const char *prog)
{
    fprintf(stderr,
            "Usage: %s [-v] [width] [file]\n"
            "Wrap UTF-8 text to a given display width.\n"
            "\n"
            "Options:\n"
            "  -v, --verbose  Append a red carriage-return marker to each line\n"
            "                 and reduce width by 1 to accommodate it.\n",
            prog);
}

/*
 * Read entire file (or stdin) into a malloc'd buffer.
 * Returns NULL on error.
 */
static char *
slurp(FILE *fp, size_t *out_len)
{
    size_t cap = 4096;
    size_t len = 0;
    char *buf = malloc(cap);
    if (!buf)
        return NULL;

    while (1) {
        size_t n = fread(buf + len, 1, cap - len, fp);
        len += n;
        if (n == 0)
            break;
        if (len == cap) {
            cap *= 2;
            char *tmp = realloc(buf, cap);
            if (!tmp) {
                free(buf);
                return NULL;
            }
            buf = tmp;
        }
    }
    *out_len = len;
    return buf;
}

int
main(int argc, char **argv)
{
    int verbose = 0;
    int width = 0;
    const char *file = NULL;

    /* Parse arguments */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-v") == 0 || strcmp(argv[i], "--verbose") == 0) {
            verbose = 1;
        }
        else if (argv[i][0] != '-') {
            /* First non-flag: try as width, then as file */
            char *endp = NULL;
            long w = strtol(argv[i], &endp, 10);
            if (endp && *endp == '\0' && w > 0) {
                width = (int) w;
            }
            else if (!file) {
                file = argv[i];
            }
        }
        else {
            usage(argv[0]);
            return 2;
        }
    }

    /* Default width from COLUMNS env, or 80 */
    if (width <= 0) {
        const char *cols = getenv("COLUMNS");
        width = cols ? (int) strtol(cols, NULL, 10) : DEFAULT_WIDTH;
        if (width <= 0)
            width = DEFAULT_WIDTH;
    }

    /* Read input */
    FILE *fp = stdin;
    if (file) {
        fp = fopen(file, "rb");
        if (!fp) {
            perror(file);
            return 1;
        }
    }

    size_t text_len = 0;
    char *text = slurp(fp, &text_len);
    if (file)
        fclose(fp);
    if (!text) {
        fprintf(stderr, "textwrap: out of memory\n");
        return 1;
    }
    if (text_len == 0) {
        free(text);
        return 0;
    }

    /* Configure wrapper */
    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = verbose ? width - 1 : width;
    opts.expand_tabs = 1;
    opts.replace_whitespace = 1;

    /* Wrap, preserving paragraph breaks */
    char *out = NULL;
    size_t out_len = 0;
    if (wrap_u8_text(text, text_len, &opts, &out, &out_len) != 0) {
        free(text);
        fprintf(stderr, "textwrap: wrapping failed\n");
        return 1;
    }
    free(text);

    /* Output */
    if (verbose) {
        const char *marker = "\x1b[31m"
                             "\xe2\x86\xa9" /* U+21A9 LEFTWARDS ARROW WITH HOOK */
                             "\x1b[0m";

        /* Replace '\n' separators with marker + '\n' */
        const char *p = out;
        const char *end = out + out_len;
        while (p < end) {
            const char *nl = memchr(p, '\n', (size_t) (end - p));
            if (!nl)
                nl = end;
            fwrite(p, 1, (size_t) (nl - p), stdout);
            if (nl < end) {
                fputs(marker, stdout);
                putchar('\n');
                p = nl + 1;
            }
            else {
                p = nl;
            }
        }
    }
    else {
        fwrite(out, 1, out_len, stdout);
        putchar('\n');
    }

    free(out);
    return 0;
}
