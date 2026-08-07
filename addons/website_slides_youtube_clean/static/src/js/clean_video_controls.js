/** @odoo-module **/

function enhanceVideo(video) {
    if (video.dataset.cleanControlsReady === '1') {
        return;
    }
    video.dataset.cleanControlsReady = '1';
    video.addEventListener('contextmenu', (event) => event.preventDefault());

    const wrapper = document.createElement('div');
    wrapper.className = 'o_wslides_clean_video_wrapper';
    video.parentNode.insertBefore(wrapper, video);
    wrapper.appendChild(video);

    const controls = document.createElement('div');
    controls.className = 'o_wslides_clean_video_controls';
    controls.innerHTML = `
        <button type="button" class="o_wslides_video_play" aria-label="Play video">▶</button>
        <input type="range" class="o_wslides_video_progress" min="0" max="100" value="0" aria-label="Video progress">
        <button type="button" class="o_wslides_video_fullscreen" aria-label="Fullscreen">⛶</button>
    `;
    wrapper.appendChild(controls);

    const playButton = controls.querySelector('.o_wslides_video_play');
    const progress = controls.querySelector('.o_wslides_video_progress');
    const fullscreenButton = controls.querySelector('.o_wslides_video_fullscreen');

    const updatePlayButton = () => {
        playButton.textContent = video.paused ? '▶' : 'Ⅱ';
        playButton.setAttribute('aria-label', video.paused ? 'Play video' : 'Pause video');
    };
    const togglePlay = () => {
        if (video.paused) {
            video.play();
        } else {
            video.pause();
        }
    };

    playButton.addEventListener('click', togglePlay);
    video.addEventListener('click', togglePlay);
    video.addEventListener('play', updatePlayButton);
    video.addEventListener('pause', updatePlayButton);
    video.addEventListener('timeupdate', () => {
        if (video.duration) {
            progress.value = (video.currentTime / video.duration) * 100;
        }
    });
    video.addEventListener('loadedmetadata', () => {
        progress.value = '0';
    });
    progress.addEventListener('input', () => {
        if (video.duration) {
            video.currentTime = (Number(progress.value) / 100) * video.duration;
        }
    });
    fullscreenButton.addEventListener('click', () => {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            wrapper.requestFullscreen?.();
        }
    });
    updatePlayButton();
}

function enhanceVideos(root = document) {
    root.querySelectorAll?.('video.o_wslides_clean_video').forEach(enhanceVideo);
}

function initCleanVideoControls() {
    enhanceVideos();
    new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    enhanceVideos(node);
                }
            });
        }
    }).observe(document.body, {childList: true, subtree: true});
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCleanVideoControls, {once: true});
} else {
    initCleanVideoControls();
}
