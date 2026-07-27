/*
 * align -- demonstrate left/right/center alignment of UTF-8 text.
 *
 * Usage:
 *   align [width]
 *
 * Reads lines from stdin and prints three-column output showing
 * ljust, rjust, and center alignment at the given width
 * (default $COLUMNS or 80).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "wcwidth/align.h"
#include "wcwidth/width.h"
#include "wcwidth/wcwidth_config.h"

static void
usage(const char *prog)
{
    fprintf(stderr,
            "Usage: %s [width]\n"
            "Demonstrate ljust, rjust, center on stdin lines.\n",
            prog);
}

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
        return 0;
    return len;
}

int
main(int argc, char **argv)
{
    int width = 0;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            usage(argv[0]);
            return 0;
        }
        char *endp = NULL;
        long w = strtol(argv[i], &endp, 10);
        if (endp && *endp == '\0' && w > 0) {
            width = (int) w;
        }
        else {
            usage(argv[0]);
            return 2;
        }
    }

    if (width <= 0) {
        const char *cols = getenv("COLUMNS");
        width = cols ? (int) strtol(cols, NULL, 10) : 80;
        if (width <= 0)
            width = 80;
    }

    char *line = NULL;
    size_t cap = 0;

    while (1) {
        size_t len = readline(stdin, &line, &cap);
        if (len == 0)
            break;

        char *lj = ljust_u8(line, len, (size_t) width, ' ', WCWIDTH_PARSE, 1, NULL, NULL);
        char *rj = rjust_u8(line, len, (size_t) width, ' ', WCWIDTH_PARSE, 1, NULL, NULL);
        char *ct = center_u8(line, len, (size_t) width, ' ', WCWIDTH_PARSE, 1, NULL, NULL);

        printf("%s  %s  %s\n", lj ? lj : "", rj ? rj : "", ct ? ct : "");

        free(lj);
        free(rj);
        free(ct);
    }

    free(line);
    return 0;
}
