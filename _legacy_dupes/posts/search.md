---
title: "Search"
layout: "single"
summary: "search"
---

<script src="https://cdn.jsdelivr.net/npm/fuse.js@6.6.2"></script>

<div style="max-width: 600px; margin: 0 auto; padding: 20px;">
    <input type="text" id="searchInput" placeholder="Type to search (e.g. Drake, Trap)..." 
           style="width: 100%; padding: 15px; font-size: 18px; border: 2px solid #333; border-radius: 8px;">
    <div id="searchResults" style="margin-top: 20px;"></div>
</div>

<script>
    let fuse;
    const resultsDiv = document.getElementById('searchResults');

    // Load the database
    fetch('/index.json')
        .then(response => {
            if (!response.ok) throw new Error("Database not found");
            return response.json();
        })
        .then(data => {
            console.log("Database loaded:", data.length);
            fuse = new Fuse(data, {
                keys: ['title', 'tags'],
                threshold: 0.3,
                limit: 50
            });
        })
        .catch(err => {
            console.error(err);
            resultsDiv.innerHTML = "<p style='color:red'>Search database is loading... try refreshing in 1 minute.</p>";
        });

    // Listen for typing
    document.getElementById('searchInput').addEventListener('input', (e) => {
        if (!fuse) return;
        
        const term = e.target.value;
        const results = fuse.search(term);
        resultsDiv.innerHTML = ''; 

        if (results.length === 0 && term.length > 0) {
            resultsDiv.innerHTML = '<p>No matches found.</p>';
            return;
        }

        results.forEach(result => {
            const item = result.item;
            // Clean up the display
            let title = item.title;
            let link = item.permalink;
            
            const html = `
                <div style="margin-bottom: 15px; padding: 10px; border-bottom: 1px solid #eee;">
                    <a href="${link}" style="font-size: 18px; font-weight: bold; text-decoration: none; color: #333; display: block;">
                        ${title}
                    </a>
                    <span style="font-size: 12px; color: #666;">
                        ${item.tags ? item.tags.join(', ') : ''}
                    </span>
                </div>
            `;
            resultsDiv.insertAdjacentHTML('beforeend', html);
        });
    });
</script>