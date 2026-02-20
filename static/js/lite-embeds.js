document.addEventListener("DOMContentLoaded", funtion() {
    const liteEmbeds = document.querySelectorAll('.lite-embed');
    
    liteEmbeds.forEach(embed => {
        embed.addEventListener('click', funtion() {
            const src = this.getAttribute('data-src');
            const type = this.getAttribute('data-type');
            let iframe = document.createElement('iframe');
            
            iframe.setAttribute('src', src);
            iframe.setAttribute('frameborder', '0');
            iframe.setAttribute('allowfullscreen', 'true');
            iframe.setAttribute('allow', 'autoplay; encrypted-media');
            
            if (type === 'spotify') {
                iframe.style.width = '100%';
                iframe.style.height = '380px';
            } else if (type === 'youtube') {
                iframe.style.width = '100%';
                iframe.style.height = '100%';
                // Add autoplay so it plays immediately on click
                if(src.includes('?')) {
                    iframe.setAttribute('src', src + '&autoplay=1');
                } else {
                    iframe.setAttribute('src', src + '?autoplay=1');
                }
            }
            
            this.innerHTML = '';
            this.appendChild(iframe);
        });
    });
});