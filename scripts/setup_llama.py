"""Install a project-local llama.cpp runtime and GGUF model on macOS."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / ".runtime"
VERSION = "b12340"
ENGINE_HASHES = {
    "arm64": "f4414a7224a2fef9e785c8673f0574be78aa914652099b40ef66890f7474e686",
    "x86_64": "f1e83a37961e69e3468244fa95c98a11f1cdd8f454a4a2bdb094c36c53b4a2ba",
}
MODEL_URL = (
    "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/"
    "e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_K_M.gguf"
)
MODEL_SHA256 = "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url: str, destination: Path, checksum: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and sha256(destination) == checksum:
        return
    partial = destination.with_suffix(destination.suffix + ".part")
    subprocess.run(
        ["curl", "--fail", "--location", "--retry", "3", "--connect-timeout", "30",
         "--continue-at", "-", "--output", str(partial), url],
        check=True,
    )
    if sha256(partial) != checksum:
        partial.unlink()
        raise ValueError("下载文件 SHA-256 校验失败，请重试")
    partial.replace(destination)


def install_engine(arch: str) -> None:
    engine = RUNTIME_DIR / "llama.cpp"
    marker = engine / ".privacyllm-version"
    if (engine / "llama-server").is_file() and marker.is_file() and marker.read_text() == VERSION:
        return
    suffix = "arm64" if arch == "arm64" else "x64"
    name = f"llama-{VERSION}-bin-macos-{suffix}.tar.gz"
    archive = RUNTIME_DIR / "downloads" / name
    print(f"安装 llama.cpp {VERSION}（{suffix}）…", flush=True)
    download(
        f"https://github.com/ggml-org/llama.cpp/releases/download/{VERSION}/{name}",
        archive, ENGINE_HASHES[arch],
    )
    with tempfile.TemporaryDirectory(dir=RUNTIME_DIR) as staging:
        with tarfile.open(archive) as bundle:
            bundle.extractall(staging, filter="data")
        extracted = Path(staging) / f"llama-{VERSION}"
        if not (extracted / "llama-server").is_file():
            raise ValueError("推理引擎压缩包中没有 llama-server")
        shutil.copytree(extracted, engine, dirs_exist_ok=True)
    marker.write_text(VERSION)


def install_model(source: Path | None) -> None:
    destination = RUNTIME_DIR / "models" / "semantic.gguf"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source is not None:
        source = source.expanduser().resolve(strict=True)
        with source.open("rb") as stream:
            if stream.read(4) != b"GGUF":
                raise ValueError("--model-file 必须指向 GGUF 模型文件")
        if source != destination.resolve():
            print("复制本地 GGUF 模型（保留原文件）…", flush=True)
            partial = destination.with_suffix(".gguf.part")
            shutil.copyfile(source, partial)
            partial.replace(destination)
    elif not destination.is_file():
        print("下载 Qwen3.5-4B Q4_K_M（约 2.74 GB），支持断点续传…", flush=True)
        download(MODEL_URL, destination, MODEL_SHA256)
    with destination.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError("本地模型不是有效 GGUF 文件，请重新安装")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-file", type=Path, help="复制已有 GGUF 模型，跳过下载")
    args = parser.parse_args()
    arch = platform.machine()
    if platform.system() != "Darwin" or arch not in ENGINE_HASHES:
        parser.error("此安装脚本仅支持 macOS arm64 / x86_64；当前优先验证 Apple Silicon")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    install_engine(arch)
    install_model(args.model_file)
    print("安装完成。运行 uv run python scripts/run_local.py，无需 Ollama。")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        raise SystemExit(f"安装失败：{exc}") from exc
