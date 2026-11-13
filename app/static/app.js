"use strict";

const ENTITY_LABELS = {
  PERSON: "人名",
  ORGANIZATION: "机构",
  PROJECT: "项目",
  DEPARTMENT: "部门",
  LOCATION: "详细地址",
  PHONE: "手机号",
  ID_CARD: "身份证",
  BANK_CARD: "银行卡",
  EMAIL: "邮箱",
  CREDIT_CODE: "信用代码",
  SECURITY_CODE: "证券代码",
  AMOUNT: "金额",
  DATE: "日期",
  IP_ADDRESS: "IP 地址",
  BUSINESS_SECRET: "业务秘密",
  CUSTOM: "自定义",
};

const state = {
  entities: [],
  activeEntityId: null,
  mapping: null,
  dictionary: [],
  settings: {},
  restoreMapping: null,
  restoreMappingSource: null,
  semanticAvailable: false,
  outputSelection: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function announce(message) {
  $("#live-region").textContent = message;
}

function showMessage(element, message, kind = "") {
  element.textContent = message;
  element.className = `inline-message ${kind}`.trim();
  element.hidden = !message;
}

async function api(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let body;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    throw new Error(body?.detail || `请求失败（${response.status}）`);
  }
  return body;
}

function switchTab(tab) {
  $$(".nav-item").forEach((button) => {
    const active = button.dataset.tab === tab;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  $$(".tab-panel").forEach((panel) => {
    const active = panel.dataset.panel === tab;
    panel.hidden = !active;
    panel.classList.toggle("is-active", active);
  });
  if (tab === "dictionary") loadDictionary();
  if (tab === "settings") loadSettings();
  if (tab === "restore") syncRestoreMappingDisplay();
}

function setAnalyzing(loading) {
  const button = $("#analyze-button");
  button.disabled = loading;
  button.textContent = loading ? "正在识别..." : "识别敏感信息";
  if (loading) {
    $("#review-empty").hidden = true;
    $("#entity-list-wrap").hidden = false;
    $("#entity-list").classList.add("is-loading");
    $("#entity-list").innerHTML = Array.from(
      { length: 3 },
      () => '<div class="entity-row" aria-hidden="true">正在识别</div>',
    ).join("");
  } else {
    $("#entity-list").classList.remove("is-loading");
  }
}

async function analyzeText() {
  const text = $("#source-text").value;
  const useLlm = $('input[name="mode"]:checked').value === "semantic";
  showMessage($("#redact-error"), "");
  if (!text.trim()) {
    showMessage($("#redact-error"), "请先输入需要识别的文本。", "error");
    $("#source-text").focus();
    return;
  }
  setAnalyzing(true);
  try {
    const result = await api("/analyze/text", {
      method: "POST",
      body: JSON.stringify({ text, use_llm: useLlm }),
    });
    state.entities = result.entities;
    state.activeEntityId = state.entities[0]?.id || null;
    state.mapping = null;
    renderEntities();
    renderHighlights();
    resetOutput();
    announce(
      `${useLlm ? "语义增强" : "快速模式"}识别完成，共发现 ${state.entities.length} 项。`,
    );
  } catch (error) {
    showMessage($("#redact-error"), error.message, "error");
    state.entities = [];
    renderEntities();
  } finally {
    setAnalyzing(false);
  }
}

function renderEntities() {
  const list = $("#entity-list");
  const hasEntities = state.entities.length > 0;
  $("#review-empty").hidden = hasEntities;
  $("#entity-list-wrap").hidden = !hasEntities;
  $("#entity-detail").hidden = !hasEntities;
  $("#anonymize-button").disabled = !hasEntities;
  $("#entity-count").textContent = hasEntities
    ? `${state.entities.length} 项候选`
    : "尚未识别";

  if (!hasEntities) {
    list.innerHTML = "";
    return;
  }

  list.innerHTML = state.entities
    .map((entity) => {
      const source = sourceLabel(entity.source);
      const classes = [
        "entity-row",
        entity.id === state.activeEntityId ? "is-active" : "",
        entity.conflict ? "has-conflict" : "",
      ]
        .filter(Boolean)
        .join(" ");
      return `
        <div class="${classes}" data-entity-id="${escapeAttribute(entity.id)}">
          <label class="entity-check" aria-label="是否脱敏 ${escapeHtml(entity.text)}">
            <input type="checkbox" data-entity-check="${escapeAttribute(entity.id)}" ${
              entity.selected ? "checked" : ""
            }>
          </label>
          <button class="entity-row-button" type="button" data-entity-open="${escapeAttribute(
            entity.id,
          )}" aria-label="编辑 ${escapeAttribute(entity.text)}">
            <span class="entity-main">
              <span class="entity-type">${escapeHtml(
                ENTITY_LABELS[entity.entity_type] || entity.entity_type,
              )}${entity.conflict ? "（冲突）" : ""}</span>
              <span class="entity-text">${escapeHtml(entity.text)}</span>
            </span>
          </button>
          <span class="entity-source">${escapeHtml(source)}</span>
        </div>
      `;
    })
    .join("");

  $$("[data-entity-check]").forEach((checkbox) => {
    checkbox.addEventListener("change", (event) => {
      const entity = findEntity(event.target.dataset.entityCheck);
      if (!entity) return;
      event.target.checked = setEntitySelected(entity, event.target.checked);
      renderHighlights();
    });
  });
  $$("[data-entity-open]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeEntityId = button.dataset.entityOpen;
      renderEntities();
    });
  });
  renderEntityDetail();
}

function renderEntityDetail() {
  const entity = findEntity(state.activeEntityId) || state.entities[0];
  if (!entity) return;
  state.activeEntityId = entity.id;
  const typeSelect = $("#detail-type");
  if (!typeSelect.options.length) {
    typeSelect.innerHTML = Object.entries(ENTITY_LABELS)
      .map(([value, label]) => `<option value="${value}">${label}</option>`)
      .join("");
  }
  typeSelect.value = entity.entity_type;
  $("#detail-text").value = entity.text;
  $("#detail-start").value = entity.start;
  $("#detail-end").value = entity.end;
  $("#conflict-message").hidden = !entity.conflict;
}

function applyEntityDetail() {
  const entity = findEntity(state.activeEntityId);
  const source = $("#source-text").value;
  if (!entity) return;
  const start = Number($("#detail-start").value);
  const end = Number($("#detail-end").value);
  const text = source.slice(start, end);
  if (
    !Number.isInteger(start) ||
    !Number.isInteger(end) ||
    start < 0 ||
    end <= start ||
    end > source.length
  ) {
    showMessage($("#redact-error"), "实体位置无效，请检查起始和结束位置。", "error");
    return;
  }
  if ($("#detail-text").value !== text) {
    showMessage(
      $("#redact-error"),
      `当前位置对应的原文是“${text}”，请确认边界后再保存。`,
      "error",
    );
    return;
  }
  entity.start = start;
  entity.end = end;
  entity.text = text;
  entity.entity_type = $("#detail-type").value;
  entity.conflict = false;
  showMessage($("#redact-error"), "");
  renderEntities();
  renderHighlights();
  announce("实体修改已应用。");
}

async function addOutputSelection() {
  const editor = $("#redacted-output");
  const selection = state.outputSelection;
  $("#output-selection-toolbar").hidden = true;
  if (!selection || selection.start === selection.end) return;
  const text = editor.textContent.slice(selection.start, selection.end);
  const source = $("#source-text").value;
  const occurrences = [];
  let searchFrom = 0;
  while (searchFrom <= source.length - text.length) {
    const index = source.indexOf(text, searchFrom);
    if (index === -1) break;
    occurrences.push(index);
    searchFrom = index + Math.max(1, text.length);
  }
  if (occurrences.length !== 1) {
    showMessage(
      $("#redact-error"),
      occurrences.length
        ? "原文中存在多处相同文字，暂时无法确定你选择的是哪一处。"
        : "选中的内容无法在原文中定位，请重新生成后再试。",
      "error",
    );
    switchTab("redact");
    return;
  }
  const start = occurrences[0];
  const end = start + text.length;
  const entity = {
    id: crypto.randomUUID(),
    text,
    entity_type: "CUSTOM",
    start,
    end,
    confidence: 1,
    source: "manual",
    selected: true,
    replacement: null,
    reason: "用户手动添加",
    conflict: state.entities.some((item) => rangesOverlap(item, { start, end })),
  };
  if (entity.conflict) entity.selected = false;
  state.entities.push(entity);
  state.entities.sort((left, right) => left.start - right.start || left.end - right.end);
  state.activeEntityId = entity.id;
  renderEntities();
  renderHighlights();
  showMessage(
    $("#redact-error"),
    entity.conflict ? "新实体与现有候选重叠，已标记为待处理冲突。" : "",
    entity.conflict ? "error" : "",
  );
  state.outputSelection = null;
  if (entity.conflict) {
    announce(`“${text}”与现有实体冲突，请先处理冲突。`);
    return;
  }
  await anonymizeText();
  announce(`已将“${text}”标记为自定义脱敏并更新结果。`);
}

function syncOutputSelectionToolbar(editor, pointerEvent = null) {
  const toolbar = $("#output-selection-toolbar");
  const selection = window.getSelection();
  if (
    !selection ||
    selection.isCollapsed ||
    selection.rangeCount === 0
  ) {
    toolbar.hidden = true;
    return;
  }
  const range = selection.getRangeAt(0);
  if (!editor.contains(range.commonAncestorContainer)) {
    toolbar.hidden = true;
    return;
  }
  const before = range.cloneRange();
  before.selectNodeContents(editor);
  before.setEnd(range.startContainer, range.startOffset);
  const start = before.toString().length;
  const end = start + range.toString().length;
  state.outputSelection = {
    start,
    end,
  };
  toolbar.hidden = false;
  toolbar.style.visibility = "hidden";
  const rangeRects = Array.from(range.getClientRects());
  const selectionRect =
    rangeRects.length > 0
      ? rangeRects[rangeRects.length - 1]
      : range.getBoundingClientRect();
  const anchorLeft =
    pointerEvent && Number.isFinite(pointerEvent.clientX)
      ? pointerEvent.clientX + 8
      : selectionRect.right + 8;
  const anchorTop =
    pointerEvent && Number.isFinite(pointerEvent.clientY)
      ? pointerEvent.clientY + 8
      : selectionRect.bottom + 7;
  const left = Math.min(
    Math.max(8, anchorLeft),
    window.innerWidth - toolbar.offsetWidth - 8,
  );
  const top = Math.min(
    Math.max(8, anchorTop),
    window.innerHeight - toolbar.offsetHeight - 8,
  );
  toolbar.style.left = `${left}px`;
  toolbar.style.top = `${top}px`;
  toolbar.style.visibility = "";
}

function deleteActiveEntity() {
  state.entities = state.entities.filter((entity) => entity.id !== state.activeEntityId);
  state.activeEntityId = state.entities[0]?.id || null;
  renderEntities();
  renderHighlights();
}

function selectAllEntities() {
  const selected = [];
  state.entities.forEach((entity) => {
    const overlaps = selected.some((item) => rangesOverlap(item, entity));
    entity.selected = !entity.conflict && !overlaps;
    if (entity.selected) selected.push(entity);
  });
  renderEntities();
  renderHighlights();
}

function clearEntities() {
  state.entities = [];
  state.activeEntityId = null;
  renderEntities();
  renderHighlights();
  resetOutput();
}

function renderHighlights() {
  const source = $("#source-text").value;
  const region = $("#highlight-region");
  if (!state.entities.length) {
    region.hidden = true;
    $("#highlight-preview").textContent = "";
    return;
  }
  region.hidden = false;
  const preview = $("#highlight-preview");
  preview.innerHTML = "";
  const usable = [];
  for (const entity of [...state.entities].sort(
    (left, right) => left.start - right.start || right.end - left.end,
  )) {
    if (!usable.some((item) => rangesOverlap(item, entity))) usable.push(entity);
  }
  let cursor = 0;
  usable.forEach((entity) => {
    preview.append(document.createTextNode(source.slice(cursor, entity.start)));
    const mark = document.createElement("mark");
    mark.className = `entity-highlight ${
      entity.conflict ? "is-conflict" : entity.selected ? "is-selected" : ""
    }`;
    mark.textContent = source.slice(entity.start, entity.end);
    mark.dataset.highlightEntity = entity.id;
    mark.tabIndex = 0;
    mark.setAttribute("role", "checkbox");
    mark.setAttribute("aria-checked", String(entity.selected));
    mark.setAttribute(
      "aria-label",
      `${entity.selected ? "取消脱敏" : "选择脱敏"} ${entity.text}`,
    );
    mark.title =
      `${ENTITY_LABELS[entity.entity_type] || entity.entity_type}，` +
      `${sourceLabel(entity.source)}；点击${entity.selected ? "取消" : "选择"}脱敏`;
    const toggle = () => {
      const nextSelected = !entity.selected;
      const selected = setEntitySelected(entity, nextSelected);
      if (nextSelected && !selected) return;
      state.activeEntityId = entity.id;
      renderEntities();
      renderHighlights();
      announce(`${entity.text}已${entity.selected ? "选择脱敏" : "取消脱敏"}。`);
    };
    mark.addEventListener("click", toggle);
    mark.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      toggle();
    });
    preview.append(mark);
    cursor = entity.end;
  });
  preview.append(document.createTextNode(source.slice(cursor)));
}

function setEntitySelected(entity, selected) {
  if (selected && overlapsSelected(entity)) {
    entity.selected = false;
    showMessage(
      $("#redact-error"),
      "此项与已选择实体重叠，请先取消另一项或调整边界。",
      "error",
    );
    return false;
  }
  entity.selected = selected;
  showMessage($("#redact-error"), "");
  return selected;
}

async function anonymizeText() {
  showMessage($("#redact-error"), "");
  const selected = state.entities.filter((entity) => entity.selected);
  if (!selected.length) {
    showMessage($("#redact-error"), "请至少选择一个需要脱敏的实体。", "error");
    return;
  }
  const button = $("#anonymize-button");
  button.disabled = true;
  button.textContent = "正在生成...";
  try {
    const result = await api("/anonymize/text", {
      method: "POST",
      body: JSON.stringify({
        text: $("#source-text").value,
        entities: state.entities,
      }),
    });
    $("#redacted-output").textContent = result.text;
    $("#redacted-output").hidden = false;
    $("#output-empty").hidden = true;
    $("#copy-button").disabled = false;
    $("#download-button").disabled = false;
    state.mapping = result.mapping;
    state.restoreMapping = result.mapping;
    state.restoreMappingSource = "current";
    syncRestoreMappingDisplay();
    result.entities.forEach((assigned) => {
      const entity = findEntity(assigned.id);
      if (entity) entity.replacement = assigned.replacement;
    });
    announce("脱敏文本已生成。");
  } catch (error) {
    showMessage($("#redact-error"), error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "生成脱敏文本";
  }
}

function resetOutput() {
  state.mapping = null;
  $("#redacted-output").textContent = "";
  $("#redacted-output").hidden = true;
  $("#output-empty").hidden = false;
  $("#copy-button").disabled = true;
  $("#download-button").disabled = true;
  state.outputSelection = null;
  $("#output-selection-toolbar").hidden = true;
}

async function copyText(text, button, doneLabel = "已复制") {
  await navigator.clipboard.writeText(text);
  const original = button.textContent;
  button.textContent = doneLabel;
  announce(doneLabel);
  setTimeout(() => {
    button.textContent = original;
  }, 1200);
}

function downloadMapping() {
  if (!state.mapping) return;
  const blob = new Blob([JSON.stringify(state.mapping, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `privacy-mapping-${state.mapping.document_id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
  announce("映射文件已下载。当前为明文 JSON，请妥善保管。");
}

async function loadRestoreMapping(file) {
  try {
    state.restoreMapping = JSON.parse(await file.text());
    state.restoreMappingSource = "file";
    syncRestoreMappingDisplay(file.name);
    showMessage($("#restore-error"), "");
  } catch {
    state.restoreMapping = null;
    state.restoreMappingSource = null;
    showMessage($("#restore-error"), "映射文件不是有效的 JSON。", "error");
    syncRestoreMappingDisplay();
  }
}

function syncRestoreMappingDisplay(fileName = "") {
  const message = $("#mapping-file-name");
  if (!state.restoreMapping) {
    message.textContent =
      "当前会话还没有可用映射。请先完成一次脱敏，或手动选择映射 JSON 文件。";
    return;
  }
  const count = Array.isArray(state.restoreMapping.mappings)
    ? state.restoreMapping.mappings.length
    : 0;
  const documentId = state.restoreMapping.document_id || "未提供";
  if (state.restoreMappingSource === "file") {
    message.textContent =
      `正在使用手动选择的映射：${fileName || "已上传文件"}，` +
      `${count} 条，文档 ID：${documentId}`;
  } else {
    message.textContent =
      `正在使用本次脱敏生成的映射，共 ${count} 条，文档 ID：${documentId}。` +
      "刷新或关闭页面后会自动清除。";
  }
}

async function restoreText() {
  if (!state.restoreMapping) {
    showMessage(
      $("#restore-error"),
      "当前没有可用映射。请先完成一次脱敏，或手动选择映射文件。",
      "error",
    );
    return;
  }
  try {
    const result = await api("/restore/text", {
      method: "POST",
      body: JSON.stringify({
        text: $("#restore-input").value,
        mapping: state.restoreMapping,
      }),
    });
    $("#restore-output").value = result.text;
    $("#copy-restore-button").disabled = false;
    $("#restore-summary").textContent =
      `已替换 ${result.replaced.length} 个占位符；` +
      `未使用 ${result.unused_mappings.length} 个；` +
      `未知 ${result.unknown_placeholders.length} 个。`;
    showMessage($("#restore-error"), "");
    announce("文本恢复完成。");
  } catch (error) {
    showMessage($("#restore-error"), error.message, "error");
  }
}

async function loadDictionary() {
  try {
    state.dictionary = await api("/dictionary");
    renderDictionary();
  } catch (error) {
    showMessage($("#dictionary-message"), error.message, "error");
  }
}

function renderDictionary() {
  const list = $("#dictionary-list");
  $("#dictionary-empty").hidden = state.dictionary.length > 0;
  list.innerHTML = state.dictionary
    .map(
      (entry, index) => `
        <div class="dictionary-row" data-dictionary-index="${index}">
          <input type="text" value="${escapeAttribute(entry.value)}" aria-label="词典内容">
          <select aria-label="实体类型">${typeOptions(entry.entity_type)}</select>
          <label class="checkbox-label">
            <input type="checkbox" ${entry.enabled ? "checked" : ""}>启用
          </label>
          <button class="text-button danger-text" type="button" data-remove-dictionary="${index}">删除</button>
        </div>
      `,
    )
    .join("");
  $$("[data-remove-dictionary]").forEach((button) => {
    button.addEventListener("click", () => {
      state.dictionary.splice(Number(button.dataset.removeDictionary), 1);
      renderDictionary();
    });
  });
}

function collectDictionary() {
  return $$(".dictionary-row").map((row) => ({
    value: row.querySelector('input[type="text"]').value.trim(),
    entity_type: row.querySelector("select").value,
    enabled: row.querySelector('input[type="checkbox"]').checked,
    selected: true,
  }));
}

async function saveDictionary() {
  const entries = collectDictionary();
  if (entries.some((entry) => !entry.value)) {
    showMessage($("#dictionary-message"), "词典内容不能为空。", "error");
    return;
  }
  try {
    state.dictionary = await api("/dictionary", {
      method: "PUT",
      body: JSON.stringify(entries),
    });
    renderDictionary();
    showMessage($("#dictionary-message"), "词典已保存到本机。");
    announce("业务词典已保存。");
  } catch (error) {
    showMessage($("#dictionary-message"), error.message, "error");
  }
}

async function loadSettings() {
  try {
    const result = await api("/settings");
    state.settings = result.entity_defaults;
    renderSettings();
  } catch (error) {
    showMessage($("#settings-message"), error.message, "error");
  }
}

function renderSettings() {
  $("#settings-list").innerHTML = Object.entries(ENTITY_LABELS)
    .map(
      ([type, label]) => `
        <label class="setting-row">
          <span>${label}</span>
          <input type="checkbox" data-setting-type="${type}" ${
            state.settings[type] ? "checked" : ""
          } aria-label="${label}识别后默认脱敏">
        </label>
      `,
    )
    .join("");
}

async function saveSettings() {
  $$("[data-setting-type]").forEach((input) => {
    state.settings[input.dataset.settingType] = input.checked;
  });
  try {
    const result = await api("/settings", {
      method: "PUT",
      body: JSON.stringify({ entity_defaults: state.settings }),
    });
    state.settings = result.entity_defaults;
    showMessage($("#settings-message"), "默认策略已保存到本机。");
    announce("设置已保存。");
  } catch (error) {
    showMessage($("#settings-message"), error.message, "error");
  }
}

function findEntity(id) {
  return state.entities.find((entity) => entity.id === id);
}

function rangesOverlap(left, right) {
  return left.start < right.end && right.start < left.end;
}

function overlapsSelected(entity) {
  return state.entities.some(
    (item) => item.id !== entity.id && item.selected && rangesOverlap(item, entity),
  );
}

function sourceLabel(source) {
  if (source.includes("dictionary")) return "业务词典";
  if (source.includes("custom_regex")) return "自定义规则";
  if (source.includes("manual")) return "手动添加";
  if (source.includes("semantic") || source.includes("qwen")) return "语义模型";
  return "规则匹配";
}

async function loadModelStatus() {
  const option = $("#semantic-mode-option");
  const input = option.querySelector("input");
  const note = $("#semantic-note");
  try {
    const status = await api("/model/status");
    state.semanticAvailable = status.available;
    input.disabled = !status.available;
    option.classList.toggle("is-disabled", !status.available);
    option.title = status.message;
    note.textContent = status.available
      ? `语义增强已连接 ${status.model}，文本仅在本机处理。`
      : `${status.message}。快速模式仍可正常使用。`;
    note.classList.toggle("is-ready", status.available);
  } catch (error) {
    input.disabled = true;
    option.classList.add("is-disabled");
    note.textContent = `无法检测语义模型：${error.message}。快速模式仍可正常使用。`;
  }
}

function typeOptions(selected) {
  return Object.entries(ENTITY_LABELS)
    .map(
      ([value, label]) =>
        `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`,
    )
    .join("");
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value);
  return element.innerHTML;
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll('"', "&quot;");
}

function wireEvents() {
  $$(".nav-item").forEach((button) =>
    button.addEventListener("click", () => switchTab(button.dataset.tab)),
  );
  $("#source-text").addEventListener("input", (event) => {
    $("#source-count").textContent = `字数：${event.target.value.length}`;
    if (state.entities.length) {
      clearEntities();
      showMessage(
        $("#redact-error"),
        "原始文本已修改，请重新识别以确保字符位置准确。",
        "error",
      );
    }
  });
  const updateOutputSelection = (event = null) => {
    const editor = $("#redacted-output");
    requestAnimationFrame(() => syncOutputSelectionToolbar(editor, event));
  };
  $("#redacted-output").addEventListener("keyup", updateOutputSelection);
  $("#redacted-output").addEventListener("pointerup", updateOutputSelection);
  $("#redacted-output").addEventListener("mouseup", updateOutputSelection);
  $("#redacted-output").addEventListener("touchend", updateOutputSelection);
  document.addEventListener("selectionchange", () => {
    if (
      !$("#redacted-output").hidden
    ) {
      updateOutputSelection();
    }
  });
  $("#add-output-selection-button").addEventListener("mousedown", (event) => {
    event.preventDefault();
  });
  $("#analyze-button").addEventListener("click", analyzeText);
  $("#add-output-selection-button").addEventListener("click", addOutputSelection);
  $("#select-all-button").addEventListener("click", selectAllEntities);
  $("#clear-entities-button").addEventListener("click", clearEntities);
  $("#apply-detail-button").addEventListener("click", applyEntityDetail);
  $("#delete-entity-button").addEventListener("click", deleteActiveEntity);
  $("#anonymize-button").addEventListener("click", anonymizeText);
  $("#copy-button").addEventListener("click", () =>
    copyText($("#redacted-output").textContent, $("#copy-button")),
  );
  $("#download-button").addEventListener("click", downloadMapping);
  $("#mapping-file").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) loadRestoreMapping(file);
  });
  $("#restore-button").addEventListener("click", restoreText);
  $("#copy-restore-button").addEventListener("click", () =>
    copyText($("#restore-output").value, $("#copy-restore-button")),
  );
  $("#add-dictionary-button").addEventListener("click", () => {
    state.dictionary.push({
      value: "",
      entity_type: "CUSTOM",
      enabled: true,
      selected: true,
    });
    renderDictionary();
    $("#dictionary-list .dictionary-row:last-child input").focus();
  });
  $("#save-dictionary-button").addEventListener("click", saveDictionary);
  $("#save-settings-button").addEventListener("click", saveSettings);
}

wireEvents();
loadModelStatus();
