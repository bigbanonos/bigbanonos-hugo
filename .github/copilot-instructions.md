# BigBanonos Hugo Site: AI Coding Guidelines

## Project Overview
BigBanonos is a music-focused Hugo static site hosted on Netlify that curates playlists and song collections across genres (trap, hip-hop, chopped & screwed). The site contains 1000+ markdown content files with artist and song information, built with PaperMod theme.

- **Build**: Hugo 0.149.1 with `hugo --gc --minify`
- **Deployment**: Netlify (build command in `netlify.toml`)
- **Theme**: PaperMod

## Data Pipeline & File Organization

### Content Files: `content/*.md`
Each post is a single artist or collection (e.g., `2pac.md`, `kendrick-lamar-16-songs.md`). Files contain:
- **YAML frontmatter**: title, date, original_title, tags (list with @ prefixes), layout
- **Body**: HTML-embedded content with `<h1>`, `<div>` tags, Hugo shortcodes like `{{< img-lite >}}` and `{{< youtube >}}`

Example frontmatter:
```yaml
---
title: "2Pac"
date: 2025-01-17
original_title: "'2Pac'"
tags:
  - '@snoopdogg'
  - '@2pac'
layout: post
---
```

### Data Processing: Python Scripts
Four utility scripts handle CSV import and format fixing (all in project root):

1. **`generate_posts_from_csv.py`**: Creates `.md` files from `data/songs.csv`
   - Expects CSV columns: title, slug, artist_display, artists_handles (comma-separated), tags, year, album, label, genres, yt_url, spotify_track_url, spotify_playlist_url, notes, date
   - Generates YAML with proper quoting; skips if slug file exists
   - Used when bulk-importing songs from CSV source

2. **`fix_tags.py`**: Normalizes tag frontmatter format
   - Converts inline tags (`tags: "@a, @b"`) to list items (`- '@a'`)
   - Removes empty tag blocks
   - Preserves @ prefixes in all tags

3. **`fix_front_matter.py`**: Rebuilds corrupted YAML headers
   - Extracts fields from malformed frontmatter (handles unicode dashes, zero-width chars, smart quotes)
   - Rebuilds with strict format: title/date/original_title/tags/layout
   - Cleans BOMs and encoding issues (UTF-8 output always)

4. **`strip_leading_garbage.py`**: Removes junk before first `---` delimiter
   - Cleans zero-width/control chars, normalizes dashes (—,–,−→-)
   - Ensures frontmatter starts at line 1

**Workflow**: CSV → `generate_posts_from_csv.py` → `fix_tags.py` → `fix_front_matter.py` → `strip_leading_garbage.py`

## Key Patterns & Conventions

### Tag System
- All artist/collection tags use **@ prefix**: `@2pac`, `@kendrick-lamar`
- Tags always in list format (never inline scalars)
- No spaces after @ in tag names
- Example: `tags: ['@snoopdogg', '@tupac']`

### Hugo Configuration
- Taxonomies: `tag = "tags"` (auto-generates `/tags/` index)
- Permalinks: posts use `:slug/` format (e.g., `/2pac/`)
- Unsafe HTML enabled (`unsafe = true` in `markup.goldmark.renderer`) to allow embedded YouTube/Spotify
- Share buttons enabled via PaperMod params

### Content Conventions
- HTML in markdown (not pure markdown) - use `<div>`, `<h1>`, `<ol>/<li>` for structure
- Hugo shortcodes embedded: `{{< img-lite src="..." alt="..." >}}`, `{{< youtube "embed" >}}`
- Link format: `[Text](URL)`
- Related links section pointing to BigBanonos social media (YouTube, X/Twitter, Blogspot)

## File Editing Guidelines

### When Modifying Posts
1. Preserve YAML frontmatter structure exactly
2. Keep tag @ prefixes; don't remove/add dashes
3. Keep date in ISO format (YYYY-MM-DDTHH:MM:SS)
4. HTML body can have whitespace/formatting adjusted; shortcodes must stay intact

### When Adding Posts
- Use CSV import (`generate_posts_from_csv.py`) for bulk adds
- For manual posts: copy template from `archetypes/default.md`, fill frontmatter, add HTML/markdown body

### Encoding & Special Chars
- **Always save UTF-8 without BOM** (scripts enforce this)
- Clean unicode dash variants (—, –, ‒, −) to ASCII `-` (scripts handle auto-fix)
- Remove zero-width chars (U+200B, U+200C, U+200D, U+FEFF) via `strip_leading_garbage.py`

## Build & Deployment

### Local Build
```bash
hugo --gc --minify  # outputs to ./public/
```

### Netlify Build (automated on git push)
- Command: `hugo --gc --minify`
- Publish dir: `public/`
- Hugo version: 0.149.1 (pinned in netlify.toml)

## Critical File Locations
- **Config**: `config.toml` (baseURL, theme, taxonomies, permalinks)
- **Theme**: `themes/PaperMod/` (customizable)
- **Layouts**: `layouts/` (index.html, list.html override PaperMod defaults)
- **Content**: `content/*.md` (1000+ artist files)
- **Utilities**: Root-level Python scripts for data cleaning
- **Archetype**: `archetypes/default.md` (template for new posts)

## Common Tasks

- **Bulk import songs**: Populate `data/songs.csv`, run `python generate_posts_from_csv.py`, then `fix_tags.py` and `fix_front_matter.py`
- **Fix encoding issues**: Run `strip_leading_garbage.py`, then `fix_front_matter.py`
- **Add single post**: Manually create `.md` file in `content/`, use @ prefixes in tags, verify YAML is valid
- **Preview locally**: Run Hugo server (check local Hugo docs; Netlify uses 0.149.1)
