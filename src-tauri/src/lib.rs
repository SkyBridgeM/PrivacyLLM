pub mod core;
pub mod model;
pub mod store;
use core::{Anonymized, CustomRule, DictionaryEntry, Entity, MappingDocument, Restored};
use serde::Serialize;
use std::{
    path::PathBuf,
    sync::{Arc, Mutex},
};
use tauri::{Manager, State};

pub struct AppState {
    pub store: Mutex<store::Store>,
    pub model: model::ModelManager,
}
#[derive(Serialize)]
struct Analysis {
    text: String,
    entities: Vec<Entity>,
    semantic_available: bool,
}
#[tauri::command]
async fn analyze_text(
    state: State<'_, Arc<AppState>>,
    text: String,
    use_llm: bool,
) -> core::Result<Analysis> {
    let (dictionary, rules, settings) = {
        let store = state.store.lock().unwrap();
        (store.dictionary()?, store.rules()?, store.settings()?)
    };
    let input = text.clone();
    let mut entities =
        tauri::async_runtime::spawn_blocking(move || core::recognize(&input, &dictionary, &rules))
            .await
            .map_err(|e| e.to_string())??;
    if use_llm {
        let semantic = state.model.analyze(&text).await?;
        let semantic: Vec<_> = semantic
            .into_iter()
            .filter(|e| {
                !entities.iter().any(|rule| {
                    rule.source.contains("regex")
                        && !matches!(
                            rule.entity_type.as_str(),
                            "PERSON"
                                | "ORGANIZATION"
                                | "PROJECT"
                                | "DEPARTMENT"
                                | "LOCATION"
                                | "BUSINESS_SECRET"
                                | "CUSTOM"
                        )
                        && e.start < rule.end
                        && rule.start < e.end
                })
            })
            .collect();
        entities.extend(semantic);
        entities = core::merge(entities);
    }
    for entity in &mut entities {
        entity.selected = !entity.conflict
            && settings
                .entity_defaults
                .get(&entity.entity_type)
                .copied()
                .unwrap_or(entity.selected);
    }
    Ok(Analysis {
        text,
        entities,
        semantic_available: use_llm,
    })
}
#[tauri::command]
async fn anonymize_text(text: String, entities: Vec<Entity>) -> core::Result<Anonymized> {
    tauri::async_runtime::spawn_blocking(move || core::anonymize(&text, entities))
        .await
        .map_err(|e| e.to_string())?
}
#[tauri::command]
async fn restore_text(text: String, mapping: MappingDocument) -> core::Result<Restored> {
    tauri::async_runtime::spawn_blocking(move || core::restore(&text, &mapping))
        .await
        .map_err(|e| e.to_string())?
}
#[tauri::command]
fn get_dictionary(state: State<'_, Arc<AppState>>) -> core::Result<Vec<DictionaryEntry>> {
    state.store.lock().unwrap().dictionary()
}
#[tauri::command]
fn save_dictionary(
    state: State<'_, Arc<AppState>>,
    entries: Vec<DictionaryEntry>,
) -> core::Result<()> {
    for entry in &entries {
        entry.validate()?;
    }
    state
        .store
        .lock()
        .unwrap()
        .save("dictionary.json", &entries)
}
#[tauri::command]
fn get_settings(state: State<'_, Arc<AppState>>) -> core::Result<store::Settings> {
    state.store.lock().unwrap().settings()
}
#[tauri::command]
fn save_settings(state: State<'_, Arc<AppState>>, settings: store::Settings) -> core::Result<()> {
    settings.validate()?;
    state.store.lock().unwrap().save("settings.json", &settings)
}
#[tauri::command]
fn get_rules(state: State<'_, Arc<AppState>>) -> core::Result<Vec<CustomRule>> {
    state.store.lock().unwrap().rules()
}
#[tauri::command]
async fn save_rules(state: State<'_, Arc<AppState>>, rules: Vec<CustomRule>) -> core::Result<()> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut names = std::collections::BTreeSet::new();
        for rule in &rules {
            rule.compile()?;
            if !names.insert(&rule.name) {
                return Err("规则名称不得重复".into());
            }
        }
        shared
            .store
            .lock()
            .unwrap()
            .save("custom_regex_rules.json", &rules)
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
fn model_status(state: State<'_, Arc<AppState>>) -> model::Status {
    state.model.status()
}
#[tauri::command]
async fn load_model(state: State<'_, Arc<AppState>>) -> core::Result<()> {
    state.model.load().await
}
#[tauri::command]
fn unload_model(state: State<'_, Arc<AppState>>) -> core::Result<()> {
    state.model.stop();
    Ok(())
}
#[tauri::command]
async fn download_model(state: State<'_, Arc<AppState>>) -> core::Result<()> {
    state.model.download().await
}
#[tauri::command]
fn cancel_download(state: State<'_, Arc<AppState>>) {
    state.model.cancel_download();
}
#[tauri::command]
async fn import_model(state: State<'_, Arc<AppState>>, path: String) -> core::Result<()> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || shared.model.import_model(path.into()))
        .await
        .map_err(|e| e.to_string())?
}
#[tauri::command]
fn export_mapping(path: String, mapping: MappingDocument) -> core::Result<()> {
    use std::io::Write;
    mapping.validate()?;
    let path = PathBuf::from(path);
    if path.extension().and_then(|s| s.to_str()) != Some("json") {
        return Err("映射文件请使用 .json 扩展名".into());
    }
    let mut file = tempfile::NamedTempFile::new_in(path.parent().ok_or("导出路径无效")?)
        .map_err(|e| e.to_string())?;
    serde_json::to_writer_pretty(&mut file, &mapping).map_err(|e| e.to_string())?;
    file.flush().map_err(|e| e.to_string())?;
    file.as_file().sync_all().map_err(|e| e.to_string())?;
    file.persist(path).map_err(|e| e.to_string())?;
    Ok(())
}
#[tauri::command]
async fn import_config(state: State<'_, Arc<AppState>>, path: String) -> core::Result<()> {
    let shared = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        shared
            .store
            .lock()
            .unwrap()
            .import_directory(&PathBuf::from(path))
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
fn data_directory(state: State<'_, Arc<AppState>>) -> String {
    state.store.lock().unwrap().dir.display().to_string()
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let data = app.path().app_data_dir()?;
            let store = store::Store::new(data.join("config"))?;
            let resources = app.path().resource_dir()?;
            let project = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .unwrap()
                .to_path_buf();
            let engine = if cfg!(debug_assertions) {
                project.join(".runtime/llama.cpp/llama-server")
            } else {
                resources.join("resources/llama.cpp/llama-server")
            };
            let model = data.join("models/semantic.gguf");
            app.manage(Arc::new(AppState {
                store: Mutex::new(store),
                model: model::ModelManager::new(engine, model),
            }));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            analyze_text,
            anonymize_text,
            restore_text,
            get_dictionary,
            save_dictionary,
            get_settings,
            save_settings,
            get_rules,
            save_rules,
            model_status,
            load_model,
            unload_model,
            download_model,
            cancel_download,
            import_model,
            export_mapping,
            import_config,
            data_directory
        ])
        .build(tauri::generate_context!())
        .expect("无法初始化 PrivacyLLM 桌面应用");
    app.run(|handle, event| {
        if matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            if let Some(state) = handle.try_state::<Arc<AppState>>() {
                state.model.cancel_download();
                state.model.stop();
            }
        }
    });
}

#[cfg(test)]
mod command_tests {
    use super::*;
    use serde_json::{json, Value};
    use tauri::test::{get_ipc_response, mock_builder, mock_context, noop_assets, MockRuntime};

    fn invoke(
        window: &tauri::WebviewWindow<MockRuntime>,
        command: &str,
        args: Value,
    ) -> std::result::Result<Value, Value> {
        get_ipc_response(
            window,
            tauri::webview::InvokeRequest {
                cmd: command.into(),
                callback: tauri::ipc::CallbackFn(0),
                error: tauri::ipc::CallbackFn(1),
                url: "tauri://localhost".parse().unwrap(),
                body: tauri::ipc::InvokeBody::Json(args),
                headers: Default::default(),
                invoke_key: tauri::test::INVOKE_KEY.into(),
            },
        )
        .map(|response| response.deserialize().unwrap())
    }
    #[test]
    fn real_tauri_command_round_trip_and_camel_case_arguments() {
        let dir = tempfile::tempdir().unwrap();
        let app = mock_builder()
            .manage(Arc::new(AppState {
                store: Mutex::new(store::Store::new(dir.path().join("config")).unwrap()),
                model: model::ModelManager::new(
                    dir.path().join("server"),
                    dir.path().join("model.gguf"),
                ),
            }))
            .invoke_handler(tauri::generate_handler![
                analyze_text,
                anonymize_text,
                restore_text,
                model_status
            ])
            .build(mock_context(noop_assets()))
            .unwrap();
        let window = tauri::WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let source = "😀联系人13812345678";
        let analysis = invoke(
            &window,
            "analyze_text",
            json!({"text":source,"useLlm":false}),
        )
        .unwrap();
        assert_eq!(analysis["entities"][0]["start"], 4);
        let redacted = invoke(
            &window,
            "anonymize_text",
            json!({"text":source,"entities":analysis["entities"]}),
        )
        .unwrap();
        assert_eq!(redacted["text"], "😀联系人[PHONE_001]");
        let restored = invoke(
            &window,
            "restore_text",
            json!({"text":redacted["text"],"mapping":redacted["mapping"]}),
        )
        .unwrap();
        assert_eq!(restored["text"], source);
        assert!(invoke(
            &window,
            "analyze_text",
            json!({"text":source,"useLlm":true})
        )
        .is_err());
        assert!(
            !invoke(&window, "model_status", json!({})).unwrap()["available"]
                .as_bool()
                .unwrap()
        );
    }
}
