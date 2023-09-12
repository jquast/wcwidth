import os
import sys
import subprocess

import importlib
update_tables = importlib.import_module("update-tables")


def to_aria2(url, dir, fname):
    return "\n".join((
        url,
        f"  dir={dir}",
        f"  out={fname}",
    ))


def run_aria2(path, args):
    cmd = ["aria2c", *args, "-i", path]
    print(f"Run: {cmd}")
    return subprocess.run(cmd)


def main():
    versions = update_tables.get_unicode_versions()
    aria2_txt_list = []
    aria2_txt_path = os.path.join(update_tables.PATH_DATA, "aria2input.txt")

    for version in versions:
        url = f"https://www.unicode.org/Public/{version}/ucd/EastAsianWidth.txt"
        fname = f"EastAsianWidth-{version}.txt"
        aria2_txt_list.append(to_aria2(url, update_tables.PATH_DATA, fname))

    for version in versions:
        url = f"https://www.unicode.org/Public/{version}/ucd/extracted/DerivedGeneralCategory.txt"
        fname = f"DerivedGeneralCategory-{version}.txt"
        aria2_txt_list.append(to_aria2(url, update_tables.PATH_DATA, fname))

    with open(aria2_txt_path, "w", encoding="utf-8") as f:
        for item in aria2_txt_list:
            f.write(item)
            f.write("\n\n")

    if len(sys.argv) > 1 and sys.argv[1] == "run":
        ret = run_aria2(aria2_txt_path, sys.argv[2:]).returncode
        sys.exit(ret)


if __name__ == "__main__":
    main()
