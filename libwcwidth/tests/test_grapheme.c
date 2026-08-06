#include "test_common.h"
#include "wcwidth/grapheme.h"
#include <string.h>

/* e + combining acute = e\u0301 */
#define STR_E_ACUTE "e\xcc\x81"

/* CRLF */
#define STR_CRLF "\x0d\x0a"

/* Hangul LV: U+1100 U+1161 */
#define STR_HANGUL_LV "\xe1\x84\x80\xe1\x85\xa1"

/* Flag US: U+1F1FA U+1F1F8 */
#define STR_FLAG_US "\xf0\x9f\x87\xba\xf0\x9f\x87\xb8"

/* Family: U+1F468 U+200D U+1F469 U+200D U+1F467 */
#define STR_FAMILY                                                                                 \
    "\xf0\x9f\x91\xa8\xe2\x80\x8d\xf0\x9f\x91\xa9"                                                 \
    "\xe2\x80\x8d\xf0\x9f\x91\xa7"

/* Wave + skin tone: U+1F44B U+1F3FB */
#define STR_WAVE_SKIN "\xf0\x9f\x91\x8b\xf0\x9f\x8f\xbb"

static int
count_clusters(const char *text)
{
    size_t len = strlen(text);
    wcwidth_grapheme_iter_t *iter = wcwidth_grapheme_iter_new(text, len);
    int count = 0;
    size_t clen;

    if (iter == NULL) {
        return -1;
    }
    while (wcwidth_grapheme_next(iter, &clen) != NULL) {
        count++;
    }
    wcwidth_grapheme_iter_free(iter);
    return count;
}

TEST(iterator_basic)
{
    /* exercises wcwidth_grapheme_iter_new / next / free */
    ASSERT_EQ(3, count_clusters("abc"));
    ASSERT_EQ(2, count_clusters("c" STR_E_ACUTE));
    ASSERT_EQ(1, count_clusters(STR_CRLF));
    ASSERT_EQ(1, count_clusters(STR_HANGUL_LV));
    ASSERT_EQ(1, count_clusters(STR_FLAG_US));
    ASSERT_EQ(1, count_clusters(STR_FAMILY));
    ASSERT_EQ(1, count_clusters(STR_WAVE_SKIN));
}

TEST(iterator_null_handling)
{
    size_t clen;
    wcwidth_grapheme_iter_t *iter = wcwidth_grapheme_iter_new("", 0);

    ASSERT_NOT_NULL(iter);
    ASSERT_NULL(wcwidth_grapheme_next(iter, &clen));
    wcwidth_grapheme_iter_free(iter);
    wcwidth_grapheme_iter_free(NULL);
    ASSERT_NULL(wcwidth_grapheme_next(NULL, &clen));
}

TEST(boundary_before_basic)
{
    char text[] = "cafe" STR_E_ACUTE; /* 7 bytes: e+acute cluster at 4 */
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_before("abc", 3, 3));
    ASSERT_EQ((int64_t) 4, (int64_t) wcwidth_grapheme_boundary_before(text, 7, 7));
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before("", 0, 0));
}

int
main(void)
{
    RUN_TEST(iterator_basic);
    RUN_TEST(iterator_null_handling);
    RUN_TEST(boundary_before_basic);
    return test_summary();
}
