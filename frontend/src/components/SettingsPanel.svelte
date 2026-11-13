<script lang="ts">
  import { onMount } from "svelte";
  import { open } from "@tauri-apps/plugin-dialog";
  import {
    Download,
    FolderOpen,
    LoaderCircle,
    Square,
    Play,
    Save,
  } from "@lucide/svelte";
  import { call } from "../backend";
  import {
    labels,
    type Settings,
    type CustomRule,
    type ModelStatus,
  } from "../types";
  let {
    model,
    refreshModel,
  }: { model: ModelStatus | null; refreshModel: () => Promise<void> } =
    $props();
  let settings = $state<Settings | null>(null);
  let rulesRaw = $state("[]");
  let dataDir = $state("");
  let busy = $state("");
  let error = $state("");
  let notice = $state("");
  let progress = $derived(
    model?.download.total
      ? Math.min(100, (100 * model.download.received) / model.download.total)
      : 0,
  );
  onMount(() => {
    void load();
  });
  async function load() {
    try {
      settings = await call("get_settings");
      rulesRaw = JSON.stringify(await call<CustomRule[]>("get_rules"), null, 2);
      dataDir = await call("data_directory");
    } catch (e) {
      error = (e as Error).message;
    }
  }
  async function perform(
    name: string,
    action: () => Promise<unknown>,
    message: string,
  ) {
    busy = name;
    error = "";
    notice = "";
    try {
      await action();
      notice = message;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = "";
      await refreshModel();
    }
  }
  async function importModel() {
    try {
      const path = await open({
        title: "选择本地 GGUF 模型",
        multiple: false,
        filters: [{ name: "GGUF 模型", extensions: ["gguf"] }],
      });
      if (typeof path === "string")
        await perform(
          "import",
          () => call("import_model", { path }),
          "模型已导入，点击“加载模型”可验证兼容性。",
        );
    } catch (e) {
      error = (e as Error).message;
    }
  }
  async function download() {
    if (
      model?.installed &&
      !confirm("下载默认模型会替换已安装模型，是否继续？")
    )
      return;
    await perform(
      "download",
      () => call("download_model"),
      "模型下载完成，SHA-256 校验通过。",
    );
  }
  async function saveRules() {
    await perform(
      "rules",
      async () => {
        const rules = JSON.parse(rulesRaw);
        if (!Array.isArray(rules)) throw new Error("规则须为 JSON 数组。");
        await call("save_rules", { rules });
      },
      "自定义规则已保存。",
    );
  }
  async function importConfig() {
    try {
      const path = await open({
        title: "选择旧版 config 目录",
        directory: true,
        multiple: false,
      });
      if (
        typeof path === "string" &&
        confirm("将导入旧版词典、规则和默认策略，并备份当前配置。是否继续？")
      )
        await perform(
          "config",
          async () => {
            await call("import_config", { path });
            await load();
          },
          "旧版配置已导入。",
        );
    } catch (e) {
      error = (e as Error).message;
    }
  }
</script>

<header class="page-header">
  <div>
    <h1>设置与模型</h1>
    <p>管理本地推理、默认脱敏策略和识别规则。</p>
  </div>
</header>
<div class="settings-layout">
  <section class="panel model-panel">
    <div class="panel-heading">
      <div>
        <h2>本地语义模型</h2>
        <p>Qwen3.5 4B · llama.cpp · 按需加载</p>
      </div>
      <span class="model-state" class:ready={model?.available}
        ><span class="status-dot"></span>{model?.available
          ? "已加载"
          : model?.loading
            ? "加载中"
            : model?.installed
              ? "已安装"
              : "未安装"}</span
      >
    </div>
    <p class="model-description">
      快速模式不需要模型。使用语义增强时加载；暂时不用时可卸载，释放推理内存。正文仅发送到应用管理的本机推理进程。
    </p>
    <div class="model-status" role="status">
      {#if model?.loading || busy === "load" || busy === "import"}<LoaderCircle
          size={16}
          class="spin"
        />{/if}{busy === "import"
        ? "正在复制模型文件，请稍候…"
        : (model?.message ?? "正在读取模型状态…")}
    </div>
    {#if model?.download.active || busy === "download"}<div
        class="download-progress"
      >
        <progress max="100" value={progress}></progress><span
          >{progress.toFixed(1)}% · {(
            (model?.download.received ?? 0) / 1e9
          ).toFixed(2)} / 2.74 GB</span
        ><button
          class="text-button"
          onclick={() =>
            call("cancel_download").catch((e) => (error = e.message))}
          >暂停下载</button
        >
      </div>{/if}
    {#if model?.download.error && !busy}<p class="message error" role="alert">
        {model.download.error}
      </p>{/if}
    <div class="button-group model-actions">
      <button
        class="button primary"
        disabled={!model?.installed ||
          !!busy ||
          model?.available ||
          model?.loading}
        onclick={() =>
          perform("load", () => call("load_model"), "模型已就绪。")}
        ><Play size={15} />加载模型</button
      ><button
        class="button"
        disabled={!model?.available || !!busy}
        onclick={() =>
          perform(
            "unload",
            () => call("unload_model"),
            "模型已卸载，推理内存已释放。",
          )}><Square size={14} />卸载模型</button
      ><button
        class="button"
        disabled={!!busy ||
          model?.available ||
          model?.loading ||
          model?.download.active}
        onclick={importModel}><FolderOpen size={15} />导入 GGUF</button
      ><button
        class="button"
        disabled={!!busy ||
          model?.available ||
          model?.loading ||
          model?.download.active}
        onclick={download}><Download size={15} />下载默认模型</button
      >
    </div>
    <p class="helper">
      默认模型约 2.74
      GB，支持断点续传与文件校验。首次安装需联网，安装后可离线使用。自选 GGUF
      的兼容性需加载验证。
    </p>
    {#if model && !model.engine_available}<p class="message error">
        应用内推理引擎缺失，请安装完整应用包。
      </p>{/if}
  </section>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <h2>默认脱敏策略</h2>
        <p>识别结果中，各类型是否默认勾选。</p>
      </div>
    </div>
    <div class="settings-grid">
      {#if settings}{#each Object.entries(labels) as [kind, label]}<label
            ><input
              type="checkbox"
              bind:checked={
                settings.entity_defaults[kind as keyof typeof labels]
              }
            />{label}</label
          >{/each}{/if}
    </div>
    <div class="panel-actions">
      <button
        class="button primary"
        disabled={!settings || !!busy}
        onclick={() =>
          perform(
            "settings",
            () => call("save_settings", { settings }),
            "默认策略已保存。",
          )}><Save size={15} />保存策略</button
      >
    </div>
  </section>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <h2>自定义正则规则</h2>
        <p>保留旧版 JSON 结构；支持常用环视，限制回溯次数。</p>
      </div>
    </div>
    <textarea
      class="code-editor"
      bind:value={rulesRaw}
      aria-label="自定义规则 JSON"
      spellcheck="false"></textarea>
    <details class="rule-help">
      <summary>规则格式与兼容性</summary>
      <pre>{JSON.stringify(
          [
            {
              name: "project_number",
              pattern: "YX-\\d{4}-\\d{3}",
              entity_type: "PROJECT",
              enabled: true,
              selected: true,
              test_samples: ["YX-2026-001"],
            },
          ],
          null,
          2,
        )}</pre>
      <p>
        部分 Python
        专用语法不受支持，保存时会明确报错。资源限制采用回溯次数与表达式大小上限，不再使用
        Python 的 50 毫秒超时。
      </p>
    </details>
    <div class="panel-actions">
      <button
        class="button primary"
        disabled={!!busy || !settings}
        onclick={saveRules}>保存规则</button
      >
    </div>
  </section>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <h2>本地数据</h2>
        <p>配置与模型独立于应用安装包，更新应用时继续保留。</p>
      </div>
    </div>
    <p class="data-path">{dataDir || "正在读取配置目录…"}</p>
    <button class="button" disabled={!!busy} onclick={importConfig}
      ><FolderOpen size={15} />导入旧版配置</button
    >
    <p class="helper">
      选择旧项目中的 config
      文件夹。当前配置会先保留备份，原文件不修改。映射文件仍以明文 JSON
      导出，请妥善保存。
    </p>
  </section>
</div>
{#if error}<div class="message error" role="alert">
    {error}
  </div>{/if}{#if notice}<div class="message success" role="status">
    {notice}
  </div>{/if}
