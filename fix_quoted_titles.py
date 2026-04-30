#!/usr/bin/env python3
"""
fix_quoted_titles.py

Find all canonical .md files where YAML title has unescaped inner double-quotes:
    title: ""Weird Al" Yankovic"
    title: ""Bobby "Blue" Bland""

Rewrite as:
    title: "Weird Al Yankovic"     (drop the inner quotes — simplest, valid YAML)
    title: "Bobby Blue Bland"

Walks content/ and content/posts/ but skips _legacy_dupes/.

Usage:
    python fix_quoted_titles.py            # dry run
    python fix_quoted_titles.py --write    # do it
"""
import re
import sys
from pathlib import Path

def main():
    write = "--write" in sys.argv

    files_to_fix = []
    for d in [Path("content"), Path("content/posts")]:
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            if "_legacy_dupes" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            if not text.startswith("---"):
                continue
            # find lines like:  title: ""ANYTHING"
            # the pattern is: title: " followed by another " (unescaped)
            m = re.search(r'^title:\s*"([^"\n]*?)"([^"\n]+)"([^"\n]*)"\s*$',
                          text, flags=re.MULTILINE)
            if m:
                files_to_fix.append((p, m.group(0)))

    print(f"Found {len(files_to_fix)} files with broken quoted titles")
    for p, original in files_to_fix:
        print(f"  {p}")
        print(f"      old: {original}")

    if not files_to_fix:
        print("Nothing to fix.")
        return

    if not write:
        print("\nDry run only. To actually fix:")
        print("  python fix_quoted_titles.py --write")
        return

    fixed = 0
    for p, _ in files_to_fix:
        text = p.read_text(encoding="utf-8")
        # rewrite: collapse the whole broken title to a single clean quoted string
        # by removing every internal double-quote between the outermost two
        def clean(match):
            # match.group(0) is the entire broken `title: "..."` line
            # we already know it has 4+ quotes. Strip ALL inner ones.
            inner = match.group(0)
            # split off the "title:" prefix
            prefix_m = re.match(r'^(title:\s*)"(.*)"\s*$', inner)
            if not prefix_m:
                return inner  # bail
            label = prefix_m.group(1)
            content = prefix_m.group(2)
            # remove ALL double-quotes from the content
            content = content.replace('"', '')
            # collapse multiple spaces
            content = re.sub(r'\s+', ' ', content).strip()
            return f'{label}"{content}"'

        new_text = re.sub(r'^title:\s*"[^\n]*"\s*$', clean, text, count=1, flags=re.MULTILINE)
        if new_text != text:
            p.write_text(new_text, encoding="utf-8")
            fixed += 1

    print(f"\nFixed {fixed} files.")

if __name__ == "__main__":
    main()
