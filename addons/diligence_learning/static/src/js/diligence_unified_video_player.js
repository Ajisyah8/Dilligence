/** @odoo-module **/

import Fullscreen from '@website_slides/js/slides_course_fullscreen_player';
import { markup } from '@odoo/owl';

/* One player contract for the normal lesson page and Odoo's fullscreen DOM.
 * The vendor libraries are local module assets; no remote media is fetched by
 * this script and no URL is proxied through Odoo. */
function youtubeId(url) {
    try {
        const parsed = new URL(url, window.location.href);
        if (['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'].includes(parsed.hostname)) {
            return parsed.searchParams.get('v') || parsed.pathname.split('/embed/')[1]?.split('/')[0];
        }
        if (parsed.hostname === 'youtu.be') return parsed.pathname.split('/')[1];
    } catch (_) { /* invalid URL is handled by the server-side validator */ }
    return null;
}

function decorateProviderIframe(iframe) {
    if (iframe.dataset.diligencePlyrReady) return iframe;
    const source = iframe.getAttribute('src') || '';
    const id = youtubeId(source);
    if (id) {
        iframe.dataset.plyrProvider = 'youtube';
        iframe.dataset.plyrEmbedId = id;
    } else if (/player\.vimeo\.com\/video\//i.test(source)) {
        const match = source.match(/player\.vimeo\.com\/video\/(\d+)/i);
        if (match) {
            iframe.dataset.plyrProvider = 'vimeo';
            iframe.dataset.plyrEmbedId = match[1];
        }
    }
    return iframe;
}

function initializeVideo(element) {
    if (!window.Plyr) return;
    let target = element;
    const isIframe = element.tagName === 'IFRAME';
    if (isIframe) {
        decorateProviderIframe(element);
        target = element.closest('.plyr__video-embed');
        if (!target) {
            target = document.createElement('div');
            target.className = 'plyr__video-embed';
            element.replaceWith(target);
            target.appendChild(element);
        }
        // Plyr reads provider metadata from the element it initializes. Odoo's
        // fullscreen templates provide it on the iframe, so copy it to the
        // wrapper before constructing Plyr.
        if (element.dataset.plyrProvider) {
            target.dataset.plyrProvider = element.dataset.plyrProvider;
            target.dataset.plyrEmbedId = element.dataset.plyrEmbedId || '';
        }
    }
    if (target.dataset.diligencePlyrReady) return;
    const media = target.matches('video') ? target : target.querySelector('video');
    const sourceElement = media || element;
    const source = sourceElement.currentSrc || sourceElement.src || sourceElement.getAttribute('src') || '';
    let hls;
    if (media && /\.m3u8(?:$|[?#])/i.test(source) && window.Hls?.isSupported()) {
        hls = new window.Hls();
        hls.loadSource(source);
        hls.attachMedia(media);
    } else if (media && /\.m3u8(?:$|[?#])/i.test(source) && media.canPlayType('application/vnd.apple.mpegurl')) {
        media.src = source;
    }
    const player = new window.Plyr(target, {
        autoplay: false,
        invertTime: false,
        controls: ['play-large', 'play', 'progress', 'current-time', 'mute', 'volume', 'settings', 'pip', 'fullscreen'],
        settings: ['speed'],
        tooltips: { controls: true, seek: true },
    });
    target.dataset.diligencePlyrReady = '1';
    target._diligencePlyr = player;
    target._diligenceHls = hls;
}

function initializeDiligencePlayers(root = document) {
    // Only initialize elements explicitly owned by Diligence. In particular,
    // do not discover arbitrary .plyr__video-embed nodes: Plyr mutates its
    // own iframe during startup and a DOM observer would initialize it again,
    // producing a request/render loop with YouTube or Vimeo.
    root.querySelectorAll?.('[data-diligence-video-player], .diligence-custom-video-frame video, .o_wslides_fs_content video').forEach((element) => {
        initializeVideo(element);
    });
}

function start() {
    initializeDiligencePlayers();
}

function providerVideoId(slide) {
    const source = slide.videoUrl || slide.video_url || slide.embedUrl || slide.embed_url
        || slide.embedCode || slide.url || '';
    const sourceText = typeof source === 'string' ? source : String(source || '');
    const category = slide.category || slide.slideCategory || slide.slide_category;
    const sourceType = slide.videoSourceType || slide.video_source_type;
    const youtubeValue = slide.youtubeId || slide.youtube_id;
    if (sourceType === 'youtube' || youtubeValue || /youtube(?:-nocookie)?\.com|youtu\.be/i.test(sourceText)) {
        const id = youtubeValue || youtubeId(sourceText)
            || sourceText.match(/youtube(?:-nocookie)?\.com\/embed\/([^?&#/]+)/i)?.[1];
        if (id) return ['youtube', id];
    }
    const vimeoValue = slide.vimeoId || slide.vimeo_id;
    if (sourceType === 'vimeo' || vimeoValue || /vimeo\.com/i.test(sourceText)) {
        const id = vimeoValue || sourceText.match(/vimeo\.com\/(?:video\/)?(\d+)/i)?.[1];
        if (id) return ['vimeo', String(id).split('/')[0]];
    }
    const youtube = youtubeId(sourceText);
    if (youtube) return ['youtube', youtube];
    const vimeo = sourceText.match(/vimeo\.com\/(?:video\/)?(\d+)/i);
    return category === 'video' && vimeo ? ['vimeo', vimeo[1]] : [null, null];
}

/* Make the fullscreen dispatcher choose Odoo's external renderer, whose
 * content is supplied by Diligence as a Plyr wrapper. This prevents the
 * native VideoPlayerYouTube/Vimeo widgets (and their autoplay/API polling)
 * from being constructed at all. */
if (!window.__diligenceUnifiedVideoPlayerPatch) {
window.__diligenceUnifiedVideoPlayerPatch = true;
Fullscreen.include({
    async _renderSlide() {
        // website_slides.fullscreen.video.external expects widget.slide,
        // while the parent fullscreen widget stores the current record as
        // _slideValue. Keep the native template compatible without editing
        // the Odoo module.
        this.slide = this._slideValue;
        const [provider, embedId] = providerVideoId(this._slideValue || {});
        if (this._slideValue?.category === 'video' && provider && embedId) {
            // Do not call the parent renderer for provider videos. The parent
            // creates VideoPlayerYouTube/Vimeo before our DOM observer can see
            // it, which causes repeated native iframe requests.
            const content = this.$('.o_wslides_fs_content')[0];
            if (!content) return;
            content.replaceChildren();
            content.classList.remove('bg-white');
            const stage = document.createElement('div');
            stage.className = 'diligence-plyr-stage w-100 h-100 d-flex align-items-center justify-content-center p-3';
            stage.style.cssText = 'display:flex;width:100%;max-width:70rem;height:min(70vh,42rem);min-height:24rem;flex:0 0 auto;align-items:center;justify-content:center;padding:0;';
            const embed = document.createElement('div');
            embed.className = 'plyr__video-embed';
            embed.style.cssText = 'position:relative;width:100%;height:100%;max-width:none;aspect-ratio:16/9;';
            embed.dataset.diligenceVideoPlayer = '1';
            embed.dataset.plyrProvider = provider;
            embed.dataset.plyrEmbedId = embedId;
            const iframe = document.createElement('iframe');
            iframe.src = provider === 'youtube'
                ? `https://www.youtube-nocookie.com/embed/${embedId}?rel=0&playsinline=1`
                : `https://player.vimeo.com/video/${embedId}?dnt=1`;
            iframe.title = this._slideValue.name || 'Course video';
            iframe.allow = 'fullscreen; picture-in-picture';
            iframe.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;border:0;';
            iframe.setAttribute('allowfullscreen', 'allowfullscreen');
            embed.appendChild(iframe);
            stage.appendChild(embed);
            content.appendChild(stage);
            initializeDiligencePlayers(stage);
            return;
        }
        return this._super(...arguments);
    },
    _preprocessSlideData(slidesDataList) {
        const slides = this._super(...arguments);
        slides.forEach((slide) => {
            const [provider, embedId] = providerVideoId(slide);
            if (slide.category !== 'video' || !provider || !embedId) return;
            slide.videoSourceType = 'external';
            const source = provider === 'youtube'
                ? `https://www.youtube-nocookie.com/embed/${embedId}?rel=0&playsinline=1`
                : `https://player.vimeo.com/video/${embedId}?dnt=1`;
            slide.embedCode = markup(
                `<div class="plyr__video-embed" data-diligence-video-player="1" `
                + `data-plyr-provider="${provider}" data-plyr-embed-id="${embedId}">`
                + `<iframe src="${source}" title="Course video" `
                + `allow="fullscreen; picture-in-picture" allowfullscreen></iframe></div>`
            );
        });
        return slides;
    },
});
}

if (!window.__diligenceUnifiedVideoPlayerStarted) {
    window.__diligenceUnifiedVideoPlayerStarted = true;
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
    else start();
}
