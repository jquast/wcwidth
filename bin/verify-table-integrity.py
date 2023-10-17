#!/usr/bin/env python3
"""
This loads all tables and their versions, from wcwidth 0.2.8, and
validates whether the values in any table, by version, is found in
every table of susbsequent versions.

If this program succeeded without error, then it would be very easy to compress
table size and possibly see some increase in performance. Unfortunately there
appears to be a few missteps.

For example, in the first two lines of output

> value 0x1f93b in table WIDE_EASTASIAN version 12.1.0 is not defined in 13.0.0 from range ('0x1f90d', '0x1f971')
> value 0x1f946 in table WIDE_EASTASIAN version 12.1.0 is not defined in 13.0.0 from range ('0x1f90d', '0x1f971')

This is because EastAsianWidth-12.1.0.txt contains:

> 1F90D..1F971;W   # So   [101] WHITE HEART..YAWNING FACE

And EastAsianWidth-12.1.0.txt contains:

> 1F90C..1F93A;W   # So    [47] PINCHED FINGERS..FENCER
> 1F93B;N          # So         MODERN PENTATHLON
> 1F93C..1F945;W   # So    [10] WRESTLERS..GOAL NET
> 1F946;N          # So         RIFLE
> 1F947..1F978;W   # So    [50] FIRST PLACE MEDAL..DISGUISED FACE

Effectively punching two "holes" while extending the range of these wide emoji character sets.
"""

def main():
    from wcwidth import ZERO_WIDTH, WIDE_EASTASIAN, list_versions, _bisearch
    reversed_uni_versions = list(reversed(list_versions()))
    for idx, version in enumerate(reversed_uni_versions):
        if idx == 0:
            continue
        next_version = reversed_uni_versions[idx - 1]
        for table, table_name in ((ZERO_WIDTH, 'ZERO_WIDTH'),
                (WIDE_EASTASIAN, 'WIDE_EASTASIAN'),):
            next_table = table[next_version]
            curr_table = table[version]
            for start_range, stop_range in curr_table:
                for unichar_n in range(start_range, stop_range):
                    if not _bisearch(unichar_n, next_table):
                        print('value', hex(unichar_n), 'in table', table_name,
                                'version', version, 'is not defined in', next_version,
                                'from range',
                                (hex(start_range), hex(stop_range)))


if __name__ == '__main__':
    main()
