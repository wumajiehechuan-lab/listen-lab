/* 主应用模块：树状导航渲染、素材加载、文件夹管理、导出 */
(function () {
  "use strict";

  const treeEl = document.getElementById("tree");
  const btnImport = document.getElementById("btn-import");
  const btnNewFolder = document.getElementById("btn-new-folder");
  const btnExport = document.getElementById("btn-export");

  let folderTree = [];
  let activeMaterialId = null;

  const STATUS_ICON = { processing: "🟡", ready: "", failed: "🔴" };

  /* 线性 SVG 图标（对齐设计稿 lucide 风格） */
  const SVG_ATTRS = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
  const ICON_FOLDER = `<span class="tree-icon"><svg ${SVG_ATTRS}><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg></span>`;
  const ICON_FILM = `<span class="tree-icon"><svg ${SVG_ATTRS}><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h18"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 16.5h4"/></svg></span>`;

  /* ---------- 通用对话框（替代原生 prompt/confirm/alert） ---------- */

  const dialogMask = document.getElementById("dialog-mask");
  const dialogTitle = document.getElementById("dialog-title");
  const dialogInput = document.getElementById("dialog-input");
  const dialogMessage = document.getElementById("dialog-message");
  const dialogOk = document.getElementById("dialog-ok");
  const dialogCancel = document.getElementById("dialog-cancel");
  let dialogResolve = null;

  function openDialog({ title, mode, value = "", message = "" }) {
    dialogTitle.textContent = title;
    dialogInput.classList.toggle("hidden", mode !== "prompt");
    dialogMessage.classList.toggle("hidden", mode === "prompt");
    dialogMessage.textContent = message;
    dialogInput.value = value;
    dialogCancel.style.display = mode === "alert" ? "none" : "";
    dialogMask.classList.remove("hidden");
    if (mode === "prompt") dialogInput.focus();
    return new Promise((resolve) => {
      dialogResolve = resolve;
    });
  }

  function closeDialog(result) {
    dialogMask.classList.add("hidden");
    if (dialogResolve) {
      dialogResolve(result);
      dialogResolve = null;
    }
  }

  dialogOk.addEventListener("click", () => {
    closeDialog(dialogInput.classList.contains("hidden") ? true : dialogInput.value.trim());
  });
  dialogCancel.addEventListener("click", () => closeDialog(null));
  dialogMask.addEventListener("click", (e) => {
    if (e.target === dialogMask) closeDialog(null);
  });
  dialogInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") dialogOk.click();
  });

  /** 输入对话框：返回输入值或 null（取消） */
  const dialogPrompt = (title, value = "") => openDialog({ title, mode: "prompt", value });
  /** 确认对话框：返回 true / null */
  const dialogConfirm = (title, message) => openDialog({ title, mode: "confirm", message });
  /** 提示对话框：仅展示信息 */
  const dialogAlert = (title, message) => openDialog({ title, mode: "alert", message });

  /* ---------- 树渲染 ---------- */

  function createMaterialNode(m) {
    const li = document.createElement("li");
    li.className = "tree-node";
    const label = document.createElement("div");
    label.className = "tree-label" + (m.id === activeMaterialId ? " active" : "");
    label.innerHTML = `
      <span class="tree-toggle"></span>
      ${ICON_FILM}
      <span class="node-name">${escapeHtml(m.title)}</span>
      <span class="status-dot">${STATUS_ICON[m.status] || ""}</span>
      <span class="node-actions">
        <button data-action="del-material" title="删除素材">✕</button>
      </span>
    `;
    label.addEventListener("click", (e) => {
      if (e.target.dataset.action === "del-material") {
        e.stopPropagation();
        deleteMaterial(m.id, m.title);
        return;
      }
      loadMaterial(m.id);
    });
    li.appendChild(label);
    return li;
  }

  function createFolderNode(f) {
    const li = document.createElement("li");
    li.className = "tree-node";
    const label = document.createElement("div");
    label.className = "tree-label";
    label.innerHTML = `
      <span class="tree-toggle">${f.children.length || f.materials.length ? "▾" : ""}</span>
      ${ICON_FOLDER}
      <span class="node-name">${escapeHtml(f.name)}</span>
      <span class="node-actions">
        <button data-action="add-sub" title="新建子文件夹">＋</button>
        <button data-action="rename" title="重命名">✎</button>
        <button data-action="del-folder" title="删除文件夹">✕</button>
      </span>
    `;
    li.appendChild(label);

    const ul = document.createElement("ul");
    for (const child of f.children) ul.appendChild(createFolderNode(child));
    for (const m of f.materials) ul.appendChild(createMaterialNode(m));
    li.appendChild(ul);

    // 折叠/展开
    const toggle = label.querySelector(".tree-toggle");
    label.addEventListener("click", async (e) => {
      const action = e.target.dataset.action;
      if (action === "add-sub") {
        e.stopPropagation();
        const name = await dialogPrompt("新建子文件夹");
        if (name) createFolder(name, f.id);
        return;
      }
      if (action === "rename") {
        e.stopPropagation();
        const name = await dialogPrompt("重命名文件夹", f.name);
        if (name) renameFolder(f.id, name);
        return;
      }
      if (action === "del-folder") {
        e.stopPropagation();
        deleteFolder(f.id, f.name);
        return;
      }
      if (ul.children.length) {
        ul.style.display = ul.style.display === "none" ? "" : "none";
        toggle.textContent = ul.style.display === "none" ? "▸" : "▾";
      }
    });
    return li;
  }

  function renderTree(data) {
    folderTree = data.folders || [];
    treeEl.innerHTML = "";
    const ul = document.createElement("ul");
    for (const f of folderTree) ul.appendChild(createFolderNode(f));
    for (const m of data.materials || []) ul.appendChild(createMaterialNode(m));
    treeEl.appendChild(ul);
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /* ---------- API 调用 ---------- */

  async function refreshTree() {
    const resp = await fetch("/api/tree");
    renderTree(await resp.json());
  }

  async function loadMaterial(id) {
    const resp = await fetch(`/api/materials/${id}`);
    if (!resp.ok) return;
    const data = await resp.json();
    activeMaterialId = id;

    if (data.status === "processing") {
      dialogAlert("提示", "该素材仍在生成中，请稍候再试");
      return;
    }
    if (data.status === "failed") {
      dialogAlert("生成失败", data.error_msg || "未知错误");
      return;
    }
    window.Player.load(data);
    refreshTree();
    checkExportStatus(id);
  }

  async function createFolder(name, parentId) {
    await fetch("/api/folders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, parent_id: parentId || null }),
    });
    refreshTree();
  }

  async function renameFolder(id, name) {
    await fetch(`/api/folders/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    refreshTree();
  }

  async function deleteFolder(id, name) {
    const ok = await dialogConfirm("删除文件夹", `删除文件夹「${name}」？其中的素材记录将一并删除。`);
    if (!ok) return;
    await fetch(`/api/folders/${id}`, { method: "DELETE" });
    refreshTree();
  }

  async function deleteMaterial(id, title) {
    const ok = await dialogConfirm("删除素材", `删除素材「${title}」？`);
    if (!ok) return;
    await fetch(`/api/materials/${id}`, { method: "DELETE" });
    if (activeMaterialId === id) {
      activeMaterialId = null;
      window.Player.clear();
      btnExport.disabled = true;
    }
    refreshTree();
  }

  /* ---------- 导出（单按钮：未导出→触发导出；已导出→下载） ---------- */

  let exportReady = false;

  function setExportButton(ready) {
    exportReady = ready;
    btnExport.disabled = false;
    btnExport.textContent = ready ? "下载 MP4" : "导出视频";
  }

  async function checkExportStatus(id) {
    const resp = await fetch(`/api/materials/${id}/export/status`);
    const data = await resp.json();
    setExportButton(data.status === "done");
  }

  async function startExport() {
    if (!activeMaterialId) return;
    // 已导出：直接下载
    if (exportReady) {
      window.open(`/api/materials/${activeMaterialId}/export/download`, "_blank");
      return;
    }
    btnExport.disabled = true;
    btnExport.textContent = "导出中…";
    await fetch(`/api/materials/${activeMaterialId}/export`, { method: "POST" });
    const id = activeMaterialId;
    const timer = setInterval(async () => {
      const resp = await fetch(`/api/materials/${id}/export/status`);
      const data = await resp.json();
      if (data.status === "done") {
        clearInterval(timer);
        setExportButton(true);
      } else if (data.status === "failed") {
        clearInterval(timer);
        setExportButton(false);
        dialogAlert("导出失败", data.error || "未知错误");
      }
    }, 3000);
  }

  /* ---------- 事件绑定 ---------- */

  btnImport.addEventListener("click", () => window.Upload.open());
  btnExport.addEventListener("click", startExport);
  btnNewFolder.addEventListener("click", async () => {
    const name = await dialogPrompt("新建文件夹");
    if (name) createFolder(name, null);
  });

  /* ---------- 对外接口 ---------- */

  window.App = {
    refreshTree,
    loadMaterial,
    getFolderTree: () => folderTree,
  };

  refreshTree();
})();
