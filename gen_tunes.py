#!/usr/bin/env python3
"""
gen_tunes.py

Builds the /tunes/ section: a chronological blog of every 2025-2026 song
from BigBanonos library. Each tune is its own post at content/tunes/<slug>.md.

Sources scanned:
  - All Songs-<letter>-2020s.csv (1-off era files)
  - All All_artists_<letter>.csv (multi-track artist aggregates)

For each track with Release Date in 2025 or 2026:
  - Creates content/tunes/<artist>-<track>.md
  - Date = song release date (so chronological feed sorts naturally)
  - Title = "<Artist> — <Track>"
  - Spotify embed if URI present
  - Tags: era, year, letter, genre tags from Spotify, plus 'tune' category
  - Crosslink to /<artist-slug>/ at the bottom

Skips if the destination file already exists.
Skips empty rows / placeholder rows / featured-artist concat junk.

Usage:
    python gen_tunes.py --csv-dir "C:\\path\\to\\spotify_playlists"            # dry run
    python gen_tunes.py --csv-dir "C:\\path\\to\\spotify_playlists" --write    # do it
    python gen_tunes.py --csv-dir "C:\\path\\to\\spotify_playlists" --write --years 2026
        # only 2026
"""
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict

LEADING_THE = re.compile(r"^the[-\s_]+", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")
TARGET_YEARS_DEFAULT = {"2025", "2026"}

def canonicalize(name):
    """Slug a name. Drops 'The', folds accents, alphanumerics + hyphens only."""
    if not name:
        return ""
    s = LEADING_THE.sub("", name.strip())
    folds = {
        "ü": "u", "ö": "o", "ä": "a", "é": "e", "è": "e", "ê": "e",
        "á": "a", "à": "a", "ó": "o", "ò": "o", "ñ": "n", "ç": "c",
        "í": "i", "ú": "u", "Ü": "u", "Ö": "o", "Ä": "a", "É": "e",
        "ø": "o", "Ø": "o", "å": "a", "Å": "a", "ß": "ss",
    }
    for k, v in folds.items():
        s = s.replace(k, v)
    s = NON_ALNUM.sub("-", s).strip("-").lower()
    return s

def primary_artist(field):
    return field.split(";")[0].strip() if field else ""

def safe_yaml_str(s):
    """Make a string safe to put in single-quoted YAML."""
    return s.replace("'", "''").replace("\n", " ").replace("\r", "").strip()

def first_letter(slug):
    if not slug:
        return "#"
    c = slug[0].upper()
    return c if c.isalpha() else "#"

def make_tune_post(artist_name, track_name, track_uri, release_date, genres, explicit, year):
    """Build the markdown content for a single tune post."""
    artist_slug = canonicalize(artist_name)
    track_slug = canonicalize(track_name)
    if not artist_slug or not track_slug:
        return None, None

    full_slug = f"{artist_slug}-{track_slug}"
    # Hugo slugs shouldn't be enormous
    if len(full_slug) > 90:
        full_slug = full_slug[:90].rstrip("-")

    letter = first_letter(artist_slug)

    # Genre list
    genre_list = []
    for g in (genres or "").lower().split(","):
        g = g.strip()
        if g and g not in genre_list:
            genre_list.append(g)
    genre_list = genre_list[:5]

    # Title display
    title = f"{artist_name.strip()} — {track_name.strip()}"
    title = safe_yaml_str(title)

    # Date (post date = release date for chronological feed)
    date = release_date[:10] if release_date and len(release_date) >= 10 else f"{year}-01-01"
    if len(date) == 7:  # "2026-03"
        date += "-01"
    elif len(date) == 4:  # "2026"
        date += "-01-01"

    fm = [
        "---",
        f"title: '{title}'",
        f"slug: '{full_slug}'",
        f"date: {date}",
        "layout: post",
        "section: tunes",
        f"letter: '{letter}'",
        f"year: '{year}'",
        "era: '2020s'",
        "category: 'tune'",
    ]
    if genre_list:
        fm.append("genre:")
        for g in genre_list:
            fm.append(f"  - '{safe_yaml_str(g)}'")
    if explicit:
        fm.append("explicit: true")
    fm.append("tags:")
    fm.append(f"  - '@{artist_slug}'")
    fm.append(f"  - '#tune'")
    fm.append(f"  - '#{year}'")
    fm.append("---")
    fm.append("")

    # Body: Spotify embed (lead), then crosslink
    body_parts = []
    if track_uri and ":" in track_uri:
        track_id = track_uri.split(":")[-1]
        body_parts.append(
            f'<iframe src="https://open.spotify.com/embed/track/{track_id}" '
            f'width="100%" height="80" frameborder="0" '
            f'allow="encrypted-media" loading="lazy"></iframe>'
        )
    else:
        body_parts.append(f'<p><em>#NotOnSpotify</em></p>')

    body_parts.append("")
    body_parts.append(f"[More by {artist_name}](/{artist_slug}/)")

    return full_slug, "\n".join(fm) + "\n" + "\n\n".join(body_parts) + "\n"


def collect_tracks(csv_dir, target_years):
    """Walk all relevant CSVs, return list of track dicts for tracks in target years."""
    csv_dir = Path(csv_dir)
    tracks = []
    seen_uris = set()  # dedupe by Spotify URI in case track appears in multiple CSVs

    # 1-off era CSVs (Songs-<letter>-2020s.csv) and multi-track aggregates (All_artists_<letter>.csv)
    patterns = ["Songs-*-2020s.csv", "All_artists_*.csv"]
    for pattern in patterns:
        for path in sorted(csv_dir.glob(pattern)):
            try:
                with open(path, encoding="utf-8-sig", newline="") as fh:
                    for r in csv.DictReader(fh):
                        rd = r.get("Release Date", "") or ""
                        year = rd[:4]
                        if year not in target_years:
                            continue
                        uri = r.get("Track URI", "") or ""
                        if uri and uri in seen_uris:
                            continue
                        if uri:
                            seen_uris.add(uri)
                        primary = primary_artist(r.get("Artist Name(s)", ""))
                        track_name = r.get("Track Name", "").strip()
                        if not primary or not track_name:
                            continue
                        tracks.append({
                            "artist": primary,
                            "track": track_name,
                            "uri": uri,
                            "release_date": rd,
                            "year": year,
                            "genres": r.get("Genres", ""),
                            "explicit": str(r.get("Explicit", "")).lower() == "true",
                            "source": path.name,
                        })
            except Exception as e:
                print(f"  WARN reading {path.name}: {e}")
    return tracks


def write_index_file(tunes_dir, write):
    """Write content/tunes/_index.md to define the section."""
    index_path = tunes_dir / "_index.md"
    if index_path.exists():
        return False
    content = """---
title: 'Tunes'
description: 'Chronological feed. Songs that earned a moment.'
---
"""
    if write:
        tunes_dir.mkdir(parents=True, exist_ok=True)
        index_path.write_text(content, encoding="utf-8")
    return True


def main():
    args = sys.argv[1:]
    write = "--write" in args
    csv_dir = None
    years = TARGET_YEARS_DEFAULT
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--csv-dir" and i + 1 < len(args):
            csv_dir = args[i + 1]
            i += 2
        elif a == "--years" and i + 1 < len(args):
            years = set(args[i + 1].split(","))
            i += 2
        else:
            i += 1

    if not csv_dir:
        print('Usage: python gen_tunes.py --csv-dir "C:\\path" [--write] [--years 2025,2026]')
        sys.exit(1)

    mode = "WRITE" if write else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"GEN TUNES — {mode}")
    print(f"Years: {sorted(years)}")
    print(f"{'='*60}\n")

    tracks = collect_tracks(csv_dir, years)
    print(f"Tracks matching target years: {len(tracks)}")

    # Group by year for display
    by_year = defaultdict(int)
    for t in tracks:
        by_year[t["year"]] += 1
    for y in sorted(by_year):
        print(f"  {y}: {by_year[y]} tracks")
    print()

    tunes_dir = Path("content/tunes")
    created = []
    skipped = []
    errors = []

    if write_index_file(tunes_dir, write):
        print(f"  [INDX] content/tunes/_index.md")
    else:
        if write:
            print(f"  [INDX] content/tunes/_index.md (already exists)")

    for t in tracks:
        slug, content = make_tune_post(
            t["artist"], t["track"], t["uri"], t["release_date"],
            t["genres"], t["explicit"], t["year"]
        )
        if not slug or not content:
            errors.append(f"failed to build: {t['artist']} - {t['track']}")
            continue
        target = tunes_dir / f"{slug}.md"
        if target.exists():
            skipped.append(slug)
            continue
        if write:
            tunes_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        created.append(slug)
        if len(created) <= 8:
            print(f"  [NEW]  content/tunes/{slug}.md")
        elif len(created) == 9:
            print(f"  ... (more posts being created, output truncated)")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  Created:  {len(created)}")
    print(f"  Skipped:  {len(skipped)} (already exist)")
    print(f"  Errors:   {len(errors)}")
    if errors[:3]:
        for e in errors[:3]:
            print(f"    ! {e}")

    if not write:
        print(f"\nDRY RUN COMPLETE. To execute:")
        print(f"  python gen_tunes.py --csv-dir \"{csv_dir}\" --write")
    else:
        print(f"\nDone. Don't forget to:")
        print(f"  git add -A")
        print(f"  git commit -m 'feat: tunes section, 2025-2026 chronological feed'")
        print(f"  git push")


if __name__ == "__main__":
    main()
