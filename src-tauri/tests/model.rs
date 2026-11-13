use privacyllm::{core::*, model::ModelManager};
use std::path::PathBuf;
#[tokio::test]
async fn missing_model_has_clear_error_and_does_not_spawn_process() {
    let temp = tempfile::tempdir().unwrap();
    let runtime = ModelManager::new(
        temp.path().join("missing-server"),
        temp.path().join("missing.gguf"),
    );
    assert!(runtime.load().await.is_err());
    assert!(!runtime.status().available);
    runtime.stop();
    runtime.stop();
}
#[test]
fn invalid_import_does_not_replace_existing_model() {
    let dir = tempfile::tempdir().unwrap();
    let model = dir.path().join("semantic.gguf");
    std::fs::write(&model, b"GGUFexisting").unwrap();
    let source = dir.path().join("wrong.gguf");
    std::fs::write(&source, b"bad!").unwrap();
    let runtime = ModelManager::new(dir.path().join("engine"), model.clone());
    assert!(runtime.import_model(source).is_err());
    assert_eq!(std::fs::read(model).unwrap(), b"GGUFexisting");
}
#[tokio::test]
#[ignore = "Requires local GGUF, llama.cpp and macOS Metal access"]
async fn real_local_model_round_trip_and_unload() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf();
    let runtime = ModelManager::new(
        std::env::var_os("PRIVACYLLM_TEST_ENGINE_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.join(".runtime/llama.cpp/llama-server")),
        std::env::var_os("PRIVACYLLM_TEST_MODEL_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.join(".runtime/models/semantic.gguf")),
    );
    let started = std::time::Instant::now();
    runtime.load().await.unwrap();
    println!("Rust model load: {:?}", started.elapsed());
    assert!(runtime.status().available);
    let source = "😀张敏是星河科技有限公司的项目经理，负责北辰计划。联系电话13812345678。";
    let started = std::time::Instant::now();
    let semantic = runtime.analyze(source).await.unwrap();
    println!("Rust inference: {:?}", started.elapsed());
    assert!(semantic
        .iter()
        .any(|e| e.text == "张敏" && e.entity_type == "PERSON"));
    let mut entities = recognize(source, &[], &[]).unwrap();
    entities.extend(semantic);
    let result = anonymize(source, merge(entities)).unwrap();
    assert!(!result.text.contains("张敏"));
    assert_eq!(restore(&result.text, &result.mapping).unwrap().text, source);
    runtime.stop();
    assert!(!runtime.status().available);
}
