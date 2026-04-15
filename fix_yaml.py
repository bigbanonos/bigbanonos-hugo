from pathlib import Path
import re

fixes = 0
for p in Path("content/posts").glob("*.md"):
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except:
        continue
    orig = txt
    # Fix 1: unescaped inner quotes -> replace inner " with '
    def fix_title(m):
        line = m.group(0)
        inner = line[len("title: \""):-1]
        inner_fixed = inner.replace("\"", "'")
        return f"title: \"{inner_fixed}\""
    txt = re.sub(r'^title: "[^\n]*"$', fix_title, txt, count=1, flags=re.M)
    # Fix 2: file with no opening --- at all
    if not txt.startswith("---"):
        txt = "---\ntitle: \"" + p.stem.replace("-", " ").title() + "\"\ndate: 2025-01-01\ncategory: \"artist\"\nstub: true\n---\n\n" + txt
    if txt != orig:
        p.write_text(txt, encoding="utf-8")
        fixes += 1
        print(f"fixed: {p.name}")
print(f"Total fixed: {fixes}")
