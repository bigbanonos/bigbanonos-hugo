// static/js/lite-embeds.js
function swapToSpotify(wrapper) {
  if (wrapper.dataset.loaded === "true") return;
  const id = wrapper.dataset.spotifyId;
  const type = wrapper.dataset.spotifyType || "track";
  if (!id) return;

  const iframe = document.createElement("iframe");
  iframe.src = `https://open.spotify.com/embed/${type}/${id}?utm_source=generator&autoplay=1`;
  iframe.loading = "lazy";
  iframe.allow = "autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture";
  iframe.style.width = "100%";
  iframe.style.height = "152px";
  iframe.style.border = "0";

  wrapper.innerHTML = "";
  wrapper.appendChild(iframe);
  wrapper.dataset.loaded = "true";
}

function swapToYouTube(wrapper) {
  if (wrapper.dataset.loaded === "true") return;
  const id = wrapper.dataset.youtubeId;
  if (!id) return;

  const iframe = document.createElement("iframe");
  iframe.src = `https://www.youtube.com/embed/${id}?autoplay=1`;
  iframe.loading = "lazy";
  iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
  iframe.allowFullscreen = true;
  iframe.style.width = "100%";
  iframe.style.height = "315px";
  iframe.style.border = "0";

  wrapper.innerHTML = "";
  wrapper.appendChild(iframe);
  wrapper.dataset.loaded = "true";
}

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".bb-spotify-lite").forEach((el) => {
    el.addEventListener("click", () => swapToSpotify(el));
    el.addEventListener("keydown", (e) => { if (e.key === "Enter") swapToSpotify(el); });
  });

  document.querySelectorAll(".bb-youtube-lite").forEach((el) => {
    el.addEventListener("click", () => swapToYouTube(el));
    el.addEventListener("keydown", (e) => { if (e.key === "Enter") swapToYouTube(el); });
  });
});
