#ifndef TEST_COMMON_H
#define TEST_COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int _tests_run = 0;
static int _tests_failed = 0;
static const char *_current_test = NULL;

#define TEST(name)                                                                                 \
    static void test_##name(void);                                                                 \
    static void test_##name(void)

#define RUN_TEST(name)                                                                             \
    do {                                                                                           \
        _current_test = #name;                                                                     \
        _tests_run++;                                                                              \
        test_##name();                                                                             \
    } while (0)

#define FAIL(fmt, ...)                                                                             \
    do {                                                                                           \
        fprintf(stderr, "FAIL: %s:%d: " fmt "\n", __FILE__, __LINE__, ##__VA_ARGS__);              \
        _tests_failed++;                                                                           \
        return;                                                                                    \
    } while (0)

#define ASSERT_EQ(expected, actual)                                                                \
    do {                                                                                           \
        int64_t _e = (int64_t) (expected);                                                         \
        int64_t _a = (int64_t) (actual);                                                           \
        if (_e != _a) {                                                                            \
            FAIL("expected %ld, got %ld", (long) _e, (long) _a);                                   \
        }                                                                                          \
    } while (0)

#define ASSERT_STREQ(expected, actual)                                                             \
    do {                                                                                           \
        const char *_e = (expected);                                                               \
        const char *_a = (actual);                                                                 \
        if (strcmp(_e, _a) != 0) {                                                                 \
            FAIL("expected \"%s\", got \"%s\"", _e, _a);                                           \
        }                                                                                          \
    } while (0)

#define ASSERT_TRUE(expr)                                                                          \
    do {                                                                                           \
        if (!(expr)) {                                                                             \
            FAIL("expected true, got false: %s", #expr);                                           \
        }                                                                                          \
    } while (0)

#define ASSERT_FALSE(expr)                                                                         \
    do {                                                                                           \
        if (expr) {                                                                                \
            FAIL("expected false, got true: %s", #expr);                                           \
        }                                                                                          \
    } while (0)

#define ASSERT_NULL(ptr)                                                                           \
    do {                                                                                           \
        if ((ptr) != NULL) {                                                                       \
            FAIL("expected NULL, got %p", (void *) (ptr));                                         \
        }                                                                                          \
    } while (0)

#define ASSERT_NOT_NULL(ptr)                                                                       \
    do {                                                                                           \
        if ((ptr) == NULL) {                                                                       \
            FAIL("expected non-NULL");                                                             \
        }                                                                                          \
    } while (0)

static int
test_summary(void)
{
    printf("\n%d tests, %d failures\n", _tests_run, _tests_failed);
    return _tests_failed ? 1 : 0;
}

#endif /* TEST_COMMON_H */
