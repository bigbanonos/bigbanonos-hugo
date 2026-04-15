from pathlib import Path
import re, os

root = Path("content/posts")
fixed_dates = 0
deleted = 0

# 1. Fix broken dates
for p in root.glob("*.md"):
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except:
        continue
    if not txt.startswith("---"): continue
    end = txt.find("\n---", 4)
    if end == -1: continue
    fm = txt[4:end]
    new_fm = fm
    # fix date lines that arent YYYY-MM-DD
    def fix_date(m):
        val = m.group(1).strip()
        # pull out first YYYY-MM-DD or YYYY
        d = re.search(r"(\d{4})-(\d{2})-(\d{2})", val)
        if d: return f"date: {d.group(0)}"
        y = re.search(r"(\d{4})", val)
        if y: return f"date: {y.group(1)}-01-01"
        return "date: 2025-01-01"
    new_fm = re.sub(r"^date:\s*(.+)$", fix_date, fm, flags=re.M)
    if new_fm != fm:
        p.write_text(txt[:4] + new_fm + txt[end:], encoding="utf-8")
        fixed_dates += 1

# 2. Delete files with absurdly long names (>200 chars) or path-traversal garbage
for p in root.glob("*.md"):
    if len(p.name) > 200 or ".." in p.stem or "\\" in p.stem or "/" in p.stem:
        print(f"delete (bad filename): {p.name[:80]}...")
        p.unlink()
        deleted += 1

print(f"Fixed dates: {fixed_dates}")
print(f"Deleted bad filenames: {deleted}")
