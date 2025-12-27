#!/usr/bin/env python3
# Strict front matter rebuilder for Hugo posts.
# Rewrites the YAML header from extracted fields to avoid parse errors.

from pathlib import Path
import sys, re

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("content/posts")

def strip_bom(b: bytes) -> bytes:
    return b[3:] if b.startswith(b"\xEF\xBB\xBF") else b

ZW = "".join(["\u200B","\u200C","\u200D","\uFEFF"])
DASHES = {"—":"-", "–":"-", "‒":"-", "−":"-"}

def clean_scalar(s: str) -> str:
    # collapse zero-widths, trim, normalize quotes inside
    s = s.replace(ZW, "").strip()
    s = s.replace('"', "'")
    return s

def parse_yaml(lines):
    """Return (start_idx, end_idx, fields:dict, tag_items:list)."""
    # locate first two delimiters (---), allowing unicode dash variants
    def is_delim(x: str) -> bool:
        t = x.replace(ZW, "").strip()
        for k,v in DASHES.items(): t = t.replace(k, v)
        return t == "---"

    first = second = -1
    limit = min(len(lines), 80)
    for i in range(limit):
        if is_delim(lines[i]): first = i; break
    if first == -1: return -1, -1, {}, []
    for j in range(first+1, limit):
        if is_delim(lines[j]): second = j; break
    if second == -1: second = first + 1

    fields = {}
    tags = []
    i = first + 1
    while i < second:
        L = lines[i]
        if not L.strip() or L.lstrip().startswith("#"):
            i += 1; continue
        # list items under tags:
        if L.lstrip().startswith("-"):
            item = L.lstrip()[1:].strip()
            if item.startswith("@") or item.startswith("'@") or item.startswith('"@'):
                item = item.strip("'\"")
                tags.append(item)
            i += 1; continue
        m = re.match(r"^\s*([A-Za-z0-9_\-]+)\s*:\s*(.*)$", L)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            fields[key] = val
        i += 1

    return first, second, fields, tags

def rebuild_yaml(fields, tags):
    title  = clean_scalar(fields.get("title",""))
    otitle = clean_scalar(fields.get("original_title",""))
    date   = clean_scalar(fields.get("date",""))
    layout = clean_scalar(fields.get("layout","post"))

    # quote titles always; keep date as-is (ISO already in your export)
    out = []
    out.append("---")
    if title:
        out.append(f'title: "{title}"')
    if date:
        out.append(f"date: {date}")
    if otitle:
        out.append(f'original_title: "{otitle}"')
    if tags:
        out.append("tags:")
        for t in tags:
            t = t.strip()
            if not t.startswith("@"):  # if someone put plain text, keep as is
                out.append(f"  - '{t}'")
            else:
                out.append(f"  - '@{t.lstrip('@')}'")
    if layout:
        out.append(f"layout: {layout}")
    out.append("---")
    return "\n".join(out) + "\n"

def process_file(p: Path) -> bool:
    raw = strip_bom(p.read_bytes())
    text = raw.decode("utf-8", errors="replace")
    # normalize unicode dashes on delimiter lines quickly
    text = text.replace("Ã¢â‚¬â€œ","–").replace("Ã¢â‚¬â€”","—").replace("Ã¢â‚¬Â","”").replace("Ã¢â‚¬â„¢","’").replace("Ã¢â‚¬Å“","“")

    lines = re.split(r"\r?\n", text)
    s, e, fields, tags = parse_yaml(lines)
    if s == -1:
        # no yaml -> leave file alone but ensure LF/utf8
        p.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        return False

    # rebuild YAML
    yaml_new = rebuild_yaml(fields, tags)

    body = "\n".join(lines[e+1:]).lstrip("\n\r")
    final = yaml_new + body
    if final != text:
        p.write_text(final, encoding="utf-8", newline="\n")
        return True
    return False

def main():
    d = ROOT
    if not d.exists():
        print(f"Not found: {d}"); sys.exit(1)
    total = fixed = 0
    for md in sorted(d.glob("*.md")):
        total += 1
        try:
            if process_file(md):
                fixed += 1
                print(f"[rebuilt] {md.name}")
        except Exception as e:
            print(f"[ERR] {md.name}: {e}")
    print(f"\nDone. Scanned: {total}, rebuilt: {fixed}")

if __name__ == "__main__":
    main()
