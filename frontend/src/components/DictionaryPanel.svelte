<script lang="ts">
  import { onMount } from "svelte";
  import { Plus, Trash2, Save } from "@lucide/svelte";
  import { call } from "../backend";
  import { labels, type DictionaryEntry } from "../types";
  let entries = $state<DictionaryEntry[]>([]);
  let busy = $state(false);
  let error = $state("");
  let notice = $state("");
  let loaded = $state(false);
  onMount(() => {
    void load();
  });
  async function load() {
    try {
      entries = await call("get_dictionary");
      loaded = true;
    } catch (e) {
      error = (e as Error).message;
    }
  }
  async function save() {
    busy = true;
    error = "";
    notice = "";
    try {
      await call("save_dictionary", { entries });
      notice = "词典已保存，下一次识别时生效。";
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<header class="page-header">
  <div>
    <h1>业务词典</h1>
    <p>让项目、客户和部门等专有名称始终被识别。</p>
  </div>
  <button
    class="button"
    disabled={!loaded || busy}
    onclick={() => {
      entries = [
        ...entries,
        { value: "", entity_type: "PROJECT", enabled: true, selected: true },
      ];
      notice = "";
    }}><Plus size={16} />新增条目</button
  >
</header>
<section class="panel dictionary-panel">
  <div class="panel-heading">
    <div>
      <h2>本地关键词</h2>
      <p>保存时保留上一版本备份。停用条目不会参与识别。</p>
    </div>
  </div>
  <div class="dictionary-table">
    <div class="dictionary-columns">
      <span>启用</span><span>关键词</span><span>类型</span><span>默认脱敏</span
      ><span></span>
    </div>
    {#each entries as entry, index}<div class="dictionary-row">
        <input
          type="checkbox"
          bind:checked={entry.enabled}
          aria-label={`启用条目 ${index + 1}`}
        /><input
          bind:value={entry.value}
          aria-label={`关键词 ${index + 1}`}
          maxlength="500"
          placeholder="输入项目名、机构名等"
        /><select
          bind:value={entry.entity_type}
          aria-label={`条目类型 ${index + 1}`}
          >{#each Object.entries(labels) as [value, label]}<option {value}
              >{label}</option
            >{/each}</select
        ><input
          type="checkbox"
          bind:checked={entry.selected}
          aria-label={`默认脱敏条目 ${index + 1}`}
        /><button
          class="icon-button danger"
          aria-label={`删除条目 ${index + 1}`}
          onclick={() => (entries = entries.filter((_, i) => i !== index))}
          ><Trash2 size={16} /></button
        >
      </div>{:else}<div class="large-empty">
        {loaded
          ? "还没有关键词。添加业务名称后，快速模式即可识别。"
          : "正在读取本地词典…"}
      </div>{/each}
  </div>
  <div class="panel-actions">
    <span class="helper">{entries.length} 个条目</span><button
      class="button primary"
      onclick={save}
      disabled={busy || !loaded}
      ><Save size={15} />{busy ? "正在保存" : "保存词典"}</button
    >
  </div>
</section>
{#if error}<div class="message error" role="alert">
    {error}
  </div>{/if}{#if notice}<div class="message success" role="status">
    {notice}
  </div>{/if}
