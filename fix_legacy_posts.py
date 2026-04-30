#!/usr/bin/env python3
"""
fix_legacy_posts.py

For each artist in audit.csv:
  1. Pick the NEWEST file (by yaml_date) as canonical.
  2. Move all other files for that artist to _legacy_dupes/.
  3. Rewrite the survivor's YAML: clean title, add slug, preserve date+tags.
  4. Body content untouched.

Usage:
    python fix_legacy_posts.py            # dry run
    python fix_legacy_posts.py --write    # actually do it
"""
import csv
import re
import shutil
import sys
from pathlib import Path
from collections import defaultdict

AUDIT = Path("audit.csv")
DUPES_DIR = Path("_legacy_dupes")

# same junk filters as generate_placeholders.py
JUNK_BUCKET_RE = re.compile(
    r'^(#|[a-z])(-1off)?-(1900s|1960s|1970s|1980s|1990s|2000s|2010s|2020s|00s-10s|dh|all-1offs)-1offs$'
)
ARCHIVE_PREFIXES = ("from-", "best-of-", "songs-")

def is_junk(slug):
    if not slug or len(slug) <= 1:
        return True
    if JUNK_BUCKET_RE.match(slug):
        return True
    if any(slug.startswith(p) for p in ARCHIVE_PREFIXES):
        return True
    if "1offs" in slug and "-" in slug:
        return True
    return False

def title_from_slug(slug):
    """100-gecs -> 100 Gecs, a-tribe-called-quest -> A Tribe Called Quest"""
    out = []
    for p in slug.split("-"):
        if not p:
            continue
        if p.isdigit() or any(c.isdigit() for c in p):
            out.append(p)
        else:
            out.append(p.capitalize())
    return " ".join(out)

def parse_front_matter(text):
    """Return (raw_fm_text, body) - keep raw fm so we can preserve fields."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 4)
    if end == -1:
        return "", text
    return text[4:end], text[end+4:].lstrip("\n")

def extract_field(fm_text, key):
    """Pull a single-line field from raw front matter. Returns '' if missing."""
    pattern = re.compile(rf'^{re.escape(key)}:\s*(.*?)$', re.MULTILINE)
    m = pattern.search(fm_text)
    return m.group(1).strip() if m else ""

def extract_tags_block(fm_text):
    """Extract the full tags: block (multi-line list). Returns the lines as a string."""
    lines = fm_text.splitlines()
    out = []
    in_tags = False
    for line in lines:
        if line.startswith("tags:"):
            in_tags = True
            out.append(line)
            continue
        if in_tags:
            # tag list items are indented
            if line.startswith(("  ", "\t", "- ")) or line.strip().startswith("-"):
                out.append(line)
            elif line.strip() == "":
                continue
            else:
                # next field; tags block ended
                break
    return "\n".join(out)

def build_clean_fm(slug, original_fm):
    """Construct fresh front matter with clean title + slug, preserving date and tags."""
    title = title_from_slug(slug)
    date = extract_field(original_fm, "date") or "2020-01-01"
    # strip time component if present
    date_match = re.match(r"\d{4}-\d{2}-\d{2}", date)
    date = date_match.group(0) if date_match else "2020-01-01"

    tags_block = extract_tags_block(original_fm)

    lines = [
        "---",
        f'title: "{title}"',
        f'slug: "{slug}"',
        f'date: {date}',
        'layout: post',
    ]
    if tags_block:
        lines.append(tags_block)
    lines.append("---")
    return "\n".join(lines)

def main():
    write = "--write" in sys.argv

    if not AUDIT.exists():
        print(f"ERROR: {AUDIT} not found. Run audit_posts.py first.")
        sys.exit(1)

    # group rows by artist, filter junk
    groups = defaultdict(list)
    for row in csv.DictReader(AUDIT.open(encoding="utf-8")):
        artist = row["derived_artist"].strip()
        if not artist or is_junk(artist):
            continue
        groups[artist].append(row)

    print(f"Processing {len(groups)} artists from audit.csv")

    survivors = 0
    moved_to_dupes = 0
    yaml_fixed = 0
    skipped_missing = 0

    for slug, rows in sorted(groups.items()):
        # sort by date, newest first; tiebreak by body_chars desc
        rows.sort(
            key=lambda r: (r.get("yaml_date", ""), int(r.get("body_chars") or 0)),
            reverse=True,
        )
        survivor = rows[0]
        losers = rows[1:]

        # move losers
        for loser in losers:
            src = Path(loser["filepath"])
            if not src.exists():
                skipped_missing += 1
                continue
            dst = DUPES_DIR / src.relative_to("content") if str(src).startswith("content") else DUPES_DIR / src.name
            if write:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
            moved_to_dupes += 1

        # fix survivor YAML
        src = Path(survivor["filepath"])
        if not src.exists():
            skipped_missing += 1
            continue
        survivors += 1

        try:
            text = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = src.read_text(encoding="utf-8", errors="replace")

        original_fm, body = parse_front_matter(text)
        new_fm = build_clean_fm(slug, original_fm)
        new_text = new_fm + "\n\n" + body

        if new_text != text:
            if write:
                src.write_text(new_text, encoding="utf-8")
            yaml_fixed += 1

    mode = "WRITTEN" if write else "DRY RUN"
    print(f"\n=== {mode} ===")
    print(f"  Survivors (canonical per artist): {survivors}")
    print(f"  YAML rewrites needed:             {yaml_fixed}")
    print(f"  Files moved to _legacy_dupes/:    {moved_to_dupes}")
    print(f"  Skipped (file missing on disk):   {skipped_missing}")

    if not write:
        print("\nDry run only. To actually do it:")
        print("  python fix_legacy_posts.py --write")

if __name__ == "__main__":
    main()
