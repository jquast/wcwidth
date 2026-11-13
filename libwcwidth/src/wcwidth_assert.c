#include "wcwidth_assert.h"

#ifdef WCWIDTH_ENABLE_ASSERTS
#include <stdio.h>
#include <stdlib.h>

/*
 * Reached only when an assertion fails, considered "unreachable", excluded by coverage.
 */
/* GCOVR_EXCL_START */
void
wcwidth_assert_fail(const char *expr, const char *file, int line)
{
    fprintf(stderr, "wcwidth: assertion failed: %s at %s:%d\n", expr, file, line);
    fflush(stderr);
    abort();
}
/* GCOVR_EXCL_STOP */
#endif
