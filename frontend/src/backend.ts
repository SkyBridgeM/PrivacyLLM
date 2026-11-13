import { invoke, isTauri } from "@tauri-apps/api/core";
export { isTauri };
export async function call<T>(
  command: string,
  args: Record<string, unknown> = {},
): Promise<T> {
  if (!isTauri())
    throw new Error("此页面是界面预览。请启动 PrivacyLLM 桌面应用以处理文本。");
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw new Error(
      typeof error === "string"
        ? error
        : error instanceof Error
          ? error.message
          : "操作失败，请重试",
    );
  }
}
