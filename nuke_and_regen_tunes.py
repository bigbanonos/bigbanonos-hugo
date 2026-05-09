#!/usr/bin/env python3
"""
nuke_and_regen_tunes.py

Wipes the 290 song-per-post tune files (built on the wrong model) and
regenerates the /tunes/ section using the (artist, year) model:

    /tunes/2026/cityboymoe/   <- one page per artist-year, all their good
    /tunes/2026/aluna/             songs from that year, chronological,
    /tunes/2025/baby-keem/         dated to the latest song

Source-of-truth rule:
    The CSV file a track lives in identifies the main artist.
    - Track in 'CityBoyMoe_-_4_Songs.csv' -> tune is by CityBoyMoe
    - Track in 'Songs-Aa-2020s.csv' (1-off bucket) -> first semicolon name

Output structure:
    content/tunes/2026/<slug>/index.md
    content/tunes/2025/<slug>/index.md

Years auto-imported: 2025 and 2026 only. Older years are added manually
via add_tune.py (separate script).

Usage:
    python nuke_and_regen_tunes.py --csv-dir "C:\\path\\to\\spotify_playlists"
    python nuke_and_regen_tunes.py --csv-dir "..." --write
"""
import csv
import re
import shutil
import sys
from pathlib import Path
from collections import defaultdict

LEADING_THE = re.compile(r"^the[-\s_]+", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")
TARGET_YEARS = {"2025", "2026"}

# Per-artist CSV file pattern: 'Artist_Name_-_N_Songs.csv'
ARTIST_FILE_RE = re.compile(
    r"^(.+?)_-_(?:\d+|XX|XXX|X+|\d+\+|Top|All|DH|IP|Rap)_Songs?\.csv$",
    re.IGNORECASE,
)

# 1-off era files: 'Songs-Aa-2020s.csv', 'Songs-BB-2020s.csv'
ONEOFF_FILE_RE = re.compile(
    r"^Songs-([A-Za-z]{1,2})-2020s\.csv$",
    re.IGNORECASE,
)


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


def parse_artist_from_filename(filename):
    """For per-artist CSVs like 'Aluna_-_3_Songs.csv', return 'Aluna'."""
    m = ARTIST_FILE_RE.match(filename)
    if not m:
        return None
    raw = m.group(1)
    return raw.replace("_", " ").strip()


def safe_yaml_str(s):
    return s.replace("'", "''").replace("\n", " ").replace("\r", "").strip()


def first_letter(slug):
    if not slug:
        return "#"
    c = slug[0].upper()
    return c if c.isalpha() else "#"


def primary_artist_from_field(field):
    return field.split(";")[0].strip() if field else ""


def collect_by_artist_year(csv_dir):
    """Walk CSVs, group tracks by (artist_slug, year).
    Returns: dict[(artist_slug, year)] -> {display_name, tracks: [...]}
    """
    csv_dir = Path(csv_dir)
    grouped = defaultdict(lambda: {"display_name": "", "tracks": []})
    seen_uris = set()

    for path in sorted(csv_dir.glob("*.csv")):
        fname = path.name

        # Determine the "main artist" for this file
        per_artist = parse_artist_from_filename(fname)
        is_oneoff = ONEOFF_FILE_RE.match(fname) is not None

        if not per_artist and not is_oneoff:
            # Skip All_artists, Covers, junk — they're not source-of-truth files
            continue

        try:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except Exception as e:
            print(f"  WARN reading {fname}: {e}")
            continue

        for r in rows:
            rd = (r.get("Release Date", "") or "").strip()
            year = rd[:4] if len(rd) >= 4 else ""
            if year not in TARGET_YEARS:
                continue

            uri = r.get("Track URI", "") or ""
            if uri and uri in seen_uris:
                continue

            # Determine the main artist:
            # - per-artist file: the file's artist is canonical
            # - 1-off file: first semicolon-separated name in the row
            if per_artist:
                main_artist = per_artist
            else:
                main_artist = primary_artist_from_field(r.get("Artist Name(s)", ""))
            if not main_artist:
                continue

            track_name = (r.get("Track Name", "") or "").strip()
            if not track_name:
                continue

            artist_slug = canonicalize(main_artist)
            if not artist_slug:
                continue

            if uri:
                seen_uris.add(uri)

            key = (artist_slug, year)
            entry = grouped[key]
            if not entry["display_name"]:
                entry["display_name"] = main_artist
            entry["tracks"].append({
                "track_name": track_name,
                "uri": uri,
                "release_date": rd,
                "genres": r.get("Genres", "") or "",
                "explicit": str(r.get("Explicit", "")).lower() == "true",
                "all_artists": r.get("Artist Name(s)", "") or "",
                "added_at": r.get("Added At", "") or "",
                "source_file": fname,
            })

    return grouped


def make_tune_page_content(artist_slug, artist_name, year, tracks):
    """Build the markdown content for a single artist-year tune page."""
    # Sort tracks chronologically within the year
    def sort_key(t):
        rd = t.get("release_date", "")
        return rd if rd else "9999-99-99"
    tracks_sorted = sorted(tracks, key=sort_key)

    # Page date = LATEST song that year (for reverse-chronological feed)
    latest_date = max(
        (t["release_date"] for t in tracks_sorted if t.get("release_date")),
        default=f"{year}-12-31",
    )
    if len(latest_date) == 7:
        latest_date += "-01"
    elif len(latest_date) == 4:
        latest_date += "-01-01"

    # Aggregated genre tags from all tracks
    genre_set = []
    for t in tracks_sorted:
        for g in (t.get("genres") or "").lower().split(","):
            g = g.strip()
            if g and g not in genre_set:
                genre_set.append(g)
    genre_list = genre_set[:6]

    is_explicit = any(t.get("explicit") for t in tracks_sorted)
    letter = first_letter(artist_slug)

    title_safe = safe_yaml_str(artist_name)
    fm = [
        "---",
        f"title: '{title_safe} — {year}'",
        f"slug: '{artist_slug}'",
        f"date: {latest_date}",
        "layout: tune",
        "section: tunes",
        f"year: '{year}'",
        f"letter: '{letter}'",
        f"artist_slug: '{artist_slug}'",
        f"track_count: {len(tracks_sorted)}",
    ]
    if genre_list:
        fm.append("genre:")
        for g in genre_list:
            fm.append(f"  - '{safe_yaml_str(g)}'")
    if is_explicit:
        fm.append("explicit: true")
    fm.append("tags:")
    fm.append(f"  - '@{artist_slug}'")
    fm.append(f"  - '#tune'")
    fm.append(f"  - '#{year}'")
    fm.append("---")
    fm.append("")

    # Body — track list with embeds, chronological
    body_lines = []
    for t in tracks_sorted:
        track_title = t["track_name"]
        rd = t.get("release_date", "") or year
        body_lines.append(f"### {track_title}")
        body_lines.append(f"<span class='tune-date'>{rd}</span>")
        body_lines.append("")
        if t.get("uri") and ":" in t["uri"]:
            track_id = t["uri"].split(":")[-1]
            body_lines.append(
                f'<iframe src="https://open.spotify.com/embed/track/{track_id}" '
                f'width="100%" height="80" frameborder="0" '
                f'allow="encrypted-media" loading="lazy"></iframe>'
            )
        else:
            body_lines.append("<em>#NotOnSpotify</em>")
        body_lines.append("")

    body_lines.append("---")
    body_lines.append("")
    body_lines.append(f"[More by {artist_name} →](/{artist_slug}/)")
    body_lines.append("")

    return "\n".join(fm) + "\n" + "\n".join(body_lines)


def wipe_old_tunes(write):
    """Delete the 290 song-per-post tune files from the old model."""
    tunes_dir = Path("content/tunes")
    if not tunes_dir.exists():
        return 0
    deleted = 0
    for p in list(tunes_dir.iterdir()):
        if p.is_file() and p.suffix == ".md":
            if write:
                p.unlink()
            deleted += 1
    return deleted


def write_section_index(write):
    """Top-level /tunes/ index page."""
    tunes_dir = Path("content/tunes")
    if write:
        tunes_dir.mkdir(parents=True, exist_ok=True)
    index_path = tunes_dir / "_index.md"
    content = """---
title: 'Tunes'
description: 'Songs that earned a moment. Reverse chronological. Specimens.'
layout: tunes-list
---
"""
    if write:
        index_path.write_text(content, encoding="utf-8")
    return index_path


def write_year_index(year, write):
    """Year-level /tunes/2026/ index."""
    year_dir = Path(f"content/tunes/{year}")
    if write:
        year_dir.mkdir(parents=True, exist_ok=True)
    index_path = year_dir / "_index.md"
    content = f"""---
title: 'Tunes — {year}'
year: '{year}'
layout: tunes-year
---
"""
    if write:
        index_path.write_text(content, encoding="utf-8")
    return index_path


def main():
    args = sys.argv[1:]
    write = "--write" in args
    csv_dir = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--csv-dir" and i + 1 < len(args):
            csv_dir = args[i + 1]
            i += 2
        else:
            i += 1

    if not csv_dir:
        print('Usage: python nuke_and_regen_tunes.py --csv-dir "C:\\path" [--write]')
        sys.exit(1)

    mode = "WRITE" if write else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"NUKE + REGEN TUNES — {mode}")
    print(f"Years: {sorted(TARGET_YEARS)}")
    print(f"{'='*60}\n")

    print(f"Step 1: Wiping old single-song tune posts...")
    deleted = wipe_old_tunes(write)
    print(f"  {'(would delete)' if not write else 'deleted'}: {deleted} files\n")

    print(f"Step 2: Walking CSVs, grouping by (artist, year)...")
    grouped = collect_by_artist_year(csv_dir)
    by_year = defaultdict(int)
    for (slug, year), entry in grouped.items():
        by_year[year] += 1
    print(f"  Total artist-year combinations: {len(grouped)}")
    for y in sorted(by_year):
        print(f"    {y}: {by_year[y]} artists")
    print()

    print(f"Step 3: Writing tune pages...")
    pages_created = 0
    pages_per_year = defaultdict(int)
    for (artist_slug, year), entry in sorted(grouped.items()):
        artist_name = entry["display_name"]
        tracks = entry["tracks"]
        target_dir = Path(f"content/tunes/{year}/{artist_slug}")
        target_path = target_dir / "index.md"
        content = make_tune_page_content(artist_slug, artist_name, year, tracks)
        if write:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
        pages_created += 1
        pages_per_year[year] += 1
        if pages_created <= 8:
            print(f"  [NEW]  {target_path} ({len(tracks)} tracks)")
    if pages_created > 8:
        print(f"  ... ({pages_created - 8} more pages)")

    print(f"\nStep 4: Section index files...")
    section_idx = write_section_index(write)
    print(f"  {'(would write)' if not write else 'wrote'}: {section_idx}")
    for year in sorted(by_year):
        year_idx = write_year_index(year, write)
        print(f"  {'(would write)' if not write else 'wrote'}: {year_idx}")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  Old single-song tunes wiped: {deleted}")
    print(f"  New artist-year tune pages:  {pages_created}")
    for y in sorted(pages_per_year):
        print(f"    {y}: {pages_per_year[y]} pages")
    print()

    if not write:
        print("DRY RUN COMPLETE. To execute:")
        print(f'  python nuke_and_regen_tunes.py --csv-dir "{csv_dir}" --write')
    else:
        print("Done. Next steps:")
        print("  1. python rebuild_manifest.py        (rebuild homepage filter data)")
        print("  2. Apply the Hugo layout files (see hugo_tunes_setup.txt)")
        print("  3. git add -A && git commit -m 'feat: tunes by artist-year' && git push")


if __name__ == "__main__":
    main()
