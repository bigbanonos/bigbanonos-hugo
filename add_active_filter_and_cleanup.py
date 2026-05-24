#!/usr/bin/env python3
"""
add_active_filter_and_cleanup.py (v2)

Custom-patched against the actual layouts/index.html structure.

Three changes in one shot:
  1. Deletes 71 orphan 1off bucket post files (404 sources)
  2. Adds two new pills (Active / Inactive) to the existing type-row in the
     bb-filters bar — appended after the Type group
  3. Extends the JS filters object with an "active" Set
  4. Adds an 'active' filter check to apply()
  5. Wires the new pills through the existing bindToggle() helper

Idempotent. Safe to re-run.

Usage:
    python add_active_filter_and_cleanup.py            # dry run
    python add_active_filter_and_cleanup.py --write    # apply
"""
import sys
import re
from pathlib import Path

INDEX_PATH = Path("layouts/index.html")
POSTS_DIR = Path("content/posts")

BUCKET_PATTERNS = [
    "#-1off-*.md",
    "*-1off-*.md",
    "#-all-1offs-*.md",
]

SENTINEL = "data-active"  # appears in our new pill markup once applied

# Anchor 1: insert pills before Reset button.
ANCHOR_RESET = '<button class="pill clear" id="bbClear">Reset</button>'
INSERT_PILLS = '''<span class="lbl" style="margin-left:18px;">Status</span>
    <button class="pill active" data-active="active">Active</button>
    <button class="pill active" data-active="inactive">Inactive</button>
    <button class="pill clear" id="bbClear">Reset</button>'''

# Anchor 2: extend the filters object to include active Set.
ANCHOR_FILTERS = "var filters={era:new Set(),type:new Set(),genre:new Set(),letter:null};"
INSERT_FILTERS = "var filters={era:new Set(),type:new Set(),genre:new Set(),active:new Set(),letter:null};"

# Anchor 3: add 'active' filter logic inside apply().
ANCHOR_APPLY = "var genreOk=(filters.genre.size===0)||cardGenres.some(function(g){return filters.genre.has(g);});"
INSERT_APPLY = '''var genreOk=(filters.genre.size===0)||cardGenres.some(function(g){return filters.genre.has(g);});
      var activeOk=(filters.active.size===0)||(filters.active.has(c.dataset.active));'''

# Anchor 4: include activeOk in the final 'ok' check
ANCHOR_OK = "var ok=eraOk&&typeOk&&letterOk&&genreOk;"
INSERT_OK = "var ok=eraOk&&typeOk&&letterOk&&genreOk&&activeOk;"

# Anchor 5: add data-active attribute to card HTML so we can filter on it.
# We anchor on the data-type attribute since it's a stable, unique landmark.
ANCHOR_CARD = '" data-type="\'+r.kind+\'" data-genres="'
INSERT_CARD = '" data-type="\'+r.kind+\'" data-active="\'+(r.active===true?\'active\':\'inactive\')+\'" data-genres="'

# Anchor 6: bind the new pill row through bindToggle (using data-active)
ANCHOR_BIND = "bindToggle('.pill.genre','genre');"
INSERT_BIND = '''bindToggle('.pill.genre','genre');
  bindToggle('.pill.active','active');'''

# Anchor 7: bindToggle uses btn.dataset[kind==='genre'?'g':kind] -- works because
# data-active="active" maps via dataset.active. But the helper only handles
# 'genre' as special. We extend the helper to know about 'active' too.
# Looking at the helper:
ANCHOR_HELPER = "var val=btn.dataset[kind==='genre'?'g':kind];"
INSERT_HELPER = "var val=btn.dataset[kind==='genre'?'g':(kind==='active'?'active':kind)];"

# Anchor 8: include filters.active in the Reset clear handler.
ANCHOR_CLEAR = "filters.era.clear();filters.type.clear();filters.genre.clear();filters.letter=null;"
INSERT_CLEAR = "filters.era.clear();filters.type.clear();filters.genre.clear();filters.active.clear();filters.letter=null;"

# CSS: style the new active pill row similar to type but with plum
ANCHOR_CSS = ".pill.type[aria-pressed=\"true\"]{background:var(--hot);color:#fff;border-color:var(--hot);}"
INSERT_CSS = """.pill.type[aria-pressed="true"]{background:var(--hot);color:#fff;border-color:var(--hot);}
  .pill.active[aria-pressed="true"]{background:var(--plum);color:#fff;border-color:var(--plum);}"""


def find_bucket_files():
    if not POSTS_DIR.exists():
        return []
    found = set()
    for pat in BUCKET_PATTERNS:
        for p in POSTS_DIR.glob(pat):
            found.add(p)
    # And era-letter buckets like "a-1900s-1offs.md", "a-2020s-1offs.md", "a-00s-10s-1offs.md"
    extra_re = re.compile(r"^[a-z]-(?:1900s|2020s|00s-10s)-1offs\.md$", re.IGNORECASE)
    for p in POSTS_DIR.glob("*.md"):
        if extra_re.match(p.name):
            found.add(p)
    return sorted(found)


def patch_text(text, find, replace, label, allow_multiple=False):
    if find not in text:
        if replace in text:
            return text, f"SKIP: {label} already applied"
        return text, f"FAIL: {label} anchor not found"
    occurrences = text.count(find)
    if occurrences > 1 and not allow_multiple:
        return text, f"WARN: {label} anchor appears {occurrences} times — refusing ambiguous patch"
    return text.replace(find, replace, 1), f"OK:   {label}"


def main():
    write = "--write" in sys.argv
    print(f"\n{'='*60}")
    print(f"ACTIVE FILTER + BUCKET CLEANUP — {'WRITE' if write else 'DRY RUN'}")
    print(f"{'='*60}\n")

    # ----- Step 1: bucket file cleanup -----
    bucket_files = find_bucket_files()
    print(f"Step 1: Bucket file cleanup")
    print(f"  Found {len(bucket_files)} orphan bucket files")
    if bucket_files[:10]:
        for p in bucket_files[:10]:
            print(f"    - {p.name}")
        if len(bucket_files) > 10:
            print(f"    ... and {len(bucket_files) - 10} more")
    if write:
        for p in bucket_files:
            try:
                p.unlink()
            except Exception as e:
                print(f"    FAIL: couldn't delete {p.name}: {e}")
        print(f"  Deleted: {len(bucket_files)} files")
    else:
        print(f"  (dry run — no files deleted)")
    print()

    # ----- Steps 2-8: homepage patches -----
    if not INDEX_PATH.exists():
        print(f"ERROR: {INDEX_PATH} not found")
        sys.exit(1)

    text = INDEX_PATH.read_text(encoding="utf-8")

    if SENTINEL in text:
        print(f"Step 2: Homepage patches already applied (sentinel found)")
        if write:
            print("       (no changes to homepage)")
        return

    print(f"Step 2: Homepage patches")
    patches = [
        (ANCHOR_RESET, INSERT_PILLS, "Active/Inactive pills HTML"),
        (ANCHOR_FILTERS, INSERT_FILTERS, "filters object includes active Set"),
        (ANCHOR_APPLY, INSERT_APPLY, "active filter logic in apply()"),
        (ANCHOR_OK, INSERT_OK, "include activeOk in ok check"),
        (ANCHOR_CARD, INSERT_CARD, "data-active attribute on cards"),
        (ANCHOR_BIND, INSERT_BIND, "bindToggle for active pills"),
        (ANCHOR_HELPER, INSERT_HELPER, "bindToggle helper knows active"),
        (ANCHOR_CLEAR, INSERT_CLEAR, "include filters.active in Reset"),
        (ANCHOR_CSS, INSERT_CSS, "Active pill plum styling"),
    ]

    all_ok = True
    for find, replace, label in patches:
        text, result = patch_text(text, find, replace, label)
        print(f"  {result}")
        if result.startswith("FAIL") or result.startswith("WARN"):
            all_ok = False

    if write and all_ok:
        INDEX_PATH.write_text(text, encoding="utf-8")
        print(f"\n  Wrote: {INDEX_PATH}")

    print()

    if not write:
        if all_ok:
            print(f"{'='*60}")
            print(f"All anchors found. Safe to write.")
            print(f"Re-run with --write to apply.")
            print(f"{'='*60}")
        else:
            print(f"{'='*60}")
            print(f"Some anchors failed. Don't write yet — paste output.")
            print(f"{'='*60}")
    else:
        if not all_ok:
            print(f"{'='*60}")
            print(f"Bucket files deleted but homepage patches had failures.")
            print(f"Re-run with corrected anchors.")
            print(f"{'='*60}")
        else:
            print(f"{'='*60}")
            print(f"DONE. Then:")
            print(f"  git add -A")
            print(f"  git commit -m 'feat: ACTIVE/INACTIVE filter + bucket cleanup'")
            print(f"  git push")
            print(f"{'='*60}")


if __name__ == "__main__":
    main()
