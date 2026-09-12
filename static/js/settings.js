/* 模型接入设置模块：ASR + LLM 配置，LLM 支持服务商预设切换 */
(function () {
  "use strict";

  const modal = document.getElementById("settings-modal");
  const fieldsBox = document.getElementById("settings-fields");
  const progressBox = document.getElementById("settings-progress");
  const btnSave = document.getElementById("btn-settings-save");
  const btnClose = document.getElementById("btn-settings-close");
  const settingsDot = document.getElementById("settings-dot");

  // 分区渲染：ASR 固定字段，LLM 含服务商下拉
  const ASR_FIELDS = ["volc_api_key"];
  const LLM_FIELDS = ["llm_api_key", "llm_base_url", "llm_model"];
  // 必填项（决定小红点提示）
  const REQUIRED = ["volc_api_key", "llm_api_key"];

  let configData = { fields: {}, presets: {} };

  function showProgress(text, isError) {
    progressBox.textContent = text;
    progressBox.classList.remove("hidden");
    progressBox.style.background = isError ? "#fdecea" : "#eafaf1";
    progressBox.style.borderColor = isError ? "#e74c3c" : "#82c99a";
    progressBox.style.color = isError ? "#c0392b" : "#1e8449";
  }

  /** 更新顶栏按钮上的未配置小红点 */
  function updateDot() {
    const fields = configData.fields || {};
    const missing = REQUIRED.some((f) => !fields[f] || !fields[f].configured);
    settingsDot.classList.toggle("hidden", !missing);
  }

  function badge(info) {
    return info.configured
      ? '<span class="cfg-badge ok">已配置</span>'
      : '<span class="cfg-badge missing">未配置</span>';
  }

  function fieldRow(field) {
    const info = configData.fields[field];
    // 敏感字段不回传明文，输入框留空表示保持不变
    const placeholder = info.secret
      ? info.configured ? `当前: ${info.value}（留空保持不变）` : "请输入"
      : "";
    return `
      <label class="form-row">
        <span>${info.label}</span>
        <input type="${info.secret ? "password" : "text"}" data-field="${field}"
               value="${info.secret ? "" : info.value}" placeholder="${placeholder}">
        ${badge(info)}
      </label>`;
  }

  function renderFields() {
    const fields = configData.fields;
    const presets = configData.presets;
    const currentProvider = fields.llm_provider.value || "deepseek";

    const providerOptions = Object.entries(presets)
      .map(([id, p]) => `<option value="${id}" ${id === currentProvider ? "selected" : ""}>${p.label}</option>`)
      .join("");

    fieldsBox.innerHTML = `
      <div class="settings-section">
        <h3>语音识别（ASR）</h3>
        <label class="form-row">
          <span>服务商</span>
          <input type="text" value="火山引擎 · 豆包录音文件识别模型 2.0" disabled>
        </label>
        <div class="preset-note">在火山引擎「语音技术 → API Key 管理」获取 Key，需开通「豆包录音文件识别模型」。更多服务商（阿里 / 腾讯）后续支持。</div>
        ${ASR_FIELDS.map(fieldRow).join("")}
      </div>
      <div class="settings-section">
        <h3>大语言模型（翻译 / 重点词）</h3>
        <label class="form-row">
          <span>${fields.llm_provider.label}</span>
          <select id="llm-provider-select">${providerOptions}</select>
          ${badge(fields.llm_provider)}
        </label>
        <div id="llm-preset-note" class="preset-note"></div>
        ${LLM_FIELDS.map(fieldRow).join("")}
      </div>
    `;

    // 切换服务商时自动填充预设的 Base URL / 模型，并展示提示
    const select = document.getElementById("llm-provider-select");
    const note = document.getElementById("llm-preset-note");
    function applyPreset() {
      const preset = presets[select.value] || {};
      note.textContent = preset.note || "";
      fieldsBox.querySelector('input[data-field="llm_base_url"]').value = preset.base_url || "";
      fieldsBox.querySelector('input[data-field="llm_model"]').value = preset.model || "";
    }
    select.addEventListener("change", applyPreset);
    note.textContent = (presets[select.value] || {}).note || "";
  }

  async function open() {
    progressBox.classList.add("hidden");
    btnSave.disabled = false;
    try {
      const resp = await fetch("/api/settings");
      configData = await resp.json();
      renderFields();
      updateDot();
    } catch (e) {
      showProgress("读取配置失败：" + e.message, true);
    }
    modal.classList.remove("hidden");
  }

  function close() {
    modal.classList.add("hidden");
  }

  async function save() {
    btnSave.disabled = true;
    const payload = {};
    fieldsBox.querySelectorAll("input[data-field]").forEach((input) => {
      payload[input.dataset.field] = input.value.trim();
    });
    const select = document.getElementById("llm-provider-select");
    if (select) payload.llm_provider = select.value;
    try {
      const resp = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      showProgress(
        data.updated.length ? `✅ 已保存 ${data.updated.length} 项配置，即时生效` : "没有改动",
        false
      );
      // 刷新配置状态
      const refresh = await fetch("/api/settings");
      configData = await refresh.json();
      renderFields();
      updateDot();
      btnSave.disabled = false;
    } catch (e) {
      showProgress("❌ 保存失败：" + e.message, true);
      btnSave.disabled = false;
    }
  }

  btnSave.addEventListener("click", save);
  btnClose.addEventListener("click", close);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) close();
  });
  document.getElementById("btn-settings").addEventListener("click", open);

  /** 页面加载时拉取一次配置状态，用于小红点提示 */
  window.Settings = {
    async init() {
      try {
        const resp = await fetch("/api/settings");
        configData = await resp.json();
        updateDot();
      } catch (e) {
        /* 忽略启动时的配置检查失败 */
      }
    },
  };
})();
