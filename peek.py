from pathlib import Path
for fn in ["nick-kroll.md","raffi.md","the-sesame-street-kids.md","woody-guthrie.md"]:
    p = Path("content/posts") / fn
    if not p.exists(): continue
    print(f"=== {fn} ===")
    for i, line in enumerate(p.read_text(encoding="utf-8",errors="ignore").split("\n")[:20], 1):
        print(f"{i:2}: {line}")
    print()
