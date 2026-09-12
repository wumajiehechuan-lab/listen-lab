/* 播放器模块：字幕渲染、播放同步高亮、单词栏渲染 */
(function () {
  "use strict";

  const video = document.getElementById("video");
  const subtitleList = document.getElementById("subtitle-list");
  const subtitlePanel = document.getElementById("subtitle-panel");
  const wordList = document.getElementById("word-list");
  const emptyHint = document.getElementById("empty-hint");

  let subtitles = [];
  let keywords = [];
  let currentSeq = -1;

  /** 毫秒 → mm:ss 显示 */
  function formatTime(ms) {
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  /** 转义 HTML 特殊字符 */
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /** 高亮句子中出现的重点词 */
  function highlightKeywords(text) {
    let html = escapeHtml(text);
    // 按词长降序，避免短词先替换破坏长词
    const words = keywords
      .map((k) => k.word)
      .filter(Boolean)
      .sort((a, b) => b.length - a.length);
    for (const w of words) {
      const pattern = new RegExp(
        `\\b(${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})\\b`,
        "gi"
      );
      html = html.replace(pattern, '<span class="kw">$1</span>');
    }
    return html;
  }

  /** 渲染字幕列表 */
  function renderSubtitles() {
    subtitleList.innerHTML = "";
    for (const sub of subtitles) {
      const item = document.createElement("div");
      item.className = "subtitle-item";
      item.dataset.seq = sub.seq;
      item.innerHTML = `
        <div class="sub-time">${formatTime(sub.start_ms)}</div>
        <div class="sub-en">${highlightKeywords(sub.text_en)}</div>
        ${sub.text_zh ? `<div class="sub-zh">${escapeHtml(sub.text_zh)}</div>` : ""}
      `;
      item.addEventListener("click", () => {
        video.currentTime = sub.start_ms / 1000;
        video.play();
      });
      subtitleList.appendChild(item);
    }
  }

  /** 渲染右侧单词卡片 */
  function renderKeywords() {
    wordList.innerHTML = "";
    if (!keywords.length) {
      wordList.innerHTML = '<div class="word-empty">暂无重点词汇</div>';
      return;
    }
    for (const kw of keywords) {
      const card = document.createElement("div");
      card.className = "word-card";
      card.innerHTML = `
        <div class="w-head">
          <span class="w-word">${escapeHtml(kw.word)}</span>
          ${kw.phonetic ? `<span class="w-phonetic">${escapeHtml(kw.phonetic)}</span>` : ""}
        </div>
        ${kw.pos ? `<div class="w-pos">${escapeHtml(kw.pos)}</div>` : ""}
        ${kw.meaning_zh ? `<div class="w-meaning">${escapeHtml(kw.meaning_zh)}</div>` : ""}
      `;
      // 点击单词卡片跳转到出处句
      if (kw.seq) {
        card.addEventListener("click", () => {
          const target = subtitles.find((s) => s.seq === kw.seq);
          if (target) {
            video.currentTime = target.start_ms / 1000;
            video.play();
          }
        });
      }
      wordList.appendChild(card);
    }
  }

  /** 根据播放时间更新高亮句 */
  function syncHighlight() {
    const nowMs = video.currentTime * 1000;
    const current = subtitles.find((s) => nowMs >= s.start_ms && nowMs < s.end_ms);
    const seq = current ? current.seq : -1;
    if (seq === currentSeq) return;
    currentSeq = seq;
    subtitleList
      .querySelectorAll(".subtitle-item.playing")
      .forEach((el) => el.classList.remove("playing"));
    if (seq > 0) {
      const el = subtitleList.querySelector(`.subtitle-item[data-seq="${seq}"]`);
      if (el) {
        el.classList.add("playing");
        // 只在用户未手动滚动字幕栏时自动滚动（近 2 秒无滚动事件）
        if (Date.now() - lastUserScroll > 2000) {
          el.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }
    }
  }

  let lastUserScroll = 0;
  subtitlePanel.addEventListener("wheel", () => {
    lastUserScroll = Date.now();
  });
  subtitlePanel.addEventListener("touchmove", () => {
    lastUserScroll = Date.now();
  });

  video.addEventListener("timeupdate", syncHighlight);

  /** 加载素材到播放器（对外暴露） */
  window.Player = {
    load(material) {
      subtitles = material.subtitles || [];
      keywords = material.keywords || [];
      currentSeq = -1;
      video.src = material.video_url;
      emptyHint.style.display = "none";
      renderSubtitles();
      renderKeywords();
    },
    clear() {
      subtitles = [];
      keywords = [];
      currentSeq = -1;
      video.removeAttribute("src");
      video.load();
      emptyHint.style.display = "";
      subtitleList.innerHTML = "";
      wordList.innerHTML = "";
    },
  };
})();
