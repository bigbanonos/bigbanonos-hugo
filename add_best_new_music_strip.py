#!/usr/bin/env python3
"""
add_best_new_music_strip.py

Injects a 'BEST NEW MUSIC' strip into layouts/index.html, positioned between
the manifesto and the era/type filter pills.

The strip shows the 6 most-recent tune pages (by .Date desc) as cards, with
a "see all →" link to /tunes/.

Idempotent — safe to run twice. Refuses if anchor not found.

Usage:
    python add_best_new_music_strip.py           # dry run
    python add_best_new_music_strip.py --write   # apply
"""
import sys
from pathlib import Path

INDEX_PATH = Path("layouts/index.html")

# Anchor: the start of the era/type filter row.
# We inject BEFORE this line.
ANCHOR = '  <div class="bb-filters" id="bbFilters">'

# Sentinel string to detect if patch already applied
SENTINEL = 'bb-bnm-strip'

# CSS for the strip
STRIP_CSS = """
  /* BEST NEW MUSIC strip */
  .bb-bnm{margin:0 0 28px;border-top:3px solid var(--ink);padding-top:18px;}
  .bb-bnm-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:14px;gap:16px;flex-wrap:wrap;}
  .bb-bnm-title{font-family:"Archivo Black",sans-serif;font-size:clamp(22px,3.2vw,40px);line-height:1;letter-spacing:-.02em;text-transform:uppercase;margin:0;}
  .bb-bnm-title .acid{background:var(--acid);padding:0 .15em;}
  .bb-bnm-seeall{font-family:"JetBrains Mono",monospace;font-size:12px;text-transform:uppercase;letter-spacing:.14em;text-decoration:none;color:var(--ink);background:var(--paper);border:2px solid var(--ink);padding:6px 12px;transition:transform .08s ease;}
  .bb-bnm-seeall:hover{transform:translate(-2px,-2px);box-shadow:3px 3px 0 var(--ink);background:var(--ink);color:var(--paper);}
  .bb-bnm-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px;}
  .bb-bnm-card{display:block;padding:14px;border:3px solid var(--ink);background:var(--paper);text-decoration:none;color:var(--ink);transition:transform .08s ease;border-left-width:6px;border-left-color:var(--hot);}
  .bb-bnm-card:nth-child(2){border-left-color:var(--cobalt);}
  .bb-bnm-card:nth-child(3){border-left-color:var(--acid);}
  .bb-bnm-card:nth-child(4){border-left-color:var(--tang);}
  .bb-bnm-card:nth-child(5){border-left-color:var(--plum);}
  .bb-bnm-card:nth-child(6){border-left-color:var(--hot);}
  .bb-bnm-card:hover{transform:translate(-3px,-3px);box-shadow:6px 6px 0 var(--ink);}
  .bb-bnm-card h4{font-family:"Archivo Black",sans-serif;font-size:18px;line-height:1.05;margin:0 0 6px;text-transform:uppercase;word-break:break-word;}
  .bb-bnm-card .bb-bnm-meta{font-family:"JetBrains Mono",monospace;font-size:10px;text-transform:uppercase;letter-spacing:.1em;opacity:.65;display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:0;}
  .bb-bnm-card .bb-bnm-meta b{background:var(--ink);color:var(--paper);padding:1px 5px;font-weight:400;}
  .bb-bnm-card .bb-bnm-meta .gb{padding:1px 5px;color:#fff;background:var(--gc,#666);font-weight:600;letter-spacing:.06em;}
  .bb-bnm-card .bb-bnm-date{font-family:"JetBrains Mono",monospace;font-size:10px;opacity:.5;margin-top:4px;}
"""

# Hugo template snippet for the strip
STRIP_HTML = """  <!-- BEST NEW MUSIC strip -->
  <section class="bb-bnm bb-bnm-strip" aria-label="Best new music">
    <div class="bb-bnm-head">
      <h2 class="bb-bnm-title">Best new music<span class="acid">.</span></h2>
      <a class="bb-bnm-seeall" href="/tunes/">see all tunes →</a>
    </div>
    <div class="bb-bnm-grid">
      {{ $bnm := first 6 (where (where .Site.RegularPages "Section" "tunes") "File.LogicalName" "index.md").ByDate.Reverse }}
      {{ range $bnm }}
        {{ $year := .Params.year }}
        {{ $artistOnly := replace .Title (printf " — %s" $year) "" }}
        <a class="bb-bnm-card" href="{{ .Permalink }}">
          <h4>{{ $artistOnly }}</h4>
          <p class="bb-bnm-meta">
            <b>TUNE</b>
            <span>{{ .Params.track_count }} TR</span>
            {{ with index .Params.genre 0 }}<span class="gb">{{ . }}</span>{{ end }}
          </p>
          <div class="bb-bnm-date">{{ .Date.Format "Jan 2, 2006" }}</div>
        </a>
      {{ end }}
    </div>
  </section>

"""


def main():
    write = "--write" in sys.argv
    print(f"\n{'='*60}")
    print(f"ADD 'BEST NEW MUSIC' STRIP — {'WRITE' if write else 'DRY RUN'}")
    print(f"{'='*60}\n")

    if not INDEX_PATH.exists():
        print(f"ERROR: {INDEX_PATH} not found")
        sys.exit(1)

    text = INDEX_PATH.read_text(encoding="utf-8")

    if SENTINEL in text:
        print(f"SKIP: '{SENTINEL}' already present in {INDEX_PATH}")
        print("      Patch appears already applied. No changes.")
        return

    if ANCHOR not in text:
        print(f"FAIL: anchor not found in {INDEX_PATH}")
        print(f"      Looking for: {ANCHOR!r}")
        sys.exit(1)

    # Insert CSS before the closing </style>
    style_close = "</style>"
    if style_close not in text:
        print(f"FAIL: no </style> tag in {INDEX_PATH}")
        sys.exit(1)

    new_text = text.replace(style_close, STRIP_CSS + "\n" + style_close, 1)
    new_text = new_text.replace(ANCHOR, STRIP_HTML + ANCHOR, 1)

    if write:
        INDEX_PATH.write_text(new_text, encoding="utf-8")
        print(f"OK: patched {INDEX_PATH}")
        print(f"    Added CSS block ({len(STRIP_CSS)} chars)")
        print(f"    Added HTML strip ({len(STRIP_HTML)} chars)")
        print()
        print("Next steps:")
        print("  git add -A")
        print("  git commit -m 'feat: BEST NEW MUSIC strip on homepage'")
        print("  git push")
    else:
        print(f"WOULD patch {INDEX_PATH}:")
        print(f"  + CSS block ({len(STRIP_CSS)} chars) before </style>")
        print(f"  + HTML strip ({len(STRIP_HTML)} chars) before filter row")
        print()
        print(f"To apply: re-run with --write")


if __name__ == "__main__":
    main()
