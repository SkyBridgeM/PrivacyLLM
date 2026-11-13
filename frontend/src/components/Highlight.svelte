<script lang="ts">
  import { type Entity } from "../types";
  let {
    text,
    entities,
    onselect,
  }: { text: string; entities: Entity[]; onselect: (id: string) => void } =
    $props();
  let pieces = $derived.by(() => {
    const characters = Array.from(text);
    const slice = (start: number, end?: number) =>
      characters.slice(start, end).join("");
    const ordered = [...entities].sort(
      (a, b) => a.start - b.start || b.end - a.end,
    );
    const result: { text: string; entity?: Entity }[] = [];
    let cursor = 0;
    for (const entity of ordered) {
      if (entity.start < cursor) continue;
      result.push({ text: slice(cursor, entity.start) });
      result.push({ text: slice(entity.start, entity.end), entity });
      cursor = entity.end;
    }
    result.push({ text: slice(cursor) });
    return result;
  });
</script>

<div class="highlight-preview">
  {#each pieces as piece}{#if piece.entity}<button
        class:chosen={piece.entity.selected}
        class:conflict={piece.entity.conflict}
        title="点击复核此项"
        onclick={() => onselect(piece.entity!.id)}>{piece.text}</button
      >{:else}{piece.text}{/if}{/each}
</div>

<style>
  .highlight-preview {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    line-height: 1.95;
    font-size: 14px;
    padding: 16px;
    background: #fafbfc;
    border-radius: 7px;
    max-height: 180px;
    overflow: auto;
  }
  .highlight-preview button {
    font: inherit;
    padding: 0;
    border: 0;
    border-bottom: 2px solid #adb5bd;
    background: none;
    border-radius: 1px;
    cursor: pointer;
    color: inherit;
  }
  .highlight-preview button.chosen {
    background: #dceee9;
    border-color: #167469;
  }
  .highlight-preview button.conflict {
    background: #fff1d9;
    border-color: #c78d29;
  }
</style>
