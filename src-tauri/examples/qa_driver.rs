//! Browser QA adapter. Executes real Rust core operations; never bundled in the app.
use privacyllm::{core::*, model::ModelManager, store::Store};
use serde_json::{json, Value};
use std::{
    io::{self, Read},
    path::PathBuf,
};
fn execute(request: Value) -> Result<Value> {
    let dir = std::env::var("PRIVACYLLM_QA_DATA").map_err(|e| e.to_string())?;
    let store = Store::new(dir.into())?;
    let args = &request["args"];
    match request["command"].as_str().ok_or("missing command")? {
        "model_status" => {
            let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .unwrap()
                .to_path_buf();
            serde_json::to_value(
                ModelManager::new(
                    root.join(".runtime/llama.cpp/llama-server"),
                    root.join(".runtime/models/semantic.gguf"),
                )
                .status(),
            )
            .map_err(|e| e.to_string())
        }
        "get_dictionary" => serde_json::to_value(store.dictionary()?).map_err(|e| e.to_string()),
        "save_dictionary" => {
            let entries: Vec<DictionaryEntry> =
                serde_json::from_value(args["entries"].clone()).map_err(|e| e.to_string())?;
            for e in &entries {
                e.validate()?;
            }
            store.save("dictionary.json", &entries)?;
            Ok(Value::Null)
        }
        "get_rules" => serde_json::to_value(store.rules()?).map_err(|e| e.to_string()),
        "save_rules" => {
            let entries: Vec<CustomRule> =
                serde_json::from_value(args["rules"].clone()).map_err(|e| e.to_string())?;
            for r in &entries {
                r.compile()?;
            }
            store.save("custom_regex_rules.json", &entries)?;
            Ok(Value::Null)
        }
        "get_settings" => serde_json::to_value(store.settings()?).map_err(|e| e.to_string()),
        "data_directory" => Ok(json!(store.dir)),
        "analyze_text" => {
            if args["useLlm"].as_bool().unwrap_or(false) {
                return Err("Browser QA uses the rule core. Real inference is covered by the Rust integration test.".into());
            }
            let text = args["text"].as_str().ok_or("missing text")?;
            let settings = store.settings()?;
            let mut entities = recognize(text, &store.dictionary()?, &store.rules()?)?;
            for e in &mut entities {
                e.selected = !e.conflict
                    && settings
                        .entity_defaults
                        .get(&e.entity_type)
                        .copied()
                        .unwrap_or(e.selected);
            }
            Ok(json!({"text":text,"entities":entities,"semantic_available":false}))
        }
        "anonymize_text" => serde_json::to_value(anonymize(
            args["text"].as_str().ok_or("missing text")?,
            serde_json::from_value(args["entities"].clone()).map_err(|e| e.to_string())?,
        )?)
        .map_err(|e| e.to_string()),
        "restore_text" => serde_json::to_value(restore(
            args["text"].as_str().ok_or("missing text")?,
            &serde_json::from_value(args["mapping"].clone()).map_err(|e| e.to_string())?,
        )?)
        .map_err(|e| e.to_string()),
        _ => Err("unsupported QA command".into()),
    }
}
fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    let result = serde_json::from_str(&input)
        .map_err(|e| e.to_string())
        .and_then(execute);
    println!(
        "{}",
        match result {
            Ok(value) => json!({"ok":value}),
            Err(error) => json!({"error":error}),
        }
    );
}
