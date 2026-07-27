/*
 * OSC 66 Text Sizing protocol parsing and measurement.
 *
 * Port of wcwidth/text_sizing.py.
 */
#include "wcwidth/text_sizing.h"
#include "wcwidth/wcwidth.h"

#include <stdlib.h>
#include <string.h>

/*
 * Field descriptor: maps a single-character key to its metadata.
 */
typedef struct
{
    char key;
    const char *name;
    int low;
    int high;
    int default_val;
} ts_field_t;

static const ts_field_t TS_FIELDS[] = {
    {'s', "scale", 1, 7, 1},          {'w', "width", 0, 7, 0},
    {'n', "numerator", 0, 15, 0},     {'d', "denominator", 0, 15, 0},
    {'v', "vertical_align", 0, 2, 0}, {'h', "horizontal_align", 0, 2, 0},
};

#define TS_NFIELDS (sizeof(TS_FIELDS) / sizeof(TS_FIELDS[0]))

static const ts_field_t *
ts_field_lookup(char key)
{
    size_t i;
    for (i = 0; i < TS_NFIELDS; ++i) {
        if (TS_FIELDS[i].key == key) {
            return &TS_FIELDS[i];
        }
    }
    return NULL;
}

bool
wcwidth_ts_parse_params(const char *meta, size_t meta_len, wcwidth_ts_params_t *params)
{
    size_t pos, part_start;
    const ts_field_t *field;
    char *endp;
    long val;

    /* Set defaults. */
    params->scale = 1;
    params->width = 0;
    params->numerator = 0;
    params->denominator = 0;
    params->vertical_align = 0;
    params->horizontal_align = 0;

    if (meta_len == 0) {
        return true;
    }

    part_start = 0;
    for (pos = 0; pos <= meta_len; ++pos) {
        if (pos < meta_len && meta[pos] != ':') {
            continue;
        }

        /* Process part [part_start, pos). */
        if (pos > part_start) {
            const char *part = meta + part_start;
            size_t part_len = pos - part_start;
            const char *eq = memchr(part, '=', part_len);

            if (eq == NULL) {
                /* No '=' -- skip this part (ignore in parse mode). */
                part_start = pos + 1;
                continue;
            }

            /* Look up field by single-char key. */
            field = ts_field_lookup(part[0]);
            if (field == NULL) {
                /* Unknown field -- ignore. */
                part_start = pos + 1;
                continue;
            }

            /* Parse integer value. */
            val = strtol(eq + 1, &endp, 10);
            if (endp == eq + 1 || *endp != '\0') {
                /* Not a valid integer -- use default. */
                part_start = pos + 1;
                continue;
            }

            /* Clamp to valid range. */
            if (val < field->low) {
                val = field->low;
            }
            else if (val > field->high) {
                val = field->high;
            }

            /* Assign to the correct struct field. */
            switch (field->key) {
                case 's':
                    params->scale = (int) val;
                    break;
                case 'w':
                    params->width = (int) val;
                    break;
                case 'n':
                    params->numerator = (int) val;
                    break;
                case 'd':
                    params->denominator = (int) val;
                    break;
                case 'v':
                    params->vertical_align = (int) val;
                    break;
                case 'h':
                    params->horizontal_align = (int) val;
                    break;
            }
        }

        part_start = pos + 1;
    }

    return true;
}

int
wcwidth_ts_display_width(const wcwidth_text_sizing_t *ts, int ambiguous_width)
{
    int text_width;

    if (ts->params.width > 0) {
        return ts->params.scale * ts->params.width;
    }

    text_width = wcswidth_u8(ts->text, ts->text_len, ambiguous_width);
    if (text_width < 0) {
        text_width = 0;
    }

    return ts->params.scale * text_width;
}
