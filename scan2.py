from pathlib import Path
try:
    import yaml
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "--quiet"])
    import yaml

broken = []
for p in Path("content/posts").glob("*.md"):
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        broken.append((p.name, f"read: {e}")); continue
    if not txt.startswith("---"):
        broken.append((p.name, "no opening ---")); continue
    end = txt.find("\n---", 4)
    if end == -1:
        broken.append((p.name, "no closing ---")); continue
    fm = txt[4:end]
    try:
        yaml.safe_load(fm)
    except yaml.YAMLError as e:
        broken.append((p.name, str(e).split("\n")[0][:120]))
print(f"Found {len(broken)} broken:")
for n, w in broken:
    print(f"  {n}: {w}")
