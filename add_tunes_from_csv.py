#!/usr/bin/env python3
"""
add_tunes_from_csv.py

Takes a CSV with the standard Exportify schema and creates / updates
tune pages at content/tunes/<year>/<artist>/index.md.

Behavior:
  - Tracks from any year (1977, 1996, 2026 — all good)
  - If /tunes/<year>/<artist>/ already exists, APPENDS new tracks to it
    (deduplicating by Spotify URI)
  - Page date = latest track release date for that artist+year
  - Tags merged across all tracks for that artist+year

Source-of-truth rule for "main artist":
  - Reads the entire CSV row by row
  - For each track, the first semicolon-separated artist is the main artist
    UNLESS the track URI is in MANUAL_OVERRIDES (hand-curated edge cases)
  - For tracks in this CSV (free-form Sheet 1, not per-artist file),
    fall-through is fine

Manual overrides: edit MANUAL_OVERRIDES below before running for known
misattributions (e.g. featured-artist credit when the song really belongs
to the featured artist's discography).

Usage:
    python add_tunes_from_csv.py PATH_TO_CSV               # dry run
    python add_tunes_from_csv.py PATH_TO_CSV --write       # do it
"""
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict

LEADING_THE = re.compile(r"^the[-\s_]+", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")

# Explicit overrides for misattributed tracks.
# Key = Spotify track URI. Value = the artist name to use as main.
MANUAL_OVERRIDES = {
    # Example: if you ever want to override, format is:
    # "spotify:track:XXXXX": "Father Philis",
}

# Known artist-name aliases — fold variants together
ARTIST_ALIASES = {
    "rosalía": "Rosalía",
    "rosalia": "Rosalía",
    "rosalã­a": "Rosalía",
}


def canonicalize(name):
    if not name:
        return ""
    s = LEADING_THE.sub("", name.strip())
    folds = {
        "ü": "u", "ö": "o", "ä": "a", "é": "e", "è": "e", "ê": "e",
        "á": "a", "à": "a", "ó": "o", "ò": "o", "ñ": "n", "ç": "c",
        "í": "i", "ú": "u", "ø": "o", "å": "a", "ß": "ss",
    }
    for k, v in folds.items():
        s = s.replace(k, v)
    s = NON_ALNUM.sub("-", s).strip("-").lower()
    return s


def get_main_artist(row):
    """Apply override > first semicolon name."""
    uri = row.get("Track URI", "")
    if uri in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[uri]
    field = row.get("Artist Name(s)", "") or ""
    primary = field.split(";")[0].strip()
    # Apply alias normalization
    if primary.lower() in ARTIST_ALIASES:
        return ARTIST_ALIASES[primary.lower()]
    return primary


def get_year(release_date):
    if not release_date or len(release_date) < 4:
        return None
    y = release_date[:4]
    if y.isdigit() and 1900 <= int(y) <= 2100:
        return y
    return None


def safe_yaml_str(s):
    return s.replace("'", "''").replace("\n", " ").replace("\r", "").strip()


def first_letter(slug):
    if not slug:
        return "#"
    c = slug[0].upper()
    return c if c.isalpha() else "#"


def parse_existing_tune(path):
    """Read an existing tune page, extract Spotify URIs already embedded."""
    if not path.exists():
        return set()
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return set()
    return set(re.findall(r"open\.spotify\.com/embed/track/([A-Za-z0-9]+)", text))


def build_tune_content(artist_slug, artist_name, year, all_tracks):
    """Build full tune-page markdown from the full track list (sorted)."""
    def sort_key(t):
        return t.get("release_date", "9999-99-99")

    tracks_sorted = sorted(all_tracks, key=sort_key)

    latest = max((t.get("release_date", "") for t in tracks_sorted if t.get("release_date")),
                 default=f"{year}-12-31")
    if len(latest) == 7:
        latest += "-01"
    elif len(latest) == 4:
        latest += "-01-01"

    genre_set = []
    for t in tracks_sorted:
        for g in (t.get("genres") or "").lower().split(","):
            g = g.strip()
            if g and g not in genre_set:
                genre_set.append(g)
    genre_list = genre_set[:6]
    is_explicit = any(t.get("explicit") for t in tracks_sorted)
    letter = first_letter(artist_slug)

    fm = [
        "---",
        f"title: '{safe_yaml_str(artist_name)} — {year}'",
        f"slug: '{artist_slug}'",
        f"date: {latest}",
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

    body = []
    for t in tracks_sorted:
        body.append(f"### {t['track_name']}")
        body.append(f"<span class='tune-date'>{t.get('release_date', year)}</span>")
        body.append("")
        if t.get("uri") and ":" in t["uri"]:
            tid = t["uri"].split(":")[-1]
            body.append(
                f'<iframe src="https://open.spotify.com/embed/track/{tid}" '
                f'width="100%" height="80" frameborder="0" '
                f'allow="encrypted-media" loading="lazy"></iframe>'
            )
        else:
            body.append("<em>#NotOnSpotify</em>")
        body.append("")

    body.append("---")
    body.append("")
    body.append(f"[More by {artist_name} →](/{artist_slug}/)")
    body.append("")

    return "\n".join(fm) + "\n" + "\n".join(body)


def extract_existing_tracks(path):
    """Read existing tune page, extract minimal track info to merge with new."""
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    tracks = []
    # Find all ### Track Name blocks with following date span and iframe
    blocks = re.split(r"\n###\s+", text)
    for block in blocks[1:]:  # first block is front matter + intro
        lines = block.split("\n")
        if not lines:
            continue
        track_name = lines[0].strip()
        if track_name.startswith("---") or not track_name:
            continue
        # Find date and uri
        rd_match = re.search(r"<span class='tune-date'>([^<]+)</span>", block)
        uri_match = re.search(r"open\.spotify\.com/embed/track/([A-Za-z0-9]+)", block)
        rd = rd_match.group(1) if rd_match else ""
        uri = f"spotify:track:{uri_match.group(1)}" if uri_match else ""
        if track_name and (uri or rd):
            tracks.append({
                "track_name": track_name,
                "uri": uri,
                "release_date": rd,
                "genres": "",  # we'll re-merge from new CSV
                "explicit": False,
            })
    return tracks


def main():
    args = sys.argv[1:]
    write = "--write" in args
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print("Usage: python add_tunes_from_csv.py PATH_TO_CSV [--write]")
        sys.exit(1)
    csv_path = Path(paths[0])
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)

    mode = "WRITE" if write else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"ADD TUNES FROM CSV — {mode}")
    print(f"Source: {csv_path}")
    print(f"{'='*60}\n")

    # Read CSV
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    print(f"Rows in CSV: {len(rows)}\n")

    # Group by (artist_slug, year)
    grouped = defaultdict(lambda: {"display_name": "", "tracks": []})
    skipped = 0
    for r in rows:
        rd = (r.get("Release Date", "") or "").strip()
        year = get_year(rd)
        if not year:
            skipped += 1
            continue
        artist_name = get_main_artist(r)
        if not artist_name:
            skipped += 1
            continue
        artist_slug = canonicalize(artist_name)
        if not artist_slug:
            skipped += 1
            continue
        track_name = (r.get("Track Name", "") or "").strip()
        if not track_name:
            skipped += 1
            continue

        key = (artist_slug, year)
        entry = grouped[key]
        if not entry["display_name"]:
            entry["display_name"] = artist_name
        entry["tracks"].append({
            "track_name": track_name,
            "uri": r.get("Track URI", "") or "",
            "release_date": rd,
            "genres": r.get("Genres", "") or "",
            "explicit": str(r.get("Explicit", "")).lower() == "true",
        })

    print(f"Grouped into {len(grouped)} (artist, year) combinations")
    print(f"Skipped: {skipped}")
    print()

    # Process each group: merge with existing if needed, write
    pages_created = 0
    pages_updated = 0
    by_year = defaultdict(int)

    for (artist_slug, year), entry in sorted(grouped.items()):
        target_dir = Path(f"content/tunes/{year}/{artist_slug}")
        target_path = target_dir / "index.md"

        existing_uris = parse_existing_tune(target_path)
        new_tracks = entry["tracks"]
        new_uris = {t["uri"] for t in new_tracks if t.get("uri")}

        if target_path.exists():
            # Merge: keep existing tracks, add only new ones (by URI)
            existing_tracks = extract_existing_tracks(target_path)
            tracks_to_add = [t for t in new_tracks
                             if t.get("uri") and t["uri"].split(":")[-1] not in existing_uris]
            if not tracks_to_add:
                continue  # no new content
            all_tracks = existing_tracks + tracks_to_add
            action = "UPDATED"
            pages_updated += 1
        else:
            all_tracks = new_tracks
            action = "CREATED"
            pages_created += 1

        by_year[year] += 1
        content = build_tune_content(artist_slug, entry["display_name"], year, all_tracks)

        if write:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

        if pages_created + pages_updated <= 12:
            n_added = len(new_tracks) if action == "CREATED" else len(tracks_to_add)
            print(f"  [{action[:3]}]  {target_path}  ({n_added} new tracks)")

    if pages_created + pages_updated > 12:
        print(f"  ... ({pages_created + pages_updated - 12} more pages)")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  Pages created: {pages_created}")
    print(f"  Pages updated: {pages_updated}")
    print(f"  By year:")
    for y in sorted(by_year):
        print(f"    {y}: {by_year[y]}")
    print()
    if not write:
        print(f"DRY RUN. To write:")
        print(f'  python add_tunes_from_csv.py "{csv_path}" --write')
    else:
        print("Done. Then:")
        print("  python rebuild_manifest.py --write")
        print("  git add -A && git commit -m 'add: april+may 2026 tunes' && git push")


if __name__ == "__main__":
    main()
