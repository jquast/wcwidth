#!/usr/bin/env python3
"""
This is a small script to make an inquiry into the version history of unicode
data tables as they apply to the wcwidth library.

This loads zero and wide tables and validate whether the values in any table, by
version, is found in every subsequent version.

If this program had zero results, then it would be very easy to compress table
size, but unfortunately there there appears to be a few missteps that would
require a more complex scheme for compressing table sizes.

Some examples,

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
def main():
    from wcwidth import ZERO_WIDTH, WIDE_EASTASIAN, list_versions, _bisearch
    reversed_uni_versions = list(reversed(list_versions()))
    tables = {'ZERO_WIDTH': ZERO_WIDTH,
              'WIDE_EASTASIAN': WIDE_EASTASIAN}
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
                    if not _bisearch(unichar_n, next_table):
                        print('value', hex(unichar_n), 'in table', table_name,
                                'version', version, 'is not defined in', next_version,
                                'from range',
                                (hex(start_range), hex(stop_range)))
                    if _bisearch(unichar_n, other_table):
                        print('value', hex(unichar_n), 'in table', table_name,
                                'version', version, 'duplicated in table', other_table_name,
                                'from range',
                                (hex(start_range), hex(stop_range)))



if __name__ == '__main__':
    main()
