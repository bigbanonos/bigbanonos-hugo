#!/usr/bin/env python3
"""
make_friday_post.py - turn an Exportify CSV into a BigBanonos /new/ post

Friday morning workflow:
  1. Export your "BigBanonos Best New Music - May 1" Spotify playlist via Exportify
  2. Drop the CSV in spotify_playlists/  (or anywhere)
  3. Run:
       python make_friday_post.py "C:\\path\\to\\BBBNM_May_1.csv"
  4. git add -A && git commit -m "new: 2026-05-01 NMF" && git push

Output: content/new/2026-05-01-best-new-music.md (or whatever date today is)

The post body is just a stack of Spotify track embeds. Title and date are
derived from the CSV filename if possible, otherwise from today's date.

Optional flags:
  --title "Friday May 1: Heat Check"     custom title
  --date 2026-05-01                       override date
  --slug heat-check                       override URL slug
  --tag "best-new-music"                  add extra YAML tag

Existing files at the same slug are NOT overwritten unless --force is passed.
"""
import csv
import re
import sys
from pathlib import Path
from datetime import datetime

OUT_DIR = Path("content/new")
SLUG_RE = re.compile(r"[^a-z0-9]+")

def slugify(s):
    return SLUG_RE.sub("-", s.lower()).strip("-")

def spotify_embed(uri):
    if not uri:
        return ""
    tid = uri.split(":")[-1]
    return (f'<iframe src="https://open.spotify.com/embed/track/{tid}" '
            f'width="100%" height="80" frameborder="0" '
            f'allow="encrypted-media" loading="lazy"></iframe>')

def get_arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default

def main():
    # find positional CSV path
    args = [a for a in sys.argv[1:] if not a.startswith("--")
            and sys.argv[sys.argv.index(a) - 1] not in ("--title", "--date", "--slug", "--tag")]
    if not args:
        print("Usage: python make_friday_post.py <csv_path> [--title T] [--date YYYY-MM-DD] [--slug S] [--tag T]")
        sys.exit(1)

    csv_path = Path(args[0])
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)

    force = "--force" in sys.argv
    custom_title = get_arg("--title")
    custom_date = get_arg("--date")
    custom_slug = get_arg("--slug")
    extra_tag = get_arg("--tag")

    # date: use --date if provided, else today
    today = custom_date or datetime.now().strftime("%Y-%m-%d")

    # title: use --title if provided, else derive from CSV filename
    if custom_title:
        title = custom_title
    else:
        stem = csv_path.stem
        # strip Exportify cruft
        clean = re.sub(r"_-_(?:\d+|XX)_Songs?$", "", stem, flags=re.IGNORECASE)
        clean = clean.replace("_", " ").strip()
        title = clean if clean else f"Best New Music {today}"

    # slug: --slug || derived from title || date-based
    if custom_slug:
        slug_part = custom_slug
    else:
        slug_part = slugify(title)
        if not slug_part:
            slug_part = "best-new-music"

    file_slug = f"{today}-{slug_part}"
    out_path = OUT_DIR / f"{file_slug}.md"

    if out_path.exists() and not force:
        print(f"ERROR: {out_path} already exists. Use --force to overwrite.")
        sys.exit(1)

    # read tracks
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    if not rows:
        print(f"ERROR: {csv_path} has no rows")
        sys.exit(1)

    # newest first
    rows.sort(key=lambda r: r.get("Release Date") or "0000", reverse=True)

    # collect distinct artists for the tag list
    artist_tags = []
    seen_tags = set()
    for r in rows:
        artists = r.get("Artist Name(s)") or ""
        for a in artists.split(";"):
            a = a.strip()
            if not a:
                continue
            tag = "@" + slugify(a)
            if tag not in seen_tags:
                seen_tags.add(tag)
                artist_tags.append(tag)

    # genres aggregate
    genres = []
    seen_g = set()
    for r in rows:
        for g in (r.get("Genres") or "").split(","):
            g = g.strip().lower()
            if g and g not in seen_g:
                seen_g.add(g)
                genres.append(g)
    genres = genres[:5]

    has_explicit = any(str(r.get("Explicit", "")).lower() == "true" for r in rows)

    # build front matter
    fm = [
        "---",
        f'title: "{title}"',
        f'slug: "{file_slug}"',
        f"date: {today}",
        'layout: post',
        'section: "new"',
    ]
    if genres:
        fm.append("genre:")
        for g in genres:
            fm.append(f'  - "{g}"')
    if has_explicit:
        fm.append("explicit: true")
    if artist_tags or extra_tag:
        fm.append("tags:")
        if extra_tag:
            fm.append(f'  - "{extra_tag}"')
        for t in artist_tags[:30]:  # cap at 30
            fm.append(f"  - '{t}'")
    fm.append("---")

    embeds = [spotify_embed(r.get("Track URI", "")) for r in rows]
    embeds = [e for e in embeds if e]

    content = "\n".join(fm) + "\n\n" + "\n\n".join(embeds) + "\n"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"  title:  {title}")
    print(f"  slug:   {file_slug}")
    print(f"  date:   {today}")
    print(f"  tracks: {len(embeds)}")
    print(f"  genres: {', '.join(genres) if genres else '(none)'}")
    print(f"  artists tagged: {len(artist_tags)}")

if __name__ == "__main__":
    main()
