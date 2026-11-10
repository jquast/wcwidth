#include "test_common.h"
#include "wcwidth/terminal_override.h"
#include <string.h>

TEST(resolve_terminal_names)
{
    char long_name[300];

    ASSERT_NOT_NULL(wcwidth_resolve_terminal("kitty"));
    ASSERT_NOT_NULL(wcwidth_resolve_terminal("  KiTtY  "));
    ASSERT_NOT_NULL(wcwidth_resolve_terminal("alacritty"));
    ASSERT_NULL(wcwidth_resolve_terminal("not-a-terminal"));
    ASSERT_NULL(wcwidth_resolve_terminal(""));
    ASSERT_NULL(wcwidth_resolve_terminal(NULL));

    memset(long_name, 'x', sizeof(long_name) - 1);
    long_name[sizeof(long_name) - 1] = '\0';
    ASSERT_NULL(wcwidth_resolve_terminal(long_name));
}

TEST(scan_zwj_cluster_end_u8)
{
    static const char base_extend[] = "a\xcc\x81";
    static const char base_extend_other[] = "a\xcc\x81"
                                            "b";
    static const char chain[] = "a\xe2\x80\x8d\xf0\x9f\x91\xa8\xcc\x81";

    ASSERT_EQ(3, wcwidth_scan_zwj_cluster_end_u8(base_extend, 3, 0));
    ASSERT_EQ(3, wcwidth_scan_zwj_cluster_end_u8(base_extend_other, 4, 0));
    ASSERT_EQ(sizeof(chain) - 1, wcwidth_scan_zwj_cluster_end_u8(chain, sizeof(chain) - 1, 0));
}

int
main(void)
{
    RUN_TEST(resolve_terminal_names);
    RUN_TEST(scan_zwj_cluster_end_u8);
    return test_summary();
}
