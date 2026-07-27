/*
 * C port of the Python wcwidth library.
 *
 * Copyright (c) 2026 Jeff Quast <contact@jeffquast.com>
 * Licensed under the MIT License.
 */
#ifndef WCWIDTH_CONFIG_H
#define WCWIDTH_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

#define WCWIDTH_VERSION_MAJOR 0
#define WCWIDTH_VERSION_MINOR 1
#define WCWIDTH_VERSION_PATCH 0
#define WCWIDTH_VERSION "0.1.0"

/* Unicode version the library tables were generated from. */
#define WCWIDTH_UNICODE_VERSION "17.0.0"

/* Maximum number of bytes needed to decode a single UTF-8 codepoint. */
#define WCWIDTH_UTF8_MAX_BYTES 4

/* Return value indicating a non-printable control character. */
#define WCWIDTH_CTRL_WIDTH (-1)

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_CONFIG_H */
