const state = {
  documents: [],
  selectedDocIds: new Set(),
  sessions: [],
  messages: [],
  sessionId: localStorage.getItem("research-assistant-session") || "",
  pending: false,
  lastSources: [],
  lastWorkflowLog: [],
  stats: null,
};

function resolveApiBase() {
  const configured = localStorage.getItem("research-assistant-api-base");
  if (configured) return configured.replace(/\/+$/, "");

  if (window.location.protocol === "file:") {
    return "http://127.0.0.1:8000";
  }

  const localHosts = new Set(["127.0.0.1", "localhost", "::1"]);
  if (localHosts.has(window.location.hostname) && window.location.port !== "8000") {
    return "http://127.0.0.1:8000";
  }

  return window.location.origin;
}

const API_BASE = resolveApiBase();

function apiUrl(path) {
  return new URL(path, `${API_BASE}/`).toString();
}

const elements = {
  sidebar: document.querySelector("#sidebar"),
  mobileOverlay: document.querySelector("#mobileOverlay"),
  mobileMenuButton: document.querySelector("#mobileMenuButton"),
  sidebarClose: document.querySelector("#sidebarClose"),
  newChatButton: document.querySelector("#newChatButton"),
  topNewChat: document.querySelector("#topNewChat"),
  refreshAll: document.querySelector("#refreshAll"),
  uploadInput: document.querySelector("#uploadInput"),
  dropZone: document.querySelector("#dropZone"),
  uploadProgress: document.querySelector("#uploadProgress"),
  uploadStatus: document.querySelector("#uploadStatus"),
  uploadPercent: document.querySelector("#uploadPercent"),
  uploadProgressBar: document.querySelector("#uploadProgressBar"),
  uploadLimit: document.querySelector("#uploadLimit"),
  documentList: document.querySelector("#documentList"),
  docCount: document.querySelector("#docCount"),
  selectAllDocs: document.querySelector("#selectAllDocs"),
  deleteSelectedDocs: document.querySelector("#deleteSelectedDocs"),
  sessionList: document.querySelector("#sessionList"),
  refreshSessions: document.querySelector("#refreshSessions"),
  healthButton: document.querySelector("#healthButton"),
  healthDot: document.querySelector("#healthDot"),
  healthText: document.querySelector("#healthText"),
  healthDetails: document.querySelector("#healthDetails"),
  chatArea: document.querySelector("#chatArea"),
  emptyState: document.querySelector("#emptyState"),
  messageList: document.querySelector("#messageList"),
  selectionText: document.querySelector("#selectionText"),
  clearSelection: document.querySelector("#clearSelection"),
  askForm: document.querySelector("#askForm"),
  queryInput: document.querySelector("#queryInput"),
  sendButton: document.querySelector("#sendButton"),
  topKSelect: document.querySelector("#topKSelect"),
  charCount: document.querySelector("#charCount"),
  workflowTrace: document.querySelector("#workflowTrace"),
  workflowState: document.querySelector("#workflowState"),
  sourceList: document.querySelector("#sourceList"),
  statDocuments: document.querySelector("#statDocuments"),
  statVectors: document.querySelector("#statVectors"),
  statSessions: document.querySelector("#statSessions"),
  toastRegion: document.querySelector("#toastRegion"),
};

const WORKFLOW_STAGES = ["research", "summarize", "critique", "edit"];

async function api(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    if (typeof payload === "string" && payload) {
      message = payload;
    } else if (payload?.detail) {
      message = Array.isArray(payload.detail)
        ? payload.detail.map((item) => item.msg || String(item)).join("；")
        : payload.detail;
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return payload;
}

function refreshIcons() {
  if (window.lucide?.createIcons) {
    window.lucide.createIcons({
      attrs: {
        "aria-hidden": "true",
      },
    });
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatInline(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function renderRichText(value) {
  const lines = String(value || "").replace(/\r\n/g, "\n").split("\n");
  const output = [];
  let listType = "";

  const closeList = () => {
    if (listType) {
      output.push(`</${listType}>`);
      listType = "";
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      continue;
    }

    const unorderedMatch = trimmed.match(/^[-*]\s+(.+)$/);
    const orderedMatch = trimmed.match(/^\d+[.)]\s+(.+)$/);

    if (unorderedMatch || orderedMatch) {
      const nextType = unorderedMatch ? "ul" : "ol";
      if (listType !== nextType) {
        closeList();
        listType = nextType;
        output.push(`<${listType}>`);
      }
      output.push(`<li>${formatInline((unorderedMatch || orderedMatch)[1])}</li>`);
      continue;
    }

    closeList();
    output.push(`<p>${formatInline(trimmed)}</p>`);
  }

  closeList();
  return output.join("");
}

function showToast(message, type = "success") {
  const toast = document.createElement("div");
  const icon = type === "error" ? "circle-alert" : "circle-check";
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <i data-lucide="${icon}"></i>
    <span>${escapeHtml(message)}</span>
  `;
  elements.toastRegion.appendChild(toast);
  refreshIcons();

  window.setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(6px)";
    window.setTimeout(() => toast.remove(), 180);
  }, 3600);
}

function setHealth(status, text, details) {
  elements.healthDot.className = `health-dot ${status}`;
  elements.healthText.textContent = text;
  elements.healthDetails.textContent = details;
}

async function checkHealth(showResult = false) {
  setHealth("loading", "检查服务状态", "正在连接后端");

  try {
    const response = await fetch(apiUrl("/health"));
    const payload = await response.json();
    const failed = Object.entries(payload.checks || {})
      .filter(([, value]) => value.status !== "ok")
      .map(([name]) => name);

    if (response.ok && failed.length === 0) {
      setHealth("ok", "所有服务正常", "MySQL · Milvus · API");
      if (showResult) showToast("后端服务运行正常");
      return true;
    }

    setHealth(
      "error",
      "部分服务不可用",
      failed.length ? `异常：${failed.join("、")}` : "请查看后端日志",
    );
    if (showResult) showToast("服务检查发现异常", "error");
    return false;
  } catch (error) {
    setHealth("error", "后端无法连接", error.message);
    if (showResult) showToast(error.message, "error");
    return false;
  }
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(Number(value) || 0);
}

function shortId(value) {
  if (!value) return "";
  return value.length > 12 ? `${value.slice(0, 8)}...${value.slice(-3)}` : value;
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function renderDocuments() {
  elements.docCount.textContent = String(state.documents.length);

  if (!state.documents.length) {
    elements.documentList.innerHTML = `
      <div class="empty-list">
        <i data-lucide="files"></i>
        <span>还没有上传文档</span>
      </div>
    `;
    updateSelectionUI();
    refreshIcons();
    return;
  }

  elements.documentList.innerHTML = state.documents
    .map((documentItem) => {
      const selected = state.selectedDocIds.has(documentItem.doc_id);
      const metadata = [
        documentItem.file_type,
        `${documentItem.chunks || 0} 个分块`,
        `${formatNumber(documentItem.characters)} 字符`,
      ]
        .filter(Boolean)
        .join(" · ");

      return `
        <article class="document-item ${selected ? "selected" : ""}">
          <input
            class="document-checkbox"
            type="checkbox"
            data-doc-select="${escapeHtml(documentItem.doc_id)}"
            ${selected ? "checked" : ""}
            aria-label="选择 ${escapeHtml(documentItem.original_filename)}"
          />
          <div class="document-copy">
            <strong title="${escapeHtml(documentItem.original_filename)}">
              ${escapeHtml(documentItem.original_filename)}
            </strong>
            <small title="${escapeHtml(metadata)}">${escapeHtml(metadata)}</small>
          </div>
          <button
            class="delete-document"
            type="button"
            data-delete-doc="${escapeHtml(documentItem.doc_id)}"
            aria-label="删除 ${escapeHtml(documentItem.original_filename)}"
            title="删除文档"
          >
            <i data-lucide="trash-2"></i>
          </button>
        </article>
      `;
    })
    .join("");

  updateSelectionUI();
  refreshIcons();
}

function updateSelectionUI() {
  const total = state.documents.length;
  const selected = state.selectedDocIds.size;

  if (total > 0 && selected === total) {
    elements.selectionText.textContent = `已选择全部 ${total} 个文档`;
  } else if (selected > 0) {
    elements.selectionText.textContent = `已选择 ${selected} / ${total} 个文档`;
  } else {
    elements.selectionText.textContent = "未选择文档时搜索全部资料";
  }

  elements.clearSelection.hidden = selected === 0;
  elements.deleteSelectedDocs.disabled = selected === 0;
  elements.selectAllDocs.querySelector("span").textContent =
    total > 0 && selected === total ? "取消全选" : "全选";
}

async function loadDocuments() {
  try {
    const payload = await api("/documents");
    state.documents = payload.documents || [];
    const validIds = new Set(state.documents.map((item) => item.doc_id));
    state.selectedDocIds = new Set(
      [...state.selectedDocIds].filter((id) => validIds.has(id)),
    );
    renderDocuments();
  } catch (error) {
    elements.documentList.innerHTML = `
      <div class="empty-list">
        <i data-lucide="circle-alert"></i>
        <span>${escapeHtml(error.message)}</span>
      </div>
    `;
    refreshIcons();
  }
}

async function uploadFiles(files) {
  const file = files?.[0];
  if (!file) return;

  const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
  const supported = [".pdf", ".docx", ".html", ".htm", ".txt"];
  if (!supported.includes(extension)) {
    showToast("不支持该文件格式，请上传 PDF、DOCX、HTML 或 TXT", "error");
    return;
  }

  elements.dropZone.disabled = true;
  elements.uploadProgress.hidden = false;
  elements.uploadStatus.textContent = `正在上传 ${file.name}`;
  elements.uploadPercent.textContent = "8%";
  elements.uploadProgressBar.style.width = "8%";

  let progress = 8;
  const timer = window.setInterval(() => {
    progress = Math.min(progress + Math.max(2, (90 - progress) / 7), 90);
    const rounded = Math.round(progress);
    elements.uploadPercent.textContent = `${rounded}%`;
    elements.uploadProgressBar.style.width = `${rounded}%`;
    if (progress > 35) {
      elements.uploadStatus.textContent = "正在解析文本并生成向量";
    }
  }, 650);

  try {
    const formData = new FormData();
    formData.append("file", file);
    const payload = await api("/upload", {
      method: "POST",
      body: formData,
    });

    state.selectedDocIds.add(payload.doc_id);
    elements.uploadStatus.textContent = "文档已入库";
    elements.uploadPercent.textContent = "100%";
    elements.uploadProgressBar.style.width = "100%";
    showToast(
      `${payload.filename} 上传成功，共生成 ${payload.chunks} 个分块`,
    );
    await Promise.all([loadDocuments(), loadStats()]);
  } catch (error) {
    elements.uploadStatus.textContent = "上传失败";
    showToast(error.message, "error");
  } finally {
    window.clearInterval(timer);
    elements.dropZone.disabled = false;
    window.setTimeout(() => {
      elements.uploadProgress.hidden = true;
      elements.uploadProgressBar.style.width = "0";
    }, 1200);
  }
}

async function deleteDocument(docId) {
  const documentItem = state.documents.find((item) => item.doc_id === docId);
  if (!documentItem) return;

  const confirmed = window.confirm(
    `确认删除“${documentItem.original_filename}”及其全部分块？`,
  );
  if (!confirmed) return;

  try {
    await api(`/documents/${encodeURIComponent(docId)}`, { method: "DELETE" });
    state.selectedDocIds.delete(docId);
    showToast("文档已删除");
    await Promise.all([loadDocuments(), loadStats()]);
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function deleteSelectedDocuments() {
  const ids = [...state.selectedDocIds];
  if (!ids.length) return;
  const confirmed = window.confirm(`确认删除选中的 ${ids.length} 个文档？`);
  if (!confirmed) return;

  try {
    await Promise.all(
      ids.map((docId) =>
        api(`/documents/${encodeURIComponent(docId)}`, { method: "DELETE" }),
      ),
    );
    ids.forEach((id) => state.selectedDocIds.delete(id));
    showToast(`已删除 ${ids.length} 个文档`);
    await Promise.all([loadDocuments(), loadStats()]);
  } catch (error) {
    showToast(error.message, "error");
  }
}

function renderSessions() {
  if (!state.sessions.length) {
    elements.sessionList.innerHTML =
      '<p class="session-empty">暂无历史会话</p>';
    return;
  }

  elements.sessionList.innerHTML = state.sessions
    .slice(0, 10)
    .map(
      (sessionId) => `
        <button
          class="session-item ${sessionId === state.sessionId ? "active" : ""}"
          type="button"
          data-session-id="${escapeHtml(sessionId)}"
          title="${escapeHtml(sessionId)}"
        >
          <i data-lucide="message-square-text"></i>
          <span>${escapeHtml(shortId(sessionId))}</span>
        </button>
      `,
    )
    .join("");
  refreshIcons();
}

async function loadSessions() {
  try {
    const payload = await api("/sessions");
    state.sessions = payload.sessions || [];
    renderSessions();
  } catch {
    state.sessions = [];
    renderSessions();
  }
}

async function loadHistory(sessionId) {
  try {
    const payload = await api(
      `/sessions/${encodeURIComponent(sessionId)}/history`,
    );
    state.sessionId = sessionId;
    localStorage.setItem("research-assistant-session", sessionId);
    state.messages = (payload.messages || []).map((message) => ({
      role: message.role,
      content: message.content,
      timestamp: message.timestamp,
      sources: message.metadata?.sources || [],
      workflowLog: message.metadata?.workflow_log || [],
    }));
    renderMessages();
    renderSessions();
  } catch (error) {
    showToast(error.message, "error");
  }
}

function resetWorkflow() {
  elements.workflowTrace
    .querySelectorAll(".trace-step")
    .forEach((step) => step.classList.remove("active", "complete"));
  elements.workflowState.textContent = "等待提问";
}

function setWorkflowStage(stage, status) {
  const step = elements.workflowTrace.querySelector(`[data-step="${stage}"]`);
  if (!step) return;
  step.classList.remove("active", "complete");
  if (status) step.classList.add(status);
}

function applyWorkflowLog(logs, complete = false) {
  resetWorkflow();
  WORKFLOW_STAGES.forEach((stage) => {
    const matched = (logs || []).some((line) =>
      line.toLowerCase().includes(stage),
    );
    if (matched) {
      setWorkflowStage(stage, complete ? "complete" : "active");
    }
  });

  if (logs?.length) {
    elements.workflowState.textContent = logs[logs.length - 1];
  }
}

function startWorkflowAnimation() {
  resetWorkflow();
  setWorkflowStage("research", "active");
  elements.workflowState.textContent = "Research Agent 正在检索文档";

  const timers = [
    window.setTimeout(() => {
      setWorkflowStage("research", "complete");
      setWorkflowStage("summarize", "active");
      elements.workflowState.textContent = "Summarizer Agent 正在生成初稿";
    }, 850),
    window.setTimeout(() => {
      setWorkflowStage("summarize", "complete");
      setWorkflowStage("critique", "active");
      elements.workflowState.textContent = "Critic Agent 正在检查回答";
    }, 1800),
    window.setTimeout(() => {
      setWorkflowStage("critique", "complete");
      setWorkflowStage("edit", "active");
      elements.workflowState.textContent = "正在整理最终回答";
    }, 2900),
  ];

  return () => timers.forEach(window.clearTimeout);
}

function renderSources(sources) {
  elements.sourceList.innerHTML = "";
  if (!sources?.length) {
    elements.sourceList.innerHTML =
      '<p class="muted-copy">提出问题后，这里会显示引用来源。</p>';
    return;
  }

  const uniqueSources = [...new Set(sources)];
  elements.sourceList.innerHTML = uniqueSources
    .map(
      (source) => `
        <span class="source-chip" title="${escapeHtml(source)}">
          <i data-lucide="file-text"></i>
          <span>${escapeHtml(source)}</span>
        </span>
      `,
    )
    .join("");
  refreshIcons();
}

function renderMessages() {
  const hasMessages = state.messages.length > 0 || state.pending;
  elements.emptyState.classList.toggle("hidden", hasMessages);

  const messagesHtml = state.messages
    .map((message) => {
      const isUser = message.role === "user";
      const messageClass = isUser ? "user" : "assistant";
      const avatar = isUser
        ? ""
        : `
          <span class="message-avatar">
            <i data-lucide="sparkles"></i>
          </span>
        `;

      const sources =
        !isUser && message.sources?.length
          ? `
            <div class="message-sources">
              ${[...new Set(message.sources)]
                .map(
                  (source) => `
                    <span class="source-chip" title="${escapeHtml(source)}">
                      <i data-lucide="file-text"></i>
                      <span>${escapeHtml(source)}</span>
                    </span>
                  `,
                )
                .join("")}
            </div>
          `
          : "";

      const trace =
        !isUser && message.workflowLog?.length
          ? `
            <details class="message-trace">
              <summary>
                <i data-lucide="list-tree"></i>
                查看智能体执行过程
              </summary>
              <div class="trace-log">
                ${message.workflowLog
                  .map((line) => `<p>${escapeHtml(line)}</p>`)
                  .join("")}
              </div>
            </details>
          `
          : "";

      return `
        <article class="message ${messageClass} ${message.error ? "error-message" : ""}">
          ${avatar}
          <div class="message-body">
            <div class="message-meta">
              <span>${isUser ? "你" : "AI Research Assistant"}</span>
              <span>${escapeHtml(formatDate(message.timestamp))}</span>
            </div>
            <div class="message-content">${renderRichText(message.content)}</div>
            ${sources}
            ${trace}
          </div>
        </article>
      `;
    })
    .join("");

  const pendingHtml = state.pending
    ? `
      <article class="message assistant">
        <span class="message-avatar">
          <i data-lucide="sparkles"></i>
        </span>
        <div class="message-body">
          <div class="loading-message">
            <span class="loading-bars"><span></span><span></span><span></span></span>
            <span>多智能体正在协作生成回答...</span>
          </div>
        </div>
      </article>
    `
    : "";

  elements.messageList.innerHTML = messagesHtml + pendingHtml;
  refreshIcons();
  scrollToBottom();
}

function scrollToBottom() {
  window.requestAnimationFrame(() => {
    elements.chatArea.scrollTop = elements.chatArea.scrollHeight;
  });
}

async function loadStats() {
  try {
    const payload = await api("/stats");
    state.stats = payload;
    elements.statDocuments.textContent = String(
      payload.documents?.total_documents ?? state.documents.length,
    );
    elements.statVectors.textContent = String(
      payload.documents?.total_vectors ?? 0,
    );
    elements.statSessions.textContent = String(
      payload.conversations?.total_sessions ?? state.sessions.length,
    );
  } catch {
    elements.statDocuments.textContent = String(state.documents.length);
  }
}

async function sendMessage() {
  const query = elements.queryInput.value.trim();
  if (!query || state.pending) return;

  const userMessage = {
    role: "user",
    content: query,
    timestamp: new Date().toISOString(),
    sources: [],
    workflowLog: [],
  };

  state.messages.push(userMessage);
  state.pending = true;
  elements.queryInput.value = "";
  elements.queryInput.style.height = "auto";
  elements.charCount.textContent = "0 / 4000";
  elements.sendButton.disabled = true;
  renderMessages();
  const stopAnimation = startWorkflowAnimation();

  try {
    const payload = await api("/ask", {
      method: "POST",
      body: JSON.stringify({
        query,
        top_k: Number(elements.topKSelect.value),
        doc_ids: state.selectedDocIds.size
          ? [...state.selectedDocIds]
          : null,
        session_id: state.sessionId || null,
      }),
    });

    state.sessionId = payload.session_id;
    localStorage.setItem("research-assistant-session", state.sessionId);
    state.lastSources = payload.sources || [];
    state.lastWorkflowLog = payload.workflow_log || [];
    state.messages.push({
      role: "assistant",
      content: payload.answer,
      timestamp: new Date().toISOString(),
      sources: payload.sources || [],
      workflowLog: payload.workflow_log || [],
    });

    applyWorkflowLog(state.lastWorkflowLog, true);
    renderSources(state.lastSources);
    await Promise.all([loadSessions(), loadStats()]);
  } catch (error) {
    resetWorkflow();
    elements.workflowState.textContent = `执行失败：${error.message}`;
    state.messages.push({
      role: "assistant",
      content: `请求未完成：${error.message}`,
      timestamp: new Date().toISOString(),
      sources: [],
      workflowLog: [],
      error: true,
    });
    showToast(error.message, "error");
  } finally {
    stopAnimation();
    state.pending = false;
    elements.sendButton.disabled = false;
    renderMessages();
    renderSessions();
    elements.queryInput.focus();
  }
}

function startNewChat() {
  state.sessionId = "";
  state.messages = [];
  state.pending = false;
  state.lastSources = [];
  state.lastWorkflowLog = [];
  localStorage.removeItem("research-assistant-session");
  renderMessages();
  renderSources([]);
  resetWorkflow();
  renderSessions();
  closeSidebar();
  elements.queryInput.focus();
}

function openSidebar() {
  elements.sidebar.classList.add("open");
  elements.mobileOverlay.classList.add("open");
}

function closeSidebar() {
  elements.sidebar.classList.remove("open");
  elements.mobileOverlay.classList.remove("open");
}

function autoResizeTextarea() {
  elements.queryInput.style.height = "auto";
  elements.queryInput.style.height = `${Math.min(
    elements.queryInput.scrollHeight,
    180,
  )}px`;
  elements.charCount.textContent = `${elements.queryInput.value.length} / 4000`;
}

function bindEvents() {
  elements.mobileMenuButton.addEventListener("click", openSidebar);
  elements.sidebarClose.addEventListener("click", closeSidebar);
  elements.mobileOverlay.addEventListener("click", closeSidebar);
  elements.newChatButton.addEventListener("click", startNewChat);
  elements.topNewChat.addEventListener("click", startNewChat);

  elements.refreshAll.addEventListener("click", async () => {
    await Promise.all([
      checkHealth(true),
      loadDocuments(),
      loadSessions(),
      loadStats(),
    ]);
  });

  elements.healthButton.addEventListener("click", () => checkHealth(true));

  elements.dropZone.addEventListener("click", () => elements.uploadInput.click());
  elements.uploadInput.addEventListener("change", async (event) => {
    await uploadFiles(event.target.files);
    event.target.value = "";
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.add("dragging");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.remove("dragging");
    });
  });

  elements.dropZone.addEventListener("drop", async (event) => {
    await uploadFiles(event.dataTransfer?.files);
  });

  elements.documentList.addEventListener("change", (event) => {
    const checkbox = event.target.closest("[data-doc-select]");
    if (!checkbox) return;
    const docId = checkbox.dataset.docSelect;
    if (checkbox.checked) {
      state.selectedDocIds.add(docId);
    } else {
      state.selectedDocIds.delete(docId);
    }
    renderDocuments();
  });

  elements.documentList.addEventListener("click", (event) => {
    const deleteButton = event.target.closest("[data-delete-doc]");
    if (deleteButton) {
      deleteDocument(deleteButton.dataset.deleteDoc);
    }
  });

  elements.selectAllDocs.addEventListener("click", () => {
    if (state.selectedDocIds.size === state.documents.length) {
      state.selectedDocIds.clear();
    } else {
      state.selectedDocIds = new Set(
        state.documents.map((documentItem) => documentItem.doc_id),
      );
    }
    renderDocuments();
  });

  elements.deleteSelectedDocs.addEventListener(
    "click",
    deleteSelectedDocuments,
  );
  elements.clearSelection.addEventListener("click", () => {
    state.selectedDocIds.clear();
    renderDocuments();
  });

  elements.sessionList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-session-id]");
    if (!button) return;
    loadHistory(button.dataset.sessionId);
    closeSidebar();
  });

  elements.refreshSessions.addEventListener("click", loadSessions);
  elements.askForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage();
  });
  elements.queryInput.addEventListener("input", autoResizeTextarea);
  elements.queryInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  document.querySelectorAll("[data-question]").forEach((button) => {
    button.addEventListener("click", () => {
      elements.queryInput.value = button.dataset.question;
      autoResizeTextarea();
      elements.queryInput.focus();
    });
  });

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "n") {
      event.preventDefault();
      startNewChat();
    }
  });
}

async function initialize() {
  bindEvents();
  refreshIcons();
  autoResizeTextarea();
  renderSources([]);
  resetWorkflow();

  const uploadLimitMb = 50;
  elements.uploadLimit.textContent = `${uploadLimitMb} MB`;

  await Promise.all([
    checkHealth(),
    loadDocuments(),
    loadSessions(),
    loadStats(),
  ]);

  if (state.sessionId) {
    await loadHistory(state.sessionId);
  }

  window.setInterval(() => checkHealth(), 30000);
}

document.addEventListener("DOMContentLoaded", initialize);
