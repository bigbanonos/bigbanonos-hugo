#!/usr/bin/env python3
"""
fix_mojibake.py

Two cleanup passes across all canonical posts in content/:

1. Fix mojibake: UTF-8 characters that got double-decoded as Windows-1252.
   The classic â€ pattern (and friends).

2. Strip trailing comma-separated tag lines like:
       @100gecs, @skrillex, @charlixcx, @riconasty,
   These duplicate the YAML tags. The YAML is the source of truth.

Usage:
    python fix_mojibake.py            # dry run
    python fix_mojibake.py --write    # actually fix
"""
import re
import sys
from pathlib import Path

# common mojibake -> correct char mappings
# these are the patterns that show up when UTF-8 was decoded as cp1252
# then re-encoded as UTF-8.
MOJIBAKE = [
    ("â€¢", "•"),    # bullet
    ("â€“", "–"),    # en dash
    ("â€”", "—"),    # em dash
    ("â€˜", "'"),    # left single quote
    ("â€™", "'"),    # right single quote / apostrophe
    ("â€œ", '"'),    # left double quote
    ("â€\u009d", '"'),  # right double quote (rendered as â€<0x9d>)
    ("â€\x9d", '"'),    # alternate
    ("â€¦", "…"),    # ellipsis
    ("â€\xa6", "…"), # alternate ellipsis
    # the catch-all: a bare "â€" with a trailing space is almost always a stray bullet
    # this is the one we see most in 100 Gecs and Heart tracklists
    ("â€ ", "• "),
    # Â (encoded non-breaking space leftover) - usually safe to drop
    ("Â ", " "),
    ("Â", ""),
    # other common ones
    ("Ã©", "é"),
    ("Ã¨", "è"),
    ("Ã ", "à"),
    ("Ã¡", "á"),
    ("Ã­", "í"),
    ("Ã³", "ó"),
    ("Ã¼", "ü"),
    ("Ã±", "ñ"),
]

# pattern: a line at the end of body that's just `@artist1, @artist2, @artist3,` (with trailing comma)
# matches lines that are nothing but @-tags separated by commas
TRAILING_TAG_LINE_RE = re.compile(
    r'^\s*@[\w-]+(?:\s*,\s*@[\w-]+)*\s*,?\s*$',
    re.MULTILINE
)

def parse_front_matter(text):
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 4)
    if end == -1:
        return "", text
    return text[:end+4], text[end+4:].lstrip("\n")

def fix_mojibake(text):
    """Apply all mojibake replacements. Returns (new_text, count_of_replacements)."""
    count = 0
    for bad, good in MOJIBAKE:
        if bad in text:
            count += text.count(bad)
            text = text.replace(bad, good)
    return text, count

def strip_trailing_tag_line(body):
    """Remove standalone @tag,@tag,@tag lines from the body. Returns (new_body, count)."""
    count = 0
    lines = body.splitlines()
    new_lines = []
    for line in lines:
        if TRAILING_TAG_LINE_RE.match(line):
            count += 1
            continue
        new_lines.append(line)
    return "\n".join(new_lines), count

def main():
    write = "--write" in sys.argv

    files = []
    for p in Path("content").rglob("*.md"):
        if "_legacy_dupes" in p.parts:
            continue
        files.append(p)

    print(f"Scanning {len(files)} canonical post files...")

    files_with_mojibake = 0
    total_mojibake_fixes = 0
    files_with_tag_lines = 0
    total_tag_lines_removed = 0
    files_changed = 0

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")

        # mojibake on the whole file (yaml + body)
        new_text, moji_count = fix_mojibake(text)

        # tag-line strip on the body only (don't touch YAML)
        fm, body = parse_front_matter(new_text)
        new_body, tag_count = strip_trailing_tag_line(body)
        # collapse 3+ blank lines
        new_body = re.sub(r"\n{3,}", "\n\n", new_body)
        new_text = fm + "\n\n" + new_body.strip() + "\n"

        if moji_count > 0:
            files_with_mojibake += 1
            total_mojibake_fixes += moji_count
        if tag_count > 0:
            files_with_tag_lines += 1
            total_tag_lines_removed += tag_count

        if new_text != text:
            files_changed += 1
            if write:
                path.write_text(new_text, encoding="utf-8")

    mode = "WRITTEN" if write else "DRY RUN"
    print(f"\n=== {mode} ===")
    print(f"  Files scanned:                 {len(files)}")
    print(f"  Files changed:                 {files_changed}")
    print(f"  Files with mojibake:           {files_with_mojibake}")
    print(f"  Total mojibake chars fixed:    {total_mojibake_fixes}")
    print(f"  Files with trailing tag lines: {files_with_tag_lines}")
    print(f"  Total tag lines removed:       {total_tag_lines_removed}")

    if not write:
        print("\nDry run only. To actually fix:")
        print("  python fix_mojibake.py --write")

if __name__ == "__main__":
    main()
