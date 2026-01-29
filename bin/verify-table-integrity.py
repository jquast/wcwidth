#!/usr/bin/env python3
"""
.. deprecated:: 0.5.0

This file depends on a previous version of wcwidth API that offered multiple versions of each
unicode table. It is just useful for investigative purposes and kept for the discoveries marked
below.

This is a small script to make an inquiry into the version history of unicode data tables, and to
validate conflicts in the tables as they are published:

- check for individual code point definitions change in in subsequent releases,
  these should be considered before attempting to reduce the size of our versioned
  tables without a careful incremental change description.  Each "violation" is
  logged as INFO.
- check that a codepoint in the 'zero' table is not present in the 'wide' table
  and vice versa. This is logged as ERROR and causes program to exit 1.

Some examples of the first kind,

1.

    value 0x1f93b in table WIDE_EASTASIAN version 12.1.0 is not defined in 13.0.0 from range ('0x1f90d', '0x1f971')
    value 0x1f946 in table WIDE_EASTASIAN version 12.1.0 is not defined in 13.0.0 from range ('0x1f90d', '0x1f971')

two characters were changed from 'W' to 'N':

    -EastAsianWidth-12.0.0.txt:1F90D..1F971;W   # So   [101] WHITE HEART..YAWNING FACE
    +EastAsianWidth-12.1.0.txt:1F90C..1F93A;W   # So    [47] PINCHED FINGERS..FENCER
    +EastAsianWidth-12.1.0.txt:1F93B;N          # So         MODERN PENTATHLON
    +EastAsianWidth-12.1.0.txt:1F93C..1F945;W   # So    [10] WRESTLERS..GOAL NET
    +EastAsianWidth-12.1.0.txt:1F946;N          # So         RIFLE
    +EastAsianWidth-12.1.0.txt:1F947..1F978;W   # So    [50] FIRST PLACE MEDAL..DISGUISED FACE

As well as for output,

    value 0x11a3 in table WIDE_EASTASIAN version 6.1.0 is not defined in 6.2.0 from range ('0x11a3', '0x11a7')
    ...
    value 0x11fe in table WIDE_EASTASIAN version 6.1.0 is not defined in 6.2.0 from range ('0x11fa', '0x11ff')

Category code was changed from 'W' to 'N':

    -EastAsianWidth-6.1.0.txt:11A3;W # HANGUL JUNGSEONG A-EU
    +EastAsianWidth-6.2.0.txt:11A3;N # HANGUL JUNGSEONG A-EU

2.

    value 0x1cf2 in table ZERO_WIDTH version 11.0.0 is not defined in 12.0.0 from range ('0x1cf2', '0x1cf4')
    value 0x1cf3 in table ZERO_WIDTH version 11.0.0 is not defined in 12.0.0 from range ('0x1cf2', '0x1cf4')

Category code was changed from 'Mc' to 'Lo':

    -DerivedGeneralCategory-11.0.0.txt:1CF2..1CF3    ; Mc #   [2] VEDIC SIGN ARDHAVISARGA..VEDIC SIGN ROTATED ARDHAVISARGA
    +DerivedGeneralCategory-12.0.0.txt:1CEE..1CF3    ; Lo #   [6] VEDIC SIGN HEXIFORM LONG ANUSVARA..VEDIC SIGN ROTATED ARDHAVISARGA

As well as for output,

     value 0x19b0 in table ZERO_WIDTH version 7.0.0 is not defined in 8.0.0 from range ('0x19b0', '0x19c0')
     ...
     value 0x19c8 in table ZERO_WIDTH version 7.0.0 is not defined in 8.0.0 from range ('0x19c8', '0x19c9')

Category code was changed from 'Mc' to 'Lo':

    -DerivedGeneralCategory-7.0.0.txt:19B0..19C0    ; Mc #  [17] NEW TAI LUE VOWEL SIGN VOWEL SHORTENER..NEW TAI LUE VOWEL SIGN IY
    +DerivedGeneralCategory-8.0.0.txt:19B0..19C9    ; Lo #  [26] NEW TAI LUE VOWEL SIGN VOWEL SHORTENER..NEW TAI LUE TONE MARK-2

"""
# std imports
import logging


def bisearch_pair(ucs, table):
    """A copy of wcwidth._bisearch() but also returns the range of matched values."""
    lbound = 0
    ubound = len(table) - 1

    if ucs < table[0][0] or ucs > table[ubound][1]:
        return (0, None, None)
    while ubound >= lbound:
        mid = (lbound + ubound) // 2
        if ucs > table[mid][1]:
            lbound = mid + 1
        elif ucs < table[mid][0]:
            ubound = mid - 1
        else:
            return (1, table[mid][0], table[mid][1])

    return (0, None, None)


def main(log: logging.Logger):
    # local
    from wcwidth import ZERO_WIDTH, WIDE_EASTASIAN, list_versions

    reversed_uni_versions = list(reversed(list_versions()))
    tables = {'ZERO_WIDTH': ZERO_WIDTH,
              'WIDE_EASTASIAN': WIDE_EASTASIAN}
    errors = 0
    for idx, version in enumerate(reversed_uni_versions):
        if idx == 0:
            continue
        next_version = reversed_uni_versions[idx - 1]
        for table_name, table in tables.items():
            next_table = table[next_version]
            curr_table = table[version]
            other_table_name = 'WIDE_EASTASIAN' if table_name == 'ZERO_WIDTH' else 'ZERO_WIDTH'
            other_table = tables[other_table_name][version]
            for start_range, stop_range in curr_table:
                for unichar_n in range(start_range, stop_range):
                    result, _, _ = bisearch_pair(unichar_n, next_table)
                    if not result:
                        log.info(
                            f'value 0x{unichar_n:05x} in table_name={table_name}'
                            f' version={version} is not defined in next_version={next_version}'
                            f' from inclusive range {hex(start_range)}-{hex(stop_range)}'
                        )
                    result, lbound, ubound = bisearch_pair(unichar_n, other_table)
                    if result:
                        log.error(
                            f'value 0x{unichar_n:05x} in table_name={table_name}'
                            f' version={version} is duplicated in other_table_name={other_table_name}'
                            f' from inclusive range 0x{start_range:05x}-0x{stop_range:05x} of'
                            f' {table_name} against 0x{lbound:05x}-0x{ubound:05x} in {other_table_name}'
                        )
                        errors += 1
    if errors:
        log.error(f'{errors} errors, exit 1')
        exit(1)


if __name__ == '__main__':
    _logfmt = '%(levelname)s %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(level="INFO", format=_logfmt, force=True)
    log = logging.getLogger()
    main(log)
