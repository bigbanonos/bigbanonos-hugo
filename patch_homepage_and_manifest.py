#!/usr/bin/env python3
"""
patch_homepage_and_manifest.py

Three changes in one shot:
  1. Drops the stickman/money SVG mascot from layouts/index.html
  2. Updates layouts/index.html so the manifesto grid is single-column
     (no more right-side mascot column)
  3. Patches rebuild_manifest.py so 1off_bucket records get excluded
  4. Prints the exact 3-line config.toml change for adding Tunes to nav

Idempotent — safe to run twice. Refuses if it can't find anchor strings.

Usage:
    python patch_homepage_and_manifest.py            # dry run, shows what would change
    python patch_homepage_and_manifest.py --write    # do it
"""
import sys
import re
from pathlib import Path

INDEX_PATH = Path("layouts/index.html")
MANIFEST_SCRIPT = Path("rebuild_manifest.py")

# The mascot SVG block — from <svg class="bb-bike" through </svg>
# We delete this entire block.
MASCOT_PATTERN = re.compile(
    r'\s*<svg class="bb-bike".*?</svg>',
    re.DOTALL,
)

# The two-column manifesto layout (with --bb-bike column). We collapse to single-column.
MANIFESTO_GRID_OLD = ".bb-manifesto{display:grid;grid-template-columns:1fr auto;gap:28px;align-items:end;border-top:3px solid var(--ink);border-bottom:3px solid var(--ink);padding:18px 0;margin:8px 0 22px;}"
MANIFESTO_GRID_NEW = ".bb-manifesto{display:block;border-top:3px solid var(--ink);border-bottom:3px solid var(--ink);padding:18px 0;margin:8px 0 22px;}"

# Mobile rule also references bb-bike — we drop its rule too.
MOBILE_RULE_OLD = "@media (max-width:640px){.bb-manifesto{grid-template-columns:1fr;}.bb-bike{justify-self:end;}}"
MOBILE_RULE_NEW = ""

# bb-bike CSS rule (sizing for the SVG) — drop it
BIKE_RULE_OLD = ".bb-bike{width:clamp(120px,18vw,220px);}"
BIKE_RULE_NEW = ""

# rebuild_manifest.py patches:
# In process_artist_post, after we determine the post's kind from filename/context,
# we want to skip records where the post looks like a 1off_bucket. The current
# script only emits kind='artist' for posts. The 1off_bucket records come from the
# OLD manifest being merged. We need to NOT inherit those.
# The fix: filter the existing manifest lookup so 1off_bucket records are not
# included as a source.

MANIFEST_PATCH_OLD = """def load_existing_manifest():
    \"\"\"Read static/playlist_manifest.json and return dict keyed by name (lowercase).\"\"\"
    p = Path(\"static/playlist_manifest.json\")
    if not p.exists():
        return {}
    try:
        with open(p, encoding=\"utf-8\") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    out = {}
    for r in data:
        if not isinstance(r, dict):
            continue
        key = (r.get(\"name\", \"\") or \"\").lower().strip()
        if key:
            out[key] = r
    return out"""

MANIFEST_PATCH_NEW = """def load_existing_manifest():
    \"\"\"Read static/playlist_manifest.json and return dict keyed by name (lowercase).
    Excludes 1off_bucket and cover records — those should not be in the new manifest.\"\"\"
    p = Path(\"static/playlist_manifest.json\")
    if not p.exists():
        return {}
    try:
        with open(p, encoding=\"utf-8\") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    out = {}
    for r in data:
        if not isinstance(r, dict):
            continue
        # Skip vestigial bucket / cover records — they're replaced by individual tunes
        if r.get(\"kind\") in (\"1off_bucket\", \"cover\"):
            continue
        key = (r.get(\"name\", \"\") or \"\").lower().strip()
        if key:
            out[key] = r
    return out"""

TUNES_NAV_INSTRUCTIONS = """
============================================================
CONFIG.TOML MANUAL EDIT NEEDED
============================================================
Open config.toml and find the menu section. Add this block between
the Home and Tags entries (or wherever feels right):

  [[menu.main]]
    name = "Tunes"
    url = "/tunes/"
    weight = 2

And bump existing weights so the order stays Home, Tunes, Tags, Search:
  Home   = weight 1
  Tunes  = weight 2   (NEW)
  Tags   = weight 3   (was 2)
  Search = weight 4   (was 3)
============================================================
"""


def apply_patch(filepath, find, replace, label, write):
    if not filepath.exists():
        return f"MISS: {filepath} not found, skipping {label}"
    text = filepath.read_text(encoding="utf-8")
    if find not in text:
        if replace in text:
            return f"SKIP: {label} already applied to {filepath}"
        return f"FAIL: {label} anchor not found in {filepath}"
    new_text = text.replace(find, replace)
    if write:
        filepath.write_text(new_text, encoding="utf-8")
    return f"OK:   {label} → {filepath}"


def apply_regex(filepath, pattern, replacement, label, write):
    if not filepath.exists():
        return f"MISS: {filepath} not found, skipping {label}"
    text = filepath.read_text(encoding="utf-8")
    if not pattern.search(text):
        return f"SKIP: {label} pattern not found in {filepath} (maybe already removed)"
    new_text = pattern.sub(replacement, text)
    if write:
        filepath.write_text(new_text, encoding="utf-8")
    return f"OK:   {label} → {filepath}"


def main():
    write = "--write" in sys.argv
    print(f"\n{'='*60}")
    print(f"PATCH HOMEPAGE + MANIFEST — {'WRITE' if write else 'DRY RUN'}")
    print(f"{'='*60}\n")

    results = []
    # 1. Drop mascot SVG
    results.append(apply_regex(INDEX_PATH, MASCOT_PATTERN, "", "drop mascot SVG", write))
    # 2. Collapse manifesto grid to single column
    results.append(apply_patch(INDEX_PATH, MANIFESTO_GRID_OLD, MANIFESTO_GRID_NEW, "single-col manifesto", write))
    # 3. Drop mobile rule referencing bb-bike
    results.append(apply_patch(INDEX_PATH, MOBILE_RULE_OLD, MOBILE_RULE_NEW, "drop bb-bike mobile rule", write))
    # 4. Drop bb-bike size rule
    results.append(apply_patch(INDEX_PATH, BIKE_RULE_OLD, BIKE_RULE_NEW, "drop bb-bike CSS", write))
    # 5. Patch rebuild_manifest.py to exclude 1off_bucket
    results.append(apply_patch(MANIFEST_SCRIPT, MANIFEST_PATCH_OLD, MANIFEST_PATCH_NEW, "exclude 1off_bucket from manifest", write))

    for r in results:
        print(f"  {r}")

    print(TUNES_NAV_INSTRUCTIONS)

    if not write:
        print("DRY RUN. To apply: re-run with --write")
        print()
        print("After --write, also do:")
        print("  1. Edit config.toml per the Tunes nav instructions above")
        print("  2. python rebuild_manifest.py --write")
        print("  3. git add -A && git commit -m 'cleanup: drop mascot + 1off buckets + tunes nav' && git push")


if __name__ == "__main__":
    main()
