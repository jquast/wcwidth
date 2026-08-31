/*
 * width -- report display width of each line of UTF-8 text.
 *
 * Usage:
 *   width [-v|--verbose] [file]
 *
 * Reads UTF-8 text from file (or stdin), and for each line prints its
 * display width.  With -v, prefixes each line with "N:text" (no space
 * after colon).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "wcwidth/width.h"
#include "wcwidth/wcwidth_config.h"

static void
usage(const char *prog)
{
    fprintf(stderr,
            "Usage: %s [-v] [file]\n"
            "Report display width of each line of UTF-8 text.\n"
            "\n"
            "Options:\n"
            "  -v, --verbose  Prefix each line with \"N:text\"\n",
            prog);
}

/*
 * Read one line from fp into a caller-managed dynamic buffer.
 * Returns length (excluding newline), or 0 at EOF.  Strips trailing
 * CR and LF.
 */
static size_t
readline(FILE *fp, char **buf, size_t *cap)
{
    size_t len = 0;
    int c;

    while ((c = fgetc(fp)) != EOF && c != '\n') {
        if (c == '\r')
            continue;
        if (len + 1 >= *cap) {
            *cap = *cap ? *cap * 2 : 256;
            char *tmp = realloc(*buf, *cap);
            if (!tmp) {
                free(*buf);
                *buf = NULL;
                return 0;
            }
            *buf = tmp;
        }
        (*buf)[len++] = (char) c;
    }
    if (c == EOF && len == 0)
        return (size_t) -1; /* EOF */
    if (len + 1 < *cap)
        (*buf)[len] = '\0';
    return len;
}

int
main(int argc, char **argv)
{
    int verbose = 0;
    const char *file = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-v") == 0 || strcmp(argv[i], "--verbose") == 0) {
            verbose = 1;
        }
        else if (argv[i][0] != '-') {
            file = argv[i];
        }
        else {
            usage(argv[0]);
            return 2;
        }
    }

    FILE *fp = stdin;
    if (file) {
        fp = fopen(file, "rb");
        if (!fp) {
            perror(file);
            return 1;
        }
    }

    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    char *line = NULL;
    size_t cap = 0;

    while (1) {
        size_t len = readline(fp, &line, &cap);
        if (len == (size_t) -1) /* EOF */
            break;

        int w = width_u8(line, len, WCWIDTH_PARSE, &opts, NULL);
        if (w < 0)
            w = 0;

        if (verbose) {
            printf("%d:%.*s\n", w, (int) len, line);
        }
        else {
            printf("%d\n", w);
        }
    }

    free(line);
    if (file)
        fclose(fp);
    return 0;
}
