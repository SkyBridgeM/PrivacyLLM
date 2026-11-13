<script lang="ts">
  import { onMount } from "svelte";
  import {
    ShieldCheck,
    FileText,
    History,
    BookOpen,
    Settings2,
    Copy,
    Download,
    Plus,
    Trash2,
    Check,
    Circle,
    LoaderCircle,
  } from "@lucide/svelte";
  import { save } from "@tauri-apps/plugin-dialog";
  import { call, isTauri } from "./backend";
  import {
    labels,
    cpLength,
    cpSlice,
    utf16ToCodePoint,
    overlap,
    sourceLabel,
    type Entity,
    type EntityType,
    type Mapping,
    type ModelStatus,
  } from "./types";
  import Highlight from "./components/Highlight.svelte";
  import DictionaryPanel from "./components/DictionaryPanel.svelte";
  import SettingsPanel from "./components/SettingsPanel.svelte";
  let tab = $state("redact");
  let source = $state("");
  let entities = $state<Entity[]>([]);
  let output = $state("");
  let mapping = $state<Mapping | null>(null);
  let activeId = $state("");
  let draft = $state({ entity_type: "CUSTOM" as EntityType, start: 0, end: 1 });
  let mode = $state("quick");
  let busy = $state("");
  let error = $state("");
  let notice = $state("");
  let model = $state<ModelStatus | null>(null);
  let sourceEditor = $state<HTMLTextAreaElement>();
  let outputEditor = $state<HTMLDivElement>();
  let outputSelection = $state("");
  let restoreInput = $state("");
  let restoreOutput = $state("");
  let importedMapping = $state<Mapping | null>(null);
  let importedName = $state("");
  let restoreSummary = $state("");
  let selected = $derived(entities.filter((e) => e.selected));
  let active = $derived(entities.find((e) => e.id === activeId));
  let draftText = $derived(
    cpSlice(source, Math.max(0, draft.start || 0), Math.max(0, draft.end || 0)),
  );
  let outputParts = $derived(output.split(/(\[[A-Z][A-Z_]*_\d{3,}\])/g));
  const navigation = [
    { id: "redact", label: "脱敏工作台", icon: FileText },
    { id: "restore", label: "恢复文本", icon: History },
    { id: "dictionary", label: "业务词典", icon: BookOpen },
    { id: "settings", label: "设置与模型", icon: Settings2 },
  ];
  async function refreshModel() {
    if (!isTauri()) return;
    try {
      model = await call<ModelStatus>("model_status");
    } catch {
      /* Keep the last known state during shutdown. */
    }
  }
  onMount(() => {
    void refreshModel();
    const timer = setInterval(refreshModel, 1500);
    const selectionChanged = () => {
      const selection = window.getSelection();
      outputSelection =
        selection &&
        selection.rangeCount &&
        outputEditor?.contains(selection.getRangeAt(0).commonAncestorContainer)
          ? selection.toString()
          : "";
    };
    document.addEventListener("selectionchange", selectionChanged);
    return () => {
      clearInterval(timer);
      document.removeEventListener("selectionchange", selectionChanged);
    };
  });
  function changeTab(next: string) {
    tab = next;
    error = "";
    notice = "";
  }
  function invalidate() {
    entities = [];
    activeId = "";
    output = "";
    error = "";
    notice = "";
  }
  function example() {
    if (source && !confirm("使用示例将替换当前原文，是否继续？")) return;
    source =
      "张敏是星河科技有限公司的项目经理，负责北辰计划。\n联系电话 13812345678，邮箱 zhang@example.com。\n\n请协助整理项目进展，并保留沟通要点。";
    invalidate();
  }
  function focusEntity(id: string) {
    activeId = id;
    const e = entities.find((e) => e.id === id);
    if (e) draft = { entity_type: e.entity_type, start: e.start, end: e.end };
  }
  function toggleEntity(e: Entity, checked: boolean, input?: HTMLInputElement) {
    if (
      checked &&
      entities.some(
        (other) => other.id !== e.id && other.selected && overlap(e, other),
      )
    ) {
      error = "此项与已选实体重叠，请先取消重叠项。";
      if (input) input.checked = false;
      return;
    }
    entities = entities.map((other) =>
      other.id === e.id ? { ...other, selected: checked } : other,
    );
    output = "";
    focusEntity(e.id);
    error = "";
  }
  function selectAll() {
    const chosen: Entity[] = [];
    entities = entities.map((e) => {
      const selected =
        !e.conflict && !chosen.some((other) => overlap(e, other));
      const next = { ...e, selected };
      if (selected) chosen.push(next);
      return next;
    });
    output = "";
  }
  function applyDetail() {
    if (!active) return;
    if (
      !Number.isInteger(draft.start) ||
      !Number.isInteger(draft.end) ||
      draft.start < 0 ||
      draft.end <= draft.start ||
      draft.end > cpLength(source)
    ) {
      error = "请输入原文范围内有效的起止位置。";
      return;
    }
    const updated = { ...active, ...draft, text: draftText };
    if (
      updated.selected &&
      entities.some(
        (e) => e.id !== activeId && e.selected && overlap(e, updated),
      )
    ) {
      error = "修改后的范围与其他已选项重叠。";
      return;
    }
    entities = entities.map((e) => (e.id === activeId ? updated : e));
    output = "";
    error = "";
    notice = "候选项已更新。";
  }
  function addSelection() {
    if (!sourceEditor) return;
    const start = utf16ToCodePoint(source, sourceEditor.selectionStart);
    const end = utf16ToCodePoint(source, sourceEditor.selectionEnd);
    if (start === end) {
      error = "请先在原始文本中选中需要脱敏的文字。";
      return;
    }
    const e: Entity = {
      id: crypto.randomUUID(),
      text: cpSlice(source, start, end),
      entity_type: "CUSTOM",
      start,
      end,
      confidence: 1,
      source: "manual",
      selected: true,
      replacement: null,
      reason: "手动添加",
      conflict: false,
    };
    if (entities.some((other) => other.selected && overlap(e, other))) {
      error = "选中文字与已选实体重叠，请先调整选择。";
      return;
    }
    entities = [...entities, e].sort(
      (a, b) => a.start - b.start || a.end - b.end,
    );
    focusEntity(e.id);
    output = "";
    error = "";
  }
  function markOutputSelection() {
    const value = outputSelection;
    if (!value) return;
    if (/\[[A-Z][A-Z_]*_\d{3,}\]/.test(value)) {
      error = "请选择尚未脱敏的原文，不包含占位符。";
      return;
    }
    const matches: { start: number; end: number }[] = [];
    let cursor = 0;
    while (cursor < source.length) {
      const index = source.indexOf(value, cursor);
      if (index < 0) break;
      const start = utf16ToCodePoint(source, index);
      const range = { start, end: start + cpLength(value) };
      if (!selected.some((e) => overlap(e, range))) matches.push(range);
      cursor = index + Math.max(value.length, 1);
    }
    if (matches.length !== 1) {
      error = "无法唯一定位这段原文，请在左侧原始文本中选中后标记。";
      return;
    }
    const e: Entity = {
      id: crypto.randomUUID(),
      text: value,
      entity_type: "CUSTOM",
      ...matches[0],
      confidence: 1,
      source: "manual",
      selected: true,
      replacement: null,
      reason: "从脱敏结果补充",
      conflict: false,
    };
    entities = [...entities, e].sort((a, b) => a.start - b.start);
    focusEntity(e.id);
    outputSelection = "";
    void anonymize();
  }
  async function analyze() {
    const snapshot = source;
    if (!snapshot.trim()) {
      error = "请先粘贴需要识别的文本。";
      return;
    }
    busy = "analyze";
    error = "";
    notice = "";
    try {
      const result = await call<{ entities: Entity[] }>("analyze_text", {
        text: snapshot,
        useLlm: mode === "semantic",
      });
      if (source !== snapshot) {
        notice = "原文已修改，请重新识别。";
        return;
      }
      entities = result.entities;
      output = "";
      activeId = "";
      if (entities.length) focusEntity(entities[0].id);
      else notice = "没有发现匹配的敏感信息，可选中文字手动添加。";
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = "";
      void refreshModel();
    }
  }
  async function anonymize() {
    busy = "anonymize";
    error = "";
    const snapshot = source;
    try {
      const result = await call<{
        text: string;
        mapping: Mapping;
        entities: Entity[];
      }>("anonymize_text", { text: snapshot, entities });
      if (source !== snapshot) return;
      output = result.text;
      mapping = result.mapping;
      const replacements = new Map(
        result.entities.map((e) => [e.id, e.replacement]),
      );
      entities = entities.map((e) => ({
        ...e,
        replacement: replacements.get(e.id) ?? null,
      }));
      notice = "脱敏结果已生成，请复核后复制。";
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = "";
    }
  }
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      notice = "已复制。";
    } catch {
      error = "无法访问剪贴板，请选中文字后使用 ⌘C 复制。";
    }
  }
  async function exportMapping() {
    if (!mapping) return;
    try {
      const path = await save({
        defaultPath: `privacy-mapping-${new Date().toISOString().slice(0, 10)}.json`,
        filters: [{ name: "JSON 映射", extensions: ["json"] }],
      });
      if (path) {
        await call("export_mapping", { path, mapping });
        notice = "映射已导出，请妥善保存。";
      }
    } catch (e) {
      error = (e as Error).message;
    }
  }
  async function readMapping(event: Event) {
    const file = (event.currentTarget as HTMLInputElement).files?.[0];
    if (!file) return;
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error("映射文件超过 10 MB。");
      const value = JSON.parse(await file.text());
      if (value.version !== 1 || !Array.isArray(value.mappings))
        throw new Error("映射文件格式无效。");
      importedMapping = value;
      importedName = file.name;
      error = "";
      restoreOutput = "";
    } catch (e) {
      error = (e as Error).message;
    }
  }
  async function restore() {
    const chosen = importedMapping ?? mapping;
    if (!chosen) {
      error = "请先生成脱敏映射，或导入已有映射文件。";
      return;
    }
    busy = "restore";
    error = "";
    try {
      const result = await call<{
        text: string;
        replaced: string[];
        unused_mappings: string[];
        unknown_placeholders: string[];
      }>("restore_text", { text: restoreInput, mapping: chosen });
      restoreOutput = result.text;
      restoreSummary = `已恢复 ${result.replaced.length} 类占位符，${result.unused_mappings.length} 类映射未使用。${result.unknown_placeholders.length ? ` 未知占位符：${result.unknown_placeholders.join("、")}` : ""}`;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = "";
    }
  }
</script>

<div class="app-shell">
  <aside class="sidebar">
    <div class="brand">
      <ShieldCheck size={24} strokeWidth={1.7} /><span>PrivacyLLM</span>
    </div>
    <nav aria-label="主导航">
      {#each navigation as item}<button
          class:active={tab === item.id}
          onclick={() => changeTab(item.id)}
          aria-current={tab === item.id ? "page" : undefined}
          ><item.icon size={20} strokeWidth={1.7} />{item.label}</button
        >{/each}
    </nav>
    <div class="sidebar-bottom">
      <span class="status-dot"></span><span>本地处理</span><small
        >{model?.available ? "语义模型已加载" : "快速模式就绪"}</small
      >
    </div>
  </aside>
  <main>
    {#if tab === "redact"}
      <header class="page-header">
        <div>
          <h1>脱敏工作台</h1>
          <p>识别、复核，再安全地发送给 AI。</p>
        </div>
        <button class="button" onclick={example}>使用示例</button>
      </header>
      <div class="workspace">
        <section class="panel editor-panel">
          <div class="panel-heading">
            <h2>原始文本</h2>
            <button
              class="text-button"
              disabled={!source || !!busy}
              onclick={() => {
                source = "";
                invalidate();
              }}>清空</button
            >
          </div>
          <textarea
            bind:this={sourceEditor}
            bind:value={source}
            oninput={invalidate}
            disabled={!!busy}
            maxlength="100000"
            spellcheck="false"
            aria-label="原始文本"
            placeholder="粘贴需要发送给外部 AI 的文本…"></textarea>
          <div class="editor-meta">
            <span>{cpLength(source).toLocaleString()} 字符 / 50,000</span
            ><button
              class="text-button"
              disabled={!source || !!busy}
              onmousedown={(event) => event.preventDefault()}
              onclick={addSelection}><Plus size={13} />标记选中文字</button
            >
          </div>
          {#if entities.length}<details class="preview-details">
              <summary>识别预览 · 点击文字复核</summary><Highlight
                text={source}
                {entities}
                onselect={focusEntity}
              />
            </details>{/if}
          <div class="editor-actions">
            <div class="mode-selector">
              <label
                ><input
                  type="radio"
                  name="mode"
                  value="quick"
                  bind:group={mode}
                  disabled={!!busy}
                />快速识别</label
              ><label title="首次使用会加载本地模型"
                ><input
                  type="radio"
                  name="mode"
                  value="semantic"
                  bind:group={mode}
                  disabled={!!busy}
                />语义增强</label
              >
            </div>
            <button
              class="button primary"
              onclick={analyze}
              disabled={!!busy || !source.trim()}
              >{#if busy === "analyze"}<LoaderCircle
                  class="spin"
                  size={15}
                />{/if}{busy === "analyze"
                ? "正在识别"
                : "识别敏感信息"}</button
            >
          </div>
          {#if mode === "semantic" && !model?.installed}<p class="helper">
              首次使用前，请到“设置与模型”导入或下载模型。
            </p>{/if}
        </section>
        <section class="panel editor-panel">
          <div class="panel-heading">
            <h2>脱敏结果</h2>
            <div class="button-group">
              <button
                class="icon-button"
                aria-label="复制结果"
                title="复制结果"
                onclick={() => copy(output)}
                disabled={!output}><Copy size={16} /></button
              ><button
                class="button small"
                onclick={exportMapping}
                disabled={!mapping}><Download size={14} />导出映射</button
              >
            </div>
          </div>
          <div
            bind:this={outputEditor}
            class="output-editor"
            role="textbox"
            aria-label="脱敏结果"
            aria-readonly="true"
            tabindex="0"
          >
            {#if output}{#each outputParts as part}{#if /^\[[A-Z][A-Z_]*_\d{3,}\]$/.test(part)}<mark
                    >{part}</mark
                  >{:else}{part}{/if}{/each}{:else}<div class="empty-editor">
                <FileText size={30} strokeWidth={1.2} /><strong
                  >复核之后，生成脱敏文本</strong
                ><span>敏感内容将替换为稳定占位符。</span>
              </div>{/if}
          </div>
          {#if outputSelection}<button
              class="button small"
              disabled={!!busy}
              onmousedown={(event) => event.preventDefault()}
              onclick={markOutputSelection}
              ><Plus size={14} />将选中文字补充脱敏</button
            >{/if}
          <div class="output-footer">
            {#if mapping}<Check size={16} /><span
                >当前会话映射已就绪{!output ? " · 结果待重新生成" : ""}</span
              >{:else}<Circle size={14} /><span>等待生成脱敏映射</span>{/if}
          </div>
          {#if output}<button
              class="text-button restore-link"
              onclick={() => {
                restoreInput = output;
                changeTab("restore");
              }}>使用当前映射恢复文本 →</button
            >{/if}
        </section>
        <aside class="panel review-panel">
          <div class="panel-heading">
            <div>
              <h2>识别结果</h2>
              <p>
                {entities.length
                  ? `${entities.length} 项候选 · 已选 ${selected.length} 项`
                  : "等待识别"}
              </p>
            </div>
          </div>
          {#if entities.length}<div class="review-tools">
              <button class="text-button" onclick={selectAll} disabled={!!busy}
                >选择无冲突项</button
              ><button
                class="text-button"
                onclick={() => {
                  entities = entities.map((e) => ({ ...e, selected: false }));
                  output = "";
                }}>全部取消</button
              >
            </div>{/if}
          <div class="entity-list">
            {#each entities as entity (entity.id)}<div
                class="entity-row"
                class:focused={activeId === entity.id}
              >
                <input
                  type="checkbox"
                  aria-label={`脱敏 ${entity.text}`}
                  checked={entity.selected}
                  disabled={!!busy}
                  onchange={(event) =>
                    toggleEntity(
                      entity,
                      event.currentTarget.checked,
                      event.currentTarget,
                    )}
                /><button
                  class="entity-content"
                  onclick={() => focusEntity(entity.id)}
                  ><span
                    >{labels[entity.entity_type]}{#if entity.conflict}<small
                        class="conflict-label">重叠</small
                      >{/if}</span
                  ><strong>{entity.text}</strong><small
                    >{sourceLabel(entity.source)}</small
                  ></button
                >
              </div>{:else}<div class="empty-review">
                <ShieldCheck size={30} strokeWidth={1.2} />
                <p>识别出的敏感信息<br />会在这里逐项展示。</p>
              </div>{/each}
          </div>
          {#if active}<section class="entity-detail">
              <div class="panel-heading">
                <h3>所选项详情</h3>
                <button
                  class="icon-button danger"
                  aria-label="删除此项"
                  onclick={() => {
                    entities = entities.filter((e) => e.id !== activeId);
                    activeId = "";
                    output = "";
                  }}><Trash2 size={15} /></button
                >
              </div>
              <label
                >类型<select bind:value={draft.entity_type} disabled={!!busy}
                  >{#each Object.entries(labels) as [value, label]}<option
                      {value}>{label}</option
                    >{/each}</select
                ></label
              >
              <div class="field-pair">
                <label
                  >起始位置<input
                    type="number"
                    min="0"
                    bind:value={draft.start}
                    disabled={!!busy}
                  /></label
                ><label
                  >结束位置<input
                    type="number"
                    min="1"
                    bind:value={draft.end}
                    disabled={!!busy}
                  /></label
                >
              </div>
              <p class="selected-text">{draftText}</p>
              {#if active.reason}<p class="helper">
                  {active.reason}
                </p>{/if}<button
                class="button small"
                onclick={applyDetail}
                disabled={!!busy}>应用修改</button
              >
            </section>{/if}
          <button
            class="button primary generate-button"
            onclick={anonymize}
            disabled={!!busy || !selected.length}
            >{busy === "anonymize" ? "正在生成" : "生成脱敏文本"}</button
          >
        </aside>
      </div>
    {:else if tab === "restore"}
      <header class="page-header">
        <div>
          <h1>恢复文本</h1>
          <p>用本地映射恢复 AI 返回内容中的占位符。</p>
        </div>
      </header>
      <div class="restore-grid">
        <section class="panel editor-panel">
          <div class="panel-heading"><h2>包含占位符的文本</h2></div>
          <textarea
            bind:value={restoreInput}
            oninput={() => {
              restoreOutput = "";
              restoreSummary = "";
            }}
            aria-label="待恢复文本"
            placeholder="粘贴 AI 返回的内容…"
            spellcheck="false"></textarea>
          <div class="mapping-input">
            <label class="button small"
              >导入映射<input
                type="file"
                accept=".json,application/json"
                onchange={readMapping}
              /></label
            ><span
              >{importedMapping
                ? importedName
                : mapping
                  ? "使用当前会话映射"
                  : "尚无可用映射"}</span
            >{#if importedMapping}<button
                class="text-button"
                onclick={() => {
                  importedMapping = null;
                  importedName = "";
                  restoreOutput = "";
                }}>使用当前会话</button
              >{/if}
          </div>
          <button
            class="button primary"
            onclick={restore}
            disabled={!!busy ||
              !restoreInput.trim() ||
              !(importedMapping ?? mapping)}>恢复文本</button
          >
        </section>
        <section class="panel editor-panel">
          <div class="panel-heading">
            <h2>恢复结果</h2>
            <button
              class="button small"
              disabled={!restoreOutput}
              onclick={() => copy(restoreOutput)}><Copy size={14} />复制</button
            >
          </div>
          <textarea
            readonly
            value={restoreOutput}
            aria-label="恢复结果"
            placeholder="恢复后的文本显示在这里。"></textarea>
          <p class="helper">{restoreSummary || "原文和映射均在本机处理。"}</p>
        </section>
      </div>
    {:else if tab === "dictionary"}<DictionaryPanel />
    {:else}<SettingsPanel {model} {refreshModel} />{/if}
    {#if error}<div class="message error" role="alert">
        {error}<button aria-label="关闭提示" onclick={() => (error = "")}
          >×</button
        >
      </div>{/if}
    {#if notice}<div class="message success" role="status">{notice}</div>{/if}
    <footer>
      正文仅在本机处理 · 发送前请复核{#if !isTauri()}<span
          >界面预览 · 文本处理请使用桌面版</span
        >{/if}
    </footer>
  </main>
</div>
