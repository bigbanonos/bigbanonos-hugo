"""Generate 1-off bucket stub posts from Songs-Xx-ERA.csv files.

Usage:
  python gen_1off.py                          # auto-discover all Songs-*.csv anywhere in repo
  python gen_1off.py path/to/Songs-Aa-2020s.csv ...  # explicit files
"""
import csv, sys, re, glob
from pathlib import Path
from datetime import datetime

def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-') or 'untitled'
def fmt_dur(ms):
    try: s=int(ms)//1000; return f'{s//60}:{s%60:02d}'
    except: return ''
def yr(rd):
    m=re.match(r'(\d{4})',rd or ''); return m.group(1) if m else ''
def pd(rd):
    if re.match(r'\d{4}-\d{2}-\d{2}',rd or ''): return rd
    if re.match(r'\d{4}',rd or ''): return rd+'-01-01'
    return ''

ERA_LABELS = {
    '2020s':'2020s', '00s-10s':'2000s-2010s', '1900s':'Pre-2000', 'DH':'Dancehall',
}
ERA_LINES = {
    '2020s':'Current shit. The 2% that\'s good.',
    '00s-10s':'The peak decades for 1-offs. Pre-mortgage artists making one or two great songs before blind love with wife, kids, and money set in.',
    '1900s':'Before 2000. One good song and out.',
    'DH':'Jamaican dancehall 1-offs. 2-minute riddims that cooked.',
}

def parse_name(stem):
    m = re.match(r'Songs-([A-Za-z#]+)-(.+)', stem, re.IGNORECASE)
    if not m: return None, None
    L = m.group(1)[:1].upper()
    if not L.isalpha(): L = '#'
    era_raw = m.group(2).lower()
    if 'dh' in era_raw: era = 'DH'
    elif '2020' in era_raw: era = '2020s'
    elif '1900' in era_raw or 'pre' in era_raw: era = '1900s'
    elif 'all' in era_raw: era = 'All'
    else: era = '00s-10s'
    return L, era

def make_post(csv_path, out_dir):
    stem = Path(csv_path).stem
    letter, era = parse_name(stem)
    if not letter or era == 'All': return None
    if era not in ERA_LABELS: return None

    try:
        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
    except Exception as e:
        print(f'  ERROR reading {csv_path}: {e}')
        return None

    if not rows: return None
    rows.sort(key=lambda r: pd(r.get('Release Date','')))

    title = f'{letter} · {ERA_LABELS[era]} 1-offs'
    post_slug = f'{letter.lower()}-{slug(era)}-1offs'
    post_date = max([pd(r.get('Release Date','')) for r in rows if pd(r.get('Release Date',''))] or [datetime.utcnow().strftime('%Y-%m-%d')])

    tags = [f'letter-{letter.lower()}', '1off', era]
    if era == 'DH': tags.append('dancehall')

    fm = ['---', f'title: "{title}"', f'date: {post_date}',
          'category: "1off"', f'track_count: {len(rows)}',
          f'letter: "{letter}"', f'era: "{era}"', 'stub: true', 'tags:']
    for t in tags: fm.append(f"  - '{t}'")
    fm.append('---')

    body = [f'## {title}', '', f'_{len(rows)} favorite songs by artists starting with {letter}. {ERA_LINES[era]}_', '', '---', '']
    for r in rows:
        name = r.get('Track Name','').strip()
        artist = (r.get('Artist Name(s)','') or '').split(';')[0].split(',')[0].strip()
        album = r.get('Album Name','').strip()
        y = yr(r.get('Release Date',''))
        uri = r.get('Track URI','') or r.get('\ufeffTrack URI','')
        tid = uri.split(':')[-1] if uri else ''
        dur = fmt_dur(r.get('Duration (ms)',''))
        if not name and not tid: continue
        body.append(f'**{artist}** — {name}')
        meta = []
        if album: meta.append(f'*{album}*')
        if y: meta.append(y)
        if dur: meta.append(dur)
        if meta: body.append(' · '.join(meta))
        body.append('')
        if tid:
            body.append(f'<iframe style="border-radius:12px" src="https://open.spotify.com/embed/track/{tid}" width="100%" height="152" frameBorder="0" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>')
        body.append('')

    out = Path(out_dir) / f'{post_slug}.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(fm)+'\n\n'+'\n'.join(body), encoding='utf-8')
    return out

if __name__ == '__main__':
    # Output always goes to content/posts/
    out_dir = Path('content/posts')

    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        # Auto-discover all Songs-*.csv anywhere under current directory
        files = glob.glob('**/Songs-*.csv', recursive=True)
        files += glob.glob('Songs-*.csv')
        files = list(set(files))
        if not files:
            print('No Songs-*.csv files found. Run from repo root or pass CSV paths as arguments.')
            sys.exit(1)
        print(f'Found {len(files)} Songs-*.csv files')

    ok = 0
    skip = 0
    for f in sorted(files):
        r = make_post(f, out_dir)
        if r:
            print(f'✓ {r.name}')
            ok += 1
        else:
            print(f'  skipped {Path(f).name}')
            skip += 1

    print(f'\nDone: {ok} created, {skip} skipped → content/posts/')
