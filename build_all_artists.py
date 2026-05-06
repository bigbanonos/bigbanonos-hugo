#!/usr/bin/env python3
"""
build_all_artists.py

Walks your spotify_playlists folder, finds every per-artist CSV
(named like Artist_Name_-_N_Songs.csv or Artist_Name_-_XX_Songs.csv),
groups them by the first alphabetic letter of the artist name, and emits
26 aggregated files: All_artists_Aa.csv ... All_artists_Zz.csv (plus #
for numeric/symbol-prefix artists).

Skips files we don't want:
- Songs-* (those are 1-off bucket files, handled separately)
- Covers-* (covers buckets)
- *_All.csv (era-combined dupes)
- *_.csv (trailing-underscore variant dupes)
- All_artists_*.csv (our own output)
- *_wrapped.csv (year-end Spotify wrapped)
- zz-* (junk prefix)

Reads each per-artist CSV, copies all rows verbatim into the right
letter-bucket file. Headers are preserved from the first file written.

Usage:
    python build_all_artists.py "C:\\path\\to\\spotify_playlists"            # dry run
    python build_all_artists.py "C:\\path\\to\\spotify_playlists" --write    # do it
"""
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict

LEADING_THE = re.compile(r"^the[_\s-]+", re.IGNORECASE)

# Files we deliberately skip
SKIP_PREFIXES = ("Songs-", "Covers-", "All_artists_", "zz-", "zz_")
SKIP_PATTERNS = [
    re.compile(r"_All\.csv$", re.IGNORECASE),       # era-combined dupes
    re.compile(r"_wrapped\.csv$", re.IGNORECASE),   # year-end variants
    re.compile(r"_\.csv$"),                          # trailing-underscore dupes
]

ARTIST_FILE_RE = re.compile(
    r"^(.+?)_-_(?:\d+|XX|XXX|X+)_Songs?\.csv$",
    re.IGNORECASE,
)

def first_letter(name):
    """Get the bucket letter for an artist name. Drops leading 'The'."""
    if not name:
        return "#"
    s = LEADING_THE.sub("", name).strip()
    if not s:
        return "#"
    c = s[0].upper()
    if c.isalpha():
        return c
    return "#"

def parse_artist(filename):
    """Songs file like 'Hold_Steady_-_25_Songs.csv' -> 'Hold Steady'.
       Returns None if not a per-artist songpack."""
    m = ARTIST_FILE_RE.match(filename)
    if not m:
        return None
    raw = m.group(1)
    # Convert underscores back to spaces, but preserve hyphens within names
    name = raw.replace("_", " ").strip()
    return name

def is_skip(filename):
    for pfx in SKIP_PREFIXES:
        if filename.startswith(pfx):
            return True
    for pat in SKIP_PATTERNS:
        if pat.search(filename):
            return True
    return False

def main():
    args = sys.argv[1:]
    write = "--write" in args
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print('Usage: python build_all_artists.py "C:\\path\\to\\spotify_playlists" [--write]')
        sys.exit(1)
    src = Path(paths[0])
    if not src.exists():
        print(f"ERROR: {src} not found")
        sys.exit(1)

    # Group artist files by first letter
    by_letter = defaultdict(list)  # letter -> [(artist_name, file_path)]
    skipped = 0
    no_match = []

    for p in sorted(src.glob("*.csv")):
        if is_skip(p.name):
            skipped += 1
            continue
        artist = parse_artist(p.name)
        if not artist:
            no_match.append(p.name)
            continue
        letter = first_letter(artist)
        by_letter[letter].append((artist, p))

    print(f"Scanned {src}")
    print(f"  Skipped (Songs/Covers/All_artists/etc):  {skipped}")
    print(f"  Per-artist files matched:                 {sum(len(v) for v in by_letter.values())}")
    print(f"  Unmatched .csv files:                     {len(no_match)}")
    print()

    print("Per-letter counts:")
    for letter in sorted(by_letter.keys()):
        files = by_letter[letter]
        total_tracks = 0
        for artist, p in files:
            try:
                with open(p, encoding="utf-8-sig", newline="") as fh:
                    total_tracks += sum(1 for _ in csv.reader(fh)) - 1
            except Exception:
                pass
        print(f"  {letter}: {len(files):>3} artists, {total_tracks:>5} tracks")

    if no_match:
        print(f"\nFirst 15 unmatched files (would not be aggregated):")
        for f in no_match[:15]:
            print(f"  {f}")

    if not write:
        print("\nDry run. To actually emit All_artists_<letter>.csv files:")
        print(f'  python build_all_artists.py "{src}" --write')
        return

    # Actually write the aggregate files
    print("\nWriting...")
    written = 0
    for letter, files in sorted(by_letter.items()):
        out_path = src / f"All_artists_{letter}{letter.lower()}.csv"
        # Don't overwrite the existing All_artists_Hh.csv unless we have to
        # (preserve whatever editorial work has been done there)
        if out_path.exists() and letter == "H":
            print(f"  skip {out_path.name} (already exists, preserving)")
            continue

        rows_out = []
        header = None
        for artist, src_path in files:
            try:
                with open(src_path, encoding="utf-8-sig", newline="") as fh:
                    reader = csv.reader(fh)
                    h = next(reader, None)
                    if h is None:
                        continue
                    if header is None:
                        header = h
                    for row in reader:
                        rows_out.append(row)
            except Exception as e:
                print(f"    WARN reading {src_path.name}: {e}")

        if header is None:
            print(f"  skip {out_path.name} (no readable rows)")
            continue

        with out_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows_out)
        print(f"  wrote {out_path.name}: {len(rows_out)} rows from {len(files)} artists")
        written += 1

    print(f"\nDone. Wrote {written} aggregated CSVs.")

if __name__ == "__main__":
    main()
