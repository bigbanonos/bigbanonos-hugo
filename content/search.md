---
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

    // 1. Fetch the database we just built
    fetch('/index.json')
        .then(response => response.json())
        .then(data => {
            console.log("Index loaded:", data.length, "items");
            // 2. Configure the engine
            fuse = new Fuse(data, {
                keys: ['title', 'tags'],
                threshold: 0.3, // 0.0 = perfect match, 1.0 = match anything
                limit: 50
            });
        })
        .catch(err => console.error("Failed to load search index:", err));

    // 3. Listen for typing
    document.getElementById('searchInput').addEventListener('input', (e) => {
        if (!fuse) return;
        
        const results = fuse.search(e.target.value);
        resultsDiv.innerHTML = ''; // Clear old results

        if (results.length === 0 && e.target.value.length > 0) {
            resultsDiv.innerHTML = '<p>No matches found.</p>';
            return;
        }

        // 4. Show results
        results.forEach(result => {
            const item = result.item;
            const html = `
                <div style="margin-bottom: 15px; padding: 10px; border-bottom: 1px solid #eee;">
                    <a href="${item.permalink}" style="font-size: 18px; font-weight: bold; text-decoration: none; color: #333;">
                        ${item.title}
                    </a>
                    <div style="font-size: 14px; color: #666; margin-top: 5px;">
                        ${item.tags.join(', ')}
                    </div>
                </div>
            `;
            resultsDiv.insertAdjacentHTML('beforeend', html);
        });
    });
</script>