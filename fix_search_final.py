import os

# 1. CREATE THE DATABASE GENERATOR (The "Brain")
# This tells Hugo: "Please build a list of all posts called index.json"
layout_dir = "layouts"
if not os.path.exists(layout_dir):
    os.makedirs(layout_dir)

with open(os.path.join(layout_dir, "index.json"), "w", encoding="utf-8") as f:
    f.write("""{{- $.Scratch.Add "index" slice -}}
{{- range .Site.RegularPages -}}
    {{- $title := .Title -}}
    {{- $url := .Permalink -}}
    {{- $tags := .Params.tags | default slice -}}
    {{- $.Scratch.Add "index" (dict "title" $title "tags" $tags "permalink" $url) -}}
{{- end -}}
{{- $.Scratch.Get "index" | jsonify -}}""")

# 2. CREATE THE SEARCH PAGE (The "Face")
# This is the actual page with the search bar
content_dir = os.path.join("content")
with open(os.path.join(content_dir, "search.md"), "w", encoding="utf-8") as f:
    f.write("""---
title: "Search"
layout: "search"
summary: "search"
---

<script src="https://cdn.jsdelivr.net/npm/fuse.js@6.6.2"></script>

<div style="max-width: 600px; margin: 0 auto; padding: 20px;">
    <input type="text" id="searchInput" placeholder="Search artists, songs..." 
           style="width: 100%; padding: 15px; font-size: 18px; border: 2px solid #333; border-radius: 8px;">
    <div id="searchResults" style="margin-top: 20px;"></div>
</div>

<script>
    let fuse;
    const resultsDiv = document.getElementById('searchResults');

    fetch('/index.json')
        .then(response => response.json())
        .then(data => {
            fuse = new Fuse(data, {
                keys: ['title', 'tags'],
                threshold: 0.3
            });
        });

    document.getElementById('searchInput').addEventListener('input', (e) => {
        if (!fuse) return;
        const results = fuse.search(e.target.value);
        resultsDiv.innerHTML = ''; 

        if (results.length === 0 && e.target.value.length > 0) {
            resultsDiv.innerHTML = '<p>No matches found.</p>';
            return;
        }

        results.forEach(result => {
            const item = result.item;
            const html = `
                <div style="margin-bottom: 15px; padding: 10px; border-bottom: 1px solid #eee;">
                    <a href="${item.permalink}" style="font-size: 18px; font-weight: bold; text-decoration: none; color: #333;">
                        ${item.title}
                    </a>
                </div>
            `;
            resultsDiv.insertAdjacentHTML('beforeend', html);
        });
    });
</script>
""")

print("--- SUCCESS: Created layouts/index.json and content/search.md ---")