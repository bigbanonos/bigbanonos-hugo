"""Generate 1-off bucket stub posts from playlist_manifest.json entries."""
import json, re
from pathlib import Path

MANIFEST = Path('static/playlist_manifest.json')
OUT_DIR   = Path('content/posts')

ERA_LABELS = {
    '2020s':   '2020s',
    '00s-10s': '2000s–2010s',
    '1900s':   'Pre-2000',
    'DH':      'Dancehall',
    'dancehall':'Dancehall',
}
ERA_LINES = {
    '2020s':    "Current shit. The 2% that's good.",
    '00s-10s':  "The peak decades for 1-offs. Pre-mortgage artists making one great song before blind love with wife, kids, and money set in.",
    '1900s':    "Before 2000. One good song and out.",
    'DH':       "Jamaican dancehall 1-offs. 2-minute riddims that cooked.",
    'dancehall':"Jamaican dancehall 1-offs. 2-minute riddims that cooked.",
}

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def era_slug(era):
    # normalize era value to a url-safe slug
    return slug(era)

def make_stub(entry):
    letter = (entry.get('letter') or '').upper()
    era    = entry.get('era') or ''
    name   = entry.get('name') or ''
    tracks = entry.get('tracks') or 0

    if not letter or not era:
        return None

    era_label = ERA_LABELS.get(era, era)
    era_line  = ERA_LINES.get(era, '')
    post_slug = f'{letter.lower()}-{era_slug(era)}-1offs'
    title     = f'{letter} · {era_label} 1-offs'

    fm = f"""---
title: "{title}"
date: 2025-01-01
category: "1off"
track_count: {tracks}
letter: "{letter}"
era: "{era}"
stub: true
tags:
  - 'letter-{letter.lower()}'
  - '1off'
  - '{era}'
---

## {title}

_{tracks} favorite songs by artists starting with {letter}. {era_line}_

---

*Songs coming soon.*
"""
    return post_slug, fm

def main():
    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST} not found. Run from repo root.")
        return

    with open(MANIFEST, encoding='utf-8') as f:
        manifest = json.load(f)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0
    for entry in manifest:
        if entry.get('kind') != '1off_bucket':
            continue
        result = make_stub(entry)
        if not result:
            skipped += 1
            continue
        post_slug, content = result
        out = OUT_DIR / f'{post_slug}.md'
        if out.exists():
            print(f'  exists  {out.name}')
            skipped += 1
        else:
            out.write_text(content, encoding='utf-8')
            print(f'  ✓ {out.name}')
            created += 1

    print(f'\nDone. {created} created, {skipped} skipped.')

if __name__ == '__main__':
    main()
