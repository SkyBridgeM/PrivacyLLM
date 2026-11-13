import { mkdir, readdir, copyFile, access } from "node:fs/promises";
import path from "node:path";
const root = path.resolve(import.meta.dirname, "..");
const source = path.join(root, ".runtime/llama.cpp");
const target = path.join(root, "src-tauri/resources/llama.cpp");
try {
  await access(path.join(source, "llama-server"));
} catch {
  throw new Error(
    "缺少 llama.cpp。请先运行 uv run python scripts/setup_llama.py，或将兼容引擎放入 .runtime/llama.cpp。",
  );
}
await mkdir(target, { recursive: true });
for (const name of await readdir(source)) {
  if (
    name === "llama-server" ||
    name.includes(".dylib") ||
    name.endsWith(".metal") ||
    name.startsWith("LICENSE")
  ) {
    await copyFile(path.join(source, name), path.join(target, name));
  }
}
console.log("已准备本地 llama.cpp 资源；模型独立存放，不打入应用包。");
