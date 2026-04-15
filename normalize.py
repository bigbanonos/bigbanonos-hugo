from pathlib import Path
import re, unicodedata

def clean_slug(name):
    # match exactly what the homepage JS does
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "untitled"

root = Path("content/posts")
renames = []
deletes = []
seen = {}

for p in root.glob("*.md"):
    new_slug = clean_slug(p.stem)
    new_name = new_slug + ".md"
    new_path = root / new_name
    if new_name != p.name:
        if new_path.exists() or new_slug in seen:
            # duplicate -> delete the less-clean one
            deletes.append(p)
            continue
        renames.append((p, new_path))
    seen[new_slug] = p

for old, new in renames:
    try:
        old.rename(new)
    except Exception as e:
        print(f"skip {old.name}: {e}")
for p in deletes:
    try:
        p.unlink()
    except: pass

print(f"Renamed: {len(renames)}  Deleted dupes: {len(deletes)}")
