#!/usr/bin/env python3
"""
strip_ai_slop.py

For each canonical post in content/ (NOT _legacy_dupes/), remove:
  - AI-generated intro paragraphs ("X has redefined Y with their powerful...")
  - "BigBanonos celebrates X" / "BigBanonos' Favorite Songs by X" headers
  - All bigbanonos.blogspot.com references and "first posted by" lines
  - "For more updates, visit..." promo blocks
  - "For more exclusive tracks not on Spotify, subscribe to..." promo blocks
  - Duplicate Tags: footer lines (the YAML tags are the source of truth)

Replace stripped intro with a placeholder comment prompting the BigBanonos voice.

Usage:
    python strip_ai_slop.py            # dry run
    python strip_ai_slop.py --write    # actually strip
"""
import re
import sys
from pathlib import Path

PLACEHOLDER = """<!-- BigBanonos voice goes here.
     - the personal connection (saw them live, friend's band, etc.)
     - the cross-reference (X covered Y, was in band Z, sampled by W)
     - the hot take (peaked 2006-2019, sucks since 2001, etc.)
     - what's missing / why these songs
     -->
"""

# patterns to strip (each is a regex matched against the body, MULTILINE+DOTALL where useful)
STRIP_PATTERNS = [
    # AI intro: <h3>BigBanonos Favorite Tracks: X</h3>
    (r"<h3>\s*BigBanonos[^<]*?(?:Favorite|favorite|Top|top)[^<]*?</h3>", "intro_h3"),
    # AI intro paragraph: <p>BigBanonos celebrates ...</p> through closing </p>
    (r"<p>\s*BigBanonos\s+celebrates.*?</p>", "celebrates_p"),
    # Markdown variant: ## BigBanonos' Favorite Songs by X  (one line)
    (r"^#{1,3}\s*BigBanonos[''']?s?\s+(?:Favorite|Top)[^\n]*\n?", "intro_md"),
    # First-posted-by lines (HTML or plain)
    (r"<p>\s*<em>\s*first posted by.*?</em>.*?</p>", "first_posted_html"),
    (r"\*?first posted by\*?\s*\[?https?://bigbanonos\.blogspot[^\n]*\n?", "first_posted_md"),
    (r"first posted by\s+https?://bigbanonos\.blogspot[^\n]*\n?", "first_posted_plain"),
    # "For more updates, visit BigBanonos blogspot..." block
    (r"<p>\s*For more updates,\s+visit.*?</p>", "more_updates_html"),
    (r"For more updates,\s+visit\s+\[BigBanonos\]\(https?://bigbanonos\.blogspot[^\n]*\n?", "more_updates_md"),
    # NotOnSpotify subscribe block (entire div)
    (r"<div>\s*<p>\s*For more exclusive tracks not on Spotify.*?</div>", "notonspotify_subscribe_div"),
    (r"<p>\s*For more exclusive tracks not on Spotify.*?</p>\s*<p>\s*<a href=[^>]*>Best Songs #NotOnSpotify[^<]*</a>[^<]*</p>", "notonspotify_subscribe_p"),
    # Markdown variant
    (r"For more exclusive tracks not on Spotify[^\n]*\n+\[Best Songs #NotOnSpotify[^\n]*\n?", "notonspotify_md"),
    # Bottom "Tags: @x, @y" duplicate of YAML tags (lowercase or capitalized)
    (r"<p>\s*[Tt]ags:\s*@[^<]*</p>", "tags_footer_html"),
    (r"^[Tt]ags:\s*@[^\n]*\n?", "tags_footer_md"),
    # Subscribe and Playlist Links comment + content
    (r"<!--\s*Subscribe and Playlist Links\s*-->", "subscribe_comment"),
    (r"<!--\s*Tags\s*-->", "tags_comment"),
    # Bare horizontal rules left over
    (r"<hr\s*/?>(\s*<hr\s*/?>)+", "<hr />"),  # collapse multiple hr
]

# patterns that mean "this post had AI intro stripped" - so we add the placeholder
TRIGGERS_PLACEHOLDER = {"intro_h3", "celebrates_p", "intro_md"}

def parse_front_matter(text):
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 4)
    if end == -1:
        return "", text
    return text[:end+4], text[end+4:].lstrip("\n")

def strip_body(body):
    """Apply all strip patterns. Returns (new_body, list_of_patterns_matched)."""
    matched = []
    for pat, name in STRIP_PATTERNS:
        if name == "<hr />":
            # special: this one has a replacement, not a strip
            new_body = re.sub(pat, "<hr />", body, flags=re.DOTALL)
            if new_body != body:
                matched.append(name)
                body = new_body
            continue
        flags = re.DOTALL | re.MULTILINE | re.IGNORECASE
        new_body, n = re.subn(pat, "", body, flags=flags)
        if n > 0:
            matched.append(name)
            body = new_body
    # collapse 3+ blank lines to 2
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n", matched

def main():
    write = "--write" in sys.argv

    # collect all canonical posts (in content/ but not in _legacy_dupes)
    files = []
    for p in Path("content").rglob("*.md"):
        if "_legacy_dupes" in p.parts:
            continue
        # skip the new placeholder pages at content/artists/ - those are already clean
        if "artists" in p.parts and p.name == "_index.md":
            continue
        files.append(p)

    print(f"Scanning {len(files)} canonical post files...")

    touched = 0
    placeholder_added = 0
    pattern_hits = {}

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")

        fm, body = parse_front_matter(text)
        new_body, matched = strip_body(body)

        if not matched:
            continue

        for m in matched:
            pattern_hits[m] = pattern_hits.get(m, 0) + 1

        # if we stripped an AI intro, add the placeholder at the top of body
        if any(m in TRIGGERS_PLACEHOLDER for m in matched):
            new_body = PLACEHOLDER + "\n" + new_body
            placeholder_added += 1

        new_text = fm + "\n\n" + new_body

        if new_text != text:
            touched += 1
            if write:
                path.write_text(new_text, encoding="utf-8")

    mode = "WRITTEN" if write else "DRY RUN"
    print(f"\n=== {mode} ===")
    print(f"  Files scanned:        {len(files)}")
    print(f"  Files touched:        {touched}")
    print(f"  Placeholders added:   {placeholder_added}")
    print(f"\nPattern hits (most common cruft):")
    for name, count in sorted(pattern_hits.items(), key=lambda x: -x[1]):
        print(f"  {name:30s} {count}")

    if not write:
        print("\nDry run only. To actually strip:")
        print("  python strip_ai_slop.py --write")

if __name__ == "__main__":
    main()
