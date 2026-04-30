#!/usr/bin/env python3
"""
clean_bodies.py

Per JOFALLON's MOVE FORWARD directive: keep posts SPARSE.
Strip from every canonical post body:
  - numbered tracklists (<ol>...</ol> blocks)
  - markdown numbered lists that look like tracklists
  - ALL apostrophes (', ', `, ', ´) - they're noise
  - broken {{< youtube "embed" >}} calls (no video ID = useless)
  - empty <div class="separator"> wrappers around dead images
  - "Top Songs:" / "Featured Video:" labels that label nothing

Leave intact:
  - working {{< youtube "REAL_VIDEO_ID" >}} shortcodes
  - working spotify embed iframes
  - working <img> tags with valid src
  - any prose that doesn't match a strip pattern

Usage:
    python clean_bodies.py            # dry run
    python clean_bodies.py --write    # actually clean
"""
import re
import sys
from pathlib import Path

def parse_front_matter(text):
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 4)
    if end == -1:
        return "", text
    return text[:end+4], text[end+4:].lstrip("\n")

# tracks list as HTML <ol>...</ol> - greedy match
HTML_OL_RE = re.compile(r"<ol\b[^>]*>.*?</ol>", re.IGNORECASE | re.DOTALL)

# tracks list as <ul> with <li><strong>...</strong> ... year ... label ...
HTML_UL_TRACK_RE = re.compile(
    r"<ul\b[^>]*>(?:\s*<li>[^<]*<strong>[^<]*</strong>[^<]*</li>\s*)+</ul>",
    re.IGNORECASE | re.DOTALL
)

# markdown numbered tracklist (3+ consecutive lines starting with "1. ", "2. " etc.)
MD_TRACKLIST_RE = re.compile(
    r"(?:^[ \t]*\d+\.\s+[^\n]+\n){3,}",
    re.MULTILINE
)

# broken youtube shortcode with literal "embed" or empty string
BROKEN_YT_RE = re.compile(
    r'\{\{<\s*youtube\s+"(?:embed|)"\s*>\}\}',
    re.IGNORECASE
)

# the separator div wrapper - whether it has content or not, this is blogspot cruft
SEPARATOR_DIV_RE = re.compile(
    r'<div class="separator"[^>]*>.*?</div>',
    re.IGNORECASE | re.DOTALL
)

# label-only paragraphs (no actual content following)
LABEL_ONLY_RE = re.compile(
    r"<p>\s*(?:Top Songs|Featured Video|Watch the official video[^<]*?):\s*</p>",
    re.IGNORECASE
)

# all apostrophe variants
APOSTROPHES = ["'", "'", "`", "'", "´", "ʼ"]

def clean_body(body):
    """Apply all body-strip rules. Returns (new_body, hits_dict)."""
    hits = {}

    def sub_count(pattern, replacement, text, name):
        new_text, n = pattern.subn(replacement, text)
        if n > 0:
            hits[name] = hits.get(name, 0) + n
        return new_text

    body = sub_count(HTML_OL_RE, "", body, "html_ol_tracklist")
    body = sub_count(HTML_UL_TRACK_RE, "", body, "html_ul_tracklist")
    body = sub_count(MD_TRACKLIST_RE, "", body, "md_tracklist")
    body = sub_count(BROKEN_YT_RE, "", body, "broken_youtube_embed")
    body = sub_count(SEPARATOR_DIV_RE, "", body, "separator_div")
    body = sub_count(LABEL_ONLY_RE, "", body, "label_only_p")

    # apostrophes - count once, strip all
    apos_count = 0
    for a in APOSTROPHES:
        apos_count += body.count(a)
        body = body.replace(a, "")
    if apos_count > 0:
        hits["apostrophes_stripped"] = apos_count

    # collapse 3+ blank lines to 2
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n", hits

def main():
    write = "--write" in sys.argv

    files = []
    for p in Path("content").rglob("*.md"):
        if "_legacy_dupes" in p.parts:
            continue
        files.append(p)

    print(f"Scanning {len(files)} canonical post files...")

    files_changed = 0
    pattern_totals = {}

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")

        fm, body = parse_front_matter(text)
        new_body, hits = clean_body(body)
        new_text = fm + "\n\n" + new_body

        if not hits:
            continue

        for k, v in hits.items():
            pattern_totals[k] = pattern_totals.get(k, 0) + v

        if new_text != text:
            files_changed += 1
            if write:
                path.write_text(new_text, encoding="utf-8")

    mode = "WRITTEN" if write else "DRY RUN"
    print(f"\n=== {mode} ===")
    print(f"  Files scanned: {len(files)}")
    print(f"  Files changed: {files_changed}")
    print(f"\nWhat was removed:")
    for name, count in sorted(pattern_totals.items(), key=lambda x: -x[1]):
        print(f"  {name:30s} {count}")

    if not write:
        print("\nDry run only. To actually clean:")
        print("  python clean_bodies.py --write")

if __name__ == "__main__":
    main()
