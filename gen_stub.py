#!/usr/bin/env python3
"""
bigbanonos stub generator v2
Usage: python gen_stub.py path/to/Artist_Name.csv [output_dir]
"""
import csv, sys, os, re
from pathlib import Path
from datetime import datetime
from collections import Counter

def slug(s):
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-') or 'untitled'

def parse_year(rd):
    m = re.match(r'(\d{4})', rd or ''); return m.group(1) if m else ''

def parse_date(rd):
    if re.match(r'\d{4}-\d{2}-\d{2}', rd or ''): return rd
    if re.match(r'\d{4}', rd or ''): return rd + '-01-01'
    return ''

def fmt_duration(ms):
    try: s=int(ms)//1000; return f'{s//60}:{s%60:02d}'
    except: return ''

def extract_artist_from_filename(filename):
    name = Path(filename).stem
    name = re.sub(r'[_\s]*-[_\s]*(XX+|\d+\+?)[_\s]*Songs?.*$','',name,flags=re.I)
    name = re.sub(r'[_\s]*-[_\s]*DH[_\s]*Songs?.*$','',name,flags=re.I)
    name = re.sub(r'[_\s]*-[_\s]*Top[_\s]*Songs?.*$','',name,flags=re.I)
    return name.replace('_',' ').strip()

def era_for(y):
    if not y: return ''
    y=int(y)
    if y>=2020: return '2020s'
    if y>=2000: return '00s-10s'
    return '1900s'

def one_liner(artist, n, earliest, latest):
    """Deadpan one-sentence description in Joe's voice."""
    if earliest and latest:
        if earliest == latest:
            return f'{n} tracks, all from {earliest}.'
        span = int(latest) - int(earliest)
        if span >= 40:
            return f'{n} tracks spanning {earliest} to {latest}. {span} years of trying.'
        if span >= 20:
            return f'{n} tracks from {earliest} to {latest}. The peak is in there somewhere.'
        if span >= 10:
            return f'{n} tracks, {earliest} to {latest}.'
        return f'{n} tracks between {earliest} and {latest}.'
    return f'{n} tracks in the library.'

def make_post(csv_path, out_dir):
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows: print(f'  empty: {csv_path}'); return None

    # artist = most common primary artist across tracks
    primaries = [r.get('Artist Name(s)','').split(',')[0].strip() for r in rows]
    artist = Counter(p for p in primaries if p).most_common(1)[0][0] if primaries else extract_artist_from_filename(csv_path)

    # chrono sort
    rows.sort(key=lambda r: parse_date(r.get('Release Date','')))

    years = [parse_year(r.get('Release Date','')) for r in rows]
    years = [y for y in years if y]
    earliest = min(years) if years else ''
    latest   = max(years) if years else ''

    # eras present
    eras = sorted(set(era_for(y) for y in years if y))

    # clean collab tags: only individual artist names, not compound
    collabs = set()
    for r in rows:
        for a in (r.get('Artist Name(s)','') or '').split(','):
            a = a.strip()
            if a and a != artist:
                collabs.add(a)
    collab_tags = ['@'+slug(c) for c in sorted(collabs)[:10]]

    # genres (top 4)
    all_g = Counter()
    for r in rows:
        for g in (r.get('Genres','') or '').split(','):
            g = g.strip()
            if g: all_g[g]+=1
    top_genres = [g for g,_ in all_g.most_common(4)]

    tags = ['@'+slug(artist)] + collab_tags + eras + top_genres

    post_date = max([parse_date(r.get('Release Date','')) for r in rows if parse_date(r.get('Release Date',''))] or [datetime.utcnow().strftime('%Y-%m-%d')])

    # build front matter
    fm = ['---', f'title: "{artist}"', f'date: {post_date}', 'category: "artist"', f'track_count: {len(rows)}']
    if earliest: fm.append(f'first_year: {earliest}')
    if latest:   fm.append(f'last_year: {latest}')
    fm.append('tags:')
    for t in tags: fm.append(f"  - '{t}'")
    fm.append('stub: true')
    fm.append('---')

    body = []
    body.append(f'## {artist}')
    body.append('')
    body.append(f'_{one_liner(artist, len(rows), earliest, latest)}_')
    body.append('')
    body.append('---')
    body.append('')

    for r in rows:
        name = r.get('Track Name','').strip()
        album = r.get('Album Name','').strip()
        yr = parse_year(r.get('Release Date',''))
        uri = r.get('Track URI','') or r.get('\ufeffTrack URI','')
        tid = uri.split(':')[-1] if uri else ''
        dur = fmt_duration(r.get('Duration (ms)',''))
        ta = [a.strip() for a in (r.get('Artist Name(s)','') or '').split(',')]
        features = [a for a in ta if a and a != artist]
        feat = f' (feat. {", ".join(features)})' if features else ''

        body.append(f'**{name}**{feat}')
        meta = []
        if album: meta.append(f'*{album}*')
        if yr: meta.append(yr)
        if dur: meta.append(dur)
        if meta: body.append(' · '.join(meta))
        body.append('')
        if tid:
            body.append(f'<iframe style="border-radius:12px" src="https://open.spotify.com/embed/track/{tid}" width="100%" height="152" frameBorder="0" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>')
        body.append('')

    out = Path(out_dir) / f'{slug(artist)}.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(fm) + '\n\n' + '\n'.join(body), encoding='utf-8')
    return out

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python gen_stub.py <csv_path> [output_dir]'); sys.exit(1)
    out = sys.argv[2] if len(sys.argv)>2 else 'content/posts'
    result = make_post(sys.argv[1], out)
    if result: print(f'\u2713 wrote {result}')
