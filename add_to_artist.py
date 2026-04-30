#!/usr/bin/env python3
"""
add_to_artist.py - update one artist's post with fresh CSV data

Use this when an artist drops a new song and you want to refresh their post.
Re-export their Spotify playlist via Exportify, then:

    python add_to_artist.py "Armanii_-_5_Songs.csv"

What it does:
  - Looks up the matching post (content/<slug>.md or content/posts/<slug>.md)
  - Reads the CSV
  - Replaces the post body with fresh stack of Spotify embeds (newest first)
  - Bumps date in YAML to today so "recently updated" sorting works
  - Updates genre/era/explicit from the new track data
  - Skips if YAML has manual: true

Refuses to run on posts that don't exist yet - use create_missing_artists.py
for net-new artists.

Usage:
    python add_to_artist.py "path\\to\\Artist_-_N_Songs.csv"

Tip: drop this command into a one-line .bat file for one-click updates.
"""
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

CONTENT_DIRS = [Path("content"), Path("content/posts")]
SLUG_RE = re.compile(r"[^a-z0-9]+")

def slugify(s):
    return SLUG_RE.sub("-", s.lower()).strip("-")

def slug_from_csv_filename(name):
    stem = Path(name).stem
    m = re.match(r"^(.+?)_-_(?:\d+|XX)_Songs?$", stem, re.IGNORECASE)
    if not m:
        return None
    return slugify(m.group(1).replace("_", " "))

def find_post_for_slug(slug):
    for d in CONTENT_DIRS:
        direct = d / f"{slug}.md"
        if direct.exists():
            return direct
    safe = re.compile(rf"^{re.escape(slug)}-(?:\d+-songs?|top-songs?|xx-songs?)$", re.IGNORECASE)
    for d in CONTENT_DIRS:
        if not d.exists():
            continue
        for f in d.glob(f"{slug}-*.md"):
            if safe.match(f.stem):
                return f
    return None

def parse_front_matter(text):
    if not text.startswith("---"):
        return "", text, {}
    end = text.find("\n---", 4)
    if end == -1:
        return "", text, {}
    fm_text = text[4:end]
    body = text[end+4:].lstrip("\n")
    fields = {}
    for line in fm_text.splitlines():
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*?)$", line)
        if m and not line.startswith(" "):
            fields[m.group(1)] = m.group(2).strip()
    return fm_text, body, fields

def parse_tags_block(fm_text):
    lines = fm_text.splitlines()
    out = []
    in_tags = False
    for line in lines:
        if line.startswith("tags:"):
            in_tags = True
            out.append(line)
            continue
        if in_tags:
            if line.startswith(("  ", "\t")) or line.strip().startswith("-"):
                out.append(line)
            elif line.strip() == "":
                continue
            else:
                break
    return "\n".join(out) if out else ""

def derive_era(release_dates):
    eras = set()
    for d in release_dates:
        m = re.match(r"(\d{4})", d or "")
        if not m:
            continue
        y = int(m.group(1))
        if y >= 2020:
            eras.add("2020s")
        elif y >= 2000:
            eras.add("2000s-2010s")
        else:
            eras.add("1900s")
    return sorted(eras)

def parse_genres(strings):
    seen = []
    for s in strings:
        if not s:
            continue
        for g in s.split(","):
            g = g.strip().lower()
            if g and g not in seen:
                seen.append(g)
    return seen[:5]

def spotify_embed(uri):
    if not uri:
        return ""
    tid = uri.split(":")[-1]
    return (f'<iframe src="https://open.spotify.com/embed/track/{tid}" '
            f'width="100%" height="80" frameborder="0" '
            f'allow="encrypted-media" loading="lazy"></iframe>')

def title_from_slug(slug):
    out = []
    for p in slug.split("-"):
        if not p:
            continue
        if any(c.isdigit() for c in p):
            out.append(p)
        else:
            out.append(p.capitalize())
    return " ".join(out)

def main():
    if len(sys.argv) < 2:
        print("Usage: python add_to_artist.py <csv_path>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)

    slug = slug_from_csv_filename(csv_path.name)
    if not slug:
        print(f"ERROR: cannot derive artist slug from filename '{csv_path.name}'")
        print("       expected format: Artist_-_N_Songs.csv")
        sys.exit(1)

    post = find_post_for_slug(slug)
    if not post:
        print(f"ERROR: no existing post found for slug '{slug}'")
        print(f"       this artist needs to be created first.")
        print(f"       use create_missing_artists.py or build the post manually.")
        sys.exit(1)

    text = post.read_text(encoding="utf-8")
    old_fm_text, old_body, fields = parse_front_matter(text)

    if fields.get("manual", "").lower() == "true":
        print(f"SKIP: {post} has manual: true")
        sys.exit(0)

    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    if not rows:
        print(f"ERROR: {csv_path} has no rows")
        sys.exit(1)

    rows.sort(key=lambda r: r.get("Release Date") or "0000", reverse=True)

    embeds = [spotify_embed(r.get("Track URI", "")) for r in rows]
    embeds = [e for e in embeds if e]

    genres = parse_genres([r.get("Genres", "") for r in rows])
    eras = derive_era([r.get("Release Date", "") for r in rows])
    explicit = any(str(r.get("Explicit", "")).lower() == "true" for r in rows)

    today = datetime.now().strftime("%Y-%m-%d")

    title = fields.get("title", "").strip().strip('"').strip("'") or title_from_slug(slug)
    tags_block = parse_tags_block(old_fm_text)

    fm = ["---", f'title: "{title}"', f'slug: "{slug}"', f"date: {today}", "layout: post"]
    if eras:
        fm.append("era:")
        for e in eras:
            fm.append(f'  - "{e}"')
    if genres:
        fm.append("genre:")
        for g in genres:
            fm.append(f'  - "{g}"')
    if explicit:
        fm.append("explicit: true")
    if tags_block:
        fm.append(tags_block)
    fm.append("---")

    new_text = "\n".join(fm) + "\n\n" + "\n\n".join(embeds) + "\n"
    post.write_text(new_text, encoding="utf-8")

    print(f"Updated {post}")
    print(f"  artist:  {title}")
    print(f"  tracks:  {len(embeds)}")
    print(f"  date:    {today}  (bumped)")
    print(f"  genres:  {', '.join(genres) if genres else '(none)'}")
    print(f"  eras:    {', '.join(eras) if eras else '(none)'}")
    print(f"  explicit: {explicit}")

if __name__ == "__main__":
    main()
