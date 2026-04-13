#!/usr/bin/env python3
"""
bigbanonos: Exportify CSVs -> Hugo markdown posts.

Usage:
    python3 build_posts.py /path/to/csv_folder /path/to/bigbanonos-hugo/content/posts

Filename rules (matches the Spotify folder taxonomy):
    Artists-A-Part-1.csv, Artists-A-Part-2.csv  -> type=artist, letter=A
    Songs-A-2020s.csv                           -> type=1off,   era=2020s
    Songs-A-00s-10s.csv                         -> type=1off,   era=00s-10s
    Songs-A-1900s.csv                           -> type=1off,   era=1900s
    Covers-A.csv                                -> type=cover
    zz-*  -> ignored
"""
import csv, os, re, sys, hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime

SLUG_RE = re.compile(r'[^a-z0-9]+')
def slug(s):
    s = SLUG_RE.sub('-', s.lower()).strip('-')
    return s or 'untitled'

def parse_filename(name):
    """Return dict {kind, letter, era} or None to skip."""
    stem = Path(name).stem
    if stem.lower().startswith('zz'):
        return None
    parts = stem.split('-')
    head = parts[0].lower()
    if head == 'artists' and len(parts) >= 2:
        return {'kind': 'artist', 'letter': parts[1][:1].upper(), 'era': None}
    if head == 'covers' and len(parts) >= 2:
        return {'kind': 'cover', 'letter': parts[1][:1].upper(), 'era': None}
    if head == 'songs' and len(parts) >= 3:
        letter = parts[1][:1].upper()
        era_raw = '-'.join(parts[2:]).lower()
        if '2020' in era_raw: era = '2020s'
        elif '1900' in era_raw or 'pre' in era_raw: era = '1900s'
        else: era = '00s-10s'
        return {'kind': '1off', 'letter': letter, 'era': era}
    return None

def spotify_embed(uri):
    # spotify:track:XXXX -> https://open.spotify.com/embed/track/XXXX
    if not uri: return ''
    tid = uri.split(':')[-1]
    return f'<iframe src="https://open.spotify.com/embed/track/{tid}" width="100%" height="80" frameborder="0" allow="encrypted-media" loading="lazy"></iframe>'

def yaml_escape(s):
    return (s or '').replace('"', '\\"')

def front_matter(title, date, tags, cover=None):
    fm = ['---', f'title: "{yaml_escape(title)}"', f'date: {date}']
    if cover:
        fm += ['cover:', f'  image: "{cover}"']
    fm.append('tags:')
    for t in tags:
        fm.append(f'  - "{yaml_escape(t)}"')
    fm.append('---')
    return '\n'.join(fm)

def write_post(out_dir, slug_name, body):
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f'{slug_name}.md'
    if p.exists():
        # de-dupe via hash suffix so re-runs don't clobber
        h = hashlib.md5(body.encode()).hexdigest()[:6]
        p = out_dir / f'{slug_name}-{h}.md'
    p.write_text(body, encoding='utf-8')

def primary_artist(row):
    a = row.get('Artist Name(s)') or row.get('Artist Name') or ''
    return a.split(',')[0].strip()

def release_year(row):
    rd = row.get('Release Date') or row.get('Album Release Date') or ''
    m = re.match(r'(\d{4})', rd)
    return m.group(1) if m else ''

def album_image(row):
    # Exportify exports "Album Image URL" in newer versions
    return row.get('Album Image URL') or row.get('Cover') or ''

def process(csv_dir, out_dir):
    csv_dir, out_dir = Path(csv_dir), Path(out_dir)
    files = sorted(csv_dir.glob('*.csv'))
    if not files:
        print(f'No CSVs in {csv_dir}'); return

    # bucket: (kind, era, artist) -> [rows]
    buckets = defaultdict(list)
    for f in files:
        meta = parse_filename(f.name)
        if not meta:
            print(f'skip: {f.name}'); continue
        with f.open(encoding='utf-8-sig', newline='') as fh:
            for row in csv.DictReader(fh):
                artist = primary_artist(row)
                if not artist: continue
                buckets[(meta['kind'], meta['era'], artist)].append(row)

    today = datetime.utcnow().strftime('%Y-%m-%d')
    n_artist = n_1off = n_cover = 0

    # Artist posts: any (kind=artist) bucket OR any 1off bucket where same artist has 2+
    artist_groups = defaultdict(list)  # artist -> rows (across artist files)
    for (kind, era, artist), rows in buckets.items():
        if kind == 'artist':
            artist_groups[artist].extend(rows)

    for artist, rows in artist_groups.items():
        letter = artist[:1].upper() if artist[:1].isalpha() else '#'
        cover = next((album_image(r) for r in rows if album_image(r)), '')
        tags = ['music', 'artist', f'letter-{letter.lower()}', artist]
        body_lines = [f'## {artist}', '']
        for r in sorted(rows, key=lambda x: release_year(x) or '0000'):
            t = r.get('Track Name','').strip()
            yr = release_year(r)
            body_lines.append(f'### {t}' + (f' · {yr}' if yr else ''))
            body_lines.append(spotify_embed(r.get('Spotify URI') or r.get('Track URI') or r.get('Spotify Track URI','')))
            body_lines.append('')
        body = front_matter(artist, today, tags, cover) + '\n\n' + '\n'.join(body_lines)
        write_post(out_dir, slug(artist), body)
        n_artist += 1

    # 1-offs and covers
    for (kind, era, artist), rows in buckets.items():
        if kind == 'artist': continue
        if kind == '1off' and artist in artist_groups: continue  # already covered
        for r in rows:
            track = r.get('Track Name','').strip()
            if not track: continue
            title = f'{artist} — {track}'
            letter = artist[:1].upper() if artist[:1].isalpha() else '#'
            tags = ['music', f'letter-{letter.lower()}', artist]
            if kind == 'cover':
                tags.append('cover'); n_cover += 1
            else:
                tags.append('1off'); n_1off += 1
            if era: tags.append(era)
            body = front_matter(title, today, tags, album_image(r)) + '\n\n' + spotify_embed(
                r.get('Spotify URI') or r.get('Track URI') or r.get('Spotify Track URI','')
            ) + '\n'
            write_post(out_dir, slug(title), body)

    print(f'Done. artists={n_artist}  1offs={n_1off}  covers={n_cover}  -> {out_dir}')

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: build_posts.py <csv_dir> <hugo_content_posts_dir>'); sys.exit(1)
    process(sys.argv[1], sys.argv[2])
