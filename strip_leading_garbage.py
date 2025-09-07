#!/usr/bin/env python3
# Remove any junk/zero-width/control chars before the first real '---' in every .md.
# Keep everything else. Save UTF-8 without BOM.

from pathlib import Path
import sys

POSTS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("content/posts")
ZW = "".join(["\u200B","\u200C","\u200D","\uFEFF"])
DASHES = str.maketrans({"—":"-","–":"-","‒":"-","−":"-"})

def is_delim(line: str) -> bool:
    s = line.replace(ZW, "").translate(DASHES).strip()
    return s == "---"

def clean(p: Path) -> bool:
    b = p.read_bytes()
    if b[:3] == b"\xEF\xBB\xBF":
        b = b[3:]
    t = b.decode("utf-8", errors="replace")
    lines = t.splitlines()

    # find first good '---' within top 80 lines
    first = None
    for i, L in enumerate(lines[:80]):
        if is_delim(L):
            first = i
            break
    if first is None:
        return False  # no yaml; leave it

    changed = False
    if first != 0:
        lines = lines[first:]
        changed = True
    if lines and lines[0].strip() != "---":
        lines[0] = "---"
        changed = True
    if changed:
        p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return changed

def main():
    if not POSTS.exists():
        print(f"Not found: {POSTS}")
        sys.exit(1)
    total = fixed = 0
    for md in sorted(POSTS.glob("*.md")):
        total += 1
        try:
            if clean(md):
                fixed += 1
                print(f"[cleaned] {md.name}")
        except Exception as e:
            print(f"[ERR] {md.name}: {e}")
    print(f"\nDone. Scanned: {total}, cleaned: {fixed}")

if __name__ == "__main__":
    main()
