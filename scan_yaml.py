import re
from pathlib import Path
broken = []
for p in Path('content/posts').glob('*.md'):
    try:
        txt = p.read_text(encoding='utf-8', errors='ignore')
        if not txt.startswith('---'):
            broken.append((p.name, 'no opening ---'))
            continue
        end = txt.find('\n---', 4)
        if end == -1:
            broken.append((p.name, 'no closing ---'))
            continue
        fm = txt[4:end]
        for line in fm.split('\n'):
            if line.startswith('title:'):
                val = line[6:].strip()
                if val.startswith('"') and val.endswith('"') and val.count('"') > 2:
                    broken.append((p.name, f'unescaped quote in title: {line.strip()}'))
                    break
                if val.count('"') == 1 or (val.startswith('"') and not val.endswith('"')):
                    broken.append((p.name, f'unbalanced quotes: {line.strip()}'))
                    break
    except Exception as e:
        broken.append((p.name, f'read error: {e}'))
print(f'Found {len(broken)} broken YAML files:')
for n, why in broken[:40]:
    print(f'  {n}: {why}')
if len(broken) > 40:
    print(f'  ... and {len(broken)-40} more')
