use crate::core::{self, Entity, Result};
use reqwest::Client;
use serde::Serialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    net::TcpListener,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    time::{Duration, Instant},
};
use uuid::Uuid;

pub const MODEL_URL:&str="https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_K_M.gguf";
pub const MODEL_HASH: &str = "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4";
pub const MODEL_BYTES: u64 = 2740937888;
#[derive(Clone, Serialize, Default)]
pub struct Download {
    pub active: bool,
    pub received: u64,
    pub total: u64,
    pub error: Option<String>,
}
#[derive(Serialize)]
pub struct Status {
    pub available: bool,
    pub installed: bool,
    pub engine_available: bool,
    pub loading: bool,
    pub model: String,
    pub message: String,
    pub download: Download,
}
#[derive(Clone)]
struct Connection {
    url: String,
    key: String,
}
pub struct ModelManager {
    pub engine: PathBuf,
    pub model: PathBuf,
    process: Mutex<Option<Child>>,
    connection: Mutex<Option<Connection>>,
    loading: AtomicBool,
    downloading: AtomicBool,
    cancel: AtomicBool,
    download: Mutex<Download>,
    last_error: Mutex<String>,
}
struct Flag<'a>(&'a AtomicBool);
impl Drop for Flag<'_> {
    fn drop(&mut self) {
        self.0.store(false, Ordering::SeqCst);
    }
}
impl ModelManager {
    pub fn new(engine: PathBuf, model: PathBuf) -> Self {
        Self {
            engine,
            model,
            process: Mutex::new(None),
            connection: Mutex::new(None),
            loading: AtomicBool::new(false),
            downloading: AtomicBool::new(false),
            cancel: AtomicBool::new(false),
            download: Mutex::new(Download {
                total: MODEL_BYTES,
                ..Default::default()
            }),
            last_error: Mutex::new(String::new()),
        }
    }
    fn local_client() -> Result<Client> {
        Client::builder()
            .no_proxy()
            .connect_timeout(Duration::from_secs(3))
            .timeout(Duration::from_secs(180))
            .build()
            .map_err(|e| e.to_string())
    }
    pub fn status(&self) -> Status {
        let alive = {
            let mut process = self.process.lock().unwrap();
            let alive = process
                .as_mut()
                .is_some_and(|child| matches!(child.try_wait(), Ok(None)));
            if !alive && process.is_some() {
                process.take();
                *self.connection.lock().unwrap() = None;
            }
            alive
        };
        let loading = self.loading.load(Ordering::SeqCst);
        let error = self.last_error.lock().unwrap().clone();
        Status {
            available: alive && !loading,
            installed: self.model.is_file(),
            engine_available: self.engine.is_file(),
            loading,
            model: "Qwen3.5 4B · 本地 GGUF".into(),
            message: if loading {
                "正在加载模型".into()
            } else if alive {
                "模型已加载，正文仅在本机处理".into()
            } else if !error.is_empty() {
                error
            } else if self.model.is_file() {
                "模型已安装，使用语义增强时加载".into()
            } else {
                "尚未安装模型，快速模式可直接使用".into()
            },
            download: self.download.lock().unwrap().clone(),
        }
    }
    pub fn stop(&self) {
        if let Some(mut child) = self.process.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *self.connection.lock().unwrap() = None;
    }
    pub async fn load(&self) -> Result<()> {
        if self
            .loading
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return Err("模型正在加载，请稍候".into());
        }
        let _guard = Flag(&self.loading);
        let result = self.load_inner().await;
        if let Err(error) = &result {
            self.stop();
            *self.last_error.lock().unwrap() = error.clone();
        } else {
            self.last_error.lock().unwrap().clear();
        }
        result
    }
    async fn load_inner(&self) -> Result<()> {
        if self.downloading.load(Ordering::SeqCst) {
            return Err("模型正在下载，请等待完成".into());
        }
        if self
            .process
            .lock()
            .unwrap()
            .as_mut()
            .is_some_and(|c| c.try_wait().ok().flatten().is_none())
        {
            return Ok(());
        }
        if !self.engine.is_file() {
            return Err("应用内推理引擎缺失，请重新安装完整应用".into());
        }
        if !self.model.is_file() {
            return Err("请先在“设置与模型”中下载或导入 GGUF 模型".into());
        }
        let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
        let port = listener.local_addr().map_err(|e| e.to_string())?.port();
        drop(listener);
        let key = Uuid::new_v4().to_string();
        let mut command = Command::new(&self.engine);
        command.args([
            "--model",
            self.model.to_str().ok_or("模型路径无效")?,
            "--host",
            "127.0.0.1",
            "--port",
            &port.to_string(),
            "--alias",
            "privacyllm-local",
            "--ctx-size",
            "32768",
            "--parallel",
            "1",
            "--gpu-layers",
            "99",
            "--jinja",
            "--reasoning-budget",
            "0",
            "--no-webui",
            "--log-disable",
            "--api-key",
            &key,
        ]);
        for (name, _) in std::env::vars() {
            if name.starts_with("LLAMA_") {
                command.env_remove(name);
            }
        }
        let child = command
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("无法启动本地推理引擎：{e}"))?;
        *self.process.lock().unwrap() = Some(child);
        let connection = Connection {
            url: format!("http://127.0.0.1:{port}"),
            key,
        };
        *self.connection.lock().unwrap() = Some(connection.clone());
        let client = Self::local_client()?;
        let deadline = Instant::now() + Duration::from_secs(120);
        while Instant::now() < deadline {
            let dead = self
                .process
                .lock()
                .unwrap()
                .as_mut()
                .and_then(|c| c.try_wait().ok().flatten());
            if dead.is_some() {
                return Err("模型启动失败，请检查 GGUF 兼容性、可用内存和 Metal 权限".into());
            }
            if self.connection.lock().unwrap().is_none() {
                return Err("模型加载已取消".into());
            }
            if let Ok(response) = client
                .get(format!("{}/health", connection.url))
                .timeout(Duration::from_secs(1))
                .send()
                .await
            {
                if response.status().is_success() {
                    return Ok(());
                }
            }
            tokio::time::sleep(Duration::from_millis(200)).await;
        }
        Err("模型加载超时，请检查可用内存后重试".into())
    }
    pub async fn analyze(&self, text: &str) -> Result<Vec<Entity>> {
        core::check_text(text, 50_000)?;
        self.load().await?;
        let connection = self
            .connection
            .lock()
            .unwrap()
            .clone()
            .ok_or("模型尚未加载")?;
        let kinds = [
            "PERSON",
            "ORGANIZATION",
            "PROJECT",
            "DEPARTMENT",
            "LOCATION",
            "BUSINESS_SECRET",
        ];
        let schema = json!({"type":"object","properties":{"entities":{"type":"array","items":{"type":"object","properties":{"text":{"type":"string"},"entity_type":{"type":"string","enum":kinds},"start":{"type":"integer","minimum":0},"end":{"type":"integer","minimum":1},"confidence":{"type":"number","minimum":0,"maximum":1},"reason":{"type":"string"}},"required":["text","entity_type","start","end","confidence","reason"],"additionalProperties":false}}},"required":["entities"],"additionalProperties":false});
        let prompt=format!("识别下方文本中仅靠格式规则难以发现的敏感信息。只标记确实应在发送给外部 AI 前隐藏的内容，避免泛化。text 必须逐字复制原文，start/end 是 Unicode 码点索引，end 不包含末位。类型仅使用 PERSON、ORGANIZATION、PROJECT、DEPARTMENT、LOCATION、BUSINESS_SECRET。不要识别泛称、普通日期、金额或公开常识。\n\n<document>\n{text}\n</document>");
        let response=Self::local_client()?.post(format!("{}/v1/chat/completions",connection.url)).bearer_auth(connection.key).json(&json!({"model":"privacyllm-local","stream":false,"chat_template_kwargs":{"enable_thinking":false},"response_format":{"type":"json_schema","json_schema":{"name":"entities","strict":true,"schema":schema}},"temperature":0,"max_tokens":8192,"messages":[{"role":"user","content":prompt}]})).send().await.map_err(|_|"本地模型请求失败或超时，请检查模型状态")?;
        if !response.status().is_success() {
            return Err("模型无法处理此输入，可能超出上下文容量或可用内存；请分段重试".into());
        }
        let response: Value = response.json().await.map_err(|_| "模型返回格式无效")?;
        let content = response["choices"][0]["message"]["content"]
            .as_str()
            .ok_or("模型返回格式无效")?;
        let parsed: Value = serde_json::from_str(content).map_err(|_| "模型未返回有效 JSON")?;
        let candidates = parsed["entities"].as_array().ok_or("模型返回格式无效")?;
        let mut result = Vec::new();
        let mut seen = std::collections::BTreeSet::new();
        for candidate in candidates {
            let Some(value) = candidate["text"].as_str().filter(|s| !s.is_empty()) else {
                continue;
            };
            let Some(kind) = candidate["entity_type"]
                .as_str()
                .filter(|s| kinds.contains(s))
            else {
                continue;
            };
            let mut start = candidate["start"]
                .as_u64()
                .and_then(|n| usize::try_from(n).ok())
                .unwrap_or(usize::MAX);
            let mut end = candidate["end"]
                .as_u64()
                .and_then(|n| usize::try_from(n).ok())
                .unwrap_or(usize::MAX);
            if core::char_slice(text, start, end) != Some(value) {
                let matches: Vec<_> = text.match_indices(value).take(2).collect();
                if matches.len() != 1 {
                    continue;
                }
                start = text[..matches[0].0].chars().count();
                end = start + value.chars().count();
            }
            if !seen.insert((start, end, kind.to_string())) {
                continue;
            }
            let e = Entity {
                id: Uuid::new_v4().to_string(),
                text: value.into(),
                entity_type: kind.into(),
                start,
                end,
                confidence: candidate["confidence"].as_f64().unwrap_or(0.).clamp(0., 1.),
                source: "semantic".into(),
                selected: true,
                replacement: None,
                reason: candidate["reason"].as_str().map(String::from),
                conflict: false,
            };
            if e.validate().is_ok() {
                result.push(e);
            }
        }
        Ok(result)
    }
    pub fn cancel_download(&self) {
        self.cancel.store(true, Ordering::SeqCst);
    }
    pub async fn download(&self) -> Result<()> {
        if self
            .downloading
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return Err("已有模型下载任务".into());
        }
        let _guard = Flag(&self.downloading);
        self.cancel.store(false, Ordering::SeqCst);
        *self.download.lock().unwrap() = Download {
            active: true,
            total: MODEL_BYTES,
            ..Default::default()
        };
        let result = self.download_inner().await;
        let mut status = self.download.lock().unwrap();
        status.active = false;
        status.error = result.as_ref().err().cloned();
        result
    }
    async fn download_inner(&self) -> Result<()> {
        if self.loading.load(Ordering::SeqCst) || self.process.lock().unwrap().is_some() {
            return Err("请先卸载模型再下载".into());
        }
        fs::create_dir_all(self.model.parent().ok_or("模型路径无效")?)
            .map_err(|e| e.to_string())?;
        let partial = self.model.with_extension("gguf.part");
        let mut offset = partial.metadata().map(|m| m.len()).unwrap_or(0);
        if offset > MODEL_BYTES {
            fs::remove_file(&partial).map_err(|e| e.to_string())?;
            offset = 0;
        }
        if offset < MODEL_BYTES {
            let client = Client::builder()
                .connect_timeout(Duration::from_secs(30))
                .read_timeout(Duration::from_secs(60))
                .build()
                .map_err(|e| e.to_string())?;
            let mut request = client.get(MODEL_URL);
            if offset > 0 {
                request = request.header("Range", format!("bytes={offset}-"));
            }
            let mut response = request
                .send()
                .await
                .map_err(|_| "下载连接失败，请检查网络后重试")?;
            if !response.status().is_success() {
                return Err(format!("模型下载失败：HTTP {}", response.status()));
            }
            if offset > 0 && response.status() == reqwest::StatusCode::PARTIAL_CONTENT {
                let range = response
                    .headers()
                    .get("content-range")
                    .and_then(|s| s.to_str().ok())
                    .unwrap_or("");
                if !range.starts_with(&format!("bytes {offset}-")) {
                    return Err("下载服务器返回了不匹配的续传范围".into());
                }
            } else {
                offset = 0;
            }
            let mut file = OpenOptions::new()
                .create(true)
                .write(true)
                .truncate(offset == 0)
                .append(offset > 0)
                .open(&partial)
                .map_err(|e| e.to_string())?;
            self.download.lock().unwrap().received = offset;
            while let Some(chunk) = response
                .chunk()
                .await
                .map_err(|_| "下载中断，可再次点击继续下载")?
            {
                if self.cancel.load(Ordering::SeqCst) {
                    return Err("下载已暂停，再次下载会从断点继续".into());
                }
                offset += chunk.len() as u64;
                if offset > MODEL_BYTES {
                    return Err("下载文件大小异常".into());
                }
                file.write_all(&chunk).map_err(|e| e.to_string())?;
                self.download.lock().unwrap().received = offset;
            }
            file.sync_all().map_err(|e| e.to_string())?;
        }
        if self.cancel.load(Ordering::SeqCst) {
            return Err("下载已暂停".into());
        }
        if partial.metadata().map_err(|e| e.to_string())?.len() != MODEL_BYTES {
            return Err("下载文件不完整，请继续下载".into());
        }
        if hash_file(&partial)? != MODEL_HASH {
            let _ = fs::remove_file(&partial);
            return Err("模型校验失败，请重新下载".into());
        }
        fs::rename(&partial, &self.model).map_err(|e| e.to_string())?;
        Ok(())
    }
    pub fn import_model(&self, path: PathBuf) -> Result<()> {
        if self
            .downloading
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return Err("已有模型下载或导入任务".into());
        }
        let _guard = Flag(&self.downloading);
        if self.loading.load(Ordering::SeqCst) || self.process.lock().unwrap().is_some() {
            return Err("请先停止模型加载并卸载模型".into());
        }
        let mut file = File::open(&path).map_err(|e| e.to_string())?;
        let mut header = [0; 4];
        file.read_exact(&mut header).map_err(|e| e.to_string())?;
        if &header != b"GGUF" {
            return Err("请选择兼容的 GGUF 模型文件".into());
        }
        if let (Ok(source), Ok(destination)) = (path.canonicalize(), self.model.canonicalize()) {
            if source == destination {
                return Ok(());
            }
        }
        fs::create_dir_all(self.model.parent().ok_or("模型路径无效")?)
            .map_err(|e| e.to_string())?;
        let partial = self.model.with_extension("importing");
        fs::copy(&path, &partial).map_err(|e| e.to_string())?;
        fs::rename(partial, &self.model).map_err(|e| e.to_string())?;
        Ok(())
    }
}
impl Drop for ModelManager {
    fn drop(&mut self) {
        self.stop();
    }
}
pub fn hash_file(path: &std::path::Path) -> Result<String> {
    let mut file = File::open(path).map_err(|e| e.to_string())?;
    let mut hash = Sha256::new();
    let mut buffer = vec![0; 1024 * 1024];
    loop {
        let n = file.read(&mut buffer).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        hash.update(&buffer[..n]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn status_reaps_exited_process_and_allows_model_import() {
        let dir = tempfile::tempdir().unwrap();
        let source = dir.path().join("source.gguf");
        std::fs::write(&source, b"GGUFtest").unwrap();
        let runtime = ModelManager::new(dir.path().join("engine"), dir.path().join("model.gguf"));
        let mut child = Command::new("/usr/bin/true").spawn().unwrap();
        child.wait().unwrap();
        *runtime.process.lock().unwrap() = Some(child);
        assert!(!runtime.status().available);
        runtime.import_model(source).unwrap();
        assert!(runtime.status().installed);
    }
}
