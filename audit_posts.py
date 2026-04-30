#!/usr/bin/env python3
"""
audit_posts.py - READ ONLY. Produces audit.csv mapping every .md file in content/.

Usage (from repo root):
    python audit_posts.py

Output: audit.csv in repo root.
"""
import csv
import re
from pathlib import Path

ROOT = Path("content")
OUT = Path("audit.csv")

SONGCOUNT_RE = re.compile(r"-(\d+|xx)-songs?$", re.IGNORECASE)
TOPSONGS_RE = re.compile(r"-top-songs?$", re.IGNORECASE)
DEDUPE_RE = re.compile(r"_(\d+)$")
ARCHIVE_RE = re.compile(r"^from-\d+s-archive-", re.IGNORECASE)

def parse_front_matter(text):
    """Return (fm_dict, body) or ({}, text) if no front matter."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end+4:].lstrip("\n")
    fm = {}
    current_key = None
    for line in fm_text.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)$", line)
        if m and not line.startswith(" "):
            current_key = m.group(1)
            fm[current_key] = m.group(2).strip()
        elif current_key and line.startswith(" "):
            fm[current_key] = (fm[current_key] + " " + line.strip()).strip()
    return fm, body

def derive_artist_from_slug(slug):
    """Strip song count, top-songs, dedupe suffix, archive prefix."""
    s = slug
    s = ARCHIVE_RE.sub("", s)
    s = DEDUPE_RE.sub("", s)
    s = TOPSONGS_RE.sub("", s)
    s = SONGCOUNT_RE.sub("", s)
    return s

def detect_bugs(filename_slug, fm):
    flags = []
    if SONGCOUNT_RE.search(filename_slug):
        flags.append("SLUG_HAS_SONGCOUNT")
    if DEDUPE_RE.search(filename_slug):
        flags.append("SLUG_HAS_DEDUPE_SUFFIX")
    if TOPSONGS_RE.search(filename_slug):
        flags.append("SLUG_HAS_TOPSONGS")
    if ARCHIVE_RE.match(filename_slug):
        flags.append("SLUG_IS_ARCHIVE")
    title = fm.get("title", "")
    if title.count("'") >= 2 and ('"' in title):
        flags.append("TITLE_QUOTES_BROKEN")
    if not title:
        flags.append("TITLE_MISSING")
    if " - " in title and "Songs" in title:
        flags.append("TITLE_HAS_SONGCOUNT")
    if not fm.get("date"):
        flags.append("DATE_MISSING")
    if "slug" not in fm:
        flags.append("NO_SLUG_FIELD")
    return flags

def main():
    if not ROOT.exists():
        print(f"ERROR: {ROOT} does not exist. Run from repo root.")
        return

    rows = []
    md_files = list(ROOT.rglob("*.md"))
    print(f"Scanning {len(md_files)} .md files...")

    for path in md_files:
        rel = path.relative_to(".")
        # folder bucket
        parts = path.parts
        if len(parts) == 2:
            folder = "content_root"
        elif len(parts) >= 3 and parts[1] == "posts":
            folder = "posts"
        else:
            folder = "/".join(parts[1:-1])

        filename_slug = path.stem

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            rows.append({
                "filepath": str(rel).replace("\\", "/"),
                "folder": folder,
                "filename_slug": filename_slug,
                "yaml_title": f"READ_ERROR: {e}",
                "yaml_slug": "",
                "yaml_date": "",
                "yaml_tags_count": "",
                "derived_artist": "",
                "body_chars": 0,
                "bug_flags": "READ_ERROR",
            })
            continue

        fm, body = parse_front_matter(text)
        derived = derive_artist_from_slug(filename_slug)
        flags = detect_bugs(filename_slug, fm)

        tags_raw = fm.get("tags", "")
        tags_count = tags_raw.count("@") if tags_raw else 0

        rows.append({
            "filepath": str(rel).replace("\\", "/"),
            "folder": folder,
            "filename_slug": filename_slug,
            "yaml_title": fm.get("title", "")[:120],
            "yaml_slug": fm.get("slug", ""),
            "yaml_date": fm.get("date", ""),
            "yaml_tags_count": tags_count,
            "derived_artist": derived,
            "body_chars": len(body),
            "bug_flags": "|".join(flags),
        })

    # detect duplicates by derived_artist
    from collections import Counter
    artist_counts = Counter(r["derived_artist"] for r in rows if r["derived_artist"])
    for r in rows:
        if r["derived_artist"] and artist_counts[r["derived_artist"]] > 1:
            existing = r["bug_flags"]
            r["bug_flags"] = (existing + "|DUPLICATE_ARTIST") if existing else "DUPLICATE_ARTIST"

    fieldnames = ["filepath", "folder", "filename_slug", "yaml_title", "yaml_slug",
                  "yaml_date", "yaml_tags_count", "derived_artist", "body_chars", "bug_flags"]

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # summary
    print(f"\nWrote {len(rows)} rows to {OUT}")
    print(f"\n=== SUMMARY ===")
    print(f"Total .md files: {len(rows)}")
    by_folder = Counter(r["folder"] for r in rows)
    for k, v in sorted(by_folder.items()):
        print(f"  {k}: {v}")

    all_flags = []
    for r in rows:
        if r["bug_flags"]:
            all_flags.extend(r["bug_flags"].split("|"))
    flag_counts = Counter(all_flags)
    print(f"\nBug flags:")
    for flag, count in flag_counts.most_common():
        print(f"  {flag}: {count}")

    dupes = [a for a, c in artist_counts.items() if c > 1]
    print(f"\nDuplicate-artist groups: {len(dupes)}")
    print(f"Top 10 duplicates:")
    for a, c in artist_counts.most_common(10):
        if c > 1:
            print(f"  {a}: {c} files")

if __name__ == "__main__":
    main()
