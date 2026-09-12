/* 导入视频模块：模态窗口、上传、状态轮询 */
(function () {
  "use strict";

  const modal = document.getElementById("upload-modal");
  const titleInput = document.getElementById("upload-title");
  const folderSelect = document.getElementById("upload-folder");
  const fileInput = document.getElementById("upload-file");
  const progressBox = document.getElementById("upload-progress");
  const btnSubmit = document.getElementById("btn-upload-submit");
  const btnCancel = document.getElementById("btn-upload-cancel");

  let folderOptions = []; // {id, label} 扁平化文件夹列表

  function open() {
    titleInput.value = "";
    fileInput.value = "";
    progressBox.classList.add("hidden");
    btnSubmit.disabled = false;
    rebuildFolderOptions();
    modal.classList.remove("hidden");
  }

  function close() {
    modal.classList.add("hidden");
  }

  /** 将树中的文件夹扁平化为带层级的下拉选项 */
  function rebuildFolderOptions() {
    folderOptions = [{ id: "", label: "（根目录）" }];
    const walk = (nodes, depth) => {
      for (const node of nodes || []) {
        folderOptions.push({ id: node.id, label: "　".repeat(depth) + node.name });
        walk(node.children, depth + 1);
      }
    };
    walk(window.App ? window.App.getFolderTree() : [], 0);
    folderSelect.innerHTML = folderOptions
      .map((f) => `<option value="${f.id}">${f.label}</option>`)
      .join("");
  }

  function showProgress(text) {
    progressBox.textContent = text;
    progressBox.classList.remove("hidden");
  }

  /** 轮询素材处理状态 */
  async function pollStatus(materialId) {
    const deadline = Date.now() + 10 * 60 * 1000;
    while (Date.now() < deadline) {
      try {
        const resp = await fetch(`/api/materials/${materialId}/status`);
        const data = await resp.json();
        if (data.status === "ready") {
          showProgress("✅ 生成完成！");
          await window.App.refreshTree();
          await window.App.loadMaterial(materialId);
          setTimeout(close, 800);
          return;
        }
        if (data.status === "failed") {
          showProgress(`❌ 生成失败：${data.error_msg || "未知错误"}`);
          await window.App.refreshTree();
          btnSubmit.disabled = false;
          return;
        }
        showProgress("⏳ 正在识别与生成，请稍候…（识别约需 1~3 分钟）");
      } catch (e) {
        showProgress("状态查询失败，重试中…");
      }
      await new Promise((r) => setTimeout(r, 4000));
    }
    showProgress("处理超时，请稍后在素材库中查看状态");
    btnSubmit.disabled = false;
  }

  async function submit() {
    const file = fileInput.files[0];
    if (!file) {
      showProgress("请先选择视频文件");
      return;
    }
    btnSubmit.disabled = true;
    showProgress("上传中…");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", titleInput.value.trim());
    if (folderSelect.value) formData.append("folder_id", folderSelect.value);

    try {
      const resp = await fetch("/api/materials/upload", {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      await pollStatus(data.id);
    } catch (e) {
      showProgress(`❌ 上传失败：${e.message}`);
      btnSubmit.disabled = false;
    }
  }

  btnSubmit.addEventListener("click", submit);
  btnCancel.addEventListener("click", close);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) close();
  });

  window.Upload = { open };
})();
