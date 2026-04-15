from pathlib import Path
import re, shutil

root = Path("content/posts")
deleted = 0
fixed_tags = 0

# Scan every post for tags containing ".." or super long tags, strip those tags
for p in root.glob("*.md"):
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except:
        continue
    if not txt.startswith("---"): continue
    end = txt.find("\n---", 4)
    if end == -1: continue
    fm = txt[4:end]
    new_lines = []
    changed = False
    for line in fm.split("\n"):
        # remove tag lines that contain .. or are absurdly long
        m = re.match(r"^(\s*-\s*['\"]?)([^'\"\n]+)(['\"]?)$", line)
        if m and (".." in m.group(2) or len(m.group(2)) > 60):
            changed = True
            continue
        new_lines.append(line)
    if changed:
        txt = txt[:4] + "\n".join(new_lines) + txt[end:]
        p.write_text(txt, encoding="utf-8")
        fixed_tags += 1

# Nuke public/ so hugo rebuilds clean
pub = Path("public")
if pub.exists():
    shutil.rmtree(pub, ignore_errors=True)
    print("deleted public/")

print(f"Cleaned tags in {fixed_tags} files")
