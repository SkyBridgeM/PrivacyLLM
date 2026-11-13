/** Install the pinned Mac engine for development/builds. No Python or Homebrew. */
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import {
  access,
  mkdir,
  readFile,
  writeFile,
  rename,
  mkdtemp,
  rm,
  cp,
} from "node:fs/promises";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { createWriteStream } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
const version = "b12340";
const hashes = {
  arm64: "f4414a7224a2fef9e785c8673f0574be78aa914652099b40ef66890f7474e686",
  x64: "f1e83a37961e69e3468244fa95c98a11f1cdd8f454a4a2bdb094c36c53b4a2ba",
};
if (process.platform !== "darwin" || !hashes[process.arch])
  throw new Error("当前构建流程仅支持 Mac。");
const root = path.resolve(import.meta.dirname, "..", ".runtime");
const engine = path.join(root, "llama.cpp");
try {
  await access(path.join(engine, "llama-server"));
  if (
    (
      await readFile(path.join(engine, ".privacyllm-version"), "utf8")
    ).trim() === version
  ) {
    console.log(`llama.cpp ${version} 已就绪。`);
    process.exit(0);
  }
} catch {}
await mkdir(path.join(root, "downloads"), { recursive: true });
const name = `llama-${version}-bin-macos-${process.arch}.tar.gz`;
const archive = path.join(root, "downloads", name);
async function hash(file) {
  const digest = createHash("sha256");
  for await (const chunk of createReadStream(file)) digest.update(chunk);
  return digest.digest("hex");
}
let valid = false;
try {
  valid = (await hash(archive)) === hashes[process.arch];
} catch {}
if (!valid) {
  console.log(`下载本地推理引擎 ${version}…`);
  const response = await fetch(
    `https://github.com/ggml-org/llama.cpp/releases/download/${version}/${name}`,
  );
  if (!response.ok || !response.body)
    throw new Error(`引擎下载失败：HTTP ${response.status}`);
  const partial = archive + ".part";
  await pipeline(Readable.fromWeb(response.body), createWriteStream(partial));
  if ((await hash(partial)) !== hashes[process.arch]) {
    await rm(partial);
    throw new Error("引擎 SHA-256 校验失败。");
  }
  await rename(partial, archive);
}
const staging = await mkdtemp(path.join(root, ".engine-"));
try {
  execFileSync("tar", ["-xzf", archive, "-C", staging, "--strip-components=1"]);
  await access(path.join(staging, "llama-server"));
  await cp(staging, engine, { recursive: true });
  await writeFile(path.join(engine, ".privacyllm-version"), version);
} finally {
  await rm(staging, { recursive: true, force: true });
}
console.log("本地引擎安装完成。模型可在 App 中下载或导入。");
