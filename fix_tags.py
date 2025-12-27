#!/usr/bin/env python3
# Fix tags front-matter across all posts:
# - Convert "tags: @a, @b" or "tags: '@a'" to list items
# - Remove empty "tags:" blocks
# - Keep everything UTF-8 without BOM

from pathlib import Path
import re, sys

ROOT = Path("content/posts")

def find_yaml(lines):
    s = e = -1
    for i in range(min(80, len(lines))):
        if lines[i].strip() == "---":
            s = i; break
    if s < 0: return -1,-1
    for j in range(s+1, min(120, len(lines))):
        if lines[j].strip() == "---":
            e = j; break
    return s, e

def fix_one(p: Path) -> bool:
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = re.split(r"\r?\n", text)
    s, e = find_yaml(lines)
    if s < 0 or e < 0:  # no yaml
        return False

    # scan for "tags:" key
    tag_i = -1
    for i in range(s+1, e):
        if re.match(r"^\s*tags\s*:", lines[i]):
            tag_i = i
            break
    if tag_i == -1:
        return False

    # capture the value on the "tags:" line (could be scalar or empty)
    m = re.match(r"^(?P<lead>\s*)tags\s*:\s*(?P<val>.*)$", lines[tag_i])
    lead = m.group("lead")
    val = m.group("val").strip()

    # collect existing list items already present below
    items = []
    j = tag_i + 1
    while j < e and re.match(r"^\s*-", lines[j]):
        item = re.sub(r"^\s*-\s*", "", lines[j]).strip().strip('"\'')
        if item:
            items.append(item)
        j += 1

    changed = False

    # If value is inline (e.g., "@a, @b" or "'@a'"), parse it
    if val and not items:
        # split by comma or spaces
        raw = [x.strip().strip('"\'') for x in re.split(r"[,\s]+", val) if x.strip()]
        items = [r for r in raw if r]

    # If still no items, remove the tags line (and any accidental non-list lines under it)
    if not items:
        # delete tags line
        del lines[tag_i]
        # also delete any immediate non-list blank lines that belonged to it
        while tag_i < e and (lines[tag_i].strip() == "" or lines[tag_i].lstrip().startswith("#")):
            del lines[tag_i]
            e -= 1
        changed = True
    else:
        # rebuild as a proper list
        block = [f"{lead}tags:"] + [f"{lead}  - '{t if t.startswith('@') else '@'+t}'" for t in items]
        # replace original tags section: tags line + any following list items we counted
        del lines[tag_i:j]
        for k, L in enumerate(block):
            lines.insert(tag_i + k, L)
        changed = True

    if changed:
        Path(p).write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return changed

def main():
    root = ROOT
    total = fixed = 0
    for md in sorted(root.glob("*.md")):
        total += 1
        try:
            if fix_one(md):
                fixed += 1
                print(f"[tags fixed] {md.name}")
        except Exception as e:
            print(f"[ERR] {md.name}: {e}")
    print(f"\nDone. Scanned: {total}, tags-fixed: {fixed}")

if __name__ == "__main__":
    main()
