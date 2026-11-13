#ifndef WCWIDTH_ASSERT_H
#define WCWIDTH_ASSERT_H

/*
 * WCWIDTH_ENABLE_ASSERTS is defined by the development and test builds
 *
 * the distributed builds (via python wheels) leave it undefined, so the checks are
 * compiled out, matching distributed python releases.
 */
#ifdef WCWIDTH_ENABLE_ASSERTS
void wcwidth_assert_fail(const char *expr, const char *file, int line);
#define WCWIDTH_ASSERT(cond) ((cond) ? (void) 0 : wcwidth_assert_fail(#cond, __FILE__, __LINE__))
#else
/*
 * A release build compiles the expression out.  The reference marks
 * assert-only variables as used.
 */
#define WCWIDTH_ASSERT(cond) ((void) (0 && (cond)))
#endif

#endif
