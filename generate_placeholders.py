#!/usr/bin/env python3
"""
generate_placeholders.py

Reads audit.csv, dedupes by derived_artist, and writes one clean placeholder
post per artist into content/artists/<slug>/_index.md.

Hugo will serve these at /artists/<slug>/. No collision with content/posts/
or content/ root legacy files.

Safe to re-run: skips files that already exist (so you can edit a placeholder
manually and not lose your work on next run). Use --force to overwrite.

Usage:
    python generate_placeholders.py            # dry run (default)
    python generate_placeholders.py --write    # actually write files
    python generate_placeholders.py --write --force   # overwrite existing
"""
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict

AUDIT = Path("audit.csv")
OUT_DIR = Path("content/artists")

# slugs from the audit that aren't really artists - skip these
SKIP_SLUGS = {
    "blog-post",
    "",
}

# slugs that are obviously archive-section headers, not artists
ARCHIVE_PREFIXES = ("from-", "best-of-")

# regex matching the legacy "1off bucket" pages:
#   #-1off-1970s-1offs, a-2020s-1offs, b-dh-1offs, i-all-1offs, etc.
# pattern: starts with a single letter or '#', has era/section, ends in '1offs'
JUNK_BUCKET_RE = re.compile(
    r'^(#|[a-z])(-1off)?-(1900s|1960s|1970s|1980s|1990s|2000s|2010s|2020s|00s-10s|dh|all-1offs)-1offs$'
)

# also skip any slug that's just a single character (parses too aggressively)
def is_junk(slug):
    if len(slug) <= 1:
        return True
    if JUNK_BUCKET_RE.match(slug):
        return True
    return False

def title_from_slug(slug):
    """Convert 'a-tribe-called-quest' -> 'A Tribe Called Quest'.
    Handles edge cases: numbers, single letters, '4batz', '8ball-mjg'."""
    parts = slug.split("-")
    out = []
    for p in parts:
        if not p:
            continue
        # all-digit chunks stay as-is (4batz, 070, 8ball, 100, 21)
        if p.isdigit() or any(c.isdigit() for c in p):
            out.append(p)
        else:
            out.append(p.capitalize())
    return " ".join(out)

def first_letter_bucket(slug):
    """Filter axis: which letter folder this artist belongs to."""
    if not slug:
        return "#"
    c = slug[0].lower()
    if c.isalpha():
        return c.upper()
    return "#"

def infer_era_from_legacy(filename_slugs):
    """Look at all legacy filenames for an artist, guess which eras are present."""
    eras = set()
    joined = " ".join(filename_slugs).lower()
    if "2020" in joined or "-20s" in joined:
        eras.add("2020s")
    if any(x in joined for x in ["2010", "00s-10s", "00s10s", "-10s", "-2010s"]):
        eras.add("2000s-2010s")
    if any(x in joined for x in ["1900", "1990", "1980", "1970", "1960", "1950", "pre-2000", "archive"]):
        eras.add("1900s")
    return sorted(eras) if eras else ["uncategorized"]

def detect_dancehall(filename_slugs, titles):
    """Heuristic: any sign this artist is in your dancehall section."""
    text = " ".join(filename_slugs + titles).lower()
    keywords = ["dancehall", "reggae", "gaza", "vybz", "popcaan", "alkaline",
                "skillibeng", "chronic-law", "intence", "masicka"]
    return any(k in text for k in keywords)

def main():
    write = "--write" in sys.argv
    force = "--force" in sys.argv

    if not AUDIT.exists():
        print(f"ERROR: {AUDIT} not found. Run audit_posts.py first.")
        sys.exit(1)

    # group rows by derived_artist
    groups = defaultdict(list)
    junk_count = 0
    with AUDIT.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            artist = row["derived_artist"].strip()
            if not artist or artist in SKIP_SLUGS:
                continue
            if any(artist.startswith(p) for p in ARCHIVE_PREFIXES):
                continue
            if is_junk(artist):
                junk_count += 1
                continue
            groups[artist].append(row)

    print(f"Found {len(groups)} unique artists in audit.csv")
    print(f"Filtered out {junk_count} junk-bucket slugs")

    # generate
    created = 0
    skipped_exists = 0
    skipped_skip = 0
    written = []

    for slug, rows in sorted(groups.items()):
        # skip non-artist slugs we couldn't filter earlier
        if len(slug) < 2 and not slug.isdigit():
            skipped_skip += 1
            continue

        out_file = OUT_DIR / slug / "_index.md"

        if out_file.exists() and not force:
            skipped_exists += 1
            continue

        # gather data from legacy rows
        filename_slugs = [r["filename_slug"] for r in rows]
        titles = [r["yaml_title"] for r in rows if r["yaml_title"]]
        dates = [r["yaml_date"] for r in rows if r["yaml_date"]]
        legacy_paths = [r["filepath"] for r in rows]

        # earliest date wins
        date = min(dates) if dates else "2020-01-01"
        # strip time component if present
        date = re.match(r"\d{4}-\d{2}-\d{2}", date)
        date = date.group(0) if date else "2020-01-01"

        title = title_from_slug(slug)
        letter = first_letter_bucket(slug)
        eras = infer_era_from_legacy(filename_slugs)
        is_dancehall = detect_dancehall(filename_slugs, titles)

        # YAML front matter
        fm_lines = [
            "---",
            f'title: "{title}"',
            f'slug: "{slug}"',
            f'date: {date}',
            f'letter: "{letter}"',
            "era:",
        ]
        for e in eras:
            fm_lines.append(f'  - "{e}"')
        fm_lines.append("genre: []")
        if is_dancehall:
            fm_lines.append('section: "dancehall"')
        fm_lines += [
            'status: "placeholder"',
            "notonspotify: false",
            "legacy_files:",
        ]
        for p in legacy_paths:
            fm_lines.append(f'  - "{p}"')
        fm_lines.append("---")

        # body: minimal stub
        body_lines = [
            "",
            f"# {title}",
            "",
            "<!-- placeholder: backfill from Spotify CSV + #NotOnSpotify YouTube. -->",
            "",
            "<!-- legacy posts from blogspot/GPT/early-Claude eras are listed in front matter -->",
            "<!-- under legacy_files. Mine those for prose worth keeping. -->",
            "",
        ]

        content = "\n".join(fm_lines) + "\n" + "\n".join(body_lines)

        if write:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(content, encoding="utf-8")
        written.append(str(out_file).replace("\\", "/"))
        created += 1

    # report
    print(f"\n=== {'WRITTEN' if write else 'DRY RUN - would create'} ===")
    print(f"  Created:        {created}")
    print(f"  Skipped (exists): {skipped_exists}")
    print(f"  Skipped (junk):  {skipped_skip}")
    print(f"\nFirst 10 to be written:")
    for w in written[:10]:
        print(f"  {w}")
    if len(written) > 10:
        print(f"  ... and {len(written)-10} more")

    if not write:
        print("\nDry run only. To actually write files, run:")
        print("  python generate_placeholders.py --write")

if __name__ == "__main__":
    main()
